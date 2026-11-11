import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/l10n/l10n.dart';
import '../core/models/companion.dart';
import '../core/models/pet.dart';
import '../core/state/app_state.dart';
import 'companion_3d.dart';
import 'ui.dart';

/// Layar perayaan saat wujud baru terbuka (Evolution Reveal, docs/03).
Future<void> showEvolutionReveal(BuildContext context, Stage stage) {
  return Navigator.of(context).push<void>(
    PageRouteBuilder<void>(
      opaque: true,
      transitionDuration: const Duration(milliseconds: 420),
      pageBuilder: (_, _, _) => _EvolutionPage(stage: stage),
      transitionsBuilder: (_, anim, _, child) =>
          FadeTransition(opacity: anim, child: child),
    ),
  );
}

class _EvolutionPage extends ConsumerStatefulWidget {
  const _EvolutionPage({required this.stage});

  final Stage stage;

  @override
  ConsumerState<_EvolutionPage> createState() => _EvolutionPageState();
}

class _EvolutionPageState extends ConsumerState<_EvolutionPage> {
  int _tick = 0;

  @override
  void initState() {
    super.initState();
    // Putar klip celebrate begitu model siap.
    Future<void>.delayed(const Duration(milliseconds: 1400), () {
      if (mounted) setState(() => _tick++);
    });
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tokensProvider);
    final s = ref.watch(l10nProvider);
    final level = ref.watch(gameProvider.select((g) => g.level));
    final pet = ref.watch(
      gameProvider.select((g) => g.petFamily ?? PetFamily.momo),
    );
    return Scaffold(
      backgroundColor: t.bg,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              const Spacer(),
              Text(
                s.t('${pet.label} berevolusi', '${pet.label} evolved'),
                style: t.heading(30),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                s.t(
                  'Sekarang tahap ${s.stageLabel(widget.stage)}, ${widget.stage.levelRange}',
                  'Now in the ${s.stageLabel(widget.stage)} stage, ${widget.stage.levelRange}',
                ),
                style: t.body(15, color: t.muted),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),
              Companion3D(
                pet: pet,
                stage: widget.stage,
                mood: Mood.segar,
                height: 260,
                celebrateTick: _tick,
                living: false,
              ),
              const SizedBox(height: 16),
              StatusPill(label: 'Lv. $level'),
              const Spacer(),
              Text(
                s.t(
                  '${pet.label} tumbuh dari rutinitas yang kamu jaga.',
                  '${pet.label} grew from the routine you kept.',
                ),
                style: t.body(14, color: t.muted),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              TokenButton(
                label: s.t('Lanjut', 'Continue'),
                onPressed: () => Navigator.of(context).pop(),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
