/// Konfigurasi balancing terpusat (prd Bab 18: angka tidak disebar sebagai
/// literal di banyak tempat). Ubah nilai di sini untuk tuning, bukan di UI.
class Balancing {
  const Balancing._();

  /// XP yang dibutuhkan untuk naik satu level.
  static const int xpPerLevel = 400;

  /// Penalti HP per menit layar dan per hit scroll. Rumus ini Terbuka untuk
  /// balancing (docs/07), jadi seluruh pemakaian angka lewat dua nilai ini.
  static const double hpPenaltyPerMinute = 0.2;
  static const double hpPenaltyPerScroll = 0.03;

  /// Batas mood harian: Segar > 60, Lelah 30-60, Kritis < 30 (docs/03).
  static const int hpFreshAbove = 60;
  static const int hpTiredFrom = 30;

  /// Batas reward istirahat harian, termasuk seluruh sesi parsial.
  static const int restMaxHpGain = 25;
  static const int restMaxXp = 30;

  /// Floor cumulative totals; epsilon only absorbs floating-point addition.
  static int restRewardTotal(double fraction, int maximum) =>
      (fraction.clamp(0.0, 1.0) * maximum + 1e-9).floor().clamp(0, maximum);

  /// Durasi istirahat yang dapat diatur pengguna (docs/03 bagian 2).
  static const int restMinMinutes = 10;
  static const int restMaxMinutes = 20;
  static const int restDefaultMinutes = 15;

  /// Mode demo: 1 detik dihitung 1 menit agar timer misi dan istirahat
  /// bisa diuji tanpa menunggu 30 menit.
  static const int demoSecondsPerMinute = 1;

  /// Batas pemakaian Bank Waktu per transaksi (mekanisme tukar masih Terbuka,
  /// docs/07). Dipakai untuk kuota tambahan pada app yang dipantau.
  static const List<int> bankSpendOptions = [10, 15, 20];

  /// Jeda Sadar: durasi tunda sebelum app target terbuka (prd Bab 10.2).
  static const int pauseMinSeconds = 3;
  static const int pauseMaxSeconds = 10;
  static const int pauseDefaultSeconds = 5;
}
