import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:screentime_companion/core/services/usage_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('usage-test');
  late UsageService service;
  late List<MethodCall> calls;
  setUp(() {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    calls = [];
    service = UsageService(channel: channel);
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          calls.add(call);
          switch (call.method) {
            case 'hasUsageAccess':
            case 'hasAccessibility':
            case 'grantBankTime':
              return true;
            case 'showPill':
            case 'showPetOverlay':
            case 'isPetOverlayVisible':
            case 'isPetOverlayFallback':
              return true;
            case 'getBaselineMinutes':
              return 100;
            case 'getTodayUsage':
              return [
                {
                  'packageName': 'com.example.app',
                  'label': 'App',
                  'minutes': 0,
                  'scrollHits': 3,
                },
              ];
            case 'getInstalledApps':
              return [
                {'packageName': 'com.example.app', 'label': 'App'},
              ];
            case 'getNightUsage':
              return {'minutes': 12, 'startHour': 22, 'endHour': 6, 'days': 7};
            case 'consumePendingAction':
              return 'rest';
            default:
              return null;
          }
        });
  });
  tearDown(() {
    debugDefaultTargetPlatformOverride = null;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
  });

  test('retains scroll-only packages instead of dropping real data', () async {
    final usage = await service.loadToday();
    expect(usage.totalScrollHits, 3);
  });
  test('keeps sub-minute foreground apps and exposes their seconds', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          switch (call.method) {
            case 'hasUsageAccess':
              return true;
            case 'hasAccessibility':
              return false;
            case 'getBaselineMinutes':
              return 0;
            case 'getTodayUsage':
              return [
                {
                  'packageName': 'com.android.vending',
                  'label': 'Play Store',
                  'minutes': 0,
                  'seconds': 58,
                  'opens': 1,
                  'longestSessionMinutes': 0,
                  'scrollHits': 0,
                  'replays': 0,
                },
              ];
            default:
              return null;
          }
        });
    final usage = await service.loadToday();
    expect(usage.apps.single.seconds, 58);
    expect(usage.totalSeconds, 58);
    expect(usage.topApp?.label, 'Play Store');
  });
  test('clear and collection commands preserve explicit intent', () async {
    await service.clearLocalData();
    await service.setCollectionEnabled(false);
    await service.setMonitoredApps([]);
    expect(calls.map((c) => c.method), [
      'clearLocalData',
      'setCollectionEnabled',
      'setMonitoredApps',
    ]);
    expect(calls[1].arguments, {'enabled': false});
    expect(calls[2].arguments, {'packages': []});
  });
  test('privacy deletion failures are not silently swallowed', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
          channel,
          (_) async => throw PlatformException(code: 'DELETE_FAILED'),
        );
    await expectLater(
      service.clearLocalData(),
      throwsA(isA<PlatformException>()),
    );
  });
  test('bank grant awaits native acceptance with exact arguments', () async {
    expect(
      await service.grantBankTime(packageName: 'com.example.app', minutes: 10),
      isTrue,
    );
    expect(calls.single.arguments, {
      'packageName': 'com.example.app',
      'minutes': 10,
    });
  });
  test('lists installed launcher apps and consumes rest action', () async {
    expect((await service.installedApps()).single['label'], 'App');
    expect(await service.consumePendingAction(), 'rest');
  });
  test('native read failure surfaces instead of faking sample data', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          switch (call.method) {
            case 'hasUsageAccess':
            case 'hasAccessibility':
              return true;
            case 'getTodayUsage':
              throw PlatformException(code: 'UNAVAILABLE');
            default:
              return null;
          }
        });
    await expectLater(service.loadToday(), throwsA(isA<PlatformException>()));
  });
  test('range read failure surfaces instead of faking sample data', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          switch (call.method) {
            case 'hasUsageAccess':
            case 'hasAccessibility':
              return true;
            case 'getUsageRange':
              throw PlatformException(code: 'UNAVAILABLE');
            default:
              return null;
          }
        });
    await expectLater(
      service.loadRange(days: 7),
      throwsA(isA<PlatformException>()),
    );
  });
  test('night usage reports genuine response, not sample', () async {
    expect((await service.nightUsage(days: 7))?['minutes'], 12);
  });
  test('night usage rejects malformed response', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (_) async => {'minutes': -1});
    expect(await service.nightUsage(days: 7), isNull);
  });

  test('pill and roaming pet carry an explicit animation mode', () async {
    expect(
      await service.showPill(
        background: 0xFFFFFFFF,
        surface: 0xFFFFFFFF,
        ink: 0xFF111111,
        accent: 0xFFFFD23F,
        radius: 14,
        language: 'en',
        stage: 'remaja',
        animation: 'full',
      ),
      isTrue,
    );
    expect(calls.last.method, 'showPill');
    expect(calls.last.arguments['animation'], 'full');
    expect(calls.last.arguments['stage'], 'remaja');
    // The pill is one object with a selectable silhouette; the head is default.
    expect(calls.last.arguments['form'], 'head');
    // Native owns the drawable set, so the pill must know which companion it is.
    expect(calls.last.arguments['pet'], 'momo');

    expect(
      await service.showPill(
        background: 0xFFFFFFFF,
        surface: 0xFFFFFFFF,
        ink: 0xFF111111,
        accent: 0xFFFFD23F,
        radius: 14,
        form: 'body',
        pet: 'drako',
      ),
      isTrue,
    );
    expect(calls.last.arguments['form'], 'body');
    expect(calls.last.arguments['pet'], 'drako');

    expect(
      await service.showPetOverlay(
        animation: 'flat',
        language: 'id',
        stage: 'dewasa',
        hpBonus: 12,
      ),
      isTrue,
    );
    expect(calls.last.method, 'showPetOverlay');
    expect(calls.last.arguments, {
      'language': 'id',
      'stage': 'dewasa',
      'animation': 'flat',
      'pet': 'momo',
      'hpBonus': 12,
    });

    expect(
      await service.showPetOverlay(
        animation: 'full',
        language: 'en',
        stage: 'bayi',
        pet: 'drako',
        hpBonus: 3,
      ),
      isTrue,
    );
    expect(calls.last.arguments['pet'], 'drako');

    expect(await service.isPetOverlayVisible(), isTrue);
    expect(calls.last.method, 'isPetOverlayVisible');
    await service.hidePetOverlay();
    expect(calls.last.method, 'hidePetOverlay');
  });

  test('roaming pet reports fallback and receives sleep state', () async {
    expect(await service.isPetOverlayFallback(), isTrue);
    expect(calls.last.method, 'isPetOverlayFallback');

    await service.setPetResting(true);
    expect(calls.last.method, 'setPetResting');
    expect(calls.last.arguments, {'resting': true});
  });

  test('hiding the roaming pet surfaces native failure', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (_) async {
          throw PlatformException(code: 'OVERLAY_STOP_FAILED');
        });
    await expectLater(
      service.hidePetOverlay(),
      throwsA(isA<PlatformException>()),
    );
  });
}
