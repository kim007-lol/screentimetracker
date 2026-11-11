import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/pet.dart';
import '../state/app_state.dart';

/// Starts or refreshes the roaming pet. The caller owns the opt-in; this
/// helper never flips [GameState.petOverlayEnabled].
Future<bool> applyPetOverlay(WidgetRef ref) {
  final game = ref.read(gameProvider);
  return ref
      .read(usageServiceProvider)
      .showPetOverlay(
        animation: game.overlayAnimationMode.storageValue,
        language: game.language,
        stage: game.stage.name,
        pet: (game.petFamily ?? PetFamily.momo).storageValue,
        hpBonus: game.bonusHp,
      );
}
