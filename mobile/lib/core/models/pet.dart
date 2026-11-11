import 'dart:math';

import 'companion.dart';

/// Pendamping yang dipilih saat onboarding. Pilihan ini permanen: hanya
/// disimpan sekali dan tidak punya jalur untuk diganti dari layar mana pun.
enum PetFamily {
  momo('momo', 'Momo'),
  drako('drako', 'Drako');

  const PetFamily(this.storageValue, this.label);

  final String storageValue;
  final String label;

  PetProfile get profile => PetRegistry.of(this);

  static PetFamily? parse(String? value) {
    for (final family in values) {
      if (family.storageValue == value) return family;
    }
    return null;
  }
}

/// How much rendering effort the pet gets outside the app.
///
/// `flat` uses the lightweight sprite path and stops every loop; `full` plays
/// the rigged GLB. The display choice never turns a surface on by itself.
enum PetAnimationMode {
  flat('flat'),
  full('full');

  const PetAnimationMode(this.storageValue);

  final String storageValue;

  static PetAnimationMode parse(String? value) {
    for (final mode in values) {
      if (mode.storageValue == value) return mode;
    }
    return PetAnimationMode.flat;
  }
}

/// How the floating pill presents the pet.
///
/// `head` keeps the compact pill: a head avatar that grows into a full-body
/// greeting when tapped. `body` keeps the full body beside the pill at all
/// times. The choice never turns the pill on by itself.
enum PillForm {
  head('head'),
  body('body');

  const PillForm(this.storageValue);

  final String storageValue;

  static PillForm parse(String? value) {
    for (final form in values) {
      if (form.storageValue == value) return form;
    }
    return PillForm.head;
  }
}

/// One stage of one pet: the rig file and the framing that fits it.
///
/// The two pets have different proportions. Drako's baby and teen heads sit
/// around y=1.5 in model space while the adult hovers around y=0, so a single
/// camera preset would crop heads or waste half the widget.
class PetStageLook {
  const PetStageLook({
    required this.asset,
    required this.cameraOrbit,
    required this.cameraTarget,
  });

  final String asset;
  final String cameraOrbit;
  final String cameraTarget;
}

/// Everything the app needs to know about one companion family.
///
/// Clip names and durations are read from the delivered GLBs, not invented.
/// Drako's idle loops are shorter and come in variants; Momo has one loop per
/// mood. The profile keeps both honest without branching UI code.
class PetProfile {
  const PetProfile({
    required this.family,
    required this.stages,
    required this.idleClips,
    required this.durations,
    required this.tapClips,
    required this.babyCardAsset,
  });

  final PetFamily family;
  final Map<Stage, PetStageLook> stages;
  final Map<Mood, List<String>> idleClips;
  final Map<Stage, Map<String, Duration>> durations;

  /// Taps cycle through these. Momo reacts once; Drako shows off its wings on
  /// every second tap.
  final List<String> tapClips;
  final String babyCardAsset;

  String get sleepClip => 'sleep';
  String get pettingClip => 'petting';
  String get celebrateClip => 'celebrate';
  String get greetClip => 'greet';
  String get walkClip => 'walk';
  String get wingShowClip => 'wing_show';

  bool get hasIdleVariants => idleClips.values.any((clips) => clips.length > 1);

  PetStageLook look(Stage stage) => stages[stage]!;

  List<String> idleClipsFor(Mood mood) => idleClips[mood]!;

  Duration durationOf(Stage stage, String clip) {
    final duration = durations[stage]?[clip];
    if (duration == null) {
      throw StateError('${family.label} has no "$clip" clip at ${stage.name}');
    }
    return duration;
  }
}

class PetRegistry {
  const PetRegistry._();

  static const _momoStage = PetStageLook(
    asset: 'assets/3d/momo_bayi.glb',
    cameraOrbit: '0deg 82deg 4.8m',
    cameraTarget: '0m 0.02m 0m',
  );
  static const _momoRemaja = PetStageLook(
    asset: 'assets/3d/momo_remaja.glb',
    cameraOrbit: '0deg 82deg 4.8m',
    cameraTarget: '0m 0.02m 0m',
  );
  static const _momoDewasa = PetStageLook(
    asset: 'assets/3d/momo_dewasa.glb',
    cameraOrbit: '0deg 82deg 4.8m',
    cameraTarget: '0m 0.02m 0m',
  );

  // Baby and teen heads reach y~1.5; the adult silhouette is centered near 0.
  // The camera targets were checked against offline renders of these GLBs.
  // Every stage starts upright at 0deg; the user drags sideways to orbit. The
  // radii therefore keep all 25 clips inside the viewport at any azimuth, not
  // just the front view that used to hide the tail behind the body.
  static const _drakoStage = PetStageLook(
    asset: 'assets/3d/drako_bayi.glb',
    cameraOrbit: '0deg 82deg 5.5m',
    cameraTarget: '0m 0.55m 0m',
  );
  static const _drakoRemaja = PetStageLook(
    asset: 'assets/3d/drako_remaja.glb',
    cameraOrbit: '0deg 82deg 5.4m',
    cameraTarget: '0m 0.43m 0m',
  );
  static const _drakoDewasa = PetStageLook(
    asset: 'assets/3d/drako_dewasa.glb',
    cameraOrbit: '0deg 82deg 4.55m',
    cameraTarget: '0m -0.06m 0m',
  );

  static const _momoDurations = <String, Duration>{
    'idle_fresh': Duration(seconds: 8),
    'idle_tired': Duration(seconds: 8),
    'idle_critical': Duration(seconds: 3),
    'sleep': Duration(seconds: 8),
    'tap_reaction': Duration(seconds: 1),
    'celebrate': Duration(seconds: 2),
    'greet': Duration(seconds: 2),
    'look_around': Duration(seconds: 3),
    'groom': Duration(milliseconds: 3200),
    'stretch': Duration(milliseconds: 2600),
    'walk': Duration(milliseconds: 1200),
    'petting': Duration(seconds: 2),
  };

  // Drako clip lengths. These are the last keyframe time of each clip in the GLB
  // that ships beside this table, not the 25 fps numbers the clips were first
  // authored on: the rigs are baked and exported on a 30 fps grid, so a clip that
  // was 36 frames at 25 fps (1.440 s) is 44 frames at 30 fps (1.4667 s) once its
  // closing key is restored. `_playOneShot` starts a Timer with this value to hand
  // the pet back to idle, so a stale number cuts the last frames of the animation
  // (or holds a finished pose a beat too long).
  //
  // Regenerate with:
  //   python tools/qa_rig/tmp_clip_durations.py --emit-dart \
  //       tools/qa_rig/dragon_look/bayi_v2.glb drako_bayi ...
  // and check the shipped table with the same script without --emit-dart; it fails
  // when a Dart duration is more than one frame away from the file.
  static const _drakoBayiDurations = <String, Duration>{
    'idle_fresh': Duration(milliseconds: 2667),
    'idle_fresh_a': Duration(milliseconds: 2900),
    'idle_fresh_b': Duration(milliseconds: 2900),
    'idle_fresh_c': Duration(milliseconds: 2400),
    'idle_fresh_d': Duration(milliseconds: 2900),
    'idle_tired': Duration(milliseconds: 3600),
    'idle_tired_a': Duration(milliseconds: 3600),
    'idle_tired_b': Duration(milliseconds: 3600),
    'idle_tired_c': Duration(milliseconds: 3600),
    'idle_critical': Duration(milliseconds: 1467),
    'idle_critical_a': Duration(milliseconds: 1467),
    'idle_critical_b': Duration(milliseconds: 1467),
    'idle_critical_c': Duration(milliseconds: 1467),
    'sleep': Duration(milliseconds: 4333),
    'tap_reaction': Duration(milliseconds: 800),
    'celebrate': Duration(milliseconds: 1800),
    'wing_flap': Duration(milliseconds: 1467),
    'tail_wag': Duration(milliseconds: 1467),
    'head_look': Duration(milliseconds: 1933),
    'fire_puff': Duration(milliseconds: 1000),
    'happy_bounce': Duration(milliseconds: 1000),
    'greet': Duration(milliseconds: 2400),
    'petting': Duration(milliseconds: 2200),
    'walk': Duration(milliseconds: 1400),
    'wing_show': Duration(milliseconds: 2200),
  };

  static const _drakoRemajaDurations = <String, Duration>{
    'idle_fresh': Duration(milliseconds: 2200),
    'idle_fresh_a': Duration(milliseconds: 2400),
    'idle_fresh_b': Duration(milliseconds: 2400),
    'idle_fresh_c': Duration(milliseconds: 2000),
    'idle_fresh_d': Duration(milliseconds: 2400),
    'idle_tired': Duration(milliseconds: 3000),
    'idle_tired_a': Duration(milliseconds: 3000),
    'idle_tired_b': Duration(milliseconds: 3000),
    'idle_tired_c': Duration(milliseconds: 3000),
    'idle_critical': Duration(milliseconds: 1200),
    'idle_critical_a': Duration(milliseconds: 1200),
    'idle_critical_b': Duration(milliseconds: 1200),
    'idle_critical_c': Duration(milliseconds: 1200),
    'sleep': Duration(milliseconds: 3600),
    'tap_reaction': Duration(milliseconds: 800),
    'celebrate': Duration(milliseconds: 1800),
    'wing_flap': Duration(milliseconds: 1200),
    'tail_wag': Duration(milliseconds: 1200),
    'head_look': Duration(milliseconds: 1600),
    'fire_puff': Duration(milliseconds: 1000),
    'happy_bounce': Duration(milliseconds: 1000),
    'greet': Duration(milliseconds: 2000),
    'petting': Duration(milliseconds: 2000),
    'walk': Duration(milliseconds: 1000),
    'wing_show': Duration(milliseconds: 1800),
  };

  static const _drakoDewasaDurations = <String, Duration>{
    'idle_fresh': Duration(milliseconds: 3200),
    'idle_fresh_a': Duration(milliseconds: 3600),
    'idle_fresh_b': Duration(milliseconds: 3400),
    'idle_fresh_c': Duration(milliseconds: 2800),
    'idle_fresh_d': Duration(milliseconds: 3000),
    'idle_tired': Duration(milliseconds: 3800),
    'idle_tired_a': Duration(milliseconds: 4000),
    'idle_tired_b': Duration(milliseconds: 3600),
    'idle_tired_c': Duration(milliseconds: 3800),
    'idle_critical': Duration(milliseconds: 1600),
    'idle_critical_a': Duration(milliseconds: 1400),
    'idle_critical_b': Duration(milliseconds: 2600),
    'idle_critical_c': Duration(milliseconds: 1500),
    // 126 frames at 30 fps. The shipped adult clip lost its closing key and held
    // at 125 (4167ms); the rebuilt asset restores it, so the Timer has to match.
    'sleep': Duration(milliseconds: 4200),
    'tap_reaction': Duration(milliseconds: 900),
    'celebrate': Duration(milliseconds: 2000),
    'wing_flap': Duration(milliseconds: 1600),
    'tail_wag': Duration(milliseconds: 1600),
    'head_look': Duration(milliseconds: 2200),
    'fire_puff': Duration(milliseconds: 1100),
    'happy_bounce': Duration(milliseconds: 1100),
    'greet': Duration(milliseconds: 2200),
    'petting': Duration(milliseconds: 2400),
    'walk': Duration(milliseconds: 1600),
    'wing_show': Duration(milliseconds: 2400),
  };

  static const momo = PetProfile(
    family: PetFamily.momo,
    stages: {
      Stage.bayi: _momoStage,
      Stage.remaja: _momoRemaja,
      Stage.dewasa: _momoDewasa,
    },
    idleClips: {
      Mood.segar: ['idle_fresh'],
      Mood.lelah: ['idle_tired'],
      Mood.kritis: ['idle_critical'],
    },
    durations: {
      Stage.bayi: _momoDurations,
      Stage.remaja: _momoDurations,
      Stage.dewasa: _momoDurations,
    },
    tapClips: ['tap_reaction'],
    babyCardAsset: 'assets/3d/momo_bayi_card.png',
  );

  static const drako = PetProfile(
    family: PetFamily.drako,
    stages: {
      Stage.bayi: _drakoStage,
      Stage.remaja: _drakoRemaja,
      Stage.dewasa: _drakoDewasa,
    },
    idleClips: {
      Mood.segar: [
        'idle_fresh',
        'idle_fresh_a',
        'idle_fresh_b',
        'idle_fresh_c',
        'idle_fresh_d',
      ],
      Mood.lelah: [
        'idle_tired',
        'idle_tired_a',
        'idle_tired_b',
        'idle_tired_c',
      ],
      Mood.kritis: [
        'idle_critical',
        'idle_critical_a',
        'idle_critical_b',
        'idle_critical_c',
      ],
    },
    durations: {
      Stage.bayi: _drakoBayiDurations,
      Stage.remaja: _drakoRemajaDurations,
      Stage.dewasa: _drakoDewasaDurations,
    },
    tapClips: ['tap_reaction', 'wing_show'],
    babyCardAsset: 'assets/3d/drako_bayi_card.png',
  );

  static PetProfile of(PetFamily family) => switch (family) {
    PetFamily.momo => momo,
    PetFamily.drako => drako,
  };
}

/// State-aware behavior rules shared by the Flutter pet and the native bridge.
///
/// The scheduler only picks clips; HP, XP, and stats are never touched here.
/// Every pet gets its own action vocabulary: Momo grooms and stretches, Drako
/// looks, wags, puffs, bounces, walks, and shows its wings.
class PetBehavior {
  const PetBehavior._();

  static const Duration sleepDelay = Duration(hours: 1);
  static const Duration minDelay = Duration(seconds: 6);
  static const Duration maxDelay = Duration(seconds: 60);

  static bool isRestingClip(String clip) => clip == 'sleep';

  static String baseClip({
    required PetFamily family,
    required Mood mood,
    bool resting = false,
  }) {
    if (resting) return PetRegistry.of(family).sleepClip;
    return PetRegistry.of(family).idleClipsFor(mood).first;
  }

  /// Spontaneous actions allowed for this mood and stage. Resting has none:
  /// sleep outranks every random action.
  static Map<String, double> weightsFor({
    required PetFamily family,
    required Mood mood,
    required Stage stage,
    bool resting = false,
    String? previous,
  }) {
    if (resting) return const {};
    final weights = switch (family) {
      PetFamily.momo => _momoWeights(mood, stage),
      PetFamily.drako => _drakoWeights(mood, stage),
    };
    if (previous == null || weights.length < 2) return weights;
    if (!weights.containsKey(previous)) return weights;
    return Map.of(weights)..remove(previous);
  }

  static Map<String, double> _momoWeights(Mood mood, Stage stage) {
    final weights = switch (mood) {
      Mood.segar => switch (stage) {
        Stage.bayi => {
          'greet': 2.0,
          'look_around': 2.0,
          'groom': 2.6,
          'stretch': 1.0,
          'walk': 1.2,
        },
        Stage.remaja => {
          'greet': 2.0,
          'look_around': 2.0,
          'groom': 1.2,
          'stretch': 1.5,
          'walk': 3.0,
        },
        Stage.dewasa => {
          'greet': 2.4,
          'look_around': 2.0,
          'groom': 1.2,
          'stretch': 1.2,
          'walk': 1.0,
        },
      },
      Mood.lelah => switch (stage) {
        Stage.bayi => {
          'greet': 1.0,
          'look_around': 2.0,
          'groom': 2.6,
          'stretch': 1.0,
        },
        Stage.remaja => {
          'greet': 1.0,
          'look_around': 2.0,
          'groom': 1.5,
          'stretch': 1.2,
        },
        Stage.dewasa => {
          'greet': 1.0,
          'look_around': 2.4,
          'groom': 1.2,
          'stretch': 1.0,
        },
      },
      Mood.kritis => const {'look_around': 2.0, 'groom': 1.0},
    };
    return weights;
  }

  static Map<String, double> _drakoWeights(Mood mood, Stage stage) {
    return switch (mood) {
      Mood.segar => switch (stage) {
        Stage.bayi => const {
          'greet': 1.6,
          'head_look': 2.2,
          'tail_wag': 2.4,
          'happy_bounce': 2.2,
          'fire_puff': 0.8,
          'walk': 1.2,
          'wing_flap': 1.0,
          'wing_show': 0.25,
        },
        Stage.remaja => const {
          'greet': 1.8,
          'head_look': 2.0,
          'tail_wag': 1.8,
          'happy_bounce': 1.8,
          'fire_puff': 1.4,
          'walk': 3.0,
          'wing_flap': 1.6,
          'wing_show': 0.4,
        },
        Stage.dewasa => const {
          'greet': 2.2,
          'head_look': 2.0,
          'tail_wag': 1.6,
          'happy_bounce': 0.8,
          'fire_puff': 1.8,
          'walk': 1.0,
          'wing_flap': 1.0,
          'wing_show': 0.8,
        },
      },
      Mood.lelah => switch (stage) {
        Stage.bayi => const {
          'greet': 1.2,
          'head_look': 2.0,
          'tail_wag': 2.0,
          'happy_bounce': 1.2,
          'fire_puff': 0.6,
          'wing_flap': 0.4,
        },
        Stage.remaja => const {
          'greet': 1.4,
          'head_look': 2.2,
          'tail_wag': 1.8,
          'happy_bounce': 1.0,
          'fire_puff': 1.0,
          'wing_flap': 0.5,
        },
        Stage.dewasa => const {
          'greet': 1.6,
          'head_look': 2.4,
          'tail_wag': 1.6,
          'happy_bounce': 0.6,
          'fire_puff': 1.2,
          'wing_flap': 0.4,
        },
      },
      Mood.kritis => const {'head_look': 2.0, 'tail_wag': 1.0},
    };
  }

  /// Weighted pick with anti-repeat. Returns null while resting even if a
  /// caller ignores [weightsFor].
  static String? choose({
    required PetFamily family,
    required Mood mood,
    required Stage stage,
    bool resting = false,
    String? previous,
    Random? random,
  }) {
    if (resting) return null;
    final weights = weightsFor(
      family: family,
      mood: mood,
      stage: stage,
      resting: resting,
      previous: previous,
    );
    if (weights.isEmpty) return null;
    final total = weights.values.fold<double>(0, (sum, w) => sum + w);
    if (total <= 0) return null;
    final rng = random ?? Random();
    var target = rng.nextDouble() * total;
    for (final entry in weights.entries) {
      target -= entry.value;
      if (target <= 0) return entry.key;
    }
    return weights.keys.last;
  }

  /// Taps cycle through the family's tap clips. Drako alternates between a
  /// quick reaction and its wing display.
  static String? tapClip({
    required PetFamily family,
    required bool resting,
    required int tapCount,
  }) {
    if (resting) return null;
    final clips = PetRegistry.of(family).tapClips;
    return clips[tapCount % clips.length];
  }

  static String? pettingClip({
    required PetFamily family,
    required bool resting,
  }) => resting ? null : PetRegistry.of(family).pettingClip;

  /// Jittered pause between spontaneous actions. Tired and critical rest
  /// longer, adolescents act sooner, and everything stays inside 6-60 s.
  static Duration nextDelay({
    required PetFamily family,
    required Mood mood,
    required Stage stage,
    bool resting = false,
    Random? random,
  }) {
    if (resting) return sleepDelay;
    final base = switch (mood) {
      Mood.segar => 12.0,
      Mood.lelah => 20.0,
      Mood.kritis => 30.0,
    };
    final stageFactor = switch (stage) {
      Stage.bayi => 1.0,
      Stage.remaja => 0.8,
      Stage.dewasa => 1.15,
    };
    final familyFactor = family == PetFamily.drako ? 0.8 : 1.0;
    final rng = random ?? Random();
    final jitter = 0.6 + rng.nextDouble() * 0.8;
    final ms = (base * stageFactor * familyFactor * jitter * 1000).round();
    return Duration(
      milliseconds: ms.clamp(minDelay.inMilliseconds, maxDelay.inMilliseconds),
    );
  }

  /// How long one idle variant stays on screen before switching to the next.
  /// Momo loops a single clip and never switches. Drako keeps looping the
  /// current variant the whole time, so the loop never freezes between clips;
  /// the hold only decides when to crossfade to another variant.
  static Duration idleHold({required PetFamily family, Random? random}) {
    if (!PetRegistry.of(family).hasIdleVariants) return Duration.zero;
    final rng = random ?? Random();
    return Duration(milliseconds: 6000 + rng.nextInt(6001));
  }
}
