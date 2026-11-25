# Panduan Aset Sketsa Manual (MVP)

Dokumen ini adalah *checklist* lengkap untuk menyiapkan sketsa manualmu agar saat dikonversi oleh `convert.py` hasilnya tajam, konsisten, dan animasinya terasa hidup di terminal.

---

## 1. Spesifikasi Teknis Kanvas (Wajib Konsisten)

| Parameter | Rekomendasi | Alasan |
| :--- | :--- | :--- |
| **Format File** | **PNG** (`.png`) | Tanpa artefak kompresi seperti JPG/GIF, garis tetap tajam. |
| **Ukuran Kanvas** | **512 × 512 px** (rasio `1:1`) | Semua frame **wajib** memakai ukuran dan posisi karakter yang sama persis agar tidak "melompat" saat berganti state. |
| **Gaya Gambar** | **Hitam pekat di atas latar putih polos** (atau latar transparan) | Seperti gaya tinta/manga (*bold ink line art* + blok bayangan solid). Hindari gradasi pensil tipis atau kertas bertekstur. |
| **Ketebalan Garis** | Agak tebal (**6–10 px** pada kanvas 512×512) | Saat diperkecil ke lebar 30 karakter Braille (`60 × 60` titik), garis tipis (<3 px) akan putus-putus atau hilang. |
| **Framing** | **Bust-up / Head & Shoulders** (kepala + bahu, mengisi ~80% tinggi kanvas) | Wajah, mata, alis, mulut, dan gestur tangan dekat dagu/bahu akan jauh lebih terbaca dibanding *full-body*. |

> **Tips Menggambar Cepat:** Buat 1 layer dasar (**Base Head & Shoulders**) di aplikasi gambar favoritmu (atau pakai kertas tracing / *onion skin*), lalu duplikat untuk menggambar variasi mata, mulut, tangan, dan simbol efek di atasnya. Hasil animasinya akan jauh lebih mulus!

---

## 2. Daftar Pose & Frame yang Perlu Disiapkan (Total: 11–13 PNG)

Taruh hasil gambarmu ke dalam folder `assets/raw/<state>/` sesuai struktur berikut:

### A. `assets/raw/idle/` — Mode Santai / Menunggu Prompt *(3 frame)*
| Nama File | Pose / Ekspresi | Durasi Default | Catatan Visual |
| :--- | :--- | :---: | :--- |
| `01_open.png` | Wajah netral/rileks, mata terbuka penuh | `2800 ms` | Pose standar utama karaktermu. |
| `02_blink.png` | Sama persis dengan `01`, mata tertutup (berkedip) | `160 ms` | Cukup ubah bagian mata jadi garis melengkung/datar. |
| `03_breathe.png` | Sama dengan `01`, badan/bahu turun 4–8 px (efek bernapas) | `1400 ms` | Opsional, tapi bikin karakter terasa sangat hidup! |

### B. `assets/raw/thinking/` — Mode Memikirkan Prompt *(2–3 frame)*
| Nama File | Pose / Ekspresi | Durasi Default | Catatan Visual |
| :--- | :--- | :---: | :--- |
| `01_think_a.png` | Mata melirik ke atas/samping, alis sedikit berkerut, tangan di dagu (opsional) | `450 ms` | Bisa tambah 1 titik pikiran kecil di sudut kanan atas. |
| `02_think_b.png` | Pose sama, tambah 2 titik pikiran / kepala sedikit miring | `450 ms` | Gerakan pelan memberi kesan sedang mencerna masalah. |
| `03_think_c.png` | Pose sama, tambah tanda `?` atau 3 titik pikiran penuh | `450 ms` | Opsional (2 frame sudah cukup untuk MVP). |

### C. `assets/raw/coding/` — Mode Mengeksekusi Tugas / Tool *(2–3 frame)*
| Nama File | Pose / Ekspresi | Durasi Default | Catatan Visual |
| :--- | :--- | :---: | :--- |
| `01_code_a.png` | Mata fokus/serius ke depan, posisi mengetik/bekerja kiri | `220 ms` | Boleh tambahkan aksen kacamata atau kilau mata fokus. |
| `02_code_b.png` | Mata fokus (sedikit geser melirik layar), posisi tangan/aksi kanan | `220 ms` | Pergantian cepat (`~220 ms`) bikin terasa sibuk mengetik. |
| `03_code_c.png` | Variasi ritme tangan/garis efek kecepatan (opsional) | `220 ms` | Opsional agar loop tidak terlalu kaku. |

### D. `assets/raw/error/` — Mode Kena Error / Gagal *(2 frame)*
| Nama File | Pose / Ekspresi | Durasi Default | Catatan Visual |
| :--- | :--- | :---: | :--- |
| `01_err_a.png` | Ekspresi kaget / panik / mata silang (`X X`) atau berkeringat, sedikit geser kiri | `200 ms` | Tambah simbol `!` atau tetesan keringat besar agar langsung terbaca. |
| `02_err_b.png` | Sama dengan `01`, sedikit geser kanan (efek bergetar) + efek tegang | `200 ms` | Otomatis kembali ke `idle` setelah 6 detik. |

### E. `assets/raw/done/` — Mode Tugas Selesai *(2 frame)*
| Nama File | Pose / Ekspresi | Durasi Default | Catatan Visual |
| :--- | :--- | :---: | :--- |
| `01_done_a.png` | Senyum puas / mata senang (`^ ^`), kilau/bintang di posisi A | `350 ms` | Boleh tambah pose jempol atau *peace sign* dekat pipi. |
| `02_done_b.png` | Senyum sama, badan sedikit terangkat + kilau berpindah ke posisi B | `350 ms` | Otomatis kembali ke `idle` setelah 4.5 detik. |

---

## 3. Mengatur Durasi Frame Sendiri (`timing.json`)

Jika kamu ingin durasi khusus untuk frame tertentu, buat file `timing.json` di dalam folder state-nya (contoh: `assets/raw/idle/timing.json`):

```json
{
  "01_open.png": 3200,
  "02_blink.png": 140,
  "03_breathe.png": 1600
}
```

---

## 4. Alur Tes & Konversi Sketsa

1. Pasang Pillow (cukup sekali):
   ```powershell
   pip install -r requirements.txt
   ```
2. **Preview 1 sketsa dulu** untuk mencari `--width` dan `--threshold` paling pas:
   ```powershell
   python convert.py --preview assets/raw/idle/01_open.png --width 30 --threshold 140
   ```
   * Jika garis terlihat terlalu tipis/hilang → **naikkan** `--threshold` (mis. `170` atau `190`).
   * Jika gambar terlalu hitam/penuh → **turunkan** `--threshold` (mis. `100` atau `115`).
   * Jika sketsamu punya arsiran/gradasi abu-abu → coba tambah flag `--dither`.
3. **Konversi semua state** sekaligus:
   ```powershell
   python convert.py --all --width 30 --threshold 140
   ```
4. **Cek hasilnya langsung di Companion:**
   ```powershell
   python companion.py --demo
   ```
   Tekan tombol **`1`–`5`** untuk melihat semua state (`idle`, `thinking`, `coding`, `error`, `done`) dan **`q`** untuk keluar!
