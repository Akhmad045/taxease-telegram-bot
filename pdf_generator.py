"""Generator PDF bukti perhitungan pajak TaxEase.

Modul ini membuat file PDF sementara di folder ``tmp/`` lalu mengembalikan
path-nya. Pemanggil bertanggung jawab menghapus file setelah dikirim ke user.
"""

import os
from datetime import datetime

from fpdf import FPDF

# Lokasi folder penyimpanan PDF sementara.
TMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")


def _rupiah(nilai):
    """Format angka ke format rupiah."""
    return "Rp " + f"{nilai:,.0f}".replace(",", ".")


class PDFPajak(FPDF):
    """Subclass FPDF dengan header dan footer khas TaxEase."""

    def __init__(self, jenis_pajak="Pajak"):
        super().__init__()
        self.jenis_pajak = jenis_pajak

    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(20, 60, 130)
        self.cell(0, 9, "BUKTI PERHITUNGAN PAJAK - TaxEase", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(90, 90, 90)
        self.cell(
            0,
            6,
            f"Tanggal: {datetime.now():%d %B %Y}   |   Jenis: {self.jenis_pajak}",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_text_color(0, 0, 0)
        self.ln(3)
        # Garis pemisah.
        self.set_draw_color(20, 60, 130)
        self.set_line_width(0.6)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(
            0,
            10,
            f"Dibuat otomatis oleh TaxEase Bot - {datetime.now():%d/%m/%Y %H:%M}",
            align="C",
        )


def _tulis_tabel(pdf, baris):
    """Menulis tabel rincian dengan dua kolom (label & nilai)."""
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(230, 238, 250)
    pdf.cell(95, 8, "Komponen", border=1, fill=True)
    pdf.cell(0, 8, "Nilai", border=1, fill=True, align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    for label, nilai in baris:
        pdf.cell(95, 8, label, border=1)
        pdf.cell(0, 8, nilai, border=1, align="R", new_x="LMARGIN", new_y="NEXT")


def _baris_pph21_bulanan(data):
    baris = []
    if data.get("nama"):
        baris.append(("Nama Karyawan", str(data["nama"])))
    if data.get("nik"):
        baris.append(("NIK", str(data["nik"])))
    if data.get("status_pegawai"):
        baris.append(("Status Pegawai", str(data["status_pegawai"])))
    baris += [
        ("Gaji Pokok", _rupiah(data.get("gaji_pokok", data.get("gaji", 0)))),
        ("Tunjangan Tetap", _rupiah(data.get("tunjangan", 0))),
        ("Tunjangan Tidak Tetap", _rupiah(data.get("tunjangan_tidak_tetap", 0))),
        ("Bruto Bulanan", _rupiah(data.get("bruto_bulanan", 0))),
        ("BPJS", _rupiah(data.get("bpjs", 0))),
        ("JHT", _rupiah(data.get("jht", 0))),
        ("Neto Bulanan", _rupiah(data.get("neto_bulanan", 0))),
        ("Neto Setahun", _rupiah(data.get("neto_setahun", 0))),
        (f"PTKP ({data.get('ptkp', '-')})", _rupiah(data.get("nilai_ptkp", 0))),
        ("PKP Setahun", _rupiah(data.get("pkp", 0))),
        ("PPh 21 Setahun", _rupiah(data.get("pph_setahun", 0))),
        ("PPh 21 Sebulan", _rupiah(data.get("pph_bulanan", 0))),
        ("Take Home Pay (THP)", _rupiah(data.get("thp", 0))),
    ]
    return baris


def _baris_pph21_tahunan(data):
    baris = []
    if data.get("nama"):
        baris.append(("Nama Pegawai", str(data["nama"])))
    if data.get("npwp"):
        baris.append(("NPWP", str(data["npwp"])))
    baris += [
        ("Bruto Setahun", _rupiah(data.get("bruto_setahun", 0))),
        ("THR Setahun", _rupiah(data.get("thr_setahun", 0))),
        ("Bonus Setahun", _rupiah(data.get("bonus_setahun", 0))),
        ("Bruto Total", _rupiah(data.get("bruto_total", data.get("bruto_setahun", 0)))),
        ("Biaya Jabatan", _rupiah(data.get("biaya_jabatan", 0))),
        ("BPJS Setahun", _rupiah(data.get("bpjs_setahun", 0))),
        ("JHT Setahun", _rupiah(data.get("jht_setahun", 0))),
        ("JKK Setahun", _rupiah(data.get("jkk_setahun", 0))),
        ("JKM Setahun", _rupiah(data.get("jkm_setahun", 0))),
        ("Total Pengurang", _rupiah(data.get("total_pengurang", 0))),
        ("Neto Setahun", _rupiah(data.get("neto_setahun", 0))),
        (f"PTKP ({data.get('ptkp', '-')})", _rupiah(data.get("nilai_ptkp", 0))),
        ("PKP Setahun", _rupiah(data.get("pkp", 0))),
        ("PPh Terutang Setahun", _rupiah(data.get("pph_terutang", 0))),
        ("PPh Sudah Dipotong", _rupiah(data.get("pph_dipotong_setahun", 0))),
        ("Status", data.get("status_selisih", "-")),
        ("PPh 29 (Kurang Bayar)", _rupiah(data.get("pph_29", 0))),
        ("PPh 28A (Lebih Bayar)", _rupiah(data.get("pph_28a", 0))),
    ]
    return baris


def _baris_pph_badan(data):
    baris = []
    if data.get("nama"):
        baris.append(("Nama Wajib Pajak", str(data["nama"])))
    if data.get("npwp"):
        baris.append(("NPWP", str(data["npwp"])))
    baris += [
        ("Peredaran Bruto Usaha", _rupiah(data.get("omzet", 0))),
        ("Peredaran Bruto Lainnya", _rupiah(data.get("peredaran_lainnya", 0))),
        ("Total Peredaran Bruto", _rupiah(data.get("total_bruto", data.get("omzet", 0)))),
        ("Biaya", _rupiah(data.get("biaya", 0))),
        ("Laba", _rupiah(data.get("laba", 0))),
        ("Skema", str(data.get("skema", "-"))),
    ]
    if data.get("pkp_fasilitas"):
        baris += [
            ("PKP Fasilitas", _rupiah(data.get("pkp_fasilitas", 0))),
            ("PPh Fasilitas (11%)", _rupiah(data.get("fasilitas", 0))),
            ("PPh Non-Fasilitas (22%)", _rupiah(data.get("non_fasilitas", 0))),
        ]
    baris += [
        ("PPh Terutang", _rupiah(data.get("pph_terutang", 0))),
        ("Kredit PPh 25", _rupiah(data.get("kredit_pph25", 0))),
        ("Kredit PPh 22/23", _rupiah(data.get("kredit_pph22_23", 0))),
        ("Total Kredit Pajak", _rupiah(data.get("total_kredit", 0))),
        ("PPh 29 (Kurang/Lebih Bayar)", _rupiah(data.get("pph_29", 0))),
    ]
    return baris


_JENIS_MAP = {
    "pph21_bulanan": ("PPh 21 Bulanan", _baris_pph21_bulanan),
    "pph21_tahunan": ("PPh 21 Tahunan", _baris_pph21_tahunan),
    "pph_badan": ("PPh Badan", _baris_pph_badan),
}


def buat_pdf_pajak(data: dict, jenis_pajak: str = "pph21_bulanan", user_id=None) -> str:
    """Membuat PDF bukti perhitungan pajak dan menyimpannya ke folder tmp/.

    Args:
        data: Dictionary hasil perhitungan pajak.
        jenis_pajak: Kunci jenis pajak ("pph21_bulanan", "pph21_tahunan", "pph_badan").
        user_id: ID user untuk nama file. Default "umum" bila tidak diberikan.

    Returns:
        Path absolut file PDF yang telah dibuat.
    """
    jenis = str(jenis_pajak).strip().lower()
    if jenis not in _JENIS_MAP:
        raise ValueError(
            "Jenis pajak tidak dikenal. Gunakan salah satu: "
            + ", ".join(_JENIS_MAP.keys())
        )

    judul, pembuat_baris = _JENIS_MAP[jenis]

    pdf = PDFPajak(jenis_pajak=judul)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Rincian Perhitungan", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    _tulis_tabel(pdf, pembuat_baris(data))

    os.makedirs(TMP_DIR, exist_ok=True)
    sel = user_id if user_id is not None else "umum"
    path = os.path.join(TMP_DIR, f"hasil_pajak_{sel}.pdf")
    pdf.output(path)
    return path