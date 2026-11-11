import 'package:flutter/material.dart';

enum AppThemeId { brutal, arcade, clay, midnight }

enum ShadowKind { hard, soft, none }

/// Token visual satu tema. Nilai mengikuti tabel di docs/04-desain-dan-tema.md.
class AppTokens {
  const AppTokens({
    required this.id,
    required this.name,
    required this.tagline,
    required this.taglineEn,
    required this.brightness,
    required this.bg,
    required this.surface,
    required this.ink,
    required this.muted,
    required this.primary,
    required this.onPrimary,
    required this.secondary,
    required this.hpHealthy,
    required this.hpTired,
    required this.hpCritical,
    required this.borderColor,
    required this.borderWidth,
    required this.shadowKind,
    required this.shadowColor,
    required this.radius,
    required this.notched,
    required this.headingFont,
    required this.bodyFont,
    required this.numberFont,
  });

  final AppThemeId id;
  final String name;
  final String tagline;
  final String taglineEn;
  final Brightness brightness;
  final Color bg;
  final Color surface;
  final Color ink;
  final Color muted;
  final Color primary;
  final Color onPrimary;
  final Color secondary;
  final Color hpHealthy;
  final Color hpTired;
  final Color hpCritical;
  final Color borderColor;
  final double borderWidth;
  final ShadowKind shadowKind;
  final Color shadowColor;
  final double radius;

  /// Sudut bertingkat (notched) khusus Pixel Arcade.
  final bool notched;
  final String headingFont;
  final String bodyFont;

  /// Font angka statistik. Selalu tabular, pixel hanya untuk angka hero Arcade.
  final String numberFont;

  static const _tabular = [FontFeature.tabularFigures()];

  TextStyle heading(double size, {FontWeight? weight, Color? color}) =>
      TextStyle(
        fontFamily: headingFont,
        fontSize: size,
        fontWeight: weight ?? FontWeight.w700,
        color: color ?? ink,
        height: 1.15,
      );

  TextStyle body(double size, {FontWeight? weight, Color? color}) => TextStyle(
    fontFamily: bodyFont,
    fontSize: size,
    fontWeight: weight ?? FontWeight.w500,
    color: color ?? ink,
    height: 1.35,
  );

  /// Angka data: tabular figures supaya mudah dibaca sekilas.
  TextStyle number(double size, {FontWeight? weight, Color? color}) =>
      TextStyle(
        fontFamily: numberFont,
        fontSize: size,
        fontWeight: weight ?? FontWeight.w700,
        color: color ?? ink,
        fontFeatures: _tabular,
        height: 1.1,
      );

  Color hpColor(double hp) {
    if (hp > 60) return hpHealthy;
    if (hp >= 30) return hpTired;
    return hpCritical;
  }

  ShapeBorder shape({double? radiusOverride, bool outlined = true}) {
    final r = radiusOverride ?? radius;
    final side = outlined && borderWidth > 0
        ? BorderSide(color: borderColor, width: borderWidth)
        : BorderSide.none;
    if (notched) {
      return BeveledRectangleBorder(
        side: side,
        borderRadius: BorderRadius.circular(r == 0 ? 6 : r),
      );
    }
    return RoundedRectangleBorder(
      side: side,
      borderRadius: BorderRadius.circular(r),
    );
  }

  List<BoxShadow> get shadows {
    switch (shadowKind) {
      case ShadowKind.hard:
        return [BoxShadow(color: shadowColor, offset: const Offset(4, 4))];
      case ShadowKind.soft:
        return [
          BoxShadow(
            color: shadowColor,
            offset: const Offset(0, 8),
            blurRadius: 16,
          ),
        ];
      case ShadowKind.none:
        return const [];
    }
  }

  ShapeDecoration box({
    Color? color,
    double? radiusOverride,
    bool outlined = true,
    bool elevated = true,
  }) => ShapeDecoration(
    color: color ?? surface,
    shape: shape(radiusOverride: radiusOverride, outlined: outlined),
    shadows: elevated ? shadows : const [],
  );

  /// A translucent tint pre-blended onto the screen background.
  ///
  /// Elevated cards paint their hard shadow behind the fill; an alpha fill
  /// would let that shadow bleed through and darken the whole card.
  Color tint(Color color, double alpha) =>
      Color.alphaBlend(color.withValues(alpha: alpha), bg);

  ThemeData toThemeData() {
    final scheme =
        ColorScheme.fromSeed(
          seedColor: primary,
          brightness: brightness,
        ).copyWith(
          surface: surface,
          primary: primary,
          onPrimary: onPrimary,
          secondary: secondary,
          onSurface: ink,
          error: hpCritical,
        );
    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      scaffoldBackgroundColor: bg,
      canvasColor: bg,
      fontFamily: bodyFont,
      textTheme: ThemeData(brightness: brightness).textTheme.apply(
        fontFamily: bodyFont,
        bodyColor: ink,
        displayColor: ink,
      ),
      splashFactory: InkRipple.splashFactory,
    );
  }
}

class AppThemes {
  static const brutal = AppTokens(
    id: AppThemeId.brutal,
    name: 'Brutal Pop',
    tagline: 'Garis tebal, warna cerah',
    taglineEn: 'Thick lines, bright colors',
    brightness: Brightness.light,
    bg: Color(0xFFFFF4E0),
    surface: Color(0xFFFFFFFF),
    ink: Color(0xFF111111),
    muted: Color(0xFF5B5445),
    primary: Color(0xFFFFD23F),
    onPrimary: Color(0xFF111111),
    secondary: Color(0xFF3DDC84),
    hpHealthy: Color(0xFF3DDC84),
    hpTired: Color(0xFFFFB020),
    hpCritical: Color(0xFFFF4D4D),
    borderColor: Color(0xFF111111),
    borderWidth: 3,
    shadowKind: ShadowKind.hard,
    shadowColor: Color(0xFF111111),
    radius: 6,
    notched: false,
    headingFont: 'Space Grotesk',
    bodyFont: 'DM Sans',
    numberFont: 'DM Sans',
  );

  static const arcade = AppTokens(
    id: AppThemeId.arcade,
    name: 'Pixel Arcade',
    tagline: 'Sudut bertingkat, nuansa RPG',
    taglineEn: 'Stepped corners, RPG feel',
    brightness: Brightness.dark,
    bg: Color(0xFF1B1B2F),
    surface: Color(0xFF26264A),
    ink: Color(0xFFF5F5F5),
    muted: Color(0xFFA9A9C8),
    primary: Color(0xFFFFD23F),
    onPrimary: Color(0xFF111111),
    secondary: Color(0xFF5BD98C),
    hpHealthy: Color(0xFF5BD98C),
    hpTired: Color(0xFFFFB020),
    hpCritical: Color(0xFFFF4D4D),
    borderColor: Color(0xFF000000),
    borderWidth: 3,
    shadowKind: ShadowKind.hard,
    shadowColor: Color(0xFF000000),
    radius: 0,
    notched: true,
    headingFont: 'Pixelify Sans',
    bodyFont: 'DM Sans',
    numberFont: 'DM Sans',
  );

  static const clay = AppTokens(
    id: AppThemeId.clay,
    name: 'Soft Clay',
    tagline: 'Bentuk membulat, warna pastel',
    taglineEn: 'Rounded shapes, pastel colors',
    brightness: Brightness.light,
    bg: Color(0xFFFFF1F5),
    surface: Color(0xFFFFFFFF),
    ink: Color(0xFF3B2F3F),
    muted: Color(0xFF7D6B82),
    primary: Color(0xFFFFB5C8),
    onPrimary: Color(0xFF3B2F3F),
    secondary: Color(0xFF9AD6C0),
    hpHealthy: Color(0xFF6FCF97),
    hpTired: Color(0xFFF2B84B),
    hpCritical: Color(0xFFEF6B6B),
    borderColor: Colors.transparent,
    borderWidth: 0,
    shadowKind: ShadowKind.soft,
    shadowColor: Color(0x2E3B2F3F),
    radius: 28,
    notched: false,
    headingFont: 'Nunito',
    bodyFont: 'Nunito',
    numberFont: 'Nunito',
  );

  static const midnight = AppTokens(
    id: AppThemeId.midnight,
    name: 'Midnight',
    tagline: 'Latar gelap, tampilan minimal',
    taglineEn: 'Dark background, minimal look',
    brightness: Brightness.dark,
    bg: Color(0xFF0B0D12),
    surface: Color(0xFF151922),
    ink: Color(0xFFEDEFF5),
    muted: Color(0xFF96A0B3),
    primary: Color(0xFF7CF2C8),
    onPrimary: Color(0xFF0B0D12),
    secondary: Color(0xFF8FA6FF),
    hpHealthy: Color(0xFF7CF2C8),
    hpTired: Color(0xFFFFC857),
    hpCritical: Color(0xFFFF6B6B),
    borderColor: Color(0xFF2A3040),
    borderWidth: 1,
    shadowKind: ShadowKind.none,
    shadowColor: Colors.transparent,
    radius: 14,
    notched: false,
    headingFont: 'Inter',
    bodyFont: 'Inter',
    numberFont: 'Inter',
  );

  static const all = [brutal, arcade, clay, midnight];

  static AppTokens of(AppThemeId id) =>
      all.firstWhere((t) => t.id == id, orElse: () => brutal);
}
