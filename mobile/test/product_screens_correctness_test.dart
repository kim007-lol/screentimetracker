import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:screentime_companion/core/l10n/l10n.dart';
import 'package:screentime_companion/core/models/duel_snapshot.dart';
import 'package:screentime_companion/core/models/usage.dart';
import 'package:screentime_companion/core/services/usage_service.dart';
import 'package:screentime_companion/core/state/app_state.dart';
import 'package:screentime_companion/core/weekly_goal.dart';
import 'package:screentime_companion/features/duel/duel_screen.dart';
import 'package:screentime_companion/features/rekap/recap_period.dart';
import 'package:screentime_companion/features/rekap/rekap_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'duel_weekly_correctness_test.dart' show stat;

class NightService extends UsageService {
  NightService(this.minutes);
  final int? minutes;
  final requested = <int>[];
  @override
  Future<Map<String, dynamic>?> nightUsage({int days = 1}) async {
    requested.add(days);
    return minutes == null
        ? null
        : {'minutes': minutes, 'startHour': 22, 'endHour': 6, 'days': days};
  }
}

void main() {
  setUpAll(() => GoogleFonts.config.allowRuntimeFetching = false);
  Future<void> mount(
    WidgetTester tester,
    Widget screen, {
    bool sample = false,
    NightService? service,
    List<String> peers = const [],
  }) async {
    SharedPreferences.setMockInitialValues({'duelPeers': peers});
    final prefs = await SharedPreferences.getInstance();
    final today = DuelSnapshot.dayKey(DateTime.now());
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sharedPrefsProvider.overrideWithValue(prefs),
          l10nProvider.overrideWithValue(const L10n('en')),
          usageServiceProvider.overrideWithValue(service ?? NightService(null)),
          usageRangeProvider.overrideWith(
            (ref, days) async => DailyUsage(
              apps: const [],
              source: sample ? UsageSource.sample : UsageSource.android,
              baselineMinutes: 0,
            ),
          ),
          historyProvider.overrideWith((ref, days) async => [stat(today)]),
          hpProvider.overrideWithValue(80),
        ],
        child: MaterialApp(home: Scaffold(body: screen)),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets(
    '30-day recap image and copied caption show period and sample source',
    (tester) async {
      String? clipboard;
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        SystemChannels.platform,
        (call) async {
          if (call.method == 'Clipboard.setData') {
            clipboard = (call.arguments as Map)['text'] as String;
          }
          return null;
        },
      );
      addTearDown(
        () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
          SystemChannels.platform,
          null,
        ),
      );
      await mount(tester, const RekapScreen(), sample: true);
      await tester.tap(find.text('30 days'));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(find.text('View recap card'), 400);
      await tester.ensureVisible(find.text('View recap card'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('View recap card'));
      await tester.pumpAndSettle();
      final dialog = find.byType(Dialog);
      expect(
        find.descendant(of: dialog, matching: find.text('Last 30 days')),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: dialog,
          matching: find.text(RecapPeriod(days: 30).dateText),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: dialog,
          matching: find.textContaining('Sample data'),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(of: dialog, matching: find.textContaining('Today')),
        findsNothing,
      );
      await tester.tap(find.text('Copy summary'));
      await tester.pumpAndSettle();
      expect(clipboard, contains('Last 30 days'));
      expect(clipboard, contains('Sample data'));
      expect(clipboard, contains(RecapPeriod(days: 30).dateText));
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'night insight uses selected period and distinguishes measured zero',
    (tester) async {
      final service = NightService(0);
      await mount(tester, const RekapScreen(), service: service);
      await tester.tap(find.text('7 days'));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Late-night usage · 22:00–06:00'),
        250,
      );
      expect(service.requested, contains(7));
      expect(find.text('0m recorded at night'), findsOneWidget);
      expect(find.text('Night usage unavailable'), findsNothing);
    },
  );

  testWidgets(
    'missing native night data is unavailable, never sample minutes',
    (tester) async {
      await mount(tester, const RekapScreen(), sample: true);
      await tester.scrollUntilVisible(
        find.text('Late-night usage · 22:00–06:00'),
        250,
      );
      expect(find.text('Night usage unavailable'), findsOneWidget);
      expect(find.text('0m recorded at night'), findsNothing);
    },
  );

  testWidgets(
    'offline board explains legacy entries rather than awarding a rank',
    (tester) async {
      final legacy = DuelSnapshot(
        name: 'Legacy Friend',
        minutes: 1,
        scrollHits: 0,
        days: 1,
        generatedAt: DateTime.now(),
      );
      await mount(tester, const DuelScreen(), peers: [legacy.encode()]);
      expect(find.textContaining('need an account and a server'), findsNothing);
      await tester.scrollUntilVisible(find.text('Legacy Friend'), 250);
      expect(
        find.textContaining('v1 code: week and balance data unavailable'),
        findsOneWidget,
      );
      expect(find.textContaining('self-reported'), findsWidgets);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'current week self snapshot uses history rather than sample range',
    (tester) async {
      final mine = duelSnapshotFrom([
        stat(DuelSnapshot.dayKey(DateTime.now())),
      ], name: 'Peer');
      await mount(
        tester,
        const DuelScreen(),
        sample: true,
        peers: [mine.encode()],
      );
      await tester.scrollUntilVisible(find.text('Offline duel board'), 250);
      expect(find.textContaining('1/1 balanced'), findsWidgets);
      expect(find.textContaining('week starts'), findsWidgets);
    },
  );
}
