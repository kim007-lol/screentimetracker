import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:screentime_companion/core/services/history_service.dart';
import 'package:screentime_companion/core/models/pet.dart';
import 'package:screentime_companion/core/services/usage_service.dart';
import 'package:screentime_companion/core/state/app_state.dart';
import 'package:screentime_companion/core/theme/app_tokens.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _FakeUsage extends UsageService {
  bool failCollection = false;
  bool failMonitored = false;
  final collectionCalls = <bool>[];
  final monitoredCalls = <List<String>>[];
  final events = <String>[];
  int clears = 0;

  @override
  Future<void> setCollectionEnabled(bool enabled) async {
    collectionCalls.add(enabled);
    events.add(enabled ? 'collection:on' : 'collection:off');
    if (failCollection && enabled) {
      throw PlatformException(code: 'FAILED');
    }
  }

  @override
  Future<void> setMonitoredApps(List<String> packages) async {
    monitoredCalls.add(List<String>.from(packages));
    events.add('monitored');
    if (failMonitored) {
      throw PlatformException(code: 'FAILED');
    }
  }

  @override
  Future<void> clearLocalData() async {
    clears++;
  }
}

class _FakeHistory extends HistoryService {
  int clears = 0;

  @override
  Future<void> clear() async {
    clears++;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late SharedPreferences prefs;
  late _FakeUsage usage;
  late _FakeHistory history;
  late ProviderContainer container;

  Future<void> init({Map<String, Object> initial = const {}}) async {
    SharedPreferences.setMockInitialValues(initial);
    prefs = await SharedPreferences.getInstance();
    usage = _FakeUsage();
    history = _FakeHistory();
    container = ProviderContainer(
      overrides: [
        sharedPrefsProvider.overrideWithValue(prefs),
        usageServiceProvider.overrideWithValue(usage),
        historyServiceProvider.overrideWithValue(history),
      ],
    );
    addTearDown(container.dispose);
  }

  test('deletion leaves no restored progress in preferences', () async {
    final today = HistoryService.dayKey(DateTime.now());
    await init(
      initial: {
        'onboarded': true,
        'theme': 'brutal',
        'collectionEnabled': true,
        'level': 6,
        'xp': 70,
        'streak': 9,
        'lastOpenDay': today,
        'day': today,
        'userName': 'Raka',
        'bankIn': 120,
        'historyBackfilled': true,
        'petFamily': 'momo',
      },
    );
    await container.read(gameProvider.notifier).deleteAllData();

    expect(usage.clears, 1);
    expect(history.clears, 1);
    expect(prefs.getString('userName'), isNull);
    expect(prefs.getString('petFamily'), isNull);
    expect(prefs.getInt('level'), isNull);
    expect(prefs.getString('day'), isNull);
    expect(prefs.getString('lastOpenDay'), isNull);
    expect(prefs.getInt('streak'), isNull);
    expect(prefs.getBool('collectionTombstone'), isTrue);
    expect(prefs.getBool('collectionEnabled'), isFalse);
    // Backfill runs again after re-onboarding; the floor keeps deleted days out.
    expect(prefs.getString('historyBackfillFloor'), today);
    final state = container.read(gameProvider);
    expect(state.onboarded, isFalse);
    expect(state.collectionEnabled, isFalse);
    expect(state.level, 1);
    expect(state.bankIn, 0);
    expect(state.petFamily, isNull);
  });

  test('failed collection opt-in keeps onboarding incomplete', () async {
    await init(initial: {'theme': 'pop'});
    usage.failCollection = true;

    await expectLater(
      container
          .read(gameProvider.notifier)
          .finishOnboarding(AppThemeId.brutal, petFamily: PetFamily.momo),
      throwsA(isA<PlatformException>()),
    );
    expect(prefs.getBool('onboarded'), isNot(true));
    expect(prefs.getBool('collectionEnabled'), isNot(true));
    final state = container.read(gameProvider);
    expect(state.onboarded, isFalse);
    expect(state.collectionEnabled, isFalse);
  });

  test(
    'successful onboarding enables collection before showing home',
    () async {
      await init();
      await container
          .read(gameProvider.notifier)
          .finishOnboarding(AppThemeId.brutal, petFamily: PetFamily.momo);

      expect(usage.collectionCalls, [true]);
      expect(prefs.getBool('onboarded'), isTrue);
      expect(prefs.getBool('collectionEnabled'), isTrue);
      final state = container.read(gameProvider);
      expect(state.onboarded, isTrue);
      expect(state.collectionEnabled, isTrue);
    },
  );

  test('onboarding saves app choices before collection opt-in', () async {
    await init();
    await container
        .read(gameProvider.notifier)
        .finishOnboarding(
          AppThemeId.clay,
          petFamily: PetFamily.momo,
          monitoredPackages: {'com.example.two', 'com.example.one'},
          appLimits: {
            'com.example.one': 30,
            'com.example.two': 0,
            '': 45,
            'com.example.three': 999,
          },
        );

    expect(usage.monitoredCalls.single, ['com.example.one', 'com.example.two']);
    expect(usage.events, ['monitored', 'collection:on']);
    expect(prefs.getStringList('monitoredPackages')!.toSet(), {
      'com.example.one',
      'com.example.two',
    });
    expect(prefs.getStringList('appLimits')!.toSet(), {
      'com.example.one=30',
      'com.example.three=480',
    });
    final state = container.read(gameProvider);
    expect(state.monitoredPackages, {'com.example.one', 'com.example.two'});
    expect(state.appLimits, {'com.example.one': 30, 'com.example.three': 480});
    expect(state.onboarded, isTrue);
  });

  test('failed app selection keeps onboarding incomplete', () async {
    await init();
    usage.failMonitored = true;

    await expectLater(
      container
          .read(gameProvider.notifier)
          .finishOnboarding(
            AppThemeId.brutal,
            petFamily: PetFamily.momo,
            monitoredPackages: {'com.example.one'},
          ),
      throwsA(isA<PlatformException>()),
    );

    expect(prefs.getBool('onboarded'), isNot(true));
    expect(prefs.getBool('collectionEnabled'), isNot(true));
    expect(prefs.getString('theme'), isNull);
    expect(usage.collectionCalls, isEmpty);
    expect(container.read(gameProvider).onboarded, isFalse);
  });

  test('empty monitored set turns conscious pause off', () async {
    await init(initial: {'onboarded': false, 'pauseEnabled': true});
    await container
        .read(gameProvider.notifier)
        .finishOnboarding(
          AppThemeId.midnight,
          petFamily: PetFamily.momo,
          monitoredPackages: {},
        );

    expect(container.read(gameProvider).pauseEnabled, isFalse);
    expect(prefs.getBool('pauseEnabled'), isFalse);
    expect(container.read(gameProvider).monitoredPackages, isEmpty);
    expect(container.read(gameProvider).onboarded, isTrue);
  });

  test('onboarding saves the chosen companion', () async {
    await init();
    await container
        .read(gameProvider.notifier)
        .finishOnboarding(AppThemeId.clay, petFamily: PetFamily.momo);

    expect(prefs.getString('petFamily'), 'momo');
    expect(container.read(gameProvider).petFamily, PetFamily.momo);
  });

  test('onboarding can save Drako as the companion', () async {
    await init();
    await container
        .read(gameProvider.notifier)
        .finishOnboarding(AppThemeId.clay, petFamily: PetFamily.drako);

    expect(prefs.getString('petFamily'), 'drako');
    expect(container.read(gameProvider).petFamily, PetFamily.drako);

    final restored = ProviderContainer(
      overrides: [
        sharedPrefsProvider.overrideWithValue(prefs),
        usageServiceProvider.overrideWithValue(usage),
      ],
    );
    addTearDown(restored.dispose);
    expect(restored.read(gameProvider).petFamily, PetFamily.drako);
  });

  test('a companion written before completion stays unlocked', () async {
    // Simulates a crash after the preference write but before onboarding done:
    // the retry must still be able to present (and save) a choice.
    await init(initial: {'onboarded': false, 'petFamily': 'momo'});
    expect(container.read(gameProvider).petFamily, isNull);

    await container
        .read(gameProvider.notifier)
        .finishOnboarding(AppThemeId.clay, petFamily: PetFamily.momo);
    expect(container.read(gameProvider).petFamily, PetFamily.momo);
  });

  test('completed onboarding restores the saved companion', () async {
    await init(initial: {'onboarded': true, 'petFamily': 'momo'});
    expect(container.read(gameProvider).petFamily, PetFamily.momo);
  });

  test('unknown companion values are ignored', () async {
    await init(initial: {'onboarded': true, 'petFamily': 'unknown'});
    expect(container.read(gameProvider).petFamily, isNull);
  });
}
