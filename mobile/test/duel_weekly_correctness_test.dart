import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:screentime_companion/core/models/duel_snapshot.dart';
import 'package:screentime_companion/core/services/history_service.dart';
import 'package:screentime_companion/core/state/app_state.dart';
import 'package:screentime_companion/core/state/duel_state.dart';
import 'package:screentime_companion/core/weekly_goal.dart';
import 'package:shared_preferences/shared_preferences.dart';

String code(Map<String, dynamic> data) =>
    base64Url.encode(utf8.encode(jsonEncode(data)));
Map<String, dynamic> payload() => {
  'v': 2,
  'name': 'Raka',
  'minutes': 200,
  'scrollHits': 50,
  'days': 2,
  'at': '2026-10-28T00:00:00.000',
  'balancedDays': 2,
  'periodStart': '20261026',
  'baselineMinutes': 240,
};
DailyStat stat(
  String day, {
  int minutes = 100,
  int baseline = 120,
  int scroll = 20,
}) => DailyStat(
  day: day,
  totalMinutes: minutes,
  scrollHits: scroll,
  replays: 0,
  baselineMinutes: baseline,
  topAppLabel: '',
  topAppMinutes: 0,
  hp: 80,
  categories: const {},
);

void main() {
  group('Snapshot input boundaries', () {
    test(
      'v1 constructor remains v1 and round trips without inventing fields',
      () {
        final old = DuelSnapshot(
          name: 'Raka',
          minutes: 320,
          scrollHits: 480,
          days: 6,
          generatedAt: DateTime(2026, 10, 28, 9, 30),
        );
        expect(old.toJson()['v'], 1);
        expect(old.toJson().containsKey('balancedDays'), isFalse);
        expect(DuelSnapshot.tryDecode(old.encode())!.days, 6);
      },
    );
    test('v2 keeps the baseline, balance count and Monday period', () {
      final decoded = DuelSnapshot.tryDecode(code(payload()));
      expect(decoded, isNotNull);
      expect(decoded!.toJson()['v'], 2);
      expect(decoded.toJson()['balancedDays'], 2);
      expect(decoded.toJson()['periodStart'], '20261026');
      expect(decoded.toJson()['baselineMinutes'], 240);
    });
    test('rejects missing, unsupported and noninteger versions', () {
      for (final version in [null, 0, 3, 1.0, '2']) {
        expect(
          DuelSnapshot.tryDecode(code(payload()..['v'] = version)),
          isNull,
          reason: 'version $version',
        );
      }
    });
    test('rejects doubles, fractions, strings and nonfinite numbers', () {
      for (final key in [
        'minutes',
        'scrollHits',
        'days',
        'balancedDays',
        'baselineMinutes',
      ]) {
        for (final value in [1.0, 1.5, '1', -1]) {
          expect(
            DuelSnapshot.tryDecode(code(payload()..[key] = value)),
            isNull,
            reason: '$key=$value',
          );
        }
      }
      final json = jsonEncode(payload());
      for (final value in ['NaN', 'Infinity', '1e999']) {
        final raw = json.replaceFirst('"minutes":200', '"minutes":$value');
        expect(
          DuelSnapshot.tryDecode(base64Url.encode(utf8.encode(raw))),
          isNull,
        );
      }
    });
    test('rejects implausible counts and inconsistent coverage', () {
      for (final change in <Map<String, dynamic>>[
        {'days': 8},
        {'days': 0},
        {'days': 4},
        {'balancedDays': 3},
        {'minutes': 2881},
        {'scrollHits': 172801},
        {'baselineMinutes': 2881},
      ]) {
        expect(
          DuelSnapshot.tryDecode(code(payload()..addAll(change))),
          isNull,
          reason: '$change',
        );
      }
    });
    test('rejects invalid Mondays, spans and future timestamps', () {
      for (final change in <Map<String, dynamic>>[
        {'periodStart': '20261027'},
        {'periodStart': '20260230'},
        {'periodStart': '20261019'},
        {'periodStart': '20990105'},
        {'periodStart': '2026-10-26'},
        {'at': '2099-01-01T00:00:00'},
        {'at': '2026-02-30T00:00:00'},
        {'at': '2026-10-28'},
      ]) {
        expect(
          DuelSnapshot.tryDecode(code(payload()..addAll(change))),
          isNull,
          reason: '$change',
        );
      }
    });
    test('rejects unsafe names and oversized input before decoding', () {
      for (final name in ['', '  ', 'x' * 25, 'A\nB', 'A\u202eB', 'A\u0000B']) {
        expect(
          DuelSnapshot.tryDecode(code(payload()..['name'] = name)),
          isNull,
        );
      }
      expect(DuelSnapshot.tryDecode('${' ' * 5000}${code(payload())}'), isNull);
      expect(
        DuelSnapshot.tryDecode(code(payload()..['extra'] = 'x' * 5000)),
        isNull,
      );
    });
  });

  group('Calendar-week progress', () {
    final now = DateTime(2026, 10, 28, 12);
    test('counts only unique days from Monday through today', () {
      final progress = weeklyProgressFrom([
        stat('20261025'),
        stat('20261026'),
        stat('20261026'),
        stat('20261027', baseline: 0),
        stat('20261028'),
        stat('20261029'),
      ], now: now);
      expect(progress.balancedDays, 2);
      expect(progress.trackedDays, 3);
      expect(progress.achieved, isFalse);
    });
    test('invalid dates and impossible records cannot earn balanced days', () {
      final progress = weeklyProgressFrom([
        stat('bad'),
        stat('20260230'),
        stat('20261026', minutes: -1),
        stat('20261027', baseline: 2000),
        stat('20261028'),
      ], now: now);
      expect(progress.balancedDays, 1);
    });
    test('five distinct balanced days reach the target on Friday', () {
      final progress = weeklyProgressFrom([
        for (var day = 26; day <= 30; day++) stat('202610$day'),
      ], now: DateTime(2026, 10, 30));
      expect(progress.balancedDays, 5);
      expect(progress.achieved, isTrue);
    });
    test('week comparison uses calendar weeks and equal elapsed weekdays', () {
      final comparison = compareWeeks([
        stat('20261026'),
        stat('20261026'),
        stat('20261028'),
        stat('20261019', minutes: 80),
        stat('20261021', minutes: 80),
        stat('20261025', minutes: 500),
        stat('20261029', minutes: 500),
      ], now: now);
      expect(comparison.thisWeekMinutes, 200);
      expect(comparison.lastWeekMinutes, 160);
      expect(comparison.thisWeekDays, 2);
      expect(comparison.lastWeekDays, 2);
      expect(comparison.ahead, isFalse);
    });
    test('unequal or empty coverage cannot claim ahead', () {
      final comparison = compareWeeks([
        stat('20261026', minutes: 10),
        stat('20261019'),
        stat('20261020'),
      ], now: now);
      expect(comparison.ahead, isFalse);
      expect(compareWeeks([stat('20261019')], now: now).ahead, isFalse);
    });
    test('equal counts on different weekdays are not comparable', () {
      final comparison = compareWeeks([
        stat('20261026', minutes: 10),
        stat('20261027', minutes: 10),
        stat('20261019', minutes: 10),
        stat('20261021', minutes: 10),
      ], now: now);
      expect(comparison.thisWeekDays, 2);
      expect(comparison.lastWeekDays, 2);
      expect(comparison.sameWeekdays, isFalse);
      expect(comparison.comparable, isFalse);
      expect(comparison.ahead, isFalse);
    });
  });

  test(
    'stored peers are deduplicated and capped at five on load and add',
    () async {
      SharedPreferences.setMockInitialValues({
        'duelPeers': [
          for (var i = 0; i < 8; i++) code(payload()..['name'] = 'Peer $i'),
          code(payload()..['name'] = 'Peer 7'),
        ],
      });
      final prefs = await SharedPreferences.getInstance();
      final container = ProviderContainer(
        overrides: [sharedPrefsProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);
      expect(container.read(duelPeersProvider).length, 5);
      final notifier = container.read(duelPeersProvider.notifier);
      expect(notifier.addCode(code(payload()..['name'] = 'New')), isFalse);
      expect(notifier.addCode(code(payload()..['name'] = 'Peer 7')), isTrue);
      notifier.remove('Peer 7');
      expect(notifier.addCode(code(payload()..['name'] = 'New')), isTrue);
      expect(container.read(duelPeersProvider).length, 5);
    },
  );
}
