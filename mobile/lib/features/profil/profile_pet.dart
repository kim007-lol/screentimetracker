part of 'profil_screen.dart';

/// The pill is the only floating surface. Its form controls how much of the
/// companion rides along without turning the overlay on by itself.
class _PetCard extends ConsumerWidget {
  const _PetCard({
    required this.state,
    required this.s,
  });

  final _ProfilScreenState state;
  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final game = ref.watch(gameProvider);
    final pet = game.petFamily ?? PetFamily.momo;
    final status = ref.watch(permissionStatusProvider).asData?.value;

    return TokenCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                pet == PetFamily.drako
                    ? Icons.local_fire_department_rounded
                    : Icons.pets_rounded,
                size: 20,
                color: t.ink,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  s.t('Tampilan Floating Pill', 'Floating Pill look'),
                  style: t.body(14, weight: FontWeight.w800),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            s.t(
              'Satu maskot, bukan dua objek melayang. Bentuk hanya berlaku '
                  'saat pill aktif, dan tidak menyalakannya.',
              'One mascot, not two floating objects. The look only applies '
                  'while the pill is on and never turns it on.',
            ),
            style: t.body(11, color: t.muted),
          ),
          const SizedBox(height: 8),
          _FormChoice(
            s: s,
            value: game.pillForm,
            onChanged: state._setPillForm,
          ),
          const SizedBox(height: 6),
          Text(
            game.pillForm == PillForm.head
                ? s.t(
                    'Kepala di dalam pill. Ketuk pill dan maskot melebar jadi '
                        'badan penuh untuk menyapa, lalu menu terbuka.',
                    'A head inside the pill. Tap it and the mascot grows into '
                        'a full body to greet you before the menu opens.',
                  )
                : s.t(
                    'Badan penuh berdiri di samping pill sejak awal. Ketuk '
                        'untuk membuka menu.',
                    'The full body stands beside the pill from the start. Tap '
                        'to open the menu.',
                  ),
            style: t.body(11, color: t.muted),
          ),
          if (status != null) ...[
            const SizedBox(height: 4),
            Text(
              status.pillRunning
                  ? s.t('Pill sedang aktif.', 'The pill is on.')
                  : s.t(
                      'Pill nonaktif; bentuk ini dipakai saat dinyalakan.',
                      'The pill is off; this look is used when it starts.',
                    ),
              style: t.body(11, color: t.muted),
            ),
          ],
          const Divider(height: 24),
          Text(
            s.t('Animasi Floating Pill', 'Floating Pill animation'),
            style: t.body(13, weight: FontWeight.w800),
          ),
          const SizedBox(height: 6),
          _ModeChoice(
            s: s,
            value: game.pillAnimationMode,
            onChanged: state._setPillMode,
          ),
          const SizedBox(height: 8),
          Text(
            s.t(
              'Statis menghentikan loop dan memakai sprite ringan. Penuh '
                  'memutar rig GLB; pilih statis bila ingin lebih hemat daya.',
              'Static stops every loop and uses a light sprite. Full plays the '
                  'GLB rig; choose static when you want to save power.',
            ),
            style: t.body(11, color: t.muted),
          ),
        ],
      ),
    );
  }
}

class _FormChoice extends ConsumerWidget {
  const _FormChoice({
    required this.s,
    required this.value,
    required this.onChanged,
  });

  final L10n s;
  final PillForm value;
  final ValueChanged<PillForm> onChanged;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);

    Widget option(PillForm form, String label) {
      final active = form == value;
      return Expanded(
        child: Semantics(
          button: true,
          selected: active,
          label: label,
          child: GestureDetector(
            onTap: () => onChanged(form),
            child: Container(
              constraints: const BoxConstraints(minHeight: 44),
              alignment: Alignment.center,
              decoration: ShapeDecoration(
                color: active ? t.primary : t.surface,
                shape: t.shape(
                  radiusOverride: t.notched ? 3 : (t.radius > 0 ? 12 : 0),
                ),
              ),
              child: Text(
                label,
                style: t.body(12, weight: FontWeight.w800),
              ),
            ),
          ),
        ),
      );
    }

    return Row(
      children: [
        option(PillForm.head, s.t('Kepala', 'Head')),
        const SizedBox(width: 8),
        option(PillForm.body, s.t('Badan penuh', 'Full body')),
      ],
    );
  }
}

class _ModeChoice extends ConsumerWidget {
  const _ModeChoice({
    required this.s,
    required this.value,
    required this.onChanged,
  });

  final L10n s;
  final PetAnimationMode value;
  final ValueChanged<PetAnimationMode> onChanged;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);

    Widget option(PetAnimationMode mode, String label) {
      final active = mode == value;
      return Expanded(
        child: Semantics(
          button: true,
          selected: active,
          label: label,
          child: GestureDetector(
            onTap: () => onChanged(mode),
            child: Container(
              constraints: const BoxConstraints(minHeight: 44),
              alignment: Alignment.center,
              decoration: ShapeDecoration(
                color: active ? t.primary : t.surface,
                shape: t.shape(
                  radiusOverride: t.notched ? 3 : (t.radius > 0 ? 12 : 0),
                ),
              ),
              child: Text(
                label,
                style: t.body(12, weight: FontWeight.w800),
              ),
            ),
          ),
        ),
      );
    }

    return Row(
      children: [
        option(
          PetAnimationMode.flat,
          s.t('Statis (hemat)', 'Static (saver)'),
        ),
        const SizedBox(width: 8),
        option(PetAnimationMode.full, s.t('Penuh', 'Full')),
      ],
    );
  }
}
