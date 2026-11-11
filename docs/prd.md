# PRD App Screen Time: Rekap Penggunaan HP yang Seru dan Interaktif

> [!TIP]
> **Dokumentasi Modular Tersedia**: Dokumen ini adalah naskah master historis. Untuk kemudahan pengelolaan, dokumen ini telah dipecah secara rapi dan terstruktur ke dalam modul-modul di [**docs/README.md**](./README.md) (Modul 01–07).
> *Folder [`docs-design/`](../docs-design) berfungsi sebagai **mockup mentah interaktif (React/Vite)** untuk referensi visual.*

Dokumen persiapan coding, versi fleksibel untuk direvisi berkali-kali. Platform: mobile saja. Bahasa dokumen: Bahasa Indonesia.

## 1. Cara membaca dokumen ini

Dokumen ini bukan pagar keras. Setiap keputusan diberi tingkat, supaya revisi berikutnya cukup menyebut bab dan tingkatnya, tanpa merombak seluruh dokumen.

| Tingkat       | Arti                                                                      |
| ------------- | ------------------------------------------------------------------------- |
| Arah Terkunci | Sudah diputuskan user, jangan diubah tanpa persetujuan user               |
| Usulan Awal   | Titik awal yang masuk akal, boleh diganti saat balancing atau saat coding |
| Terbuka       | Belum diputuskan, menunggu pilihan user di revisi berikutnya              |

Angka-angka di dokumen ini adalah contoh awal untuk mulai coding, bukan janji final. Kalau saat uji coba angka terasa salah, ubah angkanya, bukan konsepnya.

## 2. Ringkasan produk

**Arah Terkunci.** App ini adalah app mobile untuk merekap penggunaan semua app di HP user, bukan app yang hanya menghitung scroll.

- Inti produk: rekap penggunaan semua app. Total screen time, durasi per app, jumlah buka app, sesi terpanjang, pemakaian malam, dan pola harian, mingguan, bulanan.
- Scroll adalah satu lapisan data di dalam rekap itu, bukan satu-satunya tujuan. Tujuannya kesadaran dan keseimbangan pemakaian, bukan sekadar mengurangi scroll.
- Lapisan serunya: companion hewan yang kondisinya mencerminkan keseimbangan pemakaian harian (HP), progres evolusi jangka panjang (XP), misi offline, Bank Waktu, duel dengan teman, dan kartu rekap yang bisa dibagikan. (Catatan: sistem Vitalitas dihapus dari versi awal untuk menghindari double-penalty).
- Lapisan dampaknya: jeda sadar sebelum membuka app tertentu, insight saat sesi sedang berjalan, dan peringatan saat HP habis.
- Target pasar: global. Peluncuran pertama di Indonesia sebagai pasar uji awal, lalu ekspansi multi region.
- Bukan app kontrol orang tua. Segmen parental control tidak masuk scope produk ini.

Nama produk masih **Terbuka**. Di dokumen ini produk disebut App Screen Time sebagai nama kerja.

## 3. Masalah yang diselesaikan

Orang membuka HP jauh lebih banyak daripada yang mereka sadari. Satu reel menjadi 50, lalu 100, dan berjam-jam hilang tanpa terasa. Tracker bawaan HP hanya mencatat angka secara pasif, sehingga jarang mengubah perilaku.

Data yang dikutip di riset awal: data.ai 2023 menempatkan Indonesia di posisi pertama dunia untuk durasi pakai smartphone harian, rata-rata 6,05 jam per hari, dan platform video pendek mendominasi penggunaan itu. Angka ini dipakai sebagai konteks pasar awal, bukan sebagai klaim pemasaran final. Verifikasi ulang sumbernya sebelum dipakai di materi publik.

Prinsip yang diambil dari bukti yang ada:

- Bukti terkuat ada di friction dan kesadaran, bukan di gamifikasi saja. Studi tentang app one sec yang diterbitkan di PNAS menemukan penurunan pemakaian media sosial sekitar 57 persen, lewat kesadaran saat user hendak membuka app dan friction jangka panjang. Caveat: hasil satu studi pada satu app tidak otomatis berlaku sama untuk produk ini, jadi dampak produk ini harus diukur sendiri sejak versi awal.
- Gamifikasi tanpa arah bisa berbalik. Contoh yang ditemukan di riset: DoomScroller memberi koin per jarak scroll, sehingga makin banyak scroll makin banyak reward. Itu insentif terbalik dari tujuan wellbeing.
- Karena itu aturan desain produk ini: reward hanya untuk perilaku yang benar, yaitu scroll lebih sedikit, sesi lebih singkat, istirahat, dan misi offline. Tidak ada reward untuk sering membuka app ini atau untuk scroll lebih banyak.

## 4. Learning kompetitor

### 4.1 BrainPal: Stop Scroll, bukti pasar utamanya

Data dari halaman Play Store yang dibagikan user: developer EpowerX Labs, rating 4,8, sekitar 106 ribu ulasan, lebih dari 1 juta download, versi 20.0.625, diperbarui 27 Oktober 2026, ukuran 43 MB, butuh Android 7.0 ke atas, pembelian dalam app Rp 7.900 sampai Rp 461.074 per item.

Yang dikerjakan BrainPal dengan baik:

- Menghitung reel dan short secara live di Instagram, YouTube, Facebook, dan Snapchat.
- Visual kondisi otak yang makin rusak seiring hitungan scroll naik.
- Scroll Battle: tambah teman, bandingkan hitungan harian, angka paling rendah menang.
- Widget, dan penghitung Shorts yang gratis menurut ulasan user.
- Blokir reels dan shorts setelah limit tercapai, sebagai fitur Pro.
- Memakai Accessibility Service untuk deteksi scroll, dengan penjelasan izin di halaman store dan klaim data tetap di perangkat.

Tiga sinyal dari ulasan user BrainPal:

- User mengira ada double count karena video yang sudah ditonton terhitung lagi saat swipe kembali. Developer menjawab bahwa video yang diputar lagi memang dihitung. Pelajarannya: aturan hitung harus dijelaskan sejak awal, bukan dipertahankan belakangan di balasan ulasan.
- User melaporkan penurunan dari scroll 200 lebih menjadi di bawah 100. Pelajarannya: hitungan live yang terlihat memang bisa mengubah perilaku.
- User meminta opsi bayar sekali seumur hidup, bukan hanya langganan. Pelajarannya: opsi lifetime harus disiapkan sejak awal.

Celah BrainPal yang menjadi ruang produk ini: cakupannya hanya reels dan short, tidak ada rekap semua app, tidak ada durasi per app sebagai inti, tidak ada companion yang berevolusi, dan tidak ada misi offline dengan Bank Waktu.

### 4.2 Keluarga app EpowerX Labs

Pola EpowerX adalah memecah satu masalah menjadi banyak app kecil.

| App      | Fokus                                                                               | Catatan skala                                                                  |
| -------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| BrainPal | Hitung reels, battle, blokir reels Pro                                              | Terbesar kedua di keluarga ini                                                 |
| Regain   | Timer fokus belajar, Pomodoro, blocker, laporan screen time, focus room multiplayer | Terbesar di EpowerX menurut data store yang diriset                            |
| Detox    | App blocker keras, kunci app berhari-hari tanpa cara curang                         | Masih kecil, install ribuan                                                    |
| Bedlock  | Bedtime app blocker untuk tidur                                                     | Belum terverifikasi di daftar portfolio AppBrain, jangan jadikan patokan skala |

Pelajaran utamanya: user saat ini terpaksa memasang banyak app untuk kebutuhan yang sebenarnya satu. Produk ini mengambil arah sebaliknya, satu app rekap yang lengkap.

ChildLock tidak dibahas di dokumen ini karena user memutuskan segmen parental control tidak dipakai.

### 4.3 ALIVE, inspirasi interaksi dari Threads

Dari materi ALIVE yang dibagikan user, buatan Fatan, app screen time yang masih tahap demo dan belum rilis di Play Store saat diriset:

- Notch atau pill yang menampilkan waktu layar secara live.
- Layar Statistik berjudul Ke mana perginya, dengan donut total, tab kategori Hiburan, Bebas, dan Total, lalu daftar peringkat app berdasarkan durasi.
- Catatan transparan di layar Statistik: ALIVE hanya mendapat nama yang perangkat mau berikan, sebagian app tampil sebagai bagian dari nama paketnya. Kejujuran teknis seperti ini ditiru, bukan disembunyikan.
- Layar Misi berjudul Beri ruang, berisi misi offline seperti Jalan 20 Menit, Belajar 30 Menit, Membaca 30 Menit, Olahraga 20 Menit, Bereskan Kamar 20 Menit, Menggambar 20 Menit, dan Lari 20 Menit. Setiap misi memberi imbalan waktu yang berbeda.
- Bank Waktu dengan tiga angka: Masuk, Keluar, dan Tersedia. Pesannya jelas, misi membayarmu kembali dengan waktu.
- Ada juga unsur game dengan tombol Battle, Build, dan Shop di materi awalnya.

Posisi produk ini terhadap ALIVE: jangan hanya meniru. ALIVE sudah menggabungkan notch, misi, streak, dan statistik. Pembeda produk ini adalah rekap semua app, hitungan scroll untuk semua app sosial utama termasuk TikTok, jeda sadar, aturan hitung yang transparan, data lokal, dan companion yang berevolusi.

### 4.4 Tren dynamic island atau notch mengambang

Learning dari link Threads kedua: pill mengambang kecil yang bisa mengembang dan menampilkan info kontekstual sedang terasa segar dan familiar, dicontohkan sampai untuk menampilkan jadwal sholat di Windows.

Penerapan di produk ini bukan meniru Windows, tapi memakai pola interaksinya di Android: pill kecil yang live, bisa diketuk untuk mengembang menjadi info, jeda sadar, atau aksi istirahat. Detail pill ada di Bab 10.

## 5. Pengguna sasaran

**Arah Terkunci.**

- Pengguna dewasa umum yang merasa pemakaian HP-nya tidak terkendali atau sekadar ingin tahu pola pakainya.
- Bukan orang tua yang mengawasi anak, bukan app keluarga, bukan app pemantau pasangan.
- Peluncuran pertama: Indonesia, sebagai pasar uji awal yang padat pengguna Android dan tinggi durasi pakai HP.
- Setelah loop inti terbukti di Indonesia, ekspansi multi region. Bahasa dipilih user sendiri, lihat Bab 12.

**Usulan Awal** persona untuk membantu desain:

- Scroller berat: banyak reel dan short, butuh hitungan live dan peringatan.
- Pekerja atau pelajar sibuk: butuh rekap per app dan kategori kerja, belajar, hiburan.
- Pemain sosial: termotivasi duel, kartu rekap, dan koleksi companion.

Persona ini boleh berubah setelah ada data beta.

## 6. Prinsip produk

- Kesadaran dulu, hukuman belakangan. Produk ini cermin pemakaian, bukan polisi HP.
- Reward hanya untuk perilaku benar. Tidak ada XP, koin, atau progres dari scroll.
- Sedikit notifikasi, tepat konteks. Terlalu banyak notifikasi membuat user mematikan notifikasi atau uninstall.
- Target mingguan, bukan streak harian yang rapuh. Target awal 5 dari 7 hari, karena streak harian yang putus sering membuat user berhenti kembali.
- Ukur keberhasilan dari perubahan pemakaian user, bukan dari seberapa sering user membuka app ini.
- Data lokal dulu. Jelaskan izin dan aturan hitung secara jujur sejak onboarding.
- Fleksibel. Angka, durasi, dan imbalan di dokumen ini adalah titik awal balancing.

## 7. Sistem inti: HP, XP evolusi, dan companion

### 7.1 HP harian

**Arah Terkunci konsepnya, Usulan Awal angkanya.**

- Setiap user punya bar HP harian yang mencerminkan keseimbangan pemakaian hari itu.
- HP turun dari scroll tanpa henti, sesi panjang di app yang dipilih user untuk dipantau, dan pemakaian malam.
- HP terjaga dari pemakaian yang disengaja dan singkat, misalnya membuka app kerja atau belajar sesuai target.
- HP pulih dari waktu tanpa HP, mode istirahat, dan misi offline.
- Tiga kondisi mood utama: Segar (HP tinggi), Lelah (HP sedang), Kritis (HP rendah).
- Rumus pastinya **Terbuka** untuk balancing. Saat coding, buat rumus sebagai konfigurasi yang mudah diubah, jangan tanam angka mati di banyak tempat.

### 7.2 Kalau HP habis

**Arah Terkunci.** Ada peringatan bahaya, lalu user memilih sendiri. Tidak ada kunci paksa.

1. Overlay peringatan bahaya muncul, dengan kondisi companion terlihat jelas.
2. Pilihan pertama: istirahatkan HP selama beberapa menit. Usulan awal: default 15 menit, bisa diatur user dalam rentang 10 sampai 20 menit. Selama istirahat, HP pulih bertahap.
3. Pilihan kedua: tetap lanjut memakai HP. Pada versi awal/MVP tidak ada hukuman bar kedua (Vitalitas dihapus dari MVP); companion berstatus Kritis dan tidak ada perolehan XP hingga beristirahat.
4. Companion tidak mati permanen. Selalu ada jalan pulih lewat istirahat dan hari yang seimbang berikutnya.

### 7.3 Penggantian Vitalitas dengan XP Bar di Versi Awal

**Arah Terkunci (Hasil Uji Desain & UX).**

- **Vitalitas Dihapus dari MVP**: Evaluasi prototipe membuktikan bahwa adanya dua bar kesehatan (HP harian + Vitalitas jangka panjang) membuat antarmuka membingungkan dan memberikan hukuman berlebih (*double-penalty/guilt-tripping*), bertentangan dengan prinsip "kesadaran dulu, bukan polisi HP".
- **Bar Kedua di Beranda Dialihkan ke XP Bar**:
  - Bar HP (atas, chunky): Status kesehatan harian Momo (`HP 72/100`).
  - Bar XP (bawah, ramping): Progres kenaikan level dan evolusi (`XP · menuju Lv. 9 | 240/400 XP | 60%`).
- **Sifat XP**: XP hanya diperoleh dari perilaku benar (misi offline dan mode istirahat), tidak pernah dari scroll, dan **XP tidak berkurang saat HP turun**.
- Konsep Vitalitas disimpan di backlog (Bab 16) bila dibutuhkan balancing lanjutan pasca-MVP.

### 7.4 Companion hewan yang variatif

**Arah Terkunci.**

- Bentuk: hewan lucu orisinal dengan gaya monster collecting sebagai inspirasi rasa, bukan memakai IP Pokemon atau IP lain.
- Variatif: user memilih starter di onboarding. **Usulan Awal** famili starter: kucing, rubah, dan burung malam. Daftar final starter **Terbuka**.
- Tahap evolusi: Bayi, Remaja, Dewasa, lalu wujud puncak. Nama tahap boleh diganti saat penamaan final.
- XP hanya dari perilaku benar: menyelesaikan target harian atau mingguan, mode istirahat, sesi fokus, misi offline, dan duel melawan baseline sendiri. XP tidak pernah dari scroll.
- Varian warna dan pola dibuka dari misi dan pencapaian, tersimpan di album koleksi di Profil. Bukan lootbox berbayar.
- Aksesoris dan skin companion adalah backlog, lihat Bab 16, bukan scope MVP.

### 7.5 Gaya companion mengikuti tema, bukan pixel di semua tema

Ini koreksi penting dari hasil uji desain di Stitch.

- **Arah Terkunci:** companion wajib menggunakan **Asset-Driven Pipeline**, bukan digambar via deretan string koordinat path SVG di dalam kode (menghindari visual kaku/programmer art).
- Untuk aplikasi mobile final, companion dibangun menggunakan file aset **Rive (`.riv`)** dengan state machine di Flutter (mendukung idle breathing, kedipan acak, reaksi sentuhan jari, dan transisi mood halus antar state HP).
- Satu karakter master dipakai untuk semua tema dengan parameter dinamis (outline, tinting, glow).
- Efek pixel hanya muncul di tema Pixel Arcade via efek pikselasi shader pada aset vektor, bukan pixel art buatan tangan yang dipaksakan ke semua tema.
- Untuk prototipe web mockup (`docs-design/`), karakter dimuat dari file aset visual terkurasi (WebP/SVG), bukan inline code paths.

## 8. Tema dan desain visual

### 8.1 Empat preset tema awal

**Usulan Awal**, bukan daftar final. User memilih tema di onboarding dan bisa menggantinya kapan saja di Profil.

| Tema         | Rasa visual                                      | Catatan awal                           |
| ------------ | ------------------------------------------------ | -------------------------------------- |
| Brutal Pop   | Neo brutalism, outline tebal, warna datar berani | Tema default saat uji Stitch           |
| Pixel Arcade | Pixel, arcade, game retro                        | Hanya tema ini yang memakai efek pixel |
| Soft Clay    | Soft kawaii, lembut, tanpa outline keras         | Bayangan lembut, sudut membulat        |
| Midnight     | Gelap, redup, glow tipis                         | Nyaman untuk pemakaian malam           |

Tema bekerja lewat token sederhana: warna latar, warna permukaan, warna teks, warna aksen, ketebalan border, radius sudut, jenis bayangan, dan font. Pill native dan UI Flutter membaca token yang sama, supaya tema konsisten di semua permukaan.

### 8.2 Aturan keterbacaan

- **Arah Terkunci:** angka statistik tidak memakai font pixel di tema non pixel. Dari uji Stitch, angka seperti 3J 24M dan 1J 12M dengan font pixel sulit dibaca.
- Di tema non pixel, angka memakai font tabular biasa agar mudah dibandingkan.
- Font dekoratif hanya untuk judul pendek, bukan untuk angka, durasi, atau daftar app.

### 8.3 Kebutuhan desain untuk Stitch

Lampiran kerja desain, bukan bagian produk:

- Jangan hanya generate satu tema. Panel Home harus dirender di semua tema: Brutal Pop, Pixel Arcade, Soft Clay, dan Midnight.
- Screen yang perlu dibandingkan antar tema: Beranda, Rekap, Misi, Duel, Profil, pill, dan overlay peringatan bahaya.
- Prompt untuk Stitch ditulis dalam bahasa Inggris karena Stitch lebih andal membaca instruksi bahasa Inggris, sementara contoh teks UI di prompt tetap bahasa Indonesia.
- Stitch adalah alat bantu arah visual, bukan sumber kebenaran layout. Kalau ukuran font atau warna meleset dari token, sebutkan lagi secara eksplisit di prompt iterasi berikutnya.
- Hasil Stitch tidak mengunci desain final. Token dan layout di dokumen ini yang menjadi acuan coding.

## 9. Struktur app: lima tab dengan Beranda di tengah

**Arah Terkunci.** Bottom navigation berisi lima tab, urutannya:

Rekap, Misi, **Beranda di tengah**, Duel, Profil.

Beranda di tengah dibuat menonjol, misalnya tombol lebih besar atau naik sedikit dengan ikon companion, karena Beranda adalah center dan layar pertama saat app dibuka. Lima tab ini cukup untuk sekarang. Tab baru hanya ditambah kalau user memutuskan lagi.

### 9.1 Beranda

Layar pertama saat app dibuka.

- Bagian atas: salam singkat, tanggal, dan total screen time hari ini dalam ukuran kecil, tidak menyaingi companion.
- Tengah, paling besar: companion dengan nama, level, status mood seperti sehat, lemas, atau sakit, bar HP harian yang besar, bar Vitalitas yang lebih kecil, dan progres XP ke evolusi berikutnya.
- Jika HP kritis, peringatan bahaya tampil di area ini juga, bukan hanya overlay.
- Di bawah companion: ringkasan hari ini dalam 3 sampai 4 kartu kecil. Isinya total waktu layar, hitungan scroll dengan replay terpisah, jumlah buka app, dan app teratas hari ini.
- Di bawahnya: satu misi hari ini yang sedang berjalan, dengan tombol cepat untuk memulai mode istirahat.

### 9.2 Rekap

Inti produk. Rekap penggunaan semua app, bukan hanya hiburan dan bukan hanya scroll.

Struktur awal mengikuti learning Statistik ALIVE:

- Donut total screen time untuk periode terpilih.
- Tab kategori: Hiburan, Bebas, dan Total sebagai titik awal. Kategori produk ini diperluas menjadi sosial, hiburan, produktivitas, kerja, dan belajar. Pemetaan app ke kategori harus bisa diatur, karena satu app bisa berbeda fungsi bagi user yang berbeda.
- Daftar peringkat app dengan durasi, jumlah buka, dan perubahan dibanding periode sebelumnya.
- Periode: harian, mingguan, dan bulanan, selalu dibandingkan dengan baseline user sendiri, bukan dengan rata rata orang lain.
- Detail tambahan: sesi terpanjang, pemakaian malam, total scroll, scroll per app, dan replay terpisah.
- Catatan transparan ala ALIVE: jika nama app tidak bisa dibaca penuh dari perangkat, tampilkan apa adanya sebagai bagian nama paket, disertai penjelasan singkat. Jangan menebak nama app.
- Kartu rekap yang bisa dibagikan, gaya Wrapped: total waktu, app teratas, jarak atau perbandingan scroll yang mudah dipahami, dan kondisi companion. Perbandingan lokal seperti landmark Indonesia hanya untuk locale Indonesia, jangan dipaksakan ke semua negara.

### 9.3 Misi

Misi adalah mesin XP, pemulihan HP, dan Bank Waktu sekaligus. Satu misi selesai memberi tiga hasil: XP evolusi, pemulihan HP, dan saldo Bank Waktu.

Katalog awal mengikuti learning ALIVE, angka imbalan adalah **Usulan Awal** untuk balancing:

| Misi           | Durasi misi | Imbalan Bank Waktu awal |
| -------------- | ----------: | ----------------------: |
| Jalan          |    20 menit |                15 menit |
| Belajar        |    30 menit |                20 menit |
| Membaca        |    30 menit |                20 menit |
| Olahraga       |    20 menit |                25 menit |
| Bereskan Kamar |    20 menit |                15 menit |
| Menggambar     |    20 menit |                15 menit |
| Lari           |    20 menit |                25 menit |

Bank Waktu tampil di bagian atas tab Misi dengan tiga angka: Masuk, Keluar, dan Tersedia.

- Masuk: total menit yang didapat dari misi.
- Keluar: total menit jatah yang sudah dipakai.
- Tersedia: sisa saldo.

Cara saldo Bank Waktu dipakai sebagai jatah waktu layar adalah **Terbuka** untuk balancing. Pilihan awal yang bisa diuji: saldo menjadi tambahan jatah di app yang dipantau, di luar limit dasar user.

Verifikasi misi juga **Terbuka**. Pilihan awal: timer di dalam app untuk misi offline, konfirmasi manual yang jujur untuk misi yang tidak bisa diukur sensor, dan sensor gerak hanya jika izinnya masuk akal. Jangan merancang misi yang memaksa izin berlebihan.

### 9.4 Duel

- Battle dengan teman, membandingkan angka harian atau mingguan.
- Aturan awal gabungan: angka scroll paling rendah menang, dan pencapaian melawan baseline sendiri ikut dihitung, supaya user yang titik awalnya berat tetap punya peluang menang dengan perbaikan diri.
- Skor, periode, dan syarat keadilan duel adalah **Usulan Awal**, disesuaikan setelah ada data pemakaian nyata.
- Duel tidak boleh memberi reward untuk membuka app ini berulang kali. Cek hasil cukup sekali sehari.

### 9.5 Profil

- Koleksi companion dan album varian warna atau pola.
- Pilihan bahasa, lihat Bab 12.
- Pengaturan tema, ganti tema kapan saja.
- Pengaturan limit, app yang dipantau, dan mode istirahat.
- Pengaturan Pro dan opsi lifetime, lihat Bab 15.
- Pengaturan izin, privasi, ekspor data, dan hapus data.

## 10. Pill overlay dan jeda sadar

### 10.1 Pill mengambang

**Arah Terkunci konsepnya, Usulan Awal detailnya.**

- Pill kecil mengambang di Android, menampilkan maskot companion mini, hitungan atau durasi live, dan status HP secara ringkas.
- Pill bisa diketuk untuk mengembang: info sesi saat ini, tombol jeda sadar, tombol istirahat, dan misi singkat.
- Pill dibangun native di Kotlin, bukan di Flutter, karena overlay dan deteksi app berjalan di lapisan native.
- Pill menerima token tema sederhana dari app utama, supaya warna dan rasa visualnya mengikuti tema yang dipilih user.
- Izin overlay diminta terpisah dan dijelaskan manfaatnya. Pill adalah fitur opsional, bukan syarat memakai app.

### 10.2 Jeda sadar sebelum membuka app

Ini fitur dampak utama, mengikuti bukti friction dari one sec.

- Saat user membuka app yang dipilih untuk dipantau, tampilkan jeda singkat. **Usulan Awal:** 3 sampai 10 detik, bisa diatur.
- Di layar jeda, tampilkan kondisi companion dan HP saat itu, plus pertanyaan sederhana: mau ngapain di app ini.
- Tampilkan insight sesi, misalnya sudah scroll berapa banyak dalam sesi ini, bukan hanya laporan akhir hari.
- Setelah jeda, user tetap boleh lanjut. Produk ini memberi kesadaran, bukan melarang secara paksa, kecuali user sendiri mengaktifkan mode blokir di pengaturan Pro bila fitur itu nanti dibangun.
- Risiko yang dijaga: friction bisa kehilangan efek kalau user lama lama hanya menunggu delay. Karena itu isi jeda harus berubah konteks, misalnya HP, misi, dan insight terbaru, bukan layar tunggu yang selalu sama.

### 10.3 Mode istirahat

- User memulai istirahat dari Beranda, pill, atau overlay HP habis.
- Selama istirahat, tampilkan companion yang pulih, hitung mundur, dan progres pemulihan HP.
- Menyelesaikan istirahat memberi XP dan pemulihan HP. Membatalkan istirahat tidak dihukum berat, cukup tidak mendapat reward penuh.

## 11. Aturan hitung dan data

### 11.1 Aturan hitung final

**Arah Terkunci**, diputuskan user:

- Swipe balik tetap dihitung dan menambah hit. Alasannya: setiap lintasan konten adalah perhatian yang terpakai, walaupun kontennya sama.
- Replay dicatat terpisah dari hit utama. Di rekap ada kolom replay sendiri, supaya user paham beda antara konten baru yang dilewati dan konten yang diputar ulang.
- Aturan ini dijelaskan di onboarding dan di layar Rekap, dengan bahasa sederhana. Ini pelajaran langsung dari ulasan BrainPal, di mana user mengira hitungan ganda adalah bug.
- Definisi teknis satu hit, misalnya satu perpindahan reel, satu perpindahan video pendek, atau jarak scroll tertentu di feed biasa, adalah **Usulan Awal** per platform app yang dipantau. Buat definisi per app sebagai konfigurasi terpisah, karena perilaku Instagram, YouTube, TikTok, Facebook, dan Snapchat tidak identik.

### 11.2 Sumber data Android

- Durasi per app dan jumlah buka: UsageStatsManager.
- Deteksi scroll dan perpindahan konten di app lain: Accessibility Service. Ini satu satunya jalur praktis di Android untuk fitur ini.
- Alternatif untuk sebagian fungsi blokir atau jeda: polling UsageStatsManager dari foreground service, dengan konsekuensi delay sekitar satu detik dan tanpa data scroll.
- Konsekuensi Play Store: Accessibility Service wajib prominent disclosure, persetujuan eksplisit user, dan formulir deklarasi. Siapkan teks disclosure dan video atau materi deklarasi sebagai bagian dari persiapan rilis, bukan setelah ditolak.
- Minta izin bertahap: Usage Access dulu untuk rekap dasar, Accessibility hanya saat user mengaktifkan hitung scroll, overlay hanya saat user mengaktifkan pill. Jangan minta semua izin di awal.

### 11.3 Privasi

- **Arah Terkunci:** data pemakaian disimpan lokal di perangkat secara default.
- Jangan membaca isi pesan, isi konten, atau teks pribadi dari Accessibility Service. Yang dicatat adalah peristiwa scroll, perpindahan konten, dan durasi, bukan isi layarnya.
- Sinkronisasi cloud hanya untuk kebutuhan akun seperti duel dan koleksi, dan hanya setelah user membuat akun. Rekap mentah tidak perlu naik ke server untuk fitur inti.
- Sediakan ekspor data dan hapus semua data di Profil.

## 12. Pasar, bahasa, dan onboarding

### 12.1 Urutan pasar

**Arah Terkunci.**

1. Indonesia dulu, sebagai pasar uji awal untuk membuktikan loop hitung, HP, companion, dan misi.
2. Setelah validasi, ekspansi multi region. Negara gelombang kedua **Terbuka**.
3. Target akhirnya global, karena produk ini general, berbeda dengan produk spesifik lokal seperti UTBK Tracker.

Harga dan materi store disiapkan per negara saat ekspansi, bukan diterjemahkan mentah dari harga Indonesia.

### 12.2 Bahasa dipilih user di awal

**Arah Terkunci.**

- Di layar pertama onboarding, user memilih bahasa sendiri.
- Rilis pertama minimal menyediakan Bahasa Indonesia dan Bahasa Inggris.
- Bahasa bisa diganti kapan saja di Profil.
- Saat multi region bertambah, bahasa ditambah bertahap mengikuti negara rilis.
- Jangan mengunci bahasa berdasarkan lokasi saja. Pilihan user selalu menang.

### 12.3 Alur onboarding awal

**Usulan Awal**, urutan boleh berubah setelah uji:

1. Pilih bahasa.
2. Pilih tema dari empat preset, dengan preview Home dan companion di tiap tema.
3. Pilih companion starter.
4. Penjelasan singkat aturan hitung: swipe balik terhitung, replay terpisah.
5. Pilih app yang ingin dipantau dan tetapkan limit atau target awal.
6. Minta izin bertahap sesuai fitur yang diaktifkan user: Usage Access, lalu Accessibility untuk scroll, lalu overlay untuk pill.
7. Selesai di Beranda, companion tampil sebagai hero.

## 13. Arsitektur teknis untuk persiapan coding

### 13.1 Platform

- **Arah Terkunci:** mobile saja, Android first.
- iOS ditunda. Alasan teknis dari riset: lewat FamilyControls dan DeviceActivity, app pihak ketiga di iOS hanya mendapat token buram, threshold DeviceActivity dilaporkan tidak konsisten, dan scroll tracking di dalam app lain praktis tidak mungkin lewat API publik. Apple juga menyatakan pembatasan data Screen Time detail untuk pihak ketiga adalah keputusan arsitektur yang disengaja.
- Jika iOS nanti dikerjakan, scope-nya harus dirancang ulang sebagai rekap terbatas tanpa hitung scroll, bukan port langsung versi Android.

### 13.2 Stack awal

**Usulan Awal**, mengikuti stack yang biasa dipakai user:

- UI dan logika produk: Flutter.
- Modul native: Kotlin untuk UsageStats, Accessibility Service, foreground service, overlay pill, dan jeda sadar.
- Companion animasi: Rive dengan state machine, dibaca dari Flutter, dengan parameter tema.
- Penyimpanan lokal: database lokal di perangkat untuk peristiwa pemakaian, agregat harian, misi, Bank Waktu, dan progres companion. Pilihan library spesifik **Terbuka** saat setup proyek.
- Backend: hanya bila dibutuhkan untuk akun, duel, dan leaderboard. Fitur inti harus tetap jalan penuh tanpa akun dan tanpa server.

### 13.3 Batas modul yang disarankan

- Modul tracking native: hanya mengumpulkan peristiwa dan mengirim agregat ke lapisan Flutter. Jangan taruh logika game di modul tracking.
- Modul game: HP, Vitalitas, XP, evolusi, misi, dan Bank Waktu. Semua angka dari konfigurasi balancing, bukan hardcode tersebar.
- Modul tema: satu sumber token tema yang dibaca UI Flutter dan pill Kotlin.
- Modul rekap: agregasi harian, mingguan, bulanan, kategori, dan kartu bagikan.

Pemisahan ini membuat revisi angka dan tema tidak menyentuh modul tracking yang sensitif izin.

## 14. Scope MVP dan roadmap

### 14.1 MVP

**Usulan Awal.** MVP membuktikan satu loop: user melihat rekapnya, companion bereaksi, dan user mengubah satu perilaku.

- Onboarding: bahasa, tema, starter, aturan hitung, pilih app pantau, izin bertahap.
- Tracking: durasi per app, jumlah buka, dan hitung scroll untuk app sosial utama yang dipilih user.
- Beranda: companion, HP, Vitalitas, ringkasan hari ini, satu misi harian.
- Rekap: donut, kategori, peringkat app, periode harian dan mingguan.
- Misi: katalog misi offline awal dan Bank Waktu.
- HP habis: overlay peringatan bahaya dengan dua pilihan, istirahat atau lanjut dengan Vitalitas turun.
- Pill: versi sederhana, hitungan live dan ekspansi dasar.
- Kartu rekap mingguan yang bisa dibagikan.

### 14.2 Setelah MVP

Urutan **Usulan Awal**, boleh ditukar mengikuti data beta:

- Duel teman dan leaderboard mingguan.
- Jeda sadar yang lebih kaya konteks dan mode blokir opsional.
- Rekap bulanan, insight pola, dan target personal yang disarankan dari baseline.
- Lebih banyak spesies companion, varian, dan misi musiman.
- Ekspansi bahasa dan negara.
- Roast atau ringkasan bahasa santai di kartu rekap, sebagai fitur viral opsional. Nada dan bahasanya per locale, bukan satu gaya untuk semua negara.

### 14.3 Kriteria lanjut atau berhenti yang lentur

Tidak ada angka karangan di dokumen ini. Sebelum beta, tetapkan bersama:

- Berapa user beta minimum dan berapa lama periode ujinya.
- Sinyal lanjut: user kembali di minggu kedua, user menyelesaikan misi, dan ada perubahan pemakaian yang terlihat di rekap user sendiri.
- Sinyal berhenti atau pivot: tracking dianggap tidak akurat, izin dianggap menyeramkan, atau companion tidak memengaruhi perilaku sama sekali.

Angka pastinya **Terbuka** dan ditulis di dokumen ini setelah disepakati, bukan ditebak sekarang.

## 15. Monetisasi

**Usulan Awal.**

- Gratis: rekap dasar, hitung scroll, companion dasar, dan misi dasar. Pelajaran dari ulasan BrainPal: penghitung inti yang gratis adalah alasan user memuji dan bertahan.
- Pro: blokir atau jeda lanjutan, rekap mendalam, tema tambahan, dan fitur duel lanjutan.
- Wajib ada opsi bayar sekali seumur hidup atau lifetime, karena itu permintaan eksplisit user kompetitor. Harga lifetime boleh lebih mahal dari langganan tahunan, tetap masuk akal.
- Harga berjenjang per negara, mulai dari harga Indonesia saat rilis pertama.
- Companion, varian dari misi, dan pemulihan Vitalitas tidak dijual sebagai jalan pintas berbayar. Yang dijual adalah fitur dan kosmetik UI, bukan kesehatan companion.

Harga final semua paket **Terbuka**.

## 16. Backlog terbuka

Dicatat agar tidak hilang, bukan scope MVP dan bukan janji fitur:

- Skin companion lain di luar varian warna dan pola dasar.
- Skin UI atau tema tambahan di luar empat preset awal, termasuk kemungkinan tema sticker collage atau komik.
- Skin pill.
- Fitur mix: gabungan misi dengan duel, fokus dengan rekap, atau istirahat berkelompok.
- Widget home screen.
- Mode fokus atau Pomodoro seperti Regain, bila data beta menunjukkan user membutuhkannya di app yang sama.

Setiap item backlog masuk scope hanya lewat revisi dokumen ini.

## 17. Risiko utama

- Penolakan Play Store karena Accessibility Service. Mitigasi: disclosure yang jelas, deklarasi lengkap, izin bertahap, dan fitur inti tetap berguna hanya dengan Usage Access.
- Akurasi hitung berbeda antar app dan antar versi app sosial. Mitigasi: definisi hit per app sebagai konfigurasi, uji di perangkat nyata, dan tampilkan aturan hitung secara transparan.
- Nama app tidak terbaca penuh dari perangkat. Mitigasi: tampilkan nama paket apa adanya dengan penjelasan, seperti catatan transparan ALIVE.
- Over gamifikasi. Mitigasi: notifikasi sedikit, reward hanya untuk perilaku benar, dan tidak ada tekanan membuka app ini tiap jam.
- Motivasi ekstrinsik cepat pudar. Mitigasi: kaitkan progres companion dengan keseimbangan nyata user, bukan dengan badge kosong.
- Friction kehilangan efek. Mitigasi: isi jeda sadar berubah konteks mengikuti HP, misi, dan insight sesi.
- Beban aset companion membengkak. Mitigasi: satu companion vektor untuk semua tema, pixel hanya efek di satu tema.
- Klaim riset dipakai berlebihan. Angka pasar dan angka studi di dokumen ini adalah konteks riset awal. Verifikasi ulang dari sumber primer sebelum dipakai di store listing atau materi publik.

## 18. Checklist persiapan coding

- Setup proyek Flutter dengan modul Kotlin terpisah untuk tracking.
- Buat konfigurasi balancing terpusat: HP, Vitalitas, XP, imbalan misi, dan durasi istirahat.
- Buat sistem token tema dan empat preset awal.
- Buat satu companion vektor uji dengan state sehat, lemas, sakit, dan istirahat.
- Prototipe tracking: UsageStats untuk durasi, Accessibility untuk satu app sosial dulu.
- Prototipe pill native yang membaca token tema.
- Tulis teks disclosure izin dalam Bahasa Indonesia dan Bahasa Inggris.
- Uji aturan hitung di perangkat nyata, termasuk swipe balik dan replay, lalu cocokkan dengan Bab 11.
- Siapkan struktur data lokal dan agregasi Rekap sebelum mempercantik UI.

## 19. Keputusan terbuka dan status saat ini

| Keputusan                                       | Bab         | Status saat ini                                                                                |
| ----------------------------------------------- | ----------- | ---------------------------------------------------------------------------------------------- |
| Nama produk final                               | 2           | Belum dipilih (nama kerja: *Screen Time Companion*)                                            |
| Gaya pixel dipertahankan atau diganti tema lain | 7.5 dan 8.1 | **Terkunci**: Pet master vektor; gaya pixel art & font pixel hanya untuk tema *Pixel Arcade*  |
| Penghapusan sistem Vitalitas                    | 7.3         | **Terkunci**: Dihapus dari MVP; bar kedua dialihkan ke XP Bar                                  |
| Keterbacaan angka statistik                     | 8.2         | **Terkunci**: Wajib font tabular standar di tema non-pixel                                     |
| Daftar final companion starter                  | 7.4         | Usulan awal kucing, rubah, burung malam                                                        |
| Rumus penyeimbangan HP harian                   | 7.1         | Konsep terkunci, angka terbuka untuk balancing                                                 |
| Durasi istirahat default final                  | 7.2         | Usulan awal 15 menit, rentang 10 sampai 20                                                     |
| Cara saldo Bank Waktu dipakai                   | 9.3         | Belum diputuskan mekanik tukarnya                                                              |
| Cara verifikasi misi offline                    | 9.3         | Timer dan konfirmasi awal, belum final                                                         |
| Definisi satu hit per app                       | 11.1        | Konfigurasi per app, belum dirinci                                                             |
| Negara gelombang kedua                          | 12.1        | Setelah validasi Indonesia                                                                     |
| Harga Pro dan lifetime                          | 15          | Belum ditetapkan (opsi lifetime wajib ada)                                                     |
| Angka kriteria beta                             | 14.3        | Disepakati sebelum beta, bukan sekarang                                                        |

## 20. Sumber dan referensi kerja

Referensi berikut adalah bahan riset di balik dokumen ini. Salin ulang alamat lengkapnya dari sumber primer sebelum mengutipnya di tempat publik.

- Halaman Play Store BrainPal: Stop Scroll oleh EpowerX Labs, dibagikan user di percakapan. Data rating, download, versi, dan harga dalam app di Bab 4.1 berasal dari halaman itu.
- Materi ALIVE dari Threads dan screenshot Statistik serta Misi yang dibagikan user. Link Threads tambahan terakhir tidak berhasil dibaca otomatis, jadi learning ALIVE di dokumen ini hanya dari screenshot dan materi yang terlihat, bukan dari isi link yang tidak terbaca.
- Studi one sec di PNAS tentang penurunan pemakaian media sosial, dirujuk dari riset awal percakapan.
- Data durasi smartphone Indonesia dari data.ai 2023, dirujuk dari pemberitaan detik di riset awal percakapan.
- Dokumentasi Android tentang UsageStatsManager dan kebijakan Accessibility Service di Play Store, dirujuk dari riset awal percakapan.
- Dokumentasi Apple tentang FamilyControls dan DeviceActivity, dirujuk dari riset awal percakapan.
