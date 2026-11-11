import 'dart:math' as math;

import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';

import '../balancing.dart';
import '../models/companion.dart';
import '../models/usage.dart';

/// Satu hari agregat pemakaian, disimpan lokal di SQLite (docs/06 bagian
/// privasi: seluruh data mentah dan agregat tetap di perangkat).
class DailyStat {
  const DailyStat({
    required this.day,
    required this.totalMinutes,
    required this.scrollHits,
    required this.replays,
    required this.baselineMinutes,
    required this.topAppLabel,
    required this.topAppMinutes,
    required this.hp,
    required this.categories,
  });

  /// Kunci hari dalam format `yyyyMMdd`, sama dengan kunci native.
  final String day;
  final int totalMinutes;
  final int scrollHits;
  final int replays;
  final int baselineMinutes;
  final String topAppLabel;
  final int topAppMinutes;
  final int hp;
  final Map<UsageCategory, int> categories;

  DateTime get date => DateTime(
    int.parse(day.substring(0, 4)),
    int.parse(day.substring(4, 6)),
    int.parse(day.substring(6, 8)),
  );

  /// Seimbang bila pemakaian tidak melebihi baseline pengguna sendiri.
  bool get balanced => baselineMinutes > 0 && totalMinutes <= baselineMinutes;

  static String encodeCategories(Map<UsageCategory, int> map) => map.entries
      .where((e) => e.value > 0)
      .map((e) => '${e.key.name}:${e.value}')
      .join('|');

  static Map<UsageCategory, int> decodeCategories(String raw) {
    final out = <UsageCategory, int>{};
    if (raw.isEmpty) return out;
    for (final part in raw.split('|')) {
      final pieces = part.split(':');
      if (pieces.length != 2) continue;
      final match = UsageCategory.values.where((c) => c.name == pieces[0]);
      if (match.isEmpty) continue;
      final minutes = int.tryParse(pieces[1]) ?? 0;
      if (minutes > 0) out[match.first] = minutes;
    }
    return out;
  }

  Map<String, Object?> toMap() => {
    'day': day,
    'total_minutes': totalMinutes,
    'scroll_hits': scrollHits,
    'replays': replays,
    'baseline_minutes': baselineMinutes,
    'top_app_label': topAppLabel,
    'top_app_minutes': topAppMinutes,
    'hp': hp,
    'categories': encodeCategories(categories),
    'updated_at': DateTime.now().millisecondsSinceEpoch,
  };

  factory DailyStat.fromMap(Map<String, Object?> map) => DailyStat(
    day: map['day'] as String,
    totalMinutes: (map['total_minutes'] as num?)?.toInt() ?? 0,
    scrollHits: (map['scroll_hits'] as num?)?.toInt() ?? 0,
    replays: (map['replays'] as num?)?.toInt() ?? 0,
    baselineMinutes: (map['baseline_minutes'] as num?)?.toInt() ?? 0,
    topAppLabel: (map['top_app_label'] as String?) ?? '',
    topAppMinutes: (map['top_app_minutes'] as num?)?.toInt() ?? 0,
    hp: (map['hp'] as num?)?.toInt() ?? 0,
    categories: decodeCategories((map['categories'] as String?) ?? ''),
  );
}

/// Penyimpanan riwayat harian. Riwayat ini yang membuat tren mingguan,
/// target 5 dari 7 hari, dan duel melawan minggu lalu punya data nyata.
class HistoryService {
  HistoryService({Future<Database> Function()? opener}) : _opener = opener;
  final Future<Database> Function()? _opener;
  Database? _db;
  Future<Database>? _opening;

  static String dayKey(DateTime date) =>
      '${date.year}${date.month.toString().padLeft(2, '0')}${date.day.toString().padLeft(2, '0')}';

  Future<Database> _open() {
    final existing = _db;
    if (existing != null) return Future.value(existing);
    return _opening ??= (_opener?.call() ?? _openDatabase())
        .then((db) {
          _db = db;
          return db;
        })
        .whenComplete(() => _opening = null);
  }

  Future<Database> _openDatabase() async {
    final dbPath = p.join(await getDatabasesPath(), 'screentime_companion.db');
    final db = await openDatabase(
      dbPath,
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE daily_stats (
            day TEXT PRIMARY KEY,
            total_minutes INTEGER NOT NULL,
            scroll_hits INTEGER NOT NULL,
            replays INTEGER NOT NULL,
            baseline_minutes INTEGER NOT NULL,
            top_app_label TEXT NOT NULL,
            top_app_minutes INTEGER NOT NULL,
            hp INTEGER NOT NULL,
            categories TEXT NOT NULL,
            updated_at INTEGER NOT NULL
          )
        ''');
      },
    );
    _db = db;
    return db;
  }

  /// Simpan atau perbarui agregat hari ini setelah pemakaian dimuat.
  Future<void> saveUsage(
    DailyUsage usage, {
    required int hp,
    DateTime? date,
  }) async {
    if (usage.source != UsageSource.android) return;
    final top = usage.topApp;
    final stat = DailyStat(
      day: dayKey(date ?? DateTime.now()),
      totalMinutes: usage.totalMinutes,
      scrollHits: usage.totalScrollHits,
      replays: usage.totalReplays,
      baselineMinutes: usage.baselineMinutes,
      topAppLabel: top?.label ?? '',
      topAppMinutes: top?.minutes ?? 0,
      hp: hp,
      categories: usage.minutesByCategory,
    );
    final db = await _open();
    await db.transaction((txn) async {
      // A native baseline read can transiently fail and report 0. Never let
      // that overwrite a positive baseline already stored for the day, or the
      // "balanced" trend silently turns every honest day red.
      final existing = await txn.query(
        'daily_stats',
        columns: ['baseline_minutes'],
        where: 'day = ?',
        whereArgs: [stat.day],
        limit: 1,
      );
      final previous = existing.isEmpty
          ? 0
          : ((existing.first['baseline_minutes'] as num?)?.toInt() ?? 0);
      final row = stat.toMap();
      if (usage.baselineMinutes <= 0 && previous > 0) {
        row['baseline_minutes'] = previous;
      }
      await txn.insert(
        'daily_stats',
        row,
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    });
  }

  /// Riwayat dalam jendela [days] hari terakhir, urut dari terbaru.
  Future<List<DailyStat>> recent(int days) async {
    final span = days.clamp(1, 90);
    final now = DateTime.now();
    final start = DateTime(now.year, now.month, now.day - (span - 1));
    final db = await _open();
    final rows = await db.query(
      'daily_stats',
      where: 'day >= ?',
      whereArgs: [dayKey(start)],
      orderBy: 'day DESC',
      limit: span,
    );
    return rows.map(DailyStat.fromMap).toList();
  }

  /// Full local archive for backup; unlike recent(), no window or row limit.
  Future<List<DailyStat>> exportAll() async {
    final db = await _open();
    final rows = await db.query('daily_stats', orderBy: 'day DESC');
    return rows.map(DailyStat.fromMap).toList();
  }

  /// The coordinator validates the backup before calling this. Clear and all
  /// inserts share one transaction, so failed imports preserve the old archive.
  Future<void> replaceAll(List<DailyStat> stats) async {
    final db = await _open();
    await db.transaction((txn) async {
      await txn.delete('daily_stats');
      for (final stat in stats) {
        await txn.insert(
          'daily_stats',
          stat.toMap(),
          conflictAlgorithm: ConflictAlgorithm.replace,
        );
      }
    });
  }

  Future<void> clear() async {
    final db = await _open();
    await db.delete('daily_stats');
    // Deleted rows would otherwise stay recoverable in free pages.
    await db.execute('VACUUM');
  }

  /// Isi riwayat dari agregat UsageStats (backfill). Tanpa [merge], baris yang
  /// sudah ada tidak ditimpa agar data live tetap paling akurat. Dengan
  /// [merge], baris lampau digabung memakai nilai terbesar: aplikasi yang
  /// ditutup sebelum tengah malam baru menyimpan sebagian pemakaian, jadi
  /// angka native yang lebih lengkap harus menang. Hari kosong dilewati:
  /// UsageStats mencatat perangkat yang tidak dipakai, bukan hari seimbang.
  /// [afterDay] menjaga hari yang sudah dihapus pengguna tidak muncul kembali.
  /// [beforeDay] mencegah hari berjalan ditimpa (bonus HP hanya milik live).
  Future<bool> backfill(
    List<Map<String, dynamic>> rows, {
    String? afterDay,
    String? beforeDay,
    bool merge = false,
  }) async {
    if (rows.isEmpty) return false;
    final db = await _open();
    return db.transaction((txn) async {
      var changed = false;
      for (final row in rows) {
        final day = row['day'] as String?;
        if (day == null || day.length != 8) continue;
        if (afterDay != null && day.compareTo(afterDay) <= 0) continue;
        if (beforeDay != null && day.compareTo(beforeDay) >= 0) continue;
        final minutes = (row['minutes'] as num?)?.toInt() ?? 0;
        final scroll = (row['scrollHits'] as num?)?.toInt() ?? 0;
        final replays = (row['replays'] as num?)?.toInt() ?? 0;
        if (minutes <= 0 && scroll <= 0 && replays <= 0) continue;
        final nativeBaseline =
            (row['baselineMinutes'] as num?)?.toInt() ?? 0;
        DailyStat? previous;
        if (merge) {
          final found = await txn.query(
            'daily_stats',
            where: 'day = ?',
            whereArgs: [day],
            limit: 1,
          );
          if (found.isNotEmpty) previous = DailyStat.fromMap(found.first);
        }
        if (previous == null) {
          final stat = DailyStat(
            day: day,
            totalMinutes: minutes,
            scrollHits: scroll,
            replays: replays,
            baselineMinutes: nativeBaseline,
            topAppLabel: (row['topAppLabel'] as String?) ?? '',
            topAppMinutes: (row['topAppMinutes'] as num?)?.toInt() ?? 0,
            hp: _hpFor(minutes, scroll),
            categories: const {},
          );
          await txn.insert(
            'daily_stats',
            stat.toMap(),
            conflictAlgorithm: ConflictAlgorithm.ignore,
          );
          // last_insert_rowid is stale after INSERT OR IGNORE; changes() is not.
          final count =
              Sqflite.firstIntValue(await txn.rawQuery('SELECT changes()')) ??
              0;
          changed = changed || count > 0;
          continue;
        }
        final mergedMinutes = math.max(minutes, previous.totalMinutes);
        final mergedScroll = math.max(scroll, previous.scrollHits);
        final mergedReplays = math.max(replays, previous.replays);
        final mergedBaseline = nativeBaseline > 0
            ? nativeBaseline
            : previous.baselineMinutes;
        if (mergedMinutes == previous.totalMinutes &&
            mergedScroll == previous.scrollHits &&
            mergedReplays == previous.replays &&
            mergedBaseline == previous.baselineMinutes) {
          continue;
        }
        final merged = DailyStat(
          day: day,
          totalMinutes: mergedMinutes,
          scrollHits: mergedScroll,
          replays: mergedReplays,
          baselineMinutes: mergedBaseline,
          topAppLabel: previous.topAppLabel.isNotEmpty
              ? previous.topAppLabel
              : (row['topAppLabel'] as String?) ?? '',
          topAppMinutes: math.max(
            previous.topAppMinutes,
            (row['topAppMinutes'] as num?)?.toInt() ?? 0,
          ),
          hp: _hpFor(mergedMinutes, mergedScroll),
          categories: previous.categories,
        );
        await txn.insert(
          'daily_stats',
          merged.toMap(),
          conflictAlgorithm: ConflictAlgorithm.replace,
        );
        changed = true;
      }
      return changed;
    });
  }

  int _hpFor(int minutes, int scroll) {
    final penalty =
        (minutes * Balancing.hpPenaltyPerMinute +
                scroll * Balancing.hpPenaltyPerScroll)
            .round();
    return (100 - penalty).clamp(0, 100);
  }
}
