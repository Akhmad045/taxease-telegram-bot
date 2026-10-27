import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from pajak import hitung_pph21_bulanan, hitung_pph21_tahunan, hitung_pph_badan
from pdf_generator import buat_pdf_pajak

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# ---------------------------------------------------------------- State Wizard
(
    BUL_NAMA,
    BUL_NIK,
    BUL_GAJI,
    BUL_TUNJANGAN,
    BUL_TUNJANGAN_TIDAK_TETAP,
    BUL_BPJS,
    BUL_JHT,
    BUL_STATUS_PEGAWAI,
    BUL_PTKP,
    TAH_NAMA,
    TAH_NPWP,
    TAH_BRUTO,
    TAH_JKK,
    TAH_JKM,
    TAH_THR,
    TAH_BONUS,
    TAH_BPJS,
    TAH_JHT,
    TAH_PPH_DIPOTONG,
    TAH_PTKP,
    BADAN_NAMA,
    BADAN_NPWP,
    BADAN_OMZET,
    BADAN_PEREDARAN_LAINNYA,
    BADAN_BIAYA,
    BADAN_KREDIT_PPH25,
    BADAN_KREDIT_PPH22_23,
) = range(27)

PTKP_LIST = "TK/0, TK/1, TK/2, TK/3, K/0, K/1, K/2, K/3"

# Tombol PTKP dalam bentuk inline keyboard 2 kolom.
PTKP_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("TK/0", callback_data='ptkp_TK/0'),
        InlineKeyboardButton("TK/1", callback_data='ptkp_TK/1'),
    ],
    [
        InlineKeyboardButton("TK/2", callback_data='ptkp_TK/2'),
        InlineKeyboardButton("TK/3", callback_data='ptkp_TK/3'),
    ],
    [
        InlineKeyboardButton("K/0", callback_data='ptkp_K/0'),
        InlineKeyboardButton("K/1", callback_data='ptkp_K/1'),
    ],
    [
        InlineKeyboardButton("K/2", callback_data='ptkp_K/2'),
        InlineKeyboardButton("K/3", callback_data='ptkp_K/3'),
    ],
])

# Tombol Status Pegawai (PPh 21 Bulanan).
STATUS_PEGAWAI_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("Tetap", callback_data='pegawai_Tetap')],
    [InlineKeyboardButton("Tidak Tetap", callback_data='pegawai_Tidak Tetap')],
])

HASIL_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("Download PDF 📄", callback_data='download_pdf')],
    [InlineKeyboardButton("Kembali ke Menu 🏠", callback_data='menu_utama')],
])

MENU_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("Kembali ke Menu 🏠", callback_data='menu_utama')],
])

BANTUAN_TEKS = (
    "*📖 Bantuan TaxEase Bot*\n\n"
    "Ketik /start untuk memulai, pilih modul, lalu ikuti langkah pengisian data.\n"
    "Bot akan meminta data satu per satu.\n\n"
    "*Modul tersedia:*\n"
    "• PPh 21 Bulanan — Nama → NIK → Gaji → Tunjangan → Tunj. Tidak Tetap → "
    "BPJS → JHT → Status Pegawai → PTKP\n"
    "• PPh 21 Tahunan — Nama → NPWP → Bruto → JKK → JKM → THR → Bonus → "
    "BPJS → JHT → PPh Dipotong → PTKP\n"
    "• PPh Badan — Nama → NPWP → Omzet → Peredaran Lainnya → Biaya → "
    "Kredit PPh 25 → Kredit PPh 22/23\n\n"
    f"*Status PTKP:* {PTKP_LIST}\n"
    "*Status Pegawai:* Tetap / Tidak Tetap\n"
    "*NIK:* wajib 16 digit angka\n\n"
    "*Perintah lain:*\n"
    "/start — menu utama\n"
    "/help — bantuan ini\n"
    "/id — lihat ID Telegram Anda\n"
    "/cancel — batalkan pengisian yang sedang berjalan"
)

# Kunci data wizard untuk dibersihkan setelah hasil dikirim / dibatalkan.
_WIZARD_KEYS = (
    'nama', 'nik', 'npwp', 'gaji', 'tunjangan', 'tunjangan_tidak_tetap',
    'bpjs', 'jht', 'status_pegawai', 'bruto', 'jkk', 'jkm', 'thr', 'bonus',
    'pph_dipotong', 'omzet', 'peredaran_lainnya', 'biaya', 'kredit_pph25',
    'kredit_pph22_23', 'ptkp',
)


# ------------------------------------------------------------------- Utilities
def _rupiah(nilai):
    """Format angka ke format rupiah."""
    return f"Rp {nilai:,.0f}".replace(",", ".")


def _parse_angka(teks):
    """Parse string angka; raise ValueError bila bukan angka valid.

    Mendukung input seperti ``10000000``, ``10.000.000``, ``Rp 10.000.000``,
    dan ``10000000,50`` (koma sebagai desimal).
    """
    if teks is None:
        raise ValueError("kosong")
    bersih = str(teks).strip()
    bersih = bersih.replace("Rp", "").replace("rp", "").replace("RP", "").strip()
    bersih = bersih.replace(" ", "").replace("_", "").replace(".", "")
    bersih = bersih.replace(",", ".")
    if bersih == "":
        raise ValueError("kosong")
    # Tolak format seperti "1e5" atau teks lain yang tidak wajar.
    if any(c not in "0123456789.-" for c in bersih):
        raise ValueError(f"bukan angka: {teks}")
    nilai = float(bersih)
    if nilai < 0:
        raise ValueError("negatif")
    return nilai


def _parse_nik(teks):
    """Validasi NIK: harus tepat 16 digit angka. Raise ValueError bila tidak."""
    bersih = str(teks or "").strip().replace(" ", "").replace(".", "").replace("-", "")
    if bersih == "":
        raise ValueError("kosong")
    if not bersih.isdigit():
        raise ValueError(f"bukan angka: {teks}")
    if len(bersih) != 16:
        raise ValueError(f"NIK harus 16 digit, Anda memasukkan {len(bersih)} digit")
    return bersih


async def _tanya(update, teks, keyboard=None):
    """Mengirim pertanyaan wizard ke pesan yang sedang aktif."""
    await update.effective_message.reply_text(
        teks, parse_mode='Markdown', reply_markup=keyboard,
    )


async def _tolak_input(update, state, pesan=None):
    """Memberi tahu input tidak valid lalu mengulang state saat ini."""
    await update.effective_message.reply_text(
        pesan or (
            "⚠️ *Input tidak valid. Masukkan hanya angka.*\n"
            "Ketik /cancel untuk membatalkan."
        ),
        parse_mode='Markdown',
    )
    return state


async def _simpan_angka(update, context, key, state, pertanyaan_berikut, keyboard=None):
    """Validasi angka, simpan ke user_data, lanjut atau ulangi state."""
    try:
        nilai = _parse_angka(update.message.text)
    except ValueError:
        return await _tolak_input(update, state)

    context.user_data[key] = nilai
    await _tanya(update, pertanyaan_berikut, keyboard=keyboard)
    return state + 1


async def _simpan_teks(update, context, key, state, pertanyaan_berikut, keyboard=None):
    """Simpan input teks bebas (mis. nama) lalu lanjut ke state berikutnya."""
    nilai = str(update.message.text or "").strip()
    if nilai == "":
        return await _tolak_input(
            update, state,
            "⚠️ *Input tidak boleh kosong.*\nCoba lagi atau ketik /cancel untuk membatalkan.",
        )
    context.user_data[key] = nilai
    await _tanya(update, pertanyaan_berikut, keyboard=keyboard)
    return state + 1


async def _simpan_nik(update, context, state, pertanyaan_berikut, keyboard=None):
    """Validasi NIK 16 digit, simpan, lalu lanjut atau ulangi state."""
    try:
        nik = _parse_nik(update.message.text)
    except ValueError as e:
        return await _tolak_input(
            update, state,
            "⚠️ *NIK tidak valid.*\n"
            f"{e}.\n"
            "Masukkan NIK tepat 16 digit angka.\n"
            "Ketik /cancel untuk membatalkan.",
        )
    context.user_data['nik'] = nik
    await _tanya(update, pertanyaan_berikut, keyboard=keyboard)
    return state + 1


async def _ingatkan_klik_ptkp(update, state):
    """Dipakai saat user mengetik teks pada state PTKP, bukan mengklik tombol."""
    await update.effective_message.reply_text(
        "⚠️ Silakan klik salah satu tombol Status PTKP yang tersedia di atas.",
        parse_mode='Markdown',
        reply_markup=PTKP_KEYBOARD,
    )
    return state


async def _ingatkan_klik_status(update, state):
    """Dipakai saat user mengetik teks pada state Status Pegawai."""
    await update.effective_message.reply_text(
        "⚠️ Silakan klik salah satu tombol Status Pegawai yang tersedia di atas.",
        parse_mode='Markdown',
        reply_markup=STATUS_PEGAWAI_KEYBOARD,
    )
    return state


async def _tampilkan_menu(target, edit=False):
    """Menampilkan menu utama, baik via pesan baru maupun edit pesan."""
    keyboard = [
        [InlineKeyboardButton("PPh 21 Bulanan", callback_data='pph21_bulanan')],
        [InlineKeyboardButton("PPh 21 Tahunan", callback_data='pph21_tahunan')],
        [InlineKeyboardButton("PPh Badan", callback_data='pph_badan')],
        [InlineKeyboardButton("Riwayat", callback_data='riwayat')],
        [InlineKeyboardButton("Bantuan", callback_data='bantuan')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    teks = "Selamat datang di *TaxEase Bot*!\nSilakan pilih modul perhitungan:"
    if edit:
        await target.edit_message_text(
            text=teks, reply_markup=reply_markup, parse_mode='Markdown',
        )
    else:
        await target.reply_text(
            text=teks, reply_markup=reply_markup, parse_mode='Markdown',
        )


async def _kirim_hasil(update, context, jenis, hasil, teks_hasil):
    """Menyimpan hasil terakhir dan mengirim pesan hasil + tombol aksi."""
    context.user_data['last_result'] = {'jenis': jenis, 'hasil': hasil}
    await update.effective_message.reply_text(
        teks_hasil,
        parse_mode='Markdown',
        reply_markup=HASIL_KEYBOARD,
    )
    # Bersihkan data wizard yang sudah tidak dipakai.
    for key in _WIZARD_KEYS:
        context.user_data.pop(key, None)
    return ConversationHandler.END


# ------------------------------------------------------------- Perintah Global
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _tampilkan_menu(update.effective_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(BANTUAN_TEKS, parse_mode='Markdown')


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = f"@{user.username}" if user.username else "(belum diatur)"
    await update.message.reply_text(
        "*🆔 Informasi Akun*\n"
        f"*ID Telegram:* `{user.id}`\n"
        f"*Username:* {username}",
        parse_mode='Markdown',
    )


async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menangani pesan yang tidak dikenali saat tidak ada percakapan aktif."""
    await update.effective_message.reply_text(
        "Maaf, saya tidak mengerti. Ketik /start untuk melihat menu utama."
    )


# ---------------------------------------------------------- Callback & Bantuan
async def kirim_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Membuat dan mengirim PDF hasil perhitungan terakhir milik user."""
    query = update.callback_query
    await query.answer()

    last = context.user_data.get('last_result')
    if not last:
        await query.message.reply_text(
            "⚠️ Data tidak ditemukan. Silakan hitung ulang terlebih dahulu lewat /start."
        )
        return

    jenis = last['jenis']
    hasil = last['hasil']

    try:
        pdf_path = buat_pdf_pajak(hasil, jenis, user_id=query.from_user.id)
    except Exception as e:  # noqa: BLE001
        await query.message.reply_text(f"⚠️ Gagal membuat PDF: {e}")
        return

    nama_file = "Bukti_Potong_TaxEase.pdf"
    try:
        with open(pdf_path, 'rb') as dokumen:
            await query.message.reply_document(
                document=dokumen,
                filename=nama_file,
                caption="📄 Bukti perhitungan pajak Anda (PDF).",
            )
    finally:
        # Hapus file sementara agar tidak menumpuk di server.
        try:
            os.remove(pdf_path)
        except OSError:
            pass


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'menu_utama':
        try:
            await _tampilkan_menu(query, edit=True)
        except Exception:  # noqa: BLE001 - pesan lama tanpa teks/konten
            await _tampilkan_menu(query.message)
    elif query.data == 'riwayat':
        await query.edit_message_text(
            text="Anda memilih *Riwayat*. (Fitur ini akan diimplementasikan di Fase 4)",
            parse_mode='Markdown',
            reply_markup=MENU_KEYBOARD,
        )
    elif query.data == 'bantuan':
        await query.edit_message_text(
            text=BANTUAN_TEKS,
            parse_mode='Markdown',
            reply_markup=MENU_KEYBOARD,
        )
    elif query.data == 'download_pdf':
        await kirim_pdf(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mengakhiri wizard kapan saja dan mengembalikan ke menu awal."""
    context.user_data.pop('last_result', None)
    for key in _WIZARD_KEYS:
        context.user_data.pop(key, None)

    await update.effective_message.reply_text(
        "❌ Pengisian dibatalkan.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await _tampilkan_menu(update.effective_message)
    return ConversationHandler.END


# =========================================== WIZARD 1: PPh 21 Bulanan
async def pph21_bulanan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text=(
            "*PPh 21 Bulanan — Langkah 1/9*\n\n"
            "Masukkan Nama Karyawan:"
        ),
        parse_mode='Markdown',
    )
    return BUL_NAMA


async def bul_nama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_teks(
        update, context, 'nama', BUL_NAMA,
        "*PPh 21 Bulanan — Langkah 2/9*\n\n"
        "Masukkan NIK (16 digit angka):",
    )


async def bul_nik(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_nik(
        update, context, BUL_NIK,
        "*PPh 21 Bulanan — Langkah 3/9*\n\nMasukkan Gaji Pokok:",
    )


async def bul_gaji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'gaji', BUL_GAJI,
        "*PPh 21 Bulanan — Langkah 4/9*\n\nMasukkan Tunjangan Tetap:",
    )


async def bul_tunjangan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'tunjangan', BUL_TUNJANGAN,
        "*PPh 21 Bulanan — Langkah 5/9*\n\nMasukkan Tunjangan Tidak Tetap:",
    )


async def bul_tunjangan_tidak_tetap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'tunjangan_tidak_tetap', BUL_TUNJANGAN_TIDAK_TETAP,
        "*PPh 21 Bulanan — Langkah 6/9*\n\nMasukkan Iuran BPJS:",
    )


async def bul_bpjs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'bpjs', BUL_BPJS,
        "*PPh 21 Bulanan — Langkah 7/9*\n\nMasukkan Iuran JHT:",
    )


async def bul_jht(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'jht', BUL_JHT,
        "*PPh 21 Bulanan — Langkah 8/9*\n\nPilih Status Pegawai:",
        keyboard=STATUS_PEGAWAI_KEYBOARD,
    )


async def bul_status_pegawai_teks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _ingatkan_klik_status(update, BUL_STATUS_PEGAWAI)


async def bul_status_pegawai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dipicu saat tombol Status Pegawai diklik; lanjut ke pertanyaan PTKP."""
    query = update.callback_query
    await query.answer()

    status_pegawai = query.data.replace('pegawai_', '', 1)
    context.user_data['status_pegawai'] = status_pegawai

    await query.edit_message_text(
        text=(
            f"Status Pegawai: *{status_pegawai}*\n\n"
            "*PPh 21 Bulanan — Langkah 9/9*\n\nPilih Status PTKP:"
        ),
        parse_mode='Markdown',
        reply_markup=PTKP_KEYBOARD,
    )
    return BUL_PTKP


async def bul_ptkp_teks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _ingatkan_klik_ptkp(update, BUL_PTKP)


async def bul_proses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dipicu setelah tombol PTKP dipilih; menghitung dan mengirim hasil."""
    query = update.callback_query
    await query.answer()

    ptkp = query.data.replace('ptkp_', '', 1)
    d = context.user_data
    nama = d.get('nama')
    nik = d.get('nik')
    status_pegawai = d.get('status_pegawai')
    gaji = d.get('gaji', 0)
    tunjangan = d.get('tunjangan', 0)
    tunjangan_tidak_tetap = d.get('tunjangan_tidak_tetap', 0)
    bpjs = d.get('bpjs', 0)
    jht = d.get('jht', 0)

    try:
        hasil = hitung_pph21_bulanan(
            gaji, tunjangan, bpjs, jht, ptkp,
            tunjangan_tidak_tetap=tunjangan_tidak_tetap,
            nama=nama, nik=nik, status_pegawai=status_pegawai,
        )
    except ValueError as e:
        await query.message.reply_text(f"⚠️ {e}\n\nKetik /cancel untuk membatalkan.")
        return BUL_PTKP

    teks_hasil = (
        "*📊 Hasil Perhitungan PPh 21 Bulanan*\n"
        "──────────────────────────\n"
        f"*Nama Karyawan:* {nama}\n"
        f"*NIK:* {nik}\n"
        f"*Status Pegawai:* {status_pegawai}\n"
        "──────────────────────────\n"
        f"*Gaji Pokok:* {_rupiah(gaji)}\n"
        f"*Tunjangan Tetap:* {_rupiah(tunjangan)}\n"
        f"*Tunjangan Tidak Tetap:* {_rupiah(tunjangan_tidak_tetap)}\n"
        f"*Bruto Bulanan:* {_rupiah(hasil['bruto_bulanan'])}\n"
        f"*BPJS:* {_rupiah(bpjs)}\n"
        f"*JHT:* {_rupiah(jht)}\n"
        f"*Neto Bulanan:* {_rupiah(hasil['neto_bulanan'])}\n"
        f"*Neto Setahun:* {_rupiah(hasil['neto_setahun'])}\n"
        f"*PTKP ({hasil['ptkp']}):* {_rupiah(hasil['nilai_ptkp'])}\n"
        f"*PKP Setahun:* {_rupiah(hasil['pkp'])}\n"
        "──────────────────────────\n"
        f"*PPh 21 Setahun:* {_rupiah(hasil['pph_setahun'])}\n"
        f"*PPh 21 Bulanan:* {_rupiah(hasil['pph_bulanan'])}\n"
        "──────────────────────────\n"
        f"*Take Home Pay:* {_rupiah(hasil['thp'])}"
    )
    await query.edit_message_text(text=teks_hasil, parse_mode='Markdown')
    return await _kirim_hasil(update, context, 'pph21_bulanan', hasil, teks_hasil)


# =========================================== WIZARD 2: PPh 21 Tahunan
async def pph21_tahunan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text=(
            "*PPh 21 Tahunan — Langkah 1/10*\n\n"
            "Masukkan Nama Pegawai:"
        ),
        parse_mode='Markdown',
    )
    return TAH_NAMA


async def tah_nama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_teks(
        update, context, 'nama', TAH_NAMA,
        "*PPh 21 Tahunan — Langkah 2/10*\n\nMasukkan NPWP:",
    )


async def tah_npwp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_teks(
        update, context, 'npwp', TAH_NPWP,
        "*PPh 21 Tahunan — Langkah 3/10*\n\nMasukkan Total Bruto Setahun:",
    )


async def tah_bruto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'bruto', TAH_BRUTO,
        "*PPh 21 Tahunan — Langkah 4/10*\n\nMasukkan Total JKK Setahun:",
    )


async def tah_jkk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'jkk', TAH_JKK,
        "*PPh 21 Tahunan — Langkah 5/10*\n\nMasukkan Total JKM Setahun:",
    )


async def tah_jkm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'jkm', TAH_JKM,
        "*PPh 21 Tahunan — Langkah 6/10*\n\nMasukkan Total THR Setahun:",
    )


async def tah_thr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'thr', TAH_THR,
        "*PPh 21 Tahunan — Langkah 7/10*\n\nMasukkan Total Bonus Setahun:",
    )


async def tah_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'bonus', TAH_BONUS,
        "*PPh 21 Tahunan — Langkah 8/10*\n\nMasukkan Total BPJS Setahun:",
    )


async def tah_bpjs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'bpjs', TAH_BPJS,
        "*PPh 21 Tahunan — Langkah 9/10*\n\nMasukkan Total JHT Setahun:",
    )


async def tah_jht(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'jht', TAH_JHT,
        "*PPh 21 Tahunan — Langkah 10/10*\n\n"
        "Masukkan Total PPh 21 Dipotong Setahun:",
    )


async def tah_pph_dipotong(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'pph_dipotong', TAH_PPH_DIPOTONG,
        "*PPh 21 Tahunan*\n\nPilih Status PTKP:",
        keyboard=PTKP_KEYBOARD,
    )


async def tah_ptkp_teks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _ingatkan_klik_ptkp(update, TAH_PTKP)


async def tah_proses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dipicu setelah tombol PTKP dipilih; menghitung dan mengirim hasil."""
    query = update.callback_query
    await query.answer()

    ptkp = query.data.replace('ptkp_', '', 1)
    d = context.user_data
    nama = d.get('nama')
    npwp = d.get('npwp')
    bruto = d.get('bruto', 0)
    jkk = d.get('jkk', 0)
    jkm = d.get('jkm', 0)
    thr = d.get('thr', 0)
    bonus = d.get('bonus', 0)
    bpjs = d.get('bpjs', 0)
    jht = d.get('jht', 0)
    pph_dipotong = d.get('pph_dipotong', 0)

    try:
        hasil = hitung_pph21_tahunan(
            bruto, bpjs, jht, pph_dipotong, ptkp,
            jkk_setahun=jkk, jkm_setahun=jkm,
            thr_setahun=thr, bonus_setahun=bonus,
            nama=nama, npwp=npwp,
        )
    except ValueError as e:
        await query.message.reply_text(f"⚠️ {e}\n\nKetik /cancel untuk membatalkan.")
        return TAH_PTKP

    if hasil['selisih'] > 0:
        baris_status = f"*PPh 29 (Kurang Bayar):* {_rupiah(hasil['pph_29'])}\n"
    elif hasil['selisih'] < 0:
        baris_status = f"*PPh 28A (Lebih Bayar):* {_rupiah(hasil['pph_28a'])}\n"
    else:
        baris_status = "*Status:* Nihil (Tidak Kurang/Lebih Bayar)\n"

    teks_hasil = (
        "*📊 Hasil Perhitungan PPh 21 Tahunan*\n"
        "──────────────────────────\n"
        f"*Nama Pegawai:* {nama}\n"
        f"*NPWP:* {npwp}\n"
        "──────────────────────────\n"
        f"*Bruto Setahun:* {_rupiah(bruto)}\n"
        f"*THR Setahun:* {_rupiah(thr)}\n"
        f"*Bonus Setahun:* {_rupiah(bonus)}\n"
        f"*Bruto Total:* {_rupiah(hasil['bruto_total'])}\n"
        f"*Biaya Jabatan:* {_rupiah(hasil['biaya_jabatan'])}\n"
        f"*BPJS Setahun:* {_rupiah(bpjs)}\n"
        f"*JHT Setahun:* {_rupiah(jht)}\n"
        f"*JKK Setahun:* {_rupiah(jkk)}\n"
        f"*JKM Setahun:* {_rupiah(jkm)}\n"
        f"*Total Pengurang:* {_rupiah(hasil['total_pengurang'])}\n"
        f"*Neto Setahun:* {_rupiah(hasil['neto_setahun'])}\n"
        f"*PTKP ({hasil['ptkp']}):* {_rupiah(hasil['nilai_ptkp'])}\n"
        f"*PKP Setahun:* {_rupiah(hasil['pkp'])}\n"
        "──────────────────────────\n"
        f"*PPh Terutang:* {_rupiah(hasil['pph_terutang'])}\n"
        f"*PPh Sudah Dipotong:* {_rupiah(hasil['pph_dipotong_setahun'])}\n"
        "──────────────────────────\n"
        f"{baris_status}"
    )
    await query.edit_message_text(text=teks_hasil, parse_mode='Markdown')
    return await _kirim_hasil(update, context, 'pph21_tahunan', hasil, teks_hasil)


# =========================================== WIZARD 3: PPh Badan
async def pph_badan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text=(
            "*PPh Badan — Langkah 1/7*\n\n"
            "Masukkan Nama Wajib Pajak:"
        ),
        parse_mode='Markdown',
    )
    return BADAN_NAMA


async def badan_nama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_teks(
        update, context, 'nama', BADAN_NAMA,
        "*PPh Badan — Langkah 2/7*\n\nMasukkan NPWP Badan:",
    )


async def badan_npwp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_teks(
        update, context, 'npwp', BADAN_NPWP,
        "*PPh Badan — Langkah 3/7*\n\nMasukkan Peredaran Bruto Usaha (Omzet):",
    )


async def badan_omzet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'omzet', BADAN_OMZET,
        "*PPh Badan — Langkah 4/7*\n\nMasukkan Peredaran Bruto Lainnya:",
    )


async def badan_peredaran_lainnya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'peredaran_lainnya', BADAN_PEREDARAN_LAINNYA,
        "*PPh Badan — Langkah 5/7*\n\nMasukkan Biaya / Beban Usaha:",
    )


async def badan_biaya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'biaya', BADAN_BIAYA,
        "*PPh Badan — Langkah 6/7*\n\nMasukkan Kredit Pajak PPh 25:",
    )


async def badan_kredit_pph25(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'kredit_pph25', BADAN_KREDIT_PPH25,
        "*PPh Badan — Langkah 7/7*\n\nMasukkan Kredit Pajak PPh 22/23:",
    )


async def badan_kredit_pph22_23(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        kredit_pph22_23 = _parse_angka(update.message.text)
    except ValueError:
        return await _tolak_input(update, BADAN_KREDIT_PPH22_23)

    context.user_data['kredit_pph22_23'] = kredit_pph22_23
    d = context.user_data
    nama = d.get('nama')
    npwp = d.get('npwp')
    omzet = d.get('omzet', 0)
    peredaran_lainnya = d.get('peredaran_lainnya', 0)
    biaya = d.get('biaya', 0)
    kredit_pph25 = d.get('kredit_pph25', 0)

    hasil = hitung_pph_badan(
        omzet, biaya, kredit_pph25, kredit_pph22_23,
        peredaran_lainnya=peredaran_lainnya, nama=nama, npwp=npwp,
    )

    baris_fasilitas = ""
    if hasil["pkp_fasilitas"]:
        baris_fasilitas = (
            f"*PKP Fasilitas:* {_rupiah(hasil['pkp_fasilitas'])}\n"
            f"*PPh Fasilitas (11%):* {_rupiah(hasil['fasilitas'])}\n"
            f"*PPh Non-Fasilitas (22%):* {_rupiah(hasil['non_fasilitas'])}\n"
        )

    teks_hasil = (
        "*📊 Hasil Perhitungan PPh Badan*\n"
        "──────────────────────────\n"
        f"*Nama Wajib Pajak:* {nama}\n"
        f"*NPWP:* {npwp}\n"
        "──────────────────────────\n"
        f"*Peredaran Bruto Usaha:* {_rupiah(omzet)}\n"
        f"*Peredaran Bruto Lainnya:* {_rupiah(peredaran_lainnya)}\n"
        f"*Total Peredaran Bruto:* {_rupiah(hasil['total_bruto'])}\n"
        f"*Biaya:* {_rupiah(hasil['biaya'])}\n"
        f"*Laba:* {_rupiah(hasil['laba'])}\n"
        f"*Skema:* {hasil['skema']}\n"
        "──────────────────────────\n"
        f"{baris_fasilitas}"
        f"*PPh Terutang:* {_rupiah(hasil['pph_terutang'])}\n"
        f"*Kredit PPh 25:* {_rupiah(kredit_pph25)}\n"
        f"*Kredit PPh 22/23:* {_rupiah(kredit_pph22_23)}\n"
        f"*Total Kredit Pajak:* {_rupiah(hasil['total_kredit'])}\n"
        "──────────────────────────\n"
        f"*PPh 29 (Kurang/Lebih Bayar):* {_rupiah(hasil['pph_29'])}"
    )
    return await _kirim_hasil(update, context, 'pph_badan', hasil, teks_hasil)


# ------------------------------------------------------------------ Bootstrap
async def _error_handler(update, context):
    """Menangani exception tak terduga agar bot tidak berhenti."""
    print(f"[ERROR] {context.error!r}")


def main():
    app = Application.builder().token(TOKEN).build()

    # ------------------------------------------------ Wizard PPh 21 Bulanan
    conv_bulanan = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pph21_bulanan_start, pattern='^pph21_bulanan$'),
        ],
        states={
            BUL_NAMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, bul_nama)],
            BUL_NIK: [MessageHandler(filters.TEXT & ~filters.COMMAND, bul_nik)],
            BUL_GAJI: [MessageHandler(filters.TEXT & ~filters.COMMAND, bul_gaji)],
            BUL_TUNJANGAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, bul_tunjangan)],
            BUL_TUNJANGAN_TIDAK_TETAP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bul_tunjangan_tidak_tetap)
            ],
            BUL_BPJS: [MessageHandler(filters.TEXT & ~filters.COMMAND, bul_bpjs)],
            BUL_JHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bul_jht)],
            BUL_STATUS_PEGAWAI: [
                CallbackQueryHandler(bul_status_pegawai, pattern='^pegawai_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, bul_status_pegawai_teks),
            ],
            BUL_PTKP: [
                CallbackQueryHandler(bul_proses, pattern='^ptkp_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, bul_ptkp_teks),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
        ],
        allow_reentry=True,
    )

    # ------------------------------------------------ Wizard PPh 21 Tahunan
    conv_tahunan = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pph21_tahunan_start, pattern='^pph21_tahunan$'),
        ],
        states={
            TAH_NAMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, tah_nama)],
            TAH_NPWP: [MessageHandler(filters.TEXT & ~filters.COMMAND, tah_npwp)],
            TAH_BRUTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, tah_bruto)],
            TAH_JKK: [MessageHandler(filters.TEXT & ~filters.COMMAND, tah_jkk)],
            TAH_JKM: [MessageHandler(filters.TEXT & ~filters.COMMAND, tah_jkm)],
            TAH_THR: [MessageHandler(filters.TEXT & ~filters.COMMAND, tah_thr)],
            TAH_BONUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, tah_bonus)],
            TAH_BPJS: [MessageHandler(filters.TEXT & ~filters.COMMAND, tah_bpjs)],
            TAH_JHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, tah_jht)],
            TAH_PPH_DIPOTONG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, tah_pph_dipotong)
            ],
            TAH_PTKP: [
                CallbackQueryHandler(tah_proses, pattern='^ptkp_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, tah_ptkp_teks),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
        ],
        allow_reentry=True,
    )

    # --------------------------------------------------- Wizard PPh Badan
    conv_badan = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pph_badan_start, pattern='^pph_badan$'),
        ],
        states={
            BADAN_NAMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, badan_nama)],
            BADAN_NPWP: [MessageHandler(filters.TEXT & ~filters.COMMAND, badan_npwp)],
            BADAN_OMZET: [MessageHandler(filters.TEXT & ~filters.COMMAND, badan_omzet)],
            BADAN_PEREDARAN_LAINNYA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, badan_peredaran_lainnya)
            ],
            BADAN_BIAYA: [MessageHandler(filters.TEXT & ~filters.COMMAND, badan_biaya)],
            BADAN_KREDIT_PPH25: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, badan_kredit_pph25)
            ],
            BADAN_KREDIT_PPH22_23: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, badan_kredit_pph22_23)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
        ],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(conv_bulanan)
    app.add_handler(conv_tahunan)
    app.add_handler(conv_badan)
    app.add_handler(CallbackQueryHandler(button_handler))
    # Fallback terakhir: semua pesan lain (teks ngawur, stiker, gambar, dll).
    app.add_handler(MessageHandler(filters.ALL, fallback_handler))
    app.add_error_handler(_error_handler)

    print("Bot TaxEase sedang berjalan...")
    app.run_polling()


if __name__ == '__main__':
    main()