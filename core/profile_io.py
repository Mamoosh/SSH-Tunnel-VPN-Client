"""
Import / export profiles to portable ".sshh" files.

Two kinds of files:

  * UNLOCKED  : profiles stored in plain JSON. Viewable & editable after import.
  * LOCKED    : profiles encrypted. NOT viewable/editable after import.
                A password is OPTIONAL:
                  - with a password -> AES key derived from it (PBKDF2)
                  - without a password -> AES key derived from a fixed app key
                Either way the file body is encrypted and unreadable in a
                text editor, and imported profiles are flagged read-only.
"""
import json, base64, os

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAVE_CRYPTO = True
except Exception:
    HAVE_CRYPTO = False

MAGIC = "SSHH"
VERSION = 2
_FIELDS = ("name", "host", "port", "username", "password", "key_path")

# fixed application secret used when a locked file has NO user password.
# (keeps the body unreadable in a text editor; not meant as strong secrecy)
_APP_SECRET = b"SSHH-app-default-lock-key-v1-do-not-change"

def _clean(profiles_list):
    out = []
    for p in profiles_list:
        out.append({k: p.get(k, "") for k in _FIELDS})
    return out

def _derive_key(secret_bytes, salt):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=salt, iterations=200_000)
    return base64.urlsafe_b64encode(kdf.derive(secret_bytes))

def export_profiles(path, profiles_list, locked=False, password=None):
    """
    locked=False -> plain, viewable file.
    locked=True  -> encrypted file. password optional.
    """
    data = _clean(profiles_list)
    if locked:
        if not HAVE_CRYPTO:
            raise RuntimeError("cryptography package required for locked files. "
                               "pip install cryptography")
        salt = os.urandom(16)
        secret = password.encode("utf-8") if password else _APP_SECRET
        has_pw = bool(password)
        key = _derive_key(secret, salt)
        token = Fernet(key).encrypt(json.dumps(data).encode("utf-8"))
        obj = {"magic": MAGIC, "version": VERSION, "locked": True,
               "has_password": has_pw,
               "salt": base64.b64encode(salt).decode(),
               "blob": base64.b64encode(token).decode()}
    else:
        obj = {"magic": MAGIC, "version": VERSION, "locked": False,
               "has_password": False, "profiles": data}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return True

def inspect(path):
    """Return (locked, has_password) without decrypting."""
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if obj.get("magic") != MAGIC:
        raise ValueError("Not a valid .sshh file.")
    return bool(obj.get("locked")), bool(obj.get("has_password"))

def import_profiles(path, password=None):
    """
    Returns (profiles_list, locked_bool).
    - Unlocked file: returns the profiles (viewable), locked=False.
    - Locked file: decrypts (using password if the file requires one,
      otherwise the app key), returns profiles + locked=True so the caller
      can store them as read-only.
    """
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    if obj.get("magic") != MAGIC:
        raise ValueError("Not a valid .sshh file.")
    if not obj.get("locked"):
        return obj.get("profiles", []), False
    if not HAVE_CRYPTO:
        raise RuntimeError("cryptography package required to open locked files.")
    has_pw = bool(obj.get("has_password"))
    if has_pw and not password:
        raise PermissionError("This file is locked with a password.")
    salt = base64.b64decode(obj["salt"])
    token = base64.b64decode(obj["blob"])
    secret = password.encode("utf-8") if (has_pw and password) else _APP_SECRET
    key = _derive_key(secret, salt)
    try:
        raw = Fernet(key).decrypt(token)
    except Exception:
        raise PermissionError("Wrong password or corrupted file.")
    return json.loads(raw.decode("utf-8")), True
