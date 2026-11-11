import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:screentime_companion/core/l10n/l10n.dart';
import 'package:screentime_companion/core/models/companion.dart';
import 'package:screentime_companion/core/models/usage.dart';
import 'package:screentime_companion/core/state/app_state.dart';
import 'package:screentime_companion/core/theme/app_tokens.dart';
import 'package:screentime_companion/features/home/home_screen.dart';

Widget _host({DailyUsage? usage}) => ProviderScope(
  overrides: [
    tokensProvider.overrideWithValue(AppThemes.brutal),
    l10nProvider.overrideWithValue(const L10n('en')),
  ],
  child: MaterialApp(
    home: Scaffold(
      body: SizedBox(
        height: 800,
        child: ListView(children: [StatRow(usage: usage)]),
      ),
    ),
  ),
);

void main() {
  testWidgets('StatRow keeps a finite, shared height inside a ListView', (
    tester,
  ) async {
    await tester.pumpWidget(_host());
    expect(
      tester.takeException(),
      isNull,
      reason: 'stretch in a vertical viewport must not force infinite height',
    );
    final size = tester.getSize(find.byType(StatRow));
    expect(size.height.isFinite, isTrue);
    expect(size.height, greaterThan(0));
  });

  testWidgets('all three chips share the tallest chip height', (tester) async {
    await tester.pumpWidget(_host());
    final chips = find.descendant(
      of: find.byType(StatRow),
      matching: find.byType(DecoratedBox),
    );
    expect(chips, findsNWidgets(3));
    final heights = [
      for (var i = 0; i < 3; i++) tester.getSize(chips.at(i)).height,
    ];
    for (final height in heights) {
      expect(height, moreOrLessEquals(heights.first));
    }
  });

  testWidgets('shows sub-minute usage instead of an empty top app', (
    tester,
  ) async {
    const usage = DailyUsage(
      apps: [
        AppUsage(
          packageName: 'com.android.vending',
          label: 'Play Store',
          minutes: 0,
          seconds: 58,
          opens: 1,
          longestSessionMinutes: 0,
          category: UsageCategory.produktivitas,
        ),
      ],
      source: UsageSource.android,
      baselineMinutes: 0,
      permissionGranted: true,
    );
    await tester.pumpWidget(_host(usage: usage));
    expect(find.text('<1m'), findsNWidgets(2));
    expect(find.text('Play Store'), findsOneWidget);
  });
}
