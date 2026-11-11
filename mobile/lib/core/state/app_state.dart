import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../balancing.dart';
import '../models/companion.dart';
import '../models/pet.dart';
import '../models/usage.dart';
import '../services/history_service.dart';
import '../services/usage_service.dart';
import '../theme/app_tokens.dart';

/// Di-override di main() setelah SharedPreferences siap.
final sharedPrefsProvider = Provider<SharedPreferences>(
  (ref) => throw UnimplementedError('sharedPrefsProvider belum di-override'),
);

final usageServiceProvider = Provider<UsageService>((ref) => UsageService());
final nowProvider = Provider<DateTime Function()>((ref) => DateTime.now);

class GameState {
  const GameState({
    required this.themeId,
    required this.level,
    required this.xp,
    required this.bonusHp,
    required this.hpOverride,
    required this.isResting,
    required this.bankIn,
    required this.bankOut,
    required this.doneToday,
    required this.restMinutes,
    required this.demoSpeed,
    required this.language,
    required this.categoryOverrides,
    required this.onboarded,
    required this.userName,
    required this.streak,
    required this.pauseEnabled,
    required this.pauseSeconds,
    required this.appLimits,
    required this.reminderEnabled,
    required this.reminderHour,
    required this.reminderMinute,
    this.celebrationTick = 0,
    this.pendingEvolution,
    this.restRewardFraction = 0,
    Set<String>? monitoredPackages,
    this.collectionEnabled = false,
    this.petOverlayEnabled = false,
    this.pillAnimationMode = PetAnimationMode.flat,
    this.pillForm = PillForm.head,
    this.overlayAnimationMode = PetAnimationMode.flat,
    this.petFamily,
  }) : _monitoredPackages = monitoredPackages;

  final double restRewardFraction;
  final Set<String>? _monitoredPackages;
  Set<String> get monitoredPackages =>
      _monitoredPackages ?? kScrollTargets.keys.toSet();
  final bool collectionEnabled;

  /// Pet yang berjalan di atas aplikasi lain. Default mati dan hanya menyala
  /// lewat opt-in eksplisit.
  final bool petOverlayEnabled;

  /// Tampilan pil: sprite statis atau GLB penuh. Tidak menyalakan pil.
  final PetAnimationMode pillAnimationMode;

  /// Bentuk pil: kepala di dalam pil atau badan penuh di sampingnya. Tidak
  /// menyalakan pil.
  final PillForm pillForm;

  /// Tampilan pet keliling: sprite statis atau GLB penuh. Tidak menyalakan
  /// overlay.
  final PetAnimationMode overlayAnimationMode;

  /// Pendamping yang dikunci saat onboarding. Null hanya untuk instalasi lama
  /// yang onboard sebelum pilihan ini ada; UI memakai Momo sebagai bawaan.
  final PetFamily? petFamily;

  final AppThemeId themeId;
  final int level;
  final int xp;

  /// Pemulihan HP yang didapat hari ini dari misi dan istirahat.
  final int bonusHp;

  /// Nilai HP manual untuk pengujian. Null berarti HP dihitung dari pemakaian.
  final int? hpOverride;
  final bool isResting;
  final int bankIn;
  final int bankOut;
  final Set<String> doneToday;
  final int restMinutes;

  /// Mode demo: 1 detik dianggap 1 menit pada timer misi dan istirahat.
  final bool demoSpeed;
  final String language;
  final Map<String, UsageCategory> categoryOverrides;
  final bool onboarded;

  /// Nama panggilan lokal. Kosong berarti sapaan generik.
  final String userName;

  /// Jumlah hari berturut-turut aplikasi dibuka.
  final int streak;

  /// Jeda Sadar: overlay tunda sebelum app target terbuka (prd Bab 10.2).
  final bool pauseEnabled;
  final int pauseSeconds;

  /// Batas harian per paket dalam menit. Tidak ada entri berarti tanpa batas.
  final Map<String, int> appLimits;

  /// Pengingat harian tunggal, dijadwalkan lewat AlarmManager native.
  final bool reminderEnabled;
  final int reminderHour;
  final int reminderMinute;
  final int celebrationTick;

  /// Wujud baru yang baru terbuka, ditampilkan sekali sebagai Evolution Reveal.
  final Stage? pendingEvolution;

  Stage get stage => StageX.fromLevel(level);
  int get bankAvailable => (bankIn - bankOut).clamp(0, 1 << 30);

  GameState copyWith({
    AppThemeId? themeId,
    int? level,
    int? xp,
    int? bonusHp,
    int? hpOverride,
    bool clearHpOverride = false,
    bool? isResting,
    int? bankIn,
    int? bankOut,
    Set<String>? doneToday,
    int? restMinutes,
    bool? demoSpeed,
    String? language,
    Map<String, UsageCategory>? categoryOverrides,
    bool? onboarded,
    String? userName,
    int? streak,
    bool? pauseEnabled,
    int? pauseSeconds,
    Map<String, int>? appLimits,
    bool? reminderEnabled,
    int? reminderHour,
    int? reminderMinute,
    int? celebrationTick,
    Stage? pendingEvolution,
    bool clearEvolution = false,
    double? restRewardFraction,
    Set<String>? monitoredPackages,
    bool? collectionEnabled,
    bool? petOverlayEnabled,
    PetAnimationMode? pillAnimationMode,
    PillForm? pillForm,
    PetAnimationMode? overlayAnimationMode,
    PetFamily? petFamily,
  }) => GameState(
    restRewardFraction: restRewardFraction ?? this.restRewardFraction,
    monitoredPackages: monitoredPackages ?? this.monitoredPackages,
    collectionEnabled: collectionEnabled ?? this.collectionEnabled,
    petOverlayEnabled: petOverlayEnabled ?? this.petOverlayEnabled,
    pillAnimationMode: pillAnimationMode ?? this.pillAnimationMode,
    pillForm: pillForm ?? this.pillForm,
    overlayAnimationMode: overlayAnimationMode ?? this.overlayAnimationMode,
    petFamily: petFamily ?? this.petFamily,
    themeId: themeId ?? this.themeId,
    level: level ?? this.level,
    xp: xp ?? this.xp,
    bonusHp: bonusHp ?? this.bonusHp,
    hpOverride: clearHpOverride ? null : (hpOverride ?? this.hpOverride),
    isResting: isResting ?? this.isResting,
    bankIn: bankIn ?? this.bankIn,
    bankOut: bankOut ?? this.bankOut,
    doneToday: doneToday ?? this.doneToday,
    restMinutes: restMinutes ?? this.restMinutes,
    demoSpeed: demoSpeed ?? this.demoSpeed,
    language: language ?? this.language,
    categoryOverrides: categoryOverrides ?? this.categoryOverrides,
    onboarded: onboarded ?? this.onboarded,
    userName: userName ?? this.userName,
    streak: streak ?? this.streak,
    pauseEnabled: pauseEnabled ?? this.pauseEnabled,
    pauseSeconds: pauseSeconds ?? this.pauseSeconds,
    appLimits: appLimits ?? this.appLimits,
    reminderEnabled: reminderEnabled ?? this.reminderEnabled,
    reminderHour: reminderHour ?? this.reminderHour,
    reminderMinute: reminderMinute ?? this.reminderMinute,
    celebrationTick: celebrationTick ?? this.celebrationTick,
    pendingEvolution: clearEvolution
        ? null
        : (pendingEvolution ?? this.pendingEvolution),
  );
}

class _Keys {
  static const theme = 'theme';
  static const level = 'level';
  static const xp = 'xp';
  static const bonusHp = 'bonusHp';
  static const day = 'day';
  static const bankIn = 'bankIn';
  static const bankOut = 'bankOut';
  static const done = 'doneToday';
  static const rest = 'restMinutes';
  static const demo = 'demoSpeed';
  static const lang = 'language';
  static const cats = 'categoryOverrides';
  static const onboarded = 'onboarded';
  static const userName = 'userName';
  static const streak = 'streak';
  static const pauseEnabled = 'pauseEnabled';
  static const pauseSeconds = 'pauseSeconds';
  static const appLimits = 'appLimits';
  static const reminderEnabled = 'reminderEnabled';
  static const reminderHour = 'reminderHour';
  static const reminderMinute = 'reminderMinute';
  static const lastOpen = 'lastOpenDay';
  static const restReward = 'restRewardFraction';
  static const monitored = 'monitoredPackages';
  static const collection = 'collectionEnabled';
  static const petOverlay = 'petOverlayEnabled';
  static const pillAnimation = 'pillAnimationMode';
  static const pillForm = 'pillForm';
  static const overlayAnimation = 'overlayAnimationMode';
  static const petFamily = 'petFamily';
  static const tombstone = 'collectionTombstone';
  static const confirmedBankOut = 'confirmedBankOut';
  static const historyFloor = 'historyBackfillFloor';
}

class GameNotifier extends Notifier<GameState> {
  late SharedPreferences _prefs;
  bool _deleting = false;
  int _generation = 0;
  Future<bool>? _bankOperation;
  Future<void>? _collectionOperation;
  Future<void>? _monitoredOperation;

  DateTime get _now => ref.read(nowProvider)();

  @override
  GameState build() {
    _prefs = ref.read(sharedPrefsProvider);
    return _loadState();
  }

  GameState _loadState({bool persist = true}) {
    final today = HistoryService.dayKey(_now);
    final isNewDay = _prefs.getString(_Keys.day) != today;
    if (isNewDay && persist) _resetDay(today);
    final streak = _computeStreak(persist: persist);

    final cats = <String, UsageCategory>{};
    for (final entry in _prefs.getStringList(_Keys.cats) ?? const <String>[]) {
      final parts = entry.split('=');
      if (parts.length != 2) continue;
      final match = UsageCategory.values.where((c) => c.name == parts[1]);
      if (match.isNotEmpty) cats[parts[0]] = match.first;
    }

    final themeName = _prefs.getString(_Keys.theme);
    final onboarded = _prefs.getBool(_Keys.onboarded) ?? false;
    final limits = <String, int>{};
    for (final entry
        in _prefs.getStringList(_Keys.appLimits) ?? const <String>[]) {
      final parts = entry.split('=');
      if (parts.length != 2) continue;
      final minutes = int.tryParse(parts[1]) ?? 0;
      if (minutes > 0) limits[parts[0]] = minutes;
    }
    return GameState(
      themeId: AppThemeId.values.firstWhere(
        (t) => t.name == themeName,
        orElse: () => AppThemeId.brutal,
      ),
      level: _prefs.getInt(_Keys.level) ?? 1,
      xp: _prefs.getInt(_Keys.xp) ?? 0,
      bonusHp: _prefs.getInt(_Keys.bonusHp) ?? 0,
      hpOverride: null,
      isResting: false,
      bankIn: _prefs.getInt(_Keys.bankIn) ?? 0,
      bankOut: (_prefs.getInt(_Keys.bankOut) ?? 0).clamp(
        _prefs.getInt(_Keys.confirmedBankOut) ?? 0,
        1 << 30,
      ),
      doneToday: (_prefs.getStringList(_Keys.done) ?? const <String>[]).toSet(),
      restRewardFraction: _prefs.getDouble(_Keys.restReward) ?? 0,
      monitoredPackages:
          (_prefs.getStringList(_Keys.monitored) ??
                  kScrollTargets.keys.toList())
              .toSet(),
      collectionEnabled:
          _prefs.getBool(_Keys.tombstone) != true &&
          (_prefs.getBool(_Keys.onboarded) ?? false) &&
          (_prefs.getBool(_Keys.collection) ?? true),
      restMinutes: _prefs.getInt(_Keys.rest) ?? Balancing.restDefaultMinutes,
      demoSpeed: !kReleaseMode && (_prefs.getBool(_Keys.demo) ?? false),
      language: _prefs.getString(_Keys.lang) ?? 'id',
      categoryOverrides: cats,
      onboarded: onboarded,
      // A choice written just before an interrupted onboarding must not lock
      // the picker for the retry. Only a completed onboarding restores it.
      petFamily: onboarded
          ? PetFamily.parse(_prefs.getString(_Keys.petFamily))
          : null,
      userName: _prefs.getString(_Keys.userName) ?? '',
      streak: streak,
      pauseEnabled: _prefs.getBool(_Keys.pauseEnabled) ?? false,
      pauseSeconds:
          _prefs.getInt(_Keys.pauseSeconds) ?? Balancing.pauseDefaultSeconds,
      appLimits: limits,
      reminderEnabled: _prefs.getBool(_Keys.reminderEnabled) ?? false,
      reminderHour: _prefs.getInt(_Keys.reminderHour) ?? 20,
      reminderMinute: _prefs.getInt(_Keys.reminderMinute) ?? 0,
      petOverlayEnabled: _prefs.getBool(_Keys.petOverlay) ?? false,
      pillAnimationMode: PetAnimationMode.parse(
        _prefs.getString(_Keys.pillAnimation),
      ),
      pillForm: PillForm.parse(_prefs.getString(_Keys.pillForm)),
      overlayAnimationMode: PetAnimationMode.parse(
        _prefs.getString(_Keys.overlayAnimation),
      ),
    );
  }

  void _resetDay(String today) {
    // Write the day marker last: a crash mid-reset leaves the old day marked so
    // the reset is retried instead of stranding yesterday's rewards on a new day.
    _prefs.setInt(_Keys.bonusHp, 0);
    _prefs.setStringList(_Keys.done, const []);
    _prefs.setDouble(_Keys.restReward, 0);
    _prefs.setString(_Keys.day, today);
  }

  /// Call on foreground/resume and ticks. Reward mutations also call this.
  void ensureCurrentDay() {
    if (_deleting) return;
    final today = HistoryService.dayKey(_now);
    if (_prefs.getString(_Keys.day) == today) return;
    _resetDay(today);
    state = state.copyWith(
      bonusHp: 0,
      doneToday: {},
      restRewardFraction: 0,
      clearHpOverride: true,
      streak: _computeStreak(),
    );
  }

  int _computeStreak({bool persist = true}) {
    final today = _now;
    final todayKey = HistoryService.dayKey(today);
    final last = _prefs.getString(_Keys.lastOpen);
    var streak = _prefs.getInt(_Keys.streak) ?? 0;
    if (last == todayKey) return streak == 0 ? 1 : streak;
    // Calendar arithmetic, not 24 hours (DST can have 23/25-hour days).
    final yesterday = DateTime(today.year, today.month, today.day - 1);
    streak = (last == HistoryService.dayKey(yesterday)) ? streak + 1 : 1;
    // After deletion, do not immediately write fresh tracking metadata.
    if (persist) {
      _prefs.setInt(_Keys.streak, streak);
      _prefs.setString(_Keys.lastOpen, todayKey);
    }
    return streak;
  }

  void setUserName(String name) {
    final clean = name.trim();
    _prefs.setString(_Keys.userName, clean);
    state = state.copyWith(userName: clean);
  }

  void setTheme(AppThemeId id) {
    _prefs.setString(_Keys.theme, id.name);
    state = state.copyWith(themeId: id);
  }

  /// Native first, then disk, so a failed write never leaves native watching
  /// a list the app did not save.
  Future<void> _persistOnboardingMonitored(
    Set<String> next,
    int generation,
  ) async {
    final packages = next.toList()..sort();
    final service = ref.read(usageServiceProvider);
    final previous = state.monitoredPackages.toList()..sort();
    await service.setMonitoredApps(packages);
    if (_deleting || generation != _generation) return;
    if (!await _prefs.setStringList(_Keys.monitored, packages)) {
      try {
        await service.setMonitoredApps(previous);
      } catch (_) {
        /* The persistence error below is the one the caller must see. */
      }
      throw StateError('Unable to persist monitored apps');
    }
    if (_deleting || generation != _generation) return;
    state = state.copyWith(monitoredPackages: Set.unmodifiable(next));
  }

  Future<void> finishOnboarding(
    AppThemeId id, {
    required PetFamily petFamily,
    Set<String>? monitoredPackages,
    Map<String, int>? appLimits,
  }) async {
    if (_deleting) return;
    final generation = _generation;
    if (state.petFamily != null && state.petFamily != petFamily) {
      throw StateError('Companion cannot be changed');
    }
    final chosenPet = state.petFamily ?? petFamily;

    if (monitoredPackages != null) {
      final next = monitoredPackages
          .map((pkg) => pkg.trim())
          .where((pkg) => pkg.isNotEmpty)
          .toSet();
      await _persistOnboardingMonitored(next, generation);
      if (_deleting || generation != _generation) return;
    }

    if (appLimits != null) {
      final limits = <String, int>{};
      for (final entry in appLimits.entries) {
        final pkg = entry.key.trim();
        final minutes = entry.value.clamp(0, 480);
        if (pkg.isNotEmpty && minutes > 0) limits[pkg] = minutes;
      }
      if (!await _prefs.setStringList(
        _Keys.appLimits,
        limits.entries.map((entry) => '${entry.key}=${entry.value}').toList(),
      )) {
        throw StateError('Unable to persist app limits');
      }
      if (_deleting || generation != _generation) return;
      state = state.copyWith(appLimits: limits);
    }

    // Persist the companion before onboarding is marked done. The state is
    // updated only in the final copyWith so a failed save can be retried.
    if (state.petFamily == null) {
      if (!await _prefs.setString(_Keys.petFamily, chosenPet.storageValue)) {
        throw StateError('Unable to persist companion');
      }
      if (_deleting || generation != _generation) return;
    }

    // A pause overlay without a monitored app can never appear. Do not leave
    // the service claimed as on when onboarding saves an empty list.
    if (state.monitoredPackages.isEmpty && state.pauseEnabled) {
      setPauseEnabled(false);
      await ref.read(usageServiceProvider).hidePause();
      if (_deleting || generation != _generation) return;
      ref.container.invalidate(permissionStatusProvider);
    }

    if (!await _prefs.setString(_Keys.theme, id.name)) {
      throw StateError('Unable to persist theme');
    }
    if (_deleting || generation != _generation) return;
    // Only fresh onboarding clears the deletion tombstone, never lifecycle.
    if (!await _prefs.remove(_Keys.tombstone)) {
      throw StateError('Unable to clear deletion tombstone');
    }
    if (_deleting || generation != _generation) return;
    // Collection is a separate opt-in step. Run it before marking onboarding
    // done so Home never mounts while tracking consent is still missing; if it
    // fails, the caller sees the error and onboarding stays open.
    await resumeCollection(allowBeforeOnboard: true);
    if (_deleting || generation != _generation) return;
    if (!await _prefs.setBool(_Keys.onboarded, true)) {
      try {
        await ref.read(usageServiceProvider).setCollectionEnabled(false);
      } catch (_) {
        /* The error below is the one the caller must see. */
      }
      await _prefs.setBool(_Keys.collection, false);
      state = state.copyWith(collectionEnabled: false);
      throw StateError('Unable to persist onboarding');
    }
    if (_deleting || generation != _generation) return;
    state = state.copyWith(themeId: id, onboarded: true, petFamily: chosenPet);
  }

  /// Explicit opt-in API for onboarding/lifecycle, never called by build().
  /// Deletion remains opted out even if Android still has UsageStats access.
  Future<void> resumeCollection({bool allowBeforeOnboard = false}) {
    if (_deleting ||
        (!allowBeforeOnboard && !state.onboarded) ||
        _prefs.getBool(_Keys.tombstone) == true) {
      return Future.value();
    }
    return _collectionOperation ??= _enableCollection().whenComplete(() {
      _collectionOperation = null;
    });
  }

  Future<void> _enableCollection() async {
    final generation = _generation;
    await ref.read(usageServiceProvider).setCollectionEnabled(true);
    if (_deleting || generation != _generation) return;
    if (!await _prefs.setBool(_Keys.collection, true)) {
      await ref.read(usageServiceProvider).setCollectionEnabled(false);
      throw StateError('Unable to persist collection consent');
    }
    if (_deleting || generation != _generation) return;
    state = state.copyWith(collectionEnabled: true);
    ref.container.invalidate(usageRangeProvider);
    ref.container.invalidate(historyProvider);
  }

  /// Consent opt-out without deleting anything. Native stops first; the UI
  /// only reports success after the opt-out is persisted.
  Future<void> pauseCollection() async {
    if (_deleting) return;
    final generation = _generation;
    await ref.read(usageServiceProvider).setCollectionEnabled(false);
    if (_deleting || generation != _generation) return;
    if (!await _prefs.setBool(_Keys.collection, false)) {
      try {
        await ref.read(usageServiceProvider).setCollectionEnabled(true);
      } catch (_) {
        /* The persistence error below is the one the caller must see. */
      }
      throw StateError('Unable to persist collection opt-out');
    }
    state = state.copyWith(collectionEnabled: false);
    ref.container.invalidate(usageRangeProvider);
    ref.container.invalidate(historyProvider);
  }

  Future<void> setMonitoredPackage(String packageName, bool enabled) async {
    if (_deleting || packageName.trim().isEmpty) return;
    // Serialize changes so rapid toggles cannot overwrite one another.
    final previous = _monitoredOperation;
    final operation = () async {
      if (previous != null) {
        try {
          await previous;
        } catch (_) {
          /* The caller sees that failure. */
        }
      }
      if (_deleting) return;
      final generation = _generation;
      final next = {...state.monitoredPackages};
      enabled ? next.add(packageName) : next.remove(packageName);
      final service = ref.read(usageServiceProvider);
      await service.setMonitoredApps(next.toList());
      if (_deleting || generation != _generation) return;
      if (!await _prefs.setStringList(_Keys.monitored, next.toList())) {
        await service.setMonitoredApps(state.monitoredPackages.toList());
        throw StateError('Unable to persist monitored apps');
      }
      if (_deleting || generation != _generation) return;
      state = state.copyWith(monitoredPackages: Set.unmodifiable(next));
    }();
    _monitoredOperation = operation;
    try {
      await operation;
    } finally {
      if (identical(_monitoredOperation, operation)) _monitoredOperation = null;
    }
  }

  void setLanguage(String code) {
    _prefs.setString(_Keys.lang, code);
    state = state.copyWith(language: code);
  }

  void setRestMinutes(int minutes) {
    final m = minutes.clamp(Balancing.restMinMinutes, Balancing.restMaxMinutes);
    _prefs.setInt(_Keys.rest, m);
    state = state.copyWith(restMinutes: m);
  }

  void setDemoSpeed(bool value) {
    if (kReleaseMode || _deleting) return;
    _prefs.setBool(_Keys.demo, value);
    state = state.copyWith(demoSpeed: value);
  }

  void setPauseEnabled(bool value) {
    _prefs.setBool(_Keys.pauseEnabled, value);
    state = state.copyWith(pauseEnabled: value);
  }

  void setPauseSeconds(int seconds) {
    final s = seconds.clamp(
      Balancing.pauseMinSeconds,
      Balancing.pauseMaxSeconds,
    );
    _prefs.setInt(_Keys.pauseSeconds, s);
    state = state.copyWith(pauseSeconds: s);
  }

  void setAppLimit(String packageName, int minutes) {
    final next = Map<String, int>.from(state.appLimits);
    final m = minutes.clamp(0, 480);
    if (m == 0) {
      next.remove(packageName);
    } else {
      next[packageName] = m;
    }
    _prefs.setStringList(
      _Keys.appLimits,
      next.entries.map((e) => '${e.key}=${e.value}').toList(),
    );
    state = state.copyWith(appLimits: next);
  }

  void setReminderEnabled(bool value) {
    _prefs.setBool(_Keys.reminderEnabled, value);
    state = state.copyWith(reminderEnabled: value);
  }

  void setReminderTime(int hour, int minute) {
    final h = hour.clamp(0, 23);
    final m = minute.clamp(0, 59);
    _prefs.setInt(_Keys.reminderHour, h);
    _prefs.setInt(_Keys.reminderMinute, m);
    state = state.copyWith(reminderHour: h, reminderMinute: m);
  }

  void setPetOverlayEnabled(bool value) {
    if (_deleting) return;
    _prefs.setBool(_Keys.petOverlay, value);
    state = state.copyWith(petOverlayEnabled: value);
  }

  void setPillAnimationMode(PetAnimationMode mode) {
    if (_deleting) return;
    _prefs.setString(_Keys.pillAnimation, mode.storageValue);
    state = state.copyWith(pillAnimationMode: mode);
  }

  void setPillForm(PillForm form) {
    if (_deleting) return;
    _prefs.setString(_Keys.pillForm, form.storageValue);
    state = state.copyWith(pillForm: form);
  }

  void setOverlayAnimationMode(PetAnimationMode mode) {
    if (_deleting) return;
    _prefs.setString(_Keys.overlayAnimation, mode.storageValue);
    state = state.copyWith(overlayAnimationMode: mode);
  }

  void setCategory(String packageName, UsageCategory category) {
    final next = Map<String, UsageCategory>.from(state.categoryOverrides)
      ..[packageName] = category;
    _prefs.setStringList(
      _Keys.cats,
      next.entries.map((e) => '${e.key}=${e.value.name}').toList(),
    );
    state = state.copyWith(categoryOverrides: next);
  }

  void setHpOverride(int? hp) {
    if (kReleaseMode || _deleting) return;
    state = hp == null
        ? state.copyWith(clearHpOverride: true)
        : state.copyWith(hpOverride: hp.clamp(0, 100));
  }

  void setResting(bool value) {
    if (_deleting) return;
    ensureCurrentDay();
    state = state.copyWith(isResting: value);
  }

  /// Debug: lompat ke level tertentu untuk meninjau tiap wujud.
  void debugSetLevel(int level) {
    if (kReleaseMode || _deleting) return;
    final l = level.clamp(1, 30);
    _prefs.setInt(_Keys.level, l);
    _prefs.setInt(_Keys.xp, 0);
    state = state.copyWith(level: l, xp: 0);
  }

  /// Misi offline selesai: saldo waktu, XP, dan pemulihan HP.
  void completeMission(Mission mission) {
    if (_deleting) return;
    ensureCurrentDay();
    if (state.doneToday.contains(mission.id)) return;
    final done = {...state.doneToday, mission.id};
    final bankIn = state.bankIn + mission.bankReward;
    final bonus = state.bonusHp + mission.hp;
    _prefs.setStringList(_Keys.done, done.toList());
    _prefs.setInt(_Keys.bankIn, bankIn);
    _prefs.setInt(_Keys.bonusHp, bonus);
    state = state.copyWith(doneToday: done, bankIn: bankIn, bonusHp: bonus);
    _addXp(mission.xp);
    _flushRewardHistory();
  }

  /// Reward is the difference between cumulative daily totals, not rounded
  /// separately per session. One full HP/XP reward maximum per calendar day.
  void completeRest(double fraction) {
    if (_deleting) return;
    ensureCurrentDay();
    if (!state.isResting) return;
    final f = fraction.isFinite ? fraction.clamp(0.0, 1.0) : 0.0;
    final before = state.restRewardFraction;
    final after = (before + f).clamp(0.0, 1.0);
    final hpGain =
        Balancing.restRewardTotal(after, Balancing.restMaxHpGain) -
        Balancing.restRewardTotal(before, Balancing.restMaxHpGain);
    final xpGain =
        Balancing.restRewardTotal(after, Balancing.restMaxXp) -
        Balancing.restRewardTotal(before, Balancing.restMaxXp);
    final bonus = state.bonusHp + hpGain;
    _prefs.setDouble(_Keys.restReward, after);
    _prefs.setInt(_Keys.bonusHp, bonus);
    state = state.copyWith(
      bonusHp: bonus,
      isResting: false,
      restRewardFraction: after,
    );
    if (xpGain > 0) _addXp(xpGain);
    _flushRewardHistory();
  }

  void _flushRewardHistory() {
    // Imperative coordination, not a provider dependency: usage observes game.
    final container = ref.container;
    if (container.exists(usageProvider)) {
      unawaited(container.read(usageProvider.notifier).flushHistory());
    }
  }

  /// Adds today's allowance for ONE limited app, never offsets actual usage HP.
  Future<bool> spendBank(int minutes, {required String packageName}) {
    ensureCurrentDay();
    if (_deleting ||
        _bankOperation != null ||
        !state.collectionEnabled ||
        !state.pauseEnabled ||
        (state.appLimits[packageName] ?? 0) <= 0 ||
        minutes <= 0 ||
        minutes > state.bankAvailable) {
      return Future.value(false);
    }
    return _bankOperation = _grantBank(minutes, packageName).whenComplete(() {
      _bankOperation = null;
    });
  }

  Future<bool> _grantBank(int minutes, String packageName) async {
    final generation = _generation;
    final service = ref.read(usageServiceProvider);
    bool granted;
    try {
      granted = await service.grantBankTime(
        packageName: packageName,
        minutes: minutes,
      );
    } catch (_) {
      return false;
    }
    if (!granted || _deleting || generation != _generation) return false;
    ensureCurrentDay();
    final out = state.bankOut + minutes;
    // Native has confirmed. Retain the debit in memory even if disk fails,
    // and keep a confirmed journal for recovery if the primary write fails.
    state = state.copyWith(bankOut: out);
    final journal = await _prefs.setInt(_Keys.confirmedBankOut, out);
    final saved = await _prefs.setInt(_Keys.bankOut, out);
    if (!saved && !journal) {
      throw StateError('Unable to persist confirmed bank debit');
    }
    if (saved) await _prefs.remove(_Keys.confirmedBankOut);
    return true;
  }

  void clearEvolution() => state = state.copyWith(clearEvolution: true);

  void _addXp(int amount) {
    // Arithmetic instead of a per-level loop: imported XP is bounded by int32
    // and could otherwise iterate millions of times on the UI thread.
    final startStage = StageX.fromLevel(state.level);
    final totalXp = state.xp + amount;
    final level = state.level + totalXp ~/ kXpPerLevel;
    final xp = totalXp % kXpPerLevel;
    final nextStage = StageX.fromLevel(level);
    _prefs.setInt(_Keys.level, level);
    _prefs.setInt(_Keys.xp, xp);
    state = state.copyWith(
      level: level,
      xp: xp,
      celebrationTick: state.celebrationTick + 1,
      pendingEvolution: nextStage != startStage ? nextStage : null,
    );
  }

  /// Quiesce every writer before clearing. Failures are surfaced, never
  /// reported as successful deletion. The tombstone survives app restarts.
  Future<void> deleteAllData() async {
    if (_deleting) throw StateError('Deletion already in progress');
    _deleting = true;
    _generation++;
    state = state.copyWith(collectionEnabled: false, isResting: false);
    final container = ref.container;
    final usage = container.exists(usageProvider)
        ? container.read(usageProvider.notifier)
        : null;
    final quiesced = usage?.quiesce();
    try {
      if (!await _prefs.setBool(_Keys.tombstone, true) ||
          !await _prefs.setBool(_Keys.collection, false)) {
        throw StateError('Unable to persist collection opt-out');
      }
      if (quiesced != null) await quiesced;
      for (final pending in <Future<dynamic>?>[
        _bankOperation,
        _collectionOperation,
        _monitoredOperation,
      ]) {
        if (pending != null) {
          try {
            await pending;
          } catch (_) {
            /* Drain; clear below is authoritative. */
          }
        }
      }
      await ref.read(usageServiceProvider).clearLocalData();
      await ref.read(historyServiceProvider).clear();
      if (!await _prefs.clear()) {
        throw StateError('Unable to clear preferences');
      }
      if (!await _prefs.setBool(_Keys.tombstone, true) ||
          !await _prefs.setBool(_Keys.collection, false) ||
          !await _prefs.setString(
            _Keys.historyFloor,
            HistoryService.dayKey(_now),
          )) {
        throw StateError('Unable to persist collection opt-out');
      }
      // Never write fresh day/streak metadata right after a wipe.
      state = _loadState(persist: false);
    } finally {
      _deleting = false;
      ref.container.invalidate(usageProvider);
      ref.container.invalidate(usageRangeProvider);
      ref.container.invalidate(historyProvider);
      ref.container.invalidate(permissionStatusProvider);
      // Rebuild from what actually persisted: on failure the tombstone keeps
      // collection off, and memory must not keep pre-deletion rewards.
      state = _loadState(persist: false);
    }
  }
}

final gameProvider = NotifierProvider<GameNotifier, GameState>(
  GameNotifier.new,
);

final tokensProvider = Provider<AppTokens>(
  (ref) => AppThemes.of(ref.watch(gameProvider.select((s) => s.themeId))),
);

const _emptyUsage = DailyUsage(
  apps: [],
  source: UsageSource.unavailable,
  baselineMinutes: 0,
);

/// One coalesced read at a time. Polling exists only while foregrounded;
/// cached usage survives pause. Every async continuation checks its generation.
class UsageNotifier extends AsyncNotifier<DailyUsage> {
  bool _backfillTried = false;
  bool _foreground = true;
  bool _alive = true;
  int _generation = 0;
  Timer? _timer;
  Future<DailyUsage>? _inFlight;
  Future<void>? _write;
  DailyUsage _cached = _emptyUsage;
  DateTime? _loadedAt;
  DateTime? _lastSavedAt;
  String? _lastFingerprint;

  DateTime get _now => ref.read(nowProvider)();
  bool get _enabled => _alive && ref.read(gameProvider).collectionEnabled;
  bool _valid(int generation) => _enabled && generation == _generation;

  @override
  Future<DailyUsage> build() {
    ref.onDispose(() {
      _alive = false;
      _generation++;
      _timer?.cancel();
    });
    ref.listen(gameProvider, (previous, next) {
      if (previous?.collectionEnabled != next.collectionEnabled) {
        if (!next.collectionEnabled) {
          _generation++;
          _timer?.cancel();
          _cached = _emptyUsage;
          _loadedAt = null;
          state = const AsyncData(_emptyUsage);
        } else {
          _schedule();
          unawaited(refresh());
        }
      } else if (previous?.categoryOverrides != next.categoryOverrides) {
        unawaited(refresh());
      }
    });
    _schedule();
    return _request();
  }

  void _schedule() {
    _timer?.cancel();
    if (!_foreground || !_enabled) return;
    _timer = Timer.periodic(const Duration(minutes: 1), (_) {
      ref.read(gameProvider.notifier).ensureCurrentDay();
      unawaited(refresh());
    });
  }

  Future<void> setForeground(bool foreground) async {
    _foreground = foreground;
    _schedule();
    if (foreground) {
      ref.read(gameProvider.notifier).ensureCurrentDay();
      await refresh();
      // Recap ranges are cached; a device left overnight must not show
      // yesterday's 1/7/30-day windows after resume.
      ref.container.invalidate(usageRangeProvider);
      ref.container.invalidate(historyProvider);
    } else {
      final pending = _inFlight;
      if (pending != null) await pending;
      await flushHistory();
    }
  }

  Future<void> refresh() async {
    if (!_foreground || !_enabled) return;
    await _request();
  }

  Future<DailyUsage> _request() {
    if (!_enabled || !_foreground) return Future.value(_cached);
    return _inFlight ??= _load().whenComplete(() => _inFlight = null);
  }

  Future<DailyUsage> _load() async {
    final generation = _generation;
    final date = _now;
    ref.read(gameProvider.notifier).ensureCurrentDay();
    try {
      final data = await ref
          .read(usageServiceProvider)
          .loadToday(overrides: ref.read(gameProvider).categoryOverrides);
      if (!_valid(generation)) return _emptyUsage;
      if (HistoryService.dayKey(date) != HistoryService.dayKey(_now)) {
        ref.read(gameProvider.notifier).ensureCurrentDay();
        // Discard a load crossing midnight: its totals belong to yesterday, so
        // clear the cache and state instead of showing stale numbers as today.
        _cached = _emptyUsage;
        _loadedAt = null;
        state = const AsyncData(_emptyUsage);
        ref.container.invalidate(usageRangeProvider);
        ref.container.invalidate(historyProvider);
        return _emptyUsage;
      }
      _cached = data;
      _loadedAt = date;
      await _queueSave(force: false);
      if (!_valid(generation)) return _emptyUsage;
      state = AsyncData(data);
      return data;
    } catch (error, stack) {
      if (_valid(generation)) {
        // A transient native failure must not erase the last good cache.
        if (_loadedAt == null) state = AsyncError(error, stack);
      }
      return _cached;
    }
  }

  Future<void> flushHistory() => _queueSave(force: true);

  Future<void> _queueSave({required bool force}) async {
    final previous = _write;
    final generation = _generation;
    final operation = () async {
      if (previous != null) await previous;
      if (!_valid(generation)) return;
      await _saveHistory(generation, force: force);
    }();
    _write = operation;
    try {
      await operation;
    } finally {
      if (identical(_write, operation)) _write = null;
    }
  }

  Future<void> _saveHistory(int generation, {required bool force}) async {
    final data = _cached;
    final date = _loadedAt;
    if (date == null || data.source != UsageSource.android) return;
    final game = ref.read(gameProvider);
    // Only use today's recovery on today's data; an old day's last snapshot
    // can still be flushed on pause, without applying today's bonus.
    final sameDay = HistoryService.dayKey(date) == HistoryService.dayKey(_now);
    final hp = computeHp(usage: data, bonusHp: sameDay ? game.bonusHp : 0);
    final categories = data.minutesByCategory.entries.toList()
      ..sort((a, b) => a.key.name.compareTo(b.key.name));
    final fingerprint = jsonEncode([
      HistoryService.dayKey(date),
      data.totalMinutes,
      data.totalScrollHits,
      data.totalReplays,
      data.baselineMinutes,
      data.topApp?.label,
      data.topApp?.minutes,
      hp,
      for (final e in categories) [e.key.name, e.value],
    ]);
    if (fingerprint == _lastFingerprint) return;
    if (!force &&
        _lastSavedAt != null &&
        HistoryService.dayKey(date) == HistoryService.dayKey(_lastSavedAt!) &&
        _now.difference(_lastSavedAt!) >= Duration.zero &&
        _now.difference(_lastSavedAt!) < const Duration(minutes: 5)) {
      return;
    }
    try {
      final history = ref.read(historyServiceProvider);
      final prefs = ref.read(sharedPrefsProvider);
      if (!_backfillTried) {
        _backfillTried = true;
        // Rebuild the last week from UsageStats on every app start. A session
        // that ends before midnight only stored what was visible then; native
        // per-day totals fill the rest. Past days only, so today's live row
        // keeps its same-day HP bonus.
        final rows = await ref.read(usageServiceProvider).dailyTotals(days: 7);
        if (!_valid(generation)) return;
        if (rows.isNotEmpty) {
          final changed = await history.backfill(
            rows,
            afterDay: prefs.getString(_Keys.historyFloor),
            beforeDay: HistoryService.dayKey(_now),
            merge: true,
          );
          if (!_valid(generation)) return;
          if (changed) ref.container.invalidate(historyProvider);
        }
      }
      if (!_valid(generation)) return;
      await history.saveUsage(data, hp: hp, date: date);
      if (!_valid(generation)) return;
      _lastFingerprint = fingerprint;
      _lastSavedAt = _now;
      ref.container.invalidate(historyProvider);
    } catch (_) {
      // Best-effort history only. Keep dirty cache for the next flush.
      // Deletion/backup failures are deliberately NOT caught here.
    }
  }

  /// Stop reads and wait for any already-started database write before clear.
  Future<void> quiesce() async {
    _generation++;
    _foreground = false;
    _timer?.cancel();
    final pending = _inFlight;
    if (pending != null) await pending;
    final writing = _write;
    if (writing != null) await writing;
    _cached = _emptyUsage;
    _loadedAt = null;
  }
}

final usageProvider = AsyncNotifierProvider<UsageNotifier, DailyUsage>(
  UsageNotifier.new,
);

final historyServiceProvider = Provider<HistoryService>(
  (ref) => HistoryService(),
);

/// Riwayat agregat harian untuk tren dan target mingguan.
final historyProvider = FutureProvider.family<List<DailyStat>, int>((
  ref,
  days,
) async {
  if (!ref.watch(gameProvider.select((s) => s.collectionEnabled))) {
    return const [];
  }
  var active = true;
  ref.onDispose(() => active = false);
  final rows = await ref.read(historyServiceProvider).recent(days);
  return active && ref.read(gameProvider).collectionEnabled ? rows : const [];
});

/// HP harian 0-100. Turun karena menit layar dan hit scroll, pulih dari misi
/// dan istirahat. Tidak pernah menurunkan XP (docs/03).
int computeHp({
  required DailyUsage usage,
  required int bonusHp,
  int? override,
}) {
  if (!kReleaseMode && override != null) return override.clamp(0, 100);
  if (usage.source != UsageSource.android) return 100;
  final penalty =
      (usage.totalMinutes * Balancing.hpPenaltyPerMinute +
              usage.totalScrollHits * Balancing.hpPenaltyPerScroll)
          .round();
  return (100 - penalty + bonusHp).clamp(0, 100);
}

final hpProvider = Provider<int>((ref) {
  final game = ref.watch(gameProvider);
  final usage = ref.watch(usageProvider).asData?.value;
  if (usage == null) return 100;
  return computeHp(
    usage: usage,
    bonusHp: game.bonusHp,
    override: game.hpOverride,
  );
});

final moodProvider = Provider<Mood>(
  (ref) => MoodX.fromHp(ref.watch(hpProvider)),
);

/// Pemakaian beberapa hari terakhir untuk tab Rekap (1, 7, atau 30 hari).
final usageRangeProvider = FutureProvider.family<DailyUsage, int>((
  ref,
  days,
) async {
  if (!ref.watch(gameProvider.select((s) => s.collectionEnabled))) {
    return _emptyUsage;
  }
  final overrides = ref.watch(gameProvider.select((s) => s.categoryOverrides));
  var active = true;
  ref.onDispose(() => active = false);
  final data = await ref
      .read(usageServiceProvider)
      .loadRange(days: days, overrides: overrides);
  return active && ref.read(gameProvider).collectionEnabled
      ? data
      : _emptyUsage;
});

/// Status izin Android, dipakai di Profil dan onboarding.
class PermissionStatus {
  const PermissionStatus({
    required this.usage,
    required this.accessibility,
    required this.overlay,
    required this.pillRunning,
    required this.pauseRunning,
    this.petOverlayRunning = false,
    this.petOverlayFallback = false,
  });

  final bool usage;
  final bool accessibility;
  final bool overlay;
  final bool pillRunning;
  final bool pauseRunning;
  final bool petOverlayRunning;

  /// Full animation could not start; the roaming pet is showing its poster.
  final bool petOverlayFallback;

  bool get coreReady => usage;
}

final permissionStatusProvider = FutureProvider<PermissionStatus>((ref) async {
  final service = ref.read(usageServiceProvider);
  final results = await Future.wait([
    service.hasUsageAccess(),
    service.hasAccessibility(),
    service.hasOverlay(),
    service.isPillVisible(),
    service.isPauseRunning(),
    service.isPetOverlayVisible(),
    service.isPetOverlayFallback(),
  ]);
  return PermissionStatus(
    usage: results[0],
    accessibility: results[1],
    overlay: results[2],
    pillRunning: results[3],
    pauseRunning: results[4],
    petOverlayRunning: results[5],
    petOverlayFallback: results[6],
  );
});
