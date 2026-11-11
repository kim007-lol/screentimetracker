/// A trailing local-calendar range, including the current partial day.
class RecapPeriod {
  RecapPeriod({required this.days, DateTime? now})
    : end = (now ?? DateTime.now()).toLocal() {
    if (![1, 7, 30].contains(days)) throw ArgumentError.value(days, 'days');
  }

  final int days;
  final DateTime end;
  DateTime get start => DateTime(end.year, end.month, end.day - days + 1);

  static String date(DateTime day) =>
      '${day.day.toString().padLeft(2, '0')}/'
      '${day.month.toString().padLeft(2, '0')}/${day.year}';

  String get dateText =>
      days == 1 ? date(end) : '${date(start)} – ${date(end)}';

  String label({required bool english}) => days == 1
      ? (english ? 'Today' : 'Hari ini')
      : (english ? 'Last $days days' : '$days hari terakhir');

  String shareHeading({required bool english, required bool sample}) => [
    label(english: english),
    dateText,
    sample
        ? (english
              ? 'Sample data · not your device usage'
              : 'Data contoh · bukan pemakaian perangkatmu')
        : (english ? 'Device usage data' : 'Data perangkat'),
  ].join('\n');
}

/// Null means unavailable, never measured zero; do not substitute sample values.
int? nightMinutes(Map<String, dynamic>? data, {required int days}) {
  if (data == null ||
      ![1, 7, 30].contains(days) ||
      data['days'] is! int ||
      data['days'] != days ||
      data['startHour'] is! int ||
      data['startHour'] != 22 ||
      data['endHour'] is! int ||
      data['endHour'] != 6) {
    return null;
  }
  final minutes = data['minutes'];
  if (minutes is! int || minutes < 0 || minutes > days * 8 * 60) return null;
  return minutes;
}
