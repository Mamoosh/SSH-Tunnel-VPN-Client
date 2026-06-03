import shutil, subprocess, os

"""
Full system VPN (TUN) mode.

For a *true* full tunnel (not just an app proxy), the standard, safe approach
on Windows is to route all traffic into the local SOCKS proxy using the
open-source tool `tun2socks` together with the WinTUN/Wintun driver.

This module only LAUNCHES tun2socks if the user has placed the binary in
  <project>/bin/tun2socks.exe
It never installs drivers silently or modifies the routing table destructively.
If the binary is missing, VPN mode falls back with a clear message.
"""

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "bin", "tun2socks.exe")


def available():
    return os.path.isfile(BIN)


class TunMode:
    def __init__(self, socks_host="127.0.0.1", socks_port=1080):
        self.socks_host = socks_host
        self.socks_port = socks_port
        self.proc = None

    def start(self):
        if not available():
            raise RuntimeError(
                "tun2socks.exe not found in /bin. Place the tun2socks binary "
                "there to enable full VPN (TUN) mode. Proxy mode works without it.")
        # Standard tun2socks invocation; device name 'sshh-tun'.
        cmd = [BIN, "-device", "sshh-tun",
               "-proxy", f"socks5://{self.socks_host}:{self.socks_port}"]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL,
                                     creationflags=getattr(subprocess,
                                                          "CREATE_NO_WINDOW", 0))
        return True

    def stop(self):
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass
            self.proc = None
