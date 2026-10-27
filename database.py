"""Penyimpanan riwayat perhitungan TaxEase (SQLite).

Database disimpan di file ``taxease.db`` di samping modul ini. Setiap baris
riwayat terikat pada satu ``user_id`` Telegram sehingga tiap user hanya
melihat riwayatnya sendiri.
"""

import json
import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "taxease.db")

JENIS_LABEL = {
    "pph21_bulanan": "PPh 21 Bulanan",
    "pph21_tahunan": "PPh 21 Tahunan",
    "pph_badan": "PPh Badan",
}


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Membuat tabel riwayat bila belum ada. Dipanggil saat startup bot."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS riwayat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                jenis TEXT NOT NULL,
                nama TEXT,
                keterangan TEXT,
                ringkasan TEXT,
                hasil_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_riwayat_user ON riwayat (user_id, id DESC)"
        )
        conn.commit()
    return DB_PATH


def simpan_riwayat(user_id, jenis, hasil, ringkasan="", nama=None, keterangan=None):
    """Menyimpan satu hasil perhitungan milik user.

    Args:
        user_id: ID Telegram user pemilik data.
        jenis: "pph21_bulanan" | "pph21_tahunan" | "pph_badan".
        hasil: Dictionary hasil perhitungan (disimpan lengkap sebagai JSON).
        ringkasan: Teks ringkas untuk ditampilkan di daftar riwayat.
        nama: Nama karyawan / wajib pajak.
        keterangan: Info tambahan (mis. PTKP, status pegawai).

    Returns:
        ID baris yang baru disimpan.
    """
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO riwayat
                (user_id, jenis, nama, keterangan, ringkasan, hasil_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(user_id),
                str(jenis),
                nama,
                keterangan,
                ringkasan,
                json.dumps(hasil, ensure_ascii=False, default=str),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
        return cur.lastrowid


def ambil_riwayat(user_id, limit=10):
    """Mengambil riwayat milik satu user saja, terbaru lebih dahulu."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, jenis, nama, keterangan, ringkasan, hasil_json, created_at
            FROM riwayat
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(user_id), int(limit)),
        ).fetchall()

    hasil = []
    for row in rows:
        try:
            parsed = json.loads(row["hasil_json"])
        except (ValueError, TypeError):
            parsed = {}
        hasil.append({
            "id": row["id"],
            "jenis": row["jenis"],
            "jenis_label": JENIS_LABEL.get(row["jenis"], row["jenis"]),
            "nama": row["nama"],
            "keterangan": row["keterangan"],
            "ringkasan": row["ringkasan"],
            "hasil": parsed,
            "created_at": row["created_at"],
        })
    return hasil


def ambil_satu(user_id, riwayat_id):
    """Mengambil satu baris riwayat milik user tertentu (untuk cetak PDF)."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, jenis, nama, keterangan, ringkasan, hasil_json, created_at
            FROM riwayat
            WHERE user_id = ? AND id = ?
            """,
            (int(user_id), int(riwayat_id)),
        ).fetchone()

    if row is None:
        return None
    try:
        parsed = json.loads(row["hasil_json"])
    except (ValueError, TypeError):
        parsed = {}
    return {
        "id": row["id"],
        "jenis": row["jenis"],
        "jenis_label": JENIS_LABEL.get(row["jenis"], row["jenis"]),
        "nama": row["nama"],
        "keterangan": row["keterangan"],
        "ringkasan": row["ringkasan"],
        "hasil": parsed,
        "created_at": row["created_at"],
    }


def hapus_riwayat(user_id):
    """Menghapus seluruh riwayat milik satu user."""
    with _connect() as conn:
        cur = conn.execute("DELETE FROM riwayat WHERE user_id = ?", (int(user_id),))
        conn.commit()
        return cur.rowcount