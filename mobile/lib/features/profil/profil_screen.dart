import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/balancing.dart';
import '../../core/l10n/l10n.dart';
import '../../core/models/companion.dart';
import '../../core/models/pet.dart';
import '../../core/services/pause_controller.dart';
import '../../core/services/pill_controller.dart';
import '../../core/services/reminder_controller.dart';
import '../../core/state/app_state.dart';
import '../../core/theme/app_tokens.dart';
import '../../widgets/companion_3d.dart';
import '../../widgets/permission_flow.dart';
import '../../widgets/ui.dart';
import 'app_management_screen.dart';
import 'privacy_card.dart';

part 'profile_appearance.dart';
part 'profile_pet.dart';
part 'profile_permissions.dart';
part 'profile_preferences.dart';
part 'profile_pause.dart';

/// Tab Profil: koleksi, tema, bahasa, pengaturan izin, dan kontrol privasi.
class ProfilScreen extends ConsumerStatefulWidget {
  const ProfilScreen({super.key});

  @override
  ConsumerState<ProfilScreen> createState() => _ProfilScreenState();
}

class _ProfilScreenState extends ConsumerState<ProfilScreen> {
  bool _pillBusy = false;

  @override
  void initState() {
    super.initState();
    // Permissions can change in Android Settings while this tab stays alive.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) ref.invalidate(permissionStatusProvider);
    });
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tokensProvider);
    final s = ref.watch(l10nProvider);
    final pet = ref.watch(
      gameProvider.select((g) => g.petFamily ?? PetFamily.momo),
    );

    return ListView(
      padding: const EdgeInsets.fromLTRB(18, 14, 18, 28),
      children: [
        Text(s.t('Profil', 'Profile'), style: t.heading(28)),
        const SizedBox(height: 4),
        Text(
          s.t(
            'Semua pengaturan tersimpan di HP ini.',
            'All settings stay on this phone.',
          ),
          style: t.body(13, color: t.muted),
        ),
        const SizedBox(height: 14),
        _ProfileHeader(s: s),
        const SizedBox(height: 18),
        SectionTitle(
          s.t('Koleksi ${pet.label}', '${pet.label} collection'),
        ),
        _Collection(s: s),
        const SizedBox(height: 6),
        Text(
          s.t(
            'Pendamping dipilih saat onboarding dan tidak bisa diganti.',
            'The companion is chosen during onboarding and cannot be changed.',
          ),
          style: t.body(11, color: t.muted),
        ),
        const SizedBox(height: 18),
        SectionTitle(s.t('Pet & animasi', 'Pet & animation')),
        _PetCard(state: this, s: s),
        const SizedBox(height: 18),
        SectionTitle(s.t('Tema', 'Theme')),
        _ThemePicker(s: s),
        const SizedBox(height: 18),
        SectionTitle(s.t('Bahasa', 'Language')),
        _LanguagePicker(s: s),
        const SizedBox(height: 18),
        SectionTitle(s.t('Pengaturan', 'Settings')),
        _SettingsCard(s: s),
        const SizedBox(height: 18),
        SectionTitle(s.t('Izin & privasi', 'Permissions & privacy')),
        _PermissionCard(state: this, s: s, pillBusy: _pillBusy),
        const SizedBox(height: 18),
        SectionTitle(s.t('Jeda Sadar', 'Conscious Pause')),
        _PauseCard(s: s),
        const SizedBox(height: 18),
        SectionTitle(s.t('Aplikasi & batas harian', 'Apps & daily limits')),
        TokenButton(
          label: s.t('Kelola aplikasi', 'Manage apps'),
          icon: Icons.apps_rounded,
          filled: false,
          onPressed: () => Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => const AppManagementScreen(),
            ),
          ),
        ),
        const SizedBox(height: 18),
        SectionTitle(s.t('Pengingat harian', 'Daily reminder')),
        _ReminderCard(s: s),
        const SizedBox(height: 12),
        const PrivacyCard(),
        if (kDebugMode) ...[
          const SizedBox(height: 18),
          SectionTitle(s.t('Alat uji', 'Test tools')),
          _DebugCard(s: s),
        ],
        const SizedBox(height: 20),
        Center(
          child: Text(
            'Screen Time Tracker · v1.0.0',
            style: t.body(11, color: t.muted),
          ),
        ),
        const SizedBox(height: 4),
        Center(
          child: Text(
            s.t(
              '${pet.label} 3D · rig hidup',
              '${pet.label} 3D · living rig',
            ),
            style: t.body(11, color: t.muted),
          ),
        ),
      ],
    );
  }

  Future<void> _togglePill(bool enabled) async {
    final s = ref.read(l10nProvider);
    final service = ref.read(usageServiceProvider);

    setState(() => _pillBusy = true);
    if (!enabled) {
      await service.hidePill();
      ref.invalidate(permissionStatusProvider);
      if (mounted) setState(() => _pillBusy = false);
      return;
    }

    final overlay = await service.hasOverlay();
    if (!overlay) {
      if (mounted) {
        await requestOverlay(context, ref);
        if (!mounted) return;
        setState(() => _pillBusy = false);
        ref.invalidate(permissionStatusProvider);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                s.t(
                  'Setelah izin diberikan, aktifkan pill lagi di sini.',
                  'Once permission is granted, turn the pill on again here.',
                ),
              ),
            ),
          );
        }
      }
      return;
    }

    final ok = await applyPill(ref);
    ref.invalidate(permissionStatusProvider);
    if (!mounted) return;
    setState(() => _pillBusy = false);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          ok
              ? s.t('Floating Pill aktif.', 'Floating Pill is on.')
              : s.t(
                  'Pill tidak dapat dimulai di perangkat ini.',
                  'The pill cannot start on this device.',
                ),
        ),
      ),
    );
  }

  /// This only refreshes an already-running pill; it never starts one.
  void _setPillMode(PetAnimationMode mode) {
    ref.read(gameProvider.notifier).setPillAnimationMode(mode);
    final running =
        ref.read(permissionStatusProvider).asData?.value.pillRunning ?? false;
    if (running) applyPill(ref);
  }

  /// The form is part of the pill, so a running pill is rebuilt in place.
  void _setPillForm(PillForm form) {
    ref.read(gameProvider.notifier).setPillForm(form);
    final running =
        ref.read(permissionStatusProvider).asData?.value.pillRunning ?? false;
    if (running) applyPill(ref);
  }
}
