# TaxEase Telegram Bot

Bot Telegram untuk menghitung **PPh 21** (bulanan & tahunan) dan **PPh Badan**,
lengkap dengan ekspor bukti perhitungan ke PDF.

## Fitur

- **PPh 21 Bulanan** — bruto, neto, PKP, PPh setahun/bulanan, dan THP
- **PPh 21 Tahunan** — biaya jabatan (5%, maks Rp 6 jt), PKP, PPh terutang, status PPh 29/28A
- **PPh Badan** — tarif 11% / fasilitas Pasal 31E / tarif umum 22%, plus kredit pajak
- **Export PDF** — bukti perhitungan otomatis (fpdf2)
- **UI ramah** — menu inline, tombol "Kembali ke Menu", `/help`, `/id`, dan error handling

## Struktur File

| File | Keterangan |
|------|-----------|
| `main.py` | Handler bot, alur percakapan, menu |
| `pajak.py` | Logika perhitungan pajak |
| `pdf_generator.py` | Pembuat PDF bukti perhitungan (folder `tmp/`) |
| `requirements.txt` | Dependensi Python |
| `.env.example` | Template variabel environment |

## Instalasi

```bash
# 1. Buat virtual environment (opsional tapi disarankan)
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/macOS

# 2. Install dependensi
pip install -r requirements.txt

# 3. Salin template env dan isi token bot Anda
copy .env.example .env       # Windows
cp .env.example .env         # Linux/macOS
```

Isi `.env`:

```env
TELEGRAM_BOT_TOKEN=<token dari @BotFather>
```

## Menjalankan

```bash
python main.py
```

## Perintah Bot

| Perintah | Fungsi |
|----------|--------|
| `/start` | Menu utama |
| `/help` | Cara pakai |
| `/id` | Lihat ID Telegram Anda |
| `/cancel` | Batalkan input |

## Format Input

- **PPh 21 Bulanan** — `Gaji, Tunjangan, BPJS, JHT, PTKP` → `10000000, 2000000, 100000, 200000, K/1`
- **PPh 21 Tahunan** — `Bruto, BPJS, JHT, PPh Dipotong, PTKP` → `120000000, 1200000, 2400000, 5000000, K/1`
- **PPh Badan** — `Omzet, Biaya, Kredit PPh 25` → `5000000000, 4000000000, 10000000`

Status PTKP: `TK/0`, `TK/1`, `TK/2`, `TK/3`, `K/0`, `K/1`, `K/2`, `K/3`

## Catatan Keamanan

File `.env` berisi token rahasia dan **tidak** ikut ter-commit (sudah masuk `.gitignore`).