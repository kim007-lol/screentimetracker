import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:screentime_companion/core/state/app_state.dart';
import 'package:screentime_companion/features/profil/privacy_card.dart';
import 'package:screentime_companion/features/profil/profil_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:webview_flutter/webview_flutter.dart';

import 'lifecycle_webview_fake.dart';

void main() {
  Future<SharedPreferences> preferences() async {
    SharedPreferences.setMockInitialValues({});
    return SharedPreferences.getInstance();
  }

  testWidgets(
    'profile refactor exposes app management without building hidden previews',
    (tester) async {
      WebViewPlatform.instance = LifecycleWebViewPlatform();
      final prefs = await preferences();
      await tester.pumpWidget(
        ProviderScope(
          overrides: [sharedPrefsProvider.overrideWithValue(prefs)],
          child: const MaterialApp(home: Scaffold(body: ProfilScreen())),
        ),
      );
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Kelola aplikasi'),
        400,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Kelola aplikasi'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'invalid pasted backup stays in dialog and never replaces preferences',
    (tester) async {
      final prefs = await preferences();
      await prefs.setString('userName', 'Before');
      await tester.pumpWidget(
        ProviderScope(
          overrides: [sharedPrefsProvider.overrideWithValue(prefs)],
          child: const MaterialApp(
            home: Scaffold(body: SingleChildScrollView(child: PrivacyCard())),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Impor backup JSON'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), '{"version":999}');
      await tester.tap(find.text('Periksa backup'));
      await tester.pumpAndSettle();
      expect(
        find.text('Backup tidak valid atau versinya tidak didukung.'),
        findsOneWidget,
      );
      expect(prefs.getString('userName'), 'Before');
      await tester.tap(find.text('Batal'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    },
  );
}
