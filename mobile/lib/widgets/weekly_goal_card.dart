import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/l10n/l10n.dart';
import '../core/models/duel_snapshot.dart';
import '../core/state/app_state.dart';
import '../core/weekly_goal.dart';
import 'ui.dart';

/// Target mingguan 5 dari 7 hari seimbang (prd Bab 6). Dipakai di Beranda
/// dan Rekap supaya target yang sama tidak ditulis dua kali.
class WeeklyGoalCard extends ConsumerWidget {
  const WeeklyGoalCard({super.key, this.compact = false});

  final bool compact;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final s = ref.watch(l10nProvider);
    final async = ref.watch(historyProvider(7));
    final collectionOn = ref.watch(
      gameProvider.select((g) => g.collectionEnabled),
    );
    final now = DateTime.now();
    final progress = weeklyProgressFrom(
      async.asData?.value ?? const [],
      now: now,
    );
    // Never show "0/5" while history is still loading, failed, or collection
    // is off: those are unknown states, not honest zero progress.
    final loading = async.isLoading && !async.hasValue;
    final unavailable = !collectionOn || async.hasError;
    final pillLabel = unavailable
        ? '—'
        : loading
        ? '…'
        : progress.achieved
        ? s.t('Tercapai', 'Reached')
        : '${progress.balancedDays}/${progress.target}';
    final monday = DuelSnapshot.monday(now);
    final sunday = DateTime(monday.year, monday.month, monday.day + 6);
    String date(DateTime value) => '${value.day}/${value.month}/${value.year}';

    return TokenCard(
      padding: EdgeInsets.all(compact ? 12 : 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.calendar_month_rounded, size: 18, color: t.ink),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  s.t('Target mingguan', 'Weekly target'),
                  style: t.body(12, weight: FontWeight.w800, color: t.muted),
                ),
              ),
              StatusPill(
                label: pillLabel,
                color: unavailable
                    ? t.ink.withValues(alpha: 0.12)
                    : progress.achieved
                    ? t.hpHealthy
                    : t.primary,
                textColor: unavailable ? t.muted : null,
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: List.generate(progress.target, (i) {
              final filled = i < progress.balancedDays;
              return Container(
                width: compact ? 12 : 16,
                height: compact ? 12 : 16,
                margin: const EdgeInsets.only(right: 6),
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: filled ? t.hpHealthy : t.ink.withValues(alpha: 0.12),
                ),
              );
            }),
          ),
          const SizedBox(height: 8),
          Text(
            s.t(
              'Senin–Minggu · ${date(monday)} – ${date(sunday)}',
              'Monday–Sunday · ${date(monday)} – ${date(sunday)}',
            ),
            style: t.body(11, color: t.muted),
          ),
          const SizedBox(height: 4),
          Text(
            !collectionOn
                ? s.t(
                    'Pengumpulan nonaktif. Aktifkan lagi di Profil → Privasi.',
                    'Collection is off. Re-enable it in Profile → Privacy.',
                  )
                : async.hasError
                ? s.t(
                    'Riwayat gagal dimuat. Tarik untuk mencoba lagi.',
                    'History failed to load. Pull to retry.',
                  )
                : loading
                ? s.t('Memuat riwayat...', 'Loading history...')
                : progress.achieved
                ? s.t(
                    'Target tercapai: ${progress.balancedDays} hari seimbang minggu ini.',
                    'Target reached: ${progress.balancedDays} balanced ${progress.balancedDays == 1 ? 'day' : 'days'} this week.',
                  )
                : s.t(
                    '${progress.balancedDays} dari ${progress.target} hari seimbang. '
                        '${progress.trackedDays} hari tercatat.',
                    '${progress.balancedDays} of ${progress.target} balanced days. '
                        '${progress.trackedDays} ${progress.trackedDays == 1 ? 'day' : 'days'} recorded.',
                  ),
            style: t.body(11, color: t.muted),
          ),
          const SizedBox(height: 4),
          Text(
            s.t(
              'Seimbang berarti di bawah baseline harian. Hari tanpa baseline tidak dihitung. Hari ini belum selesai.',
              'Balanced means under your daily baseline. Days without a baseline do not count. Today is not over yet.',
            ),
            style: t.body(10, color: t.muted),
          ),
        ],
      ),
    );
  }
}
