"""Modul perhitungan pajak TaxEase.

Berisi fungsi perhitungan PPh 21 (orang pribadi) dan PPh Badan.
Diterjemahkan dari project FastAPI sebelumnya.
"""

# Tarif progresif PPh 21 (Pasal 17 UU HPP) berdasarkan lapisan PKP.
LAPISAN_TARIF = [
    (60_000_000, 0.05),          # 0 - 60 juta
    (250_000_000, 0.15),         # > 60 juta - 250 juta
    (500_000_000, 0.25),         # > 250 juta - 500 juta
    (5_000_000_000, 0.30),       # > 500 juta - 5 miliar
    (float("inf"), 0.35),        # > 5 miliar
]

# PTKP (Penghasilan Tidak Kena Pajak) tahunan.
PTKP_MAP = {
    "TK/0": 54_000_000,
    "TK/1": 58_500_000,
    "TK/2": 63_000_000,
    "TK/3": 67_500_000,
    "K/0": 58_500_000,
    "K/1": 63_000_000,
    "K/2": 67_500_000,
    "K/3": 72_000_000,
}


def hitung_pph_setahun(pkp):
    """Menghitung PPh 21 setahun dengan tarif progresif."""
    pajak = 0.0
    batas_sebelumnya = 0
    for batas, tarif in LAPISAN_TARIF:
        if pkp > batas_sebelumnya:
            lapisan = min(pkp, batas) - batas_sebelumnya
            pajak += lapisan * tarif
            batas_sebelumnya = batas
        else:
            break
    return pajak


def hitung_pph21_bulanan(gaji, tunjangan, bpjs, jht, ptkp,
                         tunjangan_tidak_tetap=0, nama=None, nik=None,
                         status_pegawai=None):
    """Menghitung PPh 21 bulanan untuk pegawai.

    Args:
        gaji: Gaji pokok per bulan.
        tunjangan: Tunjangan tetap per bulan.
        bpjs: Potongan BPJS per bulan.
        jht: Potongan JHT per bulan.
        ptkp: Status PTKP (mis. "TK/0", "K/1").
        tunjangan_tidak_tetap: Tunjangan tidak tetap per bulan (masuk bruto).
        nama: Nama karyawan (opsional, untuk laporan).
        nik: NIK 16 digit (opsional, untuk laporan).
        status_pegawai: "Tetap" / "Tidak Tetap" (opsional, untuk laporan).

    Returns:
        dict berisi rincian perhitungan.
    """
    status = str(ptkp).strip().upper().replace(" ", "")
    if status not in PTKP_MAP:
        raise ValueError(
            "Status PTKP tidak dikenal. Gunakan salah satu: "
            + ", ".join(PTKP_MAP.keys())
        )

    nilai_ptkp = PTKP_MAP[status]

    bruto_bulanan = gaji + tunjangan + tunjangan_tidak_tetap
    # Biaya jabatan: 5% dari bruto, maksimal Rp 500.000/bulan
    # (setara batas Rp 6.000.000/tahun pada perhitungan tahunan).
    biaya_jabatan_bulanan = min(bruto_bulanan * BIAYA_JABATAN_PERSEN, 500_000)
    neto_bulanan = bruto_bulanan - biaya_jabatan_bulanan - bpjs - jht
    neto_setahun = neto_bulanan * 12

    pkp = neto_setahun - nilai_ptkp
    if pkp < 0:
        pkp = 0
    # Pembulatan ke bawah ribuan.
    pkp = int(pkp // 1000 * 1000)

    pph_setahun = hitung_pph_setahun(pkp)
    pph_bulanan = pph_setahun / 12
    # THP Kas: bruto − BPJS − JHT − PPh (biaya jabatan tidak mengurangi THP,
    # hanya mengurangi neto/PKP — konsisten dengan definisi THP di web TaxEase).
    thp = bruto_bulanan - bpjs - jht - pph_bulanan

    return {
        "nama": nama,
        "nik": nik,
        "status_pegawai": status_pegawai,
        "gaji_pokok": gaji,
        "tunjangan": tunjangan,
        "tunjangan_tidak_tetap": tunjangan_tidak_tetap,
        "bpjs": bpjs,
        "jht": jht,
        "bruto_bulanan": bruto_bulanan,
        "biaya_jabatan": biaya_jabatan_bulanan,
        "neto_bulanan": neto_bulanan,
        "neto_setahun": neto_setahun,
        "ptkp": status,
        "nilai_ptkp": nilai_ptkp,
        "pkp": pkp,
        "pph_setahun": pph_setahun,
        "pph_bulanan": pph_bulanan,
        "thp": thp,
    }


def hitung_pph_badan(omzet, biaya, kredit_pph25=0, kredit_pph22_23=0,
                     peredaran_lainnya=0, nama=None, npwp=None):
    """Menghitung PPh Badan.

    Args:
        omzet: Peredaran bruto usaha setahun.
        biaya: Biaya/biaya yang dapat dikurangkan setahun.
        kredit_pph25: Kredit pajak PPh Pasal 25.
        kredit_pph22_23: Kredit pajak PPh Pasal 22/23.
        peredaran_lainnya: Peredaran bruto lainnya (menambah total bruto).
        nama: Nama wajib pajak badan (opsional, untuk laporan).
        npwp: NPWP badan (opsional, untuk laporan).

    Returns:
        dict berisi rincian perhitungan.
    """
    # Peredaran bruto lainnya menambah total peredaran bruto.
    total_bruto = omzet + peredaran_lainnya
    laba = total_bruto - biaya

    fasilitas = 0.0
    non_fasilitas = 0.0
    pkp_fasilitas = 0.0
    skema = ""

    # Penggunaan tarif mengikuti total peredaran bruto.
    if total_bruto <= 4_800_000_000:
        pph_terutang = laba * 0.11
        skema = "PPh Final/UMKM 11% (Omzet <= 4,8M)"
    elif total_bruto <= 50_000_000_000:
        rasio = 4_800_000_000 / total_bruto
        pkp_fasilitas = rasio * laba
        laba_non_fasilitas = laba - pkp_fasilitas
        fasilitas = pkp_fasilitas * 0.11
        non_fasilitas = laba_non_fasilitas * 0.22
        pph_terutang = fasilitas + non_fasilitas
        skema = "Fasilitas Pasal 31E (4,8M < Omzet <= 50M)"
    else:
        pph_terutang = laba * 0.22
        skema = "Tarif umum 22% (Omzet > 50M)"

    total_kredit = kredit_pph25 + kredit_pph22_23
    pph_29 = pph_terutang - total_kredit

    return {
        "nama": nama,
        "npwp": npwp,
        "omzet": omzet,
        "peredaran_lainnya": peredaran_lainnya,
        "total_bruto": total_bruto,
        "biaya": biaya,
        "laba": laba,
        "skema": skema,
        "pkp_fasilitas": pkp_fasilitas,
        "fasilitas": fasilitas,
        "non_fasilitas": non_fasilitas,
        "pph_terutang": pph_terutang,
        "kredit_pph25": kredit_pph25,
        "kredit_pph22_23": kredit_pph22_23,
        "total_kredit": total_kredit,
        "pph_29": pph_29,
    }


# Batas maksimal biaya jabatan setahun.
BIAYA_JABATAN_PERSEN = 0.05
BIAYA_JABATAN_MAKS = 6_000_000


def hitung_pph21_tahunan(bruto_setahun, bpjs_setahun, jht_setahun, pph_dipotong_setahun, ptkp,
                         jkk_setahun=0, jkm_setahun=0, thr_setahun=0, bonus_setahun=0,
                         nama=None, npwp=None):
    """Menghitung PPh 21 Tahunan (SPT Tahunan Orang Pribadi).

    Args:
        bruto_setahun: Penghasilan bruto setahun.
        bpjs_setahun: Potongan BPJS setahun.
        jht_setahun: Potongan JHT setahun.
        pph_dipotong_setahun: PPh 21 yang sudah dipotong setahun.
        ptkp: Status PTKP (mis. "TK/0", "K/1").
        jkk_setahun: Iuran JKK setahun (pengurang).
        jkm_setahun: Iuran JKM setahun (pengurang).
        thr_setahun: Total THR setahun (menambah bruto).
        bonus_setahun: Total bonus setahun (menambah bruto).
        nama: Nama pegawai (opsional, untuk laporan).
        npwp: NPWP pegawai (opsional, untuk laporan).

    Returns:
        dict berisi rincian perhitungan.
    """
    status = str(ptkp).strip().upper().replace(" ", "")
    if status not in PTKP_MAP:
        raise ValueError(
            "Status PTKP tidak dikenal. Gunakan salah satu: "
            + ", ".join(PTKP_MAP.keys())
        )

    nilai_ptkp = PTKP_MAP[status]

    # THR dan bonus menambah penghasilan bruto.
    bruto_total = bruto_setahun + thr_setahun + bonus_setahun

    # Biaya jabatan: 5% dari bruto, maksimal Rp 6.000.000 setahun.
    biaya_jabatan = bruto_total * BIAYA_JABATAN_PERSEN
    if biaya_jabatan > BIAYA_JABATAN_MAKS:
        biaya_jabatan = BIAYA_JABATAN_MAKS

    # BPJS, JHT, JKK, dan JKM merupakan pengurang.
    total_pengurang = bpjs_setahun + jht_setahun + jkk_setahun + jkm_setahun
    neto_setahun = bruto_total - biaya_jabatan - total_pengurang

    pkp = neto_setahun - nilai_ptkp
    if pkp < 0:
        pkp = 0
    pkp = int(pkp // 1000 * 1000)

    pph_terutang = hitung_pph_setahun(pkp)

    # PPh 29 = kurang bayar (positif) / PPh 28A = lebih bayar (negatif).
    selisih = pph_terutang - pph_dipotong_setahun
    if selisih > 0:
        status_selisih = "PPh 29 (Kurang Bayar)"
        pph_29 = selisih
        pph_28a = 0.0
    elif selisih < 0:
        status_selisih = "PPh 28A (Lebih Bayar)"
        pph_29 = 0.0
        pph_28a = abs(selisih)
    else:
        status_selisih = "Nihil (Tidak Kurang/Lebih Bayar)"
        pph_29 = 0.0
        pph_28a = 0.0

    return {
        "nama": nama,
        "npwp": npwp,
        "bruto_setahun": bruto_setahun,
        "thr_setahun": thr_setahun,
        "bonus_setahun": bonus_setahun,
        "bruto_total": bruto_total,
        "biaya_jabatan": biaya_jabatan,
        "bpjs_setahun": bpjs_setahun,
        "jht_setahun": jht_setahun,
        "jkk_setahun": jkk_setahun,
        "jkm_setahun": jkm_setahun,
        "total_pengurang": total_pengurang,
        "neto_setahun": neto_setahun,
        "ptkp": status,
        "nilai_ptkp": nilai_ptkp,
        "pkp": pkp,
        "pph_terutang": pph_terutang,
        "pph_dipotong_setahun": pph_dipotong_setahun,
        "status_selisih": status_selisih,
        "selisih": selisih,
        "pph_29": pph_29,
        "pph_28a": pph_28a,
    }