import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:screentime_companion/core/models/usage.dart';
import 'package:screentime_companion/core/services/usage_service.dart';
import 'package:screentime_companion/core/state/app_state.dart';
import 'package:screentime_companion/features/rest/rest_screen.dart';
import 'package:screentime_companion/main.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _Usage extends UsageNotifier {
  final foregroundCalls = <bool>[];
  @override
  Future<DailyUsage> build() async => const DailyUsage(
    apps: [],
    source: UsageSource.sample,
    baselineMinutes: 0,
  );
  @override
  Future<void> setForeground(bool foreground) async {
    foregroundCalls.add(foreground);
  }
}

class _Service extends UsageService {
  int consumed = 0;
  @override
  Future<String?> consumePendingAction() async {
    consumed++;
    return 'rest';
  }
}

void main() {
  testWidgets(
    'root refreshes permissions and foreground state during onboarding',
    (tester) async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final usage = _Usage();
      final service = _Service();
      var permissionReads = 0;
      final container = ProviderContainer(
        overrides: [
          sharedPrefsProvider.overrideWithValue(prefs),
          usageServiceProvider.overrideWithValue(service),
          usageProvider.overrideWith(() => usage),
          permissionStatusProvider.overrideWith((ref) async {
            permissionReads++;
            return const PermissionStatus(
              usage: false,
              accessibility: false,
              overlay: false,
              pillRunning: false,
              pauseRunning: false,
            );
          }),
        ],
      );
      final sub = container.listen(permissionStatusProvider, (_, _) {});
      addTearDown(() {
        sub.close();
        container.dispose();
      });
      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const ScreenTimeApp(),
        ),
      );
      await tester.pump();
      final before = permissionReads;
      // Use the real transition sequence: the name field's EditableText installs
      // an AppLifecycleListener, which rejects a direct paused -> resumed jump.
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await tester.pump();
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump();
      expect(permissionReads, greaterThan(before));
      expect(usage.foregroundCalls, containsAllInOrder([false, true]));
      expect(service.consumed, greaterThanOrEqualTo(1));
      // A stale Pill action cannot skip consent or start a rest after deletion.
      expect(find.byType(RestScreen), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}
