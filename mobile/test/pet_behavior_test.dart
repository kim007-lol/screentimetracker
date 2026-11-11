import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:screentime_companion/core/models/companion.dart';
import 'package:screentime_companion/core/models/pet.dart';

void main() {
  group('PetAnimationMode', () {
    test('persists stable flat/full values and rejects unknown input', () {
      expect(PetAnimationMode.flat.storageValue, 'flat');
      expect(PetAnimationMode.full.storageValue, 'full');
      expect(PetAnimationMode.parse('full'), PetAnimationMode.full);
      expect(PetAnimationMode.parse('flat'), PetAnimationMode.flat);
      for (final invalid in [null, '', 'static', 'FULL', 'turbo']) {
        expect(
          PetAnimationMode.parse(invalid),
          PetAnimationMode.flat,
          reason: '$invalid',
        );
      }
    });
  });

  group('PetFamily', () {
    test('parses only the two shipped companions', () {
      expect(PetFamily.parse('momo'), PetFamily.momo);
      expect(PetFamily.parse('drako'), PetFamily.drako);
      for (final invalid in [null, '', 'Momo', 'cat', 'dragon']) {
        expect(PetFamily.parse(invalid), isNull, reason: '$invalid');
      }
      expect(PetFamily.momo.label, 'Momo');
      expect(PetFamily.drako.label, 'Drako');
      expect(PetFamily.drako.profile.family, PetFamily.drako);
    });
  });

  group('PetRegistry', () {
    test('every stage has its own GLB and a framing preset', () {
      final assets = <String>{};
      for (final family in PetFamily.values) {
        final profile = PetRegistry.of(family);
        for (final stage in Stage.values) {
          final look = profile.look(stage);
          expect(
            look.asset,
            'assets/3d/${family.storageValue}_${stage.name}.glb',
          );
          expect(look.cameraOrbit, isNotEmpty);
          expect(look.cameraTarget, isNotEmpty);
          assets.add(look.asset);
        }
      }
      expect(assets, hasLength(PetFamily.values.length * Stage.values.length));
    });

    test('Drako baby, teen, and adult use measured framing', () {
      final drako = PetRegistry.drako;
      expect(drako.look(Stage.bayi).cameraOrbit, '0deg 82deg 5.5m');
      expect(drako.look(Stage.remaja).cameraOrbit, '0deg 82deg 5.4m');
      expect(drako.look(Stage.dewasa).cameraOrbit, '0deg 82deg 4.55m');
      expect(drako.look(Stage.bayi).cameraTarget, '0m 0.55m 0m');
      expect(drako.look(Stage.remaja).cameraTarget, '0m 0.43m 0m');
      expect(drako.look(Stage.dewasa).cameraTarget, '0m -0.06m 0m');
      expect(
        drako.look(Stage.dewasa).cameraOrbit,
        isNot(drako.look(Stage.bayi).cameraOrbit),
      );
    });

    test('Momo keeps 12 clips per stage with exact durations', () {
      final momo = PetRegistry.momo;
      for (final stage in Stage.values) {
        expect(momo.durations[stage], hasLength(12));
        expect(
          momo.durationOf(stage, 'idle_fresh'),
          const Duration(seconds: 8),
        );
        expect(momo.durationOf(stage, 'sleep'), const Duration(seconds: 8));
        expect(
          momo.durationOf(stage, 'tap_reaction'),
          const Duration(seconds: 1),
        );
        expect(momo.durationOf(stage, 'celebrate'), const Duration(seconds: 2));
        expect(momo.durationOf(stage, 'greet'), const Duration(seconds: 2));
        expect(
          momo.durationOf(stage, 'look_around'),
          const Duration(seconds: 3),
        );
        expect(
          momo.durationOf(stage, 'groom'),
          const Duration(milliseconds: 3200),
        );
        expect(
          momo.durationOf(stage, 'stretch'),
          const Duration(milliseconds: 2600),
        );
        expect(
          momo.durationOf(stage, 'walk'),
          const Duration(milliseconds: 1200),
        );
        expect(momo.durationOf(stage, 'petting'), const Duration(seconds: 2));
      }
      expect(momo.hasIdleVariants, isFalse);
      for (final mood in Mood.values) {
        expect(momo.idleClipsFor(mood), hasLength(1));
      }
      expect(() => momo.durationOf(Stage.bayi, 'wing_show'), throwsStateError);
    });

    test('Drako ships 25 clips including greet, petting, walk, wing_show', () {
      final drako = PetRegistry.drako;
      for (final stage in Stage.values) {
        final durations = drako.durations[stage]!;
        expect(durations, hasLength(25), reason: stage.name);
        for (final clip in [
          'sleep',
          'tap_reaction',
          'celebrate',
          'greet',
          'petting',
          'walk',
          'wing_show',
          'wing_flap',
          'tail_wag',
          'head_look',
          'fire_puff',
          'happy_bounce',
        ]) {
          expect(
            drako.durationOf(stage, clip),
            greaterThan(Duration.zero),
            reason: '$stage/$clip',
          );
        }
        for (final duration in durations.values) {
          expect(duration, greaterThan(Duration.zero));
        }
      }
      expect(drako.hasIdleVariants, isTrue);
      expect(drako.idleClipsFor(Mood.segar), hasLength(5));
      expect(drako.idleClipsFor(Mood.lelah), hasLength(4));
      expect(drako.idleClipsFor(Mood.kritis), hasLength(4));
      for (final mood in Mood.values) {
        for (final clip in drako.idleClipsFor(mood)) {
          expect(
            drako.durationOf(Stage.dewasa, clip),
            greaterThan(Duration.zero),
          );
        }
      }
      expect(
        drako.durationOf(Stage.bayi, 'wing_show'),
        const Duration(milliseconds: 2200),
      );
      expect(
        drako.durationOf(Stage.dewasa, 'wing_show'),
        const Duration(milliseconds: 2400),
      );
    });

    test('every schedulable action has a duration at every stage', () {
      for (final family in PetFamily.values) {
        final profile = PetRegistry.of(family);
        for (final stage in Stage.values) {
          for (final mood in Mood.values) {
            final weights = PetBehavior.weightsFor(
              family: family,
              mood: mood,
              stage: stage,
            );
            for (final clip in weights.keys) {
              expect(
                () => profile.durationOf(stage, clip),
                returnsNormally,
                reason: '${family.storageValue}/$stage/$mood/$clip',
              );
            }
          }
        }
      }
    });

    test('baby cards are declared per family', () {
      expect(PetRegistry.momo.babyCardAsset, 'assets/3d/momo_bayi_card.png');
      expect(PetRegistry.drako.babyCardAsset, 'assets/3d/drako_bayi_card.png');
    });
  });

  group('Base clip and rest', () {
    test('sleep outranks mood for both pets', () {
      for (final family in PetFamily.values) {
        expect(PetBehavior.isRestingClip('sleep'), isTrue);
        expect(PetBehavior.isRestingClip('idle_fresh'), isFalse);
        expect(
          PetBehavior.baseClip(family: family, mood: Mood.segar, resting: true),
          'sleep',
        );
        expect(
          PetBehavior.baseClip(family: family, mood: Mood.segar),
          PetRegistry.of(family).idleClipsFor(Mood.segar).first,
        );
      }
      expect(
        PetBehavior.baseClip(family: PetFamily.momo, mood: Mood.segar),
        'idle_fresh',
      );
      expect(
        PetBehavior.baseClip(family: PetFamily.momo, mood: Mood.lelah),
        'idle_tired',
      );
      expect(
        PetBehavior.baseClip(family: PetFamily.momo, mood: Mood.kritis),
        'idle_critical',
      );
      expect(
        PetBehavior.baseClip(family: PetFamily.drako, mood: Mood.segar),
        'idle_fresh',
      );
      expect(
        PetBehavior.baseClip(family: PetFamily.drako, mood: Mood.lelah),
        'idle_tired',
      );
      expect(
        PetBehavior.baseClip(family: PetFamily.drako, mood: Mood.kritis),
        'idle_critical',
      );
    });
  });

  group('Spontaneous behavior', () {
    test('resting never selects spontaneous, waking, or tap actions', () {
      for (final family in PetFamily.values) {
        expect(
          PetBehavior.weightsFor(
            family: family,
            mood: Mood.segar,
            stage: Stage.remaja,
            resting: true,
          ),
          isEmpty,
        );
        expect(
          PetBehavior.choose(
            family: family,
            mood: Mood.segar,
            stage: Stage.remaja,
            resting: true,
            random: Random(1),
          ),
          isNull,
        );
        expect(
          PetBehavior.tapClip(family: family, resting: true, tapCount: 0),
          isNull,
        );
        expect(PetBehavior.pettingClip(family: family, resting: true), isNull);
        expect(
          PetBehavior.pettingClip(family: family, resting: false),
          'petting',
        );
      }
    });

    test('each family keeps its own action vocabulary', () {
      final momo = PetBehavior.weightsFor(
        family: PetFamily.momo,
        mood: Mood.segar,
        stage: Stage.remaja,
      );
      expect(
        momo.keys,
        containsAll(['greet', 'look_around', 'groom', 'stretch', 'walk']),
      );
      final drako = PetBehavior.weightsFor(
        family: PetFamily.drako,
        mood: Mood.segar,
        stage: Stage.remaja,
      );
      expect(
        drako.keys,
        containsAll([
          'greet',
          'head_look',
          'tail_wag',
          'happy_bounce',
          'fire_puff',
          'walk',
          'wing_flap',
          'wing_show',
        ]),
      );
      expect(drako.keys, isNot(contains('groom')));
      expect(momo.keys, isNot(contains('wing_show')));
    });

    test('critical only uses calm actions and tired never walks', () {
      final criticalKeys = <PetFamily, Set<String>>{
        PetFamily.momo: {'look_around', 'groom'},
        PetFamily.drako: {'head_look', 'tail_wag'},
      };
      for (final family in PetFamily.values) {
        for (var seed = 0; seed < 100; seed++) {
          final critical = PetBehavior.choose(
            family: family,
            mood: Mood.kritis,
            stage: Stage.values[seed % 3],
            random: Random(seed),
          );
          expect(critical, isNotNull);
          expect(critical, isIn(criticalKeys[family]!));
          expect(
            PetBehavior.weightsFor(
              family: family,
              mood: Mood.kritis,
              stage: Stage.dewasa,
            ).keys,
            everyElement(isIn(criticalKeys[family]!)),
          );
        }
        for (final stage in Stage.values) {
          final tired = PetBehavior.weightsFor(
            family: family,
            mood: Mood.lelah,
            stage: stage,
          );
          expect(
            tired.keys,
            isNot(contains('walk')),
            reason: '${family.storageValue}/$stage',
          );
          final pick = PetBehavior.choose(
            family: family,
            mood: Mood.lelah,
            stage: stage,
            random: Random(stage.index * 37 + 3),
          );
          expect(pick, isNot('walk'));
        }
      }
    });

    test('fresh Momo can walk, greet, groom, stretch, and look around', () {
      final seen = <String>{};
      final random = Random(7);
      for (var i = 0; i < 200; i++) {
        final clip = PetBehavior.choose(
          family: PetFamily.momo,
          mood: Mood.segar,
          stage: Stage.values[i % 3],
          random: random,
        );
        if (clip != null) seen.add(clip);
      }
      expect(
        seen,
        containsAll(['greet', 'look_around', 'groom', 'stretch', 'walk']),
      );
    });

    test('fresh Drako shows wings, wags, puffs, bounces, and walks', () {
      final seen = <String>{};
      final random = Random(13);
      for (var i = 0; i < 400; i++) {
        final clip = PetBehavior.choose(
          family: PetFamily.drako,
          mood: Mood.segar,
          stage: Stage.values[i % 3],
          random: random,
        );
        if (clip != null) seen.add(clip);
      }
      expect(
        seen,
        containsAll([
          'greet',
          'head_look',
          'tail_wag',
          'happy_bounce',
          'fire_puff',
          'walk',
          'wing_flap',
          'wing_show',
        ]),
      );
    });

    test('anti-repeat skips the previous action when alternatives exist', () {
      const previousByFamily = <PetFamily, String>{
        PetFamily.momo: 'look_around',
        PetFamily.drako: 'head_look',
      };
      for (final family in PetFamily.values) {
        for (final mood in Mood.values) {
          for (var seed = 0; seed < 40; seed++) {
            final previous = previousByFamily[family]!;
            final pick = PetBehavior.choose(
              family: family,
              mood: mood,
              stage: Stage.remaja,
              previous: previous,
              random: Random(seed),
            );
            expect(
              pick,
              isNot(previous),
              reason: '${family.storageValue}/$mood/$seed',
            );
          }
        }
      }
    });

    test('stage pacing matches the personalities', () {
      final momoRemaja = PetBehavior.weightsFor(
        family: PetFamily.momo,
        mood: Mood.segar,
        stage: Stage.remaja,
      );
      final momoDewasa = PetBehavior.weightsFor(
        family: PetFamily.momo,
        mood: Mood.segar,
        stage: Stage.dewasa,
      );
      final momoBayi = PetBehavior.weightsFor(
        family: PetFamily.momo,
        mood: Mood.segar,
        stage: Stage.bayi,
      );
      expect(momoRemaja['walk']!, greaterThan(momoDewasa['walk']!));
      expect(momoBayi['groom']!, greaterThanOrEqualTo(momoRemaja['groom']!));

      final drakoBayi = PetBehavior.weightsFor(
        family: PetFamily.drako,
        mood: Mood.segar,
        stage: Stage.bayi,
      );
      final drakoRemaja = PetBehavior.weightsFor(
        family: PetFamily.drako,
        mood: Mood.segar,
        stage: Stage.remaja,
      );
      final drakoDewasa = PetBehavior.weightsFor(
        family: PetFamily.drako,
        mood: Mood.segar,
        stage: Stage.dewasa,
      );
      // The adult is the one that actually shows off its wings.
      expect(drakoBayi['wing_show']!, lessThan(drakoRemaja['wing_show']!));
      expect(drakoRemaja['wing_show']!, lessThan(drakoDewasa['wing_show']!));
      // The teen is the most restless walker; the baby is the bounciest.
      expect(drakoRemaja['walk']!, greaterThan(drakoDewasa['walk']!));
      expect(
        drakoBayi['happy_bounce']!,
        greaterThan(drakoDewasa['happy_bounce']!),
      );
    });

    test('delays stay bounded and follow mood and stage pacing', () {
      final random = Random(11);
      var momoFreshTotal = 0;
      var momoCriticalTotal = 0;
      var momoRemajaTotal = 0;
      var momoDewasaTotal = 0;
      var drakoFreshTotal = 0;
      var drakoCriticalTotal = 0;
      var drakoRemajaTotal = 0;
      var drakoDewasaTotal = 0;
      final momoRng = Random(29);
      final drakoRng = Random(29);
      for (var i = 0; i < 400; i++) {
        for (final family in PetFamily.values) {
          final fresh = PetBehavior.nextDelay(
            family: family,
            mood: Mood.segar,
            stage: Stage.values[i % 3],
            random: random,
          );
          final critical = PetBehavior.nextDelay(
            family: family,
            mood: Mood.kritis,
            stage: Stage.values[i % 3],
            random: random,
          );
          final remaja = PetBehavior.nextDelay(
            family: family,
            mood: Mood.segar,
            stage: Stage.remaja,
            random: random,
          );
          final dewasa = PetBehavior.nextDelay(
            family: family,
            mood: Mood.segar,
            stage: Stage.dewasa,
            random: random,
          );
          for (final delay in [fresh, critical, remaja, dewasa]) {
            expect(delay, greaterThanOrEqualTo(PetBehavior.minDelay));
            expect(delay, lessThanOrEqualTo(PetBehavior.maxDelay));
          }
          if (family == PetFamily.momo) {
            momoFreshTotal += fresh.inMilliseconds;
            momoCriticalTotal += critical.inMilliseconds;
            momoRemajaTotal += remaja.inMilliseconds;
            momoDewasaTotal += dewasa.inMilliseconds;
          } else {
            drakoFreshTotal += fresh.inMilliseconds;
            drakoCriticalTotal += critical.inMilliseconds;
            drakoRemajaTotal += remaja.inMilliseconds;
            drakoDewasaTotal += dewasa.inMilliseconds;
          }
        }
        // Same seed, same jitter: Drako's faster cadence must never be slower.
        final momoDelay = PetBehavior.nextDelay(
          family: PetFamily.momo,
          mood: Mood.segar,
          stage: Stage.dewasa,
          random: momoRng,
        );
        final drakoDelay = PetBehavior.nextDelay(
          family: PetFamily.drako,
          mood: Mood.segar,
          stage: Stage.dewasa,
          random: drakoRng,
        );
        expect(drakoDelay, lessThanOrEqualTo(momoDelay));
      }
      expect(momoCriticalTotal, greaterThan(momoFreshTotal));
      expect(momoRemajaTotal, lessThan(momoDewasaTotal));
      expect(drakoCriticalTotal, greaterThan(drakoFreshTotal));
      expect(drakoRemajaTotal, lessThan(drakoDewasaTotal));
    });

    test('a sleeping pet is never scheduled', () {
      for (final family in PetFamily.values) {
        expect(
          PetBehavior.nextDelay(
            family: family,
            mood: Mood.segar,
            stage: Stage.remaja,
            resting: true,
          ),
          const Duration(hours: 1),
        );
      }
    });
  });

  group('Tap, petting, and idle pause', () {
    test('taps cycle through each family tap clips', () {
      for (var tap = 0; tap < 6; tap++) {
        expect(
          PetBehavior.tapClip(
            family: PetFamily.momo,
            resting: false,
            tapCount: tap,
          ),
          'tap_reaction',
        );
      }
      expect(
        PetBehavior.tapClip(
          family: PetFamily.drako,
          resting: false,
          tapCount: 0,
        ),
        'tap_reaction',
      );
      expect(
        PetBehavior.tapClip(
          family: PetFamily.drako,
          resting: false,
          tapCount: 1,
        ),
        'wing_show',
      );
      expect(
        PetBehavior.tapClip(
          family: PetFamily.drako,
          resting: false,
          tapCount: 2,
        ),
        'tap_reaction',
      );
    });

    test('idle hold only exists for pets with idle variants', () {
      for (var seed = 0; seed < 200; seed++) {
        expect(
          PetBehavior.idleHold(family: PetFamily.momo, random: Random(seed)),
          Duration.zero,
        );
        final hold = PetBehavior.idleHold(
          family: PetFamily.drako,
          random: Random(seed),
        );
        expect(hold, greaterThanOrEqualTo(const Duration(milliseconds: 6000)));
        expect(hold, lessThanOrEqualTo(const Duration(milliseconds: 12000)));
      }
      final values = {
        for (var seed = 0; seed < 200; seed++)
          PetBehavior.idleHold(
            family: PetFamily.drako,
            random: Random(seed),
          ).inMilliseconds,
      };
      expect(values.length, greaterThan(1));
    });
  });
}
