# 06 — Arsitektur Teknis Android

Dokumen ini mendefinisikan batasan arsitektur teknis, integrasi sistem operasi Android, aturan penghitungan data, dan kepatuhan kebijakan Google Play Store.

---

## 1. Arsitektur Dua Lapisan (Dual-Layer Stack)

Aplikasi dibangun menggunakan pemisahan tanggung jawab yang tegas antara lapisan UI dan lapisan modul native:

```
┌────────────────────────────────────────────────────────┐
│              Flutter Application Layer                 │
│  - Antarmuka 5 Tab & Theme Token System               │
│  - 3D Model Controller (GLB Companion State Machine)  │
│  - Game Logic: HP Balancing, XP Leveling, Bank Waktu   │
│  - Agregasi Data Rekap & Riwayat SQLite Harian         │
└───────────────────────────▲────────────────────────────┘
                            │ Platform Channel (Method/Event)
┌───────────────────────────▼────────────────────────────┐
│              Kotlin Native Android Module              │
│  - UsageStatsManager (Durasi App & Frekuensi Buka)     │
│  - AccessibilityService (Deteksi Scroll & Swipe Feeds) │
│  - Overlay: Floating Pill & Jeda Sadar                 │
│  - Foreground Service (Liveness & Crash Guard)         │
└────────────────────────────────────────────────────────┘
```

> **Aturan Pemisahan**: Jangan menanam logika game atau visual di dalam modul native tracking. Modul tracking hanya bertugas mengumpulkan event mentah dan mengirimkannya ke Flutter.

---

## 2. Pemanfaatan API Android

| Komponen Android | Fungsi dalam Aplikasi | Tingkat Izin |
| :--- | :--- | :--- |
| **`UsageStatsManager`** | Menghitung durasi pemakaian per aplikasi, jumlah pembukaan (*open count*), dan sesi terpanjang. | `PACKAGE_USAGE_STATS` (Pengaturan Khusus) |
| **`AccessibilityService`** | Mendeteksi perpindahan konten/video pendek di Instagram, TikTok, YouTube Shorts, dan Facebook. | Izin Aksesibilitas (Wajib Persetujuan Eksplisit) |
| **`WindowManager` (Overlay)** | Menampilkan Floating Pill live di atas aplikasi lain dan memicu interupsi Jeda Sadar. | `SYSTEM_ALERT_WINDOW` (Tampil di atas aplikasi lain) |
| **`ForegroundService`** | Memastikan sinkronisasi penghitung live tidak dihentikan oleh Doze Mode / Battery Optimization. | `FOREGROUND_SERVICE` dengan persistent notification |

---

## 3. Aturan Penghitungan Scroll (Counting Rules)

1. **Swipe Balik Tetap Dihitung**:
   * Setiap lintasan konten adalah bentuk atensi pengguna yang terpakai, sehingga swipe mundur tetap dihitung sebagai $+1$ hit.
2. **Replay Dicatat Terpisah**:
   * Video atau konten yang diputar ulang dicatat pada metrik tersendiri (*Replay Column*) agar pengguna memahami perbedaan antara konten baru yang dilewati dan konten yang diulang.
   * Transparansi ini mencegah komplain pengguna yang mengira ada hitungan ganda (*double count* bug).
3. **Konfigurasi per Package**:
   * Ambang batas deteksi swipe disesuaikan per nama paket aplikasi target (Instagram, TikTok, YouTube) karena perbedaan struktur layout accessibility-nya.

---

## 4. Kepatuhan Play Store (Policy & Privacy Guard)

* **Prominent Disclosure Wajib**:
  * Sebelum pengguna diarahkan ke pengaturan Aksesibilitas, aplikasi wajib menampilkan modal layar penuh yang menjelaskan: *aplikasi hanya mendeteksi peristiwa scroll untuk kesehatan digital, tidak pernah membaca teks, password, atau pesan pribadi*.
* **Permintaan Izin Bertahap (Progressive Permission)**:
  * Jangan meminta semua izin sekaligus pada satu layar.
  * *Langkah 1*: Minta `Usage Access` untuk rekap dasar.
  * *Langkah 2*: Minta `Accessibility` hanya jika pengguna mengaktifkan pelacak scroll.
  * *Langkah 3*: Minta `Overlay` hanya jika pengguna memilih mengaktifkan Floating Pill.
* **Privasi 100% Lokal**:
  * Seluruh data mentah disimpan di database perangkat (SQLite / Isar). Fitur inti berfungsi penuh secara offline tanpa memerlukan akun atau server backend.

---

## 5. Modul Overlay Jeda Sadar & Riwayat Lokal

### A. Jeda Sadar (Conscious Pause)
* **Bentuk Implementasi**: `PauseService` adalah foreground service tipe `specialUse` yang menggambar **overlay window layar penuh** lewat `WindowManager`, bukan activity baru, sehingga tidak membutuhkan izin tambahan selain *Tampil di atas aplikasi lain* dan *Usage Access*.
* **Deteksi App Terdepan**: Service membaca event `ACTIVITY_RESUMED` terakhir dari `UsageStatsManager` setiap ~1,5 detik, hanya untuk paket yang dipilih (Instagram, TikTok, YouTube, Facebook). Tidak ada pembacaan isi layar.
* **Isi Overlay**: Pertanyaan reflektif, kondisi HP companion, hitung mundur 3–10 detik (dapat diatur di Profil), tombol besar **Batal Buka** dan tombol kecil **Lanjut**.
* **Aturan Cooldown**: Setelah lanjut, app yang sama tidak dijeda lagi selama 15 menit; setelah batal, cooldown 30 detik agar tidak terjadi loop.
* **Tanpa Blokir Paksa**: Hitung mundur selesai berarti pengguna boleh lanjut. Overlay hanya *friction* sadar, sesuai prinsip produk.
* **Batas Harian**: Jika pengguna menetapkan limit per app, saat batas tercapai overlay berubah menjadi layar batas dengan pilihan **Tutup app** atau **Lolos 5 menit**. Tidak ada pemblokiran permanen.

### B. Riwayat Harian Lokal (SQLite)
* Tabel `daily_stats` menyimpan agregat per hari: total menit, hit scroll, replay, baseline, app teratas, HP, dan menit per kategori.
* **Backfill sekali saat izin baru diberikan**: `UsageStatsManager.queryUsageStats(INTERVAL_DAILY)` diagregasi per hari (7 hari terakhir) lengkap dengan baseline 7 hari sebelumnya, lalu dimasukkan dengan mode *ignore* agar tidak menimpa data live.
* Riwayat ini menjadi dasar **tren harian** di tab Rekap, **target mingguan 5 dari 7 hari**, dan perbandingan duel melawan kebiasaan sendiri.
* Data ditulis setiap kali pemakaian dimuat/di-refresh, dan ikut terhapus saat pengguna memilih **Hapus semua data** di Profil.
* Tidak ada data riwayat yang dikirim ke server; semua query berjalan di perangkat.

### C. Pengingat Harian & Berbagi Kartu
* **Pengingat**: `AlarmManager.setInexactRepeating` + `BroadcastReceiver` menampilkan maksimal **satu notifikasi per hari**; jadwal dan teks diatur dari Flutter, dijadwalkan ulang oleh `BootReceiver` setelah perangkat restart.
* **Kartu Rekap**: dirender dari `RepaintBoundary` menjadi PNG lalu dibagikan lewat `share_plus`; tidak ada unggahan ke server.
* **Kode Duel**: ringkasan mingguan di-encode menjadi kode base64 di perangkat, dibagikan manual oleh pengguna, dan disimpan lokal (maksimal 5 teman).
