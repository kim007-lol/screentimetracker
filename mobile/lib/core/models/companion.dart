import '../balancing.dart';

/// Model domain companion. Aturan mengikuti docs/03 dan docs/08.
enum Mood { segar, lelah, kritis }

enum Stage { bayi, remaja, dewasa }

extension MoodX on Mood {
  String get label => switch (this) {
        Mood.segar => 'Segar',
        Mood.lelah => 'Lelah',
        Mood.kritis => 'Kritis',
      };

  String get speech => switch (this) {
        Mood.segar => 'Hari ini masih aman, lanjut ya!',
        Mood.lelah => 'Udah lumayan banyak scroll nih, istirahat dikit yuk?',
        Mood.kritis => 'Aku butuh istirahat...',
      };

  static Mood fromHp(int hp) {
    if (hp > Balancing.hpFreshAbove) return Mood.segar;
    if (hp >= Balancing.hpTiredFrom) return Mood.lelah;
    return Mood.kritis;
  }
}

extension StageX on Stage {
  String get label => switch (this) {
        Stage.bayi => 'Bayi',
        Stage.remaja => 'Remaja',
        Stage.dewasa => 'Dewasa',
      };

  String get levelRange => switch (this) {
        Stage.bayi => 'Lv. 1-4',
        Stage.remaja => 'Lv. 5-10',
        Stage.dewasa => 'Lv. 11+',
      };

  Stage? get next => switch (this) {
        Stage.bayi => Stage.remaja,
        Stage.remaja => Stage.dewasa,
        Stage.dewasa => null,
      };

  static Stage fromLevel(int level) {
    if (level <= 4) return Stage.bayi;
    if (level <= 10) return Stage.remaja;
    return Stage.dewasa;
  }
}

/// XP yang dibutuhkan untuk naik satu level.
const int kXpPerLevel = Balancing.xpPerLevel;

class Mission {
  const Mission({
    required this.id,
    required this.title,
    required this.durationMinutes,
    required this.bankReward,
    required this.xp,
    required this.hp,
  });

  final String id;
  final String title;
  final int durationMinutes;
  final int bankReward;
  final int xp;
  final int hp;
}

/// Katalog misi offline, sesuai docs/05 bagian Tab Misi.
const List<Mission> kMissions = [
  Mission(id: 'walk', title: 'Jalan Santai', durationMinutes: 20, bankReward: 15, xp: 40, hp: 8),
  Mission(id: 'deepwork', title: 'Belajar / Deep Work', durationMinutes: 30, bankReward: 20, xp: 60, hp: 10),
  Mission(id: 'read', title: 'Membaca Buku', durationMinutes: 30, bankReward: 20, xp: 55, hp: 10),
  Mission(id: 'workout', title: 'Olahraga / Workout', durationMinutes: 20, bankReward: 25, xp: 50, hp: 12),
  Mission(id: 'tidy', title: 'Bereskan Kamar', durationMinutes: 20, bankReward: 15, xp: 35, hp: 8),
];

enum UsageCategory { sosial, hiburan, produktivitas, kerja, belajar, lainnya }

extension UsageCategoryX on UsageCategory {
  String get label => switch (this) {
        UsageCategory.sosial => 'Sosial',
        UsageCategory.hiburan => 'Hiburan',
        UsageCategory.produktivitas => 'Produktivitas',
        UsageCategory.kerja => 'Kerja',
        UsageCategory.belajar => 'Belajar',
        UsageCategory.lainnya => 'Lainnya',
      };
}
