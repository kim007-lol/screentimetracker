import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:screentime_companion/core/models/pet.dart';
import 'package:screentime_companion/core/services/history_service.dart';
import 'package:screentime_companion/core/services/usage_service.dart';
import 'package:screentime_companion/core/state/app_state.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _FakeUsage extends UsageService {
  int clears = 0;
  int hideOverlayCalls = 0;

  @override
  Future<void> clearLocalData() async => clears++;

  @override
  Future<void> hidePetOverlay() async => hideOverlayCalls++;
}

class _FakeHistory extends HistoryService {
  int clears = 0;

  @override
  Future<void> clear() async => clears++;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late SharedPreferences prefs;
  late _FakeUsage usage;
  late _FakeHistory history;
  late ProviderContainer container;

  Future<void> init({Map<String, Object> initial = const {}}) async {
    SharedPreferences.setMockInitialValues(initial);
    prefs = await SharedPreferences.getInstance();
    usage = _FakeUsage();
    history = _FakeHistory();
    container = ProviderContainer(
      overrides: [
        sharedPrefsProvider.overrideWithValue(prefs),
        usageServiceProvider.overrideWithValue(usage),
        historyServiceProvider.overrideWithValue(history),
      ],
    );
    addTearDown(container.dispose);
  }

  test('pet overlay is off and both surfaces are static by default', () async {
    await init();
    final state = container.read(gameProvider);
    expect(state.petOverlayEnabled, isFalse);
    expect(state.pillAnimationMode, PetAnimationMode.flat);
    expect(state.overlayAnimationMode, PetAnimationMode.flat);
    expect(state.pillForm, PillForm.head);
  });

  test('pet settings persist across a fresh provider container', () async {
    await init();
    final notifier = container.read(gameProvider.notifier);
    notifier.setPetOverlayEnabled(true);
    notifier.setPillAnimationMode(PetAnimationMode.full);
    notifier.setOverlayAnimationMode(PetAnimationMode.full);
    notifier.setPillForm(PillForm.body);

    expect(prefs.getBool('petOverlayEnabled'), isTrue);
    expect(prefs.getString('pillAnimationMode'), 'full');
    expect(prefs.getString('overlayAnimationMode'), 'full');
    expect(prefs.getString('pillForm'), 'body');

    final restored = ProviderContainer(
      overrides: [
        sharedPrefsProvider.overrideWithValue(prefs),
        usageServiceProvider.overrideWithValue(usage),
        historyServiceProvider.overrideWithValue(history),
      ],
    );
    addTearDown(restored.dispose);
    final state = restored.read(gameProvider);
    expect(state.petOverlayEnabled, isTrue);
    expect(state.pillAnimationMode, PetAnimationMode.full);
    expect(state.overlayAnimationMode, PetAnimationMode.full);
    expect(state.pillForm, PillForm.body);
  });

  test('unknown stored animation values fall back to static safely', () async {
    await init(initial: {
      'pillAnimationMode': 'turbo',
      'overlayAnimationMode': 'FULL',
      'pillForm': 'tail',
      'petOverlayEnabled': true,
    });
    final state = container.read(gameProvider);
    expect(state.pillAnimationMode, PetAnimationMode.flat);
    expect(state.overlayAnimationMode, PetAnimationMode.flat);
    expect(state.pillForm, PillForm.head);
    expect(state.petOverlayEnabled, isTrue);
  });

  test('deletion removes pet settings and stops the overlay', () async {
    await init(initial: {
      'onboarded': true,
      'collectionEnabled': true,
      'petOverlayEnabled': true,
      'pillAnimationMode': 'full',
      'overlayAnimationMode': 'full',
      'pillForm': 'body',
    });
    await container.read(gameProvider.notifier).deleteAllData();

    expect(usage.clears, 1);
    expect(history.clears, 1);
    expect(prefs.getBool('petOverlayEnabled'), isNull);
    expect(prefs.getString('pillAnimationMode'), isNull);
    expect(prefs.getString('overlayAnimationMode'), isNull);
    expect(prefs.getString('pillForm'), isNull);
    final state = container.read(gameProvider);
    expect(state.petOverlayEnabled, isFalse);
    expect(state.pillAnimationMode, PetAnimationMode.flat);
    expect(state.overlayAnimationMode, PetAnimationMode.flat);
    expect(state.pillForm, PillForm.head);
  });
}
