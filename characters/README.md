# Character / Skin Packs (`agy-companion`)

Kamu bisa membuat banyak karakter atau kepribadian berbeda di dalam folder `characters/` tanpa mengubah aset default.

## Struktur Folder

```text
characters/
  my-char/
    character.json   # (opsional) metadata nama, tema default, & timer ngantuk
    dialogue.json    # (opsional) kepribadian & dialog khusus karakter ini
    raw/             # (opsional) sketsa PNG per state untuk dikonversi via convert.py
      idle/
      thinking/
      coding/
      reading/       # opsional (animasi granular, fallback ke coding)
      editing/       # opsional (fallback ke coding)
      running/       # opsional (fallback ke coding)
      searching/     # opsional (fallback ke coding)
      sleepy/        # opsional (fallback ke idle)
      error/
      done/
    frames/          # hasil konversi JSON (fallback ke assets/frames/ jika state belum ada)
```

## Contoh `character.json`

```json
{
  "name": "Neko Dev",
  "theme": "amber",
  "sleepy_after_sec": 240
}
```

Tema bawaan yang tersedia: `mono`, `amber`, `green`, `cyan`, `pastel`.

## Cara Konversi & Menjalankan

1. Konversi sketsa PNG milik karakter ini:
   ```powershell
   python convert.py --character my-char --all --width 45 --threshold 140
   ```
2. Jalankan companion dengan karakter tersebut:
   ```powershell
   python companion.py --demo --character my-char
   ```
3. Di dalam companion yang sedang berjalan, tekan **`c`** untuk gonta-ganti karakter dan **`t`** untuk gonta-ganti tema warna secara langsung!
