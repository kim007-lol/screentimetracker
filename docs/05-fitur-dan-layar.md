# 05 — Spesifikasi Fitur & 5 Layar Utama

Dokumen ini menguraikan struktur navigasi 5 tab, alur antarmuka, Bank Waktu, serta overlay interaktif di luar aplikasi utama.

---

## 1. Struktur Navigasi Utama (Bottom Navigation)

Urutan tab pada bilah navigasi bawah terkunci sebagai berikut:

$$\text{Rekap} \quad\vert\quad \text{Misi} \quad\vert\quad \mathbf{Beranda\ (Tengah,\ Raised)} \quad\vert\quad \text{Duel} \quad\vert\quad \text{Profil}$$

* **Beranda (Landing Screen)**: Dibuat menonjol (ukuran tombol lebih besar, sedikit terangkat, dengan ikon companion hero).
* **Konsistensi Hierarki**: Semua tab dapat diakses instan dengan status aktif yang jelas mengikuti token tema aktif.

---

## 2. Rincian Lima Tab Utama

### 1. Tab Beranda (Home)
* **Bagian Atas**: Tanggal harian dan sapaan personal *"Hai, Raka!"*, serta flame streak badge (*7 hari*).
* **Hero Section**: Panggung companion Momo (interaktif tap-bounce), badge tahap (*Remaja*), status mood (*Segar/Lelah/Kritis*), dan speech bubble kontekstual.
* **Bar Indikator**:
  * Bar HP Chunky: Status energi harian (`72/100`).
  * Bar XP Ramping: Progres level (`240/400 XP menuju Lv. 9`).
* **Stat Chips Sejajar**: Total waktu layar, App teratas, Hit scroll harian.
* **Target Mingguan**: Progres **5 dari 7 hari seimbang** ditampilkan sebagai deretan titik, dihitung dari riwayat harian (bukan streak yang rapuh).
* **Misi Hari Ini**: Satu misi offline yang belum selesai tampil dengan tombol cepat, tanpa harus membuka tab Misi.
* **Aksi Kritis**: Tombol utama *"Istirahatkan HP"* muncul otomatis ketika HP menyentuh level kritis.

### 2. Tab Rekap (All-App Analytics)
* **Donut Chart**: Total waktu layar pada periode terpilih (Harian / Mingguan / Bulanan) dibandingkan dengan baseline pengguna sendiri.
* **Tab Kategori**: *Sosial*, *Hiburan*, *Produktivitas*, *Kerja*, dan *Belajar* (pemetaan app dapat dikustomisasi).
* **Peringkat Penggunaan App**: Daftar durasi per app, jumlah pembukaan (*open counts*), dan sesi terpanjang.
* **Catatan Transparansi Sistem**: Menampilkan keterangan jujur jika nama paket tidak terbaca penuh dari OS (mengadopsi pembelajaran ALIVE).
* **Kartu Rekap Shareable**: Format bergaya Wrapped untuk dibagikan ke media sosial dengan perbandingan kontekstual lokal.

### 3. Tab Misi (Offline Engine & Bank Waktu)
* **Bank Waktu**: Menampilkan 3 metrik transparan:
  * **Masuk**: Total menit yang berhasil dikumpulkan dari misi offline.
  * **Keluar**: Menit yang telah digunakan sebagai kuota layar tambahan.
  * **Tersedia**: Sisa saldo waktu saat ini.
* **Katalog Misi Offline**:
  * *Jalan Santai*: 20 menit (+15m saldo, +XP, +HP)
  * *Belajar / Deep Work*: 30 menit (+20m saldo, +XP, +HP)
  * *Membaca Buku*: 30 menit (+20m saldo, +XP, +HP)
  * *Olahraga / Workout*: 20 menit (+25m saldo, +XP, +HP)
  * *Bereskan Kamar*: 20 menit (+15m saldo, +XP, +HP)
* **Jalur Evolusi**: Pratinjau tahapan wujud berikutnya dengan siluet misterius `???`.

### 4. Tab Duel (Social Battle)
* Pertandingan mingguan dengan 2–6 teman.
* Mengadu jumlah scroll terendah dan delta perbaikan terhadap baseline masing-masing (agar pengguna baru tetap memiliki kesempatan menang yang adil).
* **Duel offline tanpa server**: pengguna membagikan **kode duel** berisi nama, menit layar, dan hit scroll mingguan, lalu teman menempelkan kode tersebut. Papan peringkat tersimpan lokal; tidak ada akun, server, atau detail app yang ikut terkirim.
* Cek skor cukup dilakukan sekali sehari tanpa insentif toxic untuk membuka aplikasi berulang kali.

### 5. Tab Profil (Settings & Hub)
* Album varian dan koleksi companion yang telah dibuka.
* Theme picker (4 preset tema) & Accent color switcher.
* Pemilihan bahasa antarmuka (Bahasa Indonesia & Bahasa Inggris).
* Manajemen aplikasi yang dipantau dan pengaturan durasi istirahat.
* **Batas harian per app** (opsional): batas ditegakkan lewat Jeda Sadar; saat tercapai pengguna memilih tutup app atau lolos 5 menit.
* **Pengingat harian tunggal**: satu notifikasi per hari dengan waktu yang bisa diatur, tanpa deretan notifikasi.
* Kontrol privasi: Ekspor data lokal dan tombol hapus semua data.

---

## 3. Fitur Luar Aplikasi: Pill & Jeda Sadar

### A. Floating Pill Mengambang (Native Android Overlay)
* **Mode Collapsed**: Menempel di area atas/bawah status bar. Menampilkan ikon mini pet, durasi live di app yang sedang aktif, dan hitungan scroll (misal: `42m · 87`).
* **Mode Expanded (Saat Diketuk)**:
  * Speech bubble saran dari companion.
  * Status HP terkini.
  * Tombol instan *"Mulai Istirahat"* atau *"Tutup App"*.

### B. Jeda Sadar (Conscious Pause)
* Interupsi layar penuh selama 3–10 detik (dapat diatur di Profil) sebelum aplikasi target yang dipantau terbuka.
* Menampilkan pertanyaan reflektif: *"Mau ngapain di app ini?"* dan kondisi HP companion.
* Tindakan utama: Tombol besar **"Batal Buka"**, dengan tombol kecil *"Lanjut"*; hitung mundur selesai berarti pengguna boleh lanjut.
* Setelah lanjut, aplikasi yang sama tidak dijeda lagi selama 15 menit agar tidak mengganggu berulang.
