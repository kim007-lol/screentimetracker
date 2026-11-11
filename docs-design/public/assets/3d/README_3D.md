# Paket Momo 3D, bahan konversi ke .glb

Paham, dan ini sudah dibuat sesuai 3 Master Prompt kamu.

## Isi paket

- `momo_bayi.png`: Bayi, chibi, kepala besar bulat, mata amber besar, telinga bundar, ekor pendek berbulu, duduk depan penuh, latar putih
- `momo_remaja.png`: Remaja, telinga tegak tajam, ekor rubah besar mekar, senyum ceria, duduk depan penuh, latar putih
- `momo_dewasa.png`: Dewasa, telinga panjang ujung emas, bulu dada lebat putih, ekor panjang ujung emas bercahaya, duduk tegak depan penuh, latar putih
- `momo_3d_rig.json`: skeleton rig untuk 3 tahap, lengkap dengan bone Root, Hips, Spine, Chest, Neck, Head, Ear_L/R, Eye_L/R, Jaw, Arm/Forearm/Paw kiri kanan, Leg/Foot kiri kanan, dan Tail_1, Tail_2, Tail_3, Tail_Tip
- `README_3D.md`: file ini

Semua gambar sudah dicek visual langsung: depan penuh, simetris, latar putih bersih, warna krem dan peach-orange konsisten antar tahap.

## Cara jadi .glb, langkah yang benar

1. Upload satu gambar ke Tripo3D, Meshy, atau Rodin, pilih Image to 3D
2. Biarkan engine memotong latar putih dan membangun mesh
3. Pilih animasi Idle sesuai tahap:
   - Bayi: Idle Cute / Bouncing / Clumsy
   - Remaja: Idle Active / Alert / Tail Wagging
   - Dewasa: Idle Noble / Calm Breathing
4. Download sebagai `.glb` dengan nama:
   - `momo_bayi.glb`
   - `momo_remaja.glb`
   - `momo_dewasa.glb`
5. Di Blender / Unity / Godot, samakan nama bone dengan `momo_3d_rig.json` di atas, lalu pasang animasi Idle, PetReaction, dan Evolusi yang sudah ada di paket Rive v3 sebagai acuan timing

## Soal .glb langsung dari sini, jujur

Di mesin ini tidak ada engine Image-to-3D Tripo / Meshy / Rodin yang terhubung, dan tidak ada Blender. Kalau aku memaksakan membuat `.glb` dari kode primitif bola dan kapsul, hasilnya tidak akan sebagus gambar acuan ini, dan itu justru merusak paket final yang kamu minta harus bagus.

Jadi `.glb` Tripo-quality tidak aku palsukan di paket ini. Yang aku siapkan adalah bahan yang benar-benar siap upload: 3 foto depan penuh resolusi tinggi plus rig yang sinkron.

Kalau kamu mau `.glb` langsung dari aku, jalurnya adalah: sambungkan akun Tripo / Meshy lewat API key di Secure Vault, atau kirim file `.glb` hasil download dari Tripo / Meshy ke sini, lalu aku yang rig dan verifikasi animasinya di paket final.
