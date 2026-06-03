import os

APP_DIR_NAME = "sshh"

def _documents_dir():
    """Return the Windows Documents folder, with safe fallbacks."""
    # Try the Windows known-folder API first (most reliable, respects redirect)
    try:
        import ctypes
        from ctypes import wintypes
        CSIDL_PERSONAL = 5          # My Documents
        SHGFP_TYPE_CURRENT = 0
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(
            None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)
        if buf.value:
            return buf.value
    except Exception:
        pass
    # Fallbacks
    home = os.path.expanduser("~")
    docs = os.path.join(home, "Documents")
    if os.path.isdir(docs):
        return docs
    return home

def app_data_dir():
    """<Documents>\\sshh — created if missing. Works inside a PyInstaller exe."""
    d = os.path.join(_documents_dir(), APP_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d

def db_path():
    return os.path.join(app_data_dir(), "sshh.db")

def ensure_subdir(name):
    d = os.path.join(app_data_dir(), name)
    os.makedirs(d, exist_ok=True)
    return d
