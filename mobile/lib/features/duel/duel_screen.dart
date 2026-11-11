import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/l10n/l10n.dart';
import '../../core/models/duel_snapshot.dart';
import '../../core/state/app_state.dart';
import '../../core/state/duel_state.dart';
import '../../core/theme/app_tokens.dart';
import '../../core/weekly_goal.dart';
import '../../widgets/ui.dart';

/// Offline code exchange only: no accounts, automatic uploads, or verified scores.
class DuelScreen extends ConsumerStatefulWidget {
  const DuelScreen({super.key});

  @override
  ConsumerState<DuelScreen> createState() => _DuelScreenState();
}

class _DuelScreenState extends ConsumerState<DuelScreen> {
  static const _checkDayKey = 'duelCheckDay';
  late String _shownDay;
  Timer? _dayTimer;

  @override
  void initState() {
    super.initState();
    _shownDay = _dayKey();
    // The tab stays alive in an IndexedStack, so rebuild after midnight so the
    // daily check button is available again without restarting the app.
    _dayTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (!mounted) return;
      final today = _dayKey();
      if (today != _shownDay) setState(() => _shownDay = today);
    });
  }

  @override
  void dispose() {
    _dayTimer?.cancel();
    super.dispose();
  }

  String _dayKey() => DuelSnapshot.dayKey(DateTime.now());

  bool get _checkedToday =>
      ref.read(sharedPrefsProvider).getString(_checkDayKey) == _dayKey();

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tokensProvider);
    final s = ref.watch(l10nProvider);
    final history = ref.watch(historyProvider(14));
    final now = DateTime.now();
    final name = ref.watch(gameProvider.select((game) => game.userName));

    return RefreshIndicator(
      color: t.ink,
      backgroundColor: t.surface,
      onRefresh: () async {
        await ref.read(usageProvider.notifier).refresh();
        ref.invalidate(historyProvider);
      },
      child: ListView(
        padding: const EdgeInsets.fromLTRB(18, 14, 18, 28),
        children: [
          Text(s.t('Duel', 'Duel'), style: t.heading(28)),
          const SizedBox(height: 4),
          Text(
            s.t(
              'Minggu kalender yang sama, cakupan hari yang sama, baseline masing-masing.',
              'Same calendar week, same recorded-day coverage, your own baseline.',
            ),
            style: t.body(13, color: t.muted),
          ),
          const SizedBox(height: 14),
          NoticeBanner(
            message: s.t(
              'Duel teman tersedia lewat kode offline, maksimal 5 teman. Data dilaporkan sendiri dan bisa diubah; tidak diverifikasi server. Tidak ada pengiriman otomatis.',
              'Duel with up to 5 friends using offline codes. Scores are self-reported and editable, not server-verified. Nothing is sent automatically.',
            ),
          ),
          const SizedBox(height: 14),
          history.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (_, _) => NoticeBanner(
              message: s.t('Riwayat belum tersedia.', 'History unavailable.'),
              actionLabel: s.t('Coba lagi', 'Retry'),
              onAction: () => ref.invalidate(historyProvider),
            ),
            data: (records) {
              final mine = duelSnapshotFrom(
                records,
                name: DuelSnapshot.validName(name)
                    ? name.trim()
                    : s.t('Kamu', 'You'),
                now: now,
              );
              return Column(
                children: [
                  _LastWeekCard(
                    comparison: compareWeeks(records, now: now),
                    s: s,
                  ),
                  const SizedBox(height: 14),
                  _SelfDuelCard(mine: mine, s: s),
                  const SizedBox(height: 14),
                  _PeersCard(mine: mine, s: s),
                ],
              );
            },
          ),
          const SizedBox(height: 14),
          SectionTitle(s.t('Aturan duel', 'Duel rules')),
          _RulesCard(s: s),
          const SizedBox(height: 14),
          TokenButton(
            label: _checkedToday
                ? s.t('Skor sudah dicek hari ini', 'Score checked today')
                : s.t('Cek skor hari ini', 'Check today\'s score'),
            icon: Icons.emoji_events_rounded,
            onPressed: _checkedToday
                ? null
                : () {
                    ref
                        .read(sharedPrefsProvider)
                        .setString(_checkDayKey, _dayKey());
                    setState(() {});
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(
                          s.t(
                            'Sudah dicek. Data hari ini masih berjalan; tidak perlu membuka aplikasi berulang.',
                            'Checked. Today\'s data is still in progress; no need to keep reopening the app.',
                          ),
                        ),
                      ),
                    );
                  },
          ),
        ],
      ),
    );
  }
}

String _date(DateTime date) =>
    '${date.day.toString().padLeft(2, '0')}/'
    '${date.month.toString().padLeft(2, '0')}/${date.year}';

class _SelfDuelCard extends ConsumerWidget {
  const _SelfDuelCard({required this.mine, required this.s});
  final DuelSnapshot mine;
  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    return TokenCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            s.t('Kamu vs baseline sendiri', 'You vs your own baseline'),
            style: t.heading(17),
          ),
          const SizedBox(height: 8),
          Text(
            '${_date(DuelSnapshot.parseDay(mine.periodStart!)!)} – ${_date(mine.generatedAt)}',
            style: t.body(12, color: t.muted),
          ),
          const SizedBox(height: 8),
          Text(
            mine.days == 0
                ? s.t(
                    'Belum ada hari dengan baseline',
                    'No baseline-backed days yet',
                  )
                : s.t(
                    '${mine.balancedDays}/${mine.days} hari seimbang',
                    '${mine.balancedDays}/${mine.days} balanced ${mine.days == 1 ? 'day' : 'days'}',
                  ),
            style: t.heading(18),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: _Score(
                  label: s.t('Total tercatat', 'Recorded total'),
                  value: mine.days == 0 ? '—' : s.duration(mine.minutes),
                  sub: s.t(
                    '${mine.days} hari dengan baseline',
                    '${mine.days} baseline-backed ${mine.days == 1 ? 'day' : 'days'}',
                  ),
                  highlighted: true,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _Score(
                  label: s.t('Baseline hari tercatat', 'Recorded-day baseline'),
                  value: mine.days == 0
                      ? '—'
                      : s.duration(mine.baselineMinutes!),
                  sub: s.t(
                    'baseline tiap hari sendiri',
                    'each day\'s own baseline',
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            s.t(
              'Hanya riwayat perangkat dengan baseline tersedia. Hari tanpa baseline tidak diberi skor; hari ini belum selesai.',
              'Only device history with an available baseline. Days without a baseline are not scored; today is incomplete.',
            ),
            style: t.body(11, color: t.muted),
          ),
        ],
      ),
    );
  }
}

class _Score extends ConsumerWidget {
  const _Score({
    required this.label,
    required this.value,
    required this.sub,
    this.highlighted = false,
  });
  final String label;
  final String value;
  final String sub;
  final bool highlighted;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: ShapeDecoration(
        color: highlighted ? t.primary.withValues(alpha: 0.22) : t.surface,
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
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(value, style: t.number(22)),
          ),
          Text(sub, style: t.body(10, color: t.muted)),
        ],
      ),
    );
  }
}

class _LastWeekCard extends ConsumerWidget {
  const _LastWeekCard({required this.comparison, required this.s});
  final WeekComparison comparison;
  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final c = comparison;
    final comparable = c.comparable;
    return TokenCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            s.t('Minggu ini vs minggu lalu', 'This week vs last week'),
            style: t.heading(17),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: _Score(
                  label: s.t('Minggu ini', 'This week'),
                  value: c.thisWeekDays == 0
                      ? '—'
                      : s.duration(c.thisWeekMinutes),
                  sub:
                      '${_date(c.thisStart!)} – ${_date(c.thisEnd!)}\n${c.thisWeekDays} ${s.t('hari tercatat', c.thisWeekDays == 1 ? 'recorded day' : 'recorded days')}',
                  highlighted: true,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _Score(
                  label: s.t('Minggu lalu', 'Last week'),
                  value: c.hasLastWeek ? s.duration(c.lastWeekMinutes) : '—',
                  sub:
                      '${_date(c.lastStart!)} – ${_date(c.lastEnd!)}\n${c.lastWeekDays} ${s.t('hari tercatat', c.lastWeekDays == 1 ? 'recorded day' : 'recorded days')}',
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            !comparable
                ? s.t(
                    'Belum dibandingkan: perlu jumlah dan posisi hari tercatat yang sama, tidak kosong.',
                    'Not compared: both periods need the same recorded weekdays, nonempty.',
                  )
                : c.deltaMinutes == 0
                ? s.t(
                    'Waktu layar sama pada cakupan hari yang setara.',
                    'Equal screen time over equal day coverage.',
                  )
                : s.t(
                    '${s.duration(c.deltaMinutes.abs())} ${c.ahead ? 'lebih hemat' : 'lebih tinggi'} dari periode minggu lalu.',
                    '${s.duration(c.deltaMinutes.abs())} ${c.ahead ? 'less' : 'more'} than last week\'s period.',
                  ),
            style: t.body(12, color: t.muted),
          ),
          const SizedBox(height: 4),
          Text(
            s.t(
              'Senin sampai hari yang sama; hari yang tidak tercatat tidak dianggap nol.',
              'Monday through the same weekday; missing records are not treated as zero.',
            ),
            style: t.body(11, color: t.muted),
          ),
        ],
      ),
    );
  }
}

class _PeersCard extends ConsumerWidget {
  const _PeersCard({required this.mine, required this.s});
  final DuelSnapshot mine;
  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final peers = ref.watch(duelPeersProvider);
    final now = DateTime.now();
    final all = [mine, ...peers];
    final eligible =
        all
            .where((peer) => peer.unrankedReasonAgainst(mine, now: now) == null)
            .toList()
          ..sort(DuelSnapshot.compareScore);
    final unranked = all
        .where((peer) => peer.unrankedReasonAgainst(mine, now: now) != null)
        .toList();
    final ranked = eligible.length >= 2;
    var rank = 1;

    return TokenCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  s.t('Papan duel offline', 'Offline duel board'),
                  style: t.heading(16),
                ),
              ),
              StatusPill(
                label: s.t(
                  '${all.length}/6 peserta',
                  '${all.length}/6 players',
                ),
                color: t.ink.withValues(alpha: 0.08),
                textColor: t.ink,
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            s.t(
              'Bagikan kode, lalu tempel kode teman. Kode dilaporkan sendiri, bukan bukti terverifikasi.',
              'Share your code, then paste a friend\'s. Codes are self-reported, not verified evidence.',
            ),
            style: t.body(11, color: t.muted),
          ),
          const SizedBox(height: 10),
          for (var i = 0; i < eligible.length; i++)
            _row(
              ref,
              t,
              eligible[i],
              ranked
                  ? (i == 0 ||
                            DuelSnapshot.compareScore(
                                  eligible[i - 1],
                                  eligible[i],
                                ) !=
                                0
                        ? rank = i + 1
                        : rank)
                  : null,
              ranked
                  ? null
                  : s.t(
                      'Menunggu kode yang sebanding',
                      'Waiting for comparable codes',
                    ),
            ),
          for (final peer in unranked)
            _row(
              ref,
              t,
              peer,
              null,
              _reason(peer.unrankedReasonAgainst(mine, now: now)!),
            ),
          const SizedBox(height: 8),
          TokenButton(
            label: s.t('Salin kode duel', 'Copy duel code'),
            icon: Icons.copy_rounded,
            onPressed: mine.days == 0 ? null : () => _copy(context),
          ),
          const SizedBox(height: 8),
          TokenButton(
            label: s.t(
              'Tambah/perbarui teman (${peers.length}/5)',
              'Add/update friend (${peers.length}/5)',
            ),
            icon: Icons.content_paste_rounded,
            filled: false,
            onPressed: () => _paste(context),
          ),
          const SizedBox(height: 8),
          Text(
            s.t(
              'Kode memuat nama, waktu pembuatan, awal minggu, jumlah hari tercatat/seimbang, total menit, baseline, dan hit scroll. Tanpa detail app. Nama sama memperbarui kode lama.',
              'Codes include name, creation time, week start, recorded/balanced day counts, total minutes, baseline and scroll hits. No app detail. The same name updates an existing code.',
            ),
            style: t.body(10, color: t.muted),
          ),
        ],
      ),
    );
  }

  String _reason(DuelUnrankedReason reason) => switch (reason) {
    DuelUnrankedReason.legacy => s.t(
      'Kode v1: minggu dan data seimbang tidak tersedia',
      'v1 code: week and balance data unavailable',
    ),
    DuelUnrankedReason.week => s.t(
      'Minggu kalender berbeda atau sudah lewat',
      'Different or expired calendar week',
    ),
    DuelUnrankedReason.noData => s.t(
      'Belum ada hari dengan baseline untuk kedua peserta',
      'Both players need baseline-backed days',
    ),
    DuelUnrankedReason.coverage => s.t(
      'Jumlah hari tercatat tidak sama',
      'Recorded-day coverage differs',
    ),
    DuelUnrankedReason.baseline => s.t(
      'Baseline tidak tersedia',
      'Baseline unavailable',
    ),
    DuelUnrankedReason.invalid => s.t(
      'Skor atau tanggal tidak valid',
      'Invalid score or date',
    ),
  };

  Widget _row(
    WidgetRef ref,
    AppTokens t,
    DuelSnapshot peer,
    int? rank,
    String? reason,
  ) {
    final isMe = identical(peer, mine);
    final period = peer.periodStart == null
        ? s.t('periode tidak diketahui', 'unknown period')
        : s.t(
            'minggu mulai ${_date(DuelSnapshot.parseDay(peer.periodStart!)!)}',
            'week starts ${_date(DuelSnapshot.parseDay(peer.periodStart!)!)}',
          );
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.all(10),
      decoration: ShapeDecoration(
        color: isMe
            ? t.primary.withValues(alpha: 0.18)
            : t.ink.withValues(alpha: 0.04),
        shape: t.shape(radiusOverride: t.notched ? 3 : 10),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 24,
            child: Text(rank == null ? '—' : '$rank', style: t.number(14)),
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  isMe
                      ? s.t('${peer.name} (kamu)', '${peer.name} (you)')
                      : peer.name,
                  style: t.body(13, weight: FontWeight.w800),
                ),
                Text(
                  '$period · ${s.t('dibuat', 'created')} ${_date(peer.generatedAt)}',
                  style: t.body(10, color: t.muted),
                ),
                Text(
                  peer.balancedDays == null
                      ? s.t(
                          '${peer.days} hari tercatat',
                          '${peer.days} recorded ${peer.days == 1 ? 'day' : 'days'}',
                        )
                      : s.t(
                          '${peer.balancedDays}/${peer.days} seimbang · ${peer.days} hari tercatat',
                          '${peer.balancedDays}/${peer.days} balanced · ${peer.days} recorded ${peer.days == 1 ? 'day' : 'days'}',
                        ),
                  style: t.body(10, color: t.muted),
                ),
                Text(
                  s.t(
                    '${s.duration(peer.minutes)} total · ${peer.scrollHits} hit scroll',
                    '${s.duration(peer.minutes)} total · ${peer.scrollHits} scroll hits',
                  ),
                  style: t.body(11),
                ),
                if (peer.days > 0)
                  Text(
                    s.t(
                      '${s.duration((peer.minutes / peer.days).round())}/hari rata-rata',
                      '${s.duration((peer.minutes / peer.days).round())}/day average',
                    ),
                    style: t.body(10, color: t.muted),
                  ),
                if (reason != null)
                  Text(
                    '${s.t('Tanpa peringkat', 'Unranked')}: $reason',
                    style: t.body(11, color: t.muted),
                  ),
              ],
            ),
          ),
          if (!isMe)
            IconButton(
              onPressed: () =>
                  ref.read(duelPeersProvider.notifier).remove(peer.name),
              icon: Icon(Icons.close_rounded, size: 16, color: t.muted),
              tooltip: s.t('Hapus', 'Remove'),
            ),
        ],
      ),
    );
  }

  Future<void> _copy(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: mine.encode()));
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          s.t(
            'Kode duel disalin. Kirim ke temanmu.',
            'Duel code copied. Send it to a friend.',
          ),
        ),
      ),
    );
  }

  Future<void> _paste(BuildContext context) async {
    final added = await showDialog<bool>(
      context: context,
      builder: (_) => const _PasteCodeDialog(),
    );
    if (added == true && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(s.t('Kode teman disimpan.', 'Friend code saved.')),
        ),
      );
    }
  }
}

class _PasteCodeDialog extends ConsumerStatefulWidget {
  const _PasteCodeDialog();
  @override
  ConsumerState<_PasteCodeDialog> createState() => _PasteCodeDialogState();
}

class _PasteCodeDialogState extends ConsumerState<_PasteCodeDialog> {
  final _controller = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tokensProvider);
    final s = ref.watch(l10nProvider);
    return AlertDialog(
      backgroundColor: t.surface,
      shape: t.shape(),
      title: Text(
        s.t('Tempel kode teman', 'Paste friend code'),
        style: t.heading(18),
      ),
      content: TextField(
        controller: _controller,
        maxLines: 4,
        maxLength: DuelSnapshot.maxCodeLength,
        style: t.body(13),
        decoration: InputDecoration(
          hintText: s.t('Kode duel dari temanmu', 'Your friend\'s duel code'),
          errorText: _error,
          errorMaxLines: 3,
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: Text(s.t('Batal', 'Cancel'), style: t.body(13)),
        ),
        TextButton(
          onPressed: () {
            final snapshot = DuelSnapshot.tryDecode(_controller.text);
            if (snapshot == null) {
              setState(
                () => _error = s.t(
                  'Kode tidak valid atau tanggal di masa depan.',
                  'Invalid code or future date.',
                ),
              );
            } else if (ref
                .read(duelPeersProvider.notifier)
                .addCode(_controller.text)) {
              Navigator.of(context).pop(true);
            } else {
              setState(
                () => _error = s.t(
                  'Maksimal 5 teman. Hapus satu teman atau perbarui nama yang sudah ada.',
                  'Maximum 5 friends. Remove one or update an existing name.',
                ),
              );
            }
          },
          child: Text(
            s.t('Simpan', 'Save'),
            style: t.body(13, weight: FontWeight.w800),
          ),
        ),
      ],
    );
  }
}

class _RulesCard extends ConsumerWidget {
  const _RulesCard({required this.s});
  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final rules = [
      s.t(
        'Minggu kalender lokal Senin–Minggu, bukan 7 hari bergulir. Hanya kode minggu berjalan dengan jumlah hari tercatat sama (minimal 1) yang mendapat peringkat.',
        'Local Monday–Sunday calendar week, not a rolling 7 days. Only current-week codes with equal recorded-day coverage (at least 1 day) are ranked.',
      ),
      s.t(
        'Persentase hari seimbang tertinggi menang: menit hari itu tidak melebihi baseline pribadinya. Hari tanpa baseline tidak dihitung.',
        'Highest balanced-day rate wins: that day\'s minutes do not exceed its personal baseline. Days without a baseline are excluded.',
      ),
      s.t(
        'Jika seri, rata-rata menit layar terendah menang, lalu rata-rata hit scroll terendah. Skor sama berbagi peringkat.',
        'Ties use lower average screen minutes, then lower average scroll hits. Equal scores share a rank.',
      ),
      s.t(
        'Cakupan yang sama berarti jumlah hari tercatat sama, belum tentu tanggal rekamannya sama. Hari ini belum selesai; salin ulang kode untuk memperbarui. Kode lama v1 tetap terlihat tanpa peringkat.',
        'Equal coverage means equal recorded-day counts, not necessarily identical recorded dates. Today is incomplete; copy a new code to update. Legacy v1 codes remain visible but unranked.',
      ),
      s.t(
        'Kode bisa diubah dan nama bukan identitas terverifikasi. Duel offline berbasis kejujuran, tanpa server atau jaringan otomatis.',
        'Codes can be edited and names are not verified identities. Offline duels rely on honesty, with no server or automatic network access.',
      ),
    ];
    return TokenCard(
      child: Column(
        children: [
          for (final text in rules)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.check_rounded, size: 16, color: t.hpHealthy),
                  const SizedBox(width: 8),
                  Expanded(child: Text(text, style: t.body(12))),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
