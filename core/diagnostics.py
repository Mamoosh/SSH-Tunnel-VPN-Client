"""
Collects a verbose diagnostics report so the user can copy & send it.
"""
import os, sys, socket, subprocess, platform

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

def _run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, creationflags=_NO_WINDOW)
        return (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")
    except Exception as e:
        return f"<error: {e}>"

def _port_open(host, port, timeout=3):
    try:
        s = socket.create_connection((host, int(port)), timeout=timeout)
        s.close()
        return True
    except Exception as e:
        return f"FAIL ({e})"

def collect(tunnel=None, fullvpn=None, mode="proxy", profile=None):
    L = []
    def add(t): L.append(t)

    add("=" * 60)
    add("SSHH DIAGNOSTICS REPORT")
    add("=" * 60)
    add(f"OS         : {platform.platform()}")
    add(f"Python     : {sys.version.split()[0]}")
    add(f"Frozen exe : {getattr(sys, 'frozen', False)}")
    add(f"Mode       : {mode}")
    add("")

    # binaries
    try:
        from core.full_vpn import TUN2SOCKS, WINTUN, available, missing_reason
        add("-- Full VPN binaries --")
        add(f"tun2socks.exe : {'OK' if os.path.isfile(TUN2SOCKS) else 'MISSING'}  ({TUN2SOCKS})")
        add(f"wintun.dll    : {'OK' if os.path.isfile(WINTUN) else 'MISSING'}  ({WINTUN})")
        add(f"available()   : {available()}  missing={missing_reason()}")
    except Exception as e:
        add(f"<full_vpn import error: {e}>")
    add("")

    # local proxy ports
    add("-- Local proxy ports --")
    add(f"SOCKS 127.0.0.1:1080 : {_port_open('127.0.0.1', 1080)}")
    add(f"HTTP  127.0.0.1:1081 : {_port_open('127.0.0.1', 1081)}")
    add("")

    # tunnel state
    add("-- Tunnel --")
    if tunnel is not None:
        add(f"connected   : {getattr(tunnel, 'connected', '?')}")
        add(f"is_alive    : {tunnel.is_alive() if hasattr(tunnel,'is_alive') else '?'}")
        add(f"server_ip   : {getattr(tunnel, 'server_ip', '?')}")
        add(f"error       : {getattr(tunnel, 'error', '')}")
        tr = getattr(tunnel, "transport", None)
        add(f"transport   : active={tr.is_active() if tr else False}")
    else:
        add("no active tunnel object")
    add("")

    # ssh reachability
    if profile:
        add("-- SSH server reachability --")
        host = profile.get("host"); port = profile.get("port", 22)
        try:
            ip = socket.gethostbyname(host)
        except Exception as e:
            ip = f"<resolve fail: {e}>"
        add(f"host        : {host} -> {ip}")
        add(f"tcp {host}:{port} : {_port_open(host, port)}")
        add("")

    # network
    add("-- ipconfig --")
    add(_run(["ipconfig", "/all"])[:4000])
    add("")
    add("-- route print (IPv4) --")
    add(_run(["route", "print", "-4"])[:4000])
    add("")
    add("-- adapters --")
    add(_run(["powershell", "-NoProfile", "-Command",
              "Get-NetAdapter | Format-Table Name,Status,ifIndex,InterfaceDescription -Auto | Out-String"])[:2000])
    add("=" * 60)
    add("END OF REPORT")
    return "\n".join(L)
