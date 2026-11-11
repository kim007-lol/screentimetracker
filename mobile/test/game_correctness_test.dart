import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:screentime_companion/core/balancing.dart';
import 'package:screentime_companion/core/models/companion.dart';
import 'package:screentime_companion/core/models/usage.dart';
import 'package:screentime_companion/core/services/history_service.dart';
import 'package:screentime_companion/core/services/usage_service.dart';
import 'package:screentime_companion/core/state/app_state.dart';
import 'package:shared_preferences/shared_preferences.dart';

DailyUsage usage({
  UsageSource source = UsageSource.android,
  int minutes = 100,
}) => DailyUsage(
  apps: [
    AppUsage(
      packageName: 'app',
      label: 'App',
      minutes: minutes,
      opens: 1,
      longestSessionMinutes: minutes,
      category: UsageCategory.sosial,
      scrollHits: 200,
    ),
  ],
  source: source,
  baselineMinutes: 200,
);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late ProviderContainer container;
  late SharedPreferences prefs;

  setUp(() async {
    SharedPreferences.setMockInitialValues({'onboarded': true});
    prefs = await SharedPreferences.getInstance();
    container = ProviderContainer(
      overrides: [sharedPrefsProvider.overrideWithValue(prefs)],
    );
  });
  tearDown(() => container.dispose());

  test('sample data never damages HP', () {
    expect(
      computeHp(usage: usage(source: UsageSource.sample), bonusHp: 0),
      100,
    );
  });
  test('real data retains minute and scroll penalties', () {
    expect(computeHp(usage: usage(), bonusHp: 0), 74);
    expect(computeHp(usage: usage(), bonusHp: 10), 84);
  });
  test('rest completion without an active session gives nothing', () {
    container.read(gameProvider.notifier).completeRest(1);
    expect(container.read(gameProvider).xp, 0);
  });
  test('repeated early rests cannot farm rounded rewards', () {
    final game = container.read(gameProvider.notifier);
    for (var i = 0; i < 100; i++) {
      game.setResting(true);
      game.completeRest(0.01);
    }
    expect(container.read(gameProvider).xp, Balancing.restMaxXp);
    expect(container.read(gameProvider).bonusHp, Balancing.restMaxHpGain);
    game.setResting(true);
    game.completeRest(1);
    expect(container.read(gameProvider).xp, Balancing.restMaxXp);
  });
  test('a completed rest session cannot complete twice', () {
    final game = container.read(gameProvider.notifier);
    game.setResting(true);
    game.completeRest(1);
    game.completeRest(1);
    expect(container.read(gameProvider).xp, Balancing.restMaxXp);
  });

  late DateTime now;
  late FakeUsage service;
  late FakeHistory history;
  Future<void> setupClock() async {
    container.dispose();
    now = DateTime(2026, 10, 28, 23, 59);
    service = FakeUsage();
    history = FakeHistory();
    container = ProviderContainer(
      overrides: [
        sharedPrefsProvider.overrideWithValue(prefs),
        nowProvider.overrideWithValue(() => now),
        usageServiceProvider.overrideWithValue(service),
        historyServiceProvider.overrideWithValue(history),
      ],
    );
  }

  test(
    'midnight resets daily rewards without restart but keeps XP and bank',
    () async {
      await setupClock();
      final notifier = container.read(gameProvider.notifier);
      notifier.completeMission(kMissions.first);
      notifier.setResting(true);
      notifier.completeRest(1);
      final before = container.read(gameProvider);
      now = now.add(const Duration(minutes: 2));
      notifier.ensureCurrentDay();
      final after = container.read(gameProvider);
      expect(after.xp, before.xp);
      expect(after.bankAvailable, before.bankAvailable);
      expect(after.bonusHp, 0);
      expect(after.doneToday, isEmpty);
      expect(after.restRewardFraction, 0);
      expect(after.streak, 2);
      notifier.completeMission(kMissions.first);
      expect(container.read(gameProvider).bankIn, before.bankIn * 2);
    },
  );
  test('reward mutations check the current day themselves', () async {
    await setupClock();
    final notifier = container.read(gameProvider.notifier);
    notifier.completeMission(kMissions.first);
    now = now.add(const Duration(days: 3));
    notifier.completeMission(kMissions.first);
    expect(container.read(gameProvider).bankIn, kMissions.first.bankReward * 2);
    expect(container.read(gameProvider).streak, 1);
  });
  test('failed bank grant never debits and double taps are locked', () async {
    await setupClock();
    final notifier = container.read(gameProvider.notifier);
    notifier.completeMission(kMissions.first);
    notifier.setPauseEnabled(true);
    notifier.setAppLimit('app', 30);
    final balance = container.read(gameProvider).bankAvailable;
    expect(await notifier.spendBank(1, packageName: 'missing'), false);
    service.grant = Completer<bool>();
    final spend = notifier.spendBank(1, packageName: 'app');
    expect(await notifier.spendBank(1, packageName: 'app'), false);
    service.grant!.complete(false);
    expect(await spend, false);
    expect(container.read(gameProvider).bankAvailable, balance);
    service.grant = null;
    expect(await notifier.spendBank(1, packageName: 'app'), true);
    expect(prefs.getInt('bankOut'), 1);
  });
  test(
    'explicit empty monitored set is respected; failed native sync does not save',
    () async {
      await prefs.setStringList('monitoredPackages', []);
      await setupClock();
      expect(container.read(gameProvider).monitoredPackages, isEmpty);
      service.failSync = true;
      await expectLater(
        container.read(gameProvider.notifier).setMonitoredPackage('app', true),
        throwsStateError,
      );
      expect(prefs.getStringList('monitoredPackages'), isEmpty);
      service.failSync = false;
      await container
          .read(gameProvider.notifier)
          .setMonitoredPackage('app', true);
      expect(container.read(gameProvider).monitoredPackages, {'app'});
    },
  );
  test(
    'refresh coalesces, deduplicates history, and flushes changes on pause',
    () async {
      await setupClock();
      await container.read(usageProvider.future);
      final notifier = container.read(usageProvider.notifier);
      expect(history.saves, 1);
      await notifier.refresh();
      expect(history.saves, 1);
      service.pending = Completer<DailyUsage>();
      final a = notifier.refresh();
      final b = notifier.refresh();
      service.pending!.complete(usage(minutes: 101));
      await Future.wait([a, b]);
      expect(service.maxActive, 1);
      expect(history.saves, 1);
      await notifier.setForeground(false);
      expect(history.saves, 2);
      final reads = service.reads;
      await notifier.refresh();
      expect(service.reads, reads);
      expect(container.read(usageProvider).value!.totalMinutes, 101);
    },
  );
  test(
    'midnight during load cannot persist old usage under the new date',
    () async {
      await setupClock();
      service.pending = Completer<DailyUsage>();
      final loading = container.read(usageProvider.future);
      now = now.add(const Duration(minutes: 2));
      service.pending!.complete(usage());
      await loading;
      expect(history.saves, 0);
    },
  );
  test(
    'delete quiesces pending load and disables every read until onboarding',
    () async {
      await setupClock();
      service.pending = Completer<DailyUsage>();
      final loading = container.read(usageProvider.future);
      final deleting = container.read(gameProvider.notifier).deleteAllData();
      await Future<void>.delayed(Duration.zero);
      expect(service.clears, 0);
      service.pending!.complete(usage());
      await loading;
      await deleting;
      expect(history.saves, 0);
      expect(history.clears, 1);
      expect(container.read(gameProvider).collectionEnabled, false);
      final reads = service.reads;
      await container.read(usageProvider.future);
      await container.read(usageRangeProvider(7).future);
      await container.read(historyProvider(7).future);
      await container.read(gameProvider.notifier).resumeCollection();
      expect(service.reads, reads);
      expect(service.rangeReads, 0);
      expect(history.reads, 0);
      expect(service.enables, 0);
      expect(prefs.getBool('collectionTombstone'), true);
    },
  );
  test('clear failure is surfaced and leaves collection disabled', () async {
    await setupClock();
    service.failClear = true;
    await expectLater(
      container.read(gameProvider.notifier).deleteAllData(),
      throwsStateError,
    );
    expect(container.read(gameProvider).collectionEnabled, false);
    expect(prefs.getBool('collectionTombstone'), true);
  });
}

class FakeUsage extends UsageService {
  Completer<DailyUsage>? pending;
  Completer<bool>? grant;
  int reads = 0,
      rangeReads = 0,
      active = 0,
      maxActive = 0,
      clears = 0,
      enables = 0;
  bool failClear = false, failSync = false;
  @override
  Future<DailyUsage> loadToday({
    Map<String, UsageCategory> overrides = const {},
  }) async {
    reads++;
    active++;
    if (active > maxActive) maxActive = active;
    try {
      return await (pending?.future ?? Future.value(usage()));
    } finally {
      active--;
    }
  }

  @override
  Future<DailyUsage> loadRange({
    required int days,
    Map<String, UsageCategory> overrides = const {},
  }) async {
    rangeReads++;
    return usage();
  }

  @override
  Future<List<Map<String, dynamic>>> dailyTotals({int days = 7}) async => [];
  @override
  Future<bool> grantBankTime({
    required String packageName,
    required int minutes,
  }) async => await (grant?.future ?? Future.value(true));
  @override
  Future<void> setCollectionEnabled(bool enabled) async {
    if (enabled) enables++;
  }

  @override
  Future<void> setMonitoredApps(List<String> packages) async {
    if (failSync) throw StateError('sync failed');
  }

  @override
  Future<void> clearLocalData() async {
    if (failClear) throw StateError('clear failed');
    clears++;
  }
}

class FakeHistory extends HistoryService {
  int saves = 0, clears = 0, reads = 0;
  @override
  Future<void> saveUsage(
    DailyUsage usage, {
    required int hp,
    DateTime? date,
  }) async {
    saves++;
  }

  @override
  Future<void> clear() async {
    clears++;
  }

  @override
  Future<List<DailyStat>> recent(int days) async {
    reads++;
    return [];
  }
}
