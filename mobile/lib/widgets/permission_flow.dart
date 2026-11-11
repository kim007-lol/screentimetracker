import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/l10n/l10n.dart';
import '../core/state/app_state.dart';
import 'ui.dart';

/// Izin diminta bertahap, satu per satu, hanya saat fitur terkait diaktifkan
/// (docs/06 bagian Kepatuhan Play Store). Tiap izin didahului penjelasan penuh layar.
Future<void> requestUsageAccess(BuildContext context, WidgetRef ref) async {
  final s = ref.read(l10nProvider);
  final ok = await _disclosure(
    context,
    title: s.t('Izinkan akses pemakaian', 'Allow usage access'),
    body: s.t(
      'Rekap dan HP membutuhkan data pemakaian dari Android.\n\n'
          'Dibaca: nama app, durasi, dan jumlah buka.\n'
          'Tidak dibaca: isi layar, pesan, atau kata sandi.\n\n'
          'Data tetap di HP ini dan tidak dikirim ke server.',
      'Recap and HP need usage data from Android.\n\n'
          'Read: app name, duration, and open count.\n'
          'Not read: screen content, messages, or passwords.\n\n'
          'Data stays on this phone and is never uploaded.',
    ),
    confirm: s.t('Buka pengaturan', 'Open settings'),
  );
  if (ok != true) return;
  await ref.read(usageServiceProvider).openUsageSettings();
}

Future<void> requestAccessibility(BuildContext context, WidgetRef ref) async {
  final s = ref.read(l10nProvider);
  final ok = await _disclosure(
    context,
    title: s.t(
      'Hitung scroll lewat Aksesibilitas',
      'Count scrolls with Accessibility',
    ),
    body: s.t(
      'Layanan ini menghitung scroll di app yang kamu pilih. Hanya jenis kejadian '
          'dan nama paket yang dibaca. Teks, kata sandi, pesan, dan isi layar tidak '
          'dibaca.\n\n'
          'Daftar app bisa diubah di Kelola aplikasi. Layanan bisa dimatikan kapan '
          'saja.',
      'This service counts scrolls in the apps you select. It reads only the event '
          'type and package name. It does not read text, passwords, messages, or '
          'screen content.\n\n'
          'Change the app list in Manage apps. You can turn the service off '
          'anytime.',
    ),
    confirm: s.t('Saya mengerti, lanjut', 'I understand, continue'),
  );
  if (ok != true) return;
  await ref.read(usageServiceProvider).openAccessibilitySettings();
}

Future<void> requestOverlay(BuildContext context, WidgetRef ref) async {
  final s = ref.read(l10nProvider);
  final ok = await _disclosure(
    context,
    title: s.t('Tampilkan di atas aplikasi lain', 'Show above other apps'),
    body: s.t(
      'Floating Pill menampilkan durasi dan hitungan scroll di atas app yang sedang '
          'dibuka, tanpa harus membuka Screen Time Tracker.\n\n'
          'Izin ini hanya dipakai untuk menggambar pill kecil. Bisa dicabut kapan '
          'saja.',
      'The Floating Pill shows duration and scroll counts above the app you are '
          'using, without opening Screen Time Tracker.\n\n'
          'This permission only draws the small pill. You can revoke it anytime.',
    ),
    confirm: s.t('Buka pengaturan', 'Open settings'),
  );
  if (ok != true) return;
  await ref.read(usageServiceProvider).openOverlaySettings();
}

Future<bool?> _disclosure(
  BuildContext context, {
  required String title,
  required String body,
  required String confirm,
}) {
  return Navigator.of(context).push<bool>(
    MaterialPageRoute(
      fullscreenDialog: true,
      builder: (_) =>
          _DisclosurePage(title: title, body: body, confirm: confirm),
    ),
  );
}

class _DisclosurePage extends ConsumerWidget {
  const _DisclosurePage({
    required this.title,
    required this.body,
    required this.confirm,
  });

  final String title;
  final String body;
  final String confirm;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final s = ref.watch(l10nProvider);
    return Scaffold(
      backgroundColor: t.bg,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(22, 24, 22, 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: t.heading(26)),
              const SizedBox(height: 18),
              Expanded(
                child: SingleChildScrollView(
                  child: TokenCard(child: Text(body, style: t.body(15))),
                ),
              ),
              const SizedBox(height: 18),
              TokenButton(
                label: confirm,
                onPressed: () => Navigator.of(context).pop(true),
              ),
              const SizedBox(height: 12),
              TokenButton(
                label: s.t('Nanti saja', 'Not now'),
                filled: false,
                onPressed: () => Navigator.of(context).pop(false),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
