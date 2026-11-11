# 08 — Spesifikasi Karakter & Animasi Companion

Dokumen ini adalah **sumber acuan resmi (Source of Truth)** untuk seluruh desain, alur evolusi, kondisi mood, serta pipeline aset karakter companion di aplikasi Screen Time Companion.

---

## 1. Ringkasan Identitas Karakter

* **Nama Karakter Default**: **Momo**
* **Konsep Dasar**: Makhluk pendamping virtual (*companion*) orisinal berbentuk hibrida kucing/rubah imut yang hangat, tidak menghakimi, dan menjadi cermin emosional dari pemakaian HP pengguna.
* **Fokus Peluncuran (MVP)**: **1 Famili Karakter (Momo)** dengan 3 tahap evolusi untuk memvalidasi retensi pengguna. Famili lain (Rubah dan Burung Malam) disiapkan untuk rilis bertahap setelah MVP.

---

## 2. Alur Progresi Evolusi (Jangka Panjang / Berbasis XP)

Alur pertumbuhan karakter dimulai dari nol saat pertama kali onboarding:

$$\mathbf{Bayi\ (Lv.\ 1-4)} \xrightarrow{\text{XP Penuh}} \mathbf{Remaja\ (Lv.\ 5-10)} \xrightarrow{\text{XP Penuh}} \mathbf{Dewasa\ (Lv.\ 11+)} \xrightarrow{\text{Update}} \mathbf{Wujud\ Puncak}$$

### Aturan Alur Pertumbuhan:
1. **Titik Awal (Onboarding)**: Pengguna selalu memulai dari **Wujud Bayi (Lv. 1)**.
2. **Kondisi Terkunci (`???`)**: Wujud Remaja dan Dewasa dikunci dengan tampilan siluet hitam bertanda tanya `???` di layar Misi.
3. **Mekanisme Evolusi**: Ketika bar XP mencapai target (misal: 400/400 XP), muncul layar perayaan *Evolution Reveal* di mana siluet retak dan wujud baru terbuka.
4. **Prinsip XP**: XP hanya diperoleh dari **misi offline dan mode istirahat**. XP tidak pernah didapat dari scrolling, dan **XP tidak pernah berkurang saat HP harian turun**.

---

## 3. Matriks State Karakter: Evolusi × Mood Harian

Karakter memiliki 2 dimensi perubahan: **Evolusi (Bentuk Fisik)** dan **Mood Harian (Kondisi HP 0–100)**:

```
                  ┌──────────────────────────────┐
                  │        TAHAP EVOLUSI         │
                  │ (1: Bayi, 2: Remaja, 3: Dws) │
                  └──────────────┬───────────────┘
                                 │
             ┌───────────────────┼───────────────────┐
             ▼                   ▼                   ▼
      HP > 60             HP 30 - 60          HP < 30
    idle_fresh            idle_tired       idle_critical
   (Lincah/Ceria)         (Letih/Sayu)     (Gemetar/Kritis)
```

| Tahap Evolusi | Mood Segar (HP > 60) | Mood Lelah (HP 30–60) | Mood Kritis (HP < 30) | Mode Tidur (isResting: true) |
| :--- | :--- | :--- | :--- | :--- |
| **1. Bayi (Lv. 1–4)** | Napas canggung 2.4s, goyang lembut 3.5°, mata bulat, lompat tap kecil. | Membungkuk lambat 3.0s, telinga turun, napas berat. | Meringkuk 1.2s, gemetar halus, postur lemas. | Meringkuk lelap memeluk ekor, napas lambat 3.6s. |
| **2. Remaja (Lv. 5–10)** | Paling lincah 2.0s, telinga tegak, goyang 2.5°, lompat tap paling tinggi. | Tubuh lesu menunduk 5–7°, telinga miring ke dalam 12–14°. | Tubuh menggigil cepat, ekor bergetar $\pm 3^\circ$ tiap 0.2s. | Tidur santai, ekor melingkar ke tubuh 20–23°. |
| **3. Dewasa (Lv. 11+)** | Gerak paling tenang & stabil 3.0s, goyang 1.5°, napas dalam berwibawa. | Postur membungkuk tenang, kepala menunduk 12–15°. | Posisi protektif meringkuk, napas pendek tersengal. | Meditasi tidur anggun, aura tenang. |

---

## 4. Pipeline Aset Produksi: Murni 3D GLB Realtime (Tanpa 2D)

> [!IMPORTANT]
> **Keputusan Pipeline Final**:
> Pendekatan 2D (Rive/Sprite) telah **dihapus sepenuhnya**. Aplikasi mobile menggunakan **100% 3D Realtime GLB** untuk seluruh interaksi companion. Aset yang ada berisi **22 joint ter-skinning dan 6 klip animasi** (lihat §5 Rigging v2); animasi menggerakkan tulang, bukan node mesh. UI boleh menyebut "22 joint" karena aset sudah di-rig ulang dengan bobot tulang yang sebenarnya.

### A. Format Produksi (Flutter Mobile) $\longrightarrow$ **GLB 3D (`.glb`)**
Karakter dimuat dari paket resmi di `docs/docs-assets-chr/paket-momo-3d-final/` dan diintegrasikan melalui paket Flutter `model_viewer_plus`:
* **Stage 1 (Bayi)**: `assets/3d/momo_bayi.glb` (8.23 MB)
* **Stage 2 (Remaja)**: `assets/3d/momo_remaja.glb` (8.11 MB)
* **Stage 3 (Dewasa)**: `assets/3d/momo_dewasa.glb` (13.05 MB)

### B. Standardisasi 6 Klip Animasi Internal GLB
Semua file `.glb` menyimpan 6 klip animasi identik yang dipanggil via controller:

1. **`idle_fresh`** *(Looping, HP > 60)*: Bobbing teratur, napas dada halus, telinga bergoyang bergantian, ayunan ekor berfase.
2. **`idle_tired`** *(Looping, HP 30–60)*: Tulang belakang slouch 5–7°, kepala menunduk 12–15°, telinga rebah ke dalam, ekor lunglai.
3. **`idle_critical`** *(Looping, HP < 30)*: Gemetar cepat siklus 1.2s, kepala menunduk 10°, ujung ekor bergetar $\pm 3^\circ$ tiap 0.2s.
4. **`sleep`** *(Looping, `isResting: true`)*: Tidur pulas 3.6s, napas perut dalam, ekor melingkar memeluk badan 15–23°.
5. **`tap_reaction`** *(One-shot, 0.8s)*: Reaksi sentuhan layar—lompat riang Y, telinga merespon, ekor mengibas cepat, lalu kembali ke idle aktif.
6. **`celebrate`** *(One-shot, 1.8s)*: Selebrasi misi selesai / level up—putar badan 360°, lompat tinggi, dada membusung gembira.

---

## 5. Arsitektur Rigging v2: 22-Joint Skeleton & Skinning

Berdasarkan spesifikasi `momo_3d.rig` (format version 2):

### A. Hierarki Tulang (22 Joints)
```
Root
 └── Hips
      ├── Spine ── Chest ── Neck ── Head ── Ear_L, Ear_R
      ├── Arm_L ── Forearm_L ── Paw_L
      ├── Arm_R ── Forearm_R ── Paw_R
      ├── Leg_L ── Foot_L
      ├── Leg_R ── Foot_R
      └── Tail_1 ── Tail_2 ── Tail_3 ── Tail_Tip
```

### B. Validasi Deformasi Independen
Deformasi linear-blend skinning memverifikasi bahwa gerakan bagian telinga dan ekor benar-benar terisolasi dari torso:
* Rotasi `Ear_L` sebesar 20° menggerakkan ~4.000–5.500 vertex telinga dengan **displacement torso = 0.0000**.
* Rotasi `Tail_3` sebesar 20° menggerakkan ~3.100–6.700 vertex ekor dengan **displacement torso = 0.0000**.
* Karakter dapat digerakkan per bagian secara mandiri (misal: menggoyangkan ujung ekor atau telinga saja).

---

## 6. Integrasi Kode Controller (Flutter Dart)

Implementasi controller resmi dari `docs/docs-assets-chr/paket-momo-3d-final/momo_glb_controller.dart`:

```dart
String momoGlbForStage(int stage) {
  switch (stage) {
    case 1: return 'assets/3d/momo_bayi.glb';
    case 2: return 'assets/3d/momo_remaja.glb';
    case 3: return 'assets/3d/momo_dewasa.glb';
    default: return 'assets/3d/momo_bayi.glb';
  }
}

String momoClipForHp({required double hp, required bool isResting}) {
  if (isResting) return 'sleep';
  if (hp < 30) return 'idle_critical';
  if (hp <= 60) return 'idle_tired';
  return 'idle_fresh';
}
```

Prioritas pemutaran klip:
1. `sleep` (jika `isResting == true`) mendominasi seluruh state.
2. Jika tidak resting: `idle_critical` ($HP < 30$) $\to$ `idle_tired` ($HP \le 60$) $\to$ `idle_fresh` ($HP > 60$).
3. `tap_reaction` (0.8 detik) dan `celebrate` (1.8 detik) diputar sebagai *one-shot interrupt*, kemudian otomatis kembali ke state idle yang aktif.

---

## 7. Hubungan Karakter dengan 4 Tema Visual

> [!IMPORTANT]
> **Karakter TIDAK DIBUAT 4 Kali untuk 4 Tema**:
> Karakter 3D Momo adalah **aset yang sama** untuk semua tema. Tema (Brutal Pop, Pixel Arcade, Soft Clay, Midnight) **hanya mengatur antarmuka wadah** (lingkaran halo, kartu vitals, pencahayaan canvas, border, dan typography).
* **Pixel Arcade**: Ditambahkan post-processing shader pixelation ringan pada canvas tanpa mengubah mesh 3D.
* **Midnight**: Pencahayaan ambient diturunkan dengan rim light mint/cyan lembut.
