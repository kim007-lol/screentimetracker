import 'package:flutter_test/flutter_test.dart';
import 'package:screentime_companion/features/rekap/recap_period.dart';

void main() {
  test('daily, weekly and trailing 30-day labels include actual dates', () {
    final now = DateTime(2026, 3, 2, 23);
    final day = RecapPeriod(days: 1, now: now);
    expect(day.label(english: false), 'Hari ini');
    expect(day.dateText, '02/03/2026');
    final week = RecapPeriod(days: 7, now: now);
    expect(week.label(english: true), 'Last 7 days');
    expect(week.dateText, '24/02/2026 – 02/03/2026');
    final month = RecapPeriod(days: 30, now: now);
    expect(month.label(english: false), '30 hari terakhir');
    expect(month.dateText, '01/02/2026 – 02/03/2026');
    expect(month.label(english: true), isNot(contains('Today')));
  });
  test('range handles leap days, years, and local calendar boundaries', () {
    expect(
      RecapPeriod(days: 7, now: DateTime(2024, 3, 1)).dateText,
      '24/02/2024 – 01/03/2024',
    );
    expect(
      RecapPeriod(days: 7, now: DateTime(2026, 1, 2)).dateText,
      '27/12/2025 – 02/01/2026',
    );
    expect(() => RecapPeriod(days: 0), throwsArgumentError);
  });
  test(
    'share heading and caption identify selected period and sample source',
    () {
      final period = RecapPeriod(days: 30, now: DateTime(2026, 10, 28));
      final caption = period.shareHeading(english: true, sample: true);
      expect(caption, contains('Last 30 days'));
      expect(caption, contains('29/09/2026 – 28/10/2026'));
      expect(caption, contains('Sample data'));
      expect(caption, isNot(contains('Today')));
      expect(
        period.shareHeading(english: false, sample: false),
        contains('Data perangkat'),
      );
    },
  );
  test('night insight distinguishes unavailable from measured zero', () {
    expect(nightMinutes(null, days: 7), isNull);
    expect(
      nightMinutes({
        'minutes': 0,
        'startHour': 22,
        'endHour': 6,
        'days': 7,
      }, days: 7),
      0,
    );
    expect(
      nightMinutes({
        'minutes': 48,
        'startHour': 22,
        'endHour': 6,
        'days': 7,
      }, days: 7),
      48,
    );
    for (final data in <Map<String, dynamic>>[
      {'minutes': 48, 'startHour': 22, 'endHour': 6, 'days': 1},
      {'minutes': 48.0, 'startHour': 22, 'endHour': 6, 'days': 7},
      {'minutes': -1, 'startHour': 22, 'endHour': 6, 'days': 7},
      {'minutes': 3361, 'startHour': 22, 'endHour': 6, 'days': 7},
      {'minutes': 48, 'startHour': 21, 'endHour': 6, 'days': 7},
    ]) {
      expect(nightMinutes(data, days: 7), isNull);
    }
  });
}
