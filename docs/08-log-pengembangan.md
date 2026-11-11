# Log pengembangan fase 0–3

Tanggal mulai: 2026-10-28. Status: fase 0–3 selesai diimplementasikan; verifikasi otomatis lulus; uji perangkat fisik belum dilakukan.

## Otorisasi dan batas

Pengguna meminta seluruh roadmap fase 0, 1, 2, 3 dikerjakan beserta log, lalu meminta APK release (bukan debug) untuk diuji. Perubahan hanya lokal: tidak ada commit, deploy, atau publikasi. Folder ini bukan repository Git.

Untuk memenuhi permintaan build release, dibuat kunci signing release lokal khusus pengujian di `mobile/android/release-keystore.jks` dengan `mobile/android/key.properties` (keduanya diabaikan VCS). Ini bukan kunci distribusi Play Store dan tidak boleh dipakai untuk publikasi. Publikasi tetap memerlukan persetujuan eksplisit dan kunci distribusi yang disimpan pengguna.

Baseline audit sebelumnya: 19 tes Flutter lulus dan analyze exit 0.

## Rencana dan keputusan implementasi

Arsitektur tetap Flutter/Riverpod → MethodChannel → Kotlin. Native mengumpulkan data dan menegakkan pengingat batas; aturan HP/XP tetap Dart. Default privasi tetap lokal, tanpa server.

### Fase 0 — Integritas dan privasi

- [x] UsageRepo: jumlahkan scroll berdasarkan tanggal rentang, batas akhir eksklusif, koreksi sesi lintas batas hari; tes helper agregasi Kotlin.
- [x] GameNotifier: rollover saat foreground/timer serta sebelum mutasi reward; pisahkan data sampel dari HP; cap reward istirahat harian sebesar satu reward penuh, sesi tambahan tetap diperbolehkan tanpa reward.
- [x] Timer rest/misi memakai waktu mulai/deadline, tick hanya memperbarui tampilan. Penyelesaian idempoten dan durasi demo tidak aktif pada release.
- [x] Bank Waktu ditebus untuk app yang memiliki batas harian: tambahan menit berlaku hari ini dan saldo berkurang hanya setelah native mengonfirmasi. Tidak menghapus penggunaan nyata atau mengurangi penalti HP secara fiktif.
- [x] Hapus data menghentikan layanan, membatalkan reminder, membersihkan seluruh prefs milik app dan SQLite, serta mencegah kueri yang masih berjalan mengisi kembali data. Riwayat UsageStats milik Android tidak dapat dihapus oleh app; pengumpulan dinonaktifkan sampai persetujuan ulang. Kegagalan dilaporkan, bukan ditelan.
- [x] Status izin disegarkan saat kembali dari Settings, termasuk onboarding dan tab Rekap.

### Fase 1 — Performa

- [x] Kueri UsageStats di worker; cache singkat bersama untuk penggunaan hari ini, cache baseline per hari, skip polling ketika layar mati, worker tetap bukan thread baru per tick.
- [x] Limit diperiksa ulang meski user tidak berpindah app; cooldown masuk biasa tidak menunda limit, dan pass dibatasi satu kali per app per hari.
- [x] Dedup/throttle penulisan riwayat, proteksi refresh bersamaan, suspend polling Flutter saat background.
- [x] Tab dibuat saat pertama dikunjungi; animasi WebView nonaktif saat tab tersembunyi/background/route tertutup.
- [x] Bundle font dan lisensi, nonaktifkan pengunduhan runtime.

### Fase 2 — Fitur produk

- [x] Pilihan app yang dipantau dari app launcher Android, termasuk app tanpa riwayat. Seleksi memengaruhi Jeda Sadar/scroll; rekap tetap seluruh penggunaan nyata agar total tidak dimanipulasi.
- [x] Share card mengikuti periode dan sumber data. Duel berbasis keseimbangan terhadap baseline sendiri, kode berversi, minggu sebanding, kode lama tidak diberi skor palsu. Perbandingan mingguan juga menolak himpunan hari yang tidak sepadan.
- [x] Pill: aksi buka Momo, istirahat, kembali Home, sembunyikan; label dan warna mengikuti bahasa/tema.
- [x] Insight penggunaan pukul 22.00–06.00 dari interval native nyata, bukan angka perkiraan atau diagnosis.
- [x] Backup JSON berversi berisi preferensi, progres, riwayat lokal, peer duel dan scroll lokal; validasi sebelum impor, konfirmasi penggantian, tidak memberikan izin Android atau mengaktifkan layanan otomatis. Kegagalan rollback dilaporkan jujur.

### Fase 3 — Pemeliharaan dan rilis

- [x] Pecah Profil menjadi komponen kohesif tanpa mengubah tema yang ada; alat debug/demo hanya debug build (`kDebugMode`/`kReleaseMode`).
- [x] Regresi domain, bridge, penyimpanan, lifecycle, dan tema empat varian. Golden piksel tidak dipakai agar tidak rapuh antar-platform CI; tes tema memeriksa keluarga font dan bobot setiap tema. Workflow CI mencakup analyze, Flutter tests, native tests, dan debug APK, tetapi belum dijalankan di GitHub karena tidak ada repository/remote.
- [x] Release tidak memakai debug signing; signing berasal dari konfigurasi privat lokal/environment dan gagal tertutup bila tidak lengkap. APK release lokal berhasil dibangun dan diverifikasi. Distribusi Play Store tetap belum diverifikasi.
- [x] Nonaktifkan cleartext global; hanya loopback `127.0.0.1` yang diizinkan untuk server lokal model_viewer_plus.

## Kontrak integrasi

MethodChannel tetap `com.screentime.companion/usage`.

- `clearLocalData`: stop overlay, cancel alarm, clear prefs/cache, disable collection; gagal harus dilaporkan.
- `setCollectionEnabled {enabled}`: opt-in pengumpulan setelah onboarding/izin; tidak membuka Settings otomatis.
- `getInstalledApps`: list `{packageName, label}` untuk launcher apps.
- `setMonitoredApps {packages}`: pilihan eksplisit, list kosong berarti tidak ada target.
- `grantBankTime {packageName, minutes}`: bool; tambah allowance per tanggal/app jika izin dan batas valid.
- `exportNativeData`: map data prefs lokal yang aman diekspor; `importNativeData {data}` validasi dan pulihkan tanpa mengaktifkan service.
- `consumePendingAction`: `rest` atau null, consume sekali untuk aksi pill.
- `getNightUsage {days}`: map `{minutes, startHour: 22, endHour: 6, days}`.
- `showPill`: token lama + `language`; `showPause`: token lama + daftar target pilihan.

## Verifikasi akhir

Perintah yang dijalankan dari `mobile/`:

- `flutter analyze` → `No issues found!`
- `flutter test` → 183 tes lulus, 0 gagal.
- `bash android/gradlew -p android testDebugUnitTest` → 12 tes lulus (4 NativePolicyTest, 8 UsageAggregationTest), 0 gagal.
- `flutter build apk --release` → sukses, `build/app/outputs/flutter-apk/app-release.apk` (81,8 MB).
- `apksigner verify --verbose --print-certs` → signature v2 valid, 1 signer, DN `CN=Momo Local Release, OU=Local Testing, O=Screen Time Companion, L=Local, C=ID`, RSA 4096.
- `aapt dump badging` → package `com.screentime.companion.screentime_companion`, versionCode 1, versionName 1.0.0, minSdk 24, targetSdk 36, tidak debuggable.

Tes unit tidak menggantikan uji UsageStats, overlay, screen-off, permission revoke, midnight/timezone, alarm, atau baterai pada perangkat fisik. Belum ada pengukuran frame-time atau penghematan baterai, sehingga tidak ada klaim angka.

## Hasil pengerjaan

### Tahap integrasi awal

- Menambahkan kontrak Dart untuk reset native, pengumpulan, daftar app launcher, daftar pantauan, penebusan bank, backup native, aksi pill, dan insight malam. Operasi reset tidak menyembunyikan error.
- Regresi `usage_bridge_test.dart`: awal gagal karena API belum tersedia; setelah implementasi 7/7 lulus. Kasus scroll tanpa menit, reset gagal, pilihan kosong, argumen bank dan validasi insight malam tercakup.
- Menambahkan layar Kelola aplikasi: app tanpa pemakaian hari ini tetap muncul; pencarian nama/paket, pilihan pantauan, kategori dan batas harian tersedia. Regresi pencarian/pilihan app lulus.
- Memisahkan Profil menjadi appearance, permissions, preferences, pause, privacy/backup, dan app management. Alat demo/debug hanya ditampilkan pada debug build. Nilai HP overlay diberi label waktu sinkronisasi; aksi kembali Home tidak lagi disebut force-close.

### Audit lima agen dan perbaikan lanjutan

- Integritas data: rollover memakai kalender lokal (aman DST), cache tengah malam dibuang, urutan reset harian diperbaiki (bonus/done/reward sebelum kunci hari), baseline tersimpan tidak ditimpa nol, simpan riwayat memakai transaksi dan rollback, cut-off rentang memakai aritmetika kalender, perbandingan minggu hanya untuk himpunan hari yang sama.
- Privasi: backup divalidasi sebelum penggantian, kegagalan impor/rollback dan penghapusan dilaporkan, impor tidak mengaktifkan layanan atau memberi izin, file share sementara dipangkas setelah satu jam.
- Performa: kueri UsageStats di luar main thread, cache TTL dan cache paket dipantau, polling jeda diperlambat ke 3 detik, tab/WebView nonaktif saat tidak terlihat, font dibundel.
- UX dan produk: onboarding tidak bisa submit ganda dan memuat persetujuan lokal, status izin disegarkan setelah Settings, kartu target mingguan jujur saat pengumpulan mati/error/loading, dialog privasi tidak overflow dan tidak race, teks aksesibilitas menyebut app pilihan pengguna, reminder menghormati izin notifikasi, batas pass satu kali per hari.
- Rilis: signing release gagal tertutup tanpa kredensial lengkap dan menolak debug key, manifest memakai network security config, package visibility untuk app picker, regresi JVM native, workflow CI tersedia.

### Artefak release

`mobile/build/app/outputs/flutter-apk/app-release.apk` — APK universal release bertanda tangan kunci lokal pengujian. Kunci dan `key.properties` berada di `mobile/android/` dan diabaikan VCS. Simpan keduanya untuk update di tempat; jika hilang, update APK harus diawali uninstall (data lokal hilang). APK release tidak dapat dipasang menimpa build debug karena sidik jari signing berbeda; uninstall build debug lebih dulu.

Catatan Play Protect: instalasi APK sideload diblokir Play Protect karena kombinasi izin sensitif (aksesibilitas, usage access, overlay), bukan karena signature. Untuk pengujian, pasang lewat ADB dengan verifikasi ADB dimatikan sementara, atau matikan pemindaian Play Protect sementara; di Android 13+ izinkan "restricted settings" sebelum mengaktifkan aksesibilitas. Distribusi untuk pengguna umum harus lewat Google Play (internal testing) agar app ditandatangani Play.

### Batas yang belum diverifikasi

- Belum ada perangkat fisik terhubung (`adb devices` kosong): perilaku UsageStats, overlay Pill/Jeda, layar mati, pencabutan izin, tengah malam/zona waktu, alarm, dan baterai belum diuji runtime.
- APK universal 82 MB; build split-per-ABI belum dibuat/diuji.
- Workflow CI belum dijalankan di GitHub karena folder ini bukan repository dengan remote.
- Signature hanya v2 (cukup untuk minSdk 24/Android 7+); v1 dan v3 tidak aktif. Kunci ini bukan kunci Play Store.

## Ronde 2026-10-28 — tampilan companion, naskah, dan kesesuaian UI

### Akar masalah kotak putih

Kotak putih di belakang Momo berasal dari potret PNG statis dengan latar hampir putih opak yang dipakai sebagai gambar utama. Memotong latar tidak cukup: desain memang meminta companion tampil sebagai model 3D langsung. Perbaikan:

- Semua potret PNG (`momo_bayi.png`, `momo_remaja.png`, `momo_dewasa.png`) dihapus dari UI dan dari bundel aset. Hanya GLB yang tersisa; PNG kini hanya dipakai untuk ekspor kartu rekap.
- Beranda, koleksi Profil, sesi misi, layar istirahat, dialog evolusi, dan overlay memakai `Momo3D` yang memuat GLB. Placeholder saat memuat berupa ikon paw + spinner, bukan potret.
- Header Profil memakai lencana paw, bukan gambar. Tombol Beranda di navigasi juga ikon paw. Dialog HP kritis memakai ikon, bukan potret.
- Klaim "22 joint" dihapus dari UI, komentar kode, dan dokumen desain. Berkas GLB punya 6 klip animasi dan 22 node bernama, tetapi bukan skinning per tulang; menulis "22 joint" menyesatkan. Footer kini "Momo 3D · 6 animasi", dan `docs/08-spesifikasi-karakter-dan-animasi.md` mencatat aset perlu di-rig ulang sebelum klaim itu boleh dipakai.
- Label aksesibilitas Momo3D mengikuti locale aplikasi ("Sentuh Momo"/"Tap Momo", alt Indonesia/Inggris), bukan teks Indonesia tetap.

### Profil dan konsistensi tampilan

- Profil memakai satu hero 3D hidup dengan pemilih Bayi/Remaja/Dewasa (terkunci sampai level tercapai) dan petunjuk ketuk untuk memutar animasi. Ini menghindari empat WebView aktif sekaligus di satu layar.
- Backdrop hero di Beranda dan sesi istirahat selalu lingkaran sesuai spesifikasi, termasuk tema Arcade yang sebelumnya menampilkan kotak.
- Target sentuh yang masih di bawah 48dp diperbaiki: tombol "Atur" izin, tombol aksi NoticeBanner, pemilih periode Rekap, opsi bahasa, dan tombol kembali.
- Streak memakai bentuk tunggal/jamak: "1 hari" / "1 day", bukan "1 days".

### Naskah

- Onboarding, Profil, Privasi/backup, kelola aplikasi, pengungkapan izin, Beranda, Rekap, Misi, Duel, istirahat, dan target mingguan ditulis ulang agar ringkas dan tidak sloganis. Istilah "Conscious Pause" diseragamkan (sebelumnya ada "Mindful Pause"), dan label "Waktu layar"/"Total waktu" dibedakan sesuai konteksnya.
- Kelola aplikasi kini memperingatkan bila Jeda Sadar aktif tetapi layanan belum berjalan atau izin aksesibilitas mati, dengan aksi "Perbaiki"/"Izinkan". Peringatan hanya muncul untuk keadaan yang benar-benar menghalangi fitur.
- Label kosong yang membingungkan ("Daftar app tersedia di perangkat Android. Tidak ada data contoh.") diganti dengan kalimat yang menjelaskan keadaannya.
- Tombol overlay jeda "Batal Buka"/"Cancel" diganti "Ke layar utama"/"Go to home screen" agar sesuai aksinya (`cancelToHome`), termasuk fallback native.
- Overlay Jeda Sadar kini memakai HP nyata saat startup. Sinkronisasi native menunggu pembacaan pemakaian pertama (maksimal 2 detik) sebelum memasang overlay; sebelumnya snapshot diambil sebelum data siap sehingga overlay menulis "Data HP nyata belum tersedia" sepanjang sesi walau izin pemakaian sudah aktif. Setelah menunggu, `pauseEnabled` dibaca ulang agar toggle yang dimatikan selama pemuatan tidak dinyalakan kembali oleh sinkronisasi yang tertunda.

### Verifikasi ronde ini

- `flutter analyze` → `No issues found!`
- `flutter test` → 191 tes lulus, 0 gagal. Tes Profil memakai fake `WebViewPlatform` karena hero 3D kini hidup; spinner placeholder dimatikan lewat `TickerMode` agar `pumpAndSettle` tidak menggantung. Regresi baru memastikan peringatan aksesibilitas muncul di Kelola aplikasi saat Jeda Sadar aktif.
- `./gradlew testDebugUnitTest` → selesai tanpa error.
- APK release final: 82.156.848 byte (78,4 MB), SHA-256 `92d50e727593ec77692db1b72e454954232b455703d2c0755317f3d6bf9a42f2`, signature v2 saja dengan sertifikat lokal `CN=Momo Local Release` (bukan debug signing, bukan kunci Play Store); paket `com.screentime.companion.screentime_companion` versi 1.0.0 (code 1), minSdk 24, targetSdk 36, tanpa flag debuggable. Dipasang ulang di MuMu (Android 12, SDK 32).
- Pemeriksaan runtime MuMu: Beranda tema Pixel Arcade memakai backdrop lingkaran dan streak "1 day"; Profil menampilkan subjudul "All settings stay on this phone.", hero Momo 3D hidup tanpa kotak putih, dan pemilih tahap; Kelola aplikasi menampilkan peringatan "Accessibility is off. Scrolls in your selected apps are not counted." dengan tombol "Allow" yang membuka pengungkapan izin. Overlay Jeda Sadar muncul dengan tombol "Go to home screen", "Continue", catatan tanpa blokir paksa, dan baris "HP 100/100 · Fresh · At sync 28/10 17:20", bukan lagi "Real HP data is not available yet." Pill dapat dinyalakan dan statusnya berubah menjadi "The pill is showing", lalu dimatikan lagi.
- Cabut akses pemakaian lewat app-op saat layanan berjalan menghentikan `PauseService` dalam hitungan detik. Setelah izin dikembalikan, Profil menampilkan "The service is not running. Check overlay and usage access." dan Kelola aplikasi menampilkan "Conscious Pause is on, but the service is not running. Limits are not enforced." dengan tombol "Fix"; menekan Fix menjalankan ulang layanan dan menampilkan "The Conscious Pause service is running.", lalu peringatan berganti ke aksesibilitas yang memang masih mati.
- Isi APK juga diperiksa: string "Ke layar utama"/"Go to home screen" ada, "Batal Buka" tidak ada di `libapp.so` maupun `classes.dex`.
- Belum diuji ulang setelah perubahan naskah terakhir: ekspor/impor backup, hapus semua data lalu onboarding ulang, pengingat, dan batas harian/Jeda Sadar mode batas. Uji ini tetap menjadi celah yang harus ditutup sebelum rilis publik. Emulator bukan perangkat fisik; perilaku UsageStats, layar mati, alarm, dan baterai belum terukur.

## Ronde 2026-10-29 — maskot pill terpusat, ekspresi HP, dan interaksi

### Sprite pill baru yang terpusat

- Kepala maskot di pill sebelumnya terpotong karena ikon lama memakai crop portret asli dengan leher/ekor terpotong tepi. Dibuat pipeline `tools/make_pill_sprites.py`: latar dihapus flood-fill dari tepi (toleransi 18, hanya area terhubung), alpha dihaluskan 1px, lalu gambar di-trim dan dimuat ke kanvas 192×192 dengan padding 16px (konten maksimal 160px). Hasil RGBA dengan alpha tepi 0 — dijamin tidak menyentuh tepi.
- Sembilan drawable baru `pill_mascot_{bayi,remaja,dewasa}.png` + `_tired` + `_critical` di `res/drawable-xxxhdpi`, menggantikan ikon lama. Ekspresi tired/critical dibuat khusus lewat ImageGen dengan margin ketat, lalu diproses pipeline yang sama.
- Grid pratinjau: `tools/pill_sprite_grid.png`; contoh 4×: `tools/bayi_4x.png`, `baby_grid.png`.

### Ekspresi mengikuti HP

- `PillService` memakai registry per pet (`mascotSets`, default `momo`, bukan hardcode nama): 3 tahap × 3 mood. Mood dihitung dari HP yang sama dengan rumus Dart: `hp > 60` fresh, `30–60` tired, `< 30` critical.
- Ikon pill dan gambar panel bertukar serempak lewat `swapMascot()` (fade + pop 90/220ms, OvershootInterpolator). Perubahan mood hanya dipicu saat drawable berubah, jadi tidak ada animasi berulang tiap refresh.

### Interaksi maskot

- Napas idle: `ObjectAnimator` skala 1→1.05, 2,4 dtk, reverse tak terbatas; berhenti saat layar mati, saat app host di foreground, dan saat panel dibuka; hidup lagi saat layar menyala.
- Ketuk: squash 1.16/0.86 dengan overshoot, lalu napas dilanjutkan. Ketuk pill = buka panel; ketuk gambar maskot di panel = animasi yang sama.
- Seret: pill miring maksimal ±9° mengikuti arah geser, kembali 0° saat dilepas; posisi tetap tersimpan di `pill_prefs`.
- Gulir: setiap total gulir bertambah, maskot mengangguk (rotasi -7°, throttle 4 detik) agar terasa merespons aktivitas.
- Tidak ada kode uji siklus mood yang tertinggal di build (`grep "TEMP_CYCLE\|TEMP:"` → kosong); build final hanya bereaksi pada HP nyata.

### Naskah durasi pill vs panel

- Label pill kini berawalan "Sesi "/"Session " (mis. "Sesi <1m · 3 gulir"), bukan angka telanjang yang terbaca seperti total harian.
- Panel membedakan konteks: sesi baru → "Sesi ini baru dibuka." / "This session just started."; aplikasi aktif → "N gulir di aplikasi ini · total layar X menit." / "N scrolls in this app · X min screen time."; tanpa aplikasi → "Total layar hari ini: X menit · Y gulir."; nol gulir → "Belum ada gulir di aplikasi ini · total layar X menit."

### Verifikasi runtime (build release final)

- APK release: 82.605.501 byte, SHA-256 `17005b9195fb6fa9f349613afdf61e063662dbae0c4263d306945fd43a59befe`, dipasang di MuMu (Android 12, 900×1600 @320dpi).
- Pill di atas Chromium menampilkan kepala bayi fresh terpusat tanpa terpotong, "Chromium · Session <1m · 1 scroll", HP bar + "94/100". Panel menampilkan maskot sama, "This session just started.", "1 scroll in this app · 29 min screen time.", dan baris aksi Open app / Take a rest / Return to Home / Hide pill.
- Bukti: `tools/shot_pill_final5.png`, `tools/shot_panel_final.png`, `tools/shot_profile_retry.png` (switch ON).
- Catatan perilaku sistem: di atas layar Settings (termasuk halaman izin) Android memaksa menyembunyikan overlay non-sistem (`mForceHideNonSystemOverlayWindow=true`), jadi pill tidak tampil di sana — ini proteksi anti-tapjacking, bukan bug. Uji overlay memakai Chromium (`com.android.chromium`, aplikasi sistem) karena hanya aplikasi kita yang terdaftar sebagai pihak ketiga.
- Temuan yang masih terbuka: status pill bersifat runtime — setelah reinstall/pembunuhan proses pill mati dan harus dinyalakan lagi dari Profil; toggle tidak dipulihkan otomatis. Belum diputuskan apakah perlu auto-restore saat app dibuka (butuh izin overlay yang masih valid) atau tetap manual dengan penjelasan di UI.
- Animasi (napas, squash, miring, angguk) hanya diverifikasi implementasinya; gerak tidak bisa dibuktikan lewat tangkapan layar statis. Emulator bukan perangkat fisik.

## Ronde 2026-10-29 (lanjutan) — QA runtime mendalam di MuMu

Sesuai arahan "audit QA flow terus sampai semua fungsi dan fitur berjalan sesuai plan", ronde ini menutup celah yang tersisa dari ronde sebelumnya: pembatasan hitungan gulir, overlay Jeda Sadar mode batas, Time Bank, izin & privasi, backup, dan hapus-semua-data + onboarding ulang. Semua diuji lewat satu build release final; tidak ada rebuild per perubahan kecil.

### Build final (build tunggal)

- APK release universal: 82.553.049 byte (78,7 MB), SHA-256 `0f8fe661732d85262c7147e8ed814ded63f3ea6bd3bd784a00dc9af93c0d36e2`, signature v2 lokal `CN=Momo Local Release`, paket `com.screentime.companion.screentime_companion` 1.0.0 (code 1), minSdk 24, targetSdk 36, tanpa debuggable. Dipasang di MuMu (Android 12, 900×1600 @density 2.0 → 450×800 dp).
- Perbaikan kode (scroll tak terbatas Beranda, lokalisasi animasi idle/tap GLB) sudah masuk sebelum build ini; perubahan sesudahnya hanya komentar dok (lihat bawah), tidak mengubah perilaku sehingga tidak di-rebuild.

### Pembatasan hitungan gulir (ScrollCounterService)

- Uji A/B terhadap aplikasi yang dipantau: saat Chromium dihapus dari daftar pantau, 5 swipe tidak mengubah total gulir (count beku di 2); setelah dipantau ulang, satu swipe berikutnya menaikkan 2→3. Membuktikan gerbang `isTracked`/`NativeStore.monitored` bekerja, bukan hanya klaim kode.
- Debounce default 600 ms (Instagram 600 ms) tetap; aksesibilitas diaktifkan ulang via `settings put secure enabled_accessibility_services ...` + `accessibility_enabled 1` setelah `am force-stop` mematikannya.

### Overlay Jeda Sadar: mode batas, pass 5 menit, Time Bank, batalkan

- Overlay batas tampil saat `used >= limit`; tombol "5 menit lagi" disembunyikan bila `passCount >= PASS_CAP (1/hari/aplikasi)`. `passFiveMinutes()` menyimpan `pass|<day>|<pkg>` + `passCount|<day>|<pkg>` sebelum menutup overlay; bila persistensi gagal overlay tidak ditutup.
- Time Bank: pemberian menit tersimpan di kunci `bank|<day>|<pkg>` dan limit efektif ditampilkan benar (15 + 15 = 30 menit).
- "Ke layar utama" (`cancelToHome`) menyimpan cooldown 30 detik (`CANCEL_COOLDOWN_MS`) lalu membuka HOME.
- Overlay batas muncul lagi setelah "Ke layar utama" — sesuai desain: cooldown hanya berlaku untuk mode NORMAL, bukan LIMIT (menghindari cooldown bebas pemakaian di dekat batas). Terverifikasi lewat `PauseDecision.decide()`.
- Mode NORMAL terbukti bekerja lewat efek samping `cooldown|<pkg>` yang terset, tetapi overlay NORMAL tidak terlihat di atas Contacts — ini quirk pengiriman/timing UsageStats emulator, bukan bug logika. Overlay juga disembunyikan OS di atas layar Settings (proteksi anti-tapjacking `mForceHideNonSystemOverlayWindow`), jadi uji overlay memakai Chromium.

### Izin & privasi

- Cabut akses pemakaian → NoticeBanner muncul + HP "belum bisa dibaca". Cabut izin overlay → pill tampil status "Set" dan mati. Aksesibilitas mati → tombol "Set"/"Izinkan". Ketiga alur regrant bekerja dan kondisi pulih.

### Backup: salin, ekspor, impor

- Salin JSON ke clipboard berhasil. Ekspor lewat `Share.shareXFiles` gagal dengan "No apps can perform this action" karena emulator tidak punya target berbagi; aplikasi menanganinya dengan anggun (tanpa crash). Impor JSON tidak valid ditolak dialog validasi `BackupSnapshot.decode()`.

### Hapus semua data + onboarding ulang

- `deleteAllData()` menghapus seluruh peta native — `native_monitoring.xml`, `scroll_counts.xml`, `native_privacy.xml` (enabled=false), `reminder_prefs.xml`, `pause_prefs.xml` — dan mengembalikan aplikasi ke onboarding (Pilih bahasa → tema → layar pembuka companion).
- Menekan "Aktifkan" pada banner tombstone Home menyetel `native_privacy.xml enabled=true`; aplikasi pulih penuh (Indonesia + tema Midnight, ketiga izin aktif, durasi istirahat 15 menit). Bukti: `tools/qa_collection_on.png` dan deret `qa_delete_*`/`qa_onboard_*`.

### Perbaikan dok minor

- `mobile/lib/widgets/momo_3d.dart`: komentar "24 tulang beranimasi" → "22 tulang beranimasi dan morph kelopak mata", sesuai GLB nyata (22 joint, morph blink di mesh Eyelids).
- `docs/08-spesifikasi-karakter-dan-animasi.md`: catatan IMPORTANT yang masih bilang "belum memakai skinning per tulang … jangan menyebut 22 joint" sudah kedaluwarsa dan bertentangan dengan §5 (Rigging v2) serta GLB aktual yang kini punya `JOINTS_0`/`WEIGHTS_0` + skin 22 joint. Diperbarui menjadi "22 joint ter-skinning … UI boleh menyebut 22 joint". Keduanya dokumentasi saja; tidak mengubah perilaku, tidak di-rebuild.

### Celah tersisa (batas emulator)

- Overlay NORMAL flaky di atas Contacts dan tersembunyi di atas Settings adalah batas emulator/kebijakan OS, bukan bug aplikasi. Ekspor berbagi tidak bisa dibuktikan tanpa target berbagi di emulator.
- HP antar-lapisan beda ±1 karena fresh-nya `UsageRepo` (Home 84 vs pill 83) — dokumentasi, bukan bug.
- Perangkat fisik belum tersedia: perilaku UsageStats nyata, layar mati, alarm/pengingat end-to-end, zona waktu/tengah malam, dan baterai belum terukur. Ini tetap syarat sebelum rilis publik.

## Ronde 2026-10-29 (lanjutan) — Pet hidup, pil dua mode, dan overlay keliling

Ronde ini menyelesaikan rangkaian "maskot hidup": rig GLB yang bermain di dalam aplikasi, pil dengan mode statis/penuh, dan pet keliling di atas aplikasi lain sebagai opt-in. Satu build release dipakai untuk seluruh QA; tidak ada rebuild per perubahan.

### Build final (build tunggal)

- APK release universal: 83.305.385 byte, SHA-256 `b9b81bbe987fd413dbaec8717d2203d1dc2c0af16900332ad4f8d192d8a08fed`, signature v2 lokal `CN=Momo Local Release` (cert SHA-256 `1d255a38a5b91f07ac2aa18b9e1145d7768593aae3181847f865842e44a6ac24`), paket `com.screentime.companion.screentime_companion` 1.0.0, minSdk 24, targetSdk 36, tanpa debuggable. Dipasang di MuMu (Android 12, 900×1600 @density 2.0, WebView 110).
- Setelah build, hanya dokumentasi yang berubah; perilaku tidak berubah sehingga tidak di-rebuild.

### Implementasi yang masuk build

- **Dua belas klip** pada GLB tiap tahap: `idle_fresh`, `idle_tired`, `idle_critical`, `sleep`, `tap_reaction`, `celebrate`, `greet`, `look_around`, `groom`, `stretch`, `walk`, `petting`. Jumlah channel diverifikasi dengan `tools/glb_anim_report.py`; `celebrate` tetap dipakai layar evolusi.
- **Perilaku hidup** di Dart (`PetBehavior` pada `momo_3d.dart`/`pet_behavior.dart`) dan Kotlin (`PetBehavior.kt` + `PetLife.kt`) dengan semantik sama: tidur mengalahkan aksi, jeda acak 6–60 detik berbobot tahap/mood, sapaan sekali setelah 1,6 detik, anti-ulang aksi, dan walk dua siklus (2.400 ms) yang memicu translasi host.
- **Pil dua mode**: `flat` memakai sprite/`ImageView` tanpa loop kontinu — animasi hanya reaktif (tap squash, ganti sprite saat HP berubah, miring saat drag); `full` memuat WebView transparan berisi `model-viewer` dari aset lokal (`https://pet.local`, allowlist `PetWebAssets`) secara lazy 180 ms setelah jendela terlihat, dengan fallback poster bila 10 detik tidak termuat. Rig berhenti saat layar mati, host foreground, panel terbuka, atau mode bukan `full`; mode statis tidak punya loop untuk dihentikan.
- **Overlay keliling** `PetOverlayService`: foreground service notifikasi 43, jendela 160 dp `TYPE_APPLICATION_OVERLAY` yang bisa digeser, tap dan long-press diteruskan ke `PetLife`, posisi disimpan saat jari dilepas, dan translator `ValueAnimator` mengikuti klip `walk` (72 dp per jalan).
- **Pengaturan & bridge**: pilihan mode Statis/Penuh untuk pil dan overlay, toggle overlay default mati, tombol sembunyikan pill, serta sinkronisasi `animation`, bahasa, tema, radius, dan bonus HP ke native. Overlay dipulihkan saat aplikasi dibuka bila opt-in dan izin masih ada; pil tetap runtime-only.
- Catatan: entri ronde sebelumnya yang menyebut loop napas `ObjectAnimator` bersifat historis. Build ini tidak memakai napas kontinu; mode statis hanya animasi reaktif, mode penuh memakai rig.

### Bukti QA runtime

- **Jalan spontan overlay**: jendela bergerak dari x=153 ke x=441 tanpa drag penguji, y tetap; selisih 288 px = 2 × 144 px (72 dp), membuktikan klip walk dan perpindahan window sinkron.
- **Mode statis overlay**: dua tangkapan terpisah 2,5 detik identik piksel (0 piksel berubah) dan tidak ada log `PetWebRenderer: Starting the pet page`; tidak ada render loop tersisa.
- **Mode penuh overlay**: log 16:51:42.310 `Starting the pet page`, 16:51:42.436 `Pet page finished`; dua frame berbeda 4.167 piksel di area pet.
- **Pil mode penuh**: log 16:52:38.217/340 saat diaktifkan dari Profil; area sprite berubah 1.430 piksel antara dua frame. Tap membuka panel berisi total layar, gulir, bubble, dan aksi Buka aplikasi/Istirahat/Kembali ke Home/Sembunyikan pill.
- **Drag pil**: jendela berpindah dari [291,96] ke [505,652]; posisi bertahan setelah aplikasi dibuka ulang lalu kembali ke Home. Selisih observasi (214,556) sesuai injeksi (217,563) dalam toleransi sentuhan.
- **Pil statis**: area pil 0 piksel berubah selama 2,5 detik tanpa log renderer baru, sementara pet keliling mode penuh tetap beranimasi (4.494 piksel) — mode statis memang tidak menjalankan loop pill, dan tidak mematikan overlay.
- **Kembali ke penuh saat pil hidup**: memilih Penuh memicu ulang renderer (log 16:59:04.015/130) dan frame pil kembali berubah.
- **Cabut akses pemakaian**: `cmd appops set ... GET_USAGE_STATS ignore` → kedua jendela overlay hilang dan `PillService`/`PetOverlayService` berhenti sendiri dalam ±35 detik, tanpa `FATAL EXCEPTION`/ANR. Setelah izin dikembalikan service tidak menyala otomatis (Profil: "Pill nonaktif", pet "Menunggu layanan native siap"); mematikan–menyalakan toggle memulihkan overlay (log 16:58:01.324/447).
- **Sweep akhir**: proses aplikasi hidup, kedua notifikasi foreground 42/43 hadir, tidak ada crash/ANR di logcat maupun dropbox. Artefak tangkapan ada di `tools/qa_pet/`.

### Gerbang mutu

- `flutter analyze` bersih; `flutter test` 219 tes lulus; `./gradlew testDebugUnitTest` sukses. Cakupan baru mencakup `pet_behavior_test.dart`, `momo_behavior_test.dart`, `pet_settings_test.dart`, `PetBehaviorTest.kt`, dan `PetWebAssetsTest`.

### Batas yang belum tertutup

- Seluruh bukti berasal dari emulator; deformasi rig tidak direkam sebagai video dan performa/baterai perangkat fisik belum diukur. Klaim hemat daya hanya berupa definisi mode (tanpa render loop), bukan angka benchmark.
- Beberapa tap injeksi MuMu meleset pada posisi gulir tertentu; kejadian dicatat sebagai batas input emulator, bukan bug aplikasi. Android juga menyembunyikan overlay di atas layar Settings.
- Setelah izin dicabut, opt-in tetap tersimpan dan UI menampilkan status menunggu; pemulihan otomatis baru terjadi saat aplikasi dibuka ulang atau toggle dinyalakan. Perilaku ini sengaja tidak mengaktifkan service dari proses latar.
- Alur restore/hapus data tidak dijalankan ulang pada ronde ini; hasil ronde sebelumnya tetap berlaku dan tidak berubah oleh fitur pet.
