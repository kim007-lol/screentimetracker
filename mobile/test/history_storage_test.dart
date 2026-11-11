import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:screentime_companion/core/models/companion.dart';
import 'package:screentime_companion/core/models/usage.dart';
import 'package:screentime_companion/core/services/history_service.dart';
import 'package:sqflite/sqflite.dart';

DailyStat stat(int day) => DailyStat(
  day: HistoryService.dayKey(DateTime(2026, 1, day)),
  totalMinutes: day,
  scrollHits: 0,
  replays: 0,
  baselineMinutes: 100,
  topAppLabel: 'App',
  topAppMinutes: day,
  hp: 90,
  categories: const {},
);

void main() {
  test(
    'database opening is single-flight and export has no 90-day truncation',
    () async {
      final opened = Completer<Database>();
      var opens = 0;
      final db = MemoryDatabase();
      db.rows = List.generate(120, (i) => stat(i + 1).toMap());
      final service = HistoryService(
        opener: () {
          opens++;
          return opened.future;
        },
      );
      final first = service.exportAll();
      final second = service.exportAll();
      expect(opens, 1);
      opened.complete(db);
      expect((await first).length, 120);
      expect((await second).length, 120);
    },
  );
  test('replaceAll rolls back clear and inserts together on failure', () async {
    final db = MemoryDatabase()..rows = [stat(1).toMap()];
    final service = HistoryService(opener: () async => db);
    db.failInsert = true;
    await expectLater(service.replaceAll([stat(2)]), throwsStateError);
    expect((await service.exportAll()).single.day, stat(1).day);
    db.failInsert = false;
    await service.replaceAll([stat(2), stat(3)]);
    expect((await service.exportAll()).map((s) => s.day), [
      stat(2).day,
      stat(3).day,
    ]);
    expect(db.transactions, 2);
    await service.replaceAll([]);
    expect(await service.exportAll(), isEmpty);
  });
  test('backfill skips empty native days instead of inventing history', () async {
    final db = MemoryDatabase();
    final service = HistoryService(opener: () async => db);
    final changed = await service.backfill([
      {
        'day': '20260101',
        'minutes': 0,
        'scrollHits': 0,
        'replays': 0,
        'baselineMinutes': 120,
      },
      {
        'day': '20260102',
        'minutes': 30,
        'scrollHits': 0,
        'replays': 0,
        'baselineMinutes': 120,
      },
    ]);
    expect(changed, isTrue);
    expect((await service.exportAll()).map((s) => s.day), ['20260102']);
  });
  test('backfill after deletion never resurrects older days', () async {
    final db = MemoryDatabase();
    final service = HistoryService(opener: () async => db);
    await service.backfill([
      {
        'day': '20260101',
        'minutes': 10,
        'scrollHits': 0,
        'replays': 0,
        'baselineMinutes': 120,
      },
      {
        'day': '20260102',
        'minutes': 20,
        'scrollHits': 0,
        'replays': 0,
        'baselineMinutes': 120,
      },
    ], afterDay: '20260101');
    expect((await service.exportAll()).map((s) => s.day), ['20260102']);
  });
  test('merge backfill completes a frozen past day from native totals', () async {
    final db = MemoryDatabase();
    final service = HistoryService(opener: () async => db);
    await service.backfill([
      {
        'day': '20260102',
        'minutes': 30,
        'scrollHits': 5,
        'replays': 0,
        'baselineMinutes': 120,
        'topAppLabel': 'Live label',
        'topAppMinutes': 30,
      },
    ]);
    final changed = await service.backfill([
      {
        'day': '20260102',
        'minutes': 55,
        'scrollHits': 9,
        'replays': 1,
        'baselineMinutes': 0,
        'topAppLabel': 'Native label',
        'topAppMinutes': 20,
      },
      {
        'day': '20260103',
        'minutes': 10,
        'scrollHits': 1,
        'replays': 0,
        'baselineMinutes': 120,
      },
    ], beforeDay: '20260103', merge: true);
    expect(changed, isTrue);
    final rows = await service.exportAll();
    final merged = rows.firstWhere((s) => s.day == '20260102');
    expect(merged.totalMinutes, 55);
    expect(merged.scrollHits, 9);
    expect(merged.replays, 1);
    expect(merged.baselineMinutes, 120, reason: 'native zero must not erase');
    expect(merged.topAppLabel, 'Live label');
    expect(rows.any((s) => s.day == '20260103'), isFalse,
        reason: 'today must stay live, never backfilled');
  });
  test(
    'a transient zero baseline never overwrites a stored baseline',
    () async {
      final db = MemoryDatabase();
      final service = HistoryService(opener: () async => db);
      final day = DateTime(2026, 10, 28);
      const apps = [
        AppUsage(
          packageName: 'com.example.app',
          label: 'App',
          minutes: 40,
          opens: 2,
          longestSessionMinutes: 10,
          category: UsageCategory.lainnya,
        ),
      ];
      await service.saveUsage(
        const DailyUsage(
          apps: apps,
          source: UsageSource.android,
          baselineMinutes: 120,
        ),
        hp: 80,
        date: day,
      );
      await service.saveUsage(
        const DailyUsage(
          apps: apps,
          source: UsageSource.android,
          baselineMinutes: 0,
        ),
        hp: 75,
        date: day,
      );
      final saved = (await service.exportAll()).single;
      expect(saved.baselineMinutes, 120);
      expect(saved.hp, 75);
    },
  );
}

class MemoryDatabase implements Database {
  List<Map<String, Object?>> rows = [];
  bool failInsert = false;
  int transactions = 0;
  int lastChanges = 0;
  @override
  Future<void> execute(String sql, [List<Object?>? arguments]) async {}
  @override
  Future<List<Map<String, Object?>>> rawQuery(
    String sql, [
    List<Object?>? arguments,
  ]) async => [
    {'changes()': lastChanges},
  ];
  @override
  Future<List<Map<String, Object?>>> query(
    String table, {
    bool? distinct,
    List<String>? columns,
    String? where,
    List<Object?>? whereArgs,
    String? groupBy,
    String? having,
    String? orderBy,
    int? limit,
    int? offset,
  }) async {
    var result = rows;
    if (where == 'day = ?' && whereArgs?.isNotEmpty == true) {
      result = result.where((row) => row['day'] == whereArgs!.first).toList();
    }
    if (limit != null) result = result.take(limit).toList();
    return List.of(result);
  }

  @override
  Future<T> transaction<T>(
    Future<T> Function(Transaction txn) action, {
    bool? exclusive,
  }) async {
    transactions++;
    final backup = List<Map<String, Object?>>.of(rows);
    try {
      return await action(MemoryTransaction(this));
    } catch (_) {
      rows = backup;
      rethrow;
    }
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class MemoryTransaction implements Transaction {
  MemoryTransaction(this.db);
  final MemoryDatabase db;
  @override
  Future<int> delete(
    String table, {
    String? where,
    List<Object?>? whereArgs,
  }) async {
    final count = db.rows.length;
    db.rows.clear();
    return count;
  }

  @override
  Future<List<Map<String, Object?>>> rawQuery(
    String sql, [
    List<Object?>? arguments,
  ]) => db.rawQuery(sql, arguments);

  @override
  Future<List<Map<String, Object?>>> query(
    String table, {
    bool? distinct,
    List<String>? columns,
    String? where,
    List<Object?>? whereArgs,
    String? groupBy,
    String? having,
    String? orderBy,
    int? limit,
    int? offset,
  }) => db.query(
    table,
    distinct: distinct,
    columns: columns,
    where: where,
    whereArgs: whereArgs,
    groupBy: groupBy,
    having: having,
    orderBy: orderBy,
    limit: limit,
    offset: offset,
  );

  @override
  Future<int> insert(
    String table,
    Map<String, Object?> values, {
    String? nullColumnHack,
    ConflictAlgorithm? conflictAlgorithm,
  }) async {
    if (db.failInsert) throw StateError('disk write failed');
    final index = db.rows.indexWhere((row) => row['day'] == values['day']);
    if (index >= 0 && conflictAlgorithm == ConflictAlgorithm.replace) {
      db.rows[index] = values;
    } else if (index >= 0 && conflictAlgorithm == ConflictAlgorithm.ignore) {
      db.lastChanges = 0;
      return db.rows.length;
    } else {
      db.rows.add(values);
    }
    db.lastChanges = 1;
    return db.rows.length;
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
