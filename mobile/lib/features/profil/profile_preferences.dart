part of 'profil_screen.dart';

class _SettingsCard extends ConsumerStatefulWidget {
  const _SettingsCard({required this.s});

  final L10n s;

  @override
  ConsumerState<_SettingsCard> createState() => _SettingsCardState();
}

class _SettingsCardState extends ConsumerState<_SettingsCard> {
  double? _draft;

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tokensProvider);
    final s = widget.s;
    final game = ref.watch(gameProvider);
    final value = _draft ?? game.restMinutes.toDouble();

    return TokenCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  s.t('Durasi istirahat', 'Rest duration'),
                  style: t.body(14, weight: FontWeight.w800),
                ),
              ),
              Text(
                '${value.round()} ${s.t('menit', 'min')}',
                style: t.number(14),
              ),
            ],
          ),
          Slider(
            value: value.clamp(
              Balancing.restMinMinutes.toDouble(),
              Balancing.restMaxMinutes.toDouble(),
            ),
            min: Balancing.restMinMinutes.toDouble(),
            max: Balancing.restMaxMinutes.toDouble(),
            divisions: Balancing.restMaxMinutes - Balancing.restMinMinutes,
            label: '${value.round()}m',
            activeColor: t.primary,
            onChanged: (v) => setState(() => _draft = v),
            onChangeEnd: (v) {
              ref.read(gameProvider.notifier).setRestMinutes(v.round());
              setState(() => _draft = null);
            },
          ),
          Text(
            s.t(
              'Rentang 10–20 menit. Reward harian dibatasi satu istirahat penuh; kamu tetap boleh beristirahat lagi.',
              'Choose 10–20 minutes. Daily rewards are capped at one full rest; you can always rest again.',
            ),
            style: t.body(11, color: t.muted),
          ),
          if (kDebugMode) const Divider(height: 24),
          if (kDebugMode)
            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              value: game.demoSpeed,
              activeThumbColor: t.primary,
              title: Text(
                s.t('Mode demo', 'Demo mode'),
                style: t.body(14, weight: FontWeight.w800),
              ),
              subtitle: Text(
                s.t(
                  'Timer misi dan istirahat berjalan 1 detik = 1 menit untuk pengujian.',
                  'Mission and rest timers run 1 second = 1 minute for testing.',
                ),
                style: t.body(11, color: t.muted),
              ),
              onChanged: (v) => ref.read(gameProvider.notifier).setDemoSpeed(v),
            ),
        ],
      ),
    );
  }
}

class _DebugCard extends ConsumerWidget {
  const _DebugCard({required this.s});

  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final game = ref.watch(gameProvider);
    final petName = game.petFamily?.label ?? 'Momo';

    return TokenCard(
      elevated: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            s.t(
              'Pindah level untuk meninjau tiap wujud $petName tanpa menunggu XP.',
              'Jump levels to review each $petName form without waiting for XP.',
            ),
            style: t.body(11, color: t.muted),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: TokenButton(
                  label: s.t('Turun', 'Down'),
                  filled: false,
                  onPressed: game.level <= 1
                      ? null
                      : () => ref
                            .read(gameProvider.notifier)
                            .debugSetLevel(game.level - 1),
                ),
              ),
              const SizedBox(width: 10),
              Text('Lv. ${game.level}', style: t.number(16)),
              const SizedBox(width: 10),
              Expanded(
                child: TokenButton(
                  label: s.t('Naik', 'Up'),
                  filled: false,
                  onPressed: game.level >= 20
                      ? null
                      : () => ref
                            .read(gameProvider.notifier)
                            .debugSetLevel(game.level + 1),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: TokenButton(
                  label: s.t('Remaja (Lv. 5)', 'Teen (Lv. 5)'),
                  filled: false,
                  onPressed: () =>
                      ref.read(gameProvider.notifier).debugSetLevel(5),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TokenButton(
                  label: s.t('Dewasa (Lv. 11)', 'Adult (Lv. 11)'),
                  filled: false,
                  onPressed: () =>
                      ref.read(gameProvider.notifier).debugSetLevel(11),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// Satu pengingat harian, dijadwalkan lewat AlarmManager native.
class _ReminderCard extends ConsumerStatefulWidget {
  const _ReminderCard({required this.s});

  final L10n s;

  @override
  ConsumerState<_ReminderCard> createState() => _ReminderCardState();
}

class _ReminderCardState extends ConsumerState<_ReminderCard> {
  bool _busy = false;

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tokensProvider);
    final s = widget.s;
    final game = ref.watch(gameProvider);
    final time = TimeOfDay(
      hour: game.reminderHour,
      minute: game.reminderMinute,
    );

    return TokenCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.notifications_none_rounded, size: 20, color: t.ink),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  s.t('Pengingat harian', 'Daily reminder'),
                  style: t.heading(16),
                ),
              ),
              if (_busy)
                const SizedBox(
                  width: 22,
                  height: 22,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              else
                Switch.adaptive(
                  value: game.reminderEnabled,
                  activeThumbColor: t.primary,
                  onChanged: _toggle,
                ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            s.t(
              'Satu pengingat singkat per hari, bukan deretan notifikasi. '
                  'Matikan kapan saja tanpa kehilangan progres.',
              'One short reminder per day, not a stream of notifications. '
                  'Turn it off anytime without losing progress.',
            ),
            style: t.body(11, color: t.muted),
          ),
          const SizedBox(height: 10),
          InkWell(
            onTap: _pickTime,
            borderRadius: BorderRadius.circular(10),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      s.t('Waktu pengingat', 'Reminder time'),
                      style: t.body(13, weight: FontWeight.w800),
                    ),
                  ),
                  Text(time.format(context), style: t.number(14)),
                  const SizedBox(width: 6),
                  Icon(Icons.schedule_rounded, size: 16, color: t.muted),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _toggle(bool value) async {
    final s = widget.s;
    final petName =
        (ref.read(gameProvider).petFamily ?? PetFamily.momo).label;
    setState(() => _busy = true);
    final ok = await applyReminder(ref, enable: value);
    ref.read(gameProvider.notifier).setReminderEnabled(value && ok);
    if (!mounted) return;
    setState(() => _busy = false);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          value
              ? (ok
                    ? s.t('Pengingat harian aktif.', 'Daily reminder is on.')
                    : s.t(
                        'Pengingat tidak aktif. Izinkan notifikasi untuk $petName di pengaturan Android, lalu coba lagi.',
                        'Reminder is not active. Allow notifications for $petName in Android settings, then try again.',
                      ))
              : s.t('Pengingat harian dimatikan.', 'Daily reminder is off.'),
        ),
      ),
    );
  }

  Future<void> _pickTime() async {
    final game = ref.read(gameProvider);
    final picked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(
        hour: game.reminderHour,
        minute: game.reminderMinute,
      ),
    );
    if (picked == null) return;
    ref.read(gameProvider.notifier).setReminderTime(picked.hour, picked.minute);
    if (game.reminderEnabled) {
      await applyReminder(ref, enable: true);
    }
  }
}
