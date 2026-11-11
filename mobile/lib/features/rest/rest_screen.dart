import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/balancing.dart';
import '../../core/l10n/l10n.dart';
import '../../core/models/companion.dart';
import '../../core/models/pet.dart';
import '../../core/models/session_deadline.dart';
import '../../core/state/app_state.dart';
import '../../widgets/companion_3d.dart';
import '../../widgets/ui.dart';

/// Mulai sesi istirahat dari Beranda atau overlay HP kritis (prd Bab 10.3).
Future<void> startRest(BuildContext context, WidgetRef ref) {
  return Navigator.of(
    context,
  ).push<void>(MaterialPageRoute(builder: (_) => const RestScreen()));
}

class RestScreen extends ConsumerStatefulWidget {
  const RestScreen({super.key});

  @override
  ConsumerState<RestScreen> createState() => _RestScreenState();
}

class _RestScreenState extends ConsumerState<RestScreen>
    with WidgetsBindingObserver {
  Timer? _ticker;
  late SessionDeadline _session;
  late GameNotifier _game;
  late DateTime Function() _now;
  int _remaining = 0;
  bool _finished = false;
  bool _closing = false;
  int _celebrateTick = 0;
  double _rewardBefore = 0;
  int _awardedHp = 0;
  int _awardedXp = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _game = ref.read(gameProvider.notifier);
    _now = ref.read(nowProvider);
    final game = ref.read(gameProvider);
    _session = SessionDeadline(
      start: _now(),
      duration: Duration(
        seconds:
            game.restMinutes *
            (game.demoSpeed ? Balancing.demoSecondsPerMinute : 60),
      ),
    );
    _remaining = _session.remainingSeconds(_now());
    // Provider mutation is deferred until the route has finished building.
    Future.microtask(() {
      if (!mounted) return;
      _game.setResting(true);
      _rewardBefore = ref.read(gameProvider).restRewardFraction;
      _startTicker();
    });
  }

  void _startTicker() {
    _ticker?.cancel();
    if (_finished || _closing) return;
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) => _tick());
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
    if (!mounted || _finished || _closing) return;
    _game.ensureCurrentDay();
    _rewardBefore = ref.read(gameProvider).restRewardFraction;
    final remaining = _session.remainingSeconds(_now());
    if (remaining == 0) {
      _ticker?.cancel();
      final before = ref.read(gameProvider);
      _game.completeRest(1);
      final after = ref.read(gameProvider);
      setState(() {
        _remaining = 0;
        _finished = true;
        _awardedHp = after.bonusHp - before.bonusHp;
        _awardedXp =
            (after.level - before.level) * Balancing.xpPerLevel +
            after.xp -
            before.xp;
        _celebrateTick++;
      });
      return;
    }
    setState(() => _remaining = remaining);
  }

  double get _progress => _session.fraction(_now());

  Future<void> _cancel() async {
    final s = ref.read(l10nProvider);
    final t = ref.read(tokensProvider);
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: t.surface,
        shape: t.shape(),
        title: Text(
          s.t('Akhiri istirahat?', 'End the break?'),
          style: t.heading(18),
        ),
        content: Text(
          s.t(
            'Kamu tetap mendapat pemulihan sebanding dengan waktu yang sudah '
                'dijalani. Tidak ada hukuman tambahan.',
            'You still get recovery in proportion to the time you already spent. '
                'There is no extra penalty.',
          ),
          style: t.body(14),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(
              s.t('Lanjut istirahat', 'Keep resting'),
              style: t.body(13),
            ),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(
              s.t('Akhiri', 'End'),
              style: t.body(13, weight: FontWeight.w800),
            ),
          ),
        ],
      ),
    );
    if (confirm != true || !mounted || _closing) return;
    _closing = true;
    _ticker?.cancel();
    _game.completeRest(_progress);
    Navigator.of(context).pop();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _ticker?.cancel();
    if (!_finished && !_closing) {
      // Route removal does not grant a reward or leave the pet stuck resting.
      Future.microtask(() => _game.setResting(false));
    }
    super.dispose();
  }

  String _clock(int seconds) {
    final m = (seconds ~/ 60).toString().padLeft(2, '0');
    final sec = (seconds % 60).toString().padLeft(2, '0');
    return '$m:$sec';
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tokensProvider);
    final s = ref.watch(l10nProvider);
    final game = ref.watch(gameProvider);
    final pet = game.petFamily ?? PetFamily.momo;
    final hp = ref.watch(hpProvider);
    final rewardAfter = (_rewardBefore + _progress).clamp(0.0, 1.0);
    final recovered = _finished
        ? _awardedHp
        : Balancing.restRewardTotal(rewardAfter, Balancing.restMaxHpGain) -
              Balancing.restRewardTotal(_rewardBefore, Balancing.restMaxHpGain);
    final xpGained = _finished
        ? _awardedXp
        : Balancing.restRewardTotal(rewardAfter, Balancing.restMaxXp) -
              Balancing.restRewardTotal(_rewardBefore, Balancing.restMaxXp);
    final previewFrom = _finished ? (hp - recovered).clamp(0, 100) : hp;
    final previewTo = _finished ? hp : (hp + recovered).clamp(0, 100);

    return PopScope(
      canPop: _finished || _closing,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop && !_finished && !_closing) _cancel();
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
                      onPressed: _finished
                          ? () => Navigator.of(context).pop()
                          : _cancel,
                      icon: Icon(Icons.close_rounded, color: t.ink),
                      tooltip: s.t('Tutup', 'Close'),
                    ),
                    Expanded(
                      child: Text(
                        _finished
                            ? s.t('Istirahat selesai', 'Break complete')
                            : s.t('Mode istirahat', 'Rest mode'),
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
                Text(
                  _finished
                      ? s.t('Pulih!', 'Recovered!')
                      : s.t(
                          '${pet.label} sedang tidur',
                          '${pet.label} is sleeping',
                        ),
                  style: t.heading(26),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 6),
                Text(
                  _finished
                      ? s.t(
                          '${pet.label} bangun dengan tenaga baru.',
                          '${pet.label} is awake with new energy.',
                        )
                      : s.t(
                          'Letakkan HP sebentar. ${pet.label} pulih bertahap.',
                          'Put the phone down for a while. ${pet.label} recovers gradually.',
                        ),
                  style: t.body(14, color: t.muted),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 18),
                SizedBox(
                  height: 240,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      Container(
                        width: 200,
                        height: 200,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: t.secondary.withValues(alpha: 0.18),
                        ),
                      ),
                      Companion3D(
                        pet: pet,
                        stage: game.stage,
                        mood: Mood.segar,
                        resting: !_finished,
                        height: 210,
                        celebrateTick: _celebrateTick,
                        reactOnTap: !_finished,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  _finished ? '00:00' : _clock(_remaining),
                  style: t.number(46),
                ),
                const SizedBox(height: 10),
                StatBar(fraction: _progress, color: t.hpHealthy, height: 16),
                const SizedBox(height: 12),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      s.t('Pemulihan sesi ini', 'Recovery this session'),
                      style: t.body(12, color: t.muted),
                    ),
                    Text(
                      '+$recovered HP  ·  +$xpGained XP',
                      style: t.number(12),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(s.t('HP', 'HP'), style: t.body(12, color: t.muted)),
                    Text('$previewFrom → $previewTo', style: t.number(12)),
                  ],
                ),
                const Spacer(),
                if (_finished)
                  TokenButton(
                    label: s.t('Kembali ke Beranda', 'Back to Home'),
                    onPressed: () => Navigator.of(context).pop(),
                  )
                else ...[
                  TokenButton(
                    label: s.t('Selesaikan lebih awal', 'Finish early'),
                    filled: false,
                    onPressed: _cancel,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    s.t(
                      'Reward dihitung sesuai waktu istirahat, maksimal +25 HP dan +30 XP per hari. Kamu tetap bisa istirahat lagi.',
                      'Rewards scale with rest time, up to +25 HP and +30 XP per day. You can rest again anytime.',
                    ),
                    style: t.body(11, color: t.muted),
                    textAlign: TextAlign.center,
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
