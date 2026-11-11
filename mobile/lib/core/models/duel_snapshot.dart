import 'dart:convert';

/// Offline, self-reported scores, not authenticated or server-verified.
/// v1 remains readable but cannot establish calendar-week/baseline eligibility.
enum DuelUnrankedReason { legacy, week, noData, coverage, baseline, invalid }

class DuelSnapshot {
  const DuelSnapshot({
    required this.name,
    required this.minutes,
    required this.scrollHits,
    required this.days,
    required this.generatedAt,
    this.balancedDays,
    this.periodStart,
    this.baselineMinutes,
  });

  static const maxCodeLength = 2048;
  static const maxScrollPerDay = 86400;
  static final _unsafeName = RegExp(
    r'[\x00-\x1f\x7f-\x9f\u200b-\u200f\u2028-\u202e\u2060-\u206f\ufeff]',
  );

  final String name;
  final int minutes;
  final int scrollHits;
  final int days;
  final DateTime generatedAt;
  final int? balancedDays;

  /// Local yyyyMMdd Monday. v2 totals cover only baseline-backed recorded days.
  final String? periodStart;
  final int? baselineMinutes;

  bool get isLegacy =>
      balancedDays == null && periodStart == null && baselineMinutes == null;

  Map<String, dynamic> toJson() => {
    'v': isLegacy ? 1 : 2,
    'name': name,
    'minutes': minutes,
    'scrollHits': scrollHits,
    'days': days,
    'at': generatedAt.toIso8601String(),
    if (!isLegacy) 'balancedDays': balancedDays,
    if (!isLegacy) 'periodStart': periodStart,
    if (baselineMinutes != null) 'baselineMinutes': baselineMinutes,
  };

  String encode() =>
      base64Url.encode(utf8.encode(jsonEncode(toJson()))).replaceAll('=', '');

  static bool validName(String name) =>
      name.trim().isNotEmpty &&
      name.length <= 24 &&
      !_unsafeName.hasMatch(name);

  static String dayKey(DateTime day) =>
      '${day.year.toString().padLeft(4, '0')}'
      '${day.month.toString().padLeft(2, '0')}${day.day.toString().padLeft(2, '0')}';

  static DateTime monday(DateTime date) {
    final local = date.toLocal();
    return DateTime(local.year, local.month, local.day - local.weekday + 1);
  }

  static DateTime? parseDay(String key) {
    if (!RegExp(r'^\d{8}$').hasMatch(key)) return null;
    final date = DateTime(
      int.parse(key.substring(0, 4)),
      int.parse(key.substring(4, 6)),
      int.parse(key.substring(6, 8)),
    );
    return date.year >= 2000 && dayKey(date) == key ? date : null;
  }

  bool get _validCounts =>
      days >= 0 &&
      days <= 7 &&
      minutes >= 0 &&
      minutes <= days * 1440 &&
      scrollHits >= 0 &&
      scrollHits <= days * maxScrollPerDay;

  bool get _validBalance =>
      balancedDays != null &&
      balancedDays! >= 0 &&
      balancedDays! <= days &&
      (baselineMinutes == null ||
          (baselineMinutes! >= 0 && baselineMinutes! <= days * 1440));

  static DuelSnapshot? tryDecode(String raw, {DateTime? now}) {
    // Bound allocation before whitespace removal, base64 decoding, or JSON parsing.
    if (raw.isEmpty || raw.length > maxCodeLength) return null;
    try {
      final normalized = raw.trim().replaceAll(RegExp(r'\s'), '');
      if (normalized.isEmpty ||
          !RegExp(r'^[A-Za-z0-9_-]+={0,2}$').hasMatch(normalized)) {
        return null;
      }
      final padded = normalized + ('=' * ((4 - normalized.length % 4) % 4));
      final bytes = base64Url.decode(padded);
      if (bytes.length > 1024) return null;
      final json = jsonDecode(utf8.decode(bytes));
      if (json is! Map<String, dynamic>) return null;
      final version = json['v'];
      if (version is! int || (version != 1 && version != 2)) return null;
      if (json['name'] is! String || !validName(json['name'] as String)) {
        return null;
      }
      for (final field in ['minutes', 'scrollHits', 'days']) {
        if (json[field] is! int) return null;
      }
      final rawAt = json['at'];
      if (rawAt is! String || rawAt.length > 32) return null;
      final at = DateTime.tryParse(rawAt);
      // Reject DateTime's normalization of impossible dates and ambiguous date-only input.
      if (at == null ||
          at.toIso8601String() != rawAt ||
          at.year < 2000 ||
          at.isAfter(now ?? DateTime.now())) {
        return null;
      }
      if (version == 1 &&
          (json.containsKey('balancedDays') ||
              json.containsKey('periodStart') ||
              json.containsKey('baselineMinutes'))) {
        return null;
      }
      if (version == 2) {
        if (json['balancedDays'] is! int ||
            json['periodStart'] is! String ||
            (json.containsKey('baselineMinutes') &&
                json['baselineMinutes'] is! int)) {
          return null;
        }
        final start = parseDay(json['periodStart'] as String);
        // v2 explicitly uses the sender's local calendar, not a UTC week.
        if (start == null ||
            at.isUtc ||
            start.weekday != DateTime.monday ||
            dayKey(monday(at)) != json['periodStart'] ||
            json['days'] > at.weekday) {
          return null;
        }
      }
      final snapshot = DuelSnapshot(
        name: (json['name'] as String).trim(),
        minutes: json['minutes'] as int,
        scrollHits: json['scrollHits'] as int,
        days: json['days'] as int,
        generatedAt: at,
        balancedDays: json['balancedDays'] as int?,
        periodStart: json['periodStart'] as String?,
        baselineMinutes: json['baselineMinutes'] as int?,
      );
      if (!snapshot._validCounts || (version == 2 && !snapshot._validBalance)) {
        return null;
      }
      return snapshot;
    } catch (_) {
      return null;
    }
  }

  DuelUnrankedReason? unrankedReasonAgainst(DuelSnapshot own, {DateTime? now}) {
    if (isLegacy || own.isLegacy) return DuelUnrankedReason.legacy;
    final clock = now ?? DateTime.now();
    final currentWeek = dayKey(monday(clock));
    if (periodStart != currentWeek || own.periodStart != currentWeek) {
      return DuelUnrankedReason.week;
    }
    for (final entry in [this, own]) {
      if (!entry._validCounts ||
          !entry._validBalance ||
          !validName(entry.name) ||
          entry.generatedAt.isAfter(clock) ||
          entry.generatedAt.isUtc ||
          dayKey(monday(entry.generatedAt)) != currentWeek ||
          entry.days > entry.generatedAt.weekday) {
        return DuelUnrankedReason.invalid;
      }
      if (entry.days == 0) return DuelUnrankedReason.noData;
      if (entry.baselineMinutes == null || entry.baselineMinutes! < entry.days) {
        return DuelUnrankedReason.baseline;
      }
    }
    if (days != own.days) return DuelUnrankedReason.coverage;
    return null;
  }

  /// Only call after eligibility filtering. Cross products avoid rounding ties.
  static int compareScore(DuelSnapshot a, DuelSnapshot b) {
    final balance = (b.balancedDays! * a.days).compareTo(
      a.balancedDays! * b.days,
    );
    if (balance != 0) return balance;
    final time = (a.minutes * b.days).compareTo(b.minutes * a.days);
    if (time != 0) return time;
    return (a.scrollHits * b.days).compareTo(b.scrollHits * a.days);
  }
}
