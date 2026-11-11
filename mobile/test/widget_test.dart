import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:screentime_companion/core/l10n/l10n.dart';
import 'package:screentime_companion/core/models/companion.dart';
import 'package:screentime_companion/core/models/duel_snapshot.dart';
import 'package:screentime_companion/core/models/pet.dart';
import 'package:screentime_companion/core/models/usage.dart';
import 'package:screentime_companion/core/services/history_service.dart';
import 'package:screentime_companion/core/state/app_state.dart';
import 'package:screentime_companion/core/theme/app_tokens.dart';
import 'package:screentime_companion/core/weekly_goal.dart';
import 'package:screentime_companion/widgets/ui.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUpAll(() {
    // Tes tidak boleh memanggil jaringan untuk font.
    GoogleFonts.config.allowRuntimeFetching = false;
  });

  group('Mood harian', () {
    test('batas Segar, Lelah, dan Kritis sesuai docs/03', () {
      expect(MoodX.fromHp(100), Mood.segar);
      expect(MoodX.fromHp(61), Mood.segar);
      expect(MoodX.fromHp(60), Mood.lelah);
      expect(MoodX.fromHp(30), Mood.lelah);
      expect(MoodX.fromHp(29), Mood.kritis);
      expect(MoodX.fromHp(0), Mood.kritis);
    });

    test('setiap mood punya klip idle 3D untuk tiap pendamping', () {
      for (final family in PetFamily.values) {
        final profile = PetRegistry.of(family);
        for (final mood in Mood.values) {
          final clips = profile.idleClipsFor(mood);
          expect(clips, isNotEmpty);
          final prefix = switch (mood) {
            Mood.segar => 'idle_fresh',
            Mood.lelah => 'idle_tired',
            Mood.kritis => 'idle_critical',
          };
          for (final clip in clips) {
            expect(clip, startsWith(prefix));
            expect(
              profile.durationOf(Stage.dewasa, clip),
              greaterThan(Duration.zero),
            );
          }
        }
      }
      expect(PetRegistry.momo.idleClipsFor(Mood.segar), ['idle_fresh']);
      expect(
        PetBehavior.baseClip(family: PetFamily.drako, mood: Mood.lelah),
        'idle_tired',
      );
    });
  });

  group('Tahap evolusi', () {
    test('level memetakan ke wujud yang benar', () {
      expect(StageX.fromLevel(1), Stage.bayi);
      expect(StageX.fromLevel(4), Stage.bayi);
      expect(StageX.fromLevel(5), Stage.remaja);
      expect(StageX.fromLevel(10), Stage.remaja);
      expect(StageX.fromLevel(11), Stage.dewasa);
      expect(StageX.fromLevel(30), Stage.dewasa);
    });

    test('setiap pendamping dan tahap memakai file glb sendiri', () {
      final assets = <String>{};
      for (final family in PetFamily.values) {
        for (final stage in Stage.values) {
          final asset = PetRegistry.of(family).look(stage).asset;
          expect(asset, 'assets/3d/${family.storageValue}_${stage.name}.glb');
          assets.add(asset);
        }
      }
      expect(assets, hasLength(PetFamily.values.length * Stage.values.length));
    });

    test('rantai evolusi berakhir di Dewasa', () {
      expect(Stage.bayi.next, Stage.remaja);
      expect(Stage.remaja.next, Stage.dewasa);
      expect(Stage.dewasa.next, isNull);
    });
  });

  group('Format durasi', () {
    test('helper model tetap konsisten', () {
      expect(formatDuration(0), '0m');
      expect(formatDuration(45), '45m');
      expect(formatDuration(60), '1j');
      expect(formatDuration(204), '3j 24m');
    });

    test('lokalisasi ID dan EN memakai satuan berbeda', () {
      const id = L10n('id');
      const en = L10n('en');
      expect(id.duration(204), '3j 24m');
      expect(en.duration(204), '3h 24m');
      expect(id.duration(0, seconds: 58), '<1m');
      expect(en.duration(0, seconds: 58), '<1m');
      expect(id.duration(0), '0m');
      expect(id.moodLabel(Mood.kritis), 'Kritis');
      expect(en.moodLabel(Mood.kritis), 'Critical');
      expect(en.stageLabel(Stage.remaja), 'Teen');
    });
  });

  group('HP harian', () {
    DailyUsage usage({int minutes = 0, int scroll = 0}) => DailyUsage(
      apps: [
        AppUsage(
          packageName: 'com.example.app',
          label: 'App',
          minutes: minutes,
          opens: 1,
          longestSessionMinutes: minutes,
          category: UsageCategory.lainnya,
          scrollHits: scroll,
        ),
      ],
      source: UsageSource.android,
      baselineMinutes: 200,
    );

    test('tanpa pemakaian HP tetap penuh', () {
      expect(computeHp(usage: usage(), bonusHp: 0), 100);
    });

    test('penalti menit dan hit scroll dihitung', () {
      // 100 menit * 0.2 = 20, 200 hit * 0.03 = 6.
      expect(
        computeHp(usage: usage(minutes: 100, scroll: 200), bonusHp: 0),
        74,
      );
    });

    test('bonus misi menambah HP dan dibatasi 100', () {
      expect(computeHp(usage: usage(minutes: 10), bonusHp: 40), 100);
    });

    test('override manual menang untuk pengujian', () {
      expect(
        computeHp(usage: usage(minutes: 500), bonusHp: 0, override: 12),
        12,
      );
    });
  });

  group('Target mingguan', () {
    final now = DateTime(2026, 10, 28);

    DailyStat stat(DateTime date, int total, int baseline) => DailyStat(
      day: HistoryService.dayKey(date),
      totalMinutes: total,
      scrollHits: 0,
      replays: 0,
      baselineMinutes: baseline,
      topAppLabel: '',
      topAppMinutes: 0,
      hp: 80,
      categories: const {},
    );

    test(
      'hanya menghitung minggu kalender berjalan dan mengabaikan baseline kosong',
      () {
        final stats = [
          stat(now, 100, 120),
          stat(now.subtract(const Duration(days: 1)), 150, 120),
          stat(now.subtract(const Duration(days: 2)), 50, 0),
          // Minggu lalu (Minggu 25 Okt) tidak boleh ikut walau masih 3 hari lalu.
          stat(now.subtract(const Duration(days: 3)), 10, 100),
          stat(now.subtract(const Duration(days: 10)), 10, 100),
        ];
        final progress = weeklyProgressFrom(stats, now: now);
        expect(progress.balancedDays, 1);
        expect(progress.trackedDays, 3);
        expect(progress.target, 5);
        expect(progress.achieved, isFalse);
      },
    );

    test('tercapai saat lima hari seimbang dalam minggu kalender', () {
      final sunday = DateTime(2026, 11, 1);
      final stats = List.generate(
        5,
        (i) => stat(sunday.subtract(Duration(days: i)), 100, 120),
      );
      final progress = weeklyProgressFrom(stats, now: sunday);
      expect(progress.balancedDays, 5);
      expect(progress.trackedDays, 5);
      expect(progress.achieved, isTrue);
      expect(progress.fraction, 1);
    });

    test('membandingkan minggu berjalan dengan minggu lalu', () {
      final stats = [
        stat(now, 100, 120),
        stat(now.subtract(const Duration(days: 1)), 60, 120),
        stat(now.subtract(const Duration(days: 7)), 50, 120),
        stat(now.subtract(const Duration(days: 8)), 40, 120),
        stat(now.subtract(const Duration(days: 20)), 999, 120),
      ];
      final comparison = compareWeeks(stats, now: now);
      expect(comparison.thisWeekMinutes, 160);
      expect(comparison.lastWeekMinutes, 90);
      expect(comparison.thisWeekDays, 2);
      expect(comparison.lastWeekDays, 2);
      expect(comparison.hasLastWeek, isTrue);
      expect(comparison.comparable, isTrue);
      expect(comparison.ahead, isFalse);
      expect(comparison.deltaMinutes, 70);
    });
  });

  group('Kode duel offline', () {
    test('encode dan decode mengembalikan data yang sama', () {
      final snapshot = DuelSnapshot(
        name: 'Raka',
        minutes: 320,
        scrollHits: 480,
        days: 6,
        generatedAt: DateTime(2026, 10, 28, 9, 30),
      );
      final decoded = DuelSnapshot.tryDecode(snapshot.encode());
      expect(decoded, isNotNull);
      expect(decoded!.name, 'Raka');
      expect(decoded.minutes, 320);
      expect(decoded.scrollHits, 480);
      expect(decoded.days, 6);
      expect(decoded.generatedAt, DateTime(2026, 10, 28, 9, 30));
    });

    test('kode rusak atau nilai aneh ditolak', () {
      expect(DuelSnapshot.tryDecode('bukan-kode-duel'), isNull);
      expect(DuelSnapshot.tryDecode(''), isNull);
      expect(
        DuelSnapshot.tryDecode(
          DuelSnapshot(
            name: 'X'.padRight(25, 'X'),
            minutes: 10,
            scrollHits: 10,
            days: 1,
            generatedAt: DateTime(2026, 10, 28),
          ).encode(),
        ),
        isNull,
      );
      expect(
        DuelSnapshot.tryDecode(
          DuelSnapshot(
            name: 'Raka',
            minutes: -5,
            scrollHits: 10,
            days: 1,
            generatedAt: DateTime(2026, 10, 28),
          ).encode(),
        ),
        isNull,
      );
    });
  });

  group('Riwayat harian', () {
    test('kategori di-encode dan di-decode tanpa kehilangan data', () {
      const original = {UsageCategory.sosial: 48, UsageCategory.hiburan: 36};
      final encoded = DailyStat.encodeCategories(original);
      expect(DailyStat.decodeCategories(encoded), original);
      expect(DailyStat.decodeCategories(''), isEmpty);
      expect(DailyStat.decodeCategories('rusak'), isEmpty);
    });

    test('baris database bisa dibaca kembali', () {
      final stat = DailyStat(
        day: '20261028',
        totalMinutes: 120,
        scrollHits: 87,
        replays: 4,
        baselineMinutes: 100,
        topAppLabel: 'TikTok',
        topAppMinutes: 60,
        hp: 72,
        categories: const {UsageCategory.sosial: 60},
      );
      final restored = DailyStat.fromMap(stat.toMap());
      expect(restored.day, '20261028');
      expect(restored.totalMinutes, 120);
      expect(restored.balanced, isFalse);
      expect(restored.categories[UsageCategory.sosial], 60);
      expect(restored.date, DateTime(2026, 10, 28));
    });
  });

  testWidgets('StatBar dirender dengan token tema aktif', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [sharedPrefsProvider.overrideWithValue(prefs)],
        child: MaterialApp(
          theme: AppThemes.brutal.toThemeData(),
          home: const Scaffold(
            body: StatBar(fraction: 0.5, color: Colors.green),
          ),
        ),
      ),
    );

    expect(find.byType(StatBar), findsOneWidget);
  });

  // The Beranda HP/XP card puts StatBar inside a Column, and Column children get
  // loose cross-axis constraints. A Container that only sets `height` then
  // shrink-wraps its child, and the child is the fill (`maxWidth * fraction`) -
  // so at HP 0 and XP 0 the whole bar collapsed into a 4 px stub that read as a
  // stray "0" glyph on screen. The track must span the row at every fraction.
  testWidgets('StatBar mengisi lebar di dalam Column, bahkan saat kosong',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();

    Future<void> pump(double fraction) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [sharedPrefsProvider.overrideWithValue(prefs)],
          child: MaterialApp(
            theme: AppThemes.brutal.toThemeData(),
            home: Scaffold(
              body: Center(
                child: SizedBox(
                  width: 300,
                  child: Column(
                    children: [
                      StatBar(fraction: fraction, color: Colors.green, height: 24),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
    }

    await pump(0);
    expect(tester.getSize(find.byType(StatBar)).width, 300);
    expect(tester.getSize(find.byType(StatBar)).height, 24);

    await pump(0.5);
    expect(tester.getSize(find.byType(StatBar)).width, 300);
    final fill = tester.getSize(find.byType(AnimatedContainer).first);
    expect(fill.width, lessThanOrEqualTo(300));
    expect(fill.width, greaterThan(0));
  });
}
