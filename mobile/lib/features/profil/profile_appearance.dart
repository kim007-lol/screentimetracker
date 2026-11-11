part of 'profil_screen.dart';

class _ProfileHeader extends ConsumerWidget {
  const _ProfileHeader({required this.s});

  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final game = ref.watch(gameProvider);
    final pet = game.petFamily ?? PetFamily.momo;
    final name = game.userName.isEmpty
        ? s.t('Teman ${pet.label}', '${pet.label}\'s friend')
        : game.userName;

    return TokenCard(
      child: Row(
        children: [
          Container(
            width: 46,
            height: 46,
            decoration: ShapeDecoration(
              color: t.primary.withValues(alpha: 0.25),
              shape: CircleBorder(
                side: BorderSide(
                  color: t.borderWidth > 0 ? t.borderColor : Colors.transparent,
                  width: t.borderWidth,
                ),
              ),
            ),
            child: Icon(
              pet == PetFamily.drako
                  ? Icons.local_fire_department_rounded
                  : Icons.pets_rounded,
              color: t.ink,
              size: 24,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(name, style: t.heading(19)),
                const SizedBox(height: 4),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    StatusPill(label: 'Lv. ${game.level}'),
                    StatusPill(
                      label: s.stageLabel(game.stage),
                      color: t.secondary,
                    ),
                    StatusPill(
                      label: s.streak(game.streak),
                      color: t.ink.withValues(alpha: 0.08),
                      textColor: t.ink,
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Collection extends ConsumerStatefulWidget {
  const _Collection({required this.s});

  final L10n s;

  @override
  ConsumerState<_Collection> createState() => _CollectionState();
}

class _CollectionState extends ConsumerState<_Collection> {
  Stage? _selected;

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(tokensProvider);
    final game = ref.watch(gameProvider);
    final pet = game.petFamily ?? PetFamily.momo;
    final current = game.stage;
    final selected = _selected != null && _selected!.index <= current.index
        ? _selected!
        : current;

    return Column(
      children: [
        TokenCard(
          padding: const EdgeInsets.fromLTRB(10, 10, 10, 12),
          child: Column(
            children: [
              Companion3D(
                key: ValueKey(
                  'collection-${pet.storageValue}-${selected.name}',
                ),
                pet: pet,
                stage: selected,
                mood: Mood.segar,
                height: 200,
                living: false,
              ),
              const SizedBox(height: 2),
              Text(
                widget.s.t(
                  'Geser untuk memutar, ketuk ${pet.label} untuk animasi.',
                  'Drag to rotate, tap ${pet.label} for an animation.',
                ),
                style: t.body(11, color: t.muted),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Row(
          children: Stage.values.map((stage) {
            final unlocked = stage.index <= current.index;
            final isSelected = stage == selected;
            return Expanded(
              child: Padding(
                padding: EdgeInsets.only(right: stage == Stage.dewasa ? 0 : 8),
                child: Semantics(
                  button: true,
                  enabled: unlocked,
                  selected: isSelected,
                  label: unlocked
                      ? '${widget.s.stageLabel(stage)} ${stage.levelRange}'
                      : widget.s.t('Terkunci', 'Locked'),
                  child: GestureDetector(
                    onTap: unlocked
                        ? () => setState(() => _selected = stage)
                        : null,
                    child: TokenCard(
                      elevated: isSelected,
                      color: isSelected
                          ? t.tint(t.primary, 0.22)
                          : unlocked
                          ? t.surface
                          : t.ink.withValues(alpha: 0.06),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 10,
                      ),
                      child: Column(
                        children: [
                          Icon(
                            unlocked
                                ? (pet == PetFamily.drako
                                      ? Icons.local_fire_department_rounded
                                      : Icons.pets_rounded)
                                : Icons.lock_rounded,
                            size: 18,
                            color: unlocked ? t.ink : t.muted,
                          ),
                          const SizedBox(height: 4),
                          Text(
                            unlocked ? widget.s.stageLabel(stage) : '???',
                            style: t.body(11, weight: FontWeight.w800),
                          ),
                          Text(
                            stage.levelRange,
                            style: t.body(9, color: t.muted),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }
}

class _ThemePicker extends ConsumerWidget {
  const _ThemePicker({required this.s});

  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final active = ref.watch(gameProvider.select((g) => g.themeId));
    return Column(
      children: AppThemes.all.map((theme) {
        final selected = theme.id == active;
        return Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: GestureDetector(
            onTap: () {
              ref.read(gameProvider.notifier).setTheme(theme.id);
              // Overlay native memakai token tema, jadi segarkan bila sedang aktif.
              if (ref.read(gameProvider).pauseEnabled) {
                applyPause(ref, enable: true);
              }
            },
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: ShapeDecoration(
                color: theme.bg,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(
                    theme.notched ? 0 : theme.radius / 1.5,
                  ),
                  side: BorderSide(
                    color: selected
                        ? theme.primary
                        : theme.ink.withValues(alpha: 0.14),
                    width: selected ? 3 : 1,
                  ),
                ),
              ),
              child: Row(
                children: [
                  Container(
                    width: 34,
                    height: 34,
                    decoration: ShapeDecoration(
                      color: theme.primary,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(
                          theme.notched ? 0 : 8,
                        ),
                        side: BorderSide(
                          color: theme.borderWidth > 0
                              ? theme.borderColor
                              : Colors.transparent,
                          width: theme.borderWidth,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(theme.name, style: theme.heading(15)),
                        Text(
                          s.isEnglish ? theme.taglineEn : theme.tagline,
                          style: theme.body(10, color: theme.muted),
                        ),
                      ],
                    ),
                  ),
                  if (selected)
                    Icon(
                      Icons.check_circle_rounded,
                      color: theme.primary,
                      size: 22,
                    ),
                ],
              ),
            ),
          ),
        );
      }).toList(),
    );
  }
}

class _LanguagePicker extends ConsumerWidget {
  const _LanguagePicker({required this.s});

  final L10n s;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(tokensProvider);
    final current = ref.watch(gameProvider.select((g) => g.language));

    Widget option(String code, String label) {
      final active = current == code;
      return Expanded(
        child: GestureDetector(
          onTap: () {
            ref.read(gameProvider.notifier).setLanguage(code);
            // Teks overlay Jeda Sadar dan notifikasi ikut bahasa aktif.
            final game = ref.read(gameProvider);
            if (game.pauseEnabled) {
              applyPause(ref, enable: true);
            }
            if (game.reminderEnabled) {
              applyReminder(ref, enable: true);
            }
          },
          child: Container(
            constraints: const BoxConstraints(minHeight: 48),
            alignment: Alignment.center,
            decoration: ShapeDecoration(
              color: active ? t.primary : t.surface,
              shape: t.shape(
                radiusOverride: t.notched ? 3 : (t.radius > 0 ? 12 : 0),
              ),
            ),
            child: Text(label, style: t.body(13, weight: FontWeight.w800)),
          ),
        ),
      );
    }

    return Row(
      children: [
        option('id', 'Bahasa Indonesia'),
        const SizedBox(width: 8),
        option('en', 'English'),
      ],
    );
  }
}
