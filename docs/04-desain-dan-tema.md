# 04 — Sistem Desain & 4 Tema Visual

Dokumen ini menjelaskan sistem desain, token visual, panduan rendering karakter companion, serta fungsi folder mockup mentah [`docs-design/`](../docs-design).

---

## 1. Peran Folder `docs-design/` (Mockup Mentah)

> [!NOTE]
> Folder [`docs-design/`](../docs-design) di dalam proyek ini adalah **mockup mentah interaktif berbasis web (React 19 + Tailwind CSS v4 + Vite)**.
> * **Tujuan**: Sebagai *visual playground* dan instrumen validasi perbandingan desain 12 artboard (3 kondisi HP × 4 tema visual) pada ukuran 360 × 800 dp.
> * **Bukan Kode Produksi**: Kode di `docs-design/` tidak ditujukan sebagai aplikasi Android final. Aplikasi final akan dibangun menggunakan **Flutter** dan **modul native Kotlin Android**.

---

## 2. Empat Preset Tema Visual

Pengguna memilih satu tema pada alur onboarding dan dapat mengubahnya kapan saja melalui menu **Profil $\to$ Tema**:

| Elemen Token | **A. Brutal Pop** (Neo-Brutalism) | **B. Pixel Arcade** (Retro RPG) | **C. Soft Clay** (Pastel Kawaii) | **D. Midnight** (Dark Minimal Premium) |
| :--- | :--- | :--- | :--- | :--- |
| **Background** | `#FFF4E0` (Krem hangat) | `#1B1B2F` (Navy gelap) | `#FFF1F5` (Pastel blush) | `#0B0D12` (Onyx pekat) |
| **Surface** | `#FFFFFF` | `#26264A` | `#FFFFFF` | `#151922` |
| **Ink / Text** | `#111111` | `#F5F5F5` | `#3B2F3F` | `#EDEFF5` |
| **Aksen Utama** | `#FFD23F` (Kuning berani) | `#FFD23F` & `#5BD98C` | `#FFB5C8` (Pink lembut) | `#7CF2C8` (Mint segar terkontrol) |
| **Warna HP** | `#3DDC84` / `#FFB020` / `#FF4D4D` | `#5BD98C` / `#FFB020` / `#FF4D4D` | `#6FCF97` / `#F2B84B` / `#EF6B6B` | `#7CF2C8` / `#FFC857` / `#FF6B6B` |
| **Border** | 3 dp solid ink | 3 dp solid black | *Tanpa border* | 1 dp solid `#2A3040` |
| **Shadow** | Hard offset 4 dp kanan-bawah | Hard offset 4 dp black | Soft plum 18% (0 8dp 16dp) + inner highlight | *Tanpa bayangan*; rim glow 25% pada elemen aktif |
| **Corner Radius** | 6 dp | 0 dp (notched/stepped corners) | 28 dp (inflated clay) | 14 dp |
| **Font Judul** | Space Grotesk 700 | Pixelify Sans 700 | Nunito 800 | Inter 600 |
| **Font Angka & Isi** | **DM Sans (tabular figures)** | **DM Sans** (Pixelify khusus angka hero) | **Nunito 600** | **Inter (tabular figures)** |

---

## 3. Rendering Karakter Companion: Asset-Driven Pipeline

* **Larangan Hardcode SVG Path di Kode**:
  * Dilarang menggambar karakter langsung dengan deretan string koordinat path SVG di dalam komponen aplikasi (`App.tsx` atau file widget). Karakter harus berupa **file aset mandiri** yang di-import atau dimuat secara terisolasi.
* **Arsitektur Aset Efisien (GLB 3D Realtime)**:
  * Menggunakan **3 Model Master GLB** (Bayi, Remaja, Dewasa) dengan 6 klip animasi seragam, dimuat via `assets/3d/` (lihat [`08-spesifikasi-karakter-dan-animasi.md`](./08-spesifikasi-karakter-dan-animasi.md)).
  * Parameter tema diterapkan pada wadah render (pencahayaan kanvas, halo, border kartu, dan tipografi), bukan pada mesh karakter.
* **Penerapan Gaya per Tema**:
  * **Brutal Pop**: Aset vektor solid, outline hitam tebal 3 dp, hard offset shadow mirip stiker die-cut, pipi kemerahan.
  * **Pixel Arcade**: Aset dipikselasi menjadi 8-bit chunky dengan palet warna terindeks dan bayangan dither 2px (hanya tema ini yang menggunakan gaya pixel art).
  * **Soft Clay**: Aset terasa membulat tanpa outline keras, gradien pastel lembut, highlight glossy terasa kenyal (*inflated*).
  * **Midnight**: Aset vektor bernuansa muted, outline terang tipis 1.5 dp, dan subtle accent rim glow.
* **Aturan Keterbacaan Angka (Penting)**:
  * Angka di kartu statistik (misal: `3j 24m`, `1j 12m`, `387 hit`) **DILARANG menggunakan font pixel di tema non-pixel**. Font tabular standar wajib digunakan agar data mudah dibaca sekilas.

---

## 4. Layout 12 Layar Beranda yang Terstandarisasi

Semua 12 layar perbandingan Beranda (3 State HP × 4 Tema) memiliki tata letak identik:
1. Status bar dan Android safe area.
2. Header: Tanggal & sapaan *"Hai, Raka!"* di kiri; flame streak *7 hari* di kanan.
3. Badge status: Tahap *Remaja* dan mood (*Segar*, *Lelah*, atau *Kritis*).
4. Backdrop melingkar lembut di belakang hero pet Momo.
5. Pet Momo (tinggi 160–200 dp) dengan aksi interaktif tap bounce.
6. Nama Momo & badge Lv. 8.
7. Speech bubble kontekstual.
8. **HP Bar** lebar dan chunky.
9. **XP Bar** (`XP · menuju Lv. 9 | 240/400 XP | 60%`).
10. Tiga stat chips sejajar: Total Waktu (`3j 24m`), App Teratas (`TikTok 1j 12m`), Hit Scroll (`387`).
11. Tombol aksi utama **"Istirahatkan HP"** (hanya muncul saat mood Kritis).
12. Bottom navigation 5 tab dengan tab **Beranda** di tengah dan dibuat raised.
