# Panduan Agent: Pet, Rig, Animasi, Pill, dan Overlay

Diperiksa terhadap sumber dan GLB mobile pada **2 November 2026**.

**Tujuan:** agent yang belum mengenal proyek bisa memahami sistem pet, menambah pet baru tanpa merusak Momo/Drako, serta membedakan implementasi, bukti QA, dan batas yang masih terbuka.

**Status 31 Oktober 2026:** dua pendamping, **Momo dan Drako**, sudah terintegrasi end-to-end: registry aset/klip, pemilihan di onboarding tanpa jalur ganti di UI, perilaku hidup dalam aplikasi, framing kamera per tahap, serta pill statis/penuh. Drako membawa 25 klip rig (29 node, 26 joint termasuk dua tulang kelopak) dengan aksi sayap, ekor, kepala, napas api, dan kedip nyata; Momo tetap 12 klip. Build release final tanggal ini (`65ab60b4…`, §2.5) menggabungkan kelopak/kedip, idle berulang dengan crossfade, dan rotasi horizontal 360° dengan default tegak `0deg` untuk kedua pet. Riwayat build Drako ada di §2.2–§2.3, audit rig di §2.4, dan bukti kelopak/idle/rotasi di §2.5; riwayat build Momo ada di §2.1. Service pet keliling native masih ada, tetapi **kontrolnya tidak diekspos di Profil pada build ini**; pill adalah satu-satunya permukaan melayang yang dapat diaktifkan pengguna. QA ini tidak membuktikan performa/baterai perangkat fisik.

**Status 2 November 2026:** gerak kepala Drako diperbaiki dua lapis. Pertama, bobot wajah bayi/remaja dipindahkan ke `Head` memakai mask z halus dan pivot `Head`/`Neck` diletakkan di pangkal leher yang terlihat; vertex yang masih terikat ke sayap, kaki, ekor, `Root`, atau `Hips` dilewati agar elemen tubuh lain tidak ikut bergerak. Kedua, setelah wajah utuh ternyata klip asli memutar `Head`/`Neck` hampir seluruhnya pada roll dunia sehingga kepala terlihat "meleot" dan leher seperti mengayun; `tools/drako_head_retarget.py` memetakan roll itu menjadi yaw (menoleh) dengan sisa tilt kecil dan follow leher yang dikecilkan. Ketiga tahap—bayi, remaja, dan dewasa—kini memakai aset hasil retarget; wajah, tengkorak, tanduk, dan kelopak berputar sebagai satu unit, sedangkan leher hanya mengikuti 2–5° pada idle/menoleh. Bukti lengkap, angka, dan batas ada di §2.6.

**Batas pekerjaan dokumen ini:** panduan dan catatan bukti, bukan izin commit, deploy, publish, atau perluasan fitur di luar yang diuji.

## 1. Baca ini dahulu

1. Sumber runtime model adalah `mobile/assets/3d/`, bukan folder mockup atau paket lama.
2. Pet dalam aplikasi memakai GLB dengan rig. Mode penuh pill memutar GLB yang sama lewat `WebView` native transparan; mode statis memakai gambar RGBA/pose diam. Keduanya sudah ada dan diuji di build release.
3. Momo sekarang mempunyai 22 joint, 2 node morph kelopak mata, dan **12 klip**. Drako mempunyai 29 node, **26 joint** (24 tubuh + `Lid_L`/`Lid_R`), dua mesh (`Mesh_0` dan `DrakoEyelids`), satu skin, tekstur JPEG tertanam, dan **25 klip** (13 varian idle, sleep, tap, celebrate, greet, petting, walk, wing_flap, wing_show, tail_wag, head_look, fire_puff, happy_bounce). Kedip nyata dibake ke setiap klip Drako. Jumlah tulang pet baru tidak harus sama; kontrak klip dan adapter harus kompatibel.
4. HP, tahap evolusi, state istirahat, bahasa, dan tema berasal dari sistem aplikasi. Jangan menulis HP contoh atau nama salah satu pet sebagai asumsi untuk semua pet.
5. Animasi idle/tap Momo sudah dilokalkan untuk menghindari seluruh tubuh/pipi tertarik ketika satu bagian bergerak. Jangan mengembalikan generator full-body lama tanpa pengujian deformasi. Drako memakai klip yang sudah dibake pada GLB; jangan menjalankan patch Momo pada rig ini. Kedip Drako adalah mesh kelopak ber-skin yang diskalakan, bukan morph kelopak Momo; jangan menyalin channel blink Momo ke rig ini.
6. Pilihan **statis/flat hemat daya** dan **animasi penuh** untuk pill **sudah diimplementasikan** dan tersimpan di preferensi. Pilihan mode tidak menyalakan pill dengan sendirinya; default build adalah statis.
7. Service pet keliling native (`PetOverlayService`) dan state `petOverlayEnabled`/`overlayAnimationMode` masih ada, tetapi build 31 Oktober **tidak menampilkan kontrolnya di Profil**. Profil saat ini hanya mengatur bentuk dan animasi pill. Jangan mengklaim pet keliling dapat diaktifkan pengguna sampai UI-nya dikembalikan dan diuji ulang. Tidak ada klaim per-pixel touch passthrough.
8. Selesaikan seluruh perubahan kode dan tes sebelum membuat satu build release untuk QA. Jangan rebuild per satu fix. Jangan commit atau publish tanpa izin eksplisit.

Urutan membaca untuk agent baru: §2 status → §3 peta kode → §4–6 kontrak aset dan animasi → §7–9 pill, overlay, mode daya → §10–12 penambahan pet, privasi, dan verifikasi.

## 2. Status aktual versus kebutuhan baru

| Bagian | Status sekarang (terverifikasi) | Sisa / batas |
| --- | --- | --- |
| Pet dalam aplikasi | Dua keluarga: Momo (12 klip) dan Drako (25 klip). Idle sesuai mood; setiap varian idle Drako diputar berulang penuh, lalu crossfade 250 ms ke varian lain setelah tahan 6–12 detik, tanpa jeda beku. Sleep, ketuk/elus, selebrasi, aksi spontan state-aware, sapaan sekali per widget, dan playback berhenti saat tab/background/route tidak aktif | Ekspresi mood Drako di sprite pill lebih sederhana daripada Momo (§2.2, §12.3) |
| Rig Momo | Skin 22 joint; `JOINTS_0`/`WEIGHTS_0`; kelopak mata morph; 12 klip | Jangan menjalankan patch/generator Momo pada pet lain |
| Rig Drako | 29 node, 26 joint (24 tubuh + `Lid_L`/`Lid_R`), 2 mesh (`Mesh_0` + `DrakoEyelids`), 1 skin, 3 tekstur JPEG; 25 klip; hierarki sayap `Wing_L/R → Wing_L/R_Tip`, ekor 4 segmen, kaki ber-paw; kelopak nyata berkedip di semua klip dan menutup saat sleep | Framing kamera berbeda per tahap; default tegak `0deg` dan dapat diputar horizontal 360° tanpa crop; kedip berupa kartu kelopak ber-skin, bukan morph wajah; klip sayap bukan morph/wing tambahan |
| Pemilihan pendamping | Langkah onboarding memilih Momo/Drako; nilai disimpan permanen dan tidak ada jalur ganti di Profil | Restore backup saat ini dapat mengosongkan onboarding dan membuka pemilihan ulang; catat sebagai batas |
| Floating Pill | Service native; HP/bar; sesi aplikasi; scroll; bentuk kepala/badan penuh; mode statis (sprite + animasi View) dan penuh (GLB via WebView transparan, lazy start); drag dua sumbu + persistensi posisi; panel dan aksi; registry sprite/body untuk Momo dan Drako | Toggle pill bersifat runtime (tidak auto-restore); tap badan penuh membuka panel, bukan memicu `wing_show` |
| Pet overlay bebas | `PetOverlayService` foreground (`specialUse`, notifikasi 43); jendela 160 dp, draggable, tap = reaksi, long press = elus; jalan pendek; mode statis/penuh; fallback poster; sembunyi saat app foreground/layar mati | **Tidak diekspos di Profil build ini**; tidak di-QA ulang pada ronde Drako |
| Banyak pet | Registry Flutter `PetFamily`/`PetProfile`/`PetRegistry` dan registry native `PetKind`/`PetCatalog` sudah berisi `momo` dan `drako`; bridge membawa `pet` dan divalidasi | Pet ketiga tetap memerlukan aset, klip, kamera, sprite, dan tes baru |
| Mode daya | Pilihan tersimpan `pillAnimationMode`/`overlayAnimationMode` (statis/penuh); default statis; mode statis terbukti tidak memulai WebView/loop pill | Tidak ada pengukuran baterai; label tidak menjanjikan persentase hemat |

Persyaratan pengguna yang sudah jelas dan kini terpenuhi untuk pill: memakai rig untuk gerak hidup dan interaksi; random mengikuti state; Drako dewasa mengepak/membuka sayap dan tampil lebih gagah, sementara tahap kecil tetap lucu; pengguna bebas memilih statis versus penuh. Pet keliling di luar aplikasi belum dapat diaktifkan dari UI saat ini.

### 2.1 Bukti QA build release 29 Oktober 2026 (Momo)

Satu build release dipasang di MuMu (Android 12, 900×1600 @density 2.0, WebView 110). APK 83.305.385 byte, SHA-256 `b9b81bbe987fd413dbaec8717d2203d1dc2c0af16900332ad4f8d192d8a08fed`, signer `CN=Momo Local Release` (cert SHA-256 `1d255a38a5b91f07ac2aa18b9e1145d7768593aae3181847f865842e44a6ac24`). Artefak tangkapan layar ada di `tools/qa_pet/`.

- **Jalan spontan overlay**: jendela bergerak dari x=153 ke x=441 tanpa drag penguji, y tetap; selisih 288 px = 2 × 144 px (72 dp), membuktikan animasi walk dan translasi window sinkron.
- **Mode statis overlay**: dua tangkapan 2,5 detik terpisah identik piksel di seluruh layar (0 piksel berubah), tanpa log `PetWebRenderer: Starting the pet page`; tidak ada loop yang tersisa.
- **Mode penuh overlay**: setelah beralih kembali ke Penuh, log 16:51:42.310 `Starting the pet page` dan 16:51:42.436 `Pet page finished`; dua frame berbeda 4.167 piksel di area pet.
- **Pill mode penuh**: log 16:52:38.217/340 saat pill diaktifkan dari Profil; area sprite pill berubah 1.430 piksel antara dua frame; tap membuka panel statistik/aksi; drag dari (291,96) ke (505,652) tersimpan setelah app dibuka ulang lalu Home.
- **Pill mode statis**: area pill 0 piksel berubah selama 2,5 detik, tanpa log renderer baru, sementara pet keliling tetap beranimasi; membuktikan mode statis tidak menjalankan loop pill dan tidak mematikan overlay.
- **Kembali ke penuh saat pill hidup**: memilih Penuh memicu ulang renderer (log 16:59:04.015/130) dan frame pill kembali berubah.
- **Cabut akses pemakaian**: `cmd appops set ... GET_USAGE_STATS ignore` → kedua jendela overlay hilang dan `PillService`/`PetOverlayService` berhenti sendiri dalam ±35 detik; tidak ada `FATAL EXCEPTION`/ANR. Setelah izin dikembalikan, service **tidak** menyala otomatis: Profil menampilkan "Pill nonaktif" dan pet "Menunggu layanan native siap"; mematikan–menyalakan toggle memulihkan overlay (log 16:58:01.324/447).
- **Statis tes**: `flutter analyze` bersih; `flutter test` 219 tes lulus; `./gradlew testDebugUnitTest` lulus.

Catatan: build ini memakai tema Brutal Pop (terang) saat pengujian; perilaku mode/toggle tidak bergantung pada tema.

### 2.2 Bukti QA build release 31 Oktober 2026 (Drako + perbaikan audit)

Build korektif final di MuMu Android 12, layar 900×1600, density 320, WebView 110. APK **113.695.174 byte**, SHA-256 `290e111dc603d8966715d60f00f7990c981ae05666e55584bf64e2c76bed4cf5`, signer `CN=Momo Local Release` (cert SHA-256 `1d255a38a5b91f07ac2aa18b9e1145d7768593aae3181847f865842e44a6ac24`). Manifest release tidak memiliki atribut `application-debuggable`; bukan build debug. Build ini menggantikan build Drako pertama (113.672.802 byte, SHA-256 `81328e92b49862f05677e5ffcdef50d0b99f987e1c8cb5913c04f9ad2b8d4140`) karena memperbaiki empat idle kritis bayi/remaja. Artefak di `tools/qa_pet/` (`drako_01..41`, `finalbody_frame_1..3`, `bodyframe_1..4`, `staticframe_1..3`, `rig_fix_01..15`).

- **Onboarding/pemilihan**: Momo dan Drako tampil sebagai dua kartu; Drako dipilih, tersimpan, dan langkah berikutnya tidak menawarkan ganti pendamping. (Tangkapan `drako_01..06`.)
- **Drako dewasa di Beranda**: level 11 menampilkan sayap terbuka, idle berubah antar-frame; build ini memakai framing `5.0m`/target `0m 0m 0m`, lalu build tindak lanjut memakai `3.9m` (§2.3). (Tangkapan `adult_wing_*`, `adultseq_1..4`, `drako_19`.)
- **Interaksi tahap kecil**: Drako bayi/remaja memakai framing `5.4m`/target `0m 0.55m 0m`, aksi ketuk dan sayap berjalan tanpa crop. (Tangkapan sesi interaksi bayi/remaja.)
- **Ganti pratinjau tahap di Profil**: memilih Bayi/Dewasa mengganti model dan framing; kartu terpilih sekarang memakai fill opaque. Bukti bug sebelum perbaikan: `drako_32_baby_preview_bug.png`; sesudah: `drako_34_fixed_profile.png`, `drako_35b_profile_top.png`, `drako_36_profile_after_wait.png`.
- **Misi**: kartu Bank Waktu dan kartu evolusi terpilih tidak lagi gelap; ikon tahap Drako memakai api, bukan paw. Bukti: `drako_38_misi_fixed.png`, `drako_39_misi_path.png`, `drako_40_misi_path2.png`.
- **Pill bentuk badan penuh, statis**: sprite Drako dewasa tampil; dua frame 2,5 detik berbeda 0 piksel. `bodyframe_1..4`/`staticframe_1..3`, `drako_30_pill_body_static.png`.
- **Pill bentuk badan penuh, penuh**: renderer hidup; diff 3.183 dan 3.122 piksel pada bbox sekitar `(322,185)-(426,251)` di tiga frame. `finalbody_frame_1..3.png`, `drako_37_pill_after_update.png`.
- **Panel pill**: tap badan penuh membuka panel berisi portrait/nama Drako dan aksi; panel menutup animasi selama terbuka. `drako_27_body_panel.png`, `drako_28_app_after_panel.png`, `drako_41_pet_settings_final.png`.
- **Pill menyembunyi saat app foreground**: setelah kembali ke aplikasi, pill tidak menutupi UI; muncul lagi di atas launcher.
- **Tes**: `flutter analyze` tanpa isu; `flutter test` **249 tes lulus** (4 tes baru membuktikan fill tint opaque); `./gradlew testDebugUnitTest` **43 tes, 0 failure/error**.
- **Audit rig/animasi**: seluruh enam GLB dan 111 klip diperiksa struktural serta dirender; empat idle kritis Drako bayi/remaja ditemukan statis lalu diperbaiki. Rincian dan batas ada di §2.4.
- **Runtime aset hasil perbaikan**: pratinjau Bayi dan Remaja di Profil memuat GLB baru; urutan idle mengubah 7.456–28.615 piksel kartu (termasuk jeda idle), ketuk mengubah 40.887 piksel, tanpa cacat mesh atau crop. Tangkapan `rig_fix_03..14`; Beranda kembali normal sebagai Drako dewasa (`rig_fix_15`).
- **Batas**: semua bukti dari emulator. Mood statis Drako memakai tint + tetes keringat/air mata, jadi tidak sekuat ekspresi Momo; `wing_show` dewasa di dalam pill bentuk badan belum diverifikasi (tap badan membuka panel). Ukuran APK naik dari 83.305.385 ke 113.695.174 byte (+30.389.789) karena tiga GLB Drako sekitar 33,9 MB mentah. Tidak ada klaim kualitas gerak, FPS, atau baterai perangkat fisik.

### 2.3 Bukti QA tindak lanjut 31 Oktober 2026 (data sub-menit + framing dewasa)

Build release tunggal setelah §2.2, dipasang di MuMu Android 12, 900×1600, density 320, WebView 110. APK **113.695.174 byte**, SHA-256 `cb496fc4fb831ecde302cab1a4c44691005aa0db10a299e2ea9c0b158c61dd34`, signer `CN=Momo Local Release` (cert SHA-256 `1d255a38a5b91f07ac2aa18b9e1145d7768593aae3181847f865842e44a6ac24`); manifest release tanpa `application-debuggable`. Hash build korektif idle di §2.2 tetap `290e111d…`; build ini hanya mengubah Flutter/bridge, bukan GLB.

- **Framing Drako dewasa:** preset berubah dari `0deg 82deg 5.0m` menjadi `0deg 82deg 3.9m` dengan target `0m 0m 0m`. Pengukuran read-only `tools/qa_camera_fit.py` atas 25 klip dewasa menghasilkan keterisian siluet maksimum 0,957 lebar dan 0,831 tinggi (nilai >1 berarti crop), jadi semua klip masuk; sebelumnya hanya sekitar 78% lebar dan 65% tinggi. Bukti runtime: `zoom_data_01_home.png`, `zoom_data_30_home_tracker_off.png`. **Angka ini riwayat:** ronde §2.5 menambahkan kelopak/idle, lalu mengganti framing ke tegak `0deg` dengan radius 5,5/5,4/4,55 m dan rotasi geser; lihat §5.3.
- **Akar data tampak kosong:** pemakaian hari itu hanya sesi 58 detik (Play Store/MuMu Store). Native membulatkan ke menit dan Dart membuang baris 0 menit, sehingga total tampil `0m`/`–`. Payload native kini membawa `seconds`; `AppUsage` menyimpan `seconds`/`totalSeconds`; filter mempertahankan baris sub-menit; `topApp` membandingkan detik; formatter menampilkan `<1m` (ID/EN); Rekap tidak lagi menganggap kosong bila masih ada detik. Bukti runtime: `zoom_data_02_home_scrolled.png` (`Total waktu <1m`, `App teratas <1m MuMu Store`) dan `zoom_data_04_rekap.png` (`<1m total layar`).
- **Notice scroll:** Beranda menampilkan banner saat Aksesibilitas mati. CTA membuka penjelasan (`zoom_data_08_tracker_disclosure.png`) lalu pengaturan Aksesibilitas Android (`zoom_data_09_accessibility_settings.png`). Setelah layanan diaktifkan lewat UI Settings dan Chromium dicentang sementara di Kelola aplikasi, Beranda menampilkan 5 hitungan scroll (`zoom_data_25_home_scroll_after.png`). Layanan lalu dimatikan dan Chromium tidak lagi dipantau; `settings get secure enabled_accessibility_services` kosong dan `dumpsys accessibility` tanpa bound service (`zoom_data_30_home_tracker_off.png`).
- **Batas pembuktian Aksesibilitas:** `settings put secure` melalui adb tidak mengikat service di MuMu (Enabled/Bound kosong), sedangkan toggle UI berhasil. Karena itu pembuktian memakai alur pengguna sebenarnya; hitungan scroll tetap mensyaratkan izin Aksesibilitas dan app ada di daftar pantau.
- **Tes:** `flutter analyze` bersih; `flutter test` **251 tes lulus** (tes baru mempertahankan sesi 58 detik dan format `<1m`); `./gradlew testDebugUnitTest` **43 tes lulus**, 0 failure/error.
- **Batas:** semua bukti dari emulator; tidak ada klaim perangkat fisik. Sesi 58 detik adalah data uji, bukan pola pemakaian nyata. Hitungan scroll tidak diuji dengan aplikasi selain Chromium.

### 2.4 Audit rig dan animasi 31 Oktober 2026

Audit read-only mencakup enam GLB di `mobile/assets/3d/`: 111 klip (Momo 3×12, Drako 3×25), 22 joint Momo + morph kelopak, serta 24 joint Drako **pada kondisi audit itu** (sebelum kelopak ditambahkan; keadaan sekarang 26 joint, §2.5). Alat dan bukti:

- `tools/qa_rig_audit.py` memeriksa chunk/accessor, node, skin, jumlah dan normalisasi bobot, duplikasi/persilangan indeks, tekstur, set klip, durasi terhadap registry Dart/Kotlin (±20 ms), loop, channel statis, dan jarak pose varian idle; hasil di `tools/qa_rig/rig_audit.json`.
- `tools/qa_render_glb.py` merender empat frame per klip di Blender 5.2 (320×320, sudut 3/4), lalu `tools/qa_make_sheets.py` menyusun contact sheet per lima klip di `tools/qa_rig/sheets/` dan `sheets_regen/`.
- **Temuan dan perbaikan:** `idle_critical`, `_a`, `_b`, `_c` Drako bayi/remaja punya channel tetapi seluruh nilainya konstan; kontrak paket meminta gemetar, meringkuk, dan ekor gemetar. `tools/drako_animate.py` kini mengganti keempat klip itu di tempat dengan 25 channel, durasi 1,44/1,20 detik, loop yang kembali persis ke pose awal, dan gerak terukur 2.352–11.241 piksel per frame sampel (sebelumnya 0). Pose dasar paket tetap dipertahankan; jarak antar-varian 9,1°.
- **Hasil:** Drako ketiga tahap **0 error**; Momo bayi menyisakan satu error bobot lama (257 vertex, jumlah minimum 0,892669) yang tidak mengubah tampilan 12 klipnya dan tidak disentuh sesuai batas aset Momo. Peringatan IBM Drako bayi/remaja adalah offset translasi seragam (0,55681/0,53422) yang dikompensasi target kamera, bukan skew; `celebrate` memang memutar Root 360° dan kembali ke identitas.
- **Batas saat itu:** pada audit ini Drako belum punya kelopak, sehingga `sleep` masih tampak tanpa mata tertutup; ronde §2.5 menambahkan kelopak nyata. `fire_puff` halus karena tidak ada mesh api. Validator metadata `qoder-gltf` menolak min/max accessor lama Drako bayi/remaja dan panjang array IBM Momo, tetapi Blender dan WebView memuat aset dengan benar; ini cacat metadata, bukan kegagalan runtime. Semua bukti visual dari render offline dan emulator, bukan perangkat fisik.

### 2.5 Bukti QA build final 31 Oktober 2026 (kelopak, idle, rotasi)

Build kelopak/idle selesai 18:39, APK **114.735.482 byte**, SHA-256 `12e2b8494ae2c09c6a4fe4f3d5f73720db79542ad00520bc3fde9903e1ceba36`. Fitur rotasi kemudian menambah gestur dan preset kamera; build final 19:09 memakai ukuran byte yang sama dengan SHA-256 `65ab60b4335ca522649f8a0ea3c1d267e26a2d6de5b05e846a5c36766ea8de3c`. Keduanya bertanda tangan `CN=Momo Local Release` (cert SHA-256 `1d255a38…`), manifest release tanpa `application-debuggable`, dan GLB tidak berubah di antara keduanya (hanya kode Flutter dan target kamera). APK terpasang di MuMu (`base.apk`) memiliki SHA-256 yang sama dengan build final, dan enam GLB di dalam APK cocok byte-per-byte dengan `mobile/assets/3d`. Bukti di `tools/qa_pet/`: `lids_idle.mp4`, `lids_face_sheet.png`, `lids_blink_280/400/540.png`, `lids_frames/`, `rot_01..17`, `tmp_momo_330_1..4`, `final_01..03`; log sweep di `tools/qa_rig/tmp_orbit_{bayi,remaja,dewasa}_final.log` dan `tmp_orbit_momo_{bayi,remaja,dewasa}_{final,idle}.log`.

- **Kedip runtime:** rekaman 12 detik di Beranda Drako bayi memperlihatkan kelopak menutup dan membuka berulang. Frame 532–548 (`lids_blink_540.png`) menunjukkan kedua mata tertutup, frame sebelum/sesudahnya terbuka; `lids_face_sheet.png` memuat urutan yang sama dalam satu lembar. Kelopak adalah mesh `DrakoEyelids` ber-skin, bukan morph (§4.1b). `sleep` menahan kelopak tertutup; bukti tutupnya dari render/audit, bukan rekaman runtime baru.
- **Idle berulang:** video menunjukkan napas/ekor/kepala bergerak dan tidak membeku di akhir klip. Varian idle diputar penuh lalu berganti dengan crossfade 250 ms setelah tahan 6–12 detik; pergantian varian dikunci `companion_behavior_test.dart` dan `pet_behavior_test.dart`, bukan direkam sebagai video formal.
- **Rotasi Drako:** default tegak `0deg`, geser horizontal 0,8°/piksel. Tangkapan 0°, 80°, 176°, 256°, 336°, dan 376° (`rot_01..06`) menunjukkan tubuh/ekor/sayap utuh; ketuk setelah rotasi memicu `tap_reaction` (`rot_07/08`), drag vertikal tetap menggulir Beranda (`rot_09`), dan pratinjau Profil ikut berputar (`rot_10/11`). Tahap dewasa diuji lewat level 11 (`rot_12..14`, framing 4,55 m), lalu data dipulihkan.
- **Momo:** `rot_15..17` dan `tmp_momo_330_1..4` menunjukkan default tegak, samping, dan belakang tanpa potongan yang terlihat; framing Momo tetap 4,8 m. Sweep ketat 12 klip × 13 azimuth menghasilkan max_y hingga 1,120 pada Momo dewasa (`celebrate`/`sleep`), 1,111 pada `idle_critical` 30–60°, dan 1,076 pada `idle_critical` bayi 330°; pose ekstrem bisa melewati batas matematis walau tangkapan runtime di sudut yang diuji utuh. Ini batas yang dicatat, bukan klaim bebas crop total.
- **Sweep Drako:** 25 klip × 6 frame × 13 azimuth, semua `fit=YES` (max_x/max_y: bayi 0,692/0,963; remaja 0,899/0,961; dewasa 0,947/0,653). Ini angka build 31 Oktober; setelah retarget kepala 2 November, sweep ulang di §2.6/§5.3 memberi 0,727/0,963 (bayi), 0,944/0,959 (remaja), dan 0,995/0,653 (dewasa), semuanya `fit=YES`. Jangan menurunkan radius tanpa menjalankan sweep ulang.
- **Tes dan runtime final:** `flutter analyze` bersih, **254** tes Flutter, **43** tes native (`--rerun-tasks`, 0 gagal). Pemeriksaan ulang final 31 Oktober mencatat log `tools/qa_rig/final_qa_flutter.log` dan `final_qa_gradle.log`; XML native 21:29 menunjukkan 5+4+17+6+11 tes, 0 failure/error. Home dipulihkan ke Drako Lv1 setelah QA level 11/Momo (`final_01_home_drako_restored.png`); long press memicu `petting` (`final_02/03`); geser horizontal pada build terpasang diulang dan menghasilkan tampilan samping tanpa crop, lalu app di-restart untuk mengembalikan default tegak. Logcat build final tanpa `FATAL EXCEPTION`/ANR; WebView emulator masih mencatat `GL_INVALID_FRAMEBUFFER_OPERATION`, tetapi frame tetap dirender.
- **Batas:** semua bukti dari MuMu Android 12 900×1600 density 320; tidak ada klaim perangkat fisik, FPS, atau baterai. `sleep` runtime tidak direkam ulang di build final karena klip dan kelopaknya tidak berubah sejak build kelopak.

### 2.6 Bukti QA perbaikan gerak kepala/leher Drako 2 November 2026

**Gejala dan akar masalah.** Ada dua cacat yang bertumpuk. Pertama, wajah dan tengkorak tidak bergerak bersama: kulit wajah bayi/remaja didominasi `Neck` (bayi 2.246 vertex `Neck` vs 169 `Head`), wajah dewasa campuran `Neck`+`Head` hampir 50/50 (11.758 vertex, tidak ada vertex dengan bobot `Neck`>0,5), sedangkan tengkorak/tanduk digerakkan `Head`; pivot `Head` berada di atas tengkorak yang terlihat. Kedua, setelah wajah disatukan lewat bobot, klip asli ternyata memutar `Head`/`Neck` hampir seluruhnya pada sumbu lokal Y. Pada rig ini lokal Y memetakan ke sumbu maju glTF (roll dunia), sedangkan menoleh adalah yaw (lokal Z). Probe `tmp_head_axis_probe.py` pada aset yang beredar sebelumnya mencatat `Head` roll 17,64° dengan yaw 0,02° (bayi `idle_fresh_b` f66), roll −21,65° (`head_look` f10), roll 10,96° (remaja f66), roll −27,06° (remaja `head_look` f10), roll 13,70° (dewasa f66), dan roll −16,31° (dewasa `head_look` f10). Karena itu kepala bulat tampak miring ke samping ("meleot"), dan ayunan leher yang kecil (7–11°) terlihat sebagai pengganti putaran kepala. Pendekatan menggabungkan rotasi `Head` ke `Neck` dibuang karena yang terlihat bergerak justru leher, bukan kulit kepala.

**Perbaikan lapis 1 — bobot dan pivot.** `tools/drako_head_skin.py` dijalankan pada bayi/remaja dengan band dan pivot final: bayi `--z0 0.6819 --z1 0.7819 --head-pivot 0.92 --neck-pivot 0.852`; remaja `--z0 0.96 --z1 1.06 --head-pivot 1.235 --neck-pivot 1.166`. Bobot non-tanduk di dalam band dipindahkan ke `Head` dengan alpha smoothstep, dibatasi 4 influence, dan dinormalisasi; vertex yang masih terikat `Wing_`, `Leg`, `Paw`, `Tail_`, `Root`, atau `Hips` dilewati; bobot tanduk dipertahankan. Pivot `Head`/`Neck` kini berada di pangkal leher yang terlihat (landmark final: bayi `Head` 0,9200/`Neck` 0,8520; remaja 1,2350/1,1660; dewasa tetap 0,3100/0,2400). Kelopak digantung ke `Head` dengan rest world dijaga; channel translasi bone yang pivotnya bergeser di-rebase. Angka 0,7619/0,72 (bayi) dan 1,04/0,98 (remaja) dari percobaan pertama adalah nilai antara dan tidak berlaku lagi.

**Perbaikan lapis 2 — retarget rotasi.** `tools/drako_head_retarget.py` menulis ulang hanya kurva `rotation_quaternion` `Head` dan `Neck` pada seluruh 25 klip ketiga tahap. Setiap key didekomposisi ke Euler lokal XYZ (konvensi `drako_animate.py`), lalu pitch tetap, roll dikali `--head-roll-keep`, dan yaw ditambah `yaw_gain × roll`. Parameter final: `--head-yaw-gain 1.5 --head-roll-keep 0.10 --neck-yaw-gain 0.40 --neck-roll-keep 0.20`. Gerak roll lama menjadi menoleh; sisa tilt ≤10% pada `Head` dan ≤20% pada `Neck`; leher hanya mengikuti 40% yaw hasil itu sehingga tidak lagi mengayun menggantikan kepala. Translasi, skala, 76 channel lain, mesh, bobot, bahan, dan tekstur tidak disentuh. Waktu key dinormalkan ke grid 30 fps (`SNAP_KEY_TIMES`) agar noise float32 125/30 tidak memotong key terakhir; klip yang endpoint-nya berbeda <2e-5 dipaksa kembali ke pose awal. Jumlah key dan durasi tidak berubah.

**Bukti numerik (sumbu dunia).** Tabel sebelum→sesudah dari `axis_before_*`/`axis_after_*` (derajat):

| Tahap / klip / frame | `Head` sebelum | `Head` sesudah | `Neck` sebelum → sesudah |
| --- | --- | --- | --- |
| Bayi `idle_fresh_b` f66 | roll 17,64; pitch −2,03; yaw 0,02 | yaw −18,84; pitch −2,11; roll 2,73 | 7,03 (roll 6,93) → 3,35 (yaw −2,77; roll 1,43) |
| Bayi `idle_fresh_b` f30 | roll −15,51; pitch 1,92 | yaw 16,27; pitch 1,86; roll −2,36 | 6,43 (roll −6,35) → 3,02 (yaw 2,54; roll −1,29) |
| Bayi `head_look` f10 | roll −21,65 | yaw 22,96; pitch −0,02; roll −3,05 | 8,66 (roll −8,66) → 3,87 (yaw 3,46; roll −1,73) |
| Bayi `petting` f42 | pitch 22,64; yaw 14,29; roll 7,13 | pitch 22,03; yaw 4,61; roll 0,40 | 11,72 (pitch 11,06) → 11,33 (pitch 11,01; roll 0,09) |
| Remaja `idle_fresh_b` f66 | roll 10,96; pitch −1,45 | yaw −11,68; pitch −1,47; roll 1,59 | 4,38 (roll 4,33) → 2,06 (yaw −1,73; roll 0,88) |
| Remaja `head_look` f10 | roll −27,06 | yaw 28,70; pitch −0,03; roll −3,82 | 10,83 (roll −10,83) → 4,84 (yaw 4,33; roll −2,17) |
| Remaja `petting` f42 | pitch 24,08; yaw 13,11; roll 6,56 | pitch 23,79; yaw 5,18; roll 0,95 | 11,87 (pitch 11,70) → 11,73 (pitch 11,70; roll 0,43) |
| Dewasa `idle_fresh_b` f66 | roll 13,70; pitch −1,25 | yaw −15,44; pitch −1,31; roll 2,01 | 4,72 (roll 4,64) → 2,27 (yaw −1,85; roll 0,95) |
| Dewasa `head_look` f10 | roll −16,31; pitch 4,81; yaw −0,39 | yaw 18,43; pitch 4,73; roll −2,61 | 5,67 (roll −5,44) → 2,90 (yaw 2,16; roll −1,13) |
| Dewasa `petting` f42 | pitch 20,57; yaw 8,11; roll 9,39 | pitch 20,19; yaw −3,87; roll 1,21 | 10,49 (pitch 10,30) → 10,34 (pitch 10,30; roll 0,42) |

Roll sisa `Head` pada sepuluh sampel tabel ≤3,82°. Follow leher saat idle/menoleh turun dari 4,4–10,8° menjadi 2,1–4,8°, sedangkan nod `petting` tetap mempertahankan pitch 20–24°. `wing_show` bayi memakai yaw −33,39° dengan roll 3,90° (sebelum roll 11,36°); `wing_show` dewasa roll −5,19°→−0,59°. `Chest` tidak berubah: `idle_fresh_b` f66 0,42–0,84°, `petting` f42 4,00–5,30°, dan `wing_show` f34 2,07–9,79° antar tahap pada sebelum maupun sesudah. Tidak ada elemen tubuh lain yang masuk daftar perubahan.

**Bukti struktural final.** `tmp_glb_struct_diff.py` membandingkan GLB sumber (bobot/pivot final) dengan hasil retarget: 29 node, 26 joint, nama mesh/material, POSITION per vertex, dan bones/weights per vertex identik (galat terburuk 4,77e-07 m dan 1,19e-07); 25 nama klip dan waktu key identik; satu-satunya perubahan adalah rotasi `Neck`/`Head` dan rebase lokal kelopak (≤3,08e-05 skala). Rest world `Lid_L`/`Lid_R` terjaga (≤3,91e-07 m; 0,000°). Dua baris `FAIL` tentang parent `Lid` adalah cek hardcoded lama di alat; baris `INFO` menunjukkan kedua sisi sama-sama `Head`. Remaja menyisakan delta IBM 3,83e-05 dari float32 re-export, bukan perubahan rig. `inventory_final_*`: 25/25 klip, 78 channel per klip, `CLIP_INVENTORY_FAILS 0`. `rig_audit_final.json`: Drako 0 error/0 warning; `qoder-gltf validate`: `valid: true`, 0 error, 3 warning metadata per GLB (tangent-space runtime dan dua node skinned non-root). `final_dewasa.glb` 177.316 byte lebih besar dari sumber meski inventaris klip identik; itu layout re-export Blender, bukan konten baru. Log: `diff_retarget_*.log`, `inventory_final_*.log`, `validate_final_*.log`, `rig_audit_final.json`.

**Bukti visual dan framing.** `tmp_make_sheets.py` menyusun `compare_before_after_{bayi,remaja,dewasa}.png` dari `render_before_*` dan `render_*` (idle `f66`/`f30`, `head_look` f10 depan/25° kanan, `petting` f42). Sebelum: tengkorak dan leher miring ke samping. Sesudah: kepala tegak dan menoleh kiri-kanan di atas leher yang tenang; bahu, sayap, kaki, dan ekor tidak ikut. Tidak ada sobekan wajah, kelopak lepas, tanduk tertinggal, atau leher patah. Goresan kecil di tengkuk bayi saat sayap terbuka sudah ada pada geometri asli (`zoom_orig_wing33_back_head.png` vs `zoom_cand_wing33_back_head.png`), bukan regresi retarget. Sweep kamera `tmp_orbit_fit.py` pada GLB final (aspek 1,0 kanvas persegi, 26°, 12 azimuth × 25 klip × 6 frame) semua `fit=YES` (max_x/max_y: bayi 0,727/0,963; remaja 0,944/0,959; dewasa 0,995/0,653). Log: `orbit_retarget_*.log`.

**Tes dan build.** `flutter analyze` bersih dan **254** tes Flutter lulus (`final_analyze_retarget.log`, `final_test_retarget.log`). Ronde ini hanya mengubah GLB, bukan Kotlin/Dart, sehingga 43 tes native tidak dijalankan ulang; hasil terakhir `--rerun-tasks` tetap 0 gagal. Satu build release dilakukan setelah semua aset selesai: APK **114.796.090 byte**, SHA-256 `dc3e02b7b9512c5e78d73458f6597f505b025e66e6f1805b3d8ff2321530e918`, v2 signature valid, `CN=Momo Local Release` (cert SHA-256 `1d255a38a5b91f07ac2aa18b9e1145d7768593aae3181847f865842e44a6ac24`), manifest tanpa `application-debuggable`. `base.apk` di emulator memiliki hash yang sama. Tiga GLB Drako di APK byte-identik dengan `mobile/assets/3d`: bayi 12.031.336 `75210b87…`, remaja 9.907.448 `046bde12…`, dewasa 15.494.420 `09af2242…`. Log: `release_build_retarget.log`, `apk_verify_signature.log`, `apk_verify/`.

**Runtime MuMu.** APK dipasang di MuMu Android 12 900×1600 density 320. `retarget_idle.mp4` (20,02 detik; `runtime_idle_sheet.png`, `runtime_idle_frames/`, full frame `runtime_idle_f04/05/12_full.png`) memperlihatkan kepala menoleh kiri-kanan, kedip, napas, dan ekor tanpa membeku; saat kepala menoleh, dada, sayap, kaki, dan ekor tetap. `retarget_petting.mp4` (13,60 detik; `runtime_petting_sheet.png`) memperlihatkan anggukan elus pada detik 4–6 dengan wajah, kelopak, dan tanduk sebagai satu unit. `retarget_tap.mp4` (6,78 detik; `runtime_tap_sheet.png`) tidak menunjukkan lean samping saat reaksi ketuk. `runtime_01_home.png` adalah Beranda setelah model termuat. Logcat sesi tidak memuat `FATAL EXCEPTION`/ANR. `head_look` tidak dipanggil manual di runtime; buktinya render offline dan probe sumbu.

**Batas.** Bukti berasal dari Blender headless dan MuMu Android 12 900×1600 density 320; tidak ada klaim perangkat fisik, FPS, atau baterai. Hanya kurva rotasi `Head`/`Neck` yang berubah; jumlah klip, key, material, tekstur, posisi vertex, dan index buffer tidak berubah. Dewasa tidak menjalani perbaikan bobot/pivot—hanya retarget—sehingga bila masih ada keanehan bentuk di tahap itu, itu warisan geometri. `sleep` tidak direkam ulang di runtime; bukti loop/kelopaknya berasal dari audit klip dan render. Semua klip Drako tetap 78 channel.

### 2.7 Bukti QA repaint tekstur Drako 2 November 2026

**Gejala dan akar masalah.** Setelah gerak kepala diperbaiki (§2.6), Drako bayi di Beranda masih dibaca sebagai anjing, bukan naga. Investigasi terhadap atlas baseColor 2048² yang dipanggang di mesh membuktikan penyebabnya murni tekstur, bukan geometri, rig, atau klip. Dua hal yang menciptakan bacaan "anjing": (1) mata punya crescent sklera putih lebar di sekeliling iris cokelat-amber yang kusam dan condong ke biru, sementara kartu referensi `drako_bayi_card.png` menunjukkan iris emas berbingkai gelap dengan sklera hanya setipis garis; (2) kulit merah adalah plastik datar tanpa struktur sisik, padahal kartu referensi penuh sisik kecil padat. Tidak ada channel, bobot, atau vertex yang bersalah—`DrakoEyelids` dan 78 channel klip tetap apa adanya.

**Metode.** Repaint dilakukan pada file JPEG hasil ekstraksi, lalu dipasang kembali lewat putaran Blender; tidak ada penambalan byte GLB. Pipeline tiga langkah (dari root proyek):

```bash
python tools/drako_texture_extract.py <src.glb> <tex_dir>
python tools/drako_face_repaint.py <tex_dir> <tex_out> --scales 0.22 --cell 13 \
  --jitter 0.30 --size-jitter 0.34 --warp 0.38 --band 0.15 \
  --face-w 1.30 --groove-w 1.00 --shadow-w 0.60 \
  --sclera-band 5.0 --lift 1.0 --halo 30 --feather 18 --quality 95
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup \
  --python-exit-code 1 --python tools/drako_texture_reapply.py -- \
  <src.glb> <out.glb> <tex_out>/1_Image_0.jpg <tex_out>/2_Image_1.jpg <tex_out>/0_Image_2.jpg
```

Yang dilakukan tiap langkah: ekstraksi menyalin payload `Image_0/1/2` apa adanya (read-only pada GLB); repaint menghangatkan keluarga `iris` di dalam hull cembung bola mata ke arah emas (`R*1,10+14`, `G*1,16+8`, `B*0,78`, glow radial, dibaurkan dengan `lift`), memperdalam pupil ke `RING_DARK`, memotong crescent sklera menjadi `keep_band` piksel dan mengubah sisanya menjadi kelopak gelap, lalu mengalikan medan sisik prosedural hanya ke piksel kulit merah; reapply menukar image datablock dan menunjuk ulang setiap node `TEX_IMAGE` yang memakai image lama. Cincin emas, bintang, dan highlight sudut mata yang sudah dilukis tidak disentuh—mengganti iris seluruhnya justru memipihkan bintang dan mengukur lebih buruk terhadap kartu.

Parameter di atas adalah hasil seleksi, bukan default. Tiga mekanisme dipakai untuk membunuh bacaan "rajutan/waffle" pada sisik: jitter posisi per sel, variasi radius per sel, dan warp domain frekuensi rendah, ditambah penyeimbangan ulang face/groove/shadow (`--face-w 1.30 --groove-w 1.00 --shadow-w 0.60`; default `1.15/1.70/1.10` terlalu dalam alurnya sehingga terlihat sebagai cetakan). `tmp_scale_grid.py` menjalankan pipeline nyata per varian dan menempelkan crop tubuh + wajah di sebelah kartu referensi; grid yang menyimpang dari pass shipped tidak dipakai sebagai bukti.

**Relief dijaga tetap jauh dari mata.** Hull bola mata yang didilatasi `--halo 30` dan dibaurkan `--feather 18` menjadi area kulit telanjang tempat medan sisik diredam (`shade = 1 + (shade-1) * (1 - bare*1,06)`). Tanpa itu, pola sisik berjalan masuk ke rongga mata—separat dari alasan mengapa repaint awal masih terbaca sebagai pola pabrikan. Untuk dewasa, `find_eyes` benar-benar tidak menemukan bola mata (atlas dewasa tidak punya piksel putih sama sekali), jadi halo diturunkan dari keluarga `iris` (`HALO from iris instead of hulls`).

**Bukti struktural.** `tools/qa_rig/tmp_repaint_audit.py` membandingkan GLB lama (dari `dragon_look/backup_shipped_20261102/`, byte-identik dengan aset yang beredar sebelum ronde ini) dengan GLB hasil repaint, dan membandingkan tiap invarian pada toleransi yang dibenarkan oleh delta terukur dari round-trip no-op:

| Tahap | Hasil audit | Delta terburuk yang terukur |
| --- | --- | --- |
| Bayi | 90 PASS / 0 FAIL | TEXCOORD_0 0; POSITION 3,58e-07 m; WEIGHTS_0 1,79e-07; IBM 3,58e-07; key time 0 s; node rot 1,67e-05° |
| Remaja | 90 PASS / 0 FAIL | TEXCOORD_0 0; POSITION 8,34e-07 m; WEIGHTS_0 1,79e-07; IBM 1,94e-05; key time 0 s; node rot 4,95e-05° |
| Dewasa | 89 PASS / 1 FAIL (terdokumentasi) | TEXCOORD_0 0; POSITION 2,38e-07 m; WEIGHTS_0 1,19e-07; IBM 3,16e-06; key time 0 s; node rot 2,40e-05° |

Ketiganya lolos cek `exactly the baseColor image changed` dan `metallicRoughness and normal untouched`: hanya payload `Image_0` yang berbeda, `Image_1`/`Image_2` identik. Atlas berubah pada 90,1% / 92,6% / 95,0% texel dengan rata-rata delta absolut 6,28 / 8,48 / 6,64—mencerminkan repaint yang menyeluruh, bukan tambal-sebagian. Nama set klip (25), target channel (78 per klip), set joint, dan seluruh durasi klip tetap cocok dengan registry `pet.dart` dalam 60 ms.

**Dua deviasi dewasa.** (1) Tidak ada repaint mata: atlas dewasa tidak memuat piksel putih sama sekali, jadi mata tidak dapat ditemukan maupun di-lid; dewasa hanya mendapat sisik. (2) Klip `sleep` kehilangan key penutup loop: 126 → 125 key pada seluruh 78 channel, durasi 4.166,7 → 4.133,3 ms (34 ms). Penyebabnya pembulatan frame Blender—key terakhir di 124,99999 s runtuh ke frame 124 saat ekspor. Ini diterima dan didokumentasikan alih-alih diperbaiki dengan `export_force_sampling`, yang akan me-rebake 1.014/702/1.170 channel dan berisiko mengubah gerak yang sudah diverifikasi di §2.6. Efeknya hanya jeda 34 ms di ujung klip yang kelopakanya tertutup sepanjang klip; audit sekarang memisahkan temuan ini (`every channel keeps its key count`) dari error waktu/key-value agar sisa kurva tetap terverifikasi, dan durasi tetap diukur dari key yang dipertahankan.

**Kedua deviasi di atas tidak lagi berlaku.** Ronde 3 November (§2.8) mengecat mata dewasa sampai cocok dengan kartu referensi dan memulihkan key penutup `sleep`; keduanya sekarang diverifikasi oleh gerbang otomatis, bukan diterima sebagai toleransi. Akar masalah frame rate yang menyebabkan deviasi (2) juga sudah dihapus di level ekspor, bukan ditambal per klip. Paragraf ini dipertahankan sebagai riwayat diagnosis.

**Kelopak mata tidak ikut berubah warna.** Semua vertex `DrakoEyelids` hanya memakai empat koordinat UV — sudut atlas (0,0), (0,1), (1,0), (1,1) — sehingga tiap segmen kelopak tidak memetakan wilayah kulit ber-sisik, melainkan menyapu diagonal utama atlas sebagai gradien antar-sudut. Texel sudutnya sendiri memang berubah (terbesar 31/255 pada bayi di (2047,2047)), tapi perubahannya saling meniadakan: rata-rata warna sepanjang diagonal yang disapu bergeser ≤1,5/255 per channel pada ketiga tahap — bayi R160,1 G60,8 B37,3 → R159,3 G60,6 B36,9; remaja R169,8 G72,4 B55,0 → R168,1 G70,9 B53,3; dewasa R141,7 G53,1 B39,4 → R140,2 G52,3 B38,6. Runtime mengonfirmasi: `blink_and_tap.png` menangkap kedip di kartu Koleksi Profil dengan kelopak merah gelap halus, tanpa sobekan atau bocor putih.

**Bukti visual.** `stage_bayi_ab.png`, `stage_remaja_ab.png`, `stage_dewasa_ab.png`, dan `stage_all_close.png` disusun pada kamera aplikasi (radius/target dari `pet.dart`: bayi 5,5 m/0,55 m; remaja 5,4 m/0,43 m; dewasa 4,55 m/−0,06 m) dan close-up 2,2 m; `dewasa_close_ab.png` membandingkan close-up dewasa. Bayi dan remaja kini terbaca sebagai naga pada kamera aplikasi: kulit bersisik, cincin mata emas, sklera tinggal garis. Dewasa mendapat sisik di kepala, sayap, dan punggung. `eye_sweep_bayi.png` adalah sweep `keep_band`/`lift` yang dipakai memilih `--sclera-band 5.0`.

**Build dan runtime.** Ronde ini tidak mengubah Dart atau Kotlin, hanya aset GLB, satu alat Python baru, dan dokumen; `flutter analyze` tetap bersih dan **254** tes Flutter lulus (`analyze_test_repaint.log`). Tiga GLB dipasang ke `mobile/assets/3d/` (bayi 11.936.480 `7d4a1f3c…`, remaja 9.931.100 `45d27a31…`, dewasa 14.867.732 `29a9f2be…`), Momo tidak disentuh (`a3442db2…`, `c2263f0e…`, `07b46168…`). Validator `qoder-gltf` pada ketiga aset final: `valid: true`, 0 error, 3 warning metadata per GLB (sama seperti sebelumnya). Satu build release: APK **114.105.246 byte**, SHA-256 `4c561a15daaf07117567106b58db5e15b100f0d397128b2a7966b70fa142a5ac`, v2 signature valid, `CN=Momo Local Release`, tanpa `application-debuggable`; keenam GLB di dalam APK (termasuk tiga Momo) byte-identik dengan folder aset (`apk_verify_signature.log`, `apk_verify/`). Di MuMu Android 12 900×1600 density 320: `r01_launch.png` Beranda dengan Drako bayi ter-repaint, `repaint_idle.mp4` 16 detik + `idle_sheet.png` (6 frame; frame 4 menangkap kedip), `rotate_check.png` menunjukkan gestur putar masih berfungsi dan sisik terbaca dari depan/samping/belakang, `r04_profil.png`/`r05_pet_anim.png` kartu Koleksi Drako, `blink_and_tap.png` kedip + reaksi ketuk, dan `home_before_after.png` membandingkan Beranda build 14:12 dengan build 19:19 pada kamera yang sama. `Fully drawn +1s753ms`; logcat sesi 0 `FATAL EXCEPTION`.

**Batas.** Sprite pill (`pill_mascot_drako_*`) dan poster roaming (`pet_roam_drako_*`) dibuat `make_drako_sprites.py` dari potret tahap di paket desain, bukan dari GLB, jadi keduanya tidak terdampak repaint dan tidak perlu diregenerasi—repaint justru mendekatkan model 3D ke art yang sudah ada. Pada ronde ini tahap remaja/dewasa memang belum dapat dicapai di runtime pada Lv. 1 (`companion.dart:49` memetakan level→tahap; slot Profil terkunci `???`), jadi bukti kedua tahap saat itu adalah validator + audit struktural + render pada kamera aplikasi, bukan tangkapan layar aplikasi; ronde 3 November (§2.8) menambahkan lompatan level khusus-debug dan membuktikan kedua tahap itu di aplikasi. Mode pil "Penuh" memakai pemutar GLB yang sama yang sudah dibuktikan dua kali di aplikasi (Beranda dan Profil); pil tidak diaktifkan pada ronde ini karena memerlukan izin overlay + pelacak aksesibilitas. Bukti hanya dari MuMu: tidak ada klaim perangkat fisik, FPS, atau baterai.

### 2.8 Bukti QA ronde 3 November 2026: mata dewasa, loop `sleep`, kelopak desync, dan bukti runtime remaja/dewasa

**Permintaan.** Tiga "deviasi diterima" di §2.7 ditarik kembali dan harus benar-benar diperbaiki: (1) mata dewasa harus sesuai kartu referensi, (2) key penutup loop `sleep` dewasa harus kembali, (3) tahap remaja dan dewasa harus dibuktikan di aplikasi, bukan hanya lewat render offline.

**Akar masalah pertama ada di frame rate ekspor, bukan di klipnya.** `scene.render.fps` dipakai exporter sebagai laju sampling, dan sesi Blender `--factory-startup` berjalan pada 24 fps sementara seluruh klip Drako ditulis di grid 30. Karena itu key bisa mendarat di luar grid dan key terakhir yang runtuh ke frame pembulatan akan hilang. `tools/glb_export.py` sekarang menetapkan `ASSET_FPS = 30.0` dan `set_frame_rate()` menerapkannya saat impor maupun ekspor; Blender 5.x menolak float (`RenderSettings.fps expected an int type, not float`), jadi bagian bulatnya masuk `render.fps` dan sisanya dibawa `render.fps_base` sehingga laju efektif tetap 30. Perbaikan ini ada di level pipeline, bukan ditambal per klip.

**Key time dipaksa kembali ke grid 30.** `loop_restore_dewasa_v10.json`: 3.900 key di-snap, deviasi terbesar 3,815e-06 frame pada toleransi 0,02 frame, `failures: []`. Klip `sleep` dewasa sebelum = key terakhir frame 124, seam 0,00161904; sesudah = frame 126, seam 0,0 — 260 key disisipkan untuk menutup gap 2 frame. Di aset shipped, `sleep` dewasa sekarang 9.906 key / 78 channel = 127 key per channel, durasi 4,2000 s, dan terverifikasi `closed`.

**Kelopak dewasa ternyata desync — ini temuan baru, bukan bagian permintaan.** Audit `final_lid_sync.log` terhadap aset shipped 2 November (`########## shipped adult (before)`) menemukan 24 dari 25 klip punya kurva `Lid_L` dan `Lid_R` dengan waktu sama tetapi nilai berbeda (d 6,3–7,5; hanya `sleep` yang sinkron). Artinya kedua kelopak berkedip tidak sama rata sepanjang katalog. Setelah rebuild, ketiganya `LID_SYNC PASS - 25/25 clips drive Lid_L and Lid_R with the same curve (agree within 1e-04 on every sample)`.

**Geometri kelopak dewasa dibangun ulang, dan itu yang mengubah mata.** Kelopak shipped 2 November = 2.280 + 152 vertex; hasil ronde ini = 2.392 + 184 vertex (`gate_finalists.log`). Kelopak lama menyelimuti bola mata sehingga apa pun yang ada di atlas tertutup. `lid_fix_dewasa_v9.json` mengukur hasil barunya: coverage 100,0% covered / 100,0% fronted, saat puncak kedip 29/29 vertex bola mata tersembunyi (100,0%) dengan standoff rata-rata 9,89 mm dan maksimum 12,82 mm, dan saat rest 0 vertex tersembunyi.

**Mata dewasa adalah hasil gabungan, bukan repaint tekstur hari ini.** Diff atlas shipped→v10 (`tmp_atlas_diff.py atlas_ship atlas_v10`) hanya menemukan **1.243 texel (0,030%)** yang berbeda lebih dari 16/255, mengelompok di y700–749 (622) dan y1700–1799 (621) — persis pulau mata — dan arahnya menggelap (rata-rata RGB 151,6/102,4/66,0 → 121,1/72,1/35,7), yaitu cincin gelap + pupil yang diperdalam. Iris amber-nya sudah ada di atlas 2 November. Yang membuatnya terlihat adalah kelopak baru yang tidak lagi menutupi bola mata. Karena itu kalimat §2.7 "atlas dewasa tidak memuat piksel putih sama sekali, jadi mata tidak dapat ditemukan maupun di-lid" harus dibaca sebagai **kegagalan locator**, bukan bukti bahwa iris dewasa pucat: `dewasa_base_eye_islands.json` mengukur `amber_blob_px: 1` pada titik yang salah (`distance_bone_to_eye` 0,1097 dan 0,2123), sedangkan `dewasa_now_eye_islands.json` mengunci pulau yang benar lewat bobot tulang (`distance_bone_to_eye` 0,0258, `ring_amber_density` 0,4896).

**Statistik ambang warna dicoba dan ditolak sebagai bukti.** Tiga classifier dipakai dan ketiganya gagal: "amber" (R≥150, G≥90, B≤110) dan "gold" (R≥170, G≥110, B≤120) juga mengenai tandang krem dan api dekoratif; aturan ramp jenuh (R≥140, R−G≥55, G−B≥25, B≤130) masih mengenai api ornamen; scan atlas penuh didominasi tandang (4,5–4,6% "iris" tersebar x0..2047); pengukur otomatis pita mata malah mengunci api dada. Kotak longgar di sekitar landmark memberi ship 11,38% vs v10 11,06% — selisih 404 texel, jauh di bawah noise. Yang meyakinkan adalah **lembar crop** `dewasa_iris_ab.png`: aset 2 November bermata pucat keruh, v10 beriris amber jenuh dengan pupil celah gelap, dan kelopak tertutup berwarna merah pada v10 vs pucat pada aset lama. Kesimpulan yang harus dipertahankan agent berikutnya: render adalah bukti, ambang warna bukan.

**Penjaga `SKIN_LOST` ditambahkan karena bug yang nyaris lolos.** Pass kelopak (`tools/drako_eyelids_fix.py`) melepas modifier armature dan vertex group untuk mengukur di bind space dan harus memasangnya kembali. Ketika tidak dipasang, body ter-ekspor sebagai objek rigid: 25 klip tetap lolos audit, tetapi tubuh tidak lagi mengikuti tulang. `glb_export.py:369` kini membandingkan ikatan skin file hasil tulis dengan file sumber, menolak, dan menghapus file buruk. Gerbang rilis melaporkan `RELEASE_GATE PASS` dengan `3 skinned primitive(s), 0 rigid` untuk `bayi_v2`, `remaja_v2`, dan `dewasa_v10`.

**Audit struktural aset shipped.** `shipped_final_audit.log`: ketiga tahap 25 klip × 78 channel, `LID_SYNC PASS` 25/25, `LOOP_SEAM 25/25`, `LOOP_FRAMES PASS 25/25`, `EXIT_*=0` untuk bayi, remaja, dan dewasa. Aset terpasang di `mobile/assets/3d/`: bayi 11.951.440 `ffc2f833…`, remaja 9.964.192 `4a96cf00…`, dewasa 14.906.152 `cca1faa5…`; Momo tidak disentuh (`a3442db2…`, `c2263f0e…`, `07b46168…`). Validator `qoder-gltf` pada aset final: `valid: true`, 0 error, 3 warning metadata per GLB.

**Bukti visual pada kamera aplikasi.** `final_qa/overview_3stage.png`, `head_zoom_3stage.png`, `eye_zoom_f000.png`, `eye_zoom_stages.png`, dan lembar klip `sheet_{bayi,remaja,dewasa}_idle_fresh.png` / `_sleep.png` disusun pada radius/target aplikasi (bayi 5,5 m/0,55 m; remaja 5,4 m/0,43 m; dewasa 4,55 m/−0,06 m). Ketiganya terbaca sebagai naga: sisik padat, iris amber berbingkai gelap, tandang emas, sayap; `sleep` dewasa menampilkan kelopak merah tertutup.

**Bukti runtime remaja dan dewasa di aplikasi.** Lompatan level khusus-debug dipakai sebagai alat QA, bukan fitur produk: `debugSetLevel(int)` di `app_state.dart:683-689` mengembalikan lebih awal bila `kReleaseMode`, kartu UI-nya di-gate `if (kDebugMode)` di `profil_screen.dart:116-120` dengan tombol `Remaja (Lv. 5)` dan `Dewasa (Lv. 11)` di `profile_preferences.dart:146-158`. Pada build debug di MuMu: `dbg_22_remaja_low.png` Lv.5, `dbg_23_remaja_pet.png` naga remaja di Beranda (sisik, sayap, leher panjang, iris amber), `dbg_25_dewasa_tap_low.png` Lv.11, `dbg_26_dewasa_pet.png` naga dewasa bersayap lebar dengan pola api emas, `dbg_29_small.png` kartu Koleksi Drako + chip `Dewasa Lv. 11+` aktif, `dbg_30_crop.png` gestur putar tetap berfungsi pada model dewasa. Gerak terukur: burst 10 frame di kartu pet dewasa mengubah 6.752–23.064 piksel per 0,25 s (`dewasa_burst_sheet.png` memperlihatkan sayap bergerak antar frame).

**Build release tunggal dan verifikasinya.** `flutter analyze` bersih kecuali satu `info` (`unnecessary_brace_in_string_interps` di `test/pet_glb_asset_test.dart:234`), **258** tes Flutter lulus (`final_analyze_test.log`). Satu build release: APK **114.145.362 byte**, SHA-256 `fec42ec094ce489c745287e67a6a518d832363d3c4f7e31796aeb500a62a5e03`, apksigner `Verifies` dengan skema v2, satu signer `CN=Momo Local Release, OU=Local Testing, O=Screen Time Companion, L=Local, C=ID`, versionName 1.0.0, dan **0 kemunculan `debuggable`** pada dump manifest. Keenam GLB di dalam `base.apk` byte-identik dengan folder aset — Drako `ffc2f833641a77bc9721f2c624b8f232`, `cca1faa50fd999efe95b1822f8ee1e46`, `4a96cf000426aa8c5a35191b9a6b8ae0`; Momo `a3442db2895efa50e90803afa391a702`, `07b461681e5ecb9c180522170120c8c2`, `c2263f0e9b88e16dc3dbd10ccdd7e981`. Di aplikasi release: `rt_35_release_pet.png` Beranda Lv.1 Bayi sebagai naga merah-emas bermata amber, dan `rt_39_small.png` membuktikan dasar Profil berhenti di kartu `Privasi & backup` → footer tanpa kartu `Alat uji`, jadi alat lompat level memang tidak ada di build rilis.

**Batas lingkungan baru yang harus diketahui: MuMu menghapus paket ini sendiri.** Logcat menunjukkan `Force stopping com.screentime.companion.screentime_companion … : deletePackageX` dan `Killing … due to deletePackageX` pada 20:32:20 dan 20:36:22, diikuti `PACKAGE_FULLY_REMOVED` dan telemetri `type: UninstallAPP` dari komponen sistem MuMu (`"package":"mumu","product":"MuMu5.0","product_version":"5.30.2.3616"`, uid 1000; cuplikan disimpan di `runtime_qa_20261103/mumu_uninstall_evidence.txt`). Tidak ada `FATAL EXCEPTION` — ini bukan crash aplikasi, melainkan watchdog emulator yang menghapus paket, dan karena uninstall ikut menghapus data, onboarding harus diulang setiap kali pasang ulang. Konsekuensinya untuk QA berikutnya: verifikasi runtime di MuMu bersifat tidak idempoten; simpan bukti segera dan jangan menyimpulkan regresi dari hilangnya aplikasi.

**Batas yang tersisa.** Semua bukti di atas hanya dari MuMu Android 12 900×1600 density 320 — tidak ada klaim perangkat fisik, FPS, atau baterai. Remaja/dewasa dibuktikan di Beranda dan Profil (viewer GLB yang sama); pill mode penuh dan overlay keliling tidak diaktifkan pada ronde ini karena memerlukan izin overlay + pelacak aksesibilitas. Sprite pill dan poster roaming tetap dibuat dari potret paket desain, bukan dari GLB, sehingga tidak terdampak ronde ini.

### 2.9 Bukti QA ronde 10 November 2026: aturan ukur mata, kartu kelopak ketiga tahap, dan drift durasi Kotlin

**Permintaan.** Wajah Drako masih dilaporkan cacat ("INI APAAN BODOH" dengan dua tangkapan layar): mata asimetris, celah/gash di tengah wajah, dan kelopak yang tidak menutup rapi. Pemeriksaan dilakukan pada byte aset dan render, bukan pada tangkapan layar saja.

**Dua aturan pengukuran aperture diperbaiki di `tools/drako_eye_measure.py`.** (1) Kelas pale tetap milik wajah tanpa batas (muzzle remaja tidak boleh menjadi bukan-kulit), tetapi sklera krem dewasa dipulihkan sebagai **lubang tertutup** dari komponen bukan-kulit yang dibatasi kotak cat sisi itu sendiri: lubang di dalam kotak cat adalah mata, lubang di luar kotak adalah wajah. Tanpa batas kotak, tambalan pale di luar mata (u=+0,0278) ikut masuk dan kotak L membengkak dari +0,0138 ke +0,0278; dengan aturan ini blob L dewasa tetap 43.656 px = 5,0 cm². (2) Gerbang amber kini menilai **cakram iris** saja: amber di dalam kotak cat dalam radius `0,7 × min(half_w, half_h)` dari piksel pupil, ditambah syarat pusat aperture di atas cat dan irisan kotak ≥ 50%. Alasannya terukur: kotak cat menandai sudut yang dicat, bukan bentuk mata — pulau UV remaja membungkus moncong sehingga kotak L mencapai u=+0,0905 (mata terlihat ±0,06), dan 1.254 px tambalan hangat berjarak 73 mm dari pupil serta 162 px bintik ikut terklasifikasi amber; ambang hue tidak dapat memisahkannya karena sisik moncong yang ternaung gagal rasio kroma merah (`G < 0,30·R`). Pembukaan morfologi 2,2 mm yang membuang retak juga mengikis bibir lash amber 1–2 px (2.426 px pada 57–72 mm dari pupil); rim itu **tidak** dinilai dan ditutup skirt kelopak 5,5 mm saat kedip, bukan oleh hull terukur. Hasil akhir: `dewasa_eye_ap5.json`, `remaja_headyaw_eye9.json`, `bayi_eye_ap3.json`, semuanya `EXIT 0` dengan `APERTURE_AMBER … miss=0` di enam sisi. Remaja memakai frame kanonik dari L; sisi R hanya mengeluarkan peringatan non-fatal `PAINT_TILT_54deg_x1.55`.

**Kartu kelopak ketiga tahap ditulis ulang dari catatan ukur itu.** Perintahnya `blender -b --factory-startup --python-exit-code 1 --python tools/drako_eyelids_fix.py -- <base.glb> <eyes.json> <out.glb> --stage <tag> --sync-lids --report <json>`; `--stage` wajib sama dengan `tag` laporan ukur (`dewasa_ap5`, `remaja9`, `bayi_ap3`) atau alat berhenti dengan `MEASURE_REPORT_TAG`. Keluarannya `dewasa_lids_ap2.glb` (14.949.976 B), `remaja_headyaw_lids9.glb` (10.269.480 B), `bayi_lids_ap3.glb` (12.499.036 B). Ketiganya `LID_VERIFY PASS` — kedua mata tertutup penuh di puncak kedip dan bersih saat rest — dan `LID_SYNC 25 clips, 25 repaired, 0 still desynced`. Standoff puncak: dewasa rata-rata 3,3 mm / maks 5,5 mm, remaja 9,5/13,4 mm, bayi 9,4/14,4 mm; bayi R menyembunyikan 3.223 dari 3.224 vertex bola mata (satu vertex batas kartu, bukan celah) dan sisi lain 100%.

**Render rest dan blink diperiksa sebagai gambar, bukan hanya angka.** `dewasa_lids2_rest/blink.png`, `remaja_lids9_rest/blink.png`, `bayi_lids3_rest/blink.png` pada kamera wajah yang sama. Ketiganya membuka mata amber bersimetri dan menutup penuh saat blink. Noda hangat dan halo pale di bawah mata remaja juga ada pada render basis tanpa kartu (`remaja_base_rest.png`), jadi itu cat, bukan kelopak. Sebagai pembanding, aset shipped lama dirender dengan kamera yang sama (`shipped_*_rest.png`): remaja lama masih menoleh dan menyipit, dewasa lama lebih sempit — build baru memperbaiki keduanya, bukan sekadar menggeser cacat.

**Rollout dan audit struktural.** Ketiga GLB dipasang ke `mobile/assets/3d/` (hash di §4.1b); kondisi §2.8 dicadangkan di `tools/qa_rig/face_fix_20261105/work/backup_shipped_20261110/`. `python tools/qa_rig_audit.py` pada byte terpasang: ketiga Drako `errors=0`, 29 node, 2 mesh, skin 26 joint, 25 klip × 78 channel, tepat 25/25 durasi Dart dan Kotlin. `qoder-gltf validate` (runtime plugin modeling-glb, karena `qoder-gltf` tidak ada di PATH shell ini): `valid: true` dan hanya 2 info + 3 warning metadata per GLB. Satu-satunya error audit yang tersisa adalah `momo_bayi` weight-sum 257 vertex — kondisi lama pada aset Momo yang tidak disentuh ronde ini; bukan regresi Drako dan tidak diperbaiki karena batas "jangan ubah aset Momo".

**Drift durasi Kotlin diperbaiki.** Audit menemukan `idle_fresh`/`idle_critical*`/`wing_flap`/`tail_wag`/`head_look`/`sleep` bayi serta `sleep` dewasa masih memakai angka grid lama di `PetBehavior.kt` (mis. 1.440 vs 1.467 ms; 4.167 vs 4.200 ms), sementara tabel Dart sudah benar. Nilai Kotlin kini disamakan persis dengan GLB/Dart (12 entri bayi + 1 entri dewasa); tanpa itu timer one-shot native memotong frame terakhir atau menahan pose. Ekspektasi `PetBehaviorTest` yang masih mematok angka pra-perbaikan ikut diperbarui (termasuk baris penjaga untuk semua entri yang sempat melenceng) dan `gradlew testDebugUnitTest` lulus. Setelah perbaikan, audit kembali `errors=0` untuk ketiga Drako.

**Satu build release dan verifikasinya.** Sesuai aturan "satu build setelah semua kode selesai", build dilakukan sekali setelah perbaikan Kotlin: `flutter analyze` 0 isu, **259** tes Flutter lulus, tes JVM Kotlin `BUILD SUCCESSFUL` (`final_analyze.log`, `final_test.log`, `final_kotlin_test.log` di `tools/qa_rig/face_fix_20261105/work/`). APK **114.256.414 byte**, SHA-256 `c9724294b6e17e29568b7695a83801bbe18fd08fe2050fe58c50452bfe743e11`, md5 `40f79db08ca205806a5c1a43372208dd`; `apksigner verify` lulus skema v2 dengan satu signer `CN=Momo Local Release, OU=Local Testing, O=Screen Time Companion, L=Local, C=ID` (cert SHA-256 `1d255a38a5b91f07ac2aa18b9e1145d7768593aae3181847f865842e44a6ac24`), versionName 1.0.0, sdk 24/target 36, dan **tanpa** atribut `application-debuggable` (`final_release_build.log`, `final_apk_signer.log`). Keenam GLB di dalam APK byte-identik dengan `mobile/assets/3d`: Drako md5 `4b3cd225515a7bfdc54a182727ea96fa`, `122bf1b8e89db6799077e96d764f46b3`, `cf5007eeb6a93edb1d8fd66de1f94b8f`; Momo tetap `a3442db2…`, `c2263f0e…`, `07b46168…`.

**QA layar penuh di MuMu (10 November 2026).** APK release dipasang di MuMu Android 12 900×1600 density 320, WebView 110. Walkthrough memakai data pemakaian nyata dan tangkapan layar berurutan `01_launch.png`–`47_home_no_pill.png` di `tools/qa_rig/face_fix_20261105/runtime/`. Yang terbukti di layar: Beranda menampilkan total nyata (`12j 3m`, `au_reader` teratas) dengan StatBar selebar layar; modal status kritis dan pemulihannya; delapan frame kedip berturut-turut (`blink_1..8.png`, `blink_grid.png`) memperlihatkan kedua mata menutup simetris tanpa celah/gash di dahi — keluhan "INI APAAN BODOH" tidak lagi tampak; gestur geser memutar pet dan ketukan memicu animasi reaksi; Rekap Harian/7j/30j beserta tren, kategori, dan peringkat app; Misi; Duel; Profil; Floating Pill dinyalakan, disembunyikan lewat menu pill, menu "Istirahat" dibuka, mode istirahat dimulai dan diakhiri. Ketiga tahap Drako dilihat langsung di renderer aplikasi: Remaja Lv.5 dan Dewasa Lv.11 (injeksi level sementara lewat SharedPreferences karena `debugSetLevel` tidak ada di build rilis) keduanya tampil sebagai naga, bukan anjing. Logcat sesi tidak memuat `FATAL EXCEPTION` maupun ANR.

**Kebersihan sesudah QA.** Preferensi Flutter dikembalikan dari `prefs_backup.xml` (level/xp kembali Lv.1 Bayi; `43_restored_bayi.png`), pill dimatikan (`46_profil_scroll_more.png` menunjukkan "Pill nonaktif"), dan `47_home_no_pill.png` membuktikan tidak ada overlay tersisa di launcher. Izin Aksesibilitas tetap tidak diaktifkan; izin overlay hanya dipakai selama uji pill.

**Batas ronde ini.** Semua bukti runtime berasal dari MuMu Android 12 900×1600 density 320; tidak ada klaim perangkat fisik, FPS, atau baterai. Pelacak gulir Aksesibilitas tidak diaktifkan, jadi hitungan scroll tidak diuji ulang. Kedip dibuktikan lewat tangkapan layar berurutan, bukan rekaman video; `sleep` dan `head_look` tetap bersandar pada audit klip dan render offline karena tidak dipanggil manual di runtime.

## 3. Peta sumber yang harus diketahui

Semua path berikut relatif terhadap root proyek. Package Kotlin berada di:
`mobile/android/app/src/main/kotlin/com/screentime/companion/screentime_companion/`.

| Sumber | Tanggung jawab aktual / titik perubahan |
| --- | --- |
| [companion.dart](../mobile/lib/core/models/companion.dart) | `Mood`, `Stage`, label, rentang level, katalog misi; tidak lagi menyimpan path GLB per tahap |
| [pet.dart](../mobile/lib/core/models/pet.dart) | `PetFamily` (momo/drako), `PetProfile`, `PetRegistry`, `PetStageLook`, durasi klip per tahap, `PetBehavior` state-aware; sumber kebenaran pet di Flutter |
| [balancing.dart](../mobile/lib/core/balancing.dart) | Batas mood dan koefisien penalti HP |
| [app_state.dart](../mobile/lib/core/state/app_state.dart) | `GameState`, `GameNotifier`, `hpProvider`, `moodProvider`, `petFamily`, `pillForm`, mode animasi, collection opt-in, persistensi dan penghapusan |
| [companion_3d.dart](../mobile/lib/widgets/companion_3d.dart) | Pemutar GLB `model_viewer_plus` untuk kedua pet, bridge JavaScript, varian idle Drako, timer one-shot, lifecycle, kamera per tahap, lapisan sentuh |
| [main_shell.dart](../mobile/lib/widgets/main_shell.dart) | Sinkronisasi tema/bahasa/level/bonus HP ke native; tidak menyalakan pill hanya karena config berubah |
| [home_screen.dart](../mobile/lib/features/home/home_screen.dart) | Mood/HP, pilihan `sleep` versus idle, status HP belum terbaca |
| [profile_appearance.dart](../mobile/lib/features/profil/profile_appearance.dart) | Pratinjau koleksi dan pemilih tahap; preview memakai idle sesuai tahap; fill kartu terpilih opaque |
| [profile_pet.dart](../mobile/lib/features/profil/profile_pet.dart) | Kontrol bentuk pill (kepala/badan penuh) dan mode animasi; tidak menyalakan pill |
| [profil_screen.dart](../mobile/lib/features/profil/profil_screen.dart) dan [profile_permissions.dart](../mobile/lib/features/profil/profile_permissions.dart) | Pengaturan, toggle runtime pill, izin; tidak ada toggle pet keliling pada build ini |
| [rest_screen.dart](../mobile/lib/features/rest/rest_screen.dart), [misi_screen.dart](../mobile/lib/features/misi/misi_screen.dart), [evolution_reveal.dart](../mobile/lib/widgets/evolution_reveal.dart) | Pengguna lain widget GLB: sleep, sesi misi, selebrasi, evolusi; ikon evolusi mengikuti pet |
| [usage_service.dart](../mobile/lib/core/services/usage_service.dart) | MethodChannel `com.screentime.companion/usage`; `showPill`, `hidePill`, `isPillVisible`, `syncPillHp`, `showPetOverlay` |
| [pill_controller.dart](../mobile/lib/core/services/pill_controller.dart) dan [pet_overlay_controller.dart](../mobile/lib/core/services/pet_overlay_controller.dart) | `applyPill(ref)` mengirim `pet`, tahap, bentuk, mode, bahasa, warna, bonus HP; `applyPetOverlay` mengirim data serupa untuk service native |
| [MainActivity.kt](../mobile/android/app/src/main/kotlin/com/screentime/companion/screentime_companion/MainActivity.kt) | Validasi bridge termasuk `pet` (`momo`/`drako`), persistensi native, start/stop service, visibility host, shutdown privasi |
| [PillService.kt](../mobile/android/app/src/main/kotlin/com/screentime/companion/screentime_companion/PillService.kt) | Registry sprite/body untuk Momo dan Drako, HP native, WindowManager, drag, panel, animasi View, renderer penuh, cleanup |
| [PetBehavior.kt](../mobile/android/app/src/main/kotlin/com/screentime/companion/screentime_companion/PetBehavior.kt) | `PetKind`, `PetClips`, `PetCatalog`, bobot/perilaku native yang mencerminkan kontrak Dart |
| [PetLife.kt](../mobile/android/app/src/main/kotlin/com/screentime/companion/screentime_companion/PetLife.kt), [PetWebRenderer.kt](../mobile/android/app/src/main/kotlin/com/screentime/companion/screentime_companion/PetWebRenderer.kt), [PetWebAssets.kt](../mobile/android/app/src/main/kotlin/com/screentime/companion/screentime_companion/PetWebAssets.kt) | Scheduler klip native, renderer WebView transparan, allowlist aset termasuk GLB Drako |
| [PetOverlayService.kt](../mobile/android/app/src/main/kotlin/com/screentime/companion/screentime_companion/PetOverlayService.kt) | Service pet keliling native; ada, tetapi tidak diekspos di Profil build ini dan tidak di-QA ulang |
| [UsageRepo.kt](../mobile/android/app/src/main/kotlin/com/screentime/companion/screentime_companion/UsageRepo.kt) | Data pemakaian nyata untuk pill saat UI Flutter di background |
| [NativeStore.kt](../mobile/android/app/src/main/kotlin/com/screentime/companion/screentime_companion/NativeStore.kt), [NativeBackup.kt](../mobile/android/app/src/main/kotlin/com/screentime/companion/screentime_companion/NativeBackup.kt) | Privasi, persistensi dan allowlist backup native; bukan registry animasi |
| [backup_snapshot.dart](../mobile/lib/core/models/backup_snapshot.dart), [backup_service.dart](../mobile/lib/core/services/backup_service.dart) | Validasi preferensi yang dapat dibackup; restore mematikan collection dan service opsional |
| [AndroidManifest.xml](../mobile/android/app/src/main/AndroidManifest.xml), [network_security_config.xml](../mobile/android/app/src/main/res/xml/network_security_config.xml) | Izin, service foreground, keamanan pemuatan aset lokal |
| [pubspec.yaml](../mobile/pubspec.yaml) | Enam GLB (Momo/Drako × tiga tahap) dan kartu bayi kedua pet; registrasi aset pet baru |

Stack yang relevan: Flutter/Riverpod, `model_viewer_plus`, `webview_flutter`, Kotlin `Service` + `WindowManager`. Web prototype `docs-design/` bukan runtime Android.

## 4. Kontrak model dan rig

### 4.1 Aset Momo yang benar-benar dipakai mobile

| Tahap | Level | GLB | Ukuran byte | SHA-256 pada pemeriksaan ini |
| --- | --- | --- | --- | --- |
| Bayi | 1–4 | `mobile/assets/3d/momo_bayi.glb` | 9.527.088 | `bfd9e7f22a679178dac8ed1752b7b0eed51b9ae849ea6f775dca095adee6c6f5` |
| Remaja | 5–10 | `mobile/assets/3d/momo_remaja.glb` | 9.405.644 | `a5da57bbe4d13450802df61af91e5e8028aa4157296d5aed8bda56bad88dc9ee` |
| Dewasa | 11+ | `mobile/assets/3d/momo_dewasa.glb` | 14.351.584 | `16fa043b27f1a235a980b00362250f298f8c2e55daeda4557dc06057f0da8433` |

Ketiganya mempunyai 25 node, satu skin dengan 22 joint, serta `Blink_L` dan `Blink_R` sebagai dua node mesh kelopak mata. Setiap mesh kelopak memiliki satu morph target yang dipakai oleh primitive permukaan dan lash; bukan 24 tulang atau delapan morph independen.

### 4.1b Aset Drako yang benar-benar dipakai mobile

| Tahap | Level | GLB | Ukuran byte | SHA-256 pada pemeriksaan ini |
| --- | --- | --- | --- | --- |
| Bayi | 1–4 | `mobile/assets/3d/drako_bayi.glb` | 12.499.036 | `5019da9a87974e0a9be92fe42909413ca049a17b7d64b5d20a90d43012881570` |
| Remaja | 5–10 | `mobile/assets/3d/drako_remaja.glb` | 10.269.480 | `751d1bdc2bbe25fd84ff612bb0a514ffc3ec489c15f49fe726572f62eccd9ef0` |
| Dewasa | 11+ | `mobile/assets/3d/drako_dewasa.glb` | 14.949.976 | `d80649a5169592063af5291b0c8627184ef41deeb670c05b640d74ac548919f7` |

Angka sebelum repaint (12.031.336 / 9.907.448 / 15.494.420 dengan SHA-256 `75210b87…` / `046bde12…` / `09af2242…`) adalah kondisi build 2 November §2.6 dan disimpan byte-identik di `tools/qa_rig/dragon_look/backup_shipped_20261102/`. Kondisi §2.7 (11.936.480 / 9.931.100 / 14.867.732 dengan SHA-256 `7d4a1f3c…` / `45d27a31…` / `29a9f2be…`) disimpan byte-identik di `tools/qa_rig/dragon_look/backup_shipped_20261103/`. Kondisi §2.8 (11.951.440 / 9.964.192 / 14.906.152, SHA-256 `00140e65…` / `82e0aa72…` / `d8337e36…`) disimpan byte-identik di `tools/qa_rig/face_fix_20261105/work/backup_shipped_20261110/`. Semuanya titik masuk untuk audit atau rollback, bukan aset runtime.

Ketiganya mempunyai 29 node, dua mesh (`Mesh_0` tubuh dan `DrakoEyelids`), satu skin `DrakoSkin` dengan 26 joint (24 tubuh + `Lid_L`/`Lid_R`), dan tiga tekstur JPEG tertanam. `DrakoEyelids` terdiri dari dua primitive (kelopak berbulu dan bulu mata) dan seluruh vertex-nya berbobot 1,0 ke salah satu tulang kelopak. Sejak perbaikan gerak kepala 2 November 2026, kedua tulang kelopak digantung ke **`Head` di ketiga tahap** agar kartu kelopak mengikuti wajah yang kini berputar bersama `Head`; rest world pose dipertahankan. Sebelumnya parent-nya berbeda per tahap (bayi `Chest`, remaja `Neck`, dewasa `Head`) dan itu bukan tanda kelopak lepas.

Kedip nyata dibake ke **seluruh 25 klip** setiap tahap: `Lid_L`/`Lid_R` `scale.y` naik 1 → 30 (kartu kelopak 1/30 tinggi istirahat), tutup 1,8 frame, tahan 1 frame, buka 4 frame pada 30 fps; kedua kelopak memakai kurva yang **identik sample-per-sample** (agreement 1e-04 pada 25/25 klip — lihat §2.8). `sleep` menahan kelopak tertutup sepanjang klip. Tidak ada morph target; kedip tidak memakai channel weights Momo. Konsekuensinya setiap klip Drako sekarang membawa 78 channel (26 joint × translasi/rotasi/skala), bukan 75. Semua klip ditulis ulang lewat putaran Blender 5.2 `tools/drako_eyelids.py`; jangan menambal byte GLB langsung. Teks lama pada baris ini menyebut "kelopak kanan tertinggal 0,7 frame"; itu bug, bukan desain, dan sudah dihapus dari aset yang beredar.

Angka lama (25 node/24 joint, tanpa kelopak) adalah kondisi sebelum ronde §2.5 dan tidak berlaku lagi. Empat idle kritis bayi/remaja tetap beranimasi; dewasa ikut ditulis ulang karena penambahan kelopak, jadi perbandingan byte-per-byte dengan build sebelumnya tidak lagi bermakna.

**Bahaya salinan:** hash GLB pada folder desain/paket lama dapat berbeda dari versi mobile. File rig teks dan controller contoh juga dapat tertinggal dari perubahan BIN animasi. `mobile/assets/3d/momo_glb_controller.dart` dan `.rig` tidak direferensikan oleh `mobile/lib/`; pemutar runtime adalah widget `mobile/lib/widgets/companion_3d.dart`. Mengedit controller contoh saja tidak mengubah aplikasi. Jangan menimpa aset mobile dengan salinan itu tanpa perbandingan, backup, dan persetujuan cakupan.

### 4.2 Hierarki Momo

```text
Root
└── Hips
    ├── Spine
    │   └── Chest
    │       ├── Neck
    │       │   ├── Head
    │       │   │   ├── Ear_L
    │       │   │   └── Ear_R
    │       │   ├── Blink_L   [mesh morph, bukan joint]
    │       │   └── Blink_R   [mesh morph, bukan joint]
    │       ├── Arm_L → Forearm_L → Paw_L
    │       └── Arm_R → Forearm_R → Paw_R
    ├── Leg_L → Foot_L
    ├── Leg_R → Foot_R
    └── Tail_1 → Tail_2 → Tail_3 → Tail_Tip
```

Ini rig karakter chibi, bukan bukti bahwa model otomatis mampu berjalan anatomis seperti kucing realistis berkaki empat. Tidak ada joint lutut terpisah dalam rig sekarang. Gait harus sesuai bentuk mesh dan pembobotannya; tambah/ubah rig hanya jika hasil visual memerlukannya dan perubahan itu disetujui.

### 4.3 Hierarki Drako

```text
Root
└── Hips
    ├── Spine
    │   └── Chest
    │       ├── Neck
    │       │   └── Head
    │       │       ├── Horn_L
    │       │       └── Horn_R
    │       ├── Wing_L → Wing_L_Tip
    │       └── Wing_R → Wing_R_Tip
    ├── LegFL → PawFL
    ├── LegFR → PawFR
    ├── LegBL → PawBL
    ├── LegBR → PawBR
    └── Tail_1 → Tail_2 → Tail_3 → Tail_Tip
```

Kelopak adalah mesh terpisah `DrakoEyelids` yang di-skin 100% ke `Lid_L`/`Lid_R`. Kedua tulang kelopak sekarang digantung ke **`Head`** di semua tahap, dengan rest world pose yang sama seperti sebelumnya. Riwayatnya berbeda per tahap (bayi `Chest`, remaja `Neck`, dewasa `Head`); perbedaan lama itu bukan tanda kelopak lepas, tetapi parent `Chest`/`Neck` membuat kelopak tertinggal saat wajah berputar sehingga diseragamkan. Jangan mengubah parent kelopak lagi tanpa memverifikasi rest world pose dan drift kelopak-wajah per klip.

Drako memakai penamaan `LegFL/PawFL` dan seterusnya, bukan `Leg_L/Foot_L` seperti Momo. Klip sayap harus menggerakkan `Wing_L/R` dan tip-nya; jangan memutar mesh atau menskalakan chest sebagai pengganti kepakan. Kedip memakai skala kelopak, bukan morph; jangan menambahkan channel weights blink Momo ke rig ini. Jika parent kelopak diubah, render ulang klip di kamera akhir dan periksa kelopak saat kepala berputar—parent yang salah membuat kelopak tertinggal dari mata.

### 4.4 Aturan deformasi

- `JOINTS_0`, `WEIGHTS_0`, daftar `skin.joints`, dan inverse bind matrices harus konsisten; bobot vertex ternormalisasi dan indeks valid.
- Animasi glTF menyimpan transform lokal absolut. Jangan memasukkan delta translasi sebagai transform absolut: `Hips` harus mempertahankan rest translation milik model itu.
- Animasi satu bagian harus mengubah joint/weights bagian terkait. Memutar node mesh atau menskalakan torso bukan pengganti gerakan tangan/pipi.
- Pada Momo, pivot wajah yang diperbaiki berada pada **Neck**. `momo_rig.py` memindahkan bobot wajah dari Arm/Chest ke Neck; `momo_animate.py:share_head_motion()` membagi gerak Head/Neck. Jangan menganggap titik ini berlaku untuk pet lain.
- Pada Drako, gerak kepala diperbaiki lewat **dua lapis**: bobot/pivot lalu retarget rotasi, bukan dengan memindahkan seluruh rotasi `Head` ke `Neck`. Wajah/tengkorak bayi/remaja awalnya terikat ke `Neck`/`Chest`/`Spine` sementara klip memutar `Head` jauh lebih besar, dan pivot `Head` berada di atas tengkorak yang terlihat. `tools/drako_head_skin.py` mentransfer bobot non-tanduk di band z dengan mask smoothstep ke `Head`, melewati vertex yang masih berbobot `Wing_*`, `Leg*`, `Paw*`, `Tail_*`, `Root`, atau `Hips`, lalu menempatkan pivot final di pangkal leher (bayi `Head` 0,9200/`Neck` 0,8520; remaja 1,2350/1,1660; dewasa tetap 0,3100/0,2400), mempertahankan rest world tanduk/kelopak, dan menggantung kelopak ke `Head`. Setelah itu `tools/drako_head_retarget.py` memetakan roll lokal menjadi yaw pada 25 klip ketiga tahap (final: head gain 1,5/roll keep 0,10; neck gain 0,40/roll keep 0,20). Jangan menghapus proteksi vertex atau mengembalikan rotasi roll dominan. Jangan "memperbaiki" kepala dengan memindahkan rotasi `Head` ke `Neck`—pendekatan itu ditolak karena yang terlihat bergerak justru leher, bukan kulit kepala.
- Drako dewasa tidak menjalani perbaikan bobot/pivot: wajah, tengkorak, dan tanduknya sudah bergerak sebagai satu unit dengan leher yang menekuk. Namun klip dewasa ikut di-retarget roll→yaw karena masalah "meleot" berasal dari kurva rotasi, bukan bobot. Jangan menjalankan generator skin ke dewasa tanpa kebutuhan baru, dan jangan menyamakan angka pivot dewasa dengan bayi/remaja.
- Kelopak mata Momo adalah mesh tambahan yang mengikuti Neck dengan morph weights. Drako memakai dua kartu kelopak ber-skin (`DrakoEyelids`) yang diskalakan 1→30 pada sumbu lokal Y; setiap klip Drako wajib membawa kurva kedua kelopak, dan sleep menahan kelopak tertutup. Jangan mencampur mekanismenya: morph weights Momo tidak berlaku di Drako, dan skala kelopak Drako tidak berlaku di Momo.
- Kedip Drako bukan ekspresi tekstur: kelopak adalah geometri yang menutup mata. Jangan mengklaim kedip hanya karena ada channel `Lid_*`; periksa nilai puncak `scale.y` dan frame render saat mata tertutup.
- Pet baru boleh memakai morph/blendshape, kartu kelopak, atau mekanisme lain melalui adapter, asalkan semua klip loop dan klip tidur memuat state mata yang benar.
- Periksa batas pose ekstrem dan kamera: kepala, telinga, kaki, dan ekor tidak boleh terpotong selama klip maupun crossfade.

## 5. Kontrak klip, state, dan playback

### 5.1 Dua belas klip Momo

Durasi berikut dibaca dari accessor GLB mobile, sama untuk ketiga tahap. Setiap klip memiliki 26 channel: 22 rotation joint, translation Hips, scale Chest, dan 2 weights kelopak mata (dikonfirmasi `tools/glb_anim_report.py`). Memiliki channel tidak berarti semua tulang terus bergerak.

| Klip | Durasi | Pemicu / pemakaian aktual |
| --- | --- | --- |
| `idle_fresh` | 8 detik | HP > 60, looping |
| `idle_tired` | 8 detik | HP 30–60, looping |
| `idle_critical` | 3 detik | HP < 30, looping |
| `sleep` | 8 detik | Dipilih layar ketika istirahat, looping; mengalahkan aksi spontan |
| `tap_reaction` | 1 detik | Ketuk, one-shot, lalu kembali ke baseClip |
| `celebrate` | 2 detik | Perubahan celebrateTick, one-shot, lalu kembali ke baseClip |
| `greet` | 2 detik | Sekali setelah model siap (cooldown per widget), tidak berulang saat rebuild |
| `look_around` | 3 detik | Aksi spontan, berbobot termasuk saat HP kritis |
| `groom` | 3,2 detik | Aksi spontan; bobot lebih tinggi pada tahap bayi |
| `stretch` | 2,6 detik | Aksi spontan, bobot mengikuti tahap |
| `walk` | 1,2 detik, looping | Aksi spontan; di dalam aplikasi satu klip tanpa memindahkan widget; di service native 2 siklus dan menggerakkan jendela 72 dp |
| `petting` | 2 detik | Long press/elus; tidak menambah HP/XP |

Durasi lama di `.rig` atau dokumen desain bukan acuan untuk timer runtime. Jika durasi klip diganti, metadata dan controller harus ikut diperbarui.

### 5.1b Dua puluh lima klip Drako

Drako memakai 13 varian idle (5 segar, 4 lelah, 4 kritis) ditambah 12 klip aksi. Durasi di bawah adalah detik, urut bayi/remaja/dewasa; nilai persis per varian ada di `PetRegistry` dan `PetCatalog`.

| Klip | Bayi / Remaja / Dewasa | Pemicu / pemakaian aktual |
| --- | --- | --- |
| `idle_fresh` + `_a`..`_d` | 2,67–2,90 / 2,20–2,40 / 2,80–3,60 | HP > 60; widget memilih varian dan memutarnya loop penuh; setelah tahan 6–12 detik, crossfade 250 ms ke varian lain tanpa mengulang yang sama |
| `idle_tired` + `_a`..`_c` | 3,60 / 3,00 / 3,60–4,00 | HP 30–60, pola varian dan loop yang sama |
| `idle_critical` + `_a`..`_c` | 1,47 / 1,20 / 1,40–2,60 | HP < 30, pola varian dan loop yang sama; keempat varian beranimasi (bayi/remaja diregenerasi 31 Oktober) |
| `sleep` | 4,33 / 3,60 / 4,20 | Layar istirahat, looping; mengalahkan aksi spontan; kelopak tertutup sepanjang klip |
| `tap_reaction` | 0,80 / 0,80 / 0,90 | Ketuk ganjil; one-shot |
| `wing_show` | 2,20 / 1,80 / 2,40 | Ketuk genap (bergantian dengan `tap_reaction`); aksi spontan saat segar dengan bobot lebih tinggi saat dewasa |
| `wing_flap` | 1,47 / 1,20 / 1,60 | Aksi spontan saat segar/lelah; tidak dipilih saat HP kritis |
| `tail_wag` | 1,47 / 1,20 / 1,60 | Aksi spontan |
| `head_look` | 1,93 / 1,60 / 2,20 | Aksi spontan; tetap tersedia saat HP kritis |
| `fire_puff` | 1,00 / 1,00 / 1,10 | Aksi spontan; bobot lebih tinggi saat dewasa |
| `happy_bounce` | 1,00 / 1,00 / 1,10 | Aksi spontan; bobot turun saat lelah |
| `greet` | 2,40 / 2,00 / 2,20 | Sekali per widget setelah model siap (jeda 1.600 ms) |
| `petting` | 2,20 / 2,00 / 2,40 | Long press/elus; tidak menambah HP/XP |
| `walk` | 1,40 / 1,00 / 1,60 | Aksi spontan; satu siklus klip di dalam aplikasi |

Bobot spontan Drako berbeda per tahap: dewasa lebih sering `wing_show`/`fire_puff`, bayi/remaja lebih sering `tail_wag`/`happy_bounce`/`walk`. Jangan menyalin bobot Momo atau menganggap semua aksi ada di semua mood. `wing_show` adalah klip yang sudah dibake; tidak ada morph sayap tambahan saat runtime.

Setiap klip di tabel membawa kedip kelopak. Klip satu kali (aksi, tap, elus, sapaan, selebrasi) berkedip sekali di sekitar 42–45% durasi; klip idle berkedip di sekitar 30% dan 64% (tambah 84% bila durasi di atas 4 detik). Kedip ini deterministik per klip, bukan acak per pemutaran. Saat runtime, varian idle **tidak** berhenti di akhir klip: `play()` mengulang varian yang sama sampai timer 6–12 detik habis, lalu crossfade 250 ms ke varian lain. Jeda 0,5–2 detik pada implementasi lama sudah tidak ada dan jangan dihidupkan kembali tanpa mengukur efek beku visualnya.

### 5.2 Sumber state, bukan hardcode per pet

- `GameState.stage` diturunkan dari level; enum `Stage` dipakai bersama semua pet, sedangkan aset dan kamera berasal dari `PetProfile.look(stage)`.
- `MoodX.fromHp()` mengikuti `Balancing.hpFreshAbove = 60` dan `hpTiredFrom = 30`.
- Penalti HP: 0,2 per menit layar dan 0,03 per scroll, ditambah bonus pemulihan hari ini; hasil dibatasi 0–100. Dart memakai data pemakaian aplikasi, native menghitung dari snapshot native.
- Native pill menyimpan bonus dan `hpDay`, sehingga bonus kemarin tidak terbawa ke hari baru.
- UI memiliki kondisi **HP belum diketahui** saat sumber pemakaian tidak tersedia. `hpProvider` dapat memiliki fallback 100 untuk internal; itu tidak boleh dipromosikan sebagai pembacaan HP nyata. Lihat `hpKnown` pada Home.
- `GameState.isResting` dikirim ke native lewat `setPetResting`; `PillService.setResting` menyegarkan `PetLife` dan memberitahu overlay. Jangan menganggap state tidur hanya hidup di Flutter atau menambahkan timer tidur terpisah di native.
- Selisih kecil Home/pill dapat berasal dari agregasi dan kesegaran data. Agent harus membandingkan sumber dan timestamp sebelum mengubah rumus.

### 5.3 Pemutar sekarang

`Companion3D` menerima `pet`, `stage`, `mood`, `resting`, `height`, `celebrateTick`, `onTap`, `reactOnTap`, `living`, dan `greetOnLoad`. Widget memilih profil dari `PetRegistry`, klip dari `PetProfile`, dan framing dari `PetStageLook`; tidak ada percabangan UI per nama pet. Pemutar memilih klip melalui JavaScript `animationName`/`play()`, dengan crossfade 250 ms.

Kamera per tahap (orbit / target):

| Pet/tahap | Orbit awal | Target |
| --- | --- | --- |
| Momo semua tahap | `0deg 82deg 4.8m` | `0m 0.02m 0m` |
| Drako bayi | `0deg 82deg 5.5m` | `0m 0.55m 0m` |
| Drako remaja | `0deg 82deg 5.4m` | `0m 0.43m 0m` |
| Drako dewasa | `0deg 82deg 4.55m` | `0m -0.06m 0m` |

Sejak ronde rotasi, semua pet mulai **tegak menghadap kamera** (`0deg`), sesuai pilihan pengguna; Drako tidak lagi default 25° 3/4. Pengguna menggeser horizontal di atas pet untuk memutar azimuth 360° dengan laju 0,8°/piksel; phi `82deg`, radius, dan target tetap pada preset tahap. Gestur memakai `GestureDetector.onHorizontalDragUpdate` di lapisan atas WebView, jadi drag horizontal tidak memicu tap/elus, sementara drag vertikal tetap diteruskan ke scroll induk. Kamera di-reset ke preset saat pet atau tahap berubah. Zoom dan pan tetap dimatikan.

Radius final divalidasi dengan `tools/qa_rig/tmp_orbit_fit.py` (read-only; 12 azimuth 0–330° langkah 30°, 25 klip × 6 frame, kamera 26°, aspek 1,0 karena kanvas pet persegi). Nilai maksimum ternormalisasi (di atas 1 berarti crop):

| Tahap | Radius | max_x semua azimuth | max_y semua azimuth | Isi default 0° |
| --- | --- | --- | --- | --- |
| Bayi | 5,5 m | 0,727 | 0,963 | x 0,713 / y 0,907 |
| Remaja | 5,4 m | 0,944 | 0,959 | x 0,896 / y 0,949 |
| Dewasa | 4,55 m | 0,995 | 0,653 | x 0,925 / y 0,653 |

Semua azimuth `fit=YES`; tidak ada ekor/sayap/pose `celebrate` yang terpotong saat diputar penuh. Angka pada tabel adalah sweep ulang 2 November 2026 pada aset final setelah retarget kepala. Batas terluar tetap berasal dari ekor/sayap; max_x naik dari sweep 31 Oktober (0,692/0,899/0,947) karena yaw kepala memperlebar siluet hidung/telinga pada azimuth tertentu, bukan karena radius diubah. Bayi/remaja memakai radius sedikit lebih jauh daripada tuning 25° sebelumnya (5,15/5,2 m); jangan menurunkan radius tanpa menjalankan sweep ulang. Target dewasa lebih rendah karena tubuh dewasanya berpusat di sekitar y=0; bayi/remaja memakai target lebih tinggi karena kepala mereka di sekitar y=1,5. Angka `3.9m`/`5.0m` di §2.3 adalah riwayat, bukan preset aktif.

Momo sengaja **tidak** diubah framing-nya: radius 4,8 m sudah disetujui dan tangkapan runtime 0/80/176/330° tidak memperlihatkan potongan. Sweep ketat Momo (12 klip, 13 azimuth) menemukan max_y hingga 1,120 pada Momo dewasa (`celebrate`/`sleep`) dan 1,111 pada `idle_critical` 30–60°, sedangkan bayi mencapai 1,076 pada `idle_critical` 330°, jadi pose ekstrem tertentu memang melewati batas matematis; jangan mengecilkan Momo hanya untuk menutup angka itu tanpa persetujuan dan sweep ulang. Detail bukti di §2.5 dan batas di §12.3.

`living` mengaktifkan perilaku spontan dari `PetBehavior` Dart: jeda state-aware, anti-repeat, greet sekali, serta klip khusus per keluarga. Momo memakai look/groom/stretch/walk; Drako memakai head_look/tail_wag/happy_bounce/fire_puff/wing_flap/wing_show/walk. Ketuk memicu klip pertama di `tapClips`; Drako bergantian `tap_reaction` dan `wing_show`. Long press memicu `petting`; keduanya tidak menambah HP/XP. Walk di dalam app hanya animasi klip, tidak memindahkan widget.

Untuk keluarga dengan varian idle (`PetRegistry.hasIdleVariants`, saat ini Drako), `Companion3D` memutar varian terpilih dengan `play()` berulang dan menyimpan timer `PetBehavior.idleHold` 6.000–12.000 ms. Saat timer habis, widget memilih varian lain pada mood yang sama, memanggil `play()` dengan crossfade 250 ms, lalu memasang timer baru. One-shot (tap/celebrate/petting/spontan) memotong siklus, dan setelah selesai widget kembali ke varian idle—bukan membekukan pose. Jangan mengubah ini menjadi "putar sekali lalu berhenti"; itu regresi yang sudah diperbaiki.

Widget mem-pause klip jika app di background, `TickerMode` mati, atau route tertutup; timer dibatalkan saat dispose. Bridge load menjaga late-load tidak menyalakan klip pada widget tersembunyi. Fallback loading 8 detik menghilangkan placeholder, **bukan jaminan model berhasil dimuat**. Error JavaScript sekarang ditangani tanpa pelaporan visual rinci.

Lapisan GestureDetector sekarang menutupi seluruh kotak widget dan mendeteksi ketuk, **bukan** raycast kepala/pipi/kaki. `model_viewer_plus` memilih klip utuh; public API saat ini tidak mengontrol joint individu. Gerak per tulang dapat dibake ke klip GLB. Kontrol joint procedural atau hit-test bagian tubuh membutuhkan renderer/adapter tambahan yang diuji.

**Prioritas tidur:** baik `PetLife` (native) maupun `Companion3D` membatalkan aksi one-shot ketika state berubah menjadi sleep/mood baru; `PetBehavior.tapClip/pettingClip` mengembalikan null saat resting, dan scheduler spontan tidak dijadwalkan. Perilaku ini dikunci oleh tes `pet_behavior_test.dart`, `companion_behavior_test.dart`, dan `PetBehaviorTest.kt`.

### 5.4 Perilaku hidup yang diterapkan

Katalog aksi dan pemilih state-aware sudah diterapkan di dua tempat: `PetBehavior` Dart untuk widget dalam aplikasi dan `PetBehavior.kt` untuk pill native. Momo memakai greeting, look-around, grooming, stretch, walk pendek, respons ketuk/elus, dan selebrasi. Drako memakai greeting, head look, tail wag, happy bounce, fire puff, wing flap, wing show, walk pendek, respons ketuk/elus, dan selebrasi. Slow blink dan ear twitch Momo tidak menjadi klip terpisah; keduanya bagian dari klip idle. Drako kini juga berkedip, tetapi lewat kartu kelopak ber-skin yang dibake ke setiap klip (§4.1b), bukan morph seperti Momo.

Pet baru harus punya klip nyata sebelum memintanya pada renderer. Pet yang tidak mempunyai aksi opsional harus memilih idle yang kompatibel, bukan crash atau mengganti file pet lain.

Kontrak yang dijaga oleh implementasi dan tes:

- Safety/hidden/off mengalahkan seluruh playback; istirahat mengalahkan aksi random; HP kritis tidak memilih aksi energik.
- Interaksi memiliki cooldown dan tidak membuat antrean aksi tak terbatas. Drag membatalkan roaming; pose kembali mulus.
- Random memakai bobot sesuai mood/tahap, jeda, dan anti-pengulangan. Jam dan random dapat diinjeksi agar tes deterministik.
- Sapaan tidak dipicu setiap rebuild/tab switch; definisikan cooldown kunjungan. Sapaan yang dibahas berupa gestur, bukan fitur suara atau chatbot.
- Ketuk/elus tidak menambah XP/HP: statistik tetap berasal dari mekanik resmi.
- Event selesai klip lebih aman daripada timer tebakan; metadata durasi dan timeout dapat menjadi fallback yang dibatasi lifecycle.

## 6. Pipeline authoring: alat yang ada dan jebakannya

| Alat | Yang benar-benar dilakukan | Batas / risiko |
| --- | --- | --- |
| [glb_anim_report.py](../tools/glb_anim_report.py) | Membaca channel, durasi, first/last pose, rotation maxdev, spread translation/scale/weights | Read-only; bukan validator glTF lengkap atau tes visual deformasi |
| [momo_animate.py](../tools/momo_animate.py) | Menulis ulang keenam klip dengan banyak track full-body; mempertahankan mesh/skin/tekstur; sampling 30 FPS | Mengganti daftar animations; channel blink lama ikut hilang; accessor baru di-append dan data tak terpakai bertambah |
| [momo_rig.py](../tools/momo_rig.py) | Reweight wajah, membuat mesh kelopak mata, menambah channel weights | Parameter wajah/eye geometry khusus tiga Momo. Menjalankan main pada GLB yang sudah punya Blink dapat menduplikasi mesh/node dan channel |
| [rework_glb_idle.py](../tools/rework_glb_idle.py) | Patch BIN in-place untuk idle/sleep/tap: Hips diam, Chest scale 1, gerak lokal telinga/ekor/paw/head/weights; celebrate tidak diubah | Mengasumsikan layout accessor sesuai writer Momo dan sampling channel kompatibel. Bukan alat universal; rerun dapat mengakumulasi offset first-frame |
| [drako_animate.py](../tools/drako_animate.py) | Menambahkan empat klip Drako (greet, petting, walk, wing_show) ke 21 klip bawaan, tanpa mengubah mesh/skin/tekstur; `wing_show` bayi = kepakan sayap pura-pura, remaja = latihan, dewasa = display | Khusus nama joint/klip Drako. Semua klip baru menganimasikan 24 joint + translasi Hips; jangan jalankan pada rig lain |
| [drako_idle_alive.py](../tools/drako_idle_alive.py) | Menambahkan lapisan hidup (napas, ekor, sayap) ke varian idle Drako dan menjaga loop; dipakai sebelum kelopak ditambahkan | Khusus KLIP Drako; jalankan pada salinan kerja, lalu verifikasi loop dan jarak antar-varian. Jangan dipakai pada Momo |
| [drako_eyelids.py](../tools/drako_eyelids.py) | Membuat mesh `DrakoEyelids`, tulang `Lid_L`/`Lid_R`, material kelopak/bulu mata, dan kurva blink `scale.y` di seluruh 25 action; mengekspor ulang GLB lewat Blender 5.2 dengan `ACTIONS` dan tanpa optimasi ukuran | Putaran penuh Blender, bukan patch BIN. Parent kelopak saat dibuat khusus tahap (Chest/Neck/Head); `drako_head_skin.py` kemudian menggantung keduanya ke Head. Mengubah `BLINK_CLOSE/HOLD/OPEN` atau `REST_DIV` mengubah kecepatan tutup dan tinggi kartu; render ulang klip sebelum integrasi |
| [drako_head_skin.py](../tools/drako_head_skin.py) | Mentransfer bobot kulit kepala Drako bayi/remaja ke `Head` dengan mask z smoothstep, melewati vertex yang masih terikat sayap/kaki/ekor/root/hips, menempatkan pivot `Head`/`Neck` di pangkal leher yang terlihat (final: bayi `Head` 0,9200/`Neck` 0,8520; remaja 1,2350/1,1660), mempertahankan rest world tanduk/kelopak, menggantung kelopak ke `Head`, merebase channel translasi bone yang pivotnya bergeser, lalu mengekspor GLB lewat Blender 5.2. Kurva rotasi/skala 25 klip tidak diubah | Khusus Drako bayi/remaja; dewasa tidak dijalankan. Mask z murni pernah menangkap sayap/Chest, jadi periksa `protected_skipped` dan jalankan audit region serta `tmp_glb_struct_diff_skin.py` (IBM, bobot, posisi vertex, klip). Parameter `--z0/--z1/--head-pivot/--neck-pivot` menentukan band dan pivot; jangan menambal byte GLB |
| [drako_head_retarget.py](../tools/drako_head_retarget.py) | Menulis ulang hanya kurva rotasi `Head`/`Neck` seluruh 25 klip Drako: roll lokal dipetakan menjadi yaw dengan sisa tilt dan follow leher yang dapat diatur; translasi/skala, mesh, bobot, bahan, dan tekstur tetap; key time dinormalkan ke grid 30 fps; ekspor GLB lewat Blender 5.2 | Khusus rig Drako dan konvensi Euler `drako_animate.py`; parameter default bukan pengganti verifikasi. Jalankan pada salinan kerja setelah bobot/pivot benar, lalu bandingkan struktur (`tmp_glb_struct_diff.py`), inventaris klip, sumbu dunia, dan render sebelum/sesudah. Jangan memakainya untuk memperbaiki masalah bobot atau pivot |
| [drako_texture_extract.py](../tools/drako_texture_extract.py) | Membaca chunk JSON+BIN sebuah GLB dan menyalin payload tiga JPEG tertanam ke `<out_dir>` sebagai `<index>_Image_<N>.jpg` | Read-only; tidak decode/re-encode. Prefix indeks mengikuti urutan bufferView (mis. `0_Image_2.jpg`), jadi pasangan dilakukan pada nama kanonik `Image_N`, bukan pada urutan file |
| [drako_eye_measure.py](../tools/drako_eye_measure.py) | Merender ortografis sepanjang normal mata sendiri, mengukur aperture terbuka dari render (buang retak dengan pembukaan morfologi, pilih komponen yang memuat pupil, dilasi balik, jalur 720 sinar), dan menulis `aperture_points`/`aperture_box_eye` untuk `drako_eyelids_fix.py` | Hapus kartu `DrakoEyelids` sebelum mengukur (alat membuang mesh non-tubuh, tetapi lupakan itu saat memeriksa hasil manual). Aturan yang sudah terbukti: pale tanpa batas milik wajah, lubang bukan-kulit hanya diisi di dalam `paint_box_sides` sisi itu, dan gerbang amber hanya menilai cakram iris `0,7 × min(half_w, half_h)` dari pupil. Kotak cat menandai sudut yang dicat: pada remaja kotak membungkus moncong (u mencapai +0,0905) sehingga ambang luas/hue mentah salah; sisik ternaung juga gagal rasio kroma merah. Bibir lash 1–2 px yang terkikis pembukaan memang ditutup skirt 5,5 mm, bukan hull. Jangan melonggarkan gerbang untuk "menghilangkan" miss tanpa bukti render |
| [drako_eyelids_fix.py](../tools/drako_eyelids_fix.py) | Menyelaraskan kurva blink `Lid_R` ke `Lid_L` sample-per-sample pada seluruh klip dan mengekspor ulang lewat `glb_export`. Mengukur di bind space memang membuang modifier armature, jadi sekarang modifier itu dipasang kembali sebelum ekspor | Dulu penyebab hilangnya `skin` tubuh dewasa (modifier dihapus, tidak dipulihkan). Jangan menambah pengukuran baru tanpa memastikan modifier pulih; `glb_export.check_skin` akan menolak ekspor yang membuat mesh kehilangan binding |
| [drako_loop_restore.py](../tools/drako_loop_restore.py) | Memulihkan key penutup loop yang hilang (clip berakhir pada pose awalnya) dan men-snap key time ke grid fps aset; menulis laporan `LOOP_RESTORE` per klip dan mengekspor lewat `glb_export` dengan `src` agar penjaga skin berlaku | Tidak mengarang key baru di luar kurva authored; jalankan dengan baseline authored yang benar (`--authored`/`authored_*.json`). Verifikasi dengan `lid_sync_verify.py --authored=...` |
| [lid_sync_verify.py](../tools/lid_sync_verify.py) | Audit read-only pada byte GLB: sinkronisasi kurva `Lid_L`/`Lid_R` (tol 1e-04), penutupan seam tiap klip, dan jumlah frame terhadap baseline authored; exit 1 kalau ada desync/SHORT/Stretch | Hanya membuktikan apa yang dibaca runtime soal kelopak dan loop — bukan skin, bukan visual. Pasangan `tmp_release_gate.py` |
| [qa_rig/tmp_release_gate.py](../tools/qa_rig/tmp_release_gate.py) | Gerbang read-only per GLB: mesh terbesar (tubuh) wajib `skin` + `JOINTS_0` + `WEIGHTS_0`; mesh kecil boleh rigid hanya kalau node-nya digerakkan channel animasi; mencetak inventaris joint/clip/channel | Didesain dari bug tubuh dewasa yang membeku. Sudah dikontrol balik: FAIL pada `dewasa_lids/v7/v8.glb`, PASS pada enam aset shipped. Tidak memvalidasi bentuk glTF (masih jalankan `qoder-gltf validate`) |
| [qa_rig/tmp_clip_durations.py](../tools/qa_rig/tmp_clip_durations.py) | Membandingkan tabel `Duration` di `pet.dart` dengan panjang klip hasil baca byte GLB; `--emit-dart` mencetak tabel Dart siap-tempel | Sumber drift: tabel Dart ditulis dari timing authored 25 fps. Setelah aset Drako berubah, regenerasi tabel sebelum build. Alat ini **hanya** memeriksa Dart; tabel kedua ada di `PetBehavior.kt` dan dibandingkan oleh `qa_rig_audit.py` (toleransi 20 ms). Keduanya harus memakai durasi GLB yang sama — ronde 10 November menemukan 12 entri bayi + `sleep` dewasa tertinggal di Kotlin |
| [glb_export.py](../tools/glb_export.py) | Satu jalur ekspor Blender → GLB untuk semua alat Drako: `import_glb(fps=)` men-set `scene.render.fps` (INT di Blender 5.x) sebelum import, menolak grid frame yang bukan 30 fps, lalu `export_glb(src=...)` membandingkan binding kulit sumber vs hasil dan menghapus file + `SKIN_LOSS` jika ada mesh yang kehilangan `skin` | Bila `src` tidak diteruskan, penjaga skin tidak punya baseline — alat baru wajib melewatkan `src`. `reset_pose=True` mengembalikkan pose sebelum ekspor. Jangan pakai `export_force_sampling` tanpa rencana verifikasi ulang seluruh channel |
| [drako_face_repaint.py](../tools/drako_face_repaint.py) | Repaint atlas baseColor: mata (hangatkan iris ke emas, pupil diperdalam, sklera dipotong jadi garis, sisanya kelopak gelap) + medan sisik prosedural pada piksel kulit merah, dengan jitter posisi/radius dan warp domain; halo dari hull bola mata meredam relief di rongga mata | Hanya menyentuh JPEG hasil ekstraksi. Parameter pada §2.7 adalah hasil seleksi terhadap kartu referensi, bukan default; `--lift 0` membatalkan perubahan iris, `--halo 0` membuat sisik masuk ke rongga mata. Atlas dewasa tidak punya piksel putih sehingga tidak ada mata yang ditemukan—halo di-fallback dari keluarga `iris` |
| [drako_texture_reapply.py](../tools/drako_texture_reapply.py) | Menukar image datablock hasil import dengan JPEG hasil repaint, menunjuk ulang semua node `TEX_IMAGE` pemiliknya, lalu ekspor GLB lewat Blender 5.2 (`export_image_format="AUTO"` menyalin byte JPEG, bukan re-encode PNG) | `scene.render.fps = 30` wajib berlaku **sebelum** `bpy.ops.import_scene.gltf` — pada default 24 fps importer memetakan ulang setiap key ke grid 24 fps dan seluruh durasi klip bergeser. Sekarang aturan ini dimiliki `glb_export.import_glb(fps=...)`, bukan lagi tanggung jawab manual tiap pemanggil; memanggil import langsung tetap bisa mengulang kesalahan yang sama. Panggil dengan path blender yang dikutip penuh di Git Bash (tanpa kutip → exit 127). Jangan jalapkan sumbernya pada aset yang sudah di-repaint: `tools/qa_rig/tmp_stage_reapply.sh` membaca `mobile/assets/3d/`, jadi setelah aset diganti skrip itu harus diarahkan ke folder backup agar sisik tidak dipanggang dua kali |
| [make_drako_sprites.py](../tools/make_drako_sprites.py) | Membuat sprite pill kepala/badan dan poster roaming Drako dari potret tahap; background putih dipotong, alpha-trim, padding | Mood lelah/kritis diturunkan dari potret segar dengan tint + tetes keringat/air mata karena kuota ImageGen tidak tersedia; bukan ekspresi baru. Sumbernya potret paket desain, **bukan GLB**, jadi repaint tekstur tidak mengharuskan sprite ini dibuat ulang |
| [make_pill_sprites.py](../tools/make_pill_sprites.py) | Membuat RGBA 192×192, alpha-trim, padding 16 px, centering, laporan alpha tepi | Path/crop/input ekspresi khusus Momo. Menghasilkan resource Android, bukan GLB/rig animasi |

Pipeline aman untuk pekerjaan berikutnya:

1. Simpan input asli dan salinan kerja dengan nama/version unik di folder kerja; catat hash. **Pertahankan penanda tahap dalam path input:** `momo_animate.rebuild()` dan `momo_rig.stage_of()` mencari teks `remaja` atau `dewasa` pada path, lalu default ke bayi jika tidak ditemukan. Nama generik seperti `work.glb` dapat diam-diam memakai parameter bayi; folder bernama `dewasa` juga dapat memengaruhi deteksi. Verifikasi hasil deteksi sebelum authoring, atau ubah alat melalui desain/tes agar menerima tahap eksplisit. Jangan hanya bergantung backup temp bernama basename karena script tidak selalu menimpa backup lama.
2. Inspect skin, joint, rest pose, morph, material, dan klip aktual sebelum memilih alat.
3. Pertahankan mesh/bobot yang sudah diperbaiki. Author klip baru pada salinan kerja; jangan menjalankan semua script lama secara berurutan sebagai resep universal.
4. Jika rebuild animations menghapus weights blink, reattach channel pada node Blink yang sudah ada. `add_blink_channels()` adalah helper, tetapi caller harus menghindari target duplikat dan menambah kurva untuk klip baru; branch saat ini hanya menangani enam nama klip.
5. Jangan menjalankan patch Momo pada rig pet lain tanpa adapter. Tidak adanya nama joint/klip tertentu harus dideteksi sebelum menulis file.
6. Periksa pose awal/akhir loop, perpindahan ke/dari sleep, crossfade ke semua mood, serta deformasi regional. Jangan menutupi bug bobot dengan mematikan seluruh ekspresi.
7. Setelah validasi barulah integrasikan output ke runtime mobile; update manifest aset/metadata/tes. Sinkronkan salinan desain hanya jika masuk scope yang diminta.

Perintah inspeksi read-only, dijalankan dari root proyek:

```bash
python tools/glb_anim_report.py mobile/assets/3d/momo_bayi.glb
python tools/glb_anim_report.py mobile/assets/3d/momo_remaja.glb
python tools/glb_anim_report.py mobile/assets/3d/momo_dewasa.glb
python tools/glb_anim_report.py mobile/assets/3d/drako_bayi.glb
python tools/glb_anim_report.py mobile/assets/3d/drako_remaja.glb
python tools/glb_anim_report.py mobile/assets/3d/drako_dewasa.glb
```

Untuk baseline idle/tap Momo yang sudah dilokalkan: spread Hips.translation dan Chest.scale seharusnya nol; gerak lokal ada pada channel yang sesuai. Jangan menerapkan syarat ini pada klip berjalan/selebrasi yang memang membutuhkan gerak tubuh. Drako bawaan hanya menganimasikan sebagian joint per klip; empat klip tambahan (`greet`, `petting`, `walk`, `wing_show`) menganimasikan seluruh 24 joint agar crossfade tidak menyisakan pose lama. Saat mengedit Drako, pertahankan mesh/skin/tekstur dan daftar 21 klip bawaan; `drako_animate.py` menambahkan, bukan mengganti seluruh animations.

## 7. Pill Android: implementasi sekarang

`PillService` adalah foreground service dengan `START_NOT_STICKY`, notifikasi, serta overlay kecil `TYPE_APPLICATION_OVERLAY` pada Android 8+ (`TYPE_PHONE` untuk API lebih lama). Window memakai `FLAG_NOT_FOCUSABLE`, `PixelFormat.TRANSLUCENT`; lebar/tinggi diukur ulang dan posisi di-clamp terhadap layar.

Data disimpan di `pill_prefs`:

- Identitas/penampilan: `pet` (`KEY_PET`), `stage`, `language`, `bg`, `surface`, `ink`, `accent`, `radius`.
- HP: `hpBonus`, `hpDay`, `hpHealthy`, `hpTired`, `hpCritical`.
- Posisi: `posX`, `posY`; token aksi istirahat bukan state animasi dan tidak boleh menjadi token publik.

`mascotSets` berisi `momo` dan `drako`, masing-masing dengan matriks **3 tahap × 3 mood** untuk bentuk kepala. `bodySets` berisi sprite badan penuh **3 tahap** per pet. Resource berada di `mobile/android/app/src/main/res/drawable-xxxhdpi/`: `pill_mascot_{bayi,remaja,dewasa}.png` (Momo), `pill_mascot_drako_{bayi,remaja,dewasa}.png` (Drako), suffix `_tired` dan `_critical` untuk mode kepala, serta `pill_body_*` untuk badan penuh kedua pet. Mood lelah/kritis Drako adalah turunan tint + tetes, bukan potret ekspresi baru.

Pill punya dua mode yang tersimpan di preferensi Flutter (`pillAnimationMode`, key native `animation`):

- **Statis (flat/default):** ikon dan panel adalah `ImageView`; tidak ada loop kontinu. Animasi hanya reaktif: tap squash-and-settle, sprite berganti fade/pop saat mood/HP melintasi ambang, dan miring saat drag. Tidak ada WebView/GLB.
- **Penuh:** `WebView` transparan (`PetWebRenderer`) di atas poster, memuat halaman + `model-viewer` + GLB dari aset Flutter lewat allowlist `https://pet.local`. Renderer baru di-`start()` 180 ms setelah window benar-benar terlihat; bila window GONE (app foreground/layar mati) tidak ada permintaan load. Timeout 10 detik atau WebView/model gagal → log + fallback poster, bukan klaim animasi penuh.
- `PetLife` mengatur base clip sesuai mood/istirahat, greeting sekali, aksi spontan, dan reaksi tap; clock/random dapat diinjeksi untuk tes.
- Refresh statistik dasar 30 detik; itu bukan frame rate animasi.
- Mode penuh berhenti saat layar mati, app host foreground, panel terbuka, atau mode bukan `full`: lambda `allowed` di `PillService` memeriksa kondisi itu lalu `PetLife` memanggil `renderer.pause()`. Mode statis tidak punya loop untuk dihentikan.
- Posisi drag (x dan y) tersimpan saat ACTION_UP; service stop membatalkan Handler callback, worker, animator ikon/panel, renderer, dan melepaskan view. `tearDown()` juga menutup callback yang tertunda agar tidak menghidupkan animasi kembali.

**Registry sudah end-to-end untuk dua pet.** `GameState.petFamily` berasal dari onboarding; `applyPill` mengirim `pet` dan `form`; `MainActivity.startPill()` memvalidasi nilai `pet` hanya `momo`/`drako` sebelum menyimpannya ke `pill_prefs`. `PillService.currentPet()` memilih `mascotSets`/`bodySets` dan meneruskan `PetKind` ke `PetLife`/`PetWebRenderer`. Pet tak dikenal pada data lama jatuh ke Momo, bukan crash.

Bridge sekarang membawa:
`pet`, `form`, `language`, `stage`, `animation`, `background`, `surface`, `ink`, `accent`, `radius`, `hpBonus`, `hpHealthy`, `hpTired`, `hpCritical`.
`syncPillHp()` memanggil `setPillHpBonus` dengan key `bonus`, bukan snapshot HP final.

`MainActivity.startPill()` memerlukan collection native aktif, izin overlay, dan usage access. Aksesibilitas diperlukan untuk hitungan scroll, bukan untuk rendering pet. Jangan menambah pemantauan isi aplikasi lain untuk membuat pet bergerak.

Pill toggle bersifat runtime: proses mati/force-stop/reinstall tidak memulihkan pill; membuka app juga tidak menyalakannya kembali. Mode animasi dan bentuk pill tetap tersimpan dan dipakai saat pengguna menyalakan pill lagi. `petFamily` tidak dapat diganti dari Profil; restore backup saat ini dapat mengosongkan state onboarding, sehingga pemilihan ulang masih mungkin terjadi. Itu batas yang belum ditutup, bukan jaminan permanen yang sudah diuji ulang.

Service overlay native masih memiliki jalur `_syncPetOverlay` dan `PetOverlayService`, tetapi karena Profil build ini tidak mengekspos opt-in, jalur tersebut tidak boleh dipromosikan sebagai fitur pengguna. Jangan menyalakan overlay dari perubahan tema, backup, atau lifecycle tanpa opt-in eksplisit.

## 8. Overlay pet keliling layar: implementasi sekarang

**Status build 31 Oktober: service native ada, tetapi fitur tidak dapat diaktifkan dari UI.** `PetOverlayService` adalah foreground service terpisah dari pill (`specialUse`, notifikasi id 43) dengan jendela `TYPE_APPLICATION_OVERLAY` berukuran 160 dp, `FLAG_NOT_FOCUSABLE | FLAG_HARDWARE_ACCELERATED`, `PixelFormat.TRANSLUCENT`. Service tetap berjalan saat app foreground tetapi jendelanya GONE; pet muncul lagi di atas app lain. Service ini pernah di-QA pada build 29 Oktober, tetapi Profil saat ini tidak menampilkan toggle/mode overlay; ronde Drako tidak menguji ulang akses pengguna maupun roaming. Jangan mengklaim fitur ini tersedia sampai UI dan QA-nya dipulihkan.

Pemetaan unit:

1. **Pet definition/registry:** `PetKind` dan `PetCatalog` kini mencakup Momo dan Drako; poster `pet_roam_{bayi,remaja,dewasa}` dan `pet_roam_drako_*` tersedia. Namun tidak ada kontrol UI yang menyalakan service.
2. **Behavior selector:** `PetBehavior.kt` (murni) + `PetLife` (timer, anti-repeat, greeting, walk callback, sleep priority).
3. **Renderer adapter:** `PetWebRenderer` memuat halaman/JS/GLB dari aset APK via allowlist `PetWebAssets` (`https://pet.local`), plus bridge `loaded` terbatas. Timeout 10 detik → status fallback poster.
4. **Overlay host:** `PetOverlayService` mengatur izin, service, posisi/insets, drag (dua sumbu, clamp), tap = reaksi, long press 480 ms = elus, dan jalan otomatis dengan bounce di tepi.
5. **Settings dan persistence:** state `petOverlayEnabled`, mode `overlayAnimationMode` (`flat`/`full`), posisi `posX/posY`, bahasa, tahap masih tersimpan, tetapi **tidak ada kontrol di `profile_pet.dart`** untuk mengubah/menyalakannya. Restore backup tetap tidak boleh menyalakannya.

Start renderer bersifat lazy: `PetOverlayService`/`PillService` hanya memanggil `renderer.start()` setelah window terlihat (180 ms), layar menyala, mode penuh, dan app host tidak foreground. Ini yang mencegah kegagalan WebGL saat halaman dimuat di window GONE (root cause fallback yang ditemukan sebelum perbaikan).

Poster tetap berada di belakang WebView transparan; saat model belum siap atau gagal, poster terlihat. Jangan mengklaim full animation aktif hanya karena window tampil — cek log `PetWebRenderer`/status `KEY_FALLBACK`.

Persyaratan renderer dan gerak:

- Gunakan GLB rig yang sama, bukan mengganti mode penuh dengan sprite squash dan menyebutnya animasi rig.
- Renderer luar aplikasi harus bisa hidup tanpa Activity Flutter. Server loopback milik widget sekarang tidak boleh diasumsikan tetap tersedia sesudah Activity/widget ditutup. Paket JavaScript/model perlu lokal dan lifecycle pemuat aset harus jelas.
- Gait/klip berjalan menggerakkan kaki/tubuh/ekor; perpindahan WindowManager disinkronkan dengan langkah, bukan menggeser pose diam.
- Pilih satu pemilik translasi dunia: klip root-motion atau host movement yang dikalibrasi. Jangan menggandakan translasi keduanya; hentikan dengan settle pose.
- Clamp berdasarkan ukuran overlay dan insets; pertimbangkan rotasi, ukuran layar berubah, status/navigation bars, panel pill, dan keyboard. Jangan menjanjikan deteksi keyboard lintas aplikasi sebelum mekanismenya dibuktikan.
- Window kecil mengikuti pet. Transparansi pixel tidak otomatis membuat sentuhan pada bagian kosong diteruskan: Android melakukan hit-test window persegi dan menerapkan batas overlay/touch security. Verifikasi di perangkat, bukan mengklaim per-pixel passthrough.
- Jangan menghalangi UI izin, authentication, atau sistem; Android bisa menyembunyikan overlay pada layar sensitif. Jangan mencoba bypass.
- Tutup/pause pet saat app sendiri foreground supaya tidak ada dua pet aktif bertumpuk. Stop playback/timer saat layar mati, mode off, izin hilang, collection opt-out, restore, atau hapus data.
- Kontrol mati **belum ada di Profil build ini**; jika UI dikembalikan, sediakan toggle opt-in eksplisit dan jangan menyalakannya dari lifecycle. Long press saat ini berarti elus, bukan sembunyikan. Simpan posisi saat aksi pengguna berakhir, bukan menulis SharedPreferences tiap frame berjalan.
- Jika renderer/model gagal, laporkan kondisi dan gunakan fallback statis yang jelas jika tersedia. Jangan menampilkan status full animation sukses ketika GLB tidak pernah loaded.

## 9. Pengaturan mode dan daya

**Permintaan pengguna:** mode ini pilihan pengguna di pengaturan, bukan fitur wajib yang selalu aktif. Pengguna ingin flat/statis untuk menghemat daya atau full animasi dengan konsekuensi penggunaan daya lebih tinggi.

Model UI yang diterapkan di kartu "Pet & animasi" (Profil):

| Kontrol | Pilihan | Efek |
| --- | --- | --- |
| Floating Pill | Switch runtime terpisah dari mode | Menyalakan/mematikan service; memilih bentuk/mode tidak menyalakan pill |
| Bentuk pill | Kepala / Badan penuh | Kepala: avatar kecil di pill, tap melebar jadi badan penuh lalu membuka panel. Badan penuh: badan berdiri di samping pill sejak awal; tap membuka panel |
| Mode animasi pill | Statis (hemat) / Penuh | Statis: sprite + animasi View tanpa WebView. Penuh: rig GLB dalam framing pill |
| Pet luar aplikasi | Tidak diekspos | Service/state native masih ada, tetapi tidak ada toggle di Profil build ini; jangan mengklaim fitur tersedia |

Preferensi: `pillAnimationMode` dan `overlayAnimationMode`, nilai `flat`/`full`, default **flat**; `pillForm` default **head**; opt-in `petOverlayEnabled` default **false**. Label tidak mencantumkan persentase hemat/boros.

Mode statis yang diterapkan:

- Tidak memuat WebView/GLB, tidak menjalankan program spontan/render loop pill; drag dan aksi manual tetap bekerja (tap memutar bob ringan, sprite berganti saat HP berubah).
- HP, tahap, ekspresi, dan statistik tetap diperbarui saat data berubah; statis tidak berarti data beku.
- Bukti historis 29 Oktober: dua frame statis overlay identik piksel selama 2,5 detik dan tidak ada log start renderer; pill statis juga 0 piksel berubah. Pada ronde Drako 31 Oktober, pill badan penuh statis juga 0 piksel berubah dan mode penuh beranimasi (`finalbody_frame_1..3`).

Mode penuh memakai klip rig dan crossfade 250 ms; tetap berhenti saat hidden/screen-off/app foreground dan tidak memakai polling usage per frame. Belum ada cap FPS atau klaim efisiensi daya yang diukur.

Transisi penuh→statis/off membatalkan callback/renderer lama lewat `tearDown`; native dan Flutter membaca mode yang sama. Mengganti mode tidak mengubah izin Android, HP, XP, collection consent, atau mode Jeda Sadar. Restore backup boleh mengembalikan preferensi tampilan yang valid, **tidak** mengaktifkan service/overlay otomatis.

## 10. Checklist menambah pet baru

### 10.1 Paket yang harus diserahkan pembuat aset

- [ ] Identitas stabil `petId` yang tidak tergantung display name; nama Indonesia/Inggris dan asal/lisensi aset.
- [ ] Model setiap tahap yang didukung; jika hanya satu tahap, definisikan mapping/fallback secara eksplisit.
- [ ] GLB dengan skin/joint atau mekanisme animasi yang sesuai; rest pose, arah depan, ukuran/unit, pivot dan bounding box diketahui.
- [ ] Kontrak klip dasar atau mapping semantic yang valid, durasi, loop/one-shot, serta pose statis per mood/tahap. Drako adalah contoh paket 25 klip; Momo 12 klip. Jangan memaksa jumlah klip sama.
- [ ] Daftar kemampuan opsional: greeting, grooming, stretch, walking, petting, sayap/aksi khusus. Jangan mengiklankan aksi yang tidak ada.
- [ ] Rig map semantic: kepala, telinga/tanduk, kaki/paw, torso, ekor, mata, sayap; tulis bagian yang memang tidak dimiliki pet.
- [ ] Camera framing untuk tubuh penuh dan crop kepala pill; padding pose ekstrem. Drako memakai framing berbeda untuk bayi/remaja dan dewasa.
- [ ] Aset statis transparan sesuai kebutuhan pill; untuk Momo baseline 192×192, padding 16 px dan alpha tepi nol. Pet baru boleh berbeda jika adapter/UI divalidasi.
- [ ] Laporan hash, ukuran, morph, jumlah joint, durasi, validasi deformasi, dan pratinjau animasi.

Metadata harus menjadi data registry, bukan `if (name == 'Momo')` tersebar. Field yang perlu diwakili: `petId`, localized display name, stage mapping, asset paths, semantic clip mapping, durations, optional capabilities, rig mapping, camera presets, static fallbacks. Implementasi saat ini ada di `PetProfile`/`PetRegistry` (Flutter) dan `PetCatalog` (Kotlin); pet baru harus menambah keduanya plus aset native, bukan hanya satu sisi.

### 10.2 Titik integrasi kode

- [ ] Daftarkan aset pada `mobile/pubspec.yaml` dan uji bahwa output APK benar-benar membawa aset.
- [ ] Tambahkan `PetFamily`/`PetProfile` di `pet.dart` dan `PetKind`/`PetCatalog` di native; pisahkan species/`petId` dari tahap/level. Pet baru bukan enum `Stage` baru.
- [ ] Gunakan `PetProfile.look(stage)` untuk asset/kamera dan `durationOf(stage, clip)` untuk timer; jangan menambah lookup `if (pet == ...)` baru di layar.
- [ ] Perbarui semua pengguna `Companion3D`, collection selector, l10n/semantics, alt text, framing, serta dialog evolusi. Jangan mengganti nama widget saja lalu melupakan layar misi/istirahat.
- [ ] Kirim `pet` melalui `applyPill` → `UsageService` → `MainActivity`; validasi against registry dan persistensi native. Nilai tak dikenal harus jatuh ke Momo, bukan crash.
- [ ] Tambahkan sprite kepala (3 tahap × 3 mood) dan badan (3 tahap), plus poster overlay jika fitur itu diekspos; jangan membuat indeks mood/tahap yang bisa keluar batas.
- [ ] Sinkronkan perubahan pet, tahap, bonus HP, bahasa/tema, bentuk, mode daya, dan state istirahat untuk renderer aktif. Jangan memakai callback yang menutup state lama.
- [ ] Unknown petId pada save lama memilih fallback kompatibel; invalid input eksternal ditolak. Jangan mengeksekusi path/file/URL bebas dari metadata impor.
- [ ] Pastikan mode mati/statis/penuh tidak menyalakan service tanpa opt-in.
- [ ] Update allowlist/validasi backup dan migrasi preference jika petId/mode baru harus disimpan; jangan otomatis mengizinkan seluruh key baru.
- [ ] Jika spesies punya rig berbeda, pakai semantic clip/joint adapter. Jangan menerapkan wajah/eye bounding box atau morph kelopak Momo secara universal; Drako memakai kartu kelopak ber-skin dan tulang `Lid_*`.
- [ ] Tambahkan tes regresi: pemilihan pet tidak mengubah data pemakaian, HP, hadiah, limit, bank, atau collection consent.
- [ ] Uji framing kamera setiap tahap dengan pose sayap/ekor ekstrem; jangan memakai satu target untuk semua tahap.

### 10.3 Urutan kerja yang aman

Inspect aset → desain kontrak → tes gagal → implementasi registry/adapter → author/validasi klip → integrasi state/pill/overlay → tes lintas lifecycle dan privasi → selesai semua kode → satu build release → QA MuMu → dokumentasi bukti.

Gunakan tahap terpisah yang masing-masing bisa dites: registry dan aset; perilaku dalam app; pengaturan daya; renderer/overlay luar app. Jangan sekaligus merombak gamifikasi atau analytics yang tidak terkait.

## 11. Privasi, keamanan, dan pemulihan

- Tidak ada commit, deploy, publish, force-push, perubahan AGENTS.md, atau pengaturan izin agent tanpa otorisasi yang sesuai. Dokumen ini bukan izin tindakan itu.
- User mengaktifkan overlay dari pengaturan dengan pengungkapan izin. Jangan menyalakan melalui import backup, update tema, perubahan pet, atau lifecycle restart tanpa opt-in yang masih berlaku.
- `deleteAllData()` sekarang menggunakan tombstone collection, menghentikan writer, membersihkan native/history/preference, dan membuat error penghapusan terlihat. Tambahkan cleanup overlay/cache/model baru ke jalur ini sebelum fitur dianggap selesai.
- `BackupService._keepOff()` menghentikan collection, pill, pause, reminder; `_replacePreferences()` menonaktifkan service flags dan consent. Overlay baru harus mengikuti jaminan tersebut termasuk pada rollback gagal.
- Pilihan pendamping disimpan sekali saat onboarding dan tidak punya jalur ganti di layar mana pun. Namun restore backup saat ini mengosongkan state onboarding, sehingga pemilihan ulang dapat terjadi. Jangan mengiklankan "permanen bahkan setelah restore" sampai perilaku ini diputuskan dan diuji.
- Backup native sekarang version 1 dengan allowlist `scrollCounts`, `monitoredPackages`, `limits`, `bankAllowances`; tidak membawa izin Android, state service, atau konfigurasi visual pill. Schema Dart juga allowlist ketat. Jangan menambah state overlay tanpa validasi/migrasi.
- Jangan membaca teks, isi halaman, atau ketikan aplikasi lain untuk interaksi pet. Input cukup dari window pet sendiri; usage/scroll memakai mekanisme dan consent yang sudah ada.
- `INTERNET` saat ini dipakai untuk pemuatan 3D lokal; konfigurasi cleartext hanya mengizinkan loopback `127.0.0.1`, tidak seluruh internet/LAN. Jangan memperluas cleartext global untuk renderer baru.
- Paket renderer baru harus lokal, dependensi diverifikasi, URL/file allowlist, dan bridge hanya memproses event yang dikenal. Jangan memuat URL sembarang dari backup atau memberi JS akses native tanpa batas.
- Service foreground pet baru, jika diperlukan, harus dideklarasikan non-exported dengan izin/tipe/notifikasi sesuai target Android. Tipe `specialUse` yang dipakai pill bukan bukti bahwa semua penggunaan baru otomatis memenuhi kebijakan distribusi.
- Rilis lokal memakai keystore release privat, bukan debug signing dan bukan kunci Play Store. Jangan menyalin secret/keystore ke panduan, log, backup, atau output publik.

## 12. Verifikasi dan bukti yang harus dikumpulkan

### 12.1 Tes yang sudah tersedia

- [companion_lifecycle_test.dart](../mobile/test/companion_lifecycle_test.dart): pause ketika tab/background/route tidak aktif dan late-load tidak memulai hidden animation.
- [lifecycle_webview_fake.dart](../mobile/test/lifecycle_webview_fake.dart): fake WebView; memverifikasi panggilan JavaScript, bukan hasil render/GPU.
- [companion_behavior_test.dart](../mobile/test/companion_behavior_test.dart): perilaku hidup Dart (spontan, anti-repeat, sleep priority, tap/petting) untuk kedua pet.
- [pet_behavior_test.dart](../mobile/test/pet_behavior_test.dart): registry Momo/Drako, 25 klip Drako, framing per tahap, bobot/jeda state-aware, batas mood/tahap, tap alternation.
- [pet_glb_asset_test.dart](../mobile/test/pet_glb_asset_test.dart): membaca **byte GLB yang shipped** (bukan registry saja) dan menuntut tiga hal — mesh tubuh tiap pendamping ter-skin (`skin` + `JOINTS_0` + `WEIGHTS_0`), setiap `Duration` di `pet.dart` sama dengan panjang klip di file sampai milidetik, dan setiap klip yang bisa dipilih behaviour layer ada di GLB tahap itu. Kontrol balik sudah dijalankan: menukar `drako_dewasa.glb` dengan versi pra-perbaikan membuat tes kulit FAIL (`DrakoMesh ... neither skinned nor node-animated`) dan tes durasi FAIL (`sleep: dart=4200ms file=4133ms`); setelah file dipulihkan (SHA-256 diverifikasi) keduanya PASS lagi. Toleransinya sengaja 2 ms, bukan satu frame — satu frame justru bug yang dijaga.
- [pet_settings_test.dart](../mobile/test/pet_settings_test.dart): bentuk/mode pill tersimpan, opt-in overlay terpisah, UI pengaturan tidak menyalakan pill/overlay.
- [theme_offline_test.dart](../mobile/test/theme_offline_test.dart): termasuk 4 tes fill tint opaque untuk kartu terpilih di setiap tema.
- [app_lifecycle_test.dart](../mobile/test/app_lifecycle_test.dart), [tab_lifecycle_test.dart](../mobile/test/tab_lifecycle_test.dart): regresi lifecycle aplikasi/tab.
- [usage_bridge_test.dart](../mobile/test/usage_bridge_test.dart): kontrak MethodChannel, termasuk payload `pet`/`form`.
- [profile_flow_test.dart](../mobile/test/profile_flow_test.dart), [product_screens_correctness_test.dart](../mobile/test/product_screens_correctness_test.dart): pengaturan/layer produk terkait.
- [backup_test.dart](../mobile/test/backup_test.dart), [privacy_state_test.dart](../mobile/test/privacy_state_test.dart): batas restore, consent, penghapusan.
- `mobile/android/app/src/test/kotlin/com/screentime/companion/screentime_companion/`: `PetBehaviorTest.kt` (17 tes, termasuk Drako), `PetWebAssetsTest.kt` (6), `NativePolicyTest.kt` (4), `AccessibilityCheckTest.kt` (5), `UsageAggregationTest.kt` (11) — total **43 tes**.
- Alat audit 31 Oktober: `tools/qa_rig_audit.py` (struktur GLB, skin/bobot, set klip, durasi vs registry, loop, varian idle, cakupan dan puncak skala kelopak, langkah translasi/skala, flip kuaternion; `--assets-dir` untuk staging), `tools/qa_render_glb.py` (render Blender headless), `tools/qa_make_sheets.py` (contact sheet), dan `tools/drako_animate.py` (generator Drako deterministik termasuk penggantian idle kritis). Bukti JSON/frame/sheet ada di `tools/qa_rig/`; alat ini read-only kecuali generator yang menulis ke direktori keluaran eksplisit.
- Alat QA khusus kelopak/idle: `tools/qa_pet/tmp_all_clip_frames.py` merender empat frame per klip (awal 12%, tengah 45%, akhir 85%, dan puncak `scale.y` kelopak) dengan kamera akhir 480×480; `tools/qa_pet/tmp_contact_sheets.py` menyusun 15 contact sheet per tahap/kelompok di `tools/qa_pet/shots_clips/sheets/`. Keduanya read-only terhadap GLB dan tidak dipanggil runtime.
- Validator framing rotasi: `tools/qa_rig/tmp_orbit_fit.py` (read-only) memproyeksikan seluruh vertex skinned ke kamera model-viewer pada 12 azimuth 0–330° langkah 30°, 6 frame per klip, FOV 26°, aspek 1,0 (kanvas pet persegi); `tmp_orbit_fit_np.py` adalah versi lama 13 azimuth/aspek 1,05. Log final ada di `tools/qa_rig/head_fix/final_2026_11_02/orbit_retarget_*.log`; log ronde sebelumnya di `tools/qa_rig/tmp_orbit_*_final.log` dan `tmp_orbit_momo_*_idle.log`.
- Alat QA kepala/leher Drako 2 November: `tools/drako_head_skin.py` (generator bobot/pivot, menulis GLB keluaran eksplisit), `tools/drako_head_retarget.py` (generator retarget roll→yaw pada `Head`/`Neck`), `tmp_head_axis_probe.py` (dekomposisi yaw/pitch/roll dunia per bone), `tmp_make_sheets.py` (sheet sebelum/sesudah), `tmp_app_render.py` (render kamera aplikasi), `tmp_head_skin_audit.py` (audit bobot per kelas), `tmp_head_region_probe.py`/`tmp_head_contam_cloud.py` (asal vertex yang mendapat `Head`), `tmp_head_motion_region_probe.py` (displacement skinned per grup bone asal), `tmp_lid_horn_channel_probe.py` (drift kelopak/tanduk), `tmp_glb_struct_diff.py`/`tmp_glb_struct_diff_skin.py` dan `tmp_glb_clip_inventory.py` (struktur dan inventaris klip), serta `tmp_head_wide_render.py` (render full-body fixed-camera). Bukti final ada di `tools/qa_rig/head_fix/final_2026_11_02/` (GLB final, log retarget/axis/diff/inventory/validate/audit, render before/after, sheet, video dan frame runtime); log lama `gen_*`, `audit_*`, `motion_region_*`, `lid_probe_*`, `struct_skin_*`, `clips_*`, `orbit_skin_*`, `validate_skin_*` dan gambar `full_cand_*`, `full_orig_*`, `render_skin_bayi*`, `zoom_*` ada di `tools/qa_rig/head_fix/`.

- Alat QA 3 November (ronde §2.8): `tools/lid_sync_verify.py` dengan baseline `--authored=tools/qa_rig/dragon_look/authored_{bayi,remaja,dewasa}.json` (sinkron kelopak + seam + jumlah frame), `tools/qa_rig/tmp_release_gate.py` (binding kulit per mesh, dengan kontrol balik pada `dewasa_lids/v7/v8.glb` yang memang rusak), `tools/qa_rig/tmp_clip_durations.py` (tabel Dart vs byte GLB, `--emit-dart` untuk regenerasi), dan `tools/qa_rig/tmp_app_render.py` + `eye_map/app_sheet.py` (render kamera aplikasi 900×1600 dan lembar A/B mata). Log dan buktinya di `tools/qa_rig/dragon_look/`: `gate_finalists.log`, `shipped_final_audit.log`, `final_lid_sync.log`, `final_analyze_test.log`, `fps24_exit.log` (kontrol: ekspor pada 24 fps ditolak, `REAL_EXIT=1`, file tidak ditulis), `lid_fix_v9.log`, `loop_restore_v10.log`, `dewasa_v10_render.log`, `eye_map/dewasa_v10_ab*.png`.

Tes ini tidak membuktikan kualitas deformasi 3D atau beban GPU; untuk itu gunakan sequence/video dan pengukuran perangkat. Dua pet tercakup; pet ketiga belum.

### 12.2 Acceptance checklist fitur baru

- [ ] Load setiap pet/tahap dan klip; missing capability punya fallback aman; model rusak terlihat sebagai error.
- [ ] Drako dewasa membuka/mengepakkan sayap tanpa crop; bayi/remaja tetap lucu dan framing kepala tidak terpotong. Ini harus diuji visual, bukan hanya cek nama klip.
- [ ] Kartu terpilih di tema dengan hard shadow tetap opaque dan teks terbaca; ikon tahap mengikuti pet.
- [ ] HP 61/60/30/29 memilih state yang benar; data unknown tidak ditampilkan sebagai HP sehat nyata.
- [ ] Sleep memblokir greeting/walking/random dan reaksi yang membangunkan; perubahan state saat one-shot ditangani deterministik.
- [ ] Random memiliki jeda/anti-repeat dan tidak menumpuk; ketuk berulang/long press/drag tidak melahirkan timer liar.
- [ ] Gerak tangan/telinga/ekor tidak menarik wajah/torso yang seharusnya diam; gait sesuai mesh, loop mulus, kaki tidak sekadar slide.
- [ ] Mode statis tidak menjalankan animasi View/GLB; HP tetap update. Penuh→statis/off menghentikan callback yang tertunda.
- [ ] Memilih bentuk/mode tampilan saja tidak menyalakan pill. Jika kontrol overlay dikembalikan, uji opt-in terpisah dan pastikan tidak aktif otomatis.
- [ ] Kepala/tubuh tidak crop pada layar kecil/besar, rotasi, perubahan stage, panel, dan pose ekstrem.
- [ ] Geser horizontal memutar pet 360° tanpa crop di seluruh azimuth; drag tidak memicu tap/elus, drag vertikal tetap menggulir, dan kamera kembali ke preset saat pet/tahap berganti.
- [ ] Sentuhan luar window pet tidak diblokir; margin window dan kebijakan Android 12+ diuji. Tidak ada overlay touch fullscreen.
- [ ] Screen-off, host foreground, renderer restart, proses mati, izin dicabut, opt-out collection, delete dan restore mematikan/hide komponen sesuai desain.
- [ ] Import petId/mode invalid ditolak atau dimigrasi sesuai asal data; import tidak memulihkan izin atau service opt-in.
- [ ] Penggunaan daya diukur terpisah: off, statis, penuh; skenario/durasi/perangkat/suhu dan metode dicatat. CPU/RAM/frame timing bukan pengganti pengukuran baterai fisik.

Perintah tes dari working directory `mobile/`:

```bash
flutter analyze
flutter test
```

Tes native dari working directory `mobile/android/` (Git Bash):

```bash
./gradlew testDebugUnitTest
```

Setelah seluruh kode dan tes selesai, satu build dari `mobile/`:

```bash
flutter build apk --release
```

Build release final 31 Oktober dijalankan setelah kelopak, idle, rotasi, dan seluruh tes selesai; build kepala final 2 November dijalankan sekali setelah retarget dan semua audit selesai. Perubahan dokumentasi ini tidak memicu build baru. Build kelopak (`12e2b849…`), build final 31 Oktober (`65ab60b4…`), dan build kepala (`dc3e02b7…`, §2.6) adalah tiga build berbeda; jangan mencampur hash/asetnya. Catat size/hash/signature APK, aset yang dibundel, device Android, dan hasil QA; jangan menerbitkan keystore atau mem-bypass signing checks.

### 12.3 Batas QA yang telah diketahui

QA terbaru 31 Oktober 2026 memakai MuMu Android 12, 900×1600, density 320, WebView 110, dengan tangkapan layar dan diff piksel. Batasnya:

- Screenshot/diff piksel membuktikan ada perubahan frame dan mode statis tidak mengubah piksel, bukan kualitas gerak, kelancaran, atau beban GPU. Belum ada video/sequence formal maupun pengukuran baterai/CPU di perangkat fisik.
- Audit struktural menemukan 257 vertex Momo bayi dengan jumlah bobot minimum 0,892669; tidak terlihat cacat pada render 12 klip dan aset Momo tidak diubah. Validator `qoder-gltf validate` sekarang menerima ketiga GLB Drako baru (`valid: true`) dengan tiga warning masing-masing: tangent-space dibuat runtime dan dua node skinned mesh non-root. Momo tetap ditolak validator (ratusan error min/max accessor lama) dan tidak disentuh. Ini catatan portabilitas metadata, bukan kegagalan runtime yang teramati; Blender dan WebView memuat semua aset.
- Empat idle kritis Drako bayi/remaja beranimasi, dan ketiga tahap sekarang punya kelopak yang berkedip/menutup saat sleep. Namun ekspresi wajah tetap berasal dari tekstur dan postur; tidak ada morph alis/mulut. Keadaan kritis dibaca dari postur, gemetar, dan ekor, bukan ekspresi wajah kompleks.
- Kedip memakai dua kartu kelopak ber-skin, bukan deformer wajah. Pada dewasa mata aslinya kecil dan tertutup sebagian surai, sehingga kedip paling jelas pada bayi/remaja dan lebih halus pada kamera dewasa. Kedip satu-klip bersifat deterministik (satu kali di 42–45% untuk aksi; 30%/64% untuk idle), bukan acak tiap putaran.
- Semua klip dewasa ikut ditulis ulang oleh putaran kelopak, jadi klip dewasa tidak lagi byte-identik dengan build §2.2. Perbandingan yang sah adalah hash baru di §4.1b, bukan hash lama.
- HP emulator 100/100, jadi idle kritis tidak dipaksa muncul di aplikasi; bukti geraknya berasal dari render offline dan audit loop.
- Mood statis Drako (pill) memakai tint + tetes keringat/air mata, bukan ekspresi baru; kualitasnya lebih sederhana daripada Momo. Ini keterbatasan aset, bukan bug yang disembunyikan.
- `wing_show` dewasa sudah diverifikasi di dalam aplikasi, tetapi **belum** di pill bentuk badan penuh: tap badan membuka panel, bukan memutar klip. Jangan mengklaim keduanya sudah diuji.
- Panel pill bentuk badan melebar mengikuti ruang yang tersedia; ini perilaku desain lama, bukan regresi Drako. Tidak diuji pada layar sangat kecil/rotasi.
- Pet keliling luar aplikasi tidak memiliki kontrol di Profil build ini; service native tidak di-QA ulang pada ronde Drako. Jangan mengklaim fitur itu dapat diaktifkan.
- Tap injeksi emulator kadang tidak mendarat pada kontrol segmented di offset scroll tertentu; salah tap penguji diperbaiki dengan membaca ulang koordinat. Tidak ditemukan kode aplikasi yang bergantung offset.
- Binding Aksesibilitas lewat `settings put secure` tidak berhasil di MuMu pada ronde ini (nilai tersimpan, service tidak terikat). Pengaktifan lewat UI Settings berhasil; setelah QA layanan dimatikan dan nilai secure dibersihkan. Jangan menganggap setelan adb sebagai bukti fitur berjalan.
- Data sub-menit baru terbukti dengan sesi 58 detik; durasi lebih kecil dari satu detik tetap tidak dapat dibedakan karena sumber native memakai resolusi detik. Hitungan scroll hanya diuji pada Chromium yang dicentang sementara.
- Setelah akses pemakaian dicabut, pill/overlay berhenti dan opt-in tetap tersimpan; membuka app menampilkan status menunggu sampai toggle dimatikan/dinyalakan. Ini perilaku saat ini, bukan crash; jangan mengklaim auto-restore.
- Mode pill runtime-only: app reopen tidak menyalakan pill kembali.
- Restore/hapus data tidak diuji ulang pada ronde ini. Jaminan lama dari tes backup/privacy tetap berlaku, tetapi bukan bukti runtime baru. Restore backup masih dapat mengosongkan onboarding dan membuka pemilihan pendamping ulang.
- Ukuran APK build kepala final 2 November 114.796.090 byte, 82.540 byte lebih besar dari build kepala sebelumnya (114.713.550) karena tiga GLB Drako diekspor ulang (dewasa +177.316 byte), dan bertambah 31.490.705 byte dibanding build Momo 29 Oktober (83.305.385); kenaikan berasal dari tiga GLB Drako sekitar 37,4 MB mentah plus kelopak, bukan klaim bahwa semua halaman menjadi lebih berat saat runtime.
- Rotasi sudah diuji di Drako (0/80/176/256/336/376°, dewasa, pratinjau Profil) dan Momo (0/80/176/330°); drag tidak memicu tap dan drag vertikal tetap menggulir. Sweep ketat Momo 4,8 m menemukan pose ekstrem yang melewati batas matematis (maks 1,12) walau tidak terlihat terpotong pada tangkapan; layar kecil, tablet, dan perangkat fisik belum diuji. `sleep` runtime tidak direkam ulang di build 31 Oktober; klip/kelopaknya sama sejak build kelopak saat itu. Catatan ini tidak berlaku untuk dewasa sejak 3 November: `sleep` dewasa berubah (124→126 frame, seam 0,00161904→0,0) dan dibuktikan pada kamera aplikasi lewat `sheet_dewasa_sleep.png`, sedangkan rekaman runtime `sleep` di dalam aplikasi belum diulang (§2.8).

### 12.4 Status acceptance pada QA 31 Oktober 2026, diperbarui 10 November 2026

| Butir | Status | Bukti / catatan |
| --- | --- | --- |
| Dua pet terdaftar dan dapat dipilih | Lulus (runtime) | Onboarding Momo/Drako; `petFamily` tersimpan; tidak ada tombol ganti di Profil |
| Drako 25 klip dimuat | Lulus (GLB + render + tes) | `qa_rig_audit.py`, set klip/durasi vs Dart/Kotlin, `pet_behavior_test.dart`, `PetBehaviorTest.kt`; 4 frame per klip dirender, belum ada video formal |
| Audit enam GLB / 111 klip | Lulus (offline) | 22+26 joint, bobot, set klip, loop, varian idle, cakupan kelopak; Drako 0 error/0 warning pada audit final 2 November; validator `valid: true`, 0 error, 3 warning metadata per GLB (§2.6/§12.3); Momo bayi satu cacat bobot lama yang tidak terlihat di render. Audit ulang 3 November pada aset shipped (`shipped_final_audit.log`): ketiga tahap 25 klip × 78 channel, `LID_SYNC PASS 25/25`, `LOOP_SEAM 25/25`, `LOOP_FRAMES PASS 25/25`, `EXIT_*=0` (§2.8) |
| Idle kritis Drako bayi/remaja | Diperbaiki + lulus render | Sebelumnya statis 0 piksel; kini 25 channel, loop bersih, gerak 2.352–11.241 piksel; `sheets_regen/drako_bayi_sheet_2.png`, `drako_remaja_sheet_2.png` |
| Kelopak mata + kedip Drako | Lulus (struktur + render + runtime) | 26 joint, `DrakoEyelids` ber-skin, 25/25 klip punya `Lid_L`+`Lid_R`, puncak `scale.y` 30, sleep tertutup; 300 frame kamera akhir menunjukkan mata tertutup tanpa kelopak lepas; video runtime 12 detik frame 532–548 mata tertutup (`lids_idle.mp4`, `lids_blink_540.png`). Ronde 3 November: aset dewasa shipped ternyata **LID-DESYNC pada 24/25 klip** (kurva `Lid_L` vs `Lid_R` beda nilai, d 6,3–7,5) dan kelopaknya dibangun ulang 2.280+152 → 2.392+184 vertex; sekarang `LID_SYNC PASS 25/25` pada ketiga tahap dan coverage bola mata 100% dengan standoff puncak 9,89/12,82 mm (§2.8) |
| Idle kontinu Drako | Lulus (kode + render + runtime) | Varian di-loop penuh, hold 6–12 detik, crossfade 250 ms; tes `companion_behavior_test.dart`/`pet_behavior_test.dart`; video runtime 12 detik menunjukkan loop idle dan kedip (§2.5) |
| Visual 25 klip × 3 tahap | Lulus (render) | 299 PNG unik + 15 contact sheet; tidak ada crop, tekstur hilang, atau anggota badan terlepas; kedip dewasa lebih halus karena mata kecil |
| Pratinjau Bayi/Remaja dengan GLB baru di app | Lulus (runtime) | Idle berubah 7.456–28.615 piksel, ketuk 40.887 piksel, tanpa cacat; `rig_fix_03..14` |
| Framing Drako per tahap | Lulus (render) | Orbit awal 0°: bayi `5.5m`/target `0.55m`, remaja `5.4m`/`0.43m`, dewasa `4.55m`/`-0.06m`; sweep ulang 2 November 2026 (12 azimuth × 25 klip × 6 frame, aspek 1,0) semua `fit=YES` (max_x/max_y: 0,727/0,963; 0,944/0,959; 0,995/0,653) |
| Gerak kepala/leher Drako | Lulus (struktur + render + runtime) | Dua lapis: bobot/pivot final (bayi `Head` 0,9200/`Neck` 0,8520; remaja 1,2350/1,1660) lalu retarget roll→yaw di 25 klip ketiga tahap (head gain 1,5/roll keep 0,10; neck gain 0,40/roll keep 0,20). Roll dunia turun dari 10,96–27,06° menjadi yaw 11,27–28,70° dengan sisa roll ≤3,82°; hanya rotasi `Neck`/`Head` dan rebase kelopak yang berubah; struktur/inventaris 0 fail; render before/after dan runtime idle/petting menunjukkan kepala menoleh tanpa lean (§2.6) |
| Bacaan "naga" Drako (repaint tekstur) | Lulus (struktur + render + runtime ketiga tahap) | Atlas baseColor ketiga tahap direpaint: iris dihangatkan ke emas dengan sklera dipotong jadi garis + sisik prosedural ber-jitter/warp, relief diredam di rongga mata. Audit `tmp_repaint_audit.py`: bayi 90 PASS/0 FAIL, remaja 90/0, dewasa 89/1 (hanya `sleep` 126→125 key = 34 ms, terdokumentasi); `TEXCOORD_0` delta 0, POSITION ≤8,34e-07 m, WEIGHTS ≤1,79e-07, key time 0 s, hanya `Image_0` yang berubah, `Image_1`/`Image_2` identik. Warna kelopak bergeser ≤1,5/255 per channel. Beranda build 19:19 vs 14:12 pada kamera yang sama (`home_before_after.png`); kedip runtime utuh (`blink_and_tap.png`) (§2.7). Ronde 3 November menghapus dua deviasi yang tersisa: mata dewasa kini terbaca amber berbingkai gelap dan `sleep` kembali utuh; ketiganya dikonfirmasi di aplikasi (§2.8) |
| Mata dewasa sesuai kartu referensi | Lulus (diff atlas + render + runtime) | Hasil gabungan: cincin gelap/pupil diperdalam di pulau mata (1.243 texel >16/255, 0,030% atlas, RGB rata-rata 151,6/102,4/66,0 → 121,1/72,1/35,7) **plus** kelopak baru yang tidak lagi menyelimuti bola mata. Klaim lama "atlas dewasa tidak punya piksel putih jadi mata tak bisa di-lid" adalah kegagalan locator (`distance_bone_to_eye` 0,1097/0,2123 → 0,0258 lewat bobot tulang), bukan bukti iris pucat. Statistik ambang warna (amber/gold/ramp jenuh) dicoba dan **ditolak** sebagai bukti karena ikut mengenai tandang dan api ornamen; yang dipakai adalah lembar crop `dewasa_iris_ab.png` (§2.8) |
| Grid frame 30 fps di pipeline ekspor | Lulus (statis) | Akar kehilangan key bukan per klip melainkan `scene.render.fps` 24 pada Blender `--factory-startup` vs klip bergrid 30. `ASSET_FPS = 30.0` + `set_frame_rate()` (int di `render.fps`, sisa di `render.fps_base`) diterapkan saat impor dan ekspor di `tools/glb_export.py`; 3.900 key di-snap dengan deviasi terbesar 3,815e-06 frame pada toleransi 0,02 (§2.8) |
| Loop `sleep` dewasa dipulihkan | Lulus (statis) | Sebelum: key terakhir frame 124, seam 0,00161904, durasi 4,1333 s. Sesudah: frame 126, seam 0,0, durasi 4,2000 s, 260 key disisipkan, 9.906 key / 78 channel; `LOOP_FRAMES PASS 25/25` dan `EXIT_drako_dewasa=0` di `shipped_final_audit.log` (§2.8) |
| Penjaga `SKIN_LOST` pada ekspor | Lulus (statis) | Pass kelopak melepas modifier armature/vertex group untuk pengukuran bind space; bila tidak dipasang kembali, body ter-ekspor rigid dan 25 klip tetap lolos. `glb_export.py:369` membandingkan ikatan skin file tulis vs sumber, menolak, dan menghapus file buruk. Gerbang rilis: `RELEASE_GATE PASS` dengan `3 skinned primitive(s), 0 rigid` untuk bayi/remaja/dewasa (§2.8) |
| Tahap remaja + dewasa terbukti di aplikasi | Lulus (runtime build debug) | Tidak lagi bergantung render offline. `debugSetLevel` (`app_state.dart:683-689`, guard `kReleaseMode`) lewat kartu `Alat uji` (`profil_screen.dart:116-120`, `profile_preferences.dart:146-158`): `dbg_23_remaja_pet.png` Lv.5 dan `dbg_26_dewasa_pet.png` Lv.11 di Beranda, `dbg_29_small.png` Koleksi Drako + chip `Dewasa Lv. 11+`, `dbg_30_crop.png` gestur putar, burst dewasa 6.752–23.064 piksel berubah per 0,25 s. Build release terbukti **tidak** memuat kartu `Alat uji` (`rt_39_small.png`) (§2.8) |
| Stabilitas lingkungan MuMu | Batas baru, bukan cacat aplikasi | Watchdog sistem MuMu (`MuMu5.0` 5.30.2.3616, uid 1000) memanggil `deletePackageX` dan menghapus paket pada 20:32:20 dan 20:36:22, diikuti `PACKAGE_FULLY_REMOVED` + telemetri `UninstallAPP`; tanpa `FATAL EXCEPTION`. QA runtime di MuMu tidak idempoten — pasang ulang menghapus data dan memaksa onboarding diulang (§2.8) |
| Rotasi pet (drag horizontal) | Lulus (kode + tes) | Azimuth 0,8°/piksel, phi/radius/target tetap; 2 tes per pet + 1 tes tap-setelah-putar; runtime dibuktikan di §2.5 |
| Wajah Drako (mata simetris, tanpa gash, kelopak rapi) | Lulus (struktur + render + runtime) | Aturan aperture baru (lubang tertutup dibatasi kotak cat; amber hanya dinilai di cakram iris) memberi `APERTURE_AMBER miss=0` di enam sisi; kartu kelopak ketiga tahap dibangun ulang dengan `LID_VERIFY PASS` + `LID_SYNC 25/25`; render rest/blink ketiga tahap bersimetri dan menutup penuh; di MuMu, delapan frame kedip berturut-turut (`blink_1..8.png`, `blink_grid.png`) tidak memperlihatkan celah di dahi (§2.9) |
| Build release tunggal + QA layar penuh 10 November | Lulus (runtime MuMu) | Satu build setelah semua kode selesai: APK 114.256.414 B, SHA-256 `c9724294…`, apksigner v2 `CN=Momo Local Release`, tanpa `application-debuggable`; enam GLB byte-identik dengan aset. Walkthrough `01_launch.png`–`47_home_no_pill.png` mencakup Beranda, status kritis, kedip, rotasi, Rekap, Misi, Duel, Profil, pill, dan mode istirahat; Remaja Lv.5 dan Dewasa Lv.11 tampil sebagai naga; logcat bersih; prefs dan pill dikembalikan (§2.9) |
| Data pemakaian sub-menit | Lulus (runtime) | Sesi 58 detik tampil `<1m`; `seconds`/`totalSeconds` dipertahankan; `zoom_data_02`, `zoom_data_04` |
| Notice + CTA Aksesibilitas | Lulus (runtime) | Banner Beranda, disclosure, Settings; hitungan scroll 0→5 setelah izin dan app dipantau; `zoom_data_08/09/25` |
| Sayap dewasa di aplikasi | Lulus (runtime kandidat) | `adult_wing_*`, `adultseq_1..4`; perubahan setelahnya hanya tint/ikon |
| `wing_show` dewasa di pill badan | Belum | tap badan membuka panel |
| Pill Drako statis | Lulus (runtime) | 0 piksel berubah pada frame statis |
| Pill Drako penuh | Lulus (runtime) | diff 3.183/3.122 piksel di sekitar pet |
| Panel pill berisi Drako | Lulus (runtime) | portrait, nama, aksi; animasi berhenti saat panel terbuka |
| Kontras kartu terpilih | Lulus (runtime) | bug `drako_32`; sesudah fix `drako_34/35b/36`; fill opaque + 4 tes tema |
| Ikon tahap Misi mengikuti pet | Lulus (runtime) | `drako_38/39/40` menampilkan ikon api |
| Tes otomatis | Lulus | `flutter analyze` bersih kecuali satu `info` (`unnecessary_brace_in_string_interps`, `test/pet_glb_asset_test.dart:234`), **258** tes Flutter lulus pada ronde 3 November (`final_analyze_test.log`); 254 lulus pada ronde retarget sebelumnya; 43 tes native terakhir 0 failure/error |
| Build final (31 Oktober, 2 November, 3 November) + aset | Lulus (statis) | Build 31 Oktober: APK 114.735.482 byte, SHA-256 `65ab60b4335ca522649f8a0ea3c1d267e26a2d6de5b05e846a5c36766ea8de3c`; build kelopak `12e2b849…`. Build kepala final 2 November: **114.796.090 byte**, SHA-256 `dc3e02b7b9512c5e78d73458f6597f505b025e66e6f1805b3d8ff2321530e918`; `base.apk` terpasang sama; signature release lokal v2, bukan debug; tiga GLB Drako di APK byte-identik dengan aset (`75210b87…`, `046bde12…`, `09af2242…`) (§2.6). Build repaint 2 November: **114.105.246 byte**, SHA-256 `4c561a15daaf07117567106b58db5e15b100f0d397128b2a7966b70fa142a5ac`, v2 valid, tanpa `application-debuggable` (§2.7). Build 3 November (paling baru): **114.145.362 byte**, SHA-256 `fec42ec094ce489c745287e67a6a518d832363d3c4f7e31796aeb500a62a5e03`, apksigner `Verifies` skema v2, signer `CN=Momo Local Release, OU=Local Testing, O=Screen Time Companion, L=Local, C=ID`, versionName 1.0.0, **0 kemunculan `debuggable`** di dump manifest; keenam GLB di `base.apk` byte-identik dengan folder aset — Drako `ffc2f833…`, `cca1faa5…`, `4a96cf00…`; Momo `a3442db2…`, `07b46168…`, `c2263f0e…` (§2.8) |
| Metadata glTF | Peringatan | Tiga GLB Drako final `valid: true`, 0 error, 3 warning per GLB (tangent-space runtime dan dua node skinned non-root); Momo masih ditolak validator karena min/max accessor lama/panjang array IBM, tetapi pemuat Blender/WebView berhasil—jangan mengklaim validator metadata bersih |
| Overlay pet keliling | Tidak tersedia dari UI | service native ada; tidak diuji ulang |
| Perangkat fisik/baterai/FPS | Belum | jangan mengklaim performa atau hemat daya |
| Restore backup dan permanensi pendamping | Gap | restore dapat mengosongkan onboarding; belum diputuskan/diperbaiki |
| Rotasi horizontal di semua pet/stage | Lulus (runtime) | Bukti di §2.5 |
| Layar kecil/tablet/perangkat fisik | Belum | hanya 900×1600 portrait |

## 13. Handoff minimum agent berikutnya

Saat menerima pet baru, agent harus mengembalikan: inventaris aset/rig/klip dan hash; perbedaan dengan kontrak runtime; rencana adapter serta file yang berubah; status fitur yang tersedia versus fallback; hasil tes/deformasi/render dan QA; batas yang belum diuji.

Pelajaran dari integrasi Drako:

1. Tiga GLB sekitar 33,9 MB menambah APK sekitar 30 MB; ukur dan laporkan, jangan menyembunyikan dampak ukuran.
2. Jangan memakai satu framing kamera untuk semua tahap; Drako bayi/remaja dan dewasa membutuhkan target berbeda.
3. Klip sayap harus dibake ke joint sayap; `wing_show` dewasa adalah display, versi bayi adalah kepakan pura-pura. Ini bukan morph runtime.
4. Mood statis di pill adalah kompromi aset. Jika tidak ada ekspresi baru, akui tint/tetes dan jangan menyebutnya setara Momo.
5. Registry harus ada di Dart dan Kotlin; bridge `pet` harus divalidasi. Menambah drawable saja tidak cukup.
6. Fitur yang tidak diekspos di UI (pet keliling) jangan dipromosikan seolah dapat dipakai; dokumentasikan kode native dan gap UI secara terpisah.
7. Jumlah channel atau nama klip bukan bukti klip hidup. Empat idle kritis Drako punya channel tetapi nilainya konstan; audit harus membandingkan sampel nilai dan frame render, bukan hanya daftar channel.
8. Saat QA satu pet menemukan cacat di pet lain, jangan memperbaiki aset di luar cakupan tanpa izin; catat temuan, bukti, dan batasnya.
9. Sudut 3/4 yang dipilih untuk memperlihatkan ekor membuat pet tampak miring. Pengguna memilih default tegak `0deg`; ekor dilihat lewat rotasi horizontal. Framing harus divalidasi pada seluruh 360°, bukan satu sudut: radius yang pas di depan dapat memotong ekor di 135°, dan crop 0,4–3,2% sudah terlihat sebagai ujung terpotong.
10. Rotasi horizontal harus dipisahkan dari tap/elus dan tidak merampas drag vertikal milik scroll induk. Uji gestur di widget nyata; tes JS saja tidak membuktikan arena gestur Flutter.
11. Fitur rotasi tidak otomatis berarti menyeragamkan framing. Momo tetap 4,8 m karena default-nya sudah disetujui dan tangkapan 360° tidak memperlihatkan potongan; sweep ketat menemukan pose ekstrem yang melewati batas matematis. Laporkan angka dan batasnya, jangan mengecilkan pet tanpa mandat.
12. Frame rate ekspor adalah bagian dari kontrak aset. Blender `--factory-startup` berjalan pada 24 fps sedangkan klip Drako bergrid 30; selisih itu yang menghapus key penutup loop, bukan koreografinya. Perbaiki di `tools/glb_export.py` (`ASSET_FPS` + `set_frame_rate()`), bukan dengan `export_force_sampling` per klip.
13. Klip yang lolos audit bukan bukti mesh masih ber-skin. Ketika pass kelopak lupa memasang kembali modifier armature, body ter-ekspor rigid dan 25 klip tetap hijau. Gerbang rilis sekarang menuntut `0 rigid` dan `glb_export.py` menolak file yang ikatan skin-nya berkurang dari sumber (`SKIN_LOST`).
14. Ambang warna pada atlas bukan bukti visual. Classifier "amber"/"gold"/ramp jenuh ikut mengenai tandang krem dan api ornamen, sehingga angka ship vs kandidat nyaris identik (selisih 404 texel). Buktikan dengan crop pada kamera aplikasi; kalau dua metode bertentangan, yang benar adalah render.
15. Satu gejala bisa punya dua penyebab yang terpisah. Mata dewasa terbaca pucat bukan karena atlasnya pucat (perubahan atlas ronde ini hanya 1.243 texel, 0,030%) tetapi karena kelopak lama menyelimuti bola mata. Pisahkan bukti tekstur (diff atlas) dari bukti geometri (vertex count + coverage) sebelum menulis penyebab di dokumen.
16. MuMu dapat menghapus paketnya sendiri. Watchdog sistem emulator memanggil `deletePackageX` dan memicu `PACKAGE_FULLY_REMOVED` tanpa `FATAL EXCEPTION` (§2.8). Jangan menyimpulkan crash dari aplikasi yang hilang, dan jangan mengandalkan state aplikasi di antara langkah QA.

Contoh instruksi kerja yang dapat diberikan kepada agent:

> Baca `docs/09-panduan-pet-rig-animasi-overlay.md`. Audit paket pet baru terhadap registry Flutter (`PetProfile`/`PetRegistry`) dan native (`PetCatalog`), dokumentasikan rig, klip, state, framing kamera per tahap, sprite mood, serta fallback statisnya. Jangan menimpa GLB Momo/Drako, mengaktifkan overlay, menjalankan generator pet lain secara buta, build release, commit, atau publish dalam tahap audit. Laporkan adapter dan perubahan yang diperlukan sebelum implementasi.

Dokumen terkait: [Sistem companion/HP](03-sistem-companion-dan-hp.md), [arsitektur Android](06-arsitektur-teknis-android.md), [spesifikasi karakter/animasi](08-spesifikasi-karakter-dan-animasi.md), dan [log pengembangan/QA](08-log-pengembangan.md). Bila catatan lama bertentangan dengan kode atau GLB aktual, inspect sumber aktual, jelaskan selisih, lalu update dokumentasi dalam scope yang diizinkan.
