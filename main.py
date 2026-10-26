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
    BUL_GAJI,
    BUL_TUNJANGAN,
    BUL_BPJS,
    BUL_JHT,
    BUL_PTKP,
    TAH_BRUTO,
    TAH_BPJS,
    TAH_JHT,
    TAH_PPH_DIPOTONG,
    TAH_PTKP,
    BADAN_OMZET,
    BADAN_BIAYA,
    BADAN_KREDIT,
) = range(13)

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
    "• PPh 21 Bulanan — Gaji → Tunjangan → BPJS → JHT → PTKP\n"
    "• PPh 21 Tahunan — Bruto → BPJS → JHT → PPh Dipotong → PTKP\n"
    "• PPh Badan — Omzet → Biaya → Kredit PPh 25\n\n"
    f"*Status PTKP:* {PTKP_LIST}\n\n"
    "*Perintah lain:*\n"
    "/start — menu utama\n"
    "/help — bantuan ini\n"
    "/id — lihat ID Telegram Anda\n"
    "/cancel — batalkan pengisian yang sedang berjalan"
)

# Field wajib untuk validasi tombol PTKP pada state tertentu.
_PTKP_STATE = {
    BUL_PTKP: 'bulanan',
    TAH_PTKP: 'tahunan',
}


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


async def _tanya(update, teks, keyboard=None):
    """Mengirim pertanyaan wizard ke pesan yang sedang aktif."""
    await update.effective_message.reply_text(
        teks, parse_mode='Markdown', reply_markup=keyboard,
    )


async def _tolak_input(update, state):
    """Memberi tahu input tidak valid lalu mengulang state saat ini."""
    await update.effective_message.reply_text(
        "⚠️ *Input tidak valid. Masukkan hanya angka.*\n"
        "Ketik /cancel untuk membatalkan.",
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


async def _ingatkan_klik_ptkp(update, state):
    """Dipakai saat user mengetik teks pada state PTKP, bukan mengklik tombol."""
    await update.effective_message.reply_text(
        "⚠️ Silakan klik salah satu tombol Status PTKP yang tersedia di atas.",
        parse_mode='Markdown',
        reply_markup=PTKP_KEYBOARD,
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
    for key in ('gaji', 'tunjangan', 'bpjs', 'jht', 'bruto',
                'pph_dipotong', 'omzet', 'biaya', 'kredit_pph25', 'ptkp'):
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
    for key in ('gaji', 'tunjangan', 'bpjs', 'jht', 'bruto',
                'pph_dipotong', 'omzet', 'biaya', 'kredit_pph25', 'ptkp'):
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
            "*PPh 21 Bulanan — Langkah 1/5*\n\n"
            "Masukkan Gaji Pokok (hanya angka):"
        ),
        parse_mode='Markdown',
    )
    return BUL_GAJI


async def bul_gaji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'gaji', BUL_GAJI,
        "*PPh 21 Bulanan — Langkah 2/5*\n\nMasukkan Tunjangan Tetap:",
    )


async def bul_tunjangan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'tunjangan', BUL_TUNJANGAN,
        "*PPh 21 Bulanan — Langkah 3/5*\n\nMasukkan Iuran BPJS:",
    )


async def bul_bpjs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'bpjs', BUL_BPJS,
        "*PPh 21 Bulanan — Langkah 4/5*\n\nMasukkan Iuran JHT:",
    )


async def bul_jht(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'jht', BUL_JHT,
        "*PPh 21 Bulanan — Langkah 5/5*\n\nPilih Status PTKP:",
        keyboard=PTKP_KEYBOARD,
    )


async def bul_ptkp_teks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _ingatkan_klik_ptkp(update, BUL_PTKP)


async def bul_proses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dipicu setelah tombol PTKP dipilih; menghitung dan mengirim hasil."""
    query = update.callback_query
    await query.answer()

    ptkp = query.data.replace('ptkp_', '', 1)
    gaji = context.user_data.get('gaji', 0)
    tunjangan = context.user_data.get('tunjangan', 0)
    bpjs = context.user_data.get('bpjs', 0)
    jht = context.user_data.get('jht', 0)

    try:
        hasil = hitung_pph21_bulanan(gaji, tunjangan, bpjs, jht, ptkp)
    except ValueError as e:
        await query.message.reply_text(f"⚠️ {e}\n\nKetik /cancel untuk membatalkan.")
        return BUL_PTKP

    teks_hasil = (
        "*📊 Hasil Perhitungan PPh 21 Bulanan*\n"
        "──────────────────────────\n"
        f"*Gaji Pokok:* {_rupiah(gaji)}\n"
        f"*Tunjangan:* {_rupiah(tunjangan)}\n"
        f"*Bruto Bulanan:* {_rupiah(hasil['bruto_bulanan'])}\n"
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
            "*PPh 21 Tahunan — Langkah 1/5*\n\n"
            "Masukkan Total Bruto Setahun (hanya angka):"
        ),
        parse_mode='Markdown',
    )
    return TAH_BRUTO


async def tah_bruto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'bruto', TAH_BRUTO,
        "*PPh 21 Tahunan — Langkah 2/5*\n\nMasukkan Total BPJS Setahun:",
    )


async def tah_bpjs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'bpjs', TAH_BPJS,
        "*PPh 21 Tahunan — Langkah 3/5*\n\nMasukkan Total JHT Setahun:",
    )


async def tah_jht(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'jht', TAH_JHT,
        "*PPh 21 Tahunan — Langkah 4/5*\n\n"
        "Masukkan Total PPh 21 Dipotong Setahun:",
    )


async def tah_pph_dipotong(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'pph_dipotong', TAH_PPH_DIPOTONG,
        "*PPh 21 Tahunan — Langkah 5/5*\n\nPilih Status PTKP:",
        keyboard=PTKP_KEYBOARD,
    )


async def tah_ptkp_teks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _ingatkan_klik_ptkp(update, TAH_PTKP)


async def tah_proses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dipicu setelah tombol PTKP dipilih; menghitung dan mengirim hasil."""
    query = update.callback_query
    await query.answer()

    ptkp = query.data.replace('ptkp_', '', 1)
    bruto = context.user_data.get('bruto', 0)
    bpjs = context.user_data.get('bpjs', 0)
    jht = context.user_data.get('jht', 0)
    pph_dipotong = context.user_data.get('pph_dipotong', 0)

    try:
        hasil = hitung_pph21_tahunan(bruto, bpjs, jht, pph_dipotong, ptkp)
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
        f"*Bruto Setahun:* {_rupiah(hasil['bruto_setahun'])}\n"
        f"*Biaya Jabatan:* {_rupiah(hasil['biaya_jabatan'])}\n"
        f"*BPJS Setahun:* {_rupiah(hasil['bpjs_setahun'])}\n"
        f"*JHT Setahun:* {_rupiah(hasil['jht_setahun'])}\n"
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
            "*PPh Badan — Langkah 1/3*\n\n"
            "Masukkan Peredaran Bruto / Omzet (hanya angka):"
        ),
        parse_mode='Markdown',
    )
    return BADAN_OMZET


async def badan_omzet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'omzet', BADAN_OMZET,
        "*PPh Badan — Langkah 2/3*\n\nMasukkan Biaya / Beban Usaha:",
    )


async def badan_biaya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _simpan_angka(
        update, context, 'biaya', BADAN_BIAYA,
        "*PPh Badan — Langkah 3/3*\n\n"
        "Masukkan Kredit Pajak PPh 25 (jika tidak ada, ketik 0):",
    )


async def badan_kredit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        kredit_pph25 = _parse_angka(update.message.text)
    except ValueError:
        return await _tolak_input(update, BADAN_KREDIT)

    context.user_data['kredit_pph25'] = kredit_pph25
    omzet = context.user_data.get('omzet', 0)
    biaya = context.user_data.get('biaya', 0)
    hasil = hitung_pph_badan(omzet, biaya, kredit_pph25)

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
        f"*Omzet:* {_rupiah(hasil['omzet'])}\n"
        f"*Biaya:* {_rupiah(hasil['biaya'])}\n"
        f"*Laba:* {_rupiah(hasil['laba'])}\n"
        f"*Skema:* {hasil['skema']}\n"
        "──────────────────────────\n"
        f"{baris_fasilitas}"
        f"*PPh Terutang:* {_rupiah(hasil['pph_terutang'])}\n"
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
            BUL_GAJI: [MessageHandler(filters.TEXT & ~filters.COMMAND, bul_gaji)],
            BUL_TUNJANGAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, bul_tunjangan)],
            BUL_BPJS: [MessageHandler(filters.TEXT & ~filters.COMMAND, bul_bpjs)],
            BUL_JHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bul_jht)],
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
            TAH_BRUTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, tah_bruto)],
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
            BADAN_OMZET: [MessageHandler(filters.TEXT & ~filters.COMMAND, badan_omzet)],
            BADAN_BIAYA: [MessageHandler(filters.TEXT & ~filters.COMMAND, badan_biaya)],
            BADAN_KREDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, badan_kredit)],
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