import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../../core/l10n/l10n.dart';
import '../../core/models/backup_snapshot.dart';
import '../../core/models/pet.dart';
import '../../core/services/backup_service.dart';
import '../../core/state/app_state.dart';
import '../../core/state/duel_state.dart';
import '../../widgets/ui.dart';

/// Backup dan penghapusan dipisahkan dari pengaturan tampilan.
class PrivacyCard extends ConsumerStatefulWidget {
  const PrivacyCard({super.key});

  @override
  ConsumerState<PrivacyCard> createState() => _PrivacyCardState();
}

class _PrivacyCardState extends ConsumerState<PrivacyCard> {
  bool _busy = false;
  bool _collectionBusy = false;

  static const _exportPrefix = 'momo-backup-';

  BackupService get _backup => BackupService(
    preferences: ref.read(sharedPrefsProvider),
    history: ref.read(historyServiceProvider),
    usage: ref.read(usageServiceProvider),
  );

  String get _petName =>
      (ref.read(gameProvider).petFamily ?? PetFamily.momo).label;

  void _message(String text) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
    }
  }

  Future<void> _export({bool copy = false}) async {
    if (_busy) return;
    setState(() => _busy = true);
    final s = ref.read(l10nProvider);
    try {
      await ref.read(usageProvider.notifier).flushHistory();
      final snapshot = await _backup.export();
      final text = snapshot.encode();
      if (copy) {
        await Clipboard.setData(ClipboardData(text: text));
        _message(
          s.t(
            'Backup disalin. Simpan di tempat privat.',
            'Backup copied. Store it privately.',
          ),
        );
      } else {
        final date = DateTime.now().toIso8601String().substring(0, 10);
        final dir = await getTemporaryDirectory();
        final file = File(p.join(dir.path, '$_exportPrefix$date.json'));
        // Write the file ourselves so it can be deleted after the share sheet,
        // instead of leaving a full data copy in the cache directory.
        await file.writeAsString(text, flush: true);
        try {
          if (!mounted) return;
          final box = context.findRenderObject() as RenderBox?;
          await Share.shareXFiles(
            [
              XFile(
                file.path,
                mimeType: 'application/json',
                name: '$_exportPrefix$date.json',
              ),
            ],
            subject: '$_petName backup $date',
            sharePositionOrigin: box == null
                ? null
                : box.localToGlobal(Offset.zero) & box.size,
          );
        } finally {
          try {
            if (await file.exists()) await file.delete();
          } catch (_) {
            /* Best effort; the delete flow purges leftovers too. */
          }
        }
      }
    } catch (_) {
      _message(
        s.t(
          'Backup gagal dibuat. Data asli tidak diubah.',
          'Could not create backup. Original data was not changed.',
        ),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _import() async {
    if (_busy) return;
    final s = ref.read(l10nProvider);
    final input = TextEditingController();
    BackupSnapshot? snapshot;
    String? error;
    try {
      snapshot = await showDialog<BackupSnapshot>(
        context: context,
        builder: (ctx) => StatefulBuilder(
          builder: (ctx, setDialogState) => AlertDialog(
            title: Text(s.t('Impor backup JSON', 'Import JSON backup')),
            content: SingleChildScrollView(
              child: SizedBox(
                width: 420,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      s.t(
                        'Tempel isi backup $_petName. Data akan divalidasi sebelum ada perubahan.',
                        'Paste a $_petName backup. Data is validated before any changes.',
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: input,
                      minLines: 4,
                      maxLines: 8,
                      maxLength: 5 * 1024 * 1024,
                      decoration: InputDecoration(
                        labelText: 'JSON',
                        errorText: error,
                        counterText: '',
                      ),
                    ),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: Text(s.t('Batal', 'Cancel')),
              ),
              TextButton(
                onPressed: () {
                  try {
                    Navigator.pop(ctx, BackupSnapshot.decode(input.text));
                  } catch (_) {
                    setDialogState(
                      () => error = s.t(
                        'Backup tidak valid atau versinya tidak didukung.',
                        'Invalid backup or unsupported version.',
                      ),
                    );
                  }
                },
                child: Text(s.t('Periksa backup', 'Check backup')),
              ),
            ],
          ),
        ),
      );
    } finally {
      // Tunggu animasi dialog lepas dari tree sebelum controller dibuang.
      WidgetsBinding.instance.addPostFrameCallback((_) => input.dispose());
    }
    if (snapshot == null || !mounted) return;
    final confirmed = await _confirm(
      s.t('Ganti data lokal?', 'Replace local data?'),
      s.t(
        'Backup berisi ${snapshot.history.length} hari riwayat. Progres, pengaturan, dan riwayat saat ini akan diganti. Layanan tetap mati dan izin Android tidak ikut dipulihkan. Ekspor data sekarang dulu jika masih perlu.',
        'This backup contains ${snapshot.history.length} ${snapshot.history.length == 1 ? 'day' : 'days'} of history. Current progress, settings, and history will be replaced. Services stay off and Android permissions are not restored. Export current data first if you still need it.',
      ),
    );
    if (!confirmed || !mounted) return;
    setState(() => _busy = true);
    try {
      // Stop polling and wait for in-flight history writes before restore
      // swaps the database. setForeground(false) already drains and flushes.
      await ref.read(usageProvider.notifier).setForeground(false);
      await _backup.restore(snapshot);
      _message(
        s.t(
          'Backup dipulihkan. Tinjau izin sebelum menyalakan pengumpulan lagi.',
          'Backup restored. Review permissions before enabling collection again.',
        ),
      );
    } catch (error) {
      final incomplete =
          error is BackupRestoreException && error.rollbackErrors.isNotEmpty;
      _message(
        incomplete
            ? s.t(
                'Impor gagal dan data lama tidak pulih sepenuhnya. Periksa layanan di Profil, lalu coba lagi.',
                'Import failed and the old data did not fully come back. Check services in Profile, then try again.',
              )
            : s.t(
                'Impor gagal. Data lama dipulihkan dan layanan tetap mati.',
                'Import failed. Old data was restored and services stay off.',
              ),
      );
    } finally {
      // Both paths may have changed storage (including a failed import that
      // rolled back). Re-read every provider so the UI never keeps stale state.
      ref.invalidate(usageProvider);
      ref.invalidate(usageRangeProvider);
      ref.invalidate(historyProvider);
      ref.invalidate(duelPeersProvider);
      ref.invalidate(permissionStatusProvider);
      ref.invalidate(gameProvider);
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<bool> _confirm(String title, String body) async {
    final s = ref.read(l10nProvider);
    return await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: Text(title),
            content: Text(body),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: Text(s.t('Batal', 'Cancel')),
              ),
              TextButton(
                onPressed: () => Navigator.pop(ctx, true),
                child: Text(s.t('Lanjutkan', 'Continue')),
              ),
            ],
          ),
        ) ??
        false;
  }

  Future<void> _toggleCollection(bool enabled) async {
    if (_collectionBusy) return;
    final s = ref.read(l10nProvider);
    setState(() => _collectionBusy = true);
    try {
      if (enabled) {
        await ref.read(gameProvider.notifier).resumeCollection();
      } else {
        await ref.read(usageProvider.notifier).setForeground(false);
        await ref.read(gameProvider.notifier).pauseCollection();
      }
      ref.invalidate(permissionStatusProvider);
      _message(
        enabled
            ? s.t(
                'Pengumpulan aktif lagi.',
                'Collection is on again.',
              )
            : s.t(
                'Pengumpulan dihentikan. Data yang sudah ada tetap tersimpan.',
                'Collection is off. Existing data stays saved.',
              ),
      );
    } catch (_) {
      _message(
        s.t(
          'Pengumpulan tidak berubah. Coba lagi.',
          'Collection did not change. Try again.',
        ),
      );
    } finally {
      if (mounted) setState(() => _collectionBusy = false);
    }
  }

  Future<void> _purgeExports() async {
    final dir = await getTemporaryDirectory();
    await for (final entity in dir.list()) {
      final name = p.basename(entity.path);
      if (entity is File &&
          name.startsWith(_exportPrefix) &&
          name.endsWith('.json')) {
        try {
          await entity.delete();
        } catch (_) {
          /* Reported by the caller if any file survives. */
        }
      }
    }
  }

  Future<void> _delete() async {
    if (_busy) return;
    final s = ref.read(l10nProvider);
    final petName = _petName;
    final confirmed = await _confirm(
      s.t('Hapus semua data?', 'Delete all data?'),
      s.t(
        'Progres, Bank Waktu, pengaturan, kode duel, hit scroll, dan riwayat akan dihapus. Overlay dan pengingat berhenti. $petName tidak bisa menghapus riwayat sistem Android atau izin OS. Pengumpulan tetap mati sampai kamu setuju lagi. Tindakan ini tidak bisa dibatalkan.',
        '$petName progress, Time Bank, settings, duel codes, scroll counts, and local history will be deleted. Overlays and reminders stop. $petName cannot delete Android system history or OS permissions. Collection stays off until you consent again. This cannot be undone.',
      ),
    );
    if (!confirmed || !mounted) return;
    setState(() => _busy = true);
    try {
      await ref.read(gameProvider.notifier).deleteAllData();
      ref.invalidate(duelPeersProvider);
      var purgeFailed = false;
      try {
        await _purgeExports();
      } catch (_) {
        purgeFailed = true;
      }
      _message(
        purgeFailed
            ? s.t(
                'Data $petName terhapus, tetapi file backup sementara gagal dihapus. Hapus manual dari penyimpanan.',
                '$petName data is deleted, but temporary backup files could not be removed. Delete them from storage manually.',
              )
            : s.t(
                'Data $petName terhapus dan pengumpulan dihentikan.',
                '$petName data deleted; collection stopped.',
              ),
      );
    } catch (_) {
      _message(
        s.t(
          'Penghapusan belum selesai. Coba lagi; jangan anggap data sudah hilang.',
          'Deletion did not finish. Try again; do not assume the data is gone.',
        ),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tokensProvider);
    final s = ref.watch(l10nProvider);
    final collecting = ref.watch(
      gameProvider.select((g) => g.collectionEnabled),
    );
    return TokenCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            s.t('Privasi & backup', 'Privacy & backup'),
            style: t.heading(16),
          ),
          const SizedBox(height: 8),
          Text(
            s.t(
              'Data disimpan di HP ini. Tidak ada akun atau server. Backup berisi nama, pemakaian, dan progres; impor hanya membaca isi JSON, bukan izin Android.',
              'Data stays on this phone. No account or server. Backups contain your name, usage, and progress; import reads JSON only, not Android permissions.',
            ),
            style: t.body(11, color: t.muted),
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.only(bottom: 10),
            decoration: BoxDecoration(
              border: Border(
                bottom: BorderSide(color: t.ink.withValues(alpha: 0.10)),
              ),
            ),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        s.t('Pengumpulan pemakaian', 'Usage collection'),
                        style: t.body(13, weight: FontWeight.w800),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        collecting
                            ? s.t(
                                'Aktif. Matikan untuk berhenti mencatat.',
                                'On. Turn it off to stop recording.',
                              )
                            : s.t(
                                'Mati. Riwayat lama tetap tersimpan.',
                                'Off. Earlier history stays saved.',
                              ),
                        style: t.body(11, color: t.muted),
                      ),
                    ],
                  ),
                ),
                Switch(
                  value: collecting,
                  onChanged: _collectionBusy || _busy
                      ? null
                      : _toggleCollection,
                ),
              ],
            ),
          ),
          const SizedBox(height: 4),
          if (_busy)
            const Padding(
              padding: EdgeInsets.only(bottom: 12),
              child: LinearProgressIndicator(),
            ),
          TokenButton(
            label: s.t('Ekspor file backup', 'Export backup file'),
            icon: Icons.save_alt_rounded,
            filled: false,
            onPressed: _busy ? null : () => _export(),
          ),
          const SizedBox(height: 8),
          TokenButton(
            label: s.t('Salin backup JSON', 'Copy JSON backup'),
            icon: Icons.copy_rounded,
            filled: false,
            onPressed: _busy ? null : () => _export(copy: true),
          ),
          const SizedBox(height: 8),
          TokenButton(
            label: s.t('Impor backup JSON', 'Import JSON backup'),
            icon: Icons.restore_rounded,
            filled: false,
            onPressed: _busy ? null : _import,
          ),
          const SizedBox(height: 10),
          TokenButton(
            label: s.t('Hapus semua data', 'Delete all data'),
            icon: Icons.delete_outline_rounded,
            color: t.hpCritical,
            onPressed: _busy ? null : _delete,
          ),
        ],
      ),
    );
  }
}
