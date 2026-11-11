# 02 — Riset & Pembelajaran Kompetitor

Dokumen ini mendokumentasikan analisis pasar dan pembelajaran teknis/produk dari aplikasi sejenis sebagai dasar keputusan desain.

---

## 1. Analisis BrainPal: Stop Scroll (EpowerX Labs)

* **Data Metrik Pasar**: Rating 4,8 (~106k ulasan), >1 juta unduhan di Google Play Store. Ukuran ~43 MB, target Android 7.0 ke atas.
* **Fitur yang Dieksekusi dengan Baik**:
  * Penghitung live video pendek di Instagram, YouTube, Facebook, dan Snapchat.
  * Visual kondisi otak yang makin rusak seiring kenaikan hitungan scroll.
  * *Scroll Battle* sederhana antar teman (hitungan terendah menang).
  * Widget dan blokir reels (fitur Pro).
  * Menggunakan *Accessibility Service* untuk deteksi swipe.
* **Celah dan Masalah dari Ulasan Pengguna BrainPal**:
  1. **Kesalahpahaman Double Counting**: Pengguna mengira aplikasi bug ketika swipe balik ikut terhitung. Pelajaran bagi produk ini: aturan hitung harus diumumkan secara gamblang sejak onboarding.
  2. **Permintaan Opsi Lifetime**: Pengguna keberatan dengan sistem langganan terus-menerus dan secara eksplisit meminta opsi bayar sekali seumur hidup (*lifetime purchase*).
  3. **Fokus Sempit**: Hanya melacak reels/shorts video pendek, tidak memberikan rekap holistik seluruh penggunaan smartphone, tidak ada companion berevolusi, dan tidak ada misi offline.

---

## 2. Pola Ekosistem EpowerX Labs (Fragmentasi Masalah)

EpowerX memecah kebutuhan wellbeing ke dalam aplikasi-aplikasi terpisah:
* **BrainPal**: Fokus penghitung reels & scroll battle.
* **Regain**: Pomodoro, focus room multiplayer, blocker belajar.
* **Detox**: Hard blocker untuk mengunci HP selama berhari-hari.
* **Bedlock**: Bedtime blocker untuk jam tidur malam.

> **Peluang Produk Ini**: Pengguna merasa lelah menginstal banyak aplikasi untuk satu masalah inti. Produk ini menyatukan rekap lengkap, companion interaktif, jeda sadar, dan misi ke dalam **satu aplikasi terintegrasi**.

---

## 3. Pembelajaran dari Konsep ALIVE (Fatan / Threads)

ALIVE adalah prototipe aplikasi screen time yang menghadirkan interaksi segar:
* **Dynamic Notch / Pill Live**: Menampilkan waktu layar secara melayang dan real-time.
* **Transparansi Teknis Nama Paket**: Di layar statistik, ALIVE secara jujur mencantumkan bahwa sistem hanya dapat menampilkan nama yang diberikan OS Android (sebagian berupa nama paket). Sikap transparan ini membangun kepercayaan pengguna.
* **Sistem Misi "Beri Ruang" & Bank Waktu**: Misi offline (Jalan 20m, Belajar 30m, Bereskan Kamar 20m) menghasilkan saldo waktu (Masuk, Keluar, Tersedia). Konsep ini membuktikan bahwa misi offline "membayar pengguna kembali dengan waktu".

---

## 4. Tren UI: Floating Notch / Pill Mengambang

Pola Dynamic Island / pill kecil mengambang di layar Android yang dapat diekspansi memberikan akses informasi instan tanpa harus membuka aplikasi utama.
* Mode collapsed: Maskot mini companion + durasi sesi + status HP.
* Mode expanded: Insight sesi, tombol jeda sadar, dan tombol aksi istirahat instan.
