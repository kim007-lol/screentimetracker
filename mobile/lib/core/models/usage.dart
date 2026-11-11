import 'companion.dart';

/// Statistik satu aplikasi pada satu hari.
class AppUsage {
  const AppUsage({
    required this.packageName,
    required this.label,
    required this.minutes,
    required this.opens,
    required this.longestSessionMinutes,
    required this.category,
    this.seconds = 0,
    this.scrollHits = 0,
    this.replays = 0,
  });

  final String packageName;
  final String label;
  final int minutes;

  /// Foreground seconds before flooring to [minutes]. Kept so a short session
  /// remains visible (<1m) instead of becoming an indistinguishable zero.
  final int seconds;
  final int opens;
  final int longestSessionMinutes;
  final UsageCategory category;
  final int scrollHits;
  final int replays;

  AppUsage copyWith({UsageCategory? category}) => AppUsage(
    packageName: packageName,
    label: label,
    minutes: minutes,
    seconds: seconds,
    opens: opens,
    longestSessionMinutes: longestSessionMinutes,
    category: category ?? this.category,
    scrollHits: scrollHits,
    replays: replays,
  );
}

/// Sumber data pemakaian: nyata dari Android, contoh bila izin belum ada, atau
/// belum terbaca (tidak pernah ditampilkan sebagai angka nyata/contoh).
enum UsageSource { android, sample, unavailable }

class DailyUsage {
  const DailyUsage({
    required this.apps,
    required this.source,
    required this.baselineMinutes,
    this.permissionGranted = false,
    this.accessibilityEnabled = false,
  });

  final List<AppUsage> apps;
  final UsageSource source;

  /// Rata-rata pemakaian pengguna sendiri, dasar perbandingan (docs/05).
  final int baselineMinutes;
  final bool permissionGranted;
  final bool accessibilityEnabled;

  int get totalMinutes => apps.fold(0, (a, b) => a + b.minutes);
  int get totalSeconds => apps.fold(0, (a, b) => a + b.seconds);
  int get totalScrollHits => apps.fold(0, (a, b) => a + b.scrollHits);
  int get totalReplays => apps.fold(0, (a, b) => a + b.replays);

  AppUsage? get topApp {
    if (apps.isEmpty) return null;
    return apps.reduce((a, b) {
      if (a.minutes != b.minutes) return a.minutes >= b.minutes ? a : b;
      return a.seconds >= b.seconds ? a : b;
    });
  }

  /// Selisih terhadap baseline, negatif berarti lebih sedikit dari biasanya.
  int get deltaMinutes => totalMinutes - baselineMinutes;

  Map<UsageCategory, int> get minutesByCategory {
    final map = <UsageCategory, int>{};
    for (final a in apps) {
      map.update(a.category, (v) => v + a.minutes, ifAbsent: () => a.minutes);
    }
    return map;
  }
}

/// Format durasi menit menjadi "3j 24m".
String formatDuration(int minutes) {
  final m = minutes.abs();
  final h = m ~/ 60;
  final r = m % 60;
  if (h == 0) return '${r}m';
  if (r == 0) return '${h}j';
  return '${h}j ${r}m';
}
