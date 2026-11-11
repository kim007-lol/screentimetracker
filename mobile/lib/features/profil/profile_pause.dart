part of 'profil_screen.dart';

/// Jeda Sadar: jeda singkat sebelum app target terbuka (prd Bab 10.2).
class _PauseCard extends ConsumerStatefulWidget {
  const _PauseCard({required this.s});

  final L10n s;

  @override
  ConsumerState<_PauseCard> createState() => _PauseCardState();
}

class _PauseCardState extends ConsumerState<_PauseCard> {
  bool _busy = false;

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tokensProvider);
    final s = widget.s;
    final game = ref.watch(gameProvider);
    final status = ref.watch(permissionStatusProvider).asData?.value;
    final running = status?.pauseRunning ?? false;

    return TokenCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.hourglass_top_rounded, size: 20, color: t.ink),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  s.t('Jeda Sadar', 'Conscious Pause'),
                  style: t.heading(16),
                ),
              ),
              if (_busy)
                const SizedBox(
                  width: 22,
                  height: 22,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              else
                Switch.adaptive(
                  value: game.pauseEnabled,
                  activeThumbColor: t.primary,
                  onChanged: _toggle,
                ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            s.t(
              'Jeda muncul untuk app yang kamu pilih di Kelola aplikasi. '
                  'HP menunjukkan nilai saat sinkronisasi, bukan pengukuran langsung. Kamu tetap bisa lanjut.',
              'Pauses appear for apps selected in Manage apps. '
                  'HP shows the value at sync, not a live reading. You can still continue.',
            ),
            style: t.body(11, color: t.muted),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: Text(
                  s.t('Durasi jeda', 'Pause length'),
                  style: t.body(13, weight: FontWeight.w800),
                ),
              ),
              Text(
                '${game.pauseSeconds} ${s.t('detik', 'sec')}',
                style: t.number(13),
              ),
            ],
          ),
          Slider(
            value: game.pauseSeconds.toDouble(),
            min: Balancing.pauseMinSeconds.toDouble(),
            max: Balancing.pauseMaxSeconds.toDouble(),
            divisions: Balancing.pauseMaxSeconds - Balancing.pauseMinSeconds,
            activeColor: t.primary,
            label: '${game.pauseSeconds}s',
            onChanged: (v) =>
                ref.read(gameProvider.notifier).setPauseSeconds(v.round()),
            onChangeEnd: (v) async {
              if (!game.pauseEnabled) return;
              await applyPause(ref, enable: true);
            },
          ),
          if (game.pauseEnabled && !running)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                children: [
                  Icon(Icons.warning_amber_rounded, size: 16, color: t.hpTired),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      s.t(
                        'Layanan belum berjalan. Periksa izin overlay dan akses pemakaian.',
                        'The service is not running. Check overlay and usage access.',
                      ),
                      style: t.body(10, color: t.muted),
                    ),
                  ),
                ],
              ),
            ),
          Text(
            s.t(
              'Butuh izin "tampil di atas aplikasi lain" dan akses pemakaian. '
                  'Tidak ada blokir paksa, dan app yang sama tidak dijeda berulang.',
              'Needs "display over other apps" and usage access. Nothing is blocked '
                  'by force, and the same app is not paused repeatedly.',
            ),
            style: t.body(10, color: t.muted),
          ),
        ],
      ),
    );
  }

  Future<void> _toggle(bool value) async {
    final s = widget.s;
    if (value && ref.read(gameProvider).monitoredPackages.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            s.t(
              'Pilih minimal satu aplikasi di Kelola aplikasi sebelum menyalakan Jeda Sadar.',
              'Select at least one app in App management before turning on Conscious Pause.',
            ),
          ),
        ),
      );
      return;
    }
    setState(() => _busy = true);

    if (value) {
      final ready = await pausePrerequisitesMet(ref);
      if (!ready) {
        final service = ref.read(usageServiceProvider);
        final overlay = await service.hasOverlay();
        final usage = await service.hasUsageAccess();
        if (!mounted) return;
        setState(() => _busy = false);
        if (!overlay) await requestOverlay(context, ref);
        if (!usage) {
          if (!mounted) return;
          await requestUsageAccess(context, ref);
        }
        ref.invalidate(permissionStatusProvider);
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              s.t(
                'Setelah izin diberikan, aktifkan Jeda Sadar lagi di sini.',
                'Once permissions are granted, turn Conscious Pause on again here.',
              ),
            ),
          ),
        );
        return;
      }
    }

    final ok = await applyPause(ref, enable: value);
    ref.read(gameProvider.notifier).setPauseEnabled(value && ok);
    ref.invalidate(permissionStatusProvider);
    if (!mounted) return;
    setState(() => _busy = false);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          value
              ? (ok
                    ? s.t('Jeda Sadar aktif.', 'Conscious Pause is on.')
                    : s.t(
                        'Jeda Sadar gagal dimulai.',
                        'Conscious Pause could not start.',
                      ))
              : s.t('Jeda Sadar dimatikan.', 'Conscious Pause is off.'),
        ),
      ),
    );
  }
}
