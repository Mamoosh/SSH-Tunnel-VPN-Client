import sys, os, ctypes , time


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def elevate():
    """Re-launch the current script with a UAC admin prompt."""
    try:
        params = " ".join(f'"{a}"' for a in sys.argv)
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1)
        return rc > 32
    except Exception:
        return False


def main():
    # Problem #1: the app needs Administrator (WinDivert driver + routing).
    if os.name == "nt" and not is_admin():
        if elevate():
            sys.exit(0)          # elevated instance launched; quit this one
        # if user declined UAC, continue without admin (Full VPN disabled)

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from ui.main_window import MainWindow

    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setApplicationName("SSHH")
    win = MainWindow(is_admin=is_admin())
    win.show()
    sys.exit(app.exec())
    


if __name__ == "__main__":
    main()
    time.sleep(5)
