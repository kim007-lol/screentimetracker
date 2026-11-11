import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:screentime_companion/core/models/backup_snapshot.dart';
import 'package:screentime_companion/core/models/companion.dart';
import 'package:screentime_companion/core/models/duel_snapshot.dart';
import 'package:screentime_companion/core/services/backup_service.dart';
import 'package:screentime_companion/core/services/history_service.dart';
import 'package:screentime_companion/core/services/usage_service.dart';

Map<String, Object?> row([String day = '20240229']) => {
  'day': day,
  'total_minutes': 100,
  'scroll_hits': 300,
  'replays': 12,
  'baseline_minutes': 120,
  'top_app_label': 'YouTube',
  'top_app_minutes': 40,
  'hp': 71,
  'categories': 'sosial:60|hiburan:40',
  'updated_at': 1709164800000,
};

Map<String, dynamic> native([int count = 300]) => {
  'version': 1,
  'scrollCounts': {'20240229|com.example.app|scroll': count},
  'monitoredPackages': ['com.example.app'],
  'limits': {'com.example.app': 45},
  'bankAllowances': {'20240229|com.example.app': 15},
};

Map<String, Object> fullPreferences() => {
  'userName': 'Momo', 'theme': 'midnight', 'language': 'en',
  'level': 4, 'xp': 123, 'bonusHp': 28, 'day': '20240229',
  'bankIn': 60, 'bankOut': 15, 'confirmedBankOut': 15,
  'doneToday': <String>['walk', 'read'], 'restMinutes': 15,
  'restRewardFraction': 0.5,
  'categoryOverrides': <String>['com.example.app=sosial'],
  'onboarded': true, 'streak': 7,
  'pauseEnabled': true, 'pauseSeconds': 5,
  'appLimits': <String>['com.example.app=45'],
  'reminderEnabled': true, 'reminderHour': 20, 'reminderMinute': 30,
  'lastOpenDay': '20240229', 'historyBackfilled': true,
  'monitoredPackages': <String>['com.example.app'], 'collectionEnabled': true,
  'petOverlayEnabled': true, 'pillAnimationMode': 'full', 'pillForm': 'body',
  'overlayAnimationMode': 'full', 'duelCheckDay': '20240229',
  'duelPeers': <String>[
    DuelSnapshot(name: 'Peer', minutes: 100, scrollHits: 300, days: 2,
      generatedAt: DateTime(2024, 2, 29)).encode(),
  ],
};

Map<String, dynamic> document() => {
  'application': 'com.screentime.companion',
  'version': 1,
  'preferences': fullPreferences(),
  'history': [row()],
  'nativeData': native(),
};

BackupSnapshot snapshot() => BackupSnapshot.decode(jsonEncode(document()));

class MemoryHistory extends HistoryService {
  MemoryHistory(this.rows, this.events);
  List<DailyStat> rows;
  final List<String> events;
  int replaceCalls = 0;
  Set<int> failOnCalls = {};

  @override
  Future<List<DailyStat>> exportAll() async {
    events.add('history.export');
    return List.of(rows);
  }

  @override
  Future<void> replaceAll(List<DailyStat> replacement) async {
    events.add('history.replace');
    replaceCalls++;
    if (failOnCalls.contains(replaceCalls)) throw StateError('SQLite write failed');
    rows = List.of(replacement);
  }
}

class MemoryUsage extends UsageService {
  MemoryUsage(this.data, this.events);
  Map<String, dynamic> data;
  final List<String> events;
  int importCalls = 0;
  Set<int> failOnCalls = {};
  bool failDisable = false;
  bool collectionEnabled = true;

  @override
  Future<Map<String, dynamic>> exportNativeData() async {
    events.add('native.export');
    return jsonDecode(jsonEncode(data)) as Map<String, dynamic>;
  }

  @override
  Future<void> importNativeData(Map<String, dynamic> replacement) async {
    events.add('native.import');
    importCalls++;
    // Simulate even a partially applied native failure: rollback must repair it.
    data = jsonDecode(jsonEncode(replacement)) as Map<String, dynamic>;
    if (failOnCalls.contains(importCalls)) throw StateError('Native import failed');
  }

  @override
  Future<void> setCollectionEnabled(bool enabled) async {
    events.add('collection.$enabled');
    if (failDisable) throw StateError('Cannot stop collection');
    collectionEnabled = enabled;
  }

  @override
  Future<void> hidePill() async { events.add('pill.hide'); }
  @override
  Future<void> hidePetOverlay() async { events.add('petOverlay.hide'); }
  @override
  Future<void> hidePause() async { events.add('pause.hide'); }
  @override
  Future<void> cancelReminder() async { events.add('reminder.cancel'); }
  @override
  Future<void> clearLocalData() async => fail('Restore must not delete data first');
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('BackupSnapshot', () {
    test('round trips all recognized preferences, SQLite fields and native data', () {
      final original = document();
      final decoded = BackupSnapshot.decode(jsonEncode(original));
      expect(jsonDecode(decoded.encode()), original);
      expect(decoded.preferences, fullPreferences());
      expect(decoded.history.single.categories,
        {UsageCategory.sosial: 60, UsageCategory.hiburan: 40});
      expect(decoded.history.single.toMap(), row());
      expect(decoded.nativeData, native());
    });

    test('empty portable backup is supported', () {
      final value = BackupSnapshot(preferences: {}, history: [], nativeData: {});
      expect(BackupSnapshot.decode(value.encode()).nativeData, isEmpty);
    });

    for (final bad in <Object?>[null, [], '{', 'NaN']) {
      test('rejects corrupt document $bad', () {
        expect(() => BackupSnapshot.decode(bad == '{' ? '{' : jsonEncode(bad)),
          throwsFormatException);
      });
    }

    for (final version in <Object?>[null, 0, 2, 1.0, '1']) {
      test('rejects unsupported or mistyped version $version', () {
        final data = document()..['version'] = version;
        expect(() => BackupSnapshot.decode(jsonEncode(data)), throwsFormatException);
      });
    }

    test('rejects other application, unknown fields and missing stores', () {
      for (final data in [
        document()..['application'] = 'other',
        document()..['extra'] = true,
        document()..remove('nativeData'),
      ]) {
        expect(() => BackupSnapshot.decode(jsonEncode(data)), throwsFormatException);
      }
    });

    test('bounds UTF-8 input, not just character count', () {
      expect(() => BackupSnapshot.decode(' ' * (5 * 1024 * 1024 + 1)),
        throwsFormatException);
      final data = document();
      data['nativeData'] = {'text': '界' * (2 * 1024 * 1024)};
      expect(() => BackupSnapshot.decode(jsonEncode(data)), throwsFormatException);
    });

    test('rejects over 10000 history rows before accepting any', () {
      final data = document()..['history'] = List.generate(10001, (_) => row());
      expect(() => BackupSnapshot.decode(jsonEncode(data)), throwsFormatException);
    });

    for (final day in ['20230229', '20240230', '20241301', '20240001',
      '20240100', '00000101', '2024-02-29']) {
      test('rejects impossible or malformed day $day', () {
        final data = document()..['history'] = [row(day)];
        expect(() => BackupSnapshot.decode(jsonEncode(data)), throwsFormatException);
      });
    }

    test('rejects duplicate dates', () {
      final data = document()..['history'] = [row(), row()];
      expect(() => BackupSnapshot.decode(jsonEncode(data)), throwsFormatException);
    });

    for (final field in ['total_minutes', 'scroll_hits', 'replays',
      'baseline_minutes', 'top_app_minutes', 'hp', 'updated_at']) {
      for (final value in <Object?>[-1, 1.5, 1.0, '2', null, 9007199254740992]) {
        test('rejects invalid integer $field=$value', () {
          final data = document()..['history'] = [row()..[field] = value];
          expect(() => BackupSnapshot.decode(jsonEncode(data)), throwsFormatException);
        });
      }
    }

    test('rejects HP over 100 and missing/unknown SQLite columns', () {
      for (final invalid in [row()..['hp'] = 101,
        row()..remove('hp'), row()..['unexpected'] = 1]) {
        expect(() => BackupSnapshot.decode(jsonEncode(document()..['history'] = [invalid])),
          throwsFormatException);
      }
    });

    for (final categories in ['unknown:5', 'sosial:-1', 'sosial:1.5',
      'sosial:NaN', 'sosial:1|sosial:2', 'sosial', 'sosial:2147483648']) {
      test('rejects corrupt categories $categories', () {
        final data = document()..['history'] = [row()..['categories'] = categories];
        expect(() => BackupSnapshot.decode(jsonEncode(data)), throwsFormatException);
      });
    }

    final invalidPrefs = <String, Object?>{
      'arbitraryInjection': true, 'userName': 2, 'theme': 'unknown', 'language': 'xx',
      'xp': 1.0, 'level': -1, 'bankIn': 2147483648, 'onboarded': 'yes',
      'day': '20230229', 'reminderHour': 24, 'reminderMinute': 60,
      'categoryOverrides': ['com.example.app=unknown'],
      'appLimits': ['com.example.app=NaN'], 'monitoredPackages': [12],
      'doneToday': 'walk', 'duelPeers': ['not-a-duel'],
      'restRewardFraction': -0.5, 'demoSpeed': true, 'hpOverride': 100,
      'pillAnimationMode': 'turbo', 'overlayAnimationMode': 'FULL',
      'pillForm': 'tail', 'petOverlayEnabled': 'yes',
    };
    for (final entry in invalidPrefs.entries) {
      test('rejects invalid preference ${entry.key}', () {
        final data = document();
        (data['preferences'] as Map)[entry.key] = entry.value;
        expect(() => BackupSnapshot.decode(jsonEncode(data)), throwsFormatException);
      });
    }

    test('rejects non-JSON and non-finite native values, plus excessive depth', () {
      for (final value in [Object(), double.nan, double.infinity, -1, 1.5]) {
        expect(() => BackupSnapshot(preferences: {}, history: [],
          nativeData: {'bad': value}), throwsFormatException);
      }
      Object nested = 'end';
      for (var i = 0; i < 40; i++) { nested = [nested]; }
      expect(() => BackupSnapshot(preferences: {}, history: [],
        nativeData: {'nested': nested}), throwsFormatException);
    });

    test('snapshots freeze nested data against post-validation mutation', () {
      final data = snapshot();
      expect(() => data.preferences['xp'] = -1, throwsUnsupportedError);
      expect(() => (data.preferences['doneToday'] as List).add('bad'), throwsUnsupportedError);
      expect(() => data.history.add(data.history.first), throwsUnsupportedError);
      expect(() => data.history.first.categories[UsageCategory.sosial] = -1,
        throwsUnsupportedError);
      expect(() => (data.nativeData['limits'] as Map)['bad'] = Object(),
        throwsUnsupportedError);
    });
  });

  group('BackupService', () {
    late SharedPreferences prefs;
    late MemoryHistory history;
    late MemoryUsage usage;
    late BackupService service;
    late List<String> events;

    setUp(() async {
      SharedPreferences.setMockInitialValues({
        'userName': 'Original', 'xp': 42, 'theme': 'brutal',
        'collectionEnabled': true, 'onboarded': true, 'pauseEnabled': true,
        'reminderEnabled': true, 'serviceEnabled': true,
        'demoSpeed': true, 'hpOverride': 99, 'unrelatedPluginKey': 'keep',
      });
      prefs = await SharedPreferences.getInstance();
      events = [];
      history = MemoryHistory([DailyStat.fromMap(row('20230101'))], events);
      usage = MemoryUsage(native(99), events);
      service = BackupService(preferences: prefs, history: history, usage: usage);
    });

    void expectOff() {
      for (final key in ['collectionEnabled', 'onboarded', 'pauseEnabled',
        'reminderEnabled', 'serviceEnabled', 'petOverlayEnabled']) {
        expect(prefs.getBool(key), false, reason: key);
      }
      expect(prefs.get('demoSpeed'), isNot(true));
      expect(prefs.get('hpOverride'), isNull);
      expect(usage.collectionEnabled, false);
      expect(events, isNot(contains('collection.true')));
    }

    test('exports every history row, no recent-window truncation or debug prefs', () async {
      for (final entry in fullPreferences().entries) {
        final value = entry.value;
        if (value is bool) await prefs.setBool(entry.key, value);
        if (value is String) await prefs.setString(entry.key, value);
        if (value is int) await prefs.setInt(entry.key, value);
        if (value is double) await prefs.setDouble(entry.key, value);
        if (value is List<String>) await prefs.setStringList(entry.key, value);
      }
      history.rows = List.generate(120, (i) => DailyStat.fromMap(row(
        HistoryService.dayKey(DateTime(2020, 1, 1).add(Duration(days: i))))));
      final backup = await service.export();
      expect(backup.history.length, 120);
      expect(backup.preferences, containsPair('duelPeers', fullPreferences()['duelPeers']));
      expect(backup.preferences.keys, isNot(contains('demoSpeed')));
      expect(backup.preferences.keys, isNot(contains('hpOverride')));
      expect(backup.preferences.keys, isNot(contains('unrelatedPluginKey')));
      expect(backup.nativeData, native(99));
      expect(events, contains('history.export'));
      expect(usage.collectionEnabled, true, reason: 'Export is read-only');
    });

    test('restores native before preferences/history and leaves opt-ins off', () async {
      await service.restore(snapshot());
      expect(prefs.getString('userName'), 'Momo');
      expect(prefs.getInt('xp'), 123);
      expect(prefs.getStringList('duelPeers'), fullPreferences()['duelPeers']);
      expect(prefs.getDouble('restRewardFraction'), 0.5);
      expect(prefs.getString('pillAnimationMode'), 'full');
      expect(prefs.getString('overlayAnimationMode'), 'full');
      expect(prefs.getString('pillForm'), 'body');
      expect(prefs.getBool('petOverlayEnabled'), isFalse);
      expect(prefs.getString('unrelatedPluginKey'), 'keep');
      expect(history.rows.single.toMap(), row());
      expect(usage.data, native());
      expect(events.indexOf('collection.false'), lessThan(events.indexOf('native.import')));
      expect(events.indexOf('native.import'), lessThan(events.indexOf('history.replace')));
      expect(events, containsAll([
        'pill.hide', 'petOverlay.hide', 'pause.hide', 'reminder.cancel',
      ]));
      expectOff();
    });

    test('empty native data works and missing recognized prefs are replaced', () async {
      await service.restore(BackupSnapshot(preferences: {}, history: [], nativeData: {}));
      expect(prefs.get('userName'), isNull);
      expect(prefs.get('theme'), isNull);
      expect(history.rows, isEmpty);
      expect(usage.data, isEmpty);
      expectOff();
    });

    test('native failure cannot partially replace preferences/history', () async {
      usage.failOnCalls = {1};
      await expectLater(service.restore(snapshot()), throwsA(isA<BackupRestoreException>()
        .having((e) => e.rollbackFailed, 'rollbackFailed', false)));
      expect(prefs.getString('userName'), 'Original');
      expect(prefs.getInt('xp'), 42);
      expect(history.rows.single.day, '20230101');
      expect(history.replaceCalls, 0);
      expect(usage.data, native(99));
      expectOff();
    });

    test('later history failure restores original preferences and native data', () async {
      history.failOnCalls = {1};
      await expectLater(service.restore(snapshot()), throwsA(isA<BackupRestoreException>()
        .having((e) => e.rollbackFailed, 'rollbackFailed', false)));
      expect(prefs.getString('userName'), 'Original');
      expect(prefs.getInt('xp'), 42);
      expect(prefs.get('duelPeers'), isNull);
      expect(history.rows.single.day, '20230101');
      expect(usage.data, native(99));
      expectOff();
    });

    test('rollback failure is reported distinctly while other stores recover', () async {
      history.failOnCalls = {1, 2};
      await expectLater(service.restore(snapshot()), throwsA(isA<BackupRestoreException>()
        .having((e) => e.rollbackFailed, 'rollbackFailed', true)
        .having((e) => e.rollbackErrors, 'rollback errors', isNotEmpty)));
      expect(prefs.getString('userName'), 'Original');
      expect(usage.data, native(99));
      expectOff();
    });

    test('failure to quiesce aborts data replacement and reports safety failure', () async {
      usage.failDisable = true;
      await expectLater(service.restore(snapshot()), throwsA(isA<BackupRestoreException>()));
      expect(usage.importCalls, 0);
      expect(history.replaceCalls, 0);
      expect(prefs.getString('userName'), 'Original');
      expect(prefs.getBool('collectionEnabled'), false);
      expect(events, containsAll(['pill.hide', 'pause.hide', 'reminder.cancel']));
    });
  });
}
