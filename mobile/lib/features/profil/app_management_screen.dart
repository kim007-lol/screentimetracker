import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/l10n/l10n.dart';
import '../../core/models/companion.dart';
import '../../core/services/pause_controller.dart';
import '../../core/services/usage_service.dart';
import '../../core/state/app_state.dart';
import '../../core/state/installed_apps_provider.dart';
import '../../widgets/permission_flow.dart';
import '../../widgets/ui.dart';

/// Daftar launcher, bukan hanya app yang pernah dipakai hari ini.
class AppManagementScreen extends ConsumerStatefulWidget {
  const AppManagementScreen({super.key});

  @override
  ConsumerState<AppManagementScreen> createState() =>
      _AppManagementScreenState();
}

class _AppManagementScreenState extends ConsumerState<AppManagementScreen> {
  String _query = '';
  bool _busy = false;

  Future<void> _toggle(String package, bool enabled) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await ref
          .read(gameProvider.notifier)
          .setMonitoredPackage(package, enabled);
      if (mounted) {
        final game = ref.read(gameProvider);
        if (game.monitoredPackages.isEmpty) {
          // Without a monitored app the pause overlay has nothing to show.
          // Turn the opted-in service off instead of reporting it as running.
          if (game.pauseEnabled) {
            ref.read(gameProvider.notifier).setPauseEnabled(false);
            await ref.read(usageServiceProvider).hidePause();
            ref.invalidate(permissionStatusProvider);
          }
          if (!mounted) return;
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                ref
                    .read(l10nProvider)
                    .t(
                      'Tidak ada aplikasi yang dipantau. Jeda Sadar dimatikan.',
                      'No monitored apps left. Conscious Pause is off.',
                    ),
              ),
            ),
          );
        } else if (game.pauseEnabled) {
          if (!await applyPause(ref, enable: true)) {
            throw StateError('Native settings not applied');
          }
        }
      }
    } catch (_) {
      if (mounted) {
        final s = ref.read(l10nProvider);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              s.t(
                'Pengaturan layanan belum diterapkan. Periksa izin lalu coba lagi.',
                'Service settings were not applied. Check permissions and retry.',
              ),
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _repairPause() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final ok = await applyPause(ref, enable: true);
      ref.invalidate(permissionStatusProvider);
      if (!mounted) return;
      final s = ref.read(l10nProvider);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            ok
                ? s.t(
                    'Layanan Jeda Sadar aktif.',
                    'The Conscious Pause service is running.',
                  )
                : s.t(
                    'Layanan belum bisa dijalankan. Periksa izin overlay dan akses pemakaian.',
                    'The service could not start. Check overlay and usage access.',
                  ),
          ),
        ),
      );
    } catch (_) {
      if (!mounted) return;
      final s = ref.read(l10nProvider);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            s.t(
              'Layanan belum bisa dijalankan. Periksa izin overlay dan akses pemakaian.',
              'The service could not start. Check overlay and usage access.',
            ),
          ),
        ),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _fixService(PermissionStatus status) async {
    if (!status.overlay) {
      await requestOverlay(context, ref);
    } else if (!status.usage) {
      await requestUsageAccess(context, ref);
    } else {
      await _repairPause();
    }
    ref.invalidate(permissionStatusProvider);
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tokensProvider);
    final s = ref.watch(l10nProvider);
    final game = ref.watch(gameProvider);
    final permission = ref.watch(permissionStatusProvider);
    final status = permission.asData?.value;
    final apps = ref.watch(installedAppsProvider);

    String? notice;
    String? noticeAction;
    VoidCallback? onNotice;
    if (status != null) {
      if (game.pauseEnabled &&
          game.monitoredPackages.isNotEmpty &&
          !status.pauseRunning) {
        notice = s.t(
          'Jeda Sadar aktif, tapi layanan belum berjalan. Batas belum ditegakkan.',
          'Conscious Pause is on, but the service is not running. Limits are not enforced.',
        );
        noticeAction = s.t('Perbaiki', 'Fix');
        onNotice = _busy ? null : () => _fixService(status);
      } else if (!status.accessibility) {
        notice = s.t(
          'Izin aksesibilitas mati. Hit scroll belum dihitung.',
          'Accessibility is off. Scroll counts are paused.',
        );
        noticeAction = s.t('Izinkan', 'Allow');
        onNotice = _busy
            ? null
            : () async {
                await requestAccessibility(context, ref);
                ref.invalidate(permissionStatusProvider);
              };
      }
    }
    return Scaffold(
      backgroundColor: t.bg,
      appBar: AppBar(
        title: Text(s.t('Kelola aplikasi', 'Manage apps')),
        actions: [
          IconButton(
            tooltip: s.t('Segarkan', 'Refresh'),
            onPressed: () => ref.invalidate(installedAppsProvider),
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  s.t(
                    'Centang app untuk Jeda Sadar dan hitungan scroll. Rekap tetap mencatat semua pemakaian. Tambahan waktu dari Bank Waktu hanya berlaku hari ini.',
                    'Check apps to pause and count scrolls. Recap still records all usage. Time Bank extensions last only for today.',
                  ),
                  style: t.body(12, color: t.muted),
                ),
                if (notice != null) ...[
                  const SizedBox(height: 12),
                  NoticeBanner(
                    message: notice,
                    actionLabel: noticeAction,
                    onAction: onNotice,
                  ),
                ],
                const SizedBox(height: 12),
                TextField(
                  onChanged: (value) =>
                      setState(() => _query = value.trim().toLowerCase()),
                  decoration: InputDecoration(
                    labelText: s.t(
                      'Cari nama atau paket',
                      'Search name or package',
                    ),
                    prefixIcon: const Icon(Icons.search_rounded),
                  ),
                ),
                if (!game.pauseEnabled)
                  Padding(
                    padding: const EdgeInsets.only(top: 10),
                    child: Text(
                      s.t(
                        'Jeda Sadar mati. Batas tersimpan, tapi tidak ditegakkan.',
                        'Conscious Pause is off. Limits are saved but not enforced.',
                      ),
                      style: t.body(11, color: t.muted),
                    ),
                  ),
              ],
            ),
          ),
          if (_busy) const LinearProgressIndicator(minHeight: 2),
          Expanded(
            child: apps.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (_, _) => Center(
                child: TextButton(
                  onPressed: () => ref.invalidate(installedAppsProvider),
                  child: Text(
                    s.t('Gagal memuat. Coba lagi', 'Load failed. Retry'),
                  ),
                ),
              ),
              data: (all) {
                final visible =
                    all
                        .where(
                          (a) => '${a['label']} ${a['packageName']}'
                              .toLowerCase()
                              .contains(_query),
                        )
                        .toList()
                      ..sort(
                        (a, b) => a['label']!.toLowerCase().compareTo(
                          b['label']!.toLowerCase(),
                        ),
                      );
                if (visible.isEmpty) {
                  return Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Text(
                        s.t(
                          all.isEmpty
                              ? 'Tidak ada app yang bisa ditampilkan di perangkat ini.'
                              : 'Tidak ada app yang cocok.',
                          all.isEmpty
                              ? 'No apps can be listed on this device.'
                              : 'No matching apps.',
                        ),
                        style: t.body(13, color: t.muted),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  );
                }
                return ListView.builder(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                  itemCount: visible.length,
                  itemBuilder: (context, index) {
                    final app = visible[index];
                    final pkg = app['packageName']!;
                    final selected = game.monitoredPackages.contains(pkg);
                    final category =
                        game.categoryOverrides[pkg] ??
                        kDefaultCategories[pkg] ??
                        UsageCategory.lainnya;
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: TokenCard(
                        padding: const EdgeInsets.all(8),
                        child: Column(
                          children: [
                            CheckboxListTile(
                              value: selected,
                              title: Text(app['label']!, style: t.heading(14)),
                              subtitle: Text(
                                pkg,
                                style: t.body(10, color: t.muted),
                              ),
                              onChanged: _busy
                                  ? null
                                  : (value) => _toggle(pkg, value ?? false),
                            ),
                            Wrap(
                              spacing: 12,
                              runSpacing: 4,
                              children: [
                                PopupMenuButton<UsageCategory>(
                                  tooltip: s.t('Kategori', 'Category'),
                                  initialValue: category,
                                  onSelected: (c) => ref
                                      .read(gameProvider.notifier)
                                      .setCategory(pkg, c),
                                  itemBuilder: (_) => UsageCategory.values
                                      .map(
                                        (c) => PopupMenuItem(
                                          value: c,
                                          child: Text(s.categoryLabel(c)),
                                        ),
                                      )
                                      .toList(),
                                  child: Padding(
                                    padding: const EdgeInsets.all(12),
                                    child: Text(
                                      s.categoryLabel(category),
                                      style: t.body(12),
                                    ),
                                  ),
                                ),
                                PopupMenuButton<int>(
                                  enabled: selected && !_busy,
                                  tooltip: s.t('Batas harian', 'Daily limit'),
                                  initialValue: game.appLimits[pkg] ?? 0,
                                  onSelected: (minutes) async {
                                    ref
                                        .read(gameProvider.notifier)
                                        .setAppLimit(pkg, minutes);
                                    if (ref.read(gameProvider).pauseEnabled) {
                                      final ok = await applyPause(
                                        ref,
                                        enable: true,
                                      );
                                      if (!ok && context.mounted) {
                                        ScaffoldMessenger.of(
                                          context,
                                        ).showSnackBar(
                                          SnackBar(
                                            content: Text(
                                              s.t(
                                                'Batas tersimpan, layanan belum diperbarui.',
                                                'Limit saved; service was not updated.',
                                              ),
                                            ),
                                          ),
                                        );
                                      }
                                    }
                                  },
                                  itemBuilder: (_) =>
                                      [0, 15, 30, 60, 90, 120, 180, 240, 480]
                                          .map(
                                            (m) => PopupMenuItem(
                                              value: m,
                                              child: Text(
                                                m == 0
                                                    ? s.t(
                                                        'Tanpa batas',
                                                        'No limit',
                                                      )
                                                    : s.t(
                                                        '$m menit',
                                                        '$m minutes',
                                                      ),
                                              ),
                                            ),
                                          )
                                          .toList(),
                                  child: Padding(
                                    padding: const EdgeInsets.all(12),
                                    child: Text(
                                      !selected
                                          ? s.t(
                                              'Tidak dipantau',
                                              'Not monitored',
                                            )
                                          : (game.appLimits[pkg] == null
                                                ? s.t('Tanpa batas', 'No limit')
                                                : s.t(
                                                    'Batas ${game.appLimits[pkg]}m',
                                                    'Limit ${game.appLimits[pkg]}m',
                                                  )),
                                      style: t.body(
                                        12,
                                        color: selected ? t.ink : t.muted,
                                      ),
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
