part of 'profil_screen.dart';

class _PermissionCard extends ConsumerWidget {
  const _PermissionCard({
    required this.state,
    required this.s,
    required this.pillBusy,
  });

  final _ProfilScreenState state;
  final L10n s;
  final bool pillBusy;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final async = ref.watch(permissionStatusProvider);

    return async.when(
      loading: () => const Padding(
        padding: EdgeInsets.symmetric(vertical: 24),
        child: Center(child: CircularProgressIndicator()),
      ),
      error: (_, _) => NoticeBanner(
        message: s.t('Gagal memeriksa izin.', 'Failed to check permissions.'),
        actionLabel: s.t('Coba lagi', 'Retry'),
        onAction: () => ref.invalidate(permissionStatusProvider),
      ),
      data: (status) => TokenCard(
        child: Column(
          children: [
            _PermissionRow(
              icon: Icons.query_stats_rounded,
              title: s.t('Akses pemakaian', 'Usage access'),
              subtitle: s.t(
                'Dasar rekap durasi dan jumlah buka app.',
                'The base for app duration and open counts.',
              ),
              granted: status.usage,
              s: s,
              onPressed: () => requestUsageAccess(context, ref),
            ),
            const Divider(height: 22),
            _PermissionRow(
              icon: Icons.swipe_rounded,
              title: s.t(
                'Aksesibilitas (hitung scroll)',
                'Accessibility (scroll count)',
              ),
              subtitle: s.t(
                'Hanya menghitung gulir (metadata), tidak membaca isi layar.',
                'Counts scrolls (metadata only), never reads screen content.',
              ),
              granted: status.accessibility,
              s: s,
              onPressed: () => requestAccessibility(context, ref),
            ),
            const Divider(height: 22),
            _PermissionRow(
              icon: Icons.picture_in_picture_alt_rounded,
              title: s.t('Floating Pill', 'Floating Pill'),
              subtitle: s.t(
                'Aplikasi yang terbuka dan HP pet secara live di atas aplikasi lain.',
                'The open app and your pet\'s live HP above other apps.',
              ),
              granted: status.overlay,
              s: s,
              onPressed: () => requestOverlay(context, ref),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: Text(
                    status.pillRunning
                        ? s.t('Pill sedang tampil', 'The pill is showing')
                        : s.t('Pill nonaktif', 'The pill is off'),
                    style: t.body(12, color: t.muted),
                  ),
                ),
                if (pillBusy)
                  const SizedBox(
                    width: 22,
                    height: 22,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                else
                  Switch.adaptive(
                    value: status.pillRunning,
                    activeThumbColor: t.primary,
                    onChanged: (v) => state._togglePill(v),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _PermissionRow extends ConsumerWidget {
  const _PermissionRow({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.granted,
    required this.s,
    required this.onPressed,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final bool granted;
  final L10n s;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 20, color: granted ? t.hpHealthy : t.muted),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: t.body(13, weight: FontWeight.w800)),
              const SizedBox(height: 2),
              Text(subtitle, style: t.body(11, color: t.muted)),
            ],
          ),
        ),
        const SizedBox(width: 8),
        granted
            ? Icon(Icons.check_circle_rounded, color: t.hpHealthy, size: 22)
            : TextButton(
                onPressed: onPressed,
                style: TextButton.styleFrom(
                  minimumSize: const Size(48, 48),
                  foregroundColor: t.ink,
                ),
                child: Text(
                  s.t('Atur', 'Set'),
                  style: t.body(12, weight: FontWeight.w800),
                ),
              ),
      ],
    );
  }
}
