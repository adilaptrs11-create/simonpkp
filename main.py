from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sqlite3, os, io
import pandas as pd
from datetime import date, timedelta

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

LIBUR_2026 = {
    "2026-01-01","2026-01-16","2026-02-16","2026-02-17",
    "2026-03-18","2026-03-19","2026-03-20","2026-03-21",
    "2026-03-22","2026-03-23","2026-03-24","2026-04-03",
    "2026-05-01","2026-05-14","2026-05-15","2026-05-27",
    "2026-05-28","2026-05-31","2026-06-01","2026-06-16",
    "2026-08-17","2026-08-25","2026-12-24","2026-12-25"
}

def is_hari_kerja(d: date) -> bool:
    return d.weekday() < 5 and d.strftime("%Y-%m-%d") not in LIBUR_2026

def tambah_hari_kerja(d: date, n: int) -> date:
    current = d
    count = 0
    while count < n:
        current += timedelta(days=1)
        if is_hari_kerja(current):
            count += 1
    return current

def sisa_hari_kerja(deadline: date) -> int:
    today = date.today()
    if deadline <= today:
        return 0
    count = 0
    current = today
    while current < deadline:
        current += timedelta(days=1)
        if is_hari_kerja(current):
            count += 1
    return count

DB = "pkp.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def tulis_log(conn, nomor_kasus: str, aksi: str, detail: str, dilakukan_oleh: str):
    from datetime import datetime
    conn.execute(
        "INSERT INTO log_aktivitas (nomor_kasus, aksi, detail, dilakukan_oleh, created_at) VALUES (?, ?, ?, ?, ?)",
        (nomor_kasus, aksi, detail, dilakukan_oleh, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            nama TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'PIC'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kasus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nomor_kasus TEXT UNIQUE NOT NULL,
            npwp TEXT,
            nama_wp TEXT NOT NULL,
            alamat TEXT,
            jenis_kasus TEXT,
            status_kasus TEXT DEFAULT 'Diproses',
            sumber_kasus TEXT,
            tgl_dibuat TEXT,
            dibuat_oleh TEXT,
            tgl_ditutup TEXT,
            langkah TEXT,
            tgl_jatuh_tempo TEXT,
            tgl_akhir TEXT,
            kantor_wilayah TEXT,
            kpp TEXT,
            pic TEXT,
            ar TEXT,
            tgl_permohonan TEXT,
            deadline_bpe TEXT,
            deadline_penelitian TEXT,
            deadline_ar TEXT,
            tgl_selesai TEXT,
            hasil TEXT,
            nomor_lap TEXT,
            tgl_visit TEXT,
            nama_ar_visit TEXT,
            nomor_nd TEXT,
            tgl_nd TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pegawai (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            tipe TEXT NOT NULL,
            email TEXT
        )
    """)
    # Add email column if not exists (for existing databases)
    try:
        conn.execute("ALTER TABLE pegawai ADD COLUMN email TEXT")
        conn.commit()
    except:
        pass
    # Add ND columns if not exists
    try:
        conn.execute("ALTER TABLE kasus ADD COLUMN nomor_nd TEXT")
        conn.commit()
    except:
        pass
    try:
        conn.execute("ALTER TABLE kasus ADD COLUMN tgl_nd TEXT")
        conn.commit()
    except:
        pass
    conn.executemany(
        "INSERT OR IGNORE INTO pegawai (nama, tipe) VALUES (?, ?)",
        [("PIC A","PIC"),("PIC B","PIC"),("PIC C","PIC"),("PIC D","PIC"),
         ("AR A","AR"),("AR B","AR"),("AR C","AR"),("AR D","AR"),
         ("AR E","AR"),("AR F","AR"),("AR G","AR"),("AR H","AR"),
         ("AR I","AR"),("AR J","AR")]
    )
    conn.executemany(
        "INSERT OR IGNORE INTO users (username, password, nama, role) VALUES (?, ?, ?, ?)",
        [("admin","admin123","Administrator","admin"),
         ("pic1","pic123","PIC A","PIC"),
         ("pic2","pic123","PIC B","PIC"),
         ("pic3","pic123","PIC C","PIC"),
         ("pic4","pic123","PIC D","PIC"),
         ("ar","ar123","AR","AR"),
         ("monitor","monitor123","Monitor","Monitor"),
         ("kasi_pelayanan","monitor123","Kasi Pelayanan","Monitor"),
         ("kasi_pengawasan_1","monitor123","Kasi Pengawasan 1","Monitor"),
         ("kasi_pengawasan_2","monitor123","Kasi Pengawasan 2","Monitor"),
         ("kasi_pengawasan_3","monitor123","Kasi Pengawasan 3","Monitor"),
         ("kasi_pengawasan_4","monitor123","Kasi Pengawasan 4","Monitor"),
         ("kasi_pengawasan_5","monitor123","Kasi Pengawasan 5","Monitor"),
         ("kasi_pengawasan_6","monitor123","Kasi Pengawasan 6","Monitor")]
    )
    conn.execute("DELETE FROM pegawai WHERE id NOT IN (SELECT MIN(id) FROM pegawai GROUP BY nama)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS log_aktivitas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nomor_kasus TEXT,
            aksi TEXT NOT NULL,
            detail TEXT,
            dilakukan_oleh TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

class KasusInput(BaseModel):
    nomor_kasus: str
    nama_wp: str
    npwp: Optional[str] = None
    alamat: Optional[str] = None
    tgl_permohonan: str
    pic: str
    ar: Optional[str] = None

class UpdateStatus(BaseModel):
    hasil: str
    tgl_selesai: str
    ar: Optional[str] = None
    nomor_lap: Optional[str] = None
    nomor_nd: Optional[str] = None
    tgl_nd: Optional[str] = None

class UpdateVisitAR(BaseModel):
    tgl_visit: str
    nama_ar_visit: str
    nomor_lap: Optional[str] = None

class AssignPegawai(BaseModel):
    pic: Optional[str] = None
    ar: Optional[str] = None

class LoginInput(BaseModel):
    username: str
    password: str

@app.get("/")
def root():
    return FileResponse("index.html")

@app.post("/api/login")
def login(data: LoginInput):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (data.username, data.password)
    ).fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=401, detail="Username atau password salah!")
    return {"message": "Login berhasil", "nama": user["nama"], "username": user["username"], "role": user["role"]}

@app.get("/api/pegawai")
def get_pegawai():
    conn = get_db()
    rows = conn.execute("SELECT * FROM pegawai ORDER BY tipe, nama").fetchall()
    conn.close()
    return [dict(r) for r in rows]

class PegawaiInput(BaseModel):
    nama: str
    tipe: str
    email: Optional[str] = None

class UserInput(BaseModel):
    username: str
    password: str
    nama: str
    role: str

@app.get("/api/users")
def get_users():
    conn = get_db()
    rows = conn.execute("SELECT id, username, nama, role FROM users ORDER BY role, nama").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/users")
def tambah_user(data: UserInput):
    conn = get_db()
    try:
        conn.execute("INSERT OR IGNORE INTO users (username, password, nama, role) VALUES (?, ?, ?, ?)",
                     (data.username, data.password, data.nama, data.role))
        conn.commit()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()
    return {"message": "User berhasil ditambahkan"}

class GantiPassword(BaseModel):
    username: str
    password_lama: str
    password_baru: str

@app.post("/api/ganti-password")
def ganti_password(data: GantiPassword):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username=? AND password=?",
                        (data.username, data.password_lama)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=400, detail="Password lama salah!")
    conn.execute("UPDATE users SET password=? WHERE username=?",
                 (data.password_baru, data.username))
    conn.commit()
    conn.close()
    return {"message": "Password berhasil diubah"}

@app.put("/api/users/{username}/nama")
def update_nama_user(username: str, data: dict):
    conn = get_db()
    conn.execute("UPDATE users SET nama=? WHERE username=?", (data.get('nama'), username))
    conn.commit()
    conn.close()
    return {"message": "Nama berhasil diubah"}

@app.put("/api/users/{username}/reset-password")
def reset_password_user(username: str, data: dict):
    conn = get_db()
    conn.execute("UPDATE users SET password=? WHERE username=?", (data.get('password','pajak123'), username))
    conn.commit()
    conn.close()
    return {"message": "Password berhasil direset"}

@app.delete("/api/users/{username}")
def hapus_user(username: str):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE username=? AND username NOT IN ('admin')", (username,))
    conn.commit()
    conn.close()
    return {"message": "User berhasil dihapus"}

@app.post("/api/pegawai")
def tambah_pegawai(data: PegawaiInput):
    conn = get_db()
    try:
        conn.execute("INSERT INTO pegawai (nama, tipe, email) VALUES (?, ?, ?)",
                     (data.nama, data.tipe, data.email))
        conn.commit()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()
    return {"message": "Pegawai berhasil ditambahkan"}

@app.put("/api/pegawai/{id}")
def update_pegawai(id: int, data: PegawaiInput):
    conn = get_db()
    conn.execute("UPDATE pegawai SET nama=?, tipe=?, email=? WHERE id=?",
                 (data.nama, data.tipe, data.email, id))
    conn.commit()
    conn.close()
    return {"message": "Pegawai berhasil diupdate"}

@app.delete("/api/pegawai/{id}")
def hapus_pegawai(id: int):
    conn = get_db()
    conn.execute("DELETE FROM pegawai WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return {"message": "Pegawai berhasil dihapus"}

@app.get("/api/kasus")
def get_kasus():
    conn = get_db()
    rows = conn.execute("SELECT * FROM kasus ORDER BY created_at DESC").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        tgl_ref = d.get("tgl_permohonan") or d.get("tgl_dibuat")
        if tgl_ref and not d.get("deadline_bpe"):
            try:
                tgl = date.fromisoformat(str(tgl_ref)[:10])
                d["deadline_bpe"] = tambah_hari_kerja(tgl, 1).isoformat()
                d["deadline_penelitian"] = tambah_hari_kerja(date.fromisoformat(d["deadline_bpe"]), 10).isoformat()
            except:
                pass
        done = d.get("hasil") in ["Dikabulkan", "Ditolak"]
        if d.get("deadline_bpe"):
            try:
                d["sisa_hk_bpe"] = 0 if done else sisa_hari_kerja(date.fromisoformat(d["deadline_bpe"]))
            except: d["sisa_hk_bpe"] = 0
        else:
            d["sisa_hk_bpe"] = None
        if d.get("deadline_penelitian"):
            try:
                d["sisa_hk_penelitian"] = 0 if done else sisa_hari_kerja(date.fromisoformat(d["deadline_penelitian"]))
            except: d["sisa_hk_penelitian"] = 0
        else:
            d["sisa_hk_penelitian"] = None
        if d.get("deadline_ar"):
            try:
                d["sisa_hk_ar"] = sisa_hari_kerja(date.fromisoformat(d["deadline_ar"]))
            except: d["sisa_hk_ar"] = None
        else:
            d["sisa_hk_ar"] = None
        result.append(d)
    return result

@app.post("/api/kasus")
def tambah_kasus(data: KasusInput):
    tgl = date.fromisoformat(data.tgl_permohonan)
    deadline_bpe = tambah_hari_kerja(tgl, 1)
    deadline_penelitian = tambah_hari_kerja(deadline_bpe, 10)
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO kasus (nomor_kasus, npwp, nama_wp, alamat, tgl_permohonan, pic, ar,
                               deadline_bpe, deadline_penelitian, status_kasus, sumber_kasus)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Diproses', 'Manual')
        """, (data.nomor_kasus, data.npwp, data.nama_wp, data.alamat,
              data.tgl_permohonan, data.pic, data.ar,
              deadline_bpe.isoformat(), deadline_penelitian.isoformat()))
        tulis_log(conn, data.nomor_kasus, "Tambah Kasus", f"Kasus {data.nomor_kasus} ({data.nama_wp}) ditambahkan", data.pic or "admin")
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Nomor kasus sudah ada!")
    finally:
        conn.close()
    return {"message": "Kasus berhasil ditambahkan"}

@app.post("/api/upload-excel")
async def upload_excel(file: UploadFile = File(...)):
    contents = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal baca file: {str(e)}")
    berhasil = 0
    duplikat = 0
    conn = get_db()
    for _, row in df.iterrows():
        nomor = str(row.get("Nomor Kasus", "")).strip()
        if not nomor or nomor == "nan":
            continue
        nama_wp = str(row.get("Nama Wajib Pajak Pusat", "")).strip()
        npwp = str(row.get("NPWP Wajib Pajak Pusat", "")).strip()
        jenis = str(row.get("Jenis Kasus", "")).strip()
        status = str(row.get("Status Kasus", "")).strip()
        sumber = str(row.get("Sumber Kasus", "")).strip()
        tgl_dibuat = str(row.get("Dibuat", "")).strip()
        dibuat_oleh = str(row.get("Dibuat Oleh Pengguna", "")).strip()
        tgl_ditutup = str(row.get("Ditutup", "")).strip()
        langkah = str(row.get("Langkah Alur Kerja", "")).strip()
        tgl_jatuh_tempo = str(row.get("Tanggal Jatuh Tempo Tertinggi", "")).strip()
        kantor_wilayah = str(row.get("Kantor Wilayah", "")).strip()
        kpp = str(row.get("Kantor Pelayanan Pajak", "")).strip()

        def clean(val): return None if not val or val in ("nan","NaT","None") else val
        def clean_date(val):
            if not val or val in ("nan","NaT","None"): return None
            try: return str(val)[:10]
            except: return None

        tgl_dibuat_clean = clean_date(tgl_dibuat)
        deadline_bpe = None
        deadline_penelitian = None
        if tgl_dibuat_clean:
            try:
                tgl = date.fromisoformat(tgl_dibuat_clean)
                deadline_bpe = tambah_hari_kerja(tgl, 1).isoformat()
                deadline_penelitian = tambah_hari_kerja(date.fromisoformat(deadline_bpe), 10).isoformat()
            except: pass

        try:
            conn.execute("""
                INSERT INTO kasus (nomor_kasus, npwp, nama_wp, jenis_kasus, status_kasus,
                    sumber_kasus, tgl_dibuat, dibuat_oleh, tgl_ditutup, langkah,
                    tgl_jatuh_tempo, kantor_wilayah, kpp,
                    tgl_permohonan, deadline_bpe, deadline_penelitian)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (nomor, clean(npwp), nama_wp, clean(jenis), clean(status),
                  clean(sumber), tgl_dibuat_clean, clean(dibuat_oleh),
                  clean_date(tgl_ditutup), clean(langkah),
                  clean_date(tgl_jatuh_tempo), clean(kantor_wilayah), clean(kpp),
                  tgl_dibuat_clean, deadline_bpe, deadline_penelitian))
            berhasil += 1
        except sqlite3.IntegrityError:
            duplikat += 1
    conn.commit()
    conn.close()
    return {"message": f"{berhasil} kasus berhasil diimport, {duplikat} duplikat dilewati"}

@app.put("/api/kasus/{nomor_kasus}/assign")
def assign_pegawai(nomor_kasus: str, data: AssignPegawai):
    conn = get_db()
    if data.pic is not None:
        conn.execute("UPDATE kasus SET pic=? WHERE nomor_kasus=?", (data.pic, nomor_kasus))
    if data.ar is not None:
        conn.execute("UPDATE kasus SET ar=? WHERE nomor_kasus=?", (data.ar, nomor_kasus))
    conn.commit()
    conn.close()
    return {"message": "Berhasil diupdate"}

@app.put("/api/kasus/{nomor_kasus}/status")
def update_status(nomor_kasus: str, data: UpdateStatus):
    tgl_selesai = date.fromisoformat(data.tgl_selesai)
    deadline_ar = None
    if data.hasil == "Dikabulkan":
        deadline_ar = tambah_hari_kerja(tgl_selesai, 30)
    conn = get_db()
    conn.execute("""
        UPDATE kasus SET status_kasus=?, tgl_selesai=?, hasil=?, deadline_ar=?, ar=?, nomor_lap=?, nomor_nd=?, tgl_nd=?
        WHERE nomor_kasus=?
    """, (data.hasil, data.tgl_selesai, data.hasil,
          deadline_ar.isoformat() if deadline_ar else None,
          data.ar, data.nomor_lap, data.nomor_nd, data.tgl_nd, nomor_kasus))
    tulis_log(conn, nomor_kasus, "Update Status", f"Status diubah menjadi {data.hasil} oleh {data.ar or 'admin'}", data.ar or "admin")
    conn.commit()
    conn.close()
    return {"message": "Status berhasil diupdate"}

@app.put("/api/kasus/{nomor_kasus}/visit")
def update_visit(nomor_kasus: str, data: UpdateVisitAR):
    conn = get_db()
    conn.execute("""
        UPDATE kasus SET tgl_visit=?, nama_ar_visit=?, nomor_lap=?
        WHERE nomor_kasus=?
    """, (data.tgl_visit, data.nama_ar_visit, data.nomor_lap, nomor_kasus))
    tulis_log(conn, nomor_kasus, "Visit AR", f"Visit dilakukan oleh {data.nama_ar_visit} pada {data.tgl_visit}", data.nama_ar_visit)
    conn.commit()
    conn.close()
    return {"message": "Visit AR berhasil diupdate"}

@app.get("/api/log")
def get_log(nomor_kasus: str = None):
    conn = get_db()
    if nomor_kasus:
        rows = conn.execute(
            "SELECT * FROM log_aktivitas WHERE nomor_kasus=? ORDER BY created_at DESC LIMIT 50",
            (nomor_kasus,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM log_aktivitas ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.delete("/api/kasus/{nomor_kasus}")
def hapus_kasus(nomor_kasus: str):
    conn = get_db()
    tulis_log(conn, nomor_kasus, "Hapus Kasus", f"Kasus {nomor_kasus} dihapus", "admin")
    conn.execute("DELETE FROM kasus WHERE nomor_kasus=?", (nomor_kasus,))
    conn.commit()
    conn.close()
    return {"message": "Kasus berhasil dihapus"}