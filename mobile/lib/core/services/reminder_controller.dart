import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../l10n/l10n.dart';
import '../models/pet.dart';
import '../state/app_state.dart';

/// Jadwalkan atau batalkan satu pengingat harian. Teks dikirim dari Flutter
/// supaya mengikuti bahasa aktif, dan hanya satu notifikasi per hari.
Future<bool> applyReminder(WidgetRef ref, {required bool enable}) async {
  final service = ref.read(usageServiceProvider);
  if (!enable) {
    await service.cancelReminder();
    return true;
  }

  final game = ref.read(gameProvider);
  final s = ref.read(l10nProvider);
  final pet = game.petFamily ?? PetFamily.momo;
  return service.scheduleReminder(
    hour: game.reminderHour,
    minute: game.reminderMinute,
    title: s.t('${pet.label} menunggu', '${pet.label} is waiting'),
    body: s.t(
      'Cek HP ${pet.label} dan selesaikan satu misi hari ini.',
      'Check ${pet.label}\'s HP and finish one mission today.',
    ),
  );
}
