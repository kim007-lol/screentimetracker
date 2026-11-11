# 07 — Log Keputusan & Backlog Terbuka

Dokumen ini mencatat keputusan arsitektur yang sudah dikunci dari hasil pengujian desain, daftar keputusan yang masih terbuka, serta daftar backlog pasca-MVP.

---

## 1. Log Keputusan Terkunci (Hasil Uji Desain & UX)

| No | Keputusan | Status | Rasional & Dampak |
| :-: | :--- | :---: | :--- |
| **01** | **Penghapusan Vitalitas dari MVP** | **Terkunci** | Dua bar kesehatan plus level terbukti membingungkan pengguna dan memberi penalti berlipat (*double penalty*). Bar kedua dialihkan penuh ke **XP Bar** (`240/400 XP menuju Lv. 9`). |
| **02** | **Karakter Master Vektor (Rive)** | **Terkunci** | Menghindari pembuatan 15+ wujud karakter secara berulang per tema. Karakter vektor diatur parameternya sesuai tema; efek pikselasi hanya diterapkan di tema Pixel Arcade. **(Diperbarui: pipeline final 100% 3D GLB, lihat docs/08.)** |
| **03** | **Aturan Font Angka & Statistik** | **Terkunci** | Angka di tema non-pixel wajib menggunakan font tabular standar (*DM Sans*, *Inter*, *Space Grotesk*, *Nunito*). Dilarang memakai font pixel untuk angka statistik di luar tema Pixel Arcade. |
| **04** | **Penyempurnaan Tema Midnight** | **Terkunci** | Dibuat lebih tenang dan premium (dark minimal), aksen mint terkontrol (bukan neon menyeluruh), pet muted, dan rim glow tipis 25% pada elemen terfokus. |
| **05** | **Penyempurnaan Pixel Arcade** | **Terkunci** | Notched corners (sudut berundak 0 dp), border 3 dp solid, HP bar bersegmen retro, dither shading, dan panel bergaya inventory/dialog box RPG. |
| **06** | **Peran Folder `docs-design/`** | **Terkunci** | Berfungsi murni sebagai **mockup mentah interaktif (React/Vite)** untuk referensi desain dan perbandingan 12 artboard, bukan basis kode aplikasi mobile final. |
| **07** | **Asset-Driven Companion Pipeline** | **Terkunci** | Menolak pembuatan karakter lewat hardcoded path SVG di kode (menghindari visual kaku/programmer art). Karakter wajib berbasis file aset. **(Diperbarui: implementasi final memakai 3 file GLB dengan 6 klip animasi, lihat docs/08; bukan lagi Rive.)** |

---

## 2. Tabel Keputusan Terbuka (Siap Divalidasi)

Berikut adalah daftar keputusan yang belum difinalisasi dan akan diputuskan melalui pengujian data beta:

| Keputusan | Domain Terkait | Opsi & Status Saat Ini |
| :--- | :---: | :--- |
| **Nama Produk Final** | Branding / Store | Nama kerja saat ini: *Screen Time Companion* / *App Screen Time*. Hindari istilah *brainrot*. |
| **Rumus Penurunan & Pemulihan HP** | Game Balancing | Formula spesifik (misal: $-1$ HP per 15 scroll TikTok, $+10$ HP per sesi istirahat 15 menit). |
| **Mekanisme Tukar Bank Waktu** | Gameplay | Menentukan apakah saldo waktu dipakai sebagai tambahan kuota app yang dipantau atau voucher sesi bebas. |
| **Daftar Final Starter Companion** | Konten / Desain | Usulan awal: Famili Kucing, Rubah, dan Burung Malam. |
| **Model Harga Pro & Lifetime** | Monetisasi | Opsi pembelian satu kali seumur hidup (*lifetime*) wajib ada, mendampingi langganan bulanan/tahunan. |
| **Kriteria Keberhasilan Beta** | Peluncuran | Target retensi minggu ke-2 dan persentase penurunan scroll pada cohort awal di Indonesia. |

---

## 3. Backlog Fitur Pasca-MVP

Item berikut dicatat agar tidak hilang, namun **berada di luar scope MVP**:
* **Sistem Vitalitas Lanjutan**: Cadangan daya tahan jangka panjang yang dipertimbangkan kembali jika data beta menunjukkan perlunya diferensiasi penalti di luar HP harian.
* **Widget Home Screen Android**: Widget interaktif yang menampilkan pet Momo tidur atau segar di layar beranda sistem.
* **Tema Visual Tambahan**: Kemungkinan preset tema baru seperti *Sticker Collage* atau *Retro Manga/Komik*.
* **Skin & Aksesoris Pet**: Kustomisasi kosmetik (topi, kacamata) yang dibuka dari pencapaian misi.
* **Evaluasi Ulang Platform iOS**: Dirancang ulang sebagai rekap terbatas jika kebijakan API DeviceActivity Apple melonggar di masa depan.
