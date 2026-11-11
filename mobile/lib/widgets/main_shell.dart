import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/l10n/l10n.dart';
import '../core/models/companion.dart';
import '../core/models/pet.dart';
import '../core/services/pause_controller.dart';
import '../core/services/pill_controller.dart';
import '../core/services/reminder_controller.dart';
import '../core/state/app_state.dart';
import '../features/duel/duel_screen.dart';
import '../features/home/home_screen.dart';
import '../features/misi/misi_screen.dart';
import '../features/profil/profil_screen.dart';
import '../features/rekap/rekap_screen.dart';
import '../features/rest/rest_screen.dart';
import 'evolution_reveal.dart';
import 'ui.dart';

/// Urutan tab terkunci: Rekap | Misi | Beranda (tengah, raised) | Duel | Profil.
class MainShell extends ConsumerStatefulWidget {
  const MainShell({super.key});

  @override
  ConsumerState<MainShell> createState() => _MainShellState();
}

class _MainShellState extends ConsumerState<MainShell> {
  int _index = 2;
  bool _criticalShown = false;
  bool _syncScheduled = false;
  Set<String>? _syncedPackages;

  @override
  void initState() {
    super.initState();
    ref.listenManual(gameProvider, (previous, next) {
      if (previous == null ||
          previous.themeId != next.themeId ||
          previous.language != next.language ||
          previous.monitoredPackages != next.monitoredPackages ||
          // The pill keeps its own mascot art; a stage evolution must reach
          // native even while the pill is already visible.
          previous.level != next.level) {
        _scheduleNativeSync();
      }
    });
    // HP pill dihitung native supaya tetap hidup di luar aplikasi; bonus dari
    // misi/istirahat cukup dikirim saat berubah.
    ref.listenManual(gameProvider.select((g) => g.bonusHp), (previous, next) {
      if (previous == null || previous == next) return;
      unawaited(ref.read(usageServiceProvider).syncPillHp(next));
    });
    // Tidur mengalahkan semua perilaku spontan di kedua overlay.
    ref.listenManual(gameProvider.select((g) => g.isResting), (previous, next) {
      if (previous == null || previous == next) return;
      unawaited(ref.read(usageServiceProvider).setPetResting(next));
    });
    _scheduleNativeSync();
  }

  // Run after provider updates and this frame, never from build. Read the latest
  // tokens rather than closing over the old theme/language in a listener.
  void _scheduleNativeSync() {
    if (_syncScheduled) return;
    _syncScheduled = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _syncScheduled = false;
      if (mounted) unawaited(_syncNativeConfig());
    });
  }

  Future<void> _syncNativeConfig() async {
    try {
      final game = ref.read(gameProvider);
      if (!game.onboarded || !game.collectionEnabled) return;
      // Native counts scroll events only for the monitored set. Seed it at
      // startup so Accessibility works before Jeda Sadar is ever toggled.
      final packages = game.monitoredPackages.toList()..sort();
      if (_syncedPackages == null ||
          _syncedPackages!.length != packages.length ||
          !packages.every(_syncedPackages!.contains)) {
        try {
          await ref.read(usageServiceProvider).setMonitoredApps(packages);
          _syncedPackages = packages.toSet();
        } catch (error) {
          debugPrint('Monitored app sync failed: $error');
        }
      }
      if (game.pauseEnabled) {
        // The pause overlay carries an HP snapshot. Wait for the first usage
        // read so a startup sync does not pin "no real HP data" while access
        // is granted; cap the wait so config sync never stalls.
        try {
          await ref
              .read(usageProvider.future)
              .timeout(const Duration(seconds: 2));
        } catch (_) {
          // Usage failure is reported on Home; the overlay uses its fallback.
        }
        if (!mounted) return;
        // The toggle may have been turned off while usage was loading.
        if (ref.read(gameProvider).pauseEnabled) {
          await applyPause(ref, enable: true);
        }
      }
      if (!mounted || !ref.read(gameProvider).onboarded) return;
      if (ref.read(gameProvider).reminderEnabled) {
        await applyReminder(ref, enable: true);
      }
      if (!mounted) return;
      // A config update must not opt the user into a floating overlay.
      final running = await ref.read(usageServiceProvider).isPillVisible();
      if (mounted &&
          running &&
          ref.read(gameProvider).onboarded &&
          ref.read(gameProvider).collectionEnabled) {
        await applyPill(ref);
      }
      if (!mounted) return;
      final latest = ref.read(gameProvider);
      await ref.read(usageServiceProvider).setPetResting(latest.isResting);
    } catch (error) {
      debugPrint('Native configuration sync failed: $error');
    }
  }

  static final _screens = <WidgetBuilder>[
    (_) => const RekapScreen(),
    (_) => const MisiScreen(),
    (_) => const HomeScreen(),
    (_) => const DuelScreen(),
    (_) => const ProfilScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tokensProvider);
    final hp = ref.watch(hpProvider);
    final resting = ref.watch(gameProvider.select((g) => g.isResting));

    // Peringatan bahaya saat HP habis (prd Bab 7.2), dengan dua pilihan:
    // istirahatkan HP atau tetap lanjut. Tidak ada blokir paksa.
    if (hp > 0) _criticalShown = false;
    if (hp == 0 && !resting && !_criticalShown) {
      _criticalShown = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _showCriticalDialog();
      });
    }

    ref.listen<Stage?>(gameProvider.select((s) => s.pendingEvolution), (
      prev,
      next,
    ) {
      if (next != null) {
        WidgetsBinding.instance.addPostFrameCallback((_) async {
          if (!mounted) return;
          await showEvolutionReveal(context, next);
          ref.read(gameProvider.notifier).clearEvolution();
        });
      }
    });

    return Scaffold(
      backgroundColor: t.bg,
      body: SafeArea(
        bottom: false,
        child: LazyTabStack(index: _index, builders: _screens),
      ),
      bottomNavigationBar: _BottomNav(
        index: _index,
        onSelect: (i) => setState(() => _index = i),
      ),
    );
  }

  Future<void> _showCriticalDialog() async {
    final s = ref.read(l10nProvider);
    final t = ref.read(tokensProvider);
    final pet = ref.read(gameProvider).petFamily ?? PetFamily.momo;

    final choice = await showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => Dialog(
        backgroundColor: t.bg,
        shape: t.shape(radiusOverride: t.notched ? 0 : t.radius),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                s.t(
                  'HP ${pet.label} habis',
                  '${pet.label}\'s HP is gone',
                ),
                style: t.heading(22),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(
                s.t(
                  'Pemakaian hari ini melewati batas nyaman ${pet.label}. '
                      'Pilih langkahmu; tidak ada kunci paksa.',
                  'Today\'s usage went past ${pet.label}\'s comfort line. '
                      'Choose your next step; nothing is locked by force.',
                ),
                style: t.body(13, color: t.muted),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              Container(
                width: 88,
                height: 88,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: t.hpCritical.withValues(alpha: 0.14),
                ),
                child: Icon(
                  Icons.sentiment_dissatisfied_rounded,
                  color: t.hpCritical,
                  size: 44,
                ),
              ),
              const SizedBox(height: 16),
              TokenButton(
                label: s.t('Istirahatkan HP', 'Rest your phone'),
                icon: Icons.bedtime_rounded,
                color: t.hpCritical,
                onPressed: () => Navigator.of(ctx).pop('rest'),
              ),
              const SizedBox(height: 8),
              TokenButton(
                label: s.t('Tetap lanjut', 'Keep going'),
                filled: false,
                onPressed: () => Navigator.of(ctx).pop('continue'),
              ),
              const SizedBox(height: 8),
              Text(
                s.t(
                  'Tetap lanjut tidak memotong XP. ${pet.label} hanya tetap Kritis sampai kamu beristirahat.',
                  'Continuing does not cut XP. ${pet.label} just stays Critical until you rest.',
                ),
                style: t.body(10, color: t.muted),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );

    if (choice == 'rest' && mounted) {
      await startRest(context, ref);
    }
  }
}

/// Creates a tab on first visit and keeps its element (scroll/form state) alive.
/// Unvisited slots are cheap placeholders; retained tabs cannot tick offscreen.
class LazyTabStack extends StatefulWidget {
  const LazyTabStack({super.key, required this.index, required this.builders});

  final int index;
  final List<WidgetBuilder> builders;

  @override
  State<LazyTabStack> createState() => _LazyTabStackState();
}

class _LazyTabStackState extends State<LazyTabStack> {
  final Map<int, Widget> _visited = {};

  @override
  Widget build(BuildContext context) {
    _visited.putIfAbsent(
      widget.index,
      () => widget.builders[widget.index](context),
    );
    return IndexedStack(
      index: widget.index,
      children: List.generate(
        widget.builders.length,
        (i) => TickerMode(
          enabled: i == widget.index,
          child: _visited[i] ?? const SizedBox.shrink(),
        ),
      ),
    );
  }
}

class _NavItem {
  const _NavItem(this.icon);
  final IconData icon;
}

class _BottomNav extends ConsumerWidget {
  const _BottomNav({required this.index, required this.onSelect});

  final int index;
  final ValueChanged<int> onSelect;

  static const _items = [
    _NavItem(Icons.bar_chart_rounded),
    _NavItem(Icons.flag_rounded),
    _NavItem(Icons.home_rounded),
    _NavItem(Icons.emoji_events_rounded),
    _NavItem(Icons.person_rounded),
  ];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final s = ref.watch(l10nProvider);
    final bottomInset = MediaQuery.paddingOf(context).bottom;
    final labels = [
      s.t('Rekap', 'Recap'),
      s.t('Misi', 'Missions'),
      s.t('Beranda', 'Home'),
      s.t('Duel', 'Duel'),
      s.t('Profil', 'Profile'),
    ];

    return Container(
      decoration: BoxDecoration(
        color: t.surface,
        border: Border(
          top: BorderSide(
            color: t.borderWidth > 0
                ? t.borderColor
                : t.ink.withValues(alpha: 0.08),
            width: t.borderWidth > 0 ? t.borderWidth : 1,
          ),
        ),
      ),
      padding: EdgeInsets.only(bottom: bottomInset),
      child: SizedBox(
        height: 64,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: List.generate(_items.length, (i) {
            final item = _items[i];
            final active = i == index;
            final center = i == 2;
            return Expanded(
              child: Semantics(
                button: true,
                selected: active,
                label: labels[i],
                // Exclude the visible label so TalkBack says it only once.
                excludeSemantics: true,
                child: InkResponse(
                  onTap: () => onSelect(i),
                  radius: 36,
                  child: center
                      // Stack instead of a translated Column: the 62dp center
                      // button intentionally rises above the 64dp bar, and a
                      // Column would report a permanent overflow in debug.
                      ? Stack(
                          clipBehavior: Clip.none,
                          alignment: Alignment.bottomCenter,
                          children: [
                            Positioned(
                              left: 0,
                              right: 0,
                              bottom: 8,
                              child: Text(
                                labels[i],
                                textAlign: TextAlign.center,
                                style: t.body(
                                  11,
                                  color: active ? t.ink : t.muted,
                                  weight: active
                                      ? FontWeight.w800
                                      : FontWeight.w600,
                                ),
                              ),
                            ),
                            Positioned(
                              bottom: 24,
                              child: _CenterButton(active: active),
                            ),
                          ],
                        )
                      : Column(
                          mainAxisAlignment: MainAxisAlignment.end,
                          children: [
                            Icon(
                              item.icon,
                              size: 26,
                              color: active ? t.ink : t.muted,
                            ),
                            Padding(
                              padding: const EdgeInsets.only(top: 2, bottom: 8),
                              child: Text(
                                labels[i],
                                style: t.body(
                                  11,
                                  color: active ? t.ink : t.muted,
                                  weight: active
                                      ? FontWeight.w800
                                      : FontWeight.w600,
                                ),
                              ),
                            ),
                          ],
                        ),
                ),
              ),
            );
          }),
        ),
      ),
    );
  }
}

/// Tombol Beranda: lebih besar dan terangkat. Ikon netral, bukan potret statis.
class _CenterButton extends ConsumerWidget {
  const _CenterButton({required this.active});

  final bool active;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    return Container(
      width: 62,
      height: 62,
      decoration: ShapeDecoration(
        color: active ? t.primary : t.surface,
        shape: t.notched
            ? BeveledRectangleBorder(
                side: BorderSide(color: t.borderColor, width: t.borderWidth),
                borderRadius: BorderRadius.circular(8),
              )
            : CircleBorder(
                side: t.borderWidth > 0
                    ? BorderSide(color: t.borderColor, width: t.borderWidth)
                    : BorderSide(color: t.ink.withValues(alpha: 0.08)),
              ),
        shadows: t.shadows,
      ),
      child: Icon(
        Icons.pets_rounded,
        size: 30,
        color: active ? t.ink : t.muted,
      ),
    );
  }
}
