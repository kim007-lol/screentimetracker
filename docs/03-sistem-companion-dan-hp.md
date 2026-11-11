# 03 — Sistem Companion & Gamifikasi

Dokumen ini mendefinisikan loop permainan, metrik kesehatan companion, penghapusan konsep Vitalitas pada MVP, serta arsitektur perolehan XP dan evolusi.

---

## 1. Sistem Metrik: HP Harian & XP Evolusi

### A. HP Harian (Kondisi Hari Ini: 0–100)
* **Tujuan**: Menjadi cermin langsung keseimbangan pemakaian smartphone pada hari berjalan.
* **Pemicu Penurunan**: Doomscrolling tanpa henti pada aplikasi target, sesi yang melebihi batas yang ditentukan, serta pemakaian larut malam.
* **Pemicu Pemulihan**: Durasi tanpa smartphone, mode istirahat aktif (*Take a Break*), dan penyelesaian misi offline.
* **Tiga Kondisi Mood Utama**:
  1. **Segar (HP > 60)**: Mata cerah, senyum kecil, telinga tegak. Speech bubble: *"Hari ini masih aman, lanjut ya!"*
  2. **Lelah (HP 30–60)**: Mata sayu, telinga turun, postur rileks. Speech bubble: *"Udah lumayan banyak scroll nih, istirahat dikit yuk?"*
  3. **Kritis (HP < 30)**: Mata khawatir/gemetar, keringat kecil. Speech bubble: *"Aku butuh istirahat..."*, memicu tombol utama **"Istirahatkan HP"**.

---

### B. Keputusan Penting: Penghapusan Vitalitas $\to$ Bar Kedua Dialihkan ke XP

> [!IMPORTANT]
> **Keputusan Desain & UX**:
> Pada konsep awal, dirancang sistem dual-bar (*HP harian* + *Vitalitas jangka panjang*). Namun, melalui pengujian prototipe dan evaluasi UX, **sistem Vitalitas DIHAPUS dari versi awal (MVP)** dengan alasan:
> 1. **Mencegah Hukuman Ganda (*Double Penalty*)**: Jika HP sudah habis, memotong bar kesehatan kedua (Vitalitas) terasa terlalu menghakimi dan menekan pengguna (*guilt-tripping*), bertolak belakang dengan prinsip *"kesadaran dulu, bukan polisi HP"*.
> 2. **Menghindari Beban Kognitif di UI**: Dua bar kondisi kesehatan yang berbeda plus indikator level membuat pengguna bingung.

**Solusi Tampilan Beranda yang Ditetapkan**:
* **Bar 1 (Atas, Lebar & Chunky)**: **HP Bar** (`HP 72/100`), mencerminkan kesegaran harian Momo.
* **Bar 2 (Bawah, Lebih Ramping)**: **XP Bar** (`XP · menuju Lv. 9 | 240/400 XP | 60%`), mencerminkan progres evolusi jangka panjang.
* **Sifat XP**: XP **hanya diperoleh dari perilaku positif** (misi offline dan istirahat), tidak pernah diperoleh dari scrolling, dan **XP TIDAK PERNAH berkurang saat HP turun**.

---

## 2. Mekanisme Saat HP Habis (Kondisi Kritis)

Ketika HP mencapai titik kritis atau 0:
1. Muncul overlay peringatan bahaya yang menampilkan kondisi companion secara dramatis namun hangat.
2. **Opsi 1 (Disarankan)**: **Istirahatkan HP** selama beberapa menit (default 15 menit, dapat dikonfigurasi 10–20 menit). Selama mode istirahat, layar menampilkan animasi pemulihan bertahap dan memberikan reward XP.
3. **Opsi 2**: **Tetap Lanjut Memakai HP**. Pengguna tetap diberikan kebebasan menggunakan HP tanpa pemblokiran paksa. Pada versi MVP, tidak ada penalti pemotongan bar Vitalitas; konsekuensinya hanya berupa status companion tetap Kritis dan tidak ada perolehan XP hingga pengguna beristirahat.
4. **Companion Tidak Pernah Mati Permanen**: Selalu ada jalan untuk pulih melalui istirahat dan hari baru yang seimbang.

---

## 3. Karakter Companion & Jalur Evolusi

* **Karakter Orisinal**: Karakter hewan orisinal dengan inspirasi monster-collecting (bukan meniru IP berlisensi).
* **Famili Starter (Onboarding)**:
  1. *Kucing*: Tenang, sensitif terhadap jeda.
  2. *Rubah*: Lincah, aktif mengingatkan target.
  3. *Burung Malam*: Siaga pada pemakaian larut malam.
* **Tahap Evolusi**:
  $$\text{Bayi} \longrightarrow \text{Remaja} \longrightarrow \text{Dewasa} \longrightarrow \text{Wujud Puncak}$$
  *Tahap berikutnya yang masih terkunci ditampilkan sebagai siluet misterius dengan label "???" di layar Misi.*
* **Koleksi & Variasi**: Varian warna dan corak bulu terbuka murni dari pencapaian dan misi offline (tersimpan di album Profil), **bukan dari gacha/lootbox berbayar**.

---

## 4. Arsitektur Aset Companion: Asset-Driven Pipeline

> [!IMPORTANT]
> **Keputusan Arsitektur Visual**:
> Karakter companion **TIDAK DIBUAT melalui string koordinat path SVG langsung di dalam kode komponen**. Pendekatan hardcoded kode terbukti menghasilkan visual kaku (*programmer art*), tanpa *depth* dan emosi, serta menyulitkan animasi organik.
> 
> Seluruh visual companion wajib diproduksi dan dimuat melalui **Asset-Driven Pipeline**:

### A. Untuk Aplikasi Mobile Final (Flutter + Android) $\longrightarrow$ **GLB 3D Realtime**
* **Format File**: Aset `.glb` terisolasi di folder `assets/3d/`, satu file per tahap evolusi (`momo_bayi.glb`, `momo_remaja.glb`, `momo_dewasa.glb`).
* **Catatan Pipeline**: Rencana awal Rive (`.riv`) telah **diganti 100% 3D GLB** pada revisi final. Aset saat ini berisi 22 node bernama dan 6 klip animasi, belum skinning per tulang. Detail klip dan prioritas state ada di [`08-spesifikasi-karakter-dan-animasi.md`](./08-spesifikasi-karakter-dan-animasi.md).
* **State Machine Companion**:
  * **Idle Breathing & Blinking**: Klip `idle_fresh`, `idle_tired`, `idle_critical`, dan `sleep` diputar berulang sesuai HP dan mode istirahat.
  * **Interactive Touch / Haptic**: Ketukan memicu klip satu kali `tap_reaction`, lalu otomatis kembali ke idle aktif; misi atau level up memicu `celebrate`.
  * **Smooth Mood Blending**: Transisi antar klip dilakukan tanpa memuat ulang model, sehingga pergantian mood tidak terasa patah.
* **Efisiensi Aset**: Model 3D memakai tekstur terkompresi dan poster PNG sebagai fallback saat model masih dimuat.

### B. Untuk Prototipe Mockup Web ([`docs-design/`](../docs-design)) $\longrightarrow$ **Visual Asset Files (WebP / SVG Terkurasi)**
* Tidak lagi merender matematika path mentah di file JSX/TSX.
* Karakter dimuat dari file aset visual mandiri di `public/assets/pet/` (misal: `momo-segar.webp`, `momo-lelah.webp`, `momo-kritis.webp`).
* Memungkinkan detail visual yang kaya: tekstur bulu lembut, bayangan halus, pipi merona hangat, dan mata ekspresif yang tampak hidup.
