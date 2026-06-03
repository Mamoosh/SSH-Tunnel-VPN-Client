import sqlite3, os, json, time, threading
from .paths import db_path

DB_PATH = db_path()

_lock = threading.RLock()

def _conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def _ensure_column(c, table, col, decl):
    cols = [r["name"] for r in c.execute(f"PRAGMA table_info({table})")]
    if col not in cols:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")

def init_db():
    with _lock, _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS profiles(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            host TEXT NOT NULL,
            port INTEGER DEFAULT 22,
            username TEXT NOT NULL,
            password TEXT DEFAULT '',
            key_path TEXT DEFAULT '',
            created REAL DEFAULT 0,
            sessions INTEGER DEFAULT 0,
            total_down INTEGER DEFAULT 0,
            total_up INTEGER DEFAULT 0,
            last_ms INTEGER DEFAULT -1,
            last_ok INTEGER DEFAULT 0,
            locked INTEGER DEFAULT 0,
            total_uptime INTEGER DEFAULT 0
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS settings(
            k TEXT PRIMARY KEY, v TEXT)""")
        # migrations for older DBs
        _ensure_column(c, "profiles", "locked", "INTEGER DEFAULT 0")
        _ensure_column(c, "profiles", "total_uptime", "INTEGER DEFAULT 0")

def add_profile(name, host, port, username, password="", key_path="", locked=0):
    with _lock, _conn() as c:
        cur = c.execute(
            "INSERT INTO profiles(name,host,port,username,password,key_path,"
            "created,locked) VALUES(?,?,?,?,?,?,?,?)",
            (name, host, int(port), username, password, key_path,
             time.time(), int(locked)))
        return cur.lastrowid

def update_profile(pid, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [pid]
    with _lock, _conn() as c:
        c.execute(f"UPDATE profiles SET {cols} WHERE id=?", vals)

def delete_profile(pid):
    with _lock, _conn() as c:
        c.execute("DELETE FROM profiles WHERE id=?", (pid,))

def list_profiles():
    with _lock, _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM profiles ORDER BY id DESC").fetchall()]

def get_profile(pid):
    with _lock, _conn() as c:
        r = c.execute("SELECT * FROM profiles WHERE id=?", (pid,)).fetchone()
        return dict(r) if r else None

def add_traffic(pid, down, up):
    with _lock, _conn() as c:
        c.execute("UPDATE profiles SET total_down=total_down+?, total_up=total_up+?"
                  " WHERE id=?", (int(down), int(up), pid))

def add_uptime(pid, seconds):
    with _lock, _conn() as c:
        c.execute("UPDATE profiles SET total_uptime=total_uptime+? WHERE id=?",
                  (int(seconds), pid))

def bump_session(pid):
    with _lock, _conn() as c:
        c.execute("UPDATE profiles SET sessions=sessions+1 WHERE id=?", (pid,))

def set_ping(pid, ms, ok):
    with _lock, _conn() as c:
        c.execute("UPDATE profiles SET last_ms=?, last_ok=? WHERE id=?",
                  (int(ms), 1 if ok else 0, pid))

def get_setting(k, default=None):
    with _lock, _conn() as c:
        r = c.execute("SELECT v FROM settings WHERE k=?", (k,)).fetchone()
        if not r:
            return default
        try:
            return json.loads(r["v"])
        except Exception:
            return r["v"]

def set_setting(k, v):
    with _lock, _conn() as c:
        c.execute("INSERT INTO settings(k,v) VALUES(?,?) "
                  "ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                  (k, json.dumps(v)))

def reset_settings():
    with _lock, _conn() as c:
        c.execute("DELETE FROM settings")

def reset_data():
    with _lock, _conn() as c:
        c.execute("UPDATE profiles SET sessions=0, total_down=0, "
                  "total_up=0, last_ms=-1, last_ok=0, total_uptime=0")

def delete_all_profiles():
    with _lock, _conn() as c:
        c.execute("DELETE FROM profiles")

def global_totals():
    with _lock, _conn() as c:
        r = c.execute(
            "SELECT COUNT(*) AS cnt, "
            "COALESCE(SUM(total_down),0) AS d, "
            "COALESCE(SUM(total_up),0) AS u, "
            "COALESCE(SUM(sessions),0) AS s, "
            "COALESCE(SUM(total_uptime),0) AS ut FROM profiles").fetchone()
        return dict(count=r["cnt"], down=r["d"], up=r["u"],
                    sessions=r["s"], total_uptime=r["ut"])

init_db()
