import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/companion.dart';
import '../state/app_state.dart';

/// Pelokalan ringan tanpa kode generator.
///
/// Setiap teks ditulis berpasangan `t('Bahasa Indonesia', 'English')` supaya
/// tidak ada kunci yang hilang dan penambahan bahasa baru tetap mudah dibaca.
/// Rilis pertama wajib menyediakan ID dan EN (prd Bab 12.2).
class L10n {
  const L10n(this.code);

  final String code;

  bool get isEnglish => code == 'en';

  String t(String id, String en) => isEnglish ? en : id;

  String get localeName => isEnglish ? 'en_US' : 'id_ID';

  /// Tanggal panjang untuk header Beranda.
  String get datePattern => isEnglish ? 'EEEE, d MMMM' : 'EEEE, d MMMM';

  String moodLabel(Mood mood) => switch (mood) {
    Mood.segar => t('Segar', 'Fresh'),
    Mood.lelah => t('Lelah', 'Tired'),
    Mood.kritis => t('Kritis', 'Critical'),
  };

  String moodSpeech(Mood mood) => switch (mood) {
    Mood.segar => t(
      'Hari ini masih aman, lanjut ya!',
      'Today is still balanced. Keep it up!',
    ),
    Mood.lelah => t(
      'Udah lumayan banyak scroll nih, istirahat dikit yuk?',
      'That is a fair bit of scrolling. How about a short break?',
    ),
    Mood.kritis => t('Aku butuh istirahat...', 'I really need a break...'),
  };

  String stageLabel(Stage stage) => switch (stage) {
    Stage.bayi => t('Bayi', 'Baby'),
    Stage.remaja => t('Remaja', 'Teen'),
    Stage.dewasa => t('Dewasa', 'Adult'),
  };

  String stageHint(Stage stage) => switch (stage) {
    Stage.bayi => t(
      'Napas canggung, goyang 2.4s',
      'Clumsy breathing, 2.4s sway',
    ),
    Stage.remaja => t(
      'Lincah & ekspresif, goyang 2.0s',
      'Lively & expressive, 2.0s sway',
    ),
    Stage.dewasa => t(
      'Tenang & stabil, goyang 3.0s',
      'Calm & steady, 3.0s sway',
    ),
  };

  String categoryLabel(UsageCategory category) => switch (category) {
    UsageCategory.sosial => t('Sosial', 'Social'),
    UsageCategory.hiburan => t('Hiburan', 'Entertainment'),
    UsageCategory.produktivitas => t('Produktivitas', 'Productivity'),
    UsageCategory.kerja => t('Kerja', 'Work'),
    UsageCategory.belajar => t('Belajar', 'Study'),
    UsageCategory.lainnya => t('Lainnya', 'Other'),
  };

  String missionTitle(Mission mission) => switch (mission.id) {
    'walk' => t('Jalan Santai', 'Easy Walk'),
    'deepwork' => t('Belajar / Deep Work', 'Study / Deep Work'),
    'read' => t('Membaca Buku', 'Read a Book'),
    'workout' => t('Olahraga / Workout', 'Workout'),
    'tidy' => t('Bereskan Kamar', 'Tidy Your Room'),
    _ => mission.title,
  };

  String missionHint(Mission mission) => switch (mission.id) {
    'walk' => t('Jalan kaki tanpa HP', 'Walk without your phone'),
    'deepwork' => t(
      'Fokus belajar tanpa notifikasi',
      'Focused study, no notifications',
    ),
    'read' => t(
      'Baca buku fisik atau e-book',
      'Read a physical book or e-book',
    ),
    'workout' => t(
      'Gerak badan sampai berkeringat',
      'Move until you break a sweat',
    ),
    'tidy' => t('Rapikan meja dan kamar', 'Tidy your desk and room'),
    _ => '',
  };

  /// "3j 24m" pada Bahasa Indonesia, "3h 24m" pada Bahasa Inggris.
  /// Sesi di bawah satu menit tetap tampil sebagai "<1m", bukan "0m".
  String duration(int minutes, {int seconds = 0}) {
    final m = minutes.abs();
    final s = seconds.abs();
    final h = m ~/ 60;
    final r = m % 60;
    final hourUnit = isEnglish ? 'h' : 'j';
    final minuteUnit = 'm';
    if (m == 0 && s > 0) return '<1$minuteUnit';
    if (h == 0) return '$r$minuteUnit';
    if (r == 0) return '$h$hourUnit';
    return '$h$hourUnit $r$minuteUnit';
  }

  String delta(int minutes) {
    if (minutes == 0) {
      return t('sama seperti biasanya', 'same as usual');
    }
    final d = duration(minutes);
    if (minutes < 0) {
      return t('$d di bawah biasanya', '$d below usual');
    }
    return t('$d di atas biasanya', '$d above usual');
  }

  /// "1 hari" / "1 day" tetap tunggal, bukan "1 days".
  String streak(int days) =>
      isEnglish ? '$days ${days == 1 ? 'day' : 'days'}' : '$days hari';

  String hits(int count) =>
      isEnglish ? '$count ${count == 1 ? 'hit' : 'hits'}' : '$count hit';

  String replays(int count) => isEnglish
      ? '$count ${count == 1 ? 'replay' : 'replays'}'
      : '$count replay';

  String scrolls(int count) => isEnglish
      ? '$count ${count == 1 ? 'scroll' : 'scrolls'}'
      : '$count scroll';

  String opens(int count) =>
      isEnglish ? '$count ${count == 1 ? 'open' : 'opens'}' : '$count buka';
}

final l10nProvider = Provider<L10n>(
  (ref) => L10n(ref.watch(gameProvider.select((s) => s.language))),
);
