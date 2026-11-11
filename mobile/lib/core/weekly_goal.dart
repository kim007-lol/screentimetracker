import 'models/duel_snapshot.dart';
import 'services/history_service.dart';

/// Five balanced days in the local Monday–Sunday calendar week.
class WeeklyProgress {
  const WeeklyProgress({
    required this.balancedDays,
    required this.trackedDays,
    required this.target,
  });
  final int balancedDays;
  final int trackedDays;
  final int target;
  bool get achieved => balancedDays >= target;
  double get fraction => target == 0 ? 0 : (balancedDays / target).clamp(0, 1);
}

/// Deduplicate identical records; conflicting duplicates have no trustworthy score.
/// Baseline-free records may be counted as tracked, but never as balanced.
List<DailyStat> _records(
  List<DailyStat> stats,
  DateTime start,
  DateTime end, {
  bool requireBaseline = false,
}) {
  final byDay = <String, DailyStat>{};
  final conflicting = <String>{};
  for (final stat in stats) {
    final day = DuelSnapshot.parseDay(stat.day);
    if (day == null || day.isBefore(start) || day.isAfter(end)) continue;
    final previous = byDay[stat.day];
    if (previous != null &&
        (previous.totalMinutes != stat.totalMinutes ||
            previous.scrollHits != stat.scrollHits ||
            previous.baselineMinutes != stat.baselineMinutes)) {
      conflicting.add(stat.day);
    }
    byDay[stat.day] = stat;
  }
  return byDay.values
      .where(
        (stat) =>
            !conflicting.contains(stat.day) &&
            stat.totalMinutes >= 0 &&
            stat.totalMinutes <= 1440 &&
            stat.scrollHits >= 0 &&
            stat.scrollHits <= DuelSnapshot.maxScrollPerDay &&
            stat.baselineMinutes >= (requireBaseline ? 1 : 0) &&
            stat.baselineMinutes <= 1440,
      )
      .toList();
}

WeeklyProgress weeklyProgressFrom(
  List<DailyStat> stats, {
  int target = 5,
  DateTime? now,
}) {
  final local = (now ?? DateTime.now()).toLocal();
  final end = DateTime(local.year, local.month, local.day);
  final records = _records(stats, DuelSnapshot.monday(end), end);
  return WeeklyProgress(
    balancedDays: records.where((stat) => stat.balanced).length,
    trackedDays: records.length,
    target: target,
  );
}

/// Share only actual distinct records with an available daily personal baseline.
DuelSnapshot duelSnapshotFrom(
  List<DailyStat> stats, {
  required String name,
  DateTime? now,
}) {
  final local = (now ?? DateTime.now()).toLocal();
  final start = DuelSnapshot.monday(local);
  final end = DateTime(local.year, local.month, local.day);
  final records = _records(stats, start, end, requireBaseline: true);
  return DuelSnapshot(
    name: name,
    minutes: records.fold(0, (sum, stat) => sum + stat.totalMinutes),
    scrollHits: records.fold(0, (sum, stat) => sum + stat.scrollHits),
    days: records.length,
    generatedAt: local,
    balancedDays: records.where((stat) => stat.balanced).length,
    periodStart: DuelSnapshot.dayKey(start),
    baselineMinutes: records.fold<int>(
      0,
      (sum, stat) => sum + stat.baselineMinutes,
    ),
  );
}

/// Compare the same elapsed weekdays in adjacent calendar weeks, never a partial
/// week against a full week. Unequal recorded-day coverage cannot claim a win.
class WeekComparison {
  const WeekComparison({
    required this.thisWeekMinutes,
    required this.lastWeekMinutes,
    required this.thisWeekScroll,
    required this.lastWeekScroll,
    required this.thisWeekDays,
    required this.lastWeekDays,
    this.thisStart,
    this.lastStart,
    this.thisEnd,
    this.lastEnd,
    this.sameWeekdays = false,
  });
  final int thisWeekMinutes;
  final int lastWeekMinutes;
  final int thisWeekScroll;
  final int lastWeekScroll;
  final int thisWeekDays;
  final int lastWeekDays;
  final DateTime? thisStart;
  final DateTime? lastStart;
  final DateTime? thisEnd;
  final DateTime? lastEnd;

  /// True when both weeks cover the same weekday positions. Equal day counts
  /// with different weekdays (e.g. Mon/Tue vs Mon/Wed) are not comparable.
  final bool sameWeekdays;
  bool get hasLastWeek => lastWeekDays > 0;
  bool get comparable =>
      thisWeekDays > 0 && thisWeekDays == lastWeekDays && sameWeekdays;
  bool get ahead => comparable && thisWeekMinutes <= lastWeekMinutes;
  int get deltaMinutes => thisWeekMinutes - lastWeekMinutes;
  int get deltaScroll => thisWeekScroll - lastWeekScroll;
}

WeekComparison compareWeeks(List<DailyStat> stats, {DateTime? now}) {
  final local = (now ?? DateTime.now()).toLocal();
  final end = DateTime(local.year, local.month, local.day);
  final start = DuelSnapshot.monday(end);
  final lastStart = DateTime(start.year, start.month, start.day - 7);
  final lastEnd = DateTime(end.year, end.month, end.day - 7);
  final current = _records(stats, start, end);
  final previous = _records(stats, lastStart, lastEnd);
  final thisWeekdays = current
      .map((stat) => DuelSnapshot.parseDay(stat.day)?.weekday)
      .whereType<int>()
      .toSet();
  final lastWeekdays = previous
      .map((stat) => DuelSnapshot.parseDay(stat.day)?.weekday)
      .whereType<int>()
      .toSet();
  final sameWeekdays =
      lastWeekdays.isNotEmpty &&
      thisWeekdays.length == lastWeekdays.length &&
      thisWeekdays.containsAll(lastWeekdays);
  return WeekComparison(
    thisWeekMinutes: current.fold(0, (sum, stat) => sum + stat.totalMinutes),
    lastWeekMinutes: previous.fold(0, (sum, stat) => sum + stat.totalMinutes),
    thisWeekScroll: current.fold(0, (sum, stat) => sum + stat.scrollHits),
    lastWeekScroll: previous.fold(0, (sum, stat) => sum + stat.scrollHits),
    thisWeekDays: current.length,
    lastWeekDays: previous.length,
    thisStart: start,
    thisEnd: end,
    lastStart: lastStart,
    lastEnd: lastEnd,
    sameWeekdays: sameWeekdays,
  );
}
