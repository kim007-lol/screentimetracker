import 'dart:async';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../../core/l10n/l10n.dart';
import '../../core/models/companion.dart';
import '../../core/models/pet.dart';
import '../../core/models/usage.dart';
import '../../core/services/history_service.dart';
import '../../core/state/app_state.dart';
import '../../core/theme/app_tokens.dart';
import '../../widgets/permission_flow.dart';
import '../../widgets/ui.dart';
import '../../widgets/weekly_goal_card.dart';
import 'recap_period.dart';

/// Sample data can disappear without a permission transition (e.g. a native
/// transient failure). Always re-read recap sources after the settings trip.
Future<void> _enableUsageAccess(BuildContext context, WidgetRef ref) async {
  await requestUsageAccess(context, ref);
  if (!context.mounted) return;
  ref.invalidate(usageRangeProvider);
  ref.invalidate(recapNightUsageProvider);
  ref.invalidate(permissionStatusProvider);
  unawaited(ref.read(usageProvider.notifier).refresh());
}

final recapNightUsageProvider = FutureProvider.autoDispose.family<int?, int>((
  ref,
  days,
) async {
  try {
    return nightMinutes(
      await ref.watch(usageServiceProvider).nightUsage(days: days),
      days: days,
    );
  } catch (_) {
    return null;
  }
});

/// Tab Rekap: rekap semua app, bukan hanya scroll (prd Bab 9.2).
class RekapScreen extends ConsumerStatefulWidget {
  const RekapScreen({super.key});

  @override
  ConsumerState<RekapScreen> createState() => _RekapScreenState();
}

class _RekapScreenState extends ConsumerState<RekapScreen> {
  static const _periods = [1, 7, 30];
  int _period = 1;
  ProviderSubscription<AsyncValue<PermissionStatus>>? _permissionSub;

  @override
  void initState() {
    super.initState();
    // Returning from Android Settings does not rebuild this tab by itself.
    // When usage access flips on, drop every cached recap read.
    _permissionSub = ref.listenManual(permissionStatusProvider, (
      previous,
      next,
    ) {
      if (previous == null) return;
      final before = previous.asData?.value.usage ?? false;
      final after = next.asData?.value.usage ?? false;
      if (!before && after) {
        ref.invalidate(usageRangeProvider);
        ref.invalidate(recapNightUsageProvider);
        ref.invalidate(historyProvider);
        unawaited(ref.read(usageProvider.notifier).refresh());
      }
    });
  }

  @override
  void dispose() {
    _permissionSub?.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tokensProvider);
    final s = ref.watch(l10nProvider);
    final async = ref.watch(usageRangeProvider(_period));

    return RefreshIndicator(
      color: t.ink,
      backgroundColor: t.surface,
      onRefresh: () async {
        ref.invalidate(usageRangeProvider);
        ref.invalidate(recapNightUsageProvider);
        await ref.read(usageProvider.notifier).refresh();
      },
      child: ListView(
        padding: const EdgeInsets.fromLTRB(18, 14, 18, 28),
        children: [
          Text(s.t('Rekap', 'Recap'), style: t.heading(28)),
          const SizedBox(height: 4),
          Text(
            s.t(
              'Semua aplikasi, dibandingkan dengan kebiasaanmu sendiri.',
              'Every app, compared with your own baseline.',
            ),
            style: t.body(13, color: t.muted),
          ),
          const SizedBox(height: 14),
          _PeriodSelector(
            periods: _periods,
            value: _period,
            s: s,
            onChanged: (v) => setState(() => _period = v),
          ),
          const SizedBox(height: 16),
          async.when(
            loading: () => const Padding(
              padding: EdgeInsets.symmetric(vertical: 48),
              child: Center(child: CircularProgressIndicator()),
            ),
            error: (_, _) => NoticeBanner(
              message: s.t('Gagal memuat rekap.', 'Failed to load the recap.'),
              actionLabel: s.t('Coba lagi', 'Retry'),
              onAction: () => ref.invalidate(usageRangeProvider),
            ),
            data: (usage) => usage.source == UsageSource.unavailable
                ? NoticeBanner(
                    message: s.t(
                      'Data rekap belum bisa dibaca dari Android.',
                      'The recap could not be read from Android.',
                    ),
                    actionLabel: s.t('Coba lagi', 'Retry'),
                    onAction: () {
                      ref.invalidate(usageRangeProvider);
                      ref.invalidate(recapNightUsageProvider);
                    },
                  )
                : _RekapBody(usage: usage, period: _period, s: s),
          ),
        ],
      ),
    );
  }
}

class _PeriodSelector extends ConsumerWidget {
  const _PeriodSelector({
    required this.periods,
    required this.value,
    required this.s,
    required this.onChanged,
  });

  final List<int> periods;
  final int value;
  final L10n s;
  final ValueChanged<int> onChanged;

  String _label(int days) => switch (days) {
    1 => s.t('Harian', 'Daily'),
    7 => s.t('7 hari', '7 days'),
    _ => s.t('30 hari', '30 days'),
  };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    return Row(
      children: periods.map((days) {
        final active = days == value;
        return Expanded(
          child: Padding(
            padding: EdgeInsets.only(right: days == periods.last ? 0 : 8),
            child: GestureDetector(
              onTap: () => onChanged(days),
              child: Container(
                constraints: const BoxConstraints(minHeight: 48),
                alignment: Alignment.center,
                decoration: ShapeDecoration(
                  color: active ? t.primary : t.surface,
                  shape: t.shape(
                    radiusOverride: t.notched ? 4 : (t.radius > 0 ? 12 : 0),
                  ),
                  shadows: active ? t.shadows : const [],
                ),
                child: Text(
                  _label(days),
                  style: t.body(13, weight: FontWeight.w800),
                ),
              ),
            ),
          ),
        );
      }).toList(),
    );
  }
}

class _RekapBody extends ConsumerWidget {
  const _RekapBody({
    required this.usage,
    required this.period,
    required this.s,
  });

  final DailyUsage usage;
  final int period;
  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final byCategory = usage.minutesByCategory;
    final total = usage.totalMinutes;
    final top = usage.topApp;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (usage.source == UsageSource.sample)
          Padding(
            padding: const EdgeInsets.only(bottom: 14),
            child: NoticeBanner(
              message: s.t(
                'Masih data contoh. Beri akses pemakaian supaya rekap memakai data HP-mu.',
                'Still sample data. Grant usage access to recap your real phone.',
              ),
              actionLabel: s.t('Aktifkan', 'Enable'),
              onAction: () => _enableUsageAccess(context, ref),
            ),
          ),
        TokenCard(
          child: Column(
            children: [
              SizedBox(
                height: 190,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    if (total == 0 && usage.totalSeconds == 0)
                      Text(
                        s.t('Belum ada data', 'No data yet'),
                        style: t.body(13, color: t.muted),
                      )
                    else
                      PieChart(
                        PieChartData(
                          centerSpaceRadius: 56,
                          sectionsSpace: 3,
                          startDegreeOffset: -90,
                          sections: [
                            for (final entry in byCategory.entries)
                              if (entry.value > 0)
                                PieChartSectionData(
                                  value: entry.value.toDouble(),
                                  color: _categoryColor(t, entry.key),
                                  radius: 26,
                                  showTitle: false,
                                ),
                          ],
                        ),
                      ),
                    Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          s.duration(total, seconds: usage.totalSeconds),
                          style: t.number(26),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          s.t('total layar', 'screen time'),
                          style: t.body(11, color: t.muted),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 8),
              Text(
                usage.baselineMinutes > 0
                    ? s.delta(usage.deltaMinutes)
                    : s.t('Baseline belum tersedia', 'No baseline yet'),
                style: t.body(12, color: t.muted),
              ),
              if (usage.baselineMinutes > 0) ...[
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    StatusPill(
                      label: usage.deltaMinutes < 0
                          ? s.t('Lebih hemat', 'Below usual')
                          : usage.deltaMinutes == 0
                          ? s.t('Sama seperti biasa', 'Same as usual')
                          : s.t('Lebih tinggi', 'Above usual'),
                      color: usage.deltaMinutes <= 0 ? t.hpHealthy : t.hpTired,
                    ),
                    Text(
                      '${s.t('Baseline', 'Baseline')} ${s.duration(usage.baselineMinutes)}',
                      style: t.body(11, color: t.muted),
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 18),
        _NightUsageCard(
          days: period,
          sample: usage.source == UsageSource.sample,
          s: s,
        ),
        const SizedBox(height: 18),
        const WeeklyGoalCard(compact: true),
        if (period > 1) ...[
          const SizedBox(height: 18),
          SectionTitle(s.t('Tren harian', 'Daily trend')),
          _TrendCard(days: period, s: s),
        ],
        const SizedBox(height: 18),
        SectionTitle(s.t('Kategori', 'Categories')),
        TokenCard(
          child: Column(
            children: [
              for (final entry
                  in byCategory.entries.toList()
                    ..sort((a, b) => b.value.compareTo(a.value)))
                _CategoryRow(
                  category: entry.key,
                  minutes: entry.value,
                  total: total,
                  s: s,
                ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        SectionTitle(
          s.t('Peringkat aplikasi', 'App ranking'),
          trailing: Text(
            s.t(
              '${usage.apps.length} app',
              '${usage.apps.length} ${usage.apps.length == 1 ? 'app' : 'apps'}',
            ),
            style: t.body(11, color: t.muted),
          ),
        ),
        TokenCard(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          child: Column(
            children: [
              for (var i = 0; i < usage.apps.length && i < 10; i++)
                _AppRow(index: i, app: usage.apps[i], s: s),
            ],
          ),
        ),
        const SizedBox(height: 14),
        _ShareRow(
          usage: usage,
          top: top,
          period: RecapPeriod(days: period),
          s: s,
        ),
        const SizedBox(height: 14),
        TokenCard(
          elevated: false,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.info_outline_rounded, size: 18, color: t.muted),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  s.t(
                    'Sebagian app hanya memberi nama paket. Nama ditampilkan apa adanya, '
                        'tanpa ditebak. Scroll ke atas menambah hitungan scroll dan replay.',
                    'Some apps expose only their package name. It is shown as-is, '
                        'with no guessing. Scrolling up adds to both the scroll and '
                        'replay counts.',
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

Color _categoryColor(AppTokens t, UsageCategory category) => switch (category) {
  UsageCategory.sosial => t.hpCritical.withValues(alpha: 0.85),
  UsageCategory.hiburan => t.hpTired,
  UsageCategory.produktivitas => t.secondary,
  UsageCategory.kerja => t.primary,
  UsageCategory.belajar => t.hpHealthy,
  UsageCategory.lainnya => t.ink.withValues(alpha: 0.35),
};

class _CategoryRow extends ConsumerWidget {
  const _CategoryRow({
    required this.category,
    required this.minutes,
    required this.total,
    required this.s,
  });

  final UsageCategory category;
  final int minutes;
  final int total;
  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final fraction = total == 0 ? 0.0 : minutes / total;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Container(
            width: 12,
            height: 12,
            decoration: BoxDecoration(
              color: _categoryColor(t, category),
              borderRadius: BorderRadius.circular(3),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      s.categoryLabel(category),
                      style: t.body(13, weight: FontWeight.w700),
                    ),
                    Text(s.duration(minutes), style: t.number(12)),
                  ],
                ),
                const SizedBox(height: 5),
                ClipRRect(
                  borderRadius: BorderRadius.circular(99),
                  child: LinearProgressIndicator(
                    value: fraction,
                    minHeight: 7,
                    backgroundColor: t.ink.withValues(alpha: 0.08),
                    valueColor: AlwaysStoppedAnimation(
                      _categoryColor(t, category),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          SizedBox(
            width: 38,
            child: Text(
              '${(fraction * 100).round()}%',
              textAlign: TextAlign.right,
              style: t.number(11, color: t.muted),
            ),
          ),
        ],
      ),
    );
  }
}

class _AppRow extends ConsumerWidget {
  const _AppRow({required this.index, required this.app, required this.s});

  final int index;
  final AppUsage app;
  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final packageOnly = app.label == app.packageName;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 9),
      child: Row(
        children: [
          Container(
            width: 26,
            height: 26,
            alignment: Alignment.center,
            decoration: ShapeDecoration(
              color: index == 0 ? t.primary : t.ink.withValues(alpha: 0.06),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(t.notched ? 3 : 8),
              ),
            ),
            child: Text('${index + 1}', style: t.number(12)),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        app.label,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: t.body(14, weight: FontWeight.w700),
                      ),
                    ),
                    if (packageOnly) ...[
                      const SizedBox(width: 4),
                      Tooltip(
                        message: s.t(
                          'Nama ini dibaca langsung dari paket aplikasi.',
                          'This name comes straight from the package.',
                        ),
                        child: Icon(
                          Icons.help_outline_rounded,
                          size: 13,
                          color: t.muted,
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  [
                    s.categoryLabel(app.category),
                    s.opens(app.opens),
                    s.t(
                      'sesi ${app.longestSessionMinutes}m',
                      'longest ${app.longestSessionMinutes}m',
                    ),
                    if (app.scrollHits > 0) s.hits(app.scrollHits),
                    if (app.replays > 0) s.replays(app.replays),
                  ].join(' · '),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: t.body(11, color: t.muted),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Text(
            s.duration(app.minutes, seconds: app.seconds),
            style: t.number(14),
          ),
        ],
      ),
    );
  }
}

class _NightUsageCard extends ConsumerWidget {
  const _NightUsageCard({
    required this.days,
    required this.sample,
    required this.s,
  });
  final int days;
  final bool sample;
  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final async = sample
        ? const AsyncData<int?>(null)
        : ref.watch(recapNightUsageProvider(days));
    final minutes = async.asData?.value;
    return TokenCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            s.t(
              'Pemakaian malam · 22:00–06:00',
              'Late-night usage · 22:00–06:00',
            ),
            style: t.heading(15),
          ),
          const SizedBox(height: 6),
          Text(
            RecapPeriod(days: days).dateText,
            style: t.body(11, color: t.muted),
          ),
          const SizedBox(height: 6),
          Text(
            async.isLoading
                ? s.t('Memuat...', 'Loading...')
                : minutes == null
                ? s.t('Data malam tidak tersedia', 'Night usage unavailable')
                : s.t(
                    '${s.duration(minutes)} tercatat pada malam hari',
                    '${s.duration(minutes)} recorded at night',
                  ),
            style: t.body(13, weight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          Text(
            minutes == null
                ? s.t(
                    'Tidak ada angka perkiraan atau contoh. Data jam pemakaian dari perangkat diperlukan.',
                    'No estimates or sample numbers. Device usage event data is required.',
                  )
                : s.t(
                    'Total pukul 00–06 dan 22–24 pada tanggal di atas; hari ini masih berjalan.',
                    'Total for 00–06 and 22–24 on these dates; today is still in progress.',
                  ),
            style: t.body(11, color: t.muted),
          ),
        ],
      ),
    );
  }
}

class _ShareRow extends ConsumerWidget {
  const _ShareRow({
    required this.usage,
    required this.top,
    required this.period,
    required this.s,
  });

  final DailyUsage usage;
  final AppUsage? top;
  final RecapPeriod period;
  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    return TokenCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 32,
                height: 32,
                decoration: ShapeDecoration(
                  color: t.primary,
                  shape: t.shape(
                    radiusOverride: t.notched ? 2 : 9,
                    outlined: false,
                  ),
                ),
                child: Icon(Icons.image_rounded, size: 17, color: t.onPrimary),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  s.t('Kartu Rekap', 'Recap Card'),
                  style: t.heading(16),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            s.t(
              'Pratinjau ringkasan periode pilihanmu, termasuk nama app teratas, sebelum dibagikan.',
              'Preview your selected period summary, including the top app name, before sharing.',
            ),
            style: t.body(12, color: t.muted),
          ),
          const SizedBox(height: 10),
          TokenButton(
            label: s.t('Lihat kartu rekap', 'View recap card'),
            icon: Icons.ios_share_rounded,
            onPressed: () => _openCard(context, ref),
          ),
        ],
      ),
    );
  }

  void _openCard(BuildContext context, WidgetRef ref) {
    showDialog<void>(
      context: context,
      builder: (_) =>
          _RecapCardDialog(usage: usage, top: top, period: period, s: s),
    );
  }
}

class _RecapCardDialog extends ConsumerStatefulWidget {
  const _RecapCardDialog({
    required this.usage,
    required this.top,
    required this.period,
    required this.s,
  });

  final DailyUsage usage;
  final AppUsage? top;
  final RecapPeriod period;
  final L10n s;

  @override
  ConsumerState<_RecapCardDialog> createState() => _RecapCardDialogState();
}

class _RecapCardDialogState extends ConsumerState<_RecapCardDialog> {
  final GlobalKey _cardKey = GlobalKey();
  bool _sharing = false;

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tokensProvider);
    final s = widget.s;
    final usage = widget.usage;
    final top = widget.top;
    final petName = ref.watch(
      gameProvider.select((g) => (g.petFamily ?? PetFamily.momo).label),
    );
    final heading = widget.period.shareHeading(
      english: s.isEnglish,
      sample: usage.source == UsageSource.sample,
    );

    final summary = [
      '$petName · $heading',
      '${s.duration(usage.totalMinutes, seconds: usage.totalSeconds)} ${s.t('waktu layar', 'screen time')}',
      '${s.t('App teratas', 'Top app')}: ${top?.label ?? '-'} (${top == null ? '-' : s.duration(top.minutes, seconds: top.seconds)})',
      '${s.t('Hit scroll', 'Scroll hits')}: ${usage.totalScrollHits}'
          ' · ${s.t('replay', 'replays')}: ${usage.totalReplays}',
    ].join('\n');

    return Dialog(
      backgroundColor: Colors.transparent,
      insetPadding: const EdgeInsets.all(20),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            RepaintBoundary(
              key: _cardKey,
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(20),
                decoration: ShapeDecoration(
                  color: t.surface,
                  shape: t.shape(radiusOverride: t.notched ? 0 : t.radius),
                  shadows: t.shadows,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('MOMO', style: t.heading(12, color: t.muted)),
                    const SizedBox(height: 10),
                    for (final line in heading.split('\n'))
                      Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Text(line, style: t.body(13, color: t.muted)),
                      ),
                    Text(
                      s.t('Waktu layar', 'Screen time'),
                      style: t.body(13, color: t.muted),
                    ),
                    Text(
                      s.duration(
                        usage.totalMinutes,
                        seconds: usage.totalSeconds,
                      ),
                      style: t.number(40),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      usage.baselineMinutes > 0
                          ? s.delta(usage.deltaMinutes)
                          : s.t('Baseline belum tersedia', 'No baseline yet'),
                      style: t.body(12, color: t.muted),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Expanded(
                          child: _MiniStat(
                            label: s.t('App teratas', 'Top app'),
                            value: top?.label ?? '-',
                            sub: top == null
                                ? ''
                                : s.duration(top.minutes, seconds: top.seconds),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: _MiniStat(
                            label: s.t('Hit scroll', 'Scroll hits'),
                            value: '${usage.totalScrollHits}',
                            sub: s.replays(usage.totalReplays),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 14),
            TokenButton(
              label: _sharing
                  ? s.t('Menyiapkan gambar...', 'Preparing image...')
                  : s.t('Bagikan gambar', 'Share image'),
              icon: Icons.ios_share_rounded,
              onPressed: _sharing ? null : () => _shareImage(summary),
            ),
            const SizedBox(height: 8),
            TokenButton(
              label: s.t('Salin ringkasan', 'Copy summary'),
              icon: Icons.copy_rounded,
              onPressed: () async {
                final messenger = ScaffoldMessenger.of(context);
                await Clipboard.setData(ClipboardData(text: summary));
                if (!mounted) return;
                messenger.showSnackBar(
                  SnackBar(
                    content: Text(s.t('Ringkasan disalin.', 'Summary copied.')),
                  ),
                );
              },
            ),
            const SizedBox(height: 8),
            TokenButton(
              label: s.t('Tutup', 'Close'),
              filled: false,
              onPressed: () => Navigator.of(context).pop(),
            ),
          ],
        ),
      ),
    );
  }

  static const _exportPrefix = 'momo-rekap-';

  /// Old exports are pruned on the next share instead of deleting the file the
  /// moment the chooser closes: the receiving app may still be reading it.
  Future<void> _pruneOldCards(Directory dir) async {
    try {
      await for (final entity in dir.list()) {
        if (entity is! File ||
            !p.basename(entity.path).startsWith(_exportPrefix)) {
          continue;
        }
        final stat = await entity.stat();
        if (DateTime.now().difference(stat.modified) >
            const Duration(hours: 1)) {
          await entity.delete();
        }
      }
    } on FileSystemException {
      // Cache cleanup is best-effort; sharing must still work.
    }
  }

  Future<void> _shareImage(String summary) async {
    setState(() => _sharing = true);
    ui.Image? image;
    try {
      final boundary =
          _cardKey.currentContext?.findRenderObject() as RenderRepaintBoundary?;
      if (boundary == null) return;
      image = await boundary.toImage(pixelRatio: 3);
      final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
      if (bytes == null || !mounted) return;
      final dir = await getTemporaryDirectory();
      await _pruneOldCards(dir);
      final file = File(
        '${dir.path}/$_exportPrefix${DateTime.now().microsecondsSinceEpoch}.png',
      );
      await file.writeAsBytes(
        bytes.buffer.asUint8List(bytes.offsetInBytes, bytes.lengthInBytes),
        flush: true,
      );
      if (!mounted) return;
      final box = context.findRenderObject() as RenderBox?;
      await Share.shareXFiles(
        [XFile(file.path)],
        text: summary,
        sharePositionOrigin: box == null
            ? null
            : box.localToGlobal(Offset.zero) & box.size,
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            widget.s.t(
              'Gagal membuat gambar. Coba lagi.',
              'Could not create the image. Try again.',
            ),
          ),
        ),
      );
    } finally {
      image?.dispose();
      if (mounted) setState(() => _sharing = false);
    }
  }
}

class _MiniStat extends ConsumerWidget {
  const _MiniStat({
    required this.label,
    required this.value,
    required this.sub,
  });

  final String label;
  final String value;
  final String sub;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: ShapeDecoration(
        color: t.surface,
        shape: t.shape(radiusOverride: t.notched ? 3 : (t.radius > 0 ? 12 : 0)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: t.body(10, color: t.muted, weight: FontWeight.w800),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: t.heading(15),
          ),
          Text(sub, style: t.body(10, color: t.muted)),
        ],
      ),
    );
  }
}

/// Tren harian dari riwayat SQLite. Hijau bila seimbang dengan baseline hari itu.
class _TrendCard extends ConsumerWidget {
  const _TrendCard({required this.days, required this.s});

  final int days;
  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final async = ref.watch(historyProvider(days));
    final stats = async.asData?.value ?? const <DailyStat>[];

    if (stats.isEmpty) {
      return TokenCard(
        child: Text(
          s.t(
            'Riwayat harian mulai terkumpul setelah aplikasi dipakai. Tren muncul di sini.',
            'Daily history starts building as you use the app. The trend appears here.',
          ),
          style: t.body(12, color: t.muted),
        ),
      );
    }

    final chronological = stats.reversed.toList();
    var maxMinutes = 0;
    for (final stat in chronological) {
      if (stat.totalMinutes > maxMinutes) maxMinutes = stat.totalMinutes;
    }
    final maxY = (maxMinutes * 1.25).clamp(30, 100000).toDouble();
    final barWidth = chronological.length <= 7 ? 18.0 : 6.0;

    return TokenCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            s.t(
              '${chronological.length} hari tercatat dari $days hari terakhir',
              '${chronological.length} ${chronological.length == 1 ? 'day' : 'days'} recorded of the last $days',
            ),
            style: t.body(11, color: t.muted),
          ),
          const SizedBox(height: 10),
          SizedBox(
            height: 140,
            child: BarChart(
              BarChartData(
                maxY: maxY,
                minY: 0,
                alignment: BarChartAlignment.spaceAround,
                barTouchData: BarTouchData(enabled: false),
                titlesData: const FlTitlesData(show: false),
                borderData: FlBorderData(show: false),
                gridData: FlGridData(
                  show: true,
                  drawVerticalLine: false,
                  horizontalInterval: maxY / 4,
                  getDrawingHorizontalLine: (_) => FlLine(
                    color: t.ink.withValues(alpha: 0.08),
                    strokeWidth: 1,
                  ),
                ),
                barGroups: [
                  for (var i = 0; i < chronological.length; i++)
                    BarChartGroupData(
                      x: i,
                      barRods: [
                        BarChartRodData(
                          toY: chronological[i].totalMinutes.toDouble(),
                          width: barWidth,
                          // A day without a baseline cannot be called balanced
                          // or above baseline; keep it neutral instead of red.
                          color: chronological[i].baselineMinutes == 0
                              ? t.ink.withValues(alpha: 0.25)
                              : chronological[i].balanced
                              ? t.hpHealthy
                              : t.hpTired,
                          borderRadius: BorderRadius.circular(
                            t.notched ? 0 : 4,
                          ),
                        ),
                      ],
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 12,
            runSpacing: 4,
            children: [
              _legend(t, t.hpHealthy, s.t('Seimbang', 'Balanced')),
              _legend(t, t.hpTired, s.t('Di atas baseline', 'Above baseline')),
              _legend(
                t,
                t.ink.withValues(alpha: 0.25),
                s.t('Tanpa baseline', 'No baseline'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _legend(AppTokens t, Color color, String label) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(
        width: 10,
        height: 10,
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(3),
        ),
      ),
      const SizedBox(width: 5),
      Text(label, style: t.body(10, color: t.muted)),
    ],
  );
}
