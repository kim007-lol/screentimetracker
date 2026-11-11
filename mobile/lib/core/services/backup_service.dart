import 'package:shared_preferences/shared_preferences.dart';

import '../models/backup_snapshot.dart';
import 'history_service.dart';
import 'usage_service.dart';

/// The original failure is separate from failures to recover data or stop
/// services. An incomplete rollback must never be presented as a clean abort.
class BackupRestoreException implements Exception {
  BackupRestoreException({
    required this.phase,
    required this.cause,
    required List<String> rollbackErrors,
  }) : rollbackErrors = List.unmodifiable(rollbackErrors);

  final String phase;
  final Object cause;
  final List<String> rollbackErrors;
  bool get rollbackFailed => rollbackErrors.isNotEmpty;

  @override
  String toString() => rollbackFailed
    ? 'Backup restore failed during $phase: $cause. Recovery is incomplete: '
      '${rollbackErrors.join('; ')}. Keep the backup and do not re-enable '
      'collection until local data and permissions have been checked.'
    : 'Backup restore failed during $phase: $cause. Original data was retained '
      'or recovered; collection and optional services remain off. '
      'Check the backup and available storage before retrying.';
}

/// Local-only backup orchestration, with best-effort cross-store recovery.
///
/// The UI must obtain explicit confirmation and pause/drain Dart usage/game
/// writers before restore, then reload its providers. SQLite replacement itself
/// is transactional; SharedPreferences and native storage cannot share that
/// transaction. No service or onboarding consent is restored automatically.
class BackupService {
  BackupService({
    required SharedPreferences preferences,
    required HistoryService history,
    required UsageService usage,
  }) : _preferences = preferences, _history = history, _usage = usage;

  final SharedPreferences _preferences;
  final HistoryService _history;
  final UsageService _usage;
  bool _busy = false;

  static const _disabled = {
    'serviceEnabled', 'pauseEnabled', 'reminderEnabled',
    'collectionEnabled', 'onboarded', 'petOverlayEnabled',
  };
  static const _runtimeOnly = {
    'demoSpeed', 'hpOverride', 'isResting', 'pendingEvolution', 'celebrationTick',
  };

  /// Export every daily_stats row, not just the recent() UI window.
  /// Export is read-only and does not change the current consent state.
  Future<BackupSnapshot> export() async {
    _enter();
    try {
      return BackupSnapshot(
        preferences: _readPreferences(),
        history: await _history.exportAll(),
        nativeData: await _usage.exportNativeData(),
      );
    } finally {
      _busy = false;
    }
  }

  Future<void> restore(BackupSnapshot snapshot) async {
    _enter();
    try {
      // Validate the whole immutable payload before ANY storage/service change.
      final validated = BackupSnapshot.decode(snapshot.encode());
      await _restore(validated);
    } finally {
      _busy = false;
    }
  }

  Future<void> _restore(BackupSnapshot snapshot) async {
    var phase = 'stopping collection';
    Map<String, Object>? originalPreferences;
    BackupSnapshot? originalData;
    var nativeTouched = false;
    var historyTouched = false;
    try {
      originalPreferences = _readPreferences();
      // _keepOff already writes consent flags. Mark preferences as touched
      // before calling it so any failure from here on restores them instead of
      // silently wiping settings while the UI reports a clean abort.
      phase = 'stopping collection';
      final stopErrors = await _keepOff();
      if (stopErrors.isNotEmpty) throw StateError(stopErrors.join('; '));

      phase = 'taking rollback snapshots';
      originalData = BackupSnapshot(
        preferences: const {},
        history: await _history.exportAll(),
        nativeData: await _usage.exportNativeData(),
      );

      // Native validates its own opaque schema BEFORE Dart preferences/history
      // are replaced. Mark touched first to recover even a partial native error.
      phase = 'importing native data';
      nativeTouched = true;
      await _usage.importNativeData(snapshot.nativeData);
      final importedStopErrors = await _keepOff();
      if (importedStopErrors.isNotEmpty) throw StateError(importedStopErrors.join('; '));

      phase = 'replacing preferences';
      await _replacePreferences(snapshot.preferences);

      phase = 'replacing history';
      historyTouched = true;
      await _history.replaceAll(snapshot.history);
    } catch (error) {
      final recoveryErrors = <String>[];
      // Try every applicable store even if one recovery fails. Never restore
      // service opt-ins, runtime overrides, or the old onboarding consent.
      if (nativeTouched && originalData != null) {
        await _attempt('native rollback',
          () => _usage.importNativeData(originalData!.nativeData), recoveryErrors);
      }
      if (originalPreferences != null) {
        await _replacePreferences(originalPreferences, recoveryErrors: recoveryErrors);
      }
      if (historyTouched && originalData != null) {
        await _attempt('history rollback',
          () => _history.replaceAll(originalData!.history), recoveryErrors);
      }
      recoveryErrors.addAll(await _keepOff());
      throw BackupRestoreException(
        phase: phase, cause: error, rollbackErrors: recoveryErrors,
      );
    }
  }

  Map<String, Object> _readPreferences() => {
    for (final key in _preferences.getKeys())
      if (BackupSnapshot.preferenceKeys.contains(key))
        key: _copyPreference(_preferences.get(key)!),
  };

  Object _copyPreference(Object value) => value is List<String>
    ? List<String>.of(value) : value;

  Future<void> _replacePreferences(Map<String, Object> values, {
    List<String>? recoveryErrors,
  }) async {
    final safe = <String, Object>{
      ...values,
      for (final key in _disabled) key: false,
      // Only explicit onboarding clears this tombstone in GameNotifier.
      'collectionTombstone': true,
    };
    final keys = {
      ...BackupSnapshot.preferenceKeys, ..._runtimeOnly, 'collectionTombstone',
    };
    for (final key in keys) {
      Future<void> apply() async {
        final value = safe[key];
        if (value == null) {
          if (_preferences.getKeys().contains(key)) {
            _checked(await _preferences.remove(key), 'remove $key');
          }
        } else {
          await _write(key, value);
        }
      }
      if (recoveryErrors == null) {
        await apply();
      } else {
        await _attempt('preference rollback ($key)', apply, recoveryErrors);
      }
    }
  }

  /// Attempt all shutdown actions even when one fails. The strict native
  /// setCollectionEnabled bridge is authoritative; native import also excludes
  /// service state. The optional hide/cancel wrappers may be platform no-ops.
  Future<List<String>> _keepOff() async {
    final errors = <String>[];
    await _attempt('disable native collection',
      () => _usage.setCollectionEnabled(false), errors);
    await _attempt('hide floating pill', _usage.hidePill, errors);
    await _attempt('hide roaming pet', _usage.hidePetOverlay, errors);
    await _attempt('hide pause', _usage.hidePause, errors);
    await _attempt('cancel reminder', _usage.cancelReminder, errors);
    for (final key in _disabled) {
      await _attempt('disable $key', () => _write(key, false), errors);
    }
    await _attempt('persist collection tombstone',
      () => _write('collectionTombstone', true), errors);
    for (final key in _runtimeOnly) {
      if (_preferences.getKeys().contains(key)) {
        await _attempt('reset $key', () async {
          _checked(await _preferences.remove(key), 'remove $key');
        }, errors);
      }
    }
    return errors;
  }

  Future<void> _write(String key, Object value) async {
    final bool saved;
    if (value is bool) {
      saved = await _preferences.setBool(key, value);
    } else if (value is int) {
      saved = await _preferences.setInt(key, value);
    } else if (value is double) {
      saved = await _preferences.setDouble(key, value);
    } else if (value is String) {
      saved = await _preferences.setString(key, value);
    } else if (value is List<String>) {
      saved = await _preferences.setStringList(key, value);
    } else {
      throw StateError('Unsupported preference type for $key');
    }
    _checked(saved, 'write $key');
  }

  static void _checked(bool success, String operation) {
    if (!success) throw StateError('Unable to $operation; check available storage');
  }

  static Future<void> _attempt(String operation, Future<void> Function() action,
    List<String> errors) async {
    try {
      await action();
    } catch (error) {
      errors.add('$operation: $error');
    }
  }

  void _enter() {
    if (_busy) throw StateError('A backup operation is already in progress');
    _busy = true;
  }
}
