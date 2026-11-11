# 📱 Screen Time Companion (Screen Time Tracker)

A mindful, pet-driven Android application designed to build healthy digital habits through conscious friction (*Jeda Sadar*), offline missions (*Bank Waktu*), and an evolving 3D companion (*Momo & Drako*).

---

## 🔒 Kebijakan Privasi (Privacy Policy)

Aplikasi ini mengusung prinsip **100% On-Device & Offline Privacy**. Seluruh data penggunaan dan statistik tersimpan lokal di perangkat pengguna tanpa server eksternal, analitik pihak ketiga, maupun iklan.

Halaman Kebijakan Privasi dapat diakses secara publik melalui tautan berikut:

* **Live Web (GitHub Pages)**: [https://kim007-lol.github.io/screentimetracker/](https://kim007-lol.github.io/screentimetracker/)
* **Alternatif URL**: [https://kim007-lol.github.io/screentimetracker/privacy-policy.html](https://kim007-lol.github.io/screentimetracker/privacy-policy.html)
* **File di Repositori**: [`privacy-policy.html`](./privacy-policy.html) atau [`release/privacy-policy.html`](./release/privacy-policy.html)

> 💡 **Pengaturan GitHub Pages:**  
> Untuk mengaktifkan hosting publik gratis di repositori ini:  
> Buka **Settings** → **Pages** → **Build and deployment** → Source: **Deploy from a branch** → Branch: `main` / `/(root)` → Klik **Save**.

---

## 🌟 Fitur Utama

1. **Jeda Sadar (*Conscious Pause*)**:
   - Interupsi layar penuh 3–10 detik sebelum membuka aplikasi media sosial/pemicu doomscroll (*Instagram Reels, TikTok, YouTube Shorts, Facebook*).
   - Menghadirkan *reflective friction* berbasis riset perilaku (PNAS: ~57% reduksi durasi pemakaian).
2. **Companion 3D Realtime (Momo & Drako)**:
   - Status energi harian (**HP Bar**: Segar, Lelah, Kritis).
   - Progres jangka panjang (**XP Bar** & evolusi wujud: Bayi → Remaja → Dewasa).
   - Model interaktif `.glb` dengan respons sentuhan haptic.
3. **Misi Offline & Bank Waktu**:
   - Misi jalan santai, membaca buku, belajar/deep work, bereskan kamar, dan olahraga.
   - Mengubah aktivitas produktif offline menjadi saldo menit tambahan layar.
4. **Rekap Menyeluruh Semua App**:
   - Donut chart analitik harian, mingguan, dan bulanan dibandingkan terhadap baseline pengguna sendiri.
   - Pelacak pemakaian larut malam (22:00 – 06:00).
5. **Duel Mingguan Offline**:
   - Bertanding sehat dengan teman menggunakan kode ringkasan Base64 tanpa perlu akun atau server terpusat.

---

## 🏗️ Arsitektur Teknis (Dual-Layer)

* **Mobile App (`mobile/`)**:
  - **Flutter & Riverpod**: UI 5 tab (*Rekap, Misi, Beranda, Duel, Profil*), sistem 4 tema (*Brutal Pop, Pixel Arcade, Soft Clay, Midnight*), kalkulasi game logic, dan rendering 3D GLB.
  - **Kotlin Native Android Module**: `UsageStatsManager` untuk rekap waktu, `AccessibilityService` untuk deteksi swipe konten feed, dan `WindowManager` untuk Floating Pill HUD serta overlay Jeda Sadar.
* **Desain Prototipe (`docs-design/`)**:
  - Mockup interaktif web menggunakan React, Vite, dan Tailwind CSS.
* **Dokumentasi Lengkap (`docs/`)**:
  - Modul 01–09 dan PRD teknis menyeluruh.

---

## 📄 Lisensi & Kontak

* Pengembang: **kim007-lol**
* Kontak Pertanyaan / Privasi: `agentkimdev@gmail.com` / `ngabdullahhakim99@gmail.com`

