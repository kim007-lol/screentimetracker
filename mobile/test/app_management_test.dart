import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:screentime_companion/core/services/usage_service.dart';
import 'package:screentime_companion/core/state/app_state.dart';
import 'package:screentime_companion/features/profil/app_management_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _Apps extends UsageService {
  List<String>? selection;
  @override
  Future<List<Map<String, String>>> installedApps() async => [
    {'packageName': 'com.example.unused', 'label': 'Unused app'},
    {'packageName': 'com.example.book', 'label': 'Book reader'},
  ];
  @override
  Future<void> setMonitoredApps(List<String> packages) async {
    selection = packages;
  }
}

void main() {
  testWidgets('warns when pause is on but accessibility is off', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final container = ProviderContainer(
      overrides: [
        sharedPrefsProvider.overrideWithValue(prefs),
        usageServiceProvider.overrideWithValue(_Apps()),
        permissionStatusProvider.overrideWith(
          (ref) async => const PermissionStatus(
            usage: true,
            accessibility: false,
            overlay: true,
            pillRunning: false,
            pauseRunning: true,
          ),
        ),
      ],
    );
    addTearDown(container.dispose);
    container.read(gameProvider);
    container.read(gameProvider.notifier).setPauseEnabled(true);
    await container
        .read(gameProvider.notifier)
        .setMonitoredPackage('com.example.unused', true);
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: AppManagementScreen()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('belum dihitung'), findsOneWidget);
    expect(find.text('Izinkan'), findsOneWidget);
  });

  testWidgets('lists apps without usage and filters by label or package', (
    tester,
  ) async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final service = _Apps();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sharedPrefsProvider.overrideWithValue(prefs),
          usageServiceProvider.overrideWithValue(service),
        ],
        child: const MaterialApp(home: AppManagementScreen()),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Unused app'), findsOneWidget);
    expect(find.text('Book reader'), findsOneWidget);
    await tester.enterText(find.byType(TextField), 'unused');
    await tester.pumpAndSettle();
    expect(find.text('Unused app'), findsOneWidget);
    expect(find.text('Book reader'), findsNothing);
    await tester.tap(find.byType(CheckboxListTile).first);
    await tester.pumpAndSettle();
    expect(service.selection, contains('com.example.unused'));
  });
}
