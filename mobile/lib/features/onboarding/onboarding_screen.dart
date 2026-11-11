import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/l10n/l10n.dart';
import '../../core/models/pet.dart';
import '../../core/state/app_state.dart';
import '../../core/state/installed_apps_provider.dart';
import '../../core/theme/app_tokens.dart';
import '../../widgets/permission_flow.dart';
import '../../widgets/ui.dart';

/// Alur awal empat langkah: identitas (bahasa dan nama), tampilan (tema dan
/// pendamping), app yang dipantau beserta aturan hitung, lalu izin dan
/// persetujuan. Pendamping wajib dipilih dan pilihannya terkunci setelah
/// onboarding selesai.
class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  static const _totalSteps = 4;
  static const _limitOptions = [0, 15, 30, 60, 120];

  final _nameController = TextEditingController();
  int _step = 0;
  bool _finishing = false;
  late AppThemeId _theme;
  PetFamily? _petFamily;
  late Set<String> _selectedPackages;
  bool _selectionChanged = false;
  int _initialLimit = 0;

  @override
  void initState() {
    super.initState();
    final game = ref.read(gameProvider);
    _nameController.text = game.userName;
    // A restored backup keeps its theme; onboarding must not reset it to the
    // default just because consent has to be given again.
    _theme = game.themeId;
    _petFamily = game.petFamily;
    _selectedPackages = {...game.monitoredPackages};
  }

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  void _next() {
    if (_step == 1 && _petFamily == null) {
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(
          SnackBar(
            content: Text(
              ref
                  .read(l10nProvider)
                  .t('Pilih pendamping dulu.', 'Choose a companion first.'),
            ),
          ),
        );
      return;
    }
    if (_step < _totalSteps - 1) {
      setState(() => _step++);
    } else {
      _finish();
    }
  }

  void _back() {
    if (_step == 0) return;
    setState(() => _step--);
  }

  Future<void> _finish() async {
    if (_finishing) return;
    final pet = _petFamily;
    if (pet == null) {
      setState(() => _step = 1);
      return;
    }
    final apps = ref.read(installedAppsProvider).asData?.value;
    if (_selectionChanged && apps == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            ref
                .read(l10nProvider)
                .t(
                  'Daftar app belum termuat. Buka langkah sebelumnya lalu coba lagi.',
                  'The app list has not loaded. Go back one step and try again.',
                ),
          ),
        ),
      );
      return;
    }

    setState(() => _finishing = true);
    final notifier = ref.read(gameProvider.notifier);
    notifier.setUserName(_nameController.text);

    Set<String>? packages;
    Map<String, int>? limits;
    if (apps != null) {
      final installed = apps
          .map((app) => app['packageName'])
          .whereType<String>()
          .toSet();
      final selected = _selectedPackages.where(installed.contains).toSet();
      if (_selectionChanged) packages = selected;
      if (_initialLimit > 0) {
        final existing = ref.read(gameProvider).appLimits;
        final next = {
          for (final pkg in selected)
            if (!existing.containsKey(pkg)) pkg: _initialLimit,
        };
        if (next.isNotEmpty) limits = next;
      }
    }

    try {
      await notifier.finishOnboarding(
        _theme,
        petFamily: pet,
        monitoredPackages: packages,
        appLimits: limits,
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            ref
                .read(l10nProvider)
                .t(
                  'Pengaturan belum tersimpan. Coba lagi.',
                  'Setup was not saved. Try again.',
                ),
          ),
        ),
      );
    } finally {
      if (mounted) setState(() => _finishing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tokensProvider);
    final s = ref.watch(l10nProvider);
    // Watched here, not inside the step, so switching steps does not reload the
    // launcher list and the final save always sees the loaded data.
    final apps = ref.watch(installedAppsProvider);

    return Scaffold(
      backgroundColor: t.bg,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(22, 18, 22, 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Screen Time Tracker',
                      style: t.body(12, weight: FontWeight.w800),
                    ),
                  ),
                  Text(
                    s.t(
                      '${_step + 1} dari $_totalSteps',
                      '${_step + 1} of $_totalSteps',
                    ),
                    style: t.body(12, color: t.muted),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              _Progress(step: _step, total: _totalSteps),
              const SizedBox(height: 22),
              Expanded(
                child: SingleChildScrollView(
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 220),
                    child: KeyedSubtree(
                      key: ValueKey<int>(_step),
                      child: _buildStep(s, apps),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  if (_step > 0)
                    Expanded(
                      child: TokenButton(
                        label: s.t('Kembali', 'Back'),
                        filled: false,
                        onPressed: _finishing ? null : _back,
                      ),
                    ),
                  if (_step > 0) const SizedBox(width: 10),
                  Expanded(
                    flex: 2,
                    child: TokenButton(
                      label: _step == _totalSteps - 1
                          ? s.t('Mulai', 'Start')
                          : s.t('Lanjut', 'Next'),
                      onPressed: _finishing ? null : _next,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStep(L10n s, AsyncValue<List<Map<String, String>>> apps) {
    return switch (_step) {
      0 => _IdentityStep(s: s, controller: _nameController),
      1 => _LookStep(
        s: s,
        theme: _theme,
        onTheme: (id) => setState(() => _theme = id),
        pet: _petFamily,
        onPet: (family) => setState(() => _petFamily = family),
      ),
      2 => _AppsStep(
        s: s,
        apps: apps,
        selected: _selectedPackages,
        initialLimit: _initialLimit,
        limitOptions: _limitOptions,
        onToggle: (pkg, selected) {
          setState(() {
            _selectionChanged = true;
            selected
                ? _selectedPackages.add(pkg)
                : _selectedPackages.remove(pkg);
          });
        },
        onLimit: (minutes) => setState(() => _initialLimit = minutes),
        onRetry: () => ref.invalidate(installedAppsProvider),
      ),
      _ => _PermissionsStep(s: s),
    };
  }
}

class _Progress extends ConsumerWidget {
  const _Progress({required this.step, required this.total});

  final int step;
  final int total;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    return Row(
      children: List.generate(total, (i) {
        final active = i <= step;
        return Expanded(
          child: Container(
            height: 6,
            margin: EdgeInsets.only(right: i == total - 1 ? 0 : 6),
            decoration: BoxDecoration(
              color: active ? t.primary : t.ink.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(99),
            ),
          ),
        );
      }),
    );
  }
}

class _IdentityStep extends ConsumerWidget {
  const _IdentityStep({required this.s, required this.controller});

  final L10n s;
  final TextEditingController controller;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final current = ref.watch(gameProvider.select((g) => g.language));

    Widget language(String code, String label) {
      final selected = current == code;
      return Expanded(
        child: Semantics(
          button: true,
          selected: selected,
          excludeSemantics: true,
          label: label,
          onTap: () => ref.read(gameProvider.notifier).setLanguage(code),
          child: GestureDetector(
            onTap: () => ref.read(gameProvider.notifier).setLanguage(code),
            child: Container(
              height: 46,
              alignment: Alignment.center,
              decoration: ShapeDecoration(
                // Opaque tint keeps the selected choice clear without a halo
                // from the card shadow.
                color: selected
                    ? Color.alphaBlend(t.primary.withValues(alpha: 0.25), t.bg)
                    : t.surface,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(t.notched ? 0 : t.radius),
                  side: BorderSide(
                    color: selected ? t.ink : t.ink.withValues(alpha: 0.14),
                    width: selected ? 2 : 1,
                  ),
                ),
              ),
              child: Text(label, style: t.heading(13)),
            ),
          ),
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(s.t('Kenalan dulu', 'First, a quick intro'), style: t.heading(28)),
        const SizedBox(height: 8),
        Text(
          s.t(
            'Pilih bahasa dan isi nama panggilan.',
            'Choose a language and add a display name.',
          ),
          style: t.body(14, color: t.muted),
        ),
        const SizedBox(height: 22),
        Text(s.t('Bahasa', 'Language'), style: t.heading(15)),
        const SizedBox(height: 8),
        Row(
          children: [
            language('id', 'Indonesia'),
            const SizedBox(width: 8),
            language('en', 'English'),
          ],
        ),
        const SizedBox(height: 20),
        Text(s.t('Nama panggilan', 'Display name'), style: t.heading(15)),
        const SizedBox(height: 8),
        TokenCard(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
          child: TextField(
            controller: controller,
            textCapitalization: TextCapitalization.words,
            textInputAction: TextInputAction.done,
            style: t.body(16),
            decoration: InputDecoration(
              border: InputBorder.none,
              hintText: s.t('Contoh: Raka', 'Example: Raka'),
              hintStyle: t.body(16, color: t.muted),
            ),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          s.t(
            'Opsional, tersimpan hanya di HP ini.',
            'Optional, stored only on this phone.',
          ),
          style: t.body(11, color: t.muted),
        ),
      ],
    );
  }
}

class _LookStep extends ConsumerWidget {
  const _LookStep({
    required this.s,
    required this.theme,
    required this.onTheme,
    required this.pet,
    required this.onPet,
  });

  final L10n s;
  final AppThemeId theme;
  final ValueChanged<AppThemeId> onTheme;
  final PetFamily? pet;
  final ValueChanged<PetFamily> onPet;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(s.t('Tampilan', 'Your look'), style: t.heading(28)),
        const SizedBox(height: 8),
        Text(
          s.t('Pilih tema dan pendamping.', 'Pick a theme and a companion.'),
          style: t.body(14, color: t.muted),
        ),
        const SizedBox(height: 22),
        Text(s.t('Tema', 'Theme'), style: t.heading(15)),
        const SizedBox(height: 8),
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 8,
          crossAxisSpacing: 8,
          childAspectRatio: 2.4,
          children: [
            for (final option in AppThemes.all)
              _ThemeTile(
                theme: option,
                active: option.id == theme,
                s: s,
                onTap: () => onTheme(option.id),
              ),
          ],
        ),
        const SizedBox(height: 22),
        Text(s.t('Pendamping', 'Companion'), style: t.heading(15)),
        const SizedBox(height: 8),
        _PetPicker(s: s, selected: pet, onSelect: onPet),
        const SizedBox(height: 8),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.lock_outline_rounded, size: 14, color: t.muted),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                s.t(
                  'Tidak bisa diganti setelah onboarding.',
                  'Cannot be changed after onboarding.',
                ),
                style: t.body(11, color: t.muted),
              ),
            ),
          ],
        ),
        const SizedBox(height: 22),
        _PillLookCard(s: s),
      ],
    );
  }
}

/// Optional: how much of the companion rides along once the pill is on. These
/// choices only persist the look; the overlay itself is asked for in Profile.
class _PillLookCard extends ConsumerWidget {
  const _PillLookCard({required this.s});

  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final form = ref.watch(gameProvider.select((g) => g.pillForm));
    final mode = ref.watch(gameProvider.select((g) => g.pillAnimationMode));

    Widget option(String label, bool active, VoidCallback onTap) {
      return Expanded(
        child: Semantics(
          button: true,
          selected: active,
          excludeSemantics: true,
          label: label,
          onTap: onTap,
          child: GestureDetector(
            onTap: onTap,
            child: Container(
              height: 38,
              alignment: Alignment.center,
              decoration: ShapeDecoration(
                color: active
                    ? Color.alphaBlend(t.primary.withValues(alpha: 0.25), t.bg)
                    : t.surface,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(t.notched ? 0 : t.radius),
                  side: BorderSide(
                    color: active ? t.ink : t.ink.withValues(alpha: 0.14),
                    width: active ? 2 : 1,
                  ),
                ),
              ),
              child: Text(label, style: t.body(12, weight: FontWeight.w800)),
            ),
          ),
        ),
      );
    }

    Widget row(String label, List<Widget> choices) {
      return Row(
        children: [
          SizedBox(
            width: 70,
            child: Text(label, style: t.body(12, weight: FontWeight.w800)),
          ),
          const SizedBox(width: 8),
          ...choices,
        ],
      );
    }

    final notifier = ref.read(gameProvider.notifier);

    return TokenCard(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.picture_in_picture_alt_rounded,
                size: 18,
                color: t.ink,
              ),
              const SizedBox(width: 8),
              Expanded(child: Text('Floating Pill', style: t.heading(15))),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  border: Border.all(color: t.ink.withValues(alpha: 0.2)),
                  borderRadius: BorderRadius.circular(99),
                ),
                child: Text(
                  s.t('Opsional', 'Optional'),
                  style: t.body(10, color: t.muted, weight: FontWeight.w800),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            s.t(
              'Dilewati pun tidak apa-apa. Pill dinyalakan di Profil → Izin & '
                  'privasi; bentuk dan animasinya bisa diubah kapan saja di '
                  'Profil → Pet & animasi.',
              'Skipping is fine. Turn the pill on in Profile → Permissions & '
                  'privacy; change its form and animation anytime in Profile → '
                  'Pet & animation.',
            ),
            style: t.body(11, color: t.muted),
          ),
          const SizedBox(height: 12),
          row(s.t('Bentuk', 'Form'), [
            option(
              s.t('Kepala', 'Head'),
              form == PillForm.head,
              () => notifier.setPillForm(PillForm.head),
            ),
            const SizedBox(width: 8),
            option(
              s.t('Badan penuh', 'Full body'),
              form == PillForm.body,
              () => notifier.setPillForm(PillForm.body),
            ),
          ]),
          const SizedBox(height: 8),
          row(s.t('Animasi', 'Animation'), [
            option(
              s.t('Statis (hemat)', 'Static (saver)'),
              mode == PetAnimationMode.flat,
              () => notifier.setPillAnimationMode(PetAnimationMode.flat),
            ),
            const SizedBox(width: 8),
            option(
              s.t('Penuh', 'Full'),
              mode == PetAnimationMode.full,
              () => notifier.setPillAnimationMode(PetAnimationMode.full),
            ),
          ]),
        ],
      ),
    );
  }
}

class _ThemeTile extends StatelessWidget {
  const _ThemeTile({
    required this.theme,
    required this.active,
    required this.s,
    required this.onTap,
  });

  final AppTokens theme;
  final bool active;
  final L10n s;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      selected: active,
      excludeSemantics: true,
      label: '${theme.name}, ${s.isEnglish ? theme.taglineEn : theme.tagline}',
      onTap: onTap,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: ShapeDecoration(
            color: theme.bg,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(
                theme.notched ? 0 : theme.radius,
              ),
              side: BorderSide(
                color: active ? theme.ink : theme.ink.withValues(alpha: 0.14),
                width: active ? 2.5 : 1,
              ),
            ),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      theme.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: theme.heading(13),
                    ),
                  ),
                  if (active)
                    Icon(Icons.check_rounded, size: 16, color: theme.ink),
                ],
              ),
              const SizedBox(height: 7),
              Row(
                children: [
                  _ColorDot(color: theme.primary),
                  const SizedBox(width: 4),
                  _ColorDot(color: theme.secondary),
                  const SizedBox(width: 4),
                  _ColorDot(color: theme.hpHealthy),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ColorDot extends StatelessWidget {
  const _ColorDot({required this.color});

  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 8,
      height: 8,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    );
  }
}

class _PetPicker extends ConsumerWidget {
  const _PetPicker({
    required this.s,
    required this.selected,
    required this.onSelect,
  });

  final L10n s;
  final PetFamily? selected;
  final ValueChanged<PetFamily> onSelect;

  String _tagline(PetFamily family) => switch (family) {
    PetFamily.momo => s.t('Rubah kecil · Bayi', 'Little fox · Baby'),
    PetFamily.drako => s.t('Naga kecil · Bayi', 'Little dragon · Baby'),
  };

  String _semanticsLabel(PetFamily family) => switch (family) {
    PetFamily.momo => s.t('Momo, rubah kecil, Bayi', 'Momo, little fox, Baby'),
    PetFamily.drako => s.t(
      'Drako, naga kecil, Bayi',
      'Drako, little dragon, Baby',
    ),
  };

  Future<void> _confirm(
    BuildContext context,
    WidgetRef ref,
    PetFamily family,
  ) async {
    final s = ref.read(l10nProvider);
    final t = ref.read(tokensProvider);
    final name = family.label;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(s.t('Pilih $name?', 'Choose $name?')),
        content: Text(
          s.t(
            '$name jadi pendampingmu dan ikut tumbuh dari Bayi ke Dewasa. '
                'Setelah onboarding selesai, pendamping tidak bisa diganti.',
            '$name becomes your companion and grows from Baby to Adult. After '
                'onboarding, the companion cannot be changed.',
          ),
        ),
        actions: [
          TextButton(
            // The theme's primary is too light for text on this surface.
            style: TextButton.styleFrom(foregroundColor: t.ink),
            onPressed: () => Navigator.pop(ctx, false),
            child: Text(s.t('Batal', 'Cancel')),
          ),
          TextButton(
            style: TextButton.styleFrom(foregroundColor: t.ink),
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(
              s.t('Ya, pilih $name', 'Yes, choose $name'),
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
          ),
        ],
      ),
    );
    if (ok == true) onSelect(family);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);

    Widget choice(PetFamily family) {
      final chosen = selected == family;
      final tagline = _tagline(family);
      return Semantics(
        button: true,
        selected: chosen,
        container: true,
        excludeSemantics: true,
        label: _semanticsLabel(family),
        onTap: chosen ? null : () => _confirm(context, ref, family),
        child: GestureDetector(
          onTap: chosen ? null : () => _confirm(context, ref, family),
          child: TokenCard(
            elevated: chosen,
            color: chosen ? t.tint(t.primary, 0.18) : t.surface,
            padding: const EdgeInsets.all(8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  height: 104,
                  padding: const EdgeInsets.all(4),
                  clipBehavior: Clip.antiAlias,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(
                      t.notched ? 0 : t.radius / 2,
                    ),
                    border: Border.all(color: t.ink.withValues(alpha: 0.12)),
                  ),
                  child: Image.asset(
                    family.profile.babyCardAsset,
                    fit: BoxFit.contain,
                    excludeFromSemantics: true,
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(child: Text(family.label, style: t.heading(15))),
                    Icon(
                      chosen
                          ? Icons.check_circle_rounded
                          : Icons.circle_outlined,
                      color: chosen ? t.ink : t.muted,
                      size: 18,
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Text(tagline, style: t.body(10, color: t.muted)),
              ],
            ),
          ),
        ),
      );
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final family in PetFamily.values) ...[
          if (family != PetFamily.values.first) const SizedBox(width: 8),
          Expanded(child: choice(family)),
        ],
      ],
    );
  }
}

class _AppsStep extends ConsumerStatefulWidget {
  const _AppsStep({
    required this.s,
    required this.apps,
    required this.selected,
    required this.initialLimit,
    required this.limitOptions,
    required this.onToggle,
    required this.onLimit,
    required this.onRetry,
  });

  final L10n s;
  final AsyncValue<List<Map<String, String>>> apps;
  final Set<String> selected;
  final int initialLimit;
  final List<int> limitOptions;
  final void Function(String packageName, bool selected) onToggle;
  final ValueChanged<int> onLimit;
  final VoidCallback onRetry;

  @override
  ConsumerState<_AppsStep> createState() => _AppsStepState();
}

class _AppsStepState extends ConsumerState<_AppsStep> {
  String _query = '';

  String _limitHint(int selectedCount, int pending) {
    final s = widget.s;
    if (selectedCount == 0) {
      return s.t(
        'Pilih app dulu untuk memberi batas.',
        'Select an app first to set a limit.',
      );
    }
    if (pending == 0) {
      return s.t(
        'Semua app terpilih sudah punya batas sendiri.',
        'Every selected app already has its own limit.',
      );
    }
    if (widget.initialLimit == 0) {
      return s.t(
        'Tanpa batas awal. Batas bisa diatur nanti di Kelola aplikasi.',
        'No starting limit. You can add one later in Manage apps.',
      );
    }
    return s.t(
      'Akan dipakai untuk $pending app terpilih yang belum punya batas.',
      'Will apply to $pending selected ${pending == 1 ? 'app' : 'apps'} '
          'without a limit.',
    );
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tokensProvider);
    final s = widget.s;
    final limits = ref.watch(gameProvider.select((g) => g.appLimits));
    final data = widget.apps.asData?.value;
    final installed =
        data?.map((app) => app['packageName']).whereType<String>().toSet() ??
        const <String>{};
    final selectedInstalled = widget.selected.where(installed.contains).toSet();
    final pendingLimits = selectedInstalled
        .where((pkg) => !limits.containsKey(pkg))
        .length;
    final all = [...?data]
      ..sort(
        (a, b) => (a['label'] ?? '').toLowerCase().compareTo(
          (b['label'] ?? '').toLowerCase(),
        ),
      );
    final visible = all.where((app) {
      final haystack = '${app['label'] ?? ''} ${app['packageName'] ?? ''}'
          .toLowerCase();
      return haystack.contains(_query);
    }).toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          s.t('Pilih app yang dipantau', 'Choose apps to monitor'),
          style: t.heading(28),
        ),
        const SizedBox(height: 8),
        Text(
          s.t(
            'Semua scroll dihitung; ke atas juga replay. Rekap mencakup semua '
                'app.',
            'Every scroll counts; scrolling up also adds a replay. Recap covers '
                'all apps.',
          ),
          style: t.body(14, color: t.muted),
        ),
        const SizedBox(height: 20),
        TextField(
          onChanged: (value) =>
              setState(() => _query = value.trim().toLowerCase()),
          decoration: InputDecoration(
            labelText: s.t('Cari nama atau paket', 'Search name or package'),
            prefixIcon: const Icon(Icons.search_rounded),
          ),
        ),
        const SizedBox(height: 12),
        if (data == null)
          widget.apps.isLoading
              ? TokenCard(
                  child: Row(
                    children: [
                      const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          s.t('Memuat daftar app...', 'Loading app list...'),
                          style: t.body(13, color: t.muted),
                        ),
                      ),
                    ],
                  ),
                )
              : TokenCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        s.t(
                          'Daftar app tidak bisa dimuat. Kamu bisa lanjut tanpa '
                              'mengubah pilihan.',
                          'The app list could not be loaded. You can continue '
                              'without changing the selection.',
                        ),
                        style: t.body(13),
                      ),
                      const SizedBox(height: 6),
                      TextButton(
                        onPressed: widget.onRetry,
                        child: Text(s.t('Coba lagi', 'Try again')),
                      ),
                    ],
                  ),
                )
        else ...[
          Text(
            s.t(
              '${selectedInstalled.length} dari ${installed.length} app dipilih',
              '${selectedInstalled.length} of ${installed.length} selected',
            ),
            style: t.body(12, color: t.muted),
          ),
          const SizedBox(height: 8),
          TokenCard(
            padding: EdgeInsets.zero,
            child: SizedBox(
              height: 260,
              child: visible.isEmpty
                  ? Center(
                      child: Padding(
                        padding: const EdgeInsets.all(24),
                        child: Text(
                          s.t(
                            all.isEmpty
                                ? 'Tidak ada app yang bisa ditampilkan di perangkat ini.'
                                : 'Tidak ada app yang cocok.',
                            all.isEmpty
                                ? 'No apps can be listed on this device.'
                                : 'No matching apps.',
                          ),
                          style: t.body(13, color: t.muted),
                          textAlign: TextAlign.center,
                        ),
                      ),
                    )
                  : ListView.separated(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      itemCount: visible.length,
                      separatorBuilder: (_, _) => Divider(
                        height: 1,
                        color: t.ink.withValues(alpha: 0.08),
                      ),
                      itemBuilder: (context, index) {
                        final app = visible[index];
                        final pkg = app['packageName']!;
                        return CheckboxListTile(
                          value: widget.selected.contains(pkg),
                          onChanged: (value) =>
                              widget.onToggle(pkg, value ?? false),
                          title: Text(app['label']!, style: t.heading(14)),
                          subtitle: Text(
                            pkg,
                            style: t.body(10, color: t.muted),
                          ),
                        );
                      },
                    ),
            ),
          ),
          const SizedBox(height: 18),
          Text(
            s.t('Batas awal per app', 'Starting limit per app'),
            style: t.heading(15),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: widget.limitOptions.map((minutes) {
              final active = widget.initialLimit == minutes;
              return TokenButton(
                label: minutes == 0
                    ? s.t('Tanpa batas', 'No limit')
                    : s.t('$minutes menit', '$minutes min'),
                filled: active,
                expand: false,
                onPressed: () => widget.onLimit(minutes),
              );
            }).toList(),
          ),
          const SizedBox(height: 10),
          Text(
            _limitHint(selectedInstalled.length, pendingLimits),
            style: t.body(11, color: t.muted),
          ),
        ],
        const SizedBox(height: 8),
      ],
    );
  }
}

class _PermissionsStep extends ConsumerWidget {
  const _PermissionsStep({required this.s});

  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final status = ref.watch(permissionStatusProvider);

    Future<void> open(
      Future<void> Function(BuildContext, WidgetRef) request,
    ) async {
      await request(context, ref);
      if (context.mounted) ref.invalidate(permissionStatusProvider);
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          s.t('Izin dan persetujuan', 'Permissions and consent'),
          style: t.heading(28),
        ),
        const SizedBox(height: 8),
        Text(
          s.t(
            'Dua izin inti, opsional, dan bisa diubah kapan saja di Profil.',
            'Two core permissions, optional, and changeable anytime in Profile.',
          ),
          style: t.body(14, color: t.muted),
        ),
        const SizedBox(height: 20),
        _PermissionCard(
          title: s.t('Akses pemakaian', 'Usage access'),
          body: s.t(
            'Dibaca: nama app, durasi, jumlah buka. Tidak dibaca: isi layar, '
                'pesan, kata sandi.',
            'Read: app name, duration, open count. Not read: screen content, '
                'messages, passwords.',
          ),
          note: s.t(
            'Tanpa izin ini, app menampilkan data contoh berlabel.',
            'Without it, the app shows labeled sample data.',
          ),
          granted: status.asData?.value.usage,
          checking: status.isLoading,
          onOpen: () => open(requestUsageAccess),
        ),
        const SizedBox(height: 10),
        _PermissionCard(
          title: s.t('Layanan Aksesibilitas', 'Accessibility service'),
          body: s.t(
            'Menghitung scroll di app terpilih. Hanya jenis kejadian dan nama '
                'paket.',
            'Counts scrolls in selected apps. Only the event type and package '
                'name.',
          ),
          note: s.t(
            'Tanpa izin ini, hitungan scroll dan replay berhenti.',
            'Without it, scroll and replay counts stop.',
          ),
          granted: status.asData?.value.accessibility,
          checking: status.isLoading,
          onOpen: () => open(requestAccessibility),
        ),
        const SizedBox(height: 16),
        Text(
          s.t(
            'Dengan menekan Mulai, kamu mengizinkan Screen Time Tracker '
                'mengumpulkan rekap pemakaian di HP ini. Data lokal; bisa '
                'dimatikan atau dihapus di Profil → Privasi.',
            'By tapping Start, you allow Screen Time Tracker to collect usage '
                'summaries on this phone. Data stays local; turn it off or '
                'delete it in Profile → Privacy.',
          ),
          style: t.body(11, color: t.muted),
        ),
      ],
    );
  }
}

class _PermissionCard extends ConsumerWidget {
  const _PermissionCard({
    required this.title,
    required this.body,
    required this.note,
    required this.granted,
    required this.checking,
    required this.onOpen,
  });

  final String title;
  final String body;
  final String note;
  final bool? granted;
  final bool checking;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final s = ref.watch(l10nProvider);
    return TokenCard(
      // Opaque so the hard shadow cannot show through the tinted fill.
      color: t.tint(t.secondary, 0.16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: t.heading(15)),
          const SizedBox(height: 6),
          Text(body, style: t.body(12, color: t.muted)),
          if (granted != true) ...[
            const SizedBox(height: 4),
            Text(note, style: t.body(11, color: t.muted)),
          ],
          const SizedBox(height: 10),
          if (granted == true)
            Row(
              children: [
                Icon(Icons.check_circle_rounded, color: t.hpHealthy, size: 20),
                const SizedBox(width: 8),
                Text(
                  s.t('Aktif', 'On'),
                  style: t.body(12, weight: FontWeight.w800),
                ),
              ],
            )
          else if (granted == null && checking)
            Text(
              s.t('Memeriksa izin...', 'Checking permission...'),
              style: t.body(12, color: t.muted),
            )
          else
            TokenButton(
              label: s.t('Buka pengaturan', 'Open settings'),
              filled: false,
              onPressed: onOpen,
            ),
        ],
      ),
    );
  }
}
