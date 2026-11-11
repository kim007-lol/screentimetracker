import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import '../models/companion.dart';
import '../models/usage.dart';

/// Pemetaan awal paket -> kategori. Dapat dikustomisasi pengguna di Profil.
const Map<String, UsageCategory> kDefaultCategories = {
  'com.instagram.android': UsageCategory.sosial,
  'com.zhiliaoapp.musically': UsageCategory.sosial,
  'com.ss.android.ugc.trill': UsageCategory.sosial,
  'com.facebook.katana': UsageCategory.sosial,
  'com.whatsapp': UsageCategory.sosial,
  'org.telegram.messenger': UsageCategory.sosial,
  'com.twitter.android': UsageCategory.sosial,
  'com.google.android.youtube': UsageCategory.hiburan,
  'com.spotify.music': UsageCategory.hiburan,
  'com.netflix.mediaclient': UsageCategory.hiburan,
  'com.android.chrome': UsageCategory.produktivitas,
  'com.google.android.gm': UsageCategory.kerja,
  'com.slack': UsageCategory.kerja,
  'com.notion.id': UsageCategory.kerja,
  'com.duolingo': UsageCategory.belajar,
  'com.google.android.apps.classroom': UsageCategory.belajar,
};

/// Paket yang dipantau scroll-nya (feed pendek), sama dengan config accessibility native.
const Map<String, String> kScrollTargets = {
  'com.instagram.android': 'Instagram',
  'com.zhiliaoapp.musically': 'TikTok',
  'com.ss.android.ugc.trill': 'TikTok',
  'com.google.android.youtube': 'YouTube',
  'com.facebook.katana': 'Facebook',
};

/// Jembatan ke modul native Kotlin. Logika game tidak ada di sisi native.
class UsageService {
  UsageService({MethodChannel? channel})
    : _channel =
          channel ?? const MethodChannel('com.screentimetrack/usage');

  final MethodChannel _channel;

  bool get _isAndroid =>
      !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

  Future<bool> hasUsageAccess() async {
    if (!_isAndroid) return false;
    try {
      return await _channel.invokeMethod<bool>('hasUsageAccess') ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  Future<bool> hasAccessibility() async {
    if (!_isAndroid) return false;
    try {
      return await _channel.invokeMethod<bool>('hasAccessibility') ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  Future<bool> hasOverlay() async {
    if (!_isAndroid) return false;
    try {
      return await _channel.invokeMethod<bool>('hasOverlay') ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  Future<void> openUsageSettings() => _safeCall('openUsageSettings');
  Future<void> openAccessibilitySettings() =>
      _safeCall('openAccessibilitySettings');
  Future<void> openOverlaySettings() => _safeCall('openOverlaySettings');

  /// Floating Pill (overlay native). Fitur opsional, hanya hidup bila izin
  /// overlay diberikan (docs/06 bagian izin bertahap).
  Future<bool> isPillVisible() async {
    if (!_isAndroid) return false;
    try {
      return await _channel.invokeMethod<bool>('isPillVisible') ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  Future<bool> showPill({
    required int background,
    required int surface,
    required int ink,
    required int accent,
    required double radius,
    String language = 'id',
    String stage = 'bayi',
    String animation = 'flat',
    String form = 'head',
    String pet = 'momo',
    int hpBonus = 0,
    int hpHealthy = 0xFF3DDC84,
    int hpTired = 0xFFFFB020,
    int hpCritical = 0xFFFF4D4D,
  }) async {
    if (!_isAndroid) return false;
    try {
      final ok = await _channel.invokeMethod<bool>('showPill', {
        'language': language,
        'stage': stage,
        'animation': animation,
        'form': form,
        'pet': pet,
        'background': background,
        'surface': surface,
        'ink': ink,
        'accent': accent,
        'radius': radius,
        'hpBonus': hpBonus,
        'hpHealthy': hpHealthy,
        'hpTired': hpTired,
        'hpCritical': hpCritical,
      });
      return ok ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  /// Pemulihan HP hari ini (misi/istirahat). Pill menghitung HP sendiri dari
  /// pemakaian native; bonus ini hanya perlu dikirim saat berubah.
  Future<void> syncPillHp(int bonusHp) async {
    if (!_isAndroid) return;
    try {
      await _channel.invokeMethod<void>('setPillHpBonus', {'bonus': bonusHp});
    } on PlatformException {
      // Pill mungkin belum aktif; applyPill mengirim ulang saat dinyalakan.
    } on MissingPluginException {
      // Modul native belum terpasang.
    }
  }

  Future<void> hidePill() => _safeCall('hidePill');

  /// Pet utuh yang berjalan di atas aplikasi lain. Opt-in terpisah dari pill.
  Future<bool> showPetOverlay({
    required String animation,
    required String language,
    required String stage,
    required int hpBonus,
    String pet = 'momo',
  }) async {
    if (!_isAndroid) return false;
    try {
      final ok = await _channel.invokeMethod<bool>('showPetOverlay', {
        'language': language,
        'stage': stage,
        'animation': animation,
        'pet': pet,
        'hpBonus': hpBonus,
      });
      return ok ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  Future<bool> isPetOverlayVisible() async {
    if (!_isAndroid) return false;
    try {
      return await _channel.invokeMethod<bool>('isPetOverlayVisible') ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  /// Mode penuh bisa jatuh ke poster statis bila WebView/model gagal.
  /// Settings menampilkan kondisi sebenarnya, bukan mengaku full.
  Future<bool> isPetOverlayFallback() async {
    if (!_isAndroid) return false;
    try {
      return await _channel.invokeMethod<bool>('isPetOverlayFallback') ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  /// Tidur mengalahkan semua aksi spontan di pil dan pet keliling.
  Future<void> setPetResting(bool resting) async {
    if (!_isAndroid) return;
    try {
      await _channel.invokeMethod<void>('setPetResting', {'resting': resting});
    } on PlatformException {
      // Layanan mungkin belum aktif; status tetap tersimpan di Flutter.
    } on MissingPluginException {
      // Modul native belum terpasang.
    }
  }

  /// Strict: a privacy/restore stop must not pretend the overlay is gone.
  Future<void> hidePetOverlay() async {
    if (_isAndroid) await _channel.invokeMethod<void>('hidePetOverlay');
  }

  /// Operasi privasi harus meneruskan error: UI tidak boleh mengaku berhasil
  /// bila native belum menghapus data atau menghentikan pengumpulan.
  Future<void> clearLocalData() async {
    if (_isAndroid) await _channel.invokeMethod<void>('clearLocalData');
  }

  Future<void> setCollectionEnabled(bool enabled) async {
    if (_isAndroid) {
      await _channel.invokeMethod<void>('setCollectionEnabled', {
        'enabled': enabled,
      });
    }
  }

  Future<void> setMonitoredApps(List<String> packages) async {
    if (_isAndroid) {
      await _channel.invokeMethod<void>('setMonitoredApps', {
        'packages': packages.toSet().toList()..sort(),
      });
    }
  }

  Future<List<Map<String, String>>> installedApps() async {
    if (!_isAndroid) return const [];
    final raw =
        await _channel.invokeListMethod<dynamic>('getInstalledApps') ?? [];
    return raw
        .whereType<Map>()
        .where((row) => row['packageName'] is String && row['label'] is String)
        .map(
          (row) => {
            'packageName': row['packageName'] as String,
            'label': row['label'] as String,
          },
        )
        .toList();
  }

  Future<bool> grantBankTime({
    required String packageName,
    required int minutes,
  }) async {
    if (!_isAndroid || packageName.isEmpty || minutes <= 0 || minutes > 480) {
      return false;
    }
    try {
      return await _channel.invokeMethod<bool>('grantBankTime', {
            'packageName': packageName,
            'minutes': minutes,
          }) ??
          false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  Future<Map<String, dynamic>> exportNativeData() async {
    if (!_isAndroid) return const {};
    final raw = await _channel.invokeMapMethod<String, dynamic>(
      'exportNativeData',
    );
    if (raw == null) throw const FormatException('Native backup unavailable');
    return raw;
  }

  Future<void> importNativeData(Map<String, dynamic> data) async {
    if (_isAndroid) {
      await _channel.invokeMethod<void>('importNativeData', {'data': data});
    }
  }

  Future<String?> consumePendingAction() async {
    if (!_isAndroid) return null;
    try {
      final action = await _channel.invokeMethod<String>(
        'consumePendingAction',
      );
      return action == 'rest' ? action : null;
    } on PlatformException {
      return null;
    } on MissingPluginException {
      return null;
    }
  }

  Future<Map<String, dynamic>?> nightUsage({int days = 1}) async {
    if (!_isAndroid) return null;
    final span = days.clamp(1, 30);
    try {
      final raw = await _channel.invokeMapMethod<String, dynamic>(
        'getNightUsage',
        {'days': span},
      );
      if (raw == null ||
          raw['minutes'] is! int ||
          raw['days'] != span ||
          raw['startHour'] != 22 ||
          raw['endHour'] != 6 ||
          (raw['minutes'] as int) < 0 ||
          (raw['minutes'] as int) > span * 8 * 60) {
        return null;
      }
      return raw;
    } on PlatformException {
      return null;
    } on MissingPluginException {
      return null;
    }
  }

  /// Jeda Sadar: overlay tunda sebelum app target terbuka (prd Bab 10.2).
  /// Teks dikirim dari Flutter supaya tetap mengikuti bahasa dan tema aktif.
  Future<bool> showPause({
    required List<String> packages,
    required int delaySeconds,
    required Map<String, int> limits,
    required int background,
    required int surface,
    required int ink,
    required int accent,
    required double radius,
    required String titleTemplate,
    required String autoTemplate,
    required String cancelLabel,
    required String continueLabel,
    required String note,
    required String hpLine,
    required String appFallback,
    required String limitTitle,
    required String limitNote,
    required String limitPassLabel,
    required String limitCloseLabel,
  }) async {
    if (!_isAndroid) return false;
    try {
      final ok = await _channel.invokeMethod<bool>('showPause', {
        'packages': packages,
        'delaySeconds': delaySeconds,
        'limits': limits,
        'background': background,
        'surface': surface,
        'ink': ink,
        'accent': accent,
        'radius': radius,
        'titleTemplate': titleTemplate,
        'autoTemplate': autoTemplate,
        'cancelLabel': cancelLabel,
        'continueLabel': continueLabel,
        'note': note,
        'hpLine': hpLine,
        'appFallback': appFallback,
        'limitTitle': limitTitle,
        'limitNote': limitNote,
        'limitPassLabel': limitPassLabel,
        'limitCloseLabel': limitCloseLabel,
      });
      return ok ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  Future<bool> isPauseRunning() async {
    if (!_isAndroid) return false;
    try {
      return await _channel.invokeMethod<bool>('isPauseRunning') ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  Future<void> hidePause() => _safeCall('hidePause');

  /// Agregat per hari dari UsageStats untuk mengisi riwayat saat izin baru ada.
  Future<List<Map<String, dynamic>>> dailyTotals({int days = 7}) async {
    if (!_isAndroid) return const [];
    try {
      final raw =
          await _channel.invokeListMethod<Map<dynamic, dynamic>>(
            'getDailyTotals',
            {'days': days},
          ) ??
          const [];
      return raw
          .map(
            (row) => row.map((key, value) => MapEntry(key.toString(), value)),
          )
          .toList();
    } on PlatformException {
      return const [];
    } on MissingPluginException {
      return const [];
    }
  }

  /// Satu pengingat harian; teks dikirim dari Flutter agar ikut bahasa aktif.
  Future<bool> scheduleReminder({
    required int hour,
    required int minute,
    required String title,
    required String body,
  }) async {
    if (!_isAndroid) return false;
    try {
      final ok = await _channel.invokeMethod<bool>('scheduleReminder', {
        'hour': hour,
        'minute': minute,
        'title': title,
        'body': body,
      });
      return ok ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  Future<void> cancelReminder() => _safeCall('cancelReminder');

  Future<bool> isReminderEnabled() async {
    if (!_isAndroid) return false;
    try {
      return await _channel.invokeMethod<bool>('isReminderEnabled') ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  Future<void> _safeCall(String method) async {
    if (!_isAndroid) return;
    try {
      await _channel.invokeMethod<void>(method);
    } on PlatformException {
      // Pengaturan tidak tersedia di perangkat ini.
    } on MissingPluginException {
      // Modul native belum terpasang.
    }
  }

  /// Ambil pemakaian hari ini. Bila izin belum diberikan, kembalikan data contoh
  /// yang diberi label jelas (source = sample). Kegagalan native dilempar ke
  /// pemanggil supaya angka contoh tidak pernah menyamar sebagai data nyata.
  Future<DailyUsage> loadToday({
    Map<String, UsageCategory> overrides = const {},
  }) async {
    final access = await hasUsageAccess();
    final a11y = await hasAccessibility();
    if (!access) return _sample(a11y);

    final raw =
        await _channel.invokeListMethod<Map<dynamic, dynamic>>(
          'getTodayUsage',
        ) ??
        const [];
    return DailyUsage(
      apps: _mapApps(raw, overrides),
      source: UsageSource.android,
      baselineMinutes: await _baseline(),
      permissionGranted: true,
      accessibilityEnabled: a11y,
    );
  }

  /// Pemakaian beberapa hari terakhir untuk tab Rekap. [days] 1 = hari ini.
  Future<DailyUsage> loadRange({
    required int days,
    Map<String, UsageCategory> overrides = const {},
  }) async {
    final span = days.clamp(1, 90);
    final access = await hasUsageAccess();
    final a11y = await hasAccessibility();
    if (!access) return _sample(a11y, days: span);

    final now = DateTime.now();
    // Calendar arithmetic, not Duration: subtracting 24h can land on the same
    // local date across DST transitions and lose a day from the range.
    final start = DateTime(now.year, now.month, now.day - (span - 1));
    final raw =
        await _channel.invokeListMethod<Map<dynamic, dynamic>>(
          'getUsageRange',
          {
            'startMs': start.millisecondsSinceEpoch,
            'endMs': now.millisecondsSinceEpoch,
          },
        ) ??
        const [];
    final dailyBaseline = await _baseline();
    return DailyUsage(
      apps: _mapApps(raw, overrides),
      source: UsageSource.android,
      baselineMinutes: dailyBaseline * span,
      permissionGranted: true,
      accessibilityEnabled: a11y,
    );
  }

  List<AppUsage> _mapApps(
    List<Map<dynamic, dynamic>> raw,
    Map<String, UsageCategory> overrides,
  ) {
    return raw
        .map((m) {
          final pkg = m['packageName'] as String;
          return AppUsage(
            packageName: pkg,
            label: (m['label'] as String?) ?? pkg,
            minutes: (m['minutes'] as num?)?.toInt() ?? 0,
            seconds: (m['seconds'] as num?)?.toInt() ?? 0,
            opens: (m['opens'] as num?)?.toInt() ?? 0,
            longestSessionMinutes:
                (m['longestSessionMinutes'] as num?)?.toInt() ?? 0,
            scrollHits: (m['scrollHits'] as num?)?.toInt() ?? 0,
            replays: (m['replays'] as num?)?.toInt() ?? 0,
            category:
                overrides[pkg] ??
                kDefaultCategories[pkg] ??
                UsageCategory.lainnya,
          );
        })
        // A 58-second session floors to 0 minutes. Keep any measured activity
        // so the UI can show <1m instead of pretending nothing was recorded.
        .where(
          (a) =>
              a.minutes > 0 ||
              a.seconds > 0 ||
              a.opens > 0 ||
              a.scrollHits > 0 ||
              a.replays > 0,
        )
        .toList()
      ..sort((a, b) {
        final byMinutes = b.minutes.compareTo(a.minutes);
        return byMinutes != 0 ? byMinutes : b.seconds.compareTo(a.seconds);
      });
  }

  Future<int> _baseline() async {
    try {
      return await _channel.invokeMethod<int>('getBaselineMinutes') ?? 0;
    } on PlatformException {
      return 0;
    } on MissingPluginException {
      return 0;
    }
  }

  DailyUsage _sample(bool a11y, {int days = 1}) {
    const apps = [
      AppUsage(
        packageName: 'com.zhiliaoapp.musically',
        label: 'TikTok',
        minutes: 72,
        opens: 14,
        longestSessionMinutes: 26,
        category: UsageCategory.sosial,
        scrollHits: 214,
        replays: 18,
      ),
      AppUsage(
        packageName: 'com.instagram.android',
        label: 'Instagram',
        minutes: 48,
        opens: 11,
        longestSessionMinutes: 17,
        category: UsageCategory.sosial,
        scrollHits: 121,
        replays: 6,
      ),
      AppUsage(
        packageName: 'com.google.android.youtube',
        label: 'YouTube',
        minutes: 36,
        opens: 5,
        longestSessionMinutes: 22,
        category: UsageCategory.hiburan,
        scrollHits: 52,
        replays: 3,
      ),
      AppUsage(
        packageName: 'com.whatsapp',
        label: 'WhatsApp',
        minutes: 24,
        opens: 19,
        longestSessionMinutes: 6,
        category: UsageCategory.sosial,
      ),
      AppUsage(
        packageName: 'com.android.chrome',
        label: 'Chrome',
        minutes: 14,
        opens: 7,
        longestSessionMinutes: 5,
        category: UsageCategory.produktivitas,
      ),
      AppUsage(
        packageName: 'com.spotify.music',
        label: 'Spotify',
        minutes: 10,
        opens: 3,
        longestSessionMinutes: 6,
        category: UsageCategory.hiburan,
      ),
    ];
    final scaled = apps
        .map(
          (a) => AppUsage(
            packageName: a.packageName,
            label: a.label,
            minutes: a.minutes * days,
            opens: a.opens * days,
            longestSessionMinutes: a.longestSessionMinutes,
            category: a.category,
            scrollHits: a.scrollHits * days,
            replays: a.replays * days,
          ),
        )
        .toList();
    return DailyUsage(
      apps: scaled,
      source: UsageSource.sample,
      baselineMinutes: 222 * days,
      permissionGranted: false,
      accessibilityEnabled: a11y,
    );
  }
}
