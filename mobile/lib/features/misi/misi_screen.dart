import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/balancing.dart';
import '../../core/l10n/l10n.dart';
import '../../core/models/companion.dart';
import '../../core/models/pet.dart';
import '../../core/models/session_deadline.dart';
import '../../core/services/usage_service.dart';
import '../../core/state/app_state.dart';
import '../../widgets/companion_3d.dart';
import '../../widgets/ui.dart';

/// Tab Misi: Bank Waktu, katalog misi offline, dan jalur evolusi (prd Bab 9.3).
class MisiScreen extends ConsumerWidget {
  const MisiScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final s = ref.watch(l10nProvider);
    final game = ref.watch(gameProvider);

    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 14, 18, 28),
      children: [
        Text(s.t('Misi', 'Missions'), style: t.heading(28)),
        const SizedBox(height: 4),
        Text(
          s.t(
            'Misi offline satu-satunya sumber XP. Tiap misi selesai memberi saldo '
                'waktu, XP, dan HP.',
            'Offline missions are the only XP source. Each finished mission grants '
                'time balance, XP, and HP.',
          ),
          style: t.body(13, color: t.muted),
        ),
        const SizedBox(height: 14),
        _BankCard(game: game, s: s),
        const SizedBox(height: 18),
        SectionTitle(
          s.t('Katalog misi', 'Mission catalog'),
          trailing: Text(
            '${game.doneToday.length}/${kMissions.length}',
            style: t.body(12, color: t.muted),
          ),
        ),
        ...kMissions.map(
          (mission) => Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: _MissionCard(
              mission: mission,
              done: game.doneToday.contains(mission.id),
              s: s,
            ),
          ),
        ),
        const SizedBox(height: 8),
        SectionTitle(s.t('Jalur evolusi', 'Evolution path')),
        _EvolutionPath(game: game, s: s),
        const SizedBox(height: 12),
        TokenCard(
          elevated: false,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.lightbulb_outline_rounded, size: 18, color: t.muted),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  s.t(
                    'XP tidak berkurang saat HP turun. Hanya HP harian yang turun, '
                        'jadi tidak ada hukuman ganda.',
                    'XP never drops when HP drops. Only daily HP falls, so there is '
                        'no double penalty.',
                  ),
                  style: t.body(11, color: t.muted),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _BankCard extends ConsumerWidget {
  const _BankCard({required this.game, required this.s});

  final GameState game;
  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final available = game.bankAvailable;

    return TokenCard(
      color: t.tint(t.secondary, 0.18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.savings_outlined, color: t.ink, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  s.t('Bank Waktu', 'Time Bank'),
                  style: t.heading(18),
                ),
              ),
              StatusPill(label: s.t('3 metrik', '3 metrics')),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _BankMetric(
                  label: s.t('Masuk', 'In'),
                  value: '+${game.bankIn}m',
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _BankMetric(
                  label: s.t('Keluar', 'Out'),
                  value: '-${game.bankOut}m',
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _BankMetric(
                  label: s.t('Tersedia', 'Available'),
                  value: '${available}m',
                  highlight: true,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            s.t(
              'Tukar saldo untuk menambah batas satu app hari ini. Jeda Sadar harus '
                  'aktif dan app sudah punya batas. Pemakaian nyata tetap mengurangi HP.',
              'Trade balance for extra allowance on one app today. Conscious Pause must '
                  'be on and the app needs a limit. Real usage still affects HP.',
            ),
            style: t.body(11, color: t.muted),
          ),
          const SizedBox(height: 10),
          TokenButton(
            label: s.t('Pakai kuota tambahan', 'Use extra quota'),
            filled: false,
            onPressed:
                available <= 0 ||
                    !game.pauseEnabled ||
                    !game.collectionEnabled ||
                    game.appLimits.isEmpty
                ? null
                : () => _spend(context, ref, available),
          ),
        ],
      ),
    );
  }

  Future<void> _spend(
    BuildContext context,
    WidgetRef ref,
    int available,
  ) async {
    final s = ref.read(l10nProvider);
    final t = ref.read(tokensProvider);
    final options = Balancing.bankSpendOptions
        .where((m) => m <= available)
        .toList();
    if (options.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            s.t(
              'Saldo belum cukup untuk satu paket kuota. Selesaikan misi dulu.',
              'Not enough balance for a quota pack yet. Finish a mission first.',
            ),
          ),
        ),
      );
      return;
    }

    final packages =
        ref
            .read(gameProvider)
            .appLimits
            .entries
            .where((entry) => entry.value > 0)
            .map((entry) => entry.key)
            .toList()
          ..sort();
    if (packages.isEmpty) return;
    final packageName = await showDialog<String>(
      context: context,
      builder: (ctx) => SimpleDialog(
        title: Text(
          s.t('Pilih app dengan batas', 'Choose a limited app'),
          style: t.heading(18),
        ),
        children: [
          for (final package in packages)
            SimpleDialogOption(
              onPressed: () => Navigator.of(ctx).pop(package),
              child: Text(
                kScrollTargets[package] ?? package,
                style: t.body(14),
              ),
            ),
        ],
      ),
    );
    if (packageName == null || !context.mounted) return;
    final picked = await showDialog<int>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: t.surface,
        shape: t.shape(),
        title: Text(s.t('Pakai kuota', 'Use quota'), style: t.heading(18)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final m in options)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: TokenButton(
                  label: s.t('$m menit', '$m minutes'),
                  filled: false,
                  onPressed: () => Navigator.of(ctx).pop(m),
                ),
              ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text(s.t('Batal', 'Cancel'), style: t.body(13)),
          ),
        ],
      ),
    );
    if (picked == null || !context.mounted) return;
    String message;
    try {
      final ok = await ref
          .read(gameProvider.notifier)
          .spendBank(picked, packageName: packageName);
      message = ok
          ? s.t(
              'Batas $packageName hari ini ditambah $picked menit.',
              'Added $picked minutes to $packageName’s allowance today.',
            )
          : s.t(
              'Kuota tidak diberikan. Periksa izin, batas app, dan saldo.',
              'Allowance was not granted. Check permissions, app limit, and balance.',
            );
    } catch (_) {
      message = s.t(
        'Kuota diberikan, tetapi saldo gagal disimpan. Jangan ulangi transaksi.',
        'Allowance granted, but saving the balance failed. Do not retry the transaction.',
      );
    }
    if (!context.mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }
}

class _BankMetric extends ConsumerWidget {
  const _BankMetric({
    required this.label,
    required this.value,
    this.highlight = false,
  });

  final String label;
  final String value;
  final bool highlight;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
      decoration: ShapeDecoration(
        color: highlight ? t.surface : t.surface.withValues(alpha: 0.6),
        shape: t.shape(radiusOverride: t.notched ? 3 : (t.radius > 0 ? 12 : 0)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: t.body(10, color: t.muted, weight: FontWeight.w800),
          ),
          const SizedBox(height: 3),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(value, style: t.number(19)),
          ),
        ],
      ),
    );
  }
}

class _MissionCard extends ConsumerWidget {
  const _MissionCard({
    required this.mission,
    required this.done,
    required this.s,
  });

  final Mission mission;
  final bool done;
  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final demo = ref.watch(gameProvider.select((g) => g.demoSpeed));

    return TokenCard(
      color: done ? t.tint(t.hpHealthy, 0.14) : t.surface,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(s.missionTitle(mission), style: t.heading(16)),
              ),
              StatusPill(
                label: s.t(
                  '${mission.durationMinutes} menit',
                  '${mission.durationMinutes} min',
                ),
                color: t.ink.withValues(alpha: 0.08),
                textColor: t.ink,
              ),
            ],
          ),
          const SizedBox(height: 2),
          Text(s.missionHint(mission), style: t.body(11, color: t.muted)),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              StatusPill(label: '+${mission.bankReward}m', color: t.secondary),
              StatusPill(label: '+${mission.xp} XP', color: t.primary),
              StatusPill(label: '+${mission.hp} HP', color: t.hpHealthy),
            ],
          ),
          const SizedBox(height: 12),
          if (done)
            Row(
              children: [
                Icon(Icons.check_circle_rounded, color: t.hpHealthy, size: 20),
                const SizedBox(width: 8),
                Text(
                  s.t('Selesai hari ini', 'Done today'),
                  style: t.body(13, weight: FontWeight.w800),
                ),
              ],
            )
          else
            TokenButton(
              label: demo
                  ? s.t('Mulai (mode demo)', 'Start (demo mode)')
                  : s.t('Mulai misi', 'Start mission'),
              icon: Icons.play_arrow_rounded,
              onPressed: () => Navigator.of(context).push<void>(
                MaterialPageRoute(
                  builder: (_) => MissionSessionScreen(mission: mission),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _EvolutionPath extends ConsumerWidget {
  const _EvolutionPath({required this.game, required this.s});

  final GameState game;
  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final current = game.stage;
    final pet = game.petFamily ?? PetFamily.momo;

    return Row(
      children: Stage.values.map((stage) {
        final unlocked = stage.index <= current.index;
        final isCurrent = stage == current;
        return Expanded(
          child: Padding(
            padding: EdgeInsets.only(right: stage == Stage.dewasa ? 0 : 8),
            child: TokenCard(
              elevated: isCurrent,
              color: isCurrent
                  ? t.tint(t.primary, 0.22)
                  : unlocked
                  ? t.surface
                  : t.ink.withValues(alpha: 0.06),
              padding: const EdgeInsets.all(8),
              child: Column(
                children: [
                  SizedBox(
                    height: 70,
                    child: Center(
                      child: Icon(
                        unlocked
                            ? (pet == PetFamily.drako
                                  ? Icons.local_fire_department_rounded
                                  : Icons.pets_rounded)
                            : Icons.lock_rounded,
                        size: unlocked ? 42 : 26,
                        color: unlocked
                            ? (isCurrent ? t.ink : t.muted)
                            : t.muted,
                      ),
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    unlocked ? s.stageLabel(stage) : '???',
                    style: t.body(12, weight: FontWeight.w800),
                  ),
                  Text(stage.levelRange, style: t.body(9, color: t.muted)),
                ],
              ),
            ),
          ),
        );
      }).toList(),
    );
  }
}

/// Sesi satu misi offline. Timer berjalan penuh; membatalkan tidak memberi
/// imbalan karena misi butuh durasi nyata.
class MissionSessionScreen extends ConsumerStatefulWidget {
  const MissionSessionScreen({super.key, required this.mission});

  final Mission mission;

  @override
  ConsumerState<MissionSessionScreen> createState() =>
      _MissionSessionScreenState();
}

class _MissionSessionScreenState extends ConsumerState<MissionSessionScreen>
    with WidgetsBindingObserver {
  Timer? _ticker;
  late SessionDeadline _session;
  late DateTime Function() _now;
  int _remaining = 0;
  bool _done = false;
  bool _closing = false;
  int _celebrateTick = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _now = ref.read(nowProvider);
    final demo = ref.read(gameProvider).demoSpeed;
    _session = SessionDeadline(
      start: _now(),
      duration: Duration(
        seconds:
            widget.mission.durationMinutes *
            (demo ? Balancing.demoSecondsPerMinute : 60),
      ),
    );
    _remaining = _session.remainingSeconds(_now());
    _startTicker();
  }

  void _startTicker() {
    _ticker?.cancel();
    if (!_done && !_closing) {
      _ticker = Timer.periodic(const Duration(seconds: 1), (_) => _tick());
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _ticker?.cancel();
    if (state == AppLifecycleState.resumed) {
      _tick();
      _startTicker();
    }
  }

  void _tick() {
    if (!mounted || _done || _closing) return;
    ref.read(gameProvider.notifier).ensureCurrentDay();
    final remaining = _session.remainingSeconds(_now());
    if (remaining == 0) {
      _ticker?.cancel();
      setState(() {
        _remaining = 0;
        _done = true;
        _celebrateTick++;
      });
      ref.read(gameProvider.notifier).completeMission(widget.mission);
      return;
    }
    setState(() => _remaining = remaining);
  }

  double get _progress => _session.fraction(_now());

  String _clock(int seconds) {
    final m = (seconds ~/ 60).toString().padLeft(2, '0');
    final sec = (seconds % 60).toString().padLeft(2, '0');
    return '$m:$sec';
  }

  Future<void> _cancel() async {
    final s = ref.read(l10nProvider);
    final t = ref.read(tokensProvider);
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: t.surface,
        shape: t.shape(),
        title: Text(
          s.t('Batalkan misi?', 'Cancel mission?'),
          style: t.heading(18),
        ),
        content: Text(
          s.t(
            'Misi hanya memberi imbalan bila durasinya selesai. Kamu bisa memulai lagi '
                'kapan saja.',
            'Missions only reward you when the full duration is done. You can start '
                'again anytime.',
          ),
          style: t.body(14),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(s.t('Lanjut', 'Continue'), style: t.body(13)),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(
              s.t('Batalkan', 'Cancel'),
              style: t.body(13, weight: FontWeight.w800),
            ),
          ),
        ],
      ),
    );
    if (confirm == true && mounted && !_closing) {
      _closing = true;
      _ticker?.cancel();
      Navigator.of(context).pop();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _ticker?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tokensProvider);
    final s = ref.watch(l10nProvider);
    final game = ref.watch(gameProvider);

    return PopScope(
      canPop: _done || _closing,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop && !_done && !_closing) _cancel();
      },
      child: Scaffold(
        backgroundColor: t.bg,
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(22, 16, 22, 18),
            child: Column(
              children: [
                Row(
                  children: [
                    IconButton(
                      onPressed: _done
                          ? () => Navigator.of(context).pop()
                          : _cancel,
                      icon: Icon(Icons.close_rounded, color: t.ink),
                      tooltip: s.t('Tutup', 'Close'),
                    ),
                    Expanded(
                      child: Text(
                        s.missionTitle(widget.mission),
                        style: t.heading(20),
                        textAlign: TextAlign.center,
                      ),
                    ),
                    const SizedBox(width: 48),
                  ],
                ),
                if (game.demoSpeed)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: StatusPill(
                      label: s.t('Mode demo: 1 dtk = 1 mnt', 'Demo: 1s = 1min'),
                    ),
                  ),
                const Spacer(),
                SizedBox(
                  height: 220,
                  child: Companion3D(
                    pet: game.petFamily ?? PetFamily.momo,
                    stage: game.stage,
                    mood: Mood.segar,
                    height: 200,
                    celebrateTick: _celebrateTick,
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  _done
                      ? s.t('Misi selesai!', 'Mission complete!')
                      : _clock(_remaining),
                  style: _done ? t.heading(26) : t.number(44),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 10),
                StatBar(fraction: _progress, color: t.secondary, height: 14),
                const SizedBox(height: 14),
                Text(
                  _done
                      ? s.t(
                          'Saldo waktu, XP, dan HP sudah ditambahkan.',
                          'Time balance, XP, and HP have been added.',
                        )
                      : s.t(
                          'Tinggalkan HP selama misi berjalan. Timer tidak bisa dipercepat.',
                          'Leave your phone during the mission. The timer cannot be rushed.',
                        ),
                  style: t.body(13, color: t.muted),
                  textAlign: TextAlign.center,
                ),
                const Spacer(),
                if (_done)
                  TokenButton(
                    label: s.t('Kembali ke Misi', 'Back to Missions'),
                    onPressed: () => Navigator.of(context).pop(),
                  )
                else
                  TokenButton(
                    label: s.t('Batalkan misi', 'Cancel mission'),
                    filled: false,
                    onPressed: _cancel,
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
