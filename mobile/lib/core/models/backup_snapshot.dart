import 'dart:convert';

import '../services/history_service.dart';
import '../theme/app_tokens.dart';
import 'companion.dart';
import 'duel_snapshot.dart';
import 'pet.dart';

/// Versioned, immutable local backup. Invalid input throws [FormatException].
/// Native key semantics are validated again by the native import endpoint.
final class BackupSnapshot {
  BackupSnapshot._(this.preferences, this.history, this.nativeData);

  static const application = 'com.screentime.companion';
  static const version = 1;
  static const maxBytes = 5 * 1024 * 1024;
  static const maxHistoryRows = 10000;
  static const _maxCount = 2147483647;
  static const _maxTimestamp = 253402300799999;

  static const _booleans = {
    'onboarded', 'pauseEnabled', 'reminderEnabled', 'historyBackfilled',
    'collectionEnabled', 'serviceEnabled', 'petOverlayEnabled',
  };
  static const _modes = {'pillAnimationMode', 'overlayAnimationMode'};
  static const _forms = {'pillForm'};
  static const _integers = <String, (int, int)>{
    'level': (1, _maxCount), 'xp': (0, _maxCount),
    'bonusHp': (0, _maxCount), 'bankIn': (0, _maxCount),
    'bankOut': (0, _maxCount), 'confirmedBankOut': (0, _maxCount),
    'streak': (0, _maxCount), 'restMinutes': (10, 20),
    'pauseSeconds': (3, 10), 'reminderHour': (0, 23), 'reminderMinute': (0, 59),
  };
  static const _dates = {'day', 'lastOpenDay', 'duelCheckDay'};
  static const _lists = {
    'doneToday', 'categoryOverrides', 'appLimits', 'monitoredPackages', 'duelPeers',
  };

  /// Only these app-owned settings/progress keys cross the backup boundary.
  /// Debug overrides, deletion tombstones and unrelated plugin keys do not.
  static final Set<String> preferenceKeys = Set.unmodifiable({
    ..._booleans, ..._integers.keys, ..._dates, ..._lists, ..._modes, ..._forms,
    'userName', 'theme', 'language', 'restRewardFraction',
  });

  final Map<String, Object> preferences;
  final List<DailyStat> history;
  final Map<String, dynamic> nativeData;

  factory BackupSnapshot({
    required Map<String, Object> preferences,
    required List<DailyStat> history,
    required Map<String, dynamic> nativeData,
  }) {
    if (history.length > maxHistoryRows) _invalid('history exceeds 10000 rows');
    // toMap() intentionally omits nonpositive category totals; reject negative
    // values before that conversion can silently discard invalid source data.
    for (final stat in history) {
      for (final value in stat.categories.values) {
        _integer(value, 'history.categories', 0, _maxCount);
      }
    }
    return BackupSnapshot._fromDocument({
      'application': application,
      'version': version,
      'preferences': preferences,
      'history': history.map((stat) => stat.toMap()).toList(),
      'nativeData': nativeData,
    });
  }

  factory BackupSnapshot.decode(String source) {
    _checkSize(source);
    // Bound nesting before jsonDecode, including malicious deeply nested input.
    var depth = 0;
    var quoted = false;
    var escaped = false;
    for (final code in source.codeUnits) {
      if (quoted) {
        if (escaped) {
          escaped = false;
        } else if (code == 92) {
          escaped = true;
        } else if (code == 34) {
          quoted = false;
        }
      } else if (code == 34) {
        quoted = true;
      } else if (code == 91 || code == 123) {
        if (++depth > 32) _invalid('JSON nesting exceeds 32 levels');
      } else if (code == 93 || code == 125) {
        depth--;
      }
    }
    return BackupSnapshot._fromDocument(jsonDecode(source));
  }

  factory BackupSnapshot._fromDocument(Object? value) {
    final data = _map(value, 'backup');
    _exactKeys(data, {'application', 'version', 'preferences', 'history', 'nativeData'}, 'backup');
    if (data['application'] != application) _invalid('wrong application marker');
    if (data['version'] is! int || data['version'] != version) {
      _invalid('unsupported backup version; use a compatible app version');
    }
    final prefs = _preferences(data['preferences']);
    final rawRows = data['history'];
    if (rawRows is! List || rawRows.length > maxHistoryRows) {
      _invalid('history must contain at most 10000 rows');
    }
    final days = <String>{};
    final rows = <DailyStat>[];
    for (var i = 0; i < rawRows.length; i++) {
      final row = _map(rawRows[i], 'history[$i]');
      _exactKeys(row, {
        'day', 'total_minutes', 'scroll_hits', 'replays', 'baseline_minutes',
        'top_app_label', 'top_app_minutes', 'hp', 'categories', 'updated_at',
      }, 'history[$i]');
      final day = _day(row['day'], 'history[$i].day');
      if (!days.add(day)) _invalid('duplicate history day $day');
      for (final field in ['total_minutes', 'scroll_hits', 'replays',
        'baseline_minutes', 'top_app_minutes']) {
        _integer(row[field], 'history[$i].$field', 0, _maxCount);
      }
      _integer(row['hp'], 'history[$i].hp', 0, 100);
      _integer(row['updated_at'], 'history[$i].updated_at', 0, _maxTimestamp);
      _string(row['top_app_label'], 'history[$i].top_app_label', 1024);
      final categories = _categories(row['categories'], 'history[$i].categories');
      rows.add(_BackupDailyStat(row, categories));
    }
    final native = _map(data['nativeData'], 'nativeData');
    final frozenNative = _JsonCopy().copy(native) as Map<String, dynamic>;
    final snapshot = BackupSnapshot._(
      Map.unmodifiable(prefs), List.unmodifiable(rows), frozenNative,
    );
    // Applies the same serialized-size limit to programmatically built exports.
    snapshot.encode();
    return snapshot;
  }

  String encode() {
    final encoded = jsonEncode({
      'application': application,
      'version': version,
      'preferences': preferences,
      'history': history.map((stat) => stat.toMap()).toList(),
      'nativeData': nativeData,
    });
    _checkSize(encoded);
    return encoded;
  }

  static Map<String, Object> _preferences(Object? value) {
    final raw = _map(value, 'preferences');
    final result = <String, Object>{};
    for (final entry in raw.entries) {
      final key = entry.key;
      final value = entry.value;
      if (!preferenceKeys.contains(key)) _invalid('unknown preference $key');
      if (_booleans.contains(key)) {
        if (value is! bool) _invalid('$key must be a boolean');
        result[key] = value;
      } else if (_integers.containsKey(key)) {
        final range = _integers[key]!;
        result[key] = _integer(value, key, range.$1, range.$2);
      } else if (_dates.contains(key)) {
        result[key] = _day(value, key);
      } else if (_lists.contains(key)) {
        final list = _stringList(value, key, key == 'duelPeers' ? 5 : 1000);
        final identifiers = <String>{};
        for (final item in list) {
          switch (key) {
            case 'categoryOverrides':
            case 'appLimits':
              final parts = item.split('=');
              if (parts.length != 2) _invalid('invalid $key entry');
              _package(parts[0], key);
              if (!identifiers.add(parts[0])) _invalid('duplicate $key package');
              if (key == 'categoryOverrides') {
                if (!UsageCategory.values.any((c) => c.name == parts[1])) {
                  _invalid('unknown category in $key');
                }
              } else {
                _decimal(parts[1], key, 1, 480);
              }
            case 'monitoredPackages':
              _package(item, key);
            case 'doneToday':
              if (!kMissions.any((mission) => mission.id == item)) {
                _invalid('unknown mission in doneToday');
              }
            case 'duelPeers':
              final peer = DuelSnapshot.tryDecode(item);
              if (peer == null) _invalid('invalid duelPeers code');
              if (!identifiers.add(peer.name)) _invalid('duplicate duel peer');
          }
        }
        result[key] = List<String>.unmodifiable(list);
      } else if (_modes.contains(key)) {
        final text = _string(value, key, 16);
        if (text != PetAnimationMode.flat.storageValue &&
            text != PetAnimationMode.full.storageValue) {
          _invalid('unknown $key');
        }
        result[key] = text;
      } else if (_forms.contains(key)) {
        final text = _string(value, key, 16);
        if (text != PillForm.head.storageValue &&
            text != PillForm.body.storageValue) {
          _invalid('unknown $key');
        }
        result[key] = text;
      } else if (key == 'restRewardFraction') {
        if (value is! num || !value.isFinite || value < 0 || value > 1) {
          _invalid('restRewardFraction must be finite and between 0 and 1');
        }
        // JSON may encode 0.0 as 0; SharedPreferences must still use setDouble.
        result[key] = value.toDouble();
      } else {
        final text = _string(value, key, 1024);
        if (key == 'theme' && !AppThemeId.values.any((theme) => theme.name == text)) {
          _invalid('unknown theme');
        }
        if (key == 'language' && text != 'id' && text != 'en') _invalid('unknown language');
        result[key] = text;
      }
    }
    return result;
  }

  static Map<UsageCategory, int> _categories(Object? value, String path) {
    final raw = _string(value, path, 1024);
    final result = <UsageCategory, int>{};
    if (raw.isEmpty) return result;
    for (final part in raw.split('|')) {
      final pair = part.split(':');
      if (pair.length != 2) _invalid('invalid $path entry');
      final matches = UsageCategory.values.where((c) => c.name == pair[0]);
      if (matches.isEmpty) _invalid('unknown category in $path');
      final category = matches.first;
      if (result.containsKey(category)) _invalid('duplicate category in $path');
      result[category] = _decimal(pair[1], path, 0, _maxCount);
    }
    return result;
  }

  static int _decimal(String value, String path, int min, int max) {
    if (!RegExp(r'^(0|[1-9][0-9]*)$').hasMatch(value)) _invalid('$path must contain integer counts');
    return _integer(int.tryParse(value), path, min, max);
  }

  static int _integer(Object? value, String path, int min, int max) {
    if (value is! int || value < min || value > max) _invalid('$path must be an integer in $min..$max');
    return value;
  }

  static String _string(Object? value, String path, int maxLength) {
    if (value is! String || value.length > maxLength) _invalid('$path must be a string of at most $maxLength characters');
    return value;
  }

  static List<String> _stringList(Object? value, String path, int maximum) {
    if (value is! List || value.length > maximum) _invalid('$path must be a list of at most $maximum strings');
    final list = value.map((item) => _string(item, path, 2048)).toList();
    if (list.toSet().length != list.length) _invalid('duplicate $path entries');
    return list;
  }

  static void _package(String value, String path) {
    if (value.length > 255 || !RegExp(r'^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$').hasMatch(value)) {
      _invalid('invalid package in $path');
    }
  }

  static String _day(Object? value, String path) {
    final day = _string(value, path, 8);
    if (!RegExp(r'^[0-9]{8}$').hasMatch(day)) _invalid('$path must be yyyyMMdd');
    final year = int.parse(day.substring(0, 4));
    final month = int.parse(day.substring(4, 6));
    final date = int.parse(day.substring(6, 8));
    final parsed = DateTime.utc(year, month, date);
    if (year < 1 || parsed.year != year || parsed.month != month || parsed.day != date) {
      _invalid('$path is not a real calendar date');
    }
    return day;
  }

  static Map<String, dynamic> _map(Object? value, String path) {
    if (value is! Map || value.keys.any((key) => key is! String)) _invalid('$path must be a JSON object');
    return Map<String, dynamic>.from(value);
  }

  static void _exactKeys(Map<String, dynamic> value, Set<String> keys, String path) {
    if (value.length != keys.length || !value.keys.every(keys.contains)) _invalid('unknown or missing $path fields');
  }

  static void _checkSize(String source) {
    if (source.length > maxBytes || utf8.encode(source).length > maxBytes) _invalid('backup exceeds 5 MiB; choose a smaller backup');
  }

  static Never _invalid(String message) => throw FormatException('Invalid backup: $message');
}

/// Preserve every SQLite column (including updated_at and category encoding),
/// without relying on DailyStat.toMap() to regenerate timestamps.
class _BackupDailyStat extends DailyStat {
  _BackupDailyStat(Map<String, dynamic> row, Map<UsageCategory, int> categories)
    : _row = Map<String, Object?>.unmodifiable(row),
      super(
        day: row['day'] as String,
        totalMinutes: row['total_minutes'] as int,
        scrollHits: row['scroll_hits'] as int,
        replays: row['replays'] as int,
        baselineMinutes: row['baseline_minutes'] as int,
        topAppLabel: row['top_app_label'] as String,
        topAppMinutes: row['top_app_minutes'] as int,
        hp: row['hp'] as int,
        categories: Map.unmodifiable(categories),
      );

  final Map<String, Object?> _row;
  @override
  Map<String, Object?> toMap() => Map.of(_row);
}

/// Copies only bounded JSON primitives, never invoking an arbitrary toJson().
class _JsonCopy {
  var _nodes = 0;
  var _stringBytes = 0;

  Object? copy(Object? value, [int depth = 0]) {
    if (++_nodes > 200000 || depth > 24) BackupSnapshot._invalid('nativeData is too deeply nested or has too many entries');
    if (value == null || value is bool) return value;
    if (value is String) {
      if (value.length > BackupSnapshot.maxBytes) BackupSnapshot._invalid('nativeData is too large');
      _stringBytes += utf8.encode(value).length;
      if (_stringBytes > BackupSnapshot.maxBytes) BackupSnapshot._invalid('nativeData is too large');
      return value;
    }
    if (value is int && value >= 0 && value <= 9007199254740991) return value;
    if (value is List) return List.unmodifiable(value.map((item) => copy(item, depth + 1)));
    if (value is Map) {
      final result = <String, dynamic>{};
      for (final entry in value.entries) {
        if (entry.key is! String) BackupSnapshot._invalid('nativeData keys must be strings');
        final key = copy(entry.key, depth + 1) as String;
        result[key] = copy(entry.value, depth + 1);
      }
      return Map<String, dynamic>.unmodifiable(result);
    }
    BackupSnapshot._invalid('nativeData must contain JSON primitives and nonnegative bounded integers');
  }
}
