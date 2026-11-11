# 📱 Screen Time Companion — Dokumentasi Proyek

Dokumentasi resmi persiapan dan arsitektur produk **Screen Time Companion** (Nama kerja: *App Screen Time*).

> [!NOTE]
> **Status Prototipe Visual**: Folder [`docs-design/`](../docs-design) adalah **mockup mentah interaktif** (React 19 + Tailwind v4 + Vite) yang berfungsi sebagai **referensi desain dan visual playground**. Kode tersebut bukan kode aplikasi final; aplikasi mobile final akan dibangun dengan **Flutter + modul native Kotlin Android**.

---

## 📂 Struktur Dokumentasi Modular

Dokumentasi proyek dipecah menjadi modul-modul independen agar mudah dikelola, direvisi, dan dipelajari:

**Untuk AI agent yang menambah pet atau mengubah rig, animasi, pill, dan overlay:** mulai dari [Panduan Integrasi Pet](./09-panduan-pet-rig-animasi-overlay.md). Panduan membedakan implementasi saat ini dari kebutuhan mode statis/full animasi dan pet keliling layar yang belum diimplementasikan.

| No | Modul Dokumen | Fokus Isi |
| :-: | :--- | :--- |
| **01** | [**Visi & Arah Produk**](./01-visi-dan-arah-produk.md) | Masalah yang diselesaikan, target pengguna, prinsip wellbeing, serta scope MVP. |
| **02** | [**Riset & Pembelajaran Kompetitor**](./02-riset-kompetitor.md) | Analisis pasar BrainPal, ekosistem EpowerX, ALIVE, serta tren Dynamic Island/Pill. |
| **03** | [**Sistem Companion & Gamifikasi**](./03-sistem-companion-dan-hp.md) | HP harian, **keputusan penghapusan Vitalitas $\to$ XP Bar**, evolusi Momo, dan famili starter. |
| **04** | [**Sistem Desain & 4 Tema Visual**](./04-desain-dan-tema.md) | 4 Preset tema (Brutal Pop, Pixel Arcade, Soft Clay, Midnight), pipeline aset companion 3D, dan aturan tipografi. |
| **05** | [**Spesifikasi Fitur & 5 Layar Utama**](./05-fitur-dan-layar.md) | Alur 5 tab (Rekap, Misi, Beranda, Duel, Profil), Bank Waktu, Floating Pill, dan Jeda Sadar. |
| **06** | [**Arsitektur Teknis Android**](./06-arsitektur-teknis-android.md) | Stack Flutter + Kotlin native, `UsageStatsManager`, `AccessibilityService`, privasi lokal, dan audit Play Store. |
| **07** | [**Log Keputusan & Backlog Terbuka**](./07-keputusan-dan-backlog.md) | Rekap keputusan terkunci (Arah Terkunci), tabel keputusan terbuka, dan roadmap masa depan. |
| **08** | [**Spesifikasi Karakter & Animasi**](./08-spesifikasi-karakter-dan-animasi.md) | **Matriks lengkap karakter Momo**: alur evolusi (Bayi $\to$ Remaja $\to$ Dewasa), mood harian (Segar/Lelah/Kritis), dan pipeline aset 3D GLB dengan 6 klip animasi. |
| **09** | [**Panduan Agent: Pet, Rig, Animasi, Pill & Overlay**](./09-panduan-pet-rig-animasi-overlay.md) | Kontrak aset/runtime, pipeline dan jebakan rig, integrasi pet baru, mode statis/penuh, overlay roaming, privasi, dan checklist QA. |

---

## ⚡ Ringkasan Keputusan Kunci Terbaru (Changelog Design & UX)

1. **Vitalitas Dihapus dari MVP**:
   * Bar kedua di Beranda dialihkan menjadi **XP Bar** (`240/400 XP menuju Lv. 9`).
   * Menghilangkan hukuman ganda (*double-penalty*) agar aplikasi tetap menjadi "cermin sadar", bukan "polisi HP".
2. **Karakter Master 3D (GLB)**:
   * Satu set model 3D (Bayi, Remaja, Dewasa) dengan 6 klip animasi seragam dipakai untuk semua tema.
   * Gaya *pixel art* dan *pixel font* **hanya berlaku pada tema Pixel Arcade**.
3. **Keterbacaan Angka Statistik**:
   * Angka pada kartu statistik di tema non-pixel wajib menggunakan font tabular standar (*DM Sans*, *Space Grotesk*, *Nunito*, *Inter*).
4. **Penyempurnaan Tema Midnight & Pixel Arcade**:
   * **Midnight**: Dibuat lebih tenang dan premium (dark minimal, aksen mint terukur, rim glow tipis).
   * **Pixel Arcade**: Aksen retro RPG dengan notched corners, border 3dp, dan bar HP bersegmen.
5. **Asset-Driven Companion Pipeline**:
   * Karakter companion dialihkan dari pembuatan via kode path SVG kaku (*programmer art*) menjadi **aset file mandiri**.
   * Pipeline final: **3 file GLB 3D realtime** (`assets/3d/`) dengan 6 klip animasi (`idle_fresh`, `idle_tired`, `idle_critical`, `sleep`, `tap_reaction`, `celebrate`) untuk aplikasi mobile final.
   * File aset visual terkurasi (WebP / SVG) untuk prototipe mockup web di [`docs-design/`](../docs-design).
