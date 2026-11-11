# Screen Time Companion — Stitch Generation Spec

Dokumen ini adalah sumber acuan untuk membuat desain layar **Beranda**. Jangan membuat hanya satu tema.

## 1. Output wajib

Hasilkan **12 full-screen Android artboards** berukuran **360 × 800 dp**:

| State | Brutal Pop | Pixel Arcade | Soft Clay | Midnight |
|---|---:|---:|---:|---:|
| S4 — HP Segar, 72/100 | 1 layar | 1 layar | 1 layar | 1 layar |
| S5 — HP Lelah, 38/100 | 1 layar | 1 layar | 1 layar | 1 layar |
| S6 — HP Kritis, 9/100 | 1 layar | 1 layar | 1 layar | 1 layar |

**Total: 12 layar terpisah.** Jangan menggabungkan beberapa tema dalam satu artboard, carousel, moodboard, atau split-screen.

Urutan frame:

1. `S4 / Brutal Pop / Segar`
2. `S4 / Pixel Arcade / Segar`
3. `S4 / Soft Clay / Segar`
4. `S4 / Midnight / Segar`
5. `S5 / Brutal Pop / Lelah`
6. `S5 / Pixel Arcade / Lelah`
7. `S5 / Soft Clay / Lelah`
8. `S5 / Midnight / Lelah`
9. `S6 / Brutal Pop / Kritis`
10. `S6 / Pixel Arcade / Kritis`
11. `S6 / Soft Clay / Kritis`
12. `S6 / Midnight / Kritis`

Tulis nama frame persis seperti daftar di atas agar mudah dibandingkan.

## 2. Aturan konsistensi

- Posisi, ukuran, spacing, isi, dan hierarki komponen harus identik di seluruh tema.
- Hanya token visual dan rendering pet yang boleh berubah antartema.
- Jangan mencampur token dua tema dalam satu layar.
- Gunakan data yang sama: pengguna **Raka**, pet **Momo**, tahap **Remaja**, **Lv. 8**, **XP 240/400 menuju Lv. 9** (bar 60%), total waktu **3j 24m**, TikTok **1j 12m**, hit scroll **387**, dan streak **7 hari**.
- **HP** menunjukkan kondisi harian: turun karena doomscrolling dan pulih saat istirahat.
- **XP** menunjukkan progres jangka panjang untuk kenaikan level dan evolusi. XP hanya diperoleh dari misi dan istirahat, bukan scrolling; XP tidak berkurang ketika HP turun.
- **Vitalitas dihapus** dari versi awal. Tidak ada cadangan daya tahan atau penalti tambahan saat HP habis.
- Pixel art dan pixel font hanya boleh dipakai pada **Pixel Arcade**.
- Brutal Pop, Soft Clay, dan Midnight harus memakai pet vektor, bukan sprite pixel.
- Pet harus orisinal dan tidak menyerupai karakter dari waralaba monster mana pun.
- Semua UI copy menggunakan Bahasa Indonesia yang hangat dan tidak menghakimi.
- Beri setiap layar label tema kecil di luar area artboard, bukan di dalam UI aplikasi.

## 3. Layout Beranda yang dikunci

Semua 12 layar memakai susunan berikut:

1. Status bar dan safe area Android.
2. Header: tanggal dan sapaan **“Hai, Raka!”** di kiri; flame streak **7** di kanan.
3. Badge tahap **Remaja** dan mood **Segar**, **Lelah**, atau **Kritis**.
4. Soft round backdrop di belakang pet.
5. Pet Momo setinggi sekitar 160–200 dp, di tengah.
6. Nama **Momo** dan badge **Lv. 8**.
7. Speech bubble sesuai state.
8. HP bar lebar dan chunky.
9. XP bar yang lebih kecil, label **“XP · menuju Lv. 9”**, nilai **“240/400 XP”**, terisi 60%. Nilainya sama di semua state HP.
10. Tiga stat chips dalam satu baris:
    - Total waktu — **3j 24m**
    - App teratas — **TikTok, 1j 12m**
    - Hit scroll — **387**
11. Pada state Kritis, tambahkan tombol utama **“Istirahatkan HP”** tanpa mengubah urutan elemen lain.
12. Bottom navigation: **Rekap, Misi, Beranda, Duel, Profil**. Beranda berada di tengah, lebih besar, dan raised.

Gunakan horizontal padding 16 dp dan skala spacing 4, 8, 12, 16, 24, 32 dp. Minimum touch target 48 dp. Body text minimal 14 sp.

## 4. State Beranda

### S4 — Segar

- HP: **72/100**
- Mood: **Segar**
- Ekspresi: mata cerah, senyum kecil, telinga tegak.
- Bubble: **“Hari ini masih aman, lanjut ya!”**
- HP memakai warna healthy.
- Tidak ada tombol istirahat.

### S5 — Lelah

- HP: **38/100**
- Mood: **Lelah**
- Ekspresi: mata setengah tertutup, telinga sedikit turun, postur lelah.
- Bubble: **“Udah lumayan banyak scroll nih, istirahat dikit yuk?”**
- HP memakai warna tired.
- Tidak ada bahasa yang menyalahkan pengguna.

### S6 — Kritis

- HP: **9/100**
- Mood: **Kritis**
- Ekspresi: mata khawatir, satu tetes keringat, tubuh sedikit gemetar.
- Bubble: **“Aku butuh istirahat...”**
- HP memakai warna critical.
- Tombol utama: **“Istirahatkan HP”**.
- Jangan hanya mengandalkan warna; mood harus jelas dari ekspresi, label, dan ikon.

## 5. Empat tema

### A. Brutal Pop

- Background `#FFF4E0`
- Surface `#FFFFFF`
- Ink `#111111`
- Primary `#FFD23F`
- Secondary `#FF6B9D`
- Tertiary `#4D96FF`
- HP healthy/tired/critical: `#3DDC84`, `#FFB020`, `#FF4D4D`
- Border: 3 dp solid ink
- Shadow: hard 4 dp ke kanan dan bawah, tanpa blur
- Radius: 6 dp
- Headline: Space Grotesk 700
- Body dan angka: DM Sans dengan tabular figures
- Pet: flat vector, outline hitam 3 dp, warna solid, hard offset shadow seperti die-cut sticker, pipi kemerahan
- **Dilarang memakai pixel font atau pixel art**

### B. Pixel Arcade

- Background `#1B1B2F`
- Surface `#26264A`
- Ink `#F5F5F5`
- Primary `#FFD23F`
- Secondary dan HP healthy `#5BD98C`
- Tertiary `#4D96FF`
- HP tired/critical: `#FFB020`, `#FF4D4D`
- Border: 3 dp solid black
- Shadow: hard 4 dp black
- Radius: 0 dp dengan stepped/notched corners
- Headline dan angka besar: Pixelify Sans 700
- Body: DM Sans; jangan memakai pixel font untuk paragraf
- Pet: karakter dan pose yang sama, digambar sebagai chunky 8-bit pixel art dengan palet terbatas dan dither shadow
- Panel menyerupai dialog box dan inventory slot RPG

### C. Soft Clay

- Background `#FFF1F5`
- Surface `#FFFFFF`
- Ink `#3B2F3F`
- Primary `#FFB5C8`
- Secondary `#B8E0D2`
- Tertiary `#C7B8F5`
- HP healthy/tired/critical: `#6FCF97`, `#F2B84B`, `#EF6B6B`
- Tanpa border
- Shadow: soft plum 18%, 0 8 dp 16 dp, plus inner highlight
- Radius: 28 dp
- Headline: Nunito 800
- Body dan angka: Nunito 600
- Pet: vector clay-like tanpa outline, bentuk membulat, pastel, gradient lembut, glossy highlights
- Komponen terasa inflated dan lembut, bukan pixel

### D. Midnight

- Background `#0B0D12`
- Surface `#151922`
- Ink `#EDEFF5`
- Primary dan HP healthy `#7CF2C8`
- Secondary `#8AB4FF`
- HP tired/critical: `#FFC857`, `#FF6B6B`
- Border: 1 dp solid `#2A3040`
- Shadow: tidak ada; focused item memakai accent glow 25%
- Radius: 14 dp
- Headline: Inter 600
- Body dan angka: Inter 400/500 dengan tabular figures
- Pet: vector minimal, warna tubuh muted, outline terang tipis 1.5 dp, subtle accent rim glow
- Jangan memakai pixel art atau gradient ungu-biru generik

## 6. Interaksi untuk anotasi prototipe

- Tap pet: bounce, bunyi kecil, dan light haptic.
- HP turun: bar drain disertai shake dan flash singkat.
- HP pulih: bar mengisi dengan sparkle.
- Button press: tombol bergeser mengikuti bayangan dengan feedback springy.
- Transisi: 200–300 ms.
- Hormati pengaturan sistem **Reduce motion**.

## 7. Theme picker

Pada onboarding, pengguna memilih salah satu dari:

1. Brutal Pop
2. Pixel Arcade
3. Soft Clay
4. Midnight

Pilihan disimpan sebagai tema aktif dan dapat diganti kapan saja melalui **Profil → Tema**. Theme picker menampilkan empat live preview dengan layout mini Beranda yang sama. Memilih tema mengganti token UI dan gaya rendering pet, bukan data atau posisi komponen.

## 8. Master prompt untuk Stitch

Salin prompt ini secara utuh:

> Using this DESIGN.md as the only source of truth, create a comparison set of the Beranda screen. Generate exactly 12 separate full-screen Android artboards at 360 × 800 dp: S4 Segar, S5 Lelah, and S6 Kritis, each rendered once in Brutal Pop, Pixel Arcade, Soft Clay, and Midnight. Keep layout, component positions, copy, and sample data identical across themes. Only change the theme tokens and pet rendering described in section 5. Pixel art and pixel typography are allowed only in Pixel Arcade. Brutal Pop, Soft Clay, and Midnight must use vector pets in their specified rendering styles. Do not make a single-theme result, carousel, moodboard, split-screen, or blended theme. Name all frames exactly according to section 1 and place them in a 4-column by 3-row comparison grid.

## 9. Prompt cadangan per state

Jika Stitch membatasi jumlah output, jalankan tiga prompt berikut secara terpisah.

### Batch 1 — S4

> Generate S4 Beranda HP Segar as exactly 4 separate 360 × 800 dp screens: Brutal Pop, Pixel Arcade, Soft Clay, and Midnight. Use identical layout and sample data. Name frames “S4 / Brutal Pop / Segar”, “S4 / Pixel Arcade / Segar”, “S4 / Soft Clay / Segar”, and “S4 / Midnight / Segar”. Do not stop after one theme.

### Batch 2 — S5

> Generate S5 Beranda HP Lelah as exactly 4 separate 360 × 800 dp screens: Brutal Pop, Pixel Arcade, Soft Clay, and Midnight. Use identical layout and sample data. HP is 38/100 and Momo looks tired. Name all frames according to section 1. Do not stop after one theme.

### Batch 3 — S6

> Generate S6 Beranda HP Kritis as exactly 4 separate 360 × 800 dp screens: Brutal Pop, Pixel Arcade, Soft Clay, and Midnight. Use identical layout and sample data. HP is 9/100, Momo looks worried, and every screen includes “Istirahatkan HP”. Name all frames according to section 1. Do not stop after one theme.

## 10. Checklist penerimaan

- [ ] Ada tepat 12 artboards.
- [ ] Setiap state memiliki empat tema.
- [ ] Semua artboards berukuran 360 × 800 dp.
- [ ] Data dan layout identik di seluruh tema.
- [ ] Hanya Pixel Arcade yang memakai pixel art dan pixel font.
- [ ] Pet terlihat berbeda sesuai rendering setiap tema.
- [ ] S4, S5, dan S6 memiliki ekspresi dan HP yang benar.
- [ ] Semua layar memakai Bahasa Indonesia.
- [ ] Beranda aktif dan raised pada bottom navigation.
- [ ] Tidak ada tema campuran, carousel, atau split-screen.
