import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../l10n/l10n.dart';
import '../state/app_state.dart';
import '../models/usage.dart';

/// Apakah izin minimum untuk Jeda Sadar sudah ada (overlay + akses pemakaian).
Future<bool> pausePrerequisitesMet(WidgetRef ref) async {
  final service = ref.read(usageServiceProvider);
  final results = await Future.wait([
    service.hasOverlay(),
    service.hasUsageAccess(),
  ]);
  return results[0] && results[1];
}

/// Nyalakan atau matikan Jeda Sadar dengan teks, tema, dan daftar app aktif.
/// Mengembalikan false bila layanan native menolak (mis. izin belum ada).
Future<bool> applyPause(WidgetRef ref, {required bool enable}) async {
  final service = ref.read(usageServiceProvider);
  if (!enable) {
    await service.hidePause();
    return true;
  }

  final game = ref.read(gameProvider);
  final s = ref.read(l10nProvider);
  final t = ref.read(tokensProvider);
  final hp = ref.read(hpProvider);
  final mood = ref.read(moodProvider);
  final now = DateTime.now();
  final stamp =
      '${now.day}/${now.month} '
      '${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}';
  final real =
      ref.read(usageProvider).asData?.value.source == UsageSource.android;
  final packages = game.monitoredPackages.toList()..sort();
  try {
    await service.setMonitoredApps(packages);
  } catch (_) {
    return false;
  }
  if (packages.isEmpty) {
    // Nothing would ever be paused. Report failure instead of claiming the
    // service is on while the overlay stays hidden.
    await service.hidePause();
    return false;
  }

  return service.showPause(
    packages: packages,
    delaySeconds: game.pauseSeconds,
    limits: game.appLimits,
    background: t.bg.toARGB32(),
    surface: t.surface.toARGB32(),
    ink: t.ink.toARGB32(),
    accent: t.primary.toARGB32(),
    radius: t.notched ? 4 : t.radius,
    titleTemplate: s.t('Mau ngapain di {app}?', 'What are you doing in {app}?'),
    autoTemplate: s.t(
      'Lanjut otomatis dalam {s} detik',
      'Continuing automatically in {s}s',
    ),
    cancelLabel: s.t('Ke layar utama', 'Go to home screen'),
    continueLabel: s.t('Lanjut', 'Continue'),
    note: s.t(
      'Tidak ada blokir paksa. Kamu tetap bisa lanjut.',
      'No forced block. You can still continue.',
    ),
    hpLine: real
        ? 'HP $hp/100 · ${s.moodLabel(mood)} · ${s.t('Saat sinkronisasi', 'At sync')} $stamp'
        : s.t(
            'Data HP nyata belum tersedia.',
            'Real HP data is not available yet.',
          ),
    appFallback: s.t('aplikasi ini', 'this app'),
    limitTitle: s.t(
      'Batas harian {app} tercapai',
      'Daily limit for {app} reached',
    ),
    limitNote: s.t(
      'Hari ini {used}m dari batas {limit}m.',
      'Today {used}m of your {limit}m limit.',
    ),
    limitPassLabel: s.t('Lanjut 5 menit', '5 more minutes'),
    limitCloseLabel: s.t('Ke layar utama', 'Go to home screen'),
  );
}
