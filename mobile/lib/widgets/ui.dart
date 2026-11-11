import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/state/app_state.dart';
import '../core/theme/app_tokens.dart';

/// Kartu permukaan mengikuti border, bayangan, dan radius tema aktif.
class TokenCard extends ConsumerWidget {
  const TokenCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.color,
    this.elevated = true,
    this.radius,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color? color;
  final bool elevated;
  final double? radius;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    return DecoratedBox(
      decoration: t.box(color: color, elevated: elevated, radiusOverride: radius),
      child: Padding(padding: padding, child: child),
    );
  }
}

/// Tombol utama dengan umpan balik tekan. Tema bayangan keras bergeser saat ditekan.
class TokenButton extends ConsumerStatefulWidget {
  const TokenButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.filled = true,
    this.color,
    this.expand = true,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool filled;
  final Color? color;
  final bool expand;

  @override
  ConsumerState<TokenButton> createState() => _TokenButtonState();
}

class _TokenButtonState extends ConsumerState<TokenButton> {
  bool _down = false;

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tokensProvider);
    final enabled = widget.onPressed != null;
    final bg = widget.filled ? (widget.color ?? t.primary) : t.surface;
    final fg = widget.filled
        ? (widget.color == null ? t.onPrimary : _onColor(widget.color!))
        : t.ink;
    final hard = t.shadowKind == ShadowKind.hard;
    final shift = _down && hard ? 3.0 : 0.0;

    final content = Row(
      mainAxisSize: widget.expand ? MainAxisSize.max : MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (widget.icon != null) ...[
          Icon(widget.icon, size: 20, color: fg),
          const SizedBox(width: 8),
        ],
        Flexible(
          child: Text(
            widget.label,
            textAlign: TextAlign.center,
            style: t.heading(15, color: fg, weight: FontWeight.w800),
          ),
        ),
      ],
    );

    return Semantics(
      button: true,
      enabled: enabled,
      label: widget.label,
      // The visible Text would otherwise be announced a second time.
      excludeSemantics: true,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTapDown: enabled ? (_) => setState(() => _down = true) : null,
        onTapCancel: enabled ? () => setState(() => _down = false) : null,
        onTapUp: enabled ? (_) => setState(() => _down = false) : null,
        onTap: widget.onPressed,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 90),
          constraints: const BoxConstraints(minHeight: 48),
          transform: Matrix4.translationValues(shift, shift, 0),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
          decoration: ShapeDecoration(
            color: enabled ? bg : bg.withValues(alpha: 0.45),
            shape: t.shape(),
            shadows: _down && hard ? const [] : t.shadows,
          ),
          child: content,
        ),
      ),
    );
  }

  Color _onColor(Color c) =>
      ThemeData.estimateBrightnessForColor(c) == Brightness.dark
          ? Colors.white
          : const Color(0xFF111111);
}

/// Bar progres. Bar HP lebar dan tebal, bar XP lebih ramping. Arcade bersegmen.
class StatBar extends ConsumerWidget {
  const StatBar({
    super.key,
    required this.fraction,
    required this.color,
    this.height = 20,
  });

  final double fraction;
  final Color color;
  final double height;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final f = fraction.clamp(0.0, 1.0);
    final track = t.ink.withValues(alpha: t.brightness == Brightness.dark ? 0.14 : 0.1);
    final pad = t.borderWidth > 1 ? 2.0 : 0.0;
    final inner = t.radius > 0 && !t.notched ? (t.radius / 3).clamp(3.0, 99.0) : 0.0;

    return Container(
      height: height,
      // `width: double.infinity` is not decoration: the bar is used inside
      // Columns, whose children get loose cross-axis constraints. Without it the
      // Container shrink-wraps its only sized child - the fill, whose width is
      // `maxWidth * fraction` - so an empty HP or XP bar collapsed to a 10 px
      // stub that reads as a stray glyph instead of an empty track.
      width: double.infinity,
      padding: EdgeInsets.all(pad),
      decoration: ShapeDecoration(
        color: track,
        shape: t.shape(radiusOverride: t.notched ? 3 : (t.radius / 2).clamp(4.0, 14.0)),
      ),
      child: LayoutBuilder(
        builder: (context, c) {
          return Stack(
            children: [
              AnimatedContainer(
                duration: const Duration(milliseconds: 500),
                curve: Curves.easeOutCubic,
                width: c.maxWidth * f,
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(inner),
                ),
              ),
              if (t.notched)
                Positioned.fill(
                  child: Row(
                    children: List.generate(
                      10,
                      (i) => Expanded(
                        child: Container(
                          decoration: BoxDecoration(
                            border: Border(
                              right: BorderSide(
                                color: i == 9 ? Colors.transparent : t.borderColor,
                                width: 2,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}

/// Judul bagian dengan sub-keterangan opsional.
class SectionTitle extends ConsumerWidget {
  const SectionTitle(this.title, {super.key, this.trailing});

  final String title;
  final Widget? trailing;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          Expanded(child: Text(title, style: t.heading(18))),
          ?trailing,
        ],
      ),
    );
  }
}

/// Label status kecil. Warna hanya untuk menandai status yang nyata.
class StatusPill extends ConsumerWidget {
  const StatusPill({super.key, required this.label, this.color, this.textColor});

  final String label;
  final Color? color;
  final Color? textColor;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final bg = color ?? t.primary;
    final fg = textColor ??
        (ThemeData.estimateBrightnessForColor(bg) == Brightness.dark
            ? Colors.white
            : const Color(0xFF111111));
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: ShapeDecoration(
        color: bg,
        shape: t.shape(radiusOverride: t.notched ? 3 : (t.radius > 0 ? 10 : 0)),
      ),
      child: Text(label, style: t.body(12, color: fg, weight: FontWeight.w800)),
    );
  }
}

/// Catatan transparansi data, dipakai saat sumber data belum nyata.
class NoticeBanner extends ConsumerWidget {
  const NoticeBanner({
    super.key,
    required this.message,
    this.actionLabel,
    this.onAction,
  });

  final String message;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    return TokenCard(
      elevated: false,
      color: t.hpTired.withValues(alpha: 0.16),
      padding: const EdgeInsets.all(14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Icon(Icons.info_outline_rounded, color: t.ink, size: 22),
          const SizedBox(width: 12),
          Expanded(child: Text(message, style: t.body(13))),
          if (actionLabel != null) ...[
            const SizedBox(width: 8),
            TextButton(
              onPressed: onAction,
              style: TextButton.styleFrom(
                minimumSize: const Size(48, 48),
                foregroundColor: t.ink,
              ),
              child: Text(actionLabel!, style: t.body(13, weight: FontWeight.w800)),
            ),
          ],
        ],
      ),
    );
  }
}
