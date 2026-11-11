import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:screentime_companion/core/theme/app_tokens.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  GoogleFonts.config.allowRuntimeFetching = false;

  for (final tokens in AppThemes.all) {
    test(
      '${tokens.name} uses declared offline families and original weights',
      () {
        expect(tokens.heading(24).fontFamily, tokens.headingFont);
        expect(tokens.body(14).fontFamily, tokens.bodyFont);
        expect(tokens.number(32).fontFamily, tokens.numberFont);
        expect(tokens.heading(24).fontWeight, FontWeight.w700);
        expect(tokens.body(14).fontWeight, FontWeight.w500);
        expect(tokens.number(32).fontWeight, FontWeight.w700);
        expect(
          tokens.heading(15, weight: FontWeight.w800).fontWeight,
          FontWeight.w800,
        );
        expect(tokens.number(32).fontFeatures, [
          const FontFeature.tabularFigures(),
        ]);
        expect(
          tokens.toThemeData().textTheme.bodyMedium!.fontFamily,
          tokens.bodyFont,
        );
      },
    );

    test(
      '${tokens.name} tinted card fills stay opaque over the background',
      () {
        for (final color in [
          tokens.primary,
          tokens.secondary,
          tokens.hpHealthy,
        ]) {
          for (final alpha in [0.14, 0.18, 0.22]) {
            final fill = tokens.tint(color, alpha);
            expect(fill.a, 1.0, reason: '${color.toARGB32()} @ $alpha');
          }
        }
      },
    );
  }
}
