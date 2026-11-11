// Drako GLB controller, per-joint rig v2, 3 models complete.
// Stage 1 = Bayi, 2 = Remaja, 3 = Dewasa (6 Lite, rig per-joint, same joint and clip names).
// Loop vs one-shot is set in the player, glTF does not store a loop flag.
// Tap and celebrate are one-shots: after they finish, return to the idle variant cycle.

import 'dart:math';

String drakoGlbForStage(int stage) {
  switch (stage) {
    case 1:
      return 'assets/3d/drako_bayi.glb';
    case 2:
      return 'assets/3d/drako_remaja.glb';
    case 3:
      return 'assets/3d/drako_dewasa.glb';
    default:
      throw ArgumentError('Drako stage $stage is not in this package (stages are 1-3).');
  }
}

String drakoClipForHp({required double hp, required bool isResting}) {
  if (isResting) return 'sleep';
  if (hp < 30) return 'idle_critical';
  if (hp <= 60) return 'idle_tired';
  return 'idle_fresh';
}

// Idle auto-cycle: do NOT loop one idle clip forever.
// Pick a variant at random, play it once, wait a random 0.5-2.0s delay,
// then pick a different variant. Interrupt immediately on tap, celebrate,
// or a state change (HP band or isResting).
const Map<String, List<String>> drakoIdleVariants = {
  'idle_fresh': ['idle_fresh', 'idle_fresh_a', 'idle_fresh_b', 'idle_fresh_c', 'idle_fresh_d'],
  'idle_tired': ['idle_tired', 'idle_tired_a', 'idle_tired_b', 'idle_tired_c'],
  'idle_critical': ['idle_critical', 'idle_critical_a', 'idle_critical_b', 'idle_critical_c'],
  'sleep': ['sleep'],
};

String drakoNextIdleVariant(String baseClip, String? previous, Random random) {
  final variants = drakoIdleVariants[baseClip] ?? [baseClip];
  if (variants.length == 1) return variants.first;
  var next = variants[random.nextInt(variants.length)];
  while (next == previous) {
    next = variants[random.nextInt(variants.length)];
  }
  return next;
}

Duration drakoIdleDelay(Random random) {
  // 0.5 to 2.0 seconds, random, so idle changes by itself.
  return Duration(milliseconds: 500 + random.nextInt(1501));
}

String drakoOneShotForTap() => 'tap_reaction';
String drakoOneShotForCelebrate() => 'celebrate';

// Single-joint control examples (Three.js / Unity / Godot, by joint name):
// Wing_L only:  getObjectByName('Wing_L').rotation.z += 0.35
// Tail_3 only:  getObjectByName('Tail_3').rotation.y += 0.35
// Head only:    getObjectByName('Head').rotation.y += 0.25
// Full joint list is in drako_3d.rig.
