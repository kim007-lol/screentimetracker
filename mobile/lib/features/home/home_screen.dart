import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/l10n/l10n.dart';
import '../../core/models/companion.dart';
import '../../core/models/pet.dart';
import '../../core/models/usage.dart';
import '../../core/state/app_state.dart';
import '../../widgets/companion_3d.dart';
import '../../widgets/permission_flow.dart';
import '../../widgets/ui.dart';
import '../../widgets/weekly_goal_card.dart';
import '../misi/misi_screen.dart';
import '../rest/rest_screen.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final s = ref.watch(l10nProvider);
    final game = ref.watch(gameProvider);
    final hp = ref.watch(hpProvider);
    final mood = ref.watch(moodProvider);
    final usageAsync = ref.watch(usageProvider);
    final loaded = usageAsync.asData?.value;
    // Unavailable is not a measurement: show empty values, never zeros.
    final usage = loaded?.source == UsageSource.unavailable ? null : loaded;
    // HP is only a real reading from Android usage stats. Loading, sample,
    // and unavailable data are unknown, not a healthy 100.
    final hpKnown = usage != null && usage.source == UsageSource.android;
    // A real zero can mean "nothing recorded yet" (no other app opened today)
    // or "scroll tracker is off"; both need a visible next step on Beranda.
    final realUsage = usage != null && usage.source == UsageSource.android;
    final noTrackedApps = realUsage && usage.apps.isEmpty;
    final needsScrollAccess = realUsage && !usage.accessibilityEnabled;

    final pet = game.petFamily ?? PetFamily.momo;
    final hpColor = t.hpColor(hp.toDouble());
    final greeting = game.userName.isEmpty
        ? s.t('Hai!', 'Hi!')
        : s.t('Hai, ${game.userName}!', 'Hi, ${game.userName}!');
    final date = DateFormat(s.datePattern, s.localeName).format(DateTime.now());

    return RefreshIndicator(
      color: t.ink,
      backgroundColor: t.surface,
      onRefresh: () => ref.read(usageProvider.notifier).refresh(),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(18, 14, 18, 28),
        children: [
          // 2. Header: tanggal dan sapaan, streak di kanan
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(date, style: t.body(13, color: t.muted)),
                    const SizedBox(height: 2),
                    Text(greeting, style: t.heading(26)),
                  ],
                ),
              ),
              _StreakBadge(days: game.streak),
            ],
          ),
          const SizedBox(height: 14),

          // 3. Badge tahap dan mood
          Row(
            children: [
              StatusPill(label: s.stageLabel(game.stage)),
              const SizedBox(width: 8),
              StatusPill(
                label: game.isResting
                    ? s.t('Istirahat', 'Resting')
                    : hpKnown
                    ? s.moodLabel(mood)
                    : s.t('Belum terbaca', 'Not read yet'),
                color: game.isResting
                    ? t.secondary
                    : hpKnown
                    ? hpColor
                    : t.muted.withValues(alpha: 0.18),
              ),
            ],
          ),

          // 4-5. Backdrop melingkar dan pendamping
          const SizedBox(height: 4),
          SizedBox(
            height: 250,
            child: Stack(
              alignment: Alignment.center,
              children: [
                Container(
                  width: 210,
                  height: 210,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: t.primary.withValues(alpha: 0.22),
                  ),
                ),
                Companion3D(
                  pet: pet,
                  stage: game.stage,
                  mood: mood,
                  resting: game.isResting,
                  height: 210,
                  celebrateTick: game.celebrationTick,
                  greetOnLoad: true,
                ),
              ],
            ),
          ),

          // 6. Nama dan level
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(pet.label, style: t.heading(24)),
              const SizedBox(width: 8),
              StatusPill(label: 'Lv. ${game.level}'),
            ],
          ),
          const SizedBox(height: 10),

          // 7. Speech bubble
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 320),
              child: TokenCard(
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 10,
                ),
                radius: t.notched
                    ? null
                    : (t.radius > 0 ? t.radius.clamp(6, 18) : 0),
                child: Text(
                  game.isResting
                      ? s.t(
                          'Zzz... istirahat sebentar ya...',
                          'Zzz... taking a short break...',
                        )
                      : hpKnown
                      ? s.moodSpeech(mood)
                      : s.t(
                          'Aku belum bisa membaca pemakaian hari ini.',
                          'I cannot read today\'s usage yet.',
                        ),
                  textAlign: TextAlign.center,
                  style: t.body(13, weight: FontWeight.w700),
                ),
              ),
            ),
          ),
          const SizedBox(height: 18),

          if (usageAsync.hasError) ...[
            NoticeBanner(
              message: s.t(
                'Pemakaian hari ini belum bisa dibaca. Data lama tetap aman.',
                'Today\'s usage could not be read. Earlier data is safe.',
              ),
              actionLabel: s.t('Coba lagi', 'Retry'),
              onAction: () => ref.read(usageProvider.notifier).refresh(),
            ),
            const SizedBox(height: 14),
          ],
          if (usage != null && usage.source == UsageSource.sample) ...[
            NoticeBanner(
              message: s.t(
                'Masih data contoh. Beri akses pemakaian supaya angka dan HP ${pet.label} sesuai pemakaian nyata.',
                'Still sample data. Grant usage access so ${pet.label} reflects your real usage.',
              ),
              actionLabel: s.t('Aktifkan', 'Enable'),
              onAction: () => requestUsageAccess(context, ref),
            ),
            const SizedBox(height: 14),
          ],
          if (usage == null &&
              !usageAsync.isLoading &&
              !usageAsync.hasError &&
              game.collectionEnabled) ...[
            NoticeBanner(
              message: s.t(
                'Akses pemakaian belum aktif. Angka dan HP ${pet.label} belum bisa dibaca.',
                'Usage access is not active. Numbers and ${pet.label}\'s HP cannot be read yet.',
              ),
              actionLabel: s.t('Aktifkan', 'Enable'),
              onAction: () => requestUsageAccess(context, ref),
            ),
            const SizedBox(height: 14),
          ],
          if (realUsage && (noTrackedApps || needsScrollAccess)) ...[
            NoticeBanner(
              message: noTrackedApps
                  ? (needsScrollAccess
                        ? s.t(
                            'Belum ada pemakaian app lain hari ini. Pelacak scroll juga belum aktif.',
                            'No other app usage recorded today. The scroll tracker is off too.',
                          )
                        : s.t(
                            'Belum ada pemakaian app lain hari ini. Buka app sebentar, lalu tarik untuk menyegarkan.',
                            'No other app usage recorded today. Open another app, then pull to refresh.',
                          ))
                  : s.t(
                      'Pelacak scroll belum aktif. Hit scroll butuh izin Aksesibilitas.',
                      'The scroll tracker is off. Scroll hits need Accessibility access.',
                    ),
              actionLabel: needsScrollAccess
                  ? s.t('Aktifkan pelacak', 'Enable tracker')
                  : s.t('Segarkan', 'Refresh'),
              onAction: needsScrollAccess
                  ? () => requestAccessibility(context, ref)
                  : () => ref.read(usageProvider.notifier).refresh(),
            ),
            const SizedBox(height: 14),
          ],

          // 8-9. Bar HP lebar dan bar XP ramping
          TokenCard(
            child: Column(
              children: [
                _BarLabel(left: 'HP', right: hpKnown ? '$hp/100' : '—/100'),
                const SizedBox(height: 6),
                StatBar(
                  fraction: hpKnown ? hp / 100 : 0,
                  color: hpKnown ? hpColor : t.muted.withValues(alpha: 0.35),
                  height: 24,
                ),
                const SizedBox(height: 14),
                _BarLabel(
                  left: s.t(
                    'XP, menuju Lv. ${game.level + 1}',
                    'XP, toward Lv. ${game.level + 1}',
                  ),
                  right:
                      '${game.xp}/$kXpPerLevel XP  ${(game.xp * 100 / kXpPerLevel).round()}%',
                  small: true,
                ),
                const SizedBox(height: 6),
                StatBar(
                  fraction: game.xp / kXpPerLevel,
                  color: t.secondary,
                  height: 12,
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),

          // 10. Tiga stat chip sejajar
          StatRow(usage: usage),
          const SizedBox(height: 14),
          const WeeklyGoalCard(),
          const SizedBox(height: 14),

          // Peringatan HP kritis tampil juga di Beranda, bukan hanya overlay.
          if (mood == Mood.kritis && !game.isResting) ...[
            NoticeBanner(
              message: s.t(
                'HP ${pet.label} kritis. Istirahatkan HP sebentar agar ${pet.label} pulih.',
                '${pet.label}\'s HP is critical. Rest your phone for a moment so ${pet.label} recovers.',
              ),
            ),
            const SizedBox(height: 14),
          ],

          // Misi hari ini: tombol cepat memulai satu misi yang belum selesai.
          _TodayMissionCard(game: game, s: s),

          // 11. Aksi utama hanya saat Kritis
          if (mood == Mood.kritis && !game.isResting) ...[
            const SizedBox(height: 16),
            TokenButton(
              label: s.t('Istirahatkan HP', 'Rest your phone'),
              icon: Icons.bedtime_rounded,
              color: t.hpCritical,
              onPressed: () => startRest(context, ref),
            ),
          ],
          if (game.isResting) ...[
            const SizedBox(height: 16),
            TokenButton(
              label: s.t('Lihat sesi istirahat', 'View rest session'),
              icon: Icons.bedtime_rounded,
              onPressed: () => startRest(context, ref),
            ),
          ],
        ],
      ),
    );
  }
}

class _StreakBadge extends ConsumerWidget {
  const _StreakBadge({required this.days});

  final int days;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final s = ref.watch(l10nProvider);
    return Container(
      constraints: const BoxConstraints(minHeight: 44),
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: ShapeDecoration(
        color: t.surface,
        shape: t.shape(radiusOverride: t.notched ? 4 : (t.radius > 0 ? 14 : 0)),
        shadows: t.shadows,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.local_fire_department_rounded, color: t.hpTired, size: 22),
          const SizedBox(width: 6),
          Text('$days', style: t.number(20)),
          const SizedBox(width: 4),
          Text(
            s.t('hari', days == 1 ? 'day' : 'days'),
            style: t.body(12, color: t.muted),
          ),
        ],
      ),
    );
  }
}

class _BarLabel extends ConsumerWidget {
  const _BarLabel({
    required this.left,
    required this.right,
    this.small = false,
  });

  final String left;
  final String right;
  final bool small;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Flexible(
          child: Text(
            left,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: t.body(small ? 12 : 14, weight: FontWeight.w800),
          ),
        ),
        Text(right, style: t.number(small ? 12 : 15)),
      ],
    );
  }
}

/// Tiga chip statistik dengan tinggi seragam.
///
/// Dipisah dari [HomeScreen] agar bisa diuji: `CrossAxisAlignment.stretch`
/// di dalam `ListView` menerima tinggi tak terbatas, sehingga Row wajib
/// dibungkus [IntrinsicHeight]. Tanpa itu tinggi menjadi tak hingga
/// (di release tanpa assert), kartu tidak terpaint dan Beranda bisa
/// di-scroll tanpa batas.
class StatRow extends ConsumerWidget {
  const StatRow({super.key, required this.usage});

  final DailyUsage? usage;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final s = ref.watch(l10nProvider);
    final u = usage;
    final top = u?.topApp;

    final delta = (u != null && u.baselineMinutes > 0)
        ? s.delta(u.deltaMinutes)
        : '';

    final scrollSub = u == null
        ? ''
        : (u.accessibilityEnabled || u.source == UsageSource.sample
              ? s.t('hari ini', 'today')
              : s.t('pelacak belum aktif', 'tracker not active'));

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            flex: 11,
            child: _Chip(
              title: s.t('Total waktu', 'Total time'),
              value: u == null
                  ? '-'
                  : s.duration(u.totalMinutes, seconds: u.totalSeconds),
              sub: delta,
            ),
          ),
          SizedBox(width: t.notched ? 8 : 10),
          Expanded(
            flex: 10,
            child: _Chip(
              title: s.t('App teratas', 'Top app'),
              value: top == null
                  ? '-'
                  : s.duration(top.minutes, seconds: top.seconds),
              sub: top?.label ?? '',
            ),
          ),
          SizedBox(width: t.notched ? 8 : 10),
          Expanded(
            flex: 9,
            child: _Chip(
              title: s.t('Hit scroll', 'Scroll hits'),
              value: u == null ? '-' : '${u.totalScrollHits}',
              sub: scrollSub,
            ),
          ),
        ],
      ),
    );
  }
}

class _Chip extends ConsumerWidget {
  const _Chip({required this.title, required this.value, required this.sub});

  final String title;
  final String value;
  final String sub;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    return TokenCard(
      padding: const EdgeInsets.fromLTRB(10, 10, 10, 10),
      radius: t.notched ? null : (t.radius > 0 ? t.radius.clamp(6, 16) : 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: t.body(11, weight: FontWeight.w800, color: t.muted),
          ),
          const SizedBox(height: 6),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(value, style: t.number(22)),
          ),
          const SizedBox(height: 4),
          Text(
            sub,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: t.body(10, color: t.muted),
          ),
        ],
      ),
    );
  }
}

/// Satu misi hari ini yang belum selesai, dengan tombol cepat (prd Bab 9.1).
class _TodayMissionCard extends ConsumerWidget {
  const _TodayMissionCard({required this.game, required this.s});

  final GameState game;
  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final petName = game.petFamily?.label ?? 'Momo';
    final remaining = kMissions
        .where((m) => !game.doneToday.contains(m.id))
        .toList();

    if (remaining.isEmpty) {
      return TokenCard(
        color: t.tint(t.hpHealthy, 0.14),
        child: Row(
          children: [
            Icon(Icons.verified_rounded, color: t.hpHealthy, size: 20),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                s.t(
                  'Semua misi hari ini selesai. $petName senang!',
                  'All of today\'s missions are done. $petName is happy!',
                ),
                style: t.body(13, weight: FontWeight.w700),
              ),
            ),
          ],
        ),
      );
    }

    final mission = remaining.first;
    return TokenCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.flag_rounded, size: 18, color: t.ink),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  s.t('Misi hari ini', 'Today\'s mission'),
                  style: t.body(12, weight: FontWeight.w800, color: t.muted),
                ),
              ),
              StatusPill(
                label: s.t(
                  '${remaining.length} tersisa',
                  '${remaining.length} left',
                ),
                color: t.ink.withValues(alpha: 0.08),
                textColor: t.ink,
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(s.missionTitle(mission), style: t.heading(16)),
          Text(s.missionHint(mission), style: t.body(11, color: t.muted)),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 6,
            children: [
              StatusPill(label: '+${mission.bankReward}m', color: t.secondary),
              StatusPill(label: '+${mission.xp} XP', color: t.primary),
              StatusPill(label: '+${mission.hp} HP', color: t.hpHealthy),
            ],
          ),
          const SizedBox(height: 12),
          TokenButton(
            label: s.t('Mulai misi', 'Start mission'),
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
