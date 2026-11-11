import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/pet.dart';
import '../state/app_state.dart';

/// Terapkan token terbaru dan maskot tahap terkini. Pemanggil bertanggung
/// jawab atas opt-in pengguna.
Future<bool> applyPill(WidgetRef ref) {
  final t = ref.read(tokensProvider);
  final game = ref.read(gameProvider);
  return ref
      .read(usageServiceProvider)
      .showPill(
        background: t.bg.toARGB32(),
        surface: t.surface.toARGB32(),
        ink: t.ink.toARGB32(),
        accent: t.primary.toARGB32(),
        radius: t.notched ? 4 : t.radius,
        language: game.language,
        stage: game.stage.name,
        animation: game.pillAnimationMode.storageValue,
        form: game.pillForm.storageValue,
        pet: (game.petFamily ?? PetFamily.momo).storageValue,
        // HP itu milik pet, bukan milik Momo: pill menghitungnya dari pemakaian
        // native, sementara bonus hari ini dan warna tema datang dari sini.
        hpBonus: game.bonusHp,
        hpHealthy: t.hpHealthy.toARGB32(),
        hpTired: t.hpTired.toARGB32(),
        hpCritical: t.hpCritical.toARGB32(),
      );
}
