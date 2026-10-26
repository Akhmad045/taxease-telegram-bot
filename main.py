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

# State percakapan
PILIH_PPH21, PILIH_PPH21_TAHUNAN, PILIH_PPH_BADAN = range(3)

PTKP_LIST = "TK/0, TK/1, TK/2, TK/3, K/0, K/1, K/2, K/3"


def _rupiah(nilai):
    """Format angka ke format rupiah."""
    return f"Rp {nilai:,.0f}".replace(",", ".")


def _parse_angka(teks):
    """Parse string angka yang mungkin mengandung titik/koma ribuan."""
    bersih = teks.strip().replace("Rp", "").replace("rp", "").replace(" ", "")
    # Hapus pemisah ribuan berupa titik.
    bersih = bersih.replace(".", "").replace("_", "")
    bersih = bersih.replace(",", ".")
    return float(bersih)


BANTUAN_TEKS = (
    "*📖 Bantuan TaxEase Bot*\n\n"
    "Ketik /start untuk memulai, pilih modul, lalu masukkan data sesuai format.\n\n"
    "*Modul tersedia:*\n"
    "• PPh 21 Bulanan — `Gaji, Tunjangan, BPJS, JHT, PTKP`\n"
    "• PPh 21 Tahunan — `Bruto, BPJS, JHT, PPh Dipotong, PTKP`\n"
    "• PPh Badan — `Omzet, Biaya, Kredit PPh 25`\n\n"
    f"*Status PTKP:* {PTKP_LIST}\n\n"
    "*Perintah lain:*\n"
    "/start — menu utama\n"
    "/help — bantuan ini\n"
    "/id — lihat ID Telegram Anda\n"
    "/cancel — batalkan input yang sedang berjalan"
)

MENU_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("Kembali ke Menu 🏠", callback_data='menu_utama')],
])


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
        await target.edit_message_text(text=teks, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await target.reply_text(text=teks, reply_markup=reply_markup, parse_mode='Markdown')


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _tampilkan_menu(update.message)


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


# ---------------------------------------------------------------- PPh 21 Bulanan
async def pph21_bulanan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text=(
            "*PPh 21 Bulanan*\n\n"
            "Masukkan Gaji, Tunjangan, BPJS, JHT, PTKP (pisahkan dengan koma).\n"
            f"Contoh: `10000000, 2000000, 100000, 200000, K/1`\n\n"
            f"Status PTKP tersedia: {PTKP_LIST}\n"
            "Ketik /cancel untuk membatalkan."
        ),
        parse_mode='Markdown',
    )
    return PILIH_PPH21


async def pph21_bulanan_hitung(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teks = update.message.text
    bagian = [b.strip() for b in teks.split(",")]

    if len(bagian) < 5:
        await update.message.reply_text(
            "⚠️ Format salah. Mohon masukkan *5 nilai* dipisahkan koma:\n"
            "`Gaji, Tunjangan, BPJS, JHT, PTKP`\n"
            "Contoh: `10000000, 2000000, 100000, 200000, K/1`\n\n"
            "Coba lagi atau ketik /cancel untuk membatalkan.",
            parse_mode='Markdown',
        )
        return PILIH_PPH21

    try:
        gaji = _parse_angka(bagian[0])
        tunjangan = _parse_angka(bagian[1])
        bpjs = _parse_angka(bagian[2])
        jht = _parse_angka(bagian[3])
        ptkp = bagian[4]
    except ValueError:
        await update.message.reply_text(
            "⚠️ Gaji/Tunjangan/BPJS/JHT harus berupa angka.\n"
            "Contoh: `10000000, 2000000, 100000, 200000, K/1`\n\n"
            "Coba lagi atau ketik /cancel untuk membatalkan.",
            parse_mode='Markdown',
        )
        return PILIH_PPH21

    try:
        hasil = hitung_pph21_bulanan(gaji, tunjangan, bpjs, jht, ptkp)
    except ValueError as e:
        await update.message.reply_text(
            f"⚠️ {e}\n\nCoba lagi atau ketik /cancel untuk membatalkan.",
        )
        return PILIH_PPH21

    teks_hasil = (
        "*📊 Hasil Perhitungan PPh 21 Bulanan*\n"
        "──────────────────────────\n"
        f"*Bruto Bulanan:* {_rupiah(hasil['bruto_bulanan'])}\n"
        f"*Neto Bulanan:* {_rupiah(hasil['neto_bulanan'])}\n"
        f"*Neto Setahun:* {_rupiah(hasil['neto_setahun'])}\n"
        f"*PTKP ({hasil['ptkp']}):* {_rupiah(hasil['nilai_ptkp'])}\n"
        f"*PKP Setahun:* {_rupiah(hasil['pkp'])}\n"
        "──────────────────────────\n"
        f"*PPh 21 Setahun:* {_rupiah(hasil['pph_setahun'])}\n"
        f"*PPh 21 Bulanan:* {_rupiah(hasil['pph_bulanan'])}\n"
        "──────────────────────────\n"
        f"*Take Home Pay:* {_rupiah(hasil['thp'])}\n\n"
        "Ketik /start untuk kembali ke menu utama."
    )
    context.user_data['last_result'] = {'jenis': 'pph21_bulanan', 'hasil': hasil}
    keyboard = [
        [InlineKeyboardButton("Download PDF 📄", callback_data='download_pdf')],
        [InlineKeyboardButton("Kembali ke Menu 🏠", callback_data='menu_utama')],
    ]
    await update.message.reply_text(
        teks_hasil,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ConversationHandler.END


# --------------------------------------------------------------- PPh 21 Tahunan
async def pph21_tahunan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text=(
            "*PPh 21 Tahunan*\n\n"
            "Masukkan Bruto Setahun, BPJS Setahun, JHT Setahun, PPh Dipotong, PTKP "
            "(pisahkan dengan koma).\n"
            "Contoh: `120000000, 1200000, 2400000, 5000000, K/1`\n\n"
            f"Status PTKP tersedia: {PTKP_LIST}\n"
            "Ketik /cancel untuk membatalkan."
        ),
        parse_mode='Markdown',
    )
    return PILIH_PPH21_TAHUNAN


async def pph21_tahunan_hitung(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teks = update.message.text
    bagian = [b.strip() for b in teks.split(",")]

    if len(bagian) < 5:
        await update.message.reply_text(
            "⚠️ Format salah. Mohon masukkan *5 nilai* dipisahkan koma:\n"
            "`Bruto Setahun, BPJS Setahun, JHT Setahun, PPh Dipotong, PTKP`\n"
            "Contoh: `120000000, 1200000, 2400000, 5000000, K/1`\n\n"
            "Coba lagi atau ketik /cancel untuk membatalkan.",
            parse_mode='Markdown',
        )
        return PILIH_PPH21_TAHUNAN

    try:
        bruto = _parse_angka(bagian[0])
        bpjs = _parse_angka(bagian[1])
        jht = _parse_angka(bagian[2])
        pph_dipotong = _parse_angka(bagian[3])
        ptkp = bagian[4]
    except ValueError:
        await update.message.reply_text(
            "⚠️ Bruto/BPJS/JHT/PPh Dipotong harus berupa angka.\n"
            "Contoh: `120000000, 1200000, 2400000, 5000000, K/1`\n\n"
            "Coba lagi atau ketik /cancel untuk membatalkan.",
            parse_mode='Markdown',
        )
        return PILIH_PPH21_TAHUNAN

    try:
        hasil = hitung_pph21_tahunan(bruto, bpjs, jht, pph_dipotong, ptkp)
    except ValueError as e:
        await update.message.reply_text(
            f"⚠️ {e}\n\nCoba lagi atau ketik /cancel untuk membatalkan.",
        )
        return PILIH_PPH21_TAHUNAN

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
        f"{baris_status}\n"
        "Ketik /start untuk kembali ke menu utama."
    )
    context.user_data['last_result'] = {'jenis': 'pph21_tahunan', 'hasil': hasil}
    keyboard = [
        [InlineKeyboardButton("Download PDF 📄", callback_data='download_pdf')],
        [InlineKeyboardButton("Kembali ke Menu 🏠", callback_data='menu_utama')],
    ]
    await update.message.reply_text(
        teks_hasil,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ConversationHandler.END


# ------------------------------------------------------------------ PPh Badan
async def pph_badan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text=(
            "*PPh Badan*\n\n"
            "Masukkan Omzet, Biaya, Kredit PPh 25 (pisahkan dengan koma).\n"
            "Contoh: `5000000000, 4000000000, 10000000`\n\n"
            "Jika tidak ada kredit PPh 25, cukup tulis 0.\n"
            "Ketik /cancel untuk membatalkan."
        ),
        parse_mode='Markdown',
    )
    return PILIH_PPH_BADAN


async def pph_badan_hitung(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teks = update.message.text
    bagian = [b.strip() for b in teks.split(",")]

    if len(bagian) not in (2, 3):
        await update.message.reply_text(
            "⚠️ Format salah. Mohon masukkan *2 atau 3 nilai* dipisahkan koma:\n"
            "`Omzet, Biaya, Kredit PPh 25`\n"
            "Contoh: `5000000000, 4000000000, 10000000`\n\n"
            "Coba lagi atau ketik /cancel untuk membatalkan.",
            parse_mode='Markdown',
        )
        return PILIH_PPH_BADAN

    try:
        omzet = _parse_angka(bagian[0])
        biaya = _parse_angka(bagian[1])
        kredit_pph25 = _parse_angka(bagian[2]) if len(bagian) == 3 else 0
    except ValueError:
        await update.message.reply_text(
            "⚠️ Omzet, Biaya, dan Kredit PPh 25 harus berupa angka.\n"
            "Contoh: `5000000000, 4000000000, 10000000`\n\n"
            "Coba lagi atau ketik /cancel untuk membatalkan.",
            parse_mode='Markdown',
        )
        return PILIH_PPH_BADAN

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
        f"*PPh 29 (Kurang/Lebih Bayar):* {_rupiah(hasil['pph_29'])}\n\n"
        "Ketik /start untuk kembali ke menu utama."
    )
    context.user_data['last_result'] = {'jenis': 'pph_badan', 'hasil': hasil}
    keyboard = [
        [InlineKeyboardButton("Download PDF 📄", callback_data='download_pdf')],
        [InlineKeyboardButton("Kembali ke Menu 🏠", callback_data='menu_utama')],
    ]
    await update.message.reply_text(
        teks_hasil,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Perhitungan dibatalkan. Ketik /start untuk kembali ke menu utama.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


def _error_handler(update, context):
    """Menangani exception tak terduga agar bot tidak berhenti."""
    print(f"[ERROR] {context.error!r}")


def main():
    app = Application.builder().token(TOKEN).build()

    conv_pph21 = ConversationHandler(
        entry_points=[CallbackQueryHandler(pph21_bulanan_start, pattern='^pph21_bulanan$')],
        states={
            PILIH_PPH21: [MessageHandler(filters.TEXT & ~filters.COMMAND, pph21_bulanan_hitung)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
        ],
        allow_reentry=True,
    )

    conv_pph_badan = ConversationHandler(
        entry_points=[CallbackQueryHandler(pph_badan_start, pattern='^pph_badan$')],
        states={
            PILIH_PPH_BADAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, pph_badan_hitung)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
        ],
        allow_reentry=True,
    )

    conv_pph21_tahunan = ConversationHandler(
        entry_points=[CallbackQueryHandler(pph21_tahunan_start, pattern='^pph21_tahunan$')],
        states={
            PILIH_PPH21_TAHUNAN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, pph21_tahunan_hitung)
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
    app.add_handler(conv_pph21)
    app.add_handler(conv_pph21_tahunan)
    app.add_handler(conv_pph_badan)
    app.add_handler(CallbackQueryHandler(button_handler))
    # Fallback terakhir: semua pesan lain (teks ngawur, stiker, gambar, dll).
    app.add_handler(MessageHandler(filters.ALL, fallback_handler))
    app.add_error_handler(_error_handler)

    print("Bot TaxEase sedang berjalan...")
    app.run_polling()


if __name__ == '__main__':
    main()