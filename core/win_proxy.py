import ctypes
try:
    import winreg
except ImportError:
    winreg = None

_SETTINGS_CHANGED = 39
_REFRESH = 37
_PATH = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"


def _refresh():
    try:
        w = ctypes.windll.wininet
        w.InternetSetOptionW(0, _SETTINGS_CHANGED, 0, 0)
        w.InternetSetOptionW(0, _REFRESH, 0, 0)
    except Exception:
        pass


def set_proxy(host="127.0.0.1", http_port=1081, socks_port=1080,
              bypass="localhost;127.*;10.*;172.16.*;192.168.*;<local>"):
    """Set BOTH http/https (reliable) and socks fallback."""
    if winreg is None:
        return False
    server = (f"http={host}:{http_port};https={host}:{http_port};"
              f"socks={host}:{socks_port}")
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _PATH, 0,
                             winreg.KEY_WRITE)
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, server)
        winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, bypass)
        winreg.CloseKey(key)
        _refresh()
        return True
    except Exception:
        return False


def clear_proxy():
    if winreg is None:
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _PATH, 0,
                             winreg.KEY_WRITE)
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        try:
            winreg.DeleteValue(key, "ProxyServer")
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
        _refresh()
        return True
    except Exception:
        return False


def is_enabled():
    if winreg is None:
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _PATH)
        val, _ = winreg.QueryValueEx(key, "ProxyEnable")
        winreg.CloseKey(key)
        return bool(val)
    except Exception:
        return False
