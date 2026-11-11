import 'package:flutter_test/flutter_test.dart';
import 'package:screentime_companion/core/models/duel_snapshot.dart';
import 'package:screentime_companion/core/weekly_goal.dart';

import 'duel_weekly_correctness_test.dart' show stat;

void main() {
  final now = DateTime(2026, 10, 28, 12);
  DuelSnapshot player({
    String name = 'A',
    int days = 2,
    int balanced = 1,
    int minutes = 100,
    int scroll = 20,
    String week = '20261026',
    int baseline = 240,
  }) => DuelSnapshot(
    name: name,
    minutes: minutes,
    scrollHits: scroll,
    days: days,
    generatedAt: now,
    balancedDays: balanced,
    periodStart: week,
    baselineMinutes: baseline,
  );
  test(
    'balance rate outranks raw minutes, then average minutes, then scroll',
    () {
      final best = player(name: 'B', balanced: 2, minutes: 200);
      final second = player(name: 'C', minutes: 90, scroll: 99);
      final third = player(name: 'D', minutes: 100, scroll: 1);
      final fourth = player(name: 'E', minutes: 100, scroll: 2);
      final sorted = [fourth, third, second, best]
        ..sort(DuelSnapshot.compareScore);
      expect(sorted.map((p) => p.name), ['B', 'C', 'D', 'E']);
      expect(DuelSnapshot.compareScore(player(), player(name: 'Z')), 0);
    },
  );
  test('only same current calendar week and equal nonempty coverage ranks', () {
    final mine = player();
    expect(mine.unrankedReasonAgainst(player(), now: now), isNull);
    expect(
      player(days: 1, balanced: 1).unrankedReasonAgainst(mine, now: now),
      DuelUnrankedReason.coverage,
    );
    expect(
      player(week: '20261019').unrankedReasonAgainst(mine, now: now),
      DuelUnrankedReason.week,
    );
    expect(
      player(
        days: 0,
        balanced: 0,
        minutes: 0,
        scroll: 0,
        baseline: 0,
      ).unrankedReasonAgainst(mine, now: now),
      DuelUnrankedReason.noData,
    );
    expect(
      player(baseline: 0).unrankedReasonAgainst(mine, now: now),
      DuelUnrankedReason.baseline,
    );
    expect(
      player(balanced: 3).unrankedReasonAgainst(mine, now: now),
      DuelUnrankedReason.invalid,
    );
    final legacy = DuelSnapshot(
      name: 'Old',
      minutes: 10,
      scrollHits: 1,
      days: 2,
      generatedAt: now,
    );
    expect(
      legacy.unrankedReasonAgainst(mine, now: now),
      DuelUnrankedReason.legacy,
    );
    expect(
      mine.unrankedReasonAgainst(mine, now: DateTime(2026, 11, 2)),
      DuelUnrankedReason.week,
    );
  });
  test('own snapshot counts distinct baseline-backed real records only', () {
    final mine = duelSnapshotFrom(
      [
        stat('20261026', minutes: 100),
        stat('20261026', minutes: 100),
        stat('20261027', minutes: 400, baseline: 0),
        stat('20261028', minutes: 150, baseline: 130),
        stat('20261029'),
        stat('20261025'),
        stat('bad'),
      ],
      name: 'Self',
      now: now,
    );
    expect(mine.days, 2);
    expect(mine.balancedDays, 1);
    expect(mine.minutes, 250);
    expect(mine.baselineMinutes, 250);
    expect(mine.periodStart, '20261026');
    expect(DuelSnapshot.tryDecode(mine.encode(), now: now), isNotNull);
  });
  test('no available baseline produces honest zero coverage and no rank', () {
    final mine = duelSnapshotFrom(
      [stat('20261028', baseline: 0)],
      name: 'Self',
      now: now,
    );
    expect(mine.days, 0);
    expect(mine.minutes, 0);
    expect(mine.balancedDays, 0);
    expect(
      mine.unrankedReasonAgainst(mine, now: now),
      DuelUnrankedReason.noData,
    );
    expect(DuelSnapshot.tryDecode(mine.encode(), now: now), isNotNull);
  });
  test(
    'conflicting duplicate dates are excluded rather than cherry picked',
    () {
      final stats = [
        stat('20261026'),
        stat('20261026', minutes: 1000),
        stat('20261028'),
      ];
      expect(duelSnapshotFrom(stats, name: 'Self', now: now).days, 1);
      expect(weeklyProgressFrom(stats, now: now).balancedDays, 1);
    },
  );
}
