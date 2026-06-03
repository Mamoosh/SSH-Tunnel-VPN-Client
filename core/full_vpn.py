"""Full VPN removed. Kept as a stub so old imports don't crash."""
def available(): return False
def missing_reason(): return "Full VPN was removed."
def download_binaries(logger=None): return False, "Full VPN was removed."
class FullVPN:
    def __init__(self, *a, **k): raise RuntimeError("Full VPN was removed.")
    def start(self): raise RuntimeError("Full VPN was removed.")
    def stop(self): pass
