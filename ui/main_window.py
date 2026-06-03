import os, threading, time, webbrowser
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel,
    QPushButton, QStackedWidget, QFrame, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QButtonGroup, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QDialog, QFormLayout, QPlainTextEdit, QTextEdit, QFileDialog,
    QInputDialog, QCheckBox, QApplication)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

from core import profiles
from core import profile_io
from core.ssh_tunnel import SSHTunnel
from core.tun_mode import TunMode, available as tun_available
from core import notify
from core import diagnostics
from core import win_proxy
from core.pinger import tcp_ping
from core.stats import Stats
from ui.theme import stylesheet, ACCENTS, ACCENTS2, BG, THEMES
from ui.widgets import (PowerButton, TrafficChart, StatCard,
                        fmt_bytes, fmt_speed, fmt_time)
from ui.background import AnimatedBackground

LOCAL_PORT = 1080
HTTP_PORT = 1081
GITHUB_URL = "https://github.com/Mamoosh/Windows-SSH-VPN"


def mask_ip(text):
    """Return a masked version of an address for demo mode."""
    return "*" * max(4, min(14, len(str(text))))


class BulkAddDialog(QDialog):
    """Add one OR many profiles. Bulk format: name,host,port,user,password"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Profile(s)")
        self.setMinimumWidth(520)
        if parent: self.setStyleSheet(parent.styleSheet())
        v = QVBoxLayout(self)

        # single
        form = QFormLayout()
        self.name = QLineEdit(); self.host = QLineEdit()
        self.port = QSpinBox(); self.port.setRange(1, 65535); self.port.setValue(22)
        self.user = QLineEdit(); self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.key = QLineEdit()
        form.addRow("Name", self.name); form.addRow("Host / IP", self.host)
        form.addRow("Port", self.port); form.addRow("Username", self.user)
        form.addRow("Password", self.pw); form.addRow("Key file (optional)", self.key)
        v.addWidget(QLabel("Single profile:"))
        sf = QFrame(); sf.setLayout(form); v.addWidget(sf)

        v.addSpacing(8)
        v.addWidget(QLabel(
            "OR bulk add — one profile per line:\n"
            "name,host,port,username,password"))
        self.bulk = QPlainTextEdit()
        self.bulk.setPlaceholderText(
            "Server-DE,1.2.3.4,22,root,secret\n"
            "Server-NL,5.6.7.8,2222,user,pass")
        self.bulk.setMaximumHeight(140)
        v.addWidget(self.bulk)

        row = QHBoxLayout()
        ok = QPushButton("Add"); ok.setProperty("class", "btn primary")
        cancel = QPushButton("Cancel"); cancel.setProperty("class", "btn")
        ok.clicked.connect(self.accept); cancel.clicked.connect(self.reject)
        row.addStretch(1); row.addWidget(cancel); row.addWidget(ok)
        v.addLayout(row)

    def results(self):
        """Return a list of profile dicts (single + bulk)."""
        out = []
        # single (only if host present)
        if self.host.text().strip():
            out.append(dict(
                name=self.name.text().strip() or "Server",
                host=self.host.text().strip(), port=self.port.value(),
                username=self.user.text().strip(),
                password=self.pw.text(), key_path=self.key.text().strip()))
        # bulk
        for line in self.bulk.toPlainText().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2:
                continue
            name = parts[0] or "Server"
            host = parts[1]
            port = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 22
            user = parts[3] if len(parts) > 3 else "root"
            pw = parts[4] if len(parts) > 4 else ""
            out.append(dict(name=name, host=host, port=port,
                            username=user, password=pw, key_path=""))
        return out


class ProfileDialog(QDialog):
    """Edit a single profile. Read-only when the profile is locked."""
    def __init__(self, parent=None, prof=None, read_only=False):
        super().__init__(parent)
        self.setWindowTitle("Profile" + (" (locked - read only)" if read_only else ""))
        self.setMinimumWidth(420)
        if parent: self.setStyleSheet(parent.styleSheet())
        form = QFormLayout(self)
        self.name = QLineEdit(); self.host = QLineEdit()
        self.port = QSpinBox(); self.port.setRange(1, 65535); self.port.setValue(22)
        self.user = QLineEdit(); self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.key = QLineEdit()
        if prof:
            if read_only:
                # do NOT reveal the secrets of a locked profile
                self.name.setText(prof.get("name", "Locked profile"))
                self.host.setText("**** locked ****")
                self.user.setText("**** locked ****")
                self.pw.setText("")
                self.key.setText("")
            else:
                self.name.setText(prof.get("name", ""))
                self.host.setText(prof.get("host", ""))
                self.port.setValue(int(prof.get("port", 22) or 22))
                self.user.setText(prof.get("username", ""))
                self.pw.setText(prof.get("password", ""))
                self.key.setText(prof.get("key_path", ""))
        form.addRow("Name", self.name); form.addRow("Host / IP", self.host)
        form.addRow("Port", self.port); form.addRow("Username", self.user)
        form.addRow("Password", self.pw)
        form.addRow("Key file (optional)", self.key)
        if read_only:
            for wdg in (self.name, self.host, self.port, self.user, self.pw, self.key):
                wdg.setEnabled(False)
        row = QHBoxLayout()
        if not read_only:
            ok = QPushButton("Save"); ok.setProperty("class", "btn primary")
            ok.clicked.connect(self.accept); row.addWidget(ok)
        close = QPushButton("Close" if read_only else "Cancel")
        close.setProperty("class", "btn"); close.clicked.connect(self.reject)
        row.addWidget(close); form.addRow(row)

    def data(self):
        return dict(name=self.name.text().strip() or "Server",
                    host=self.host.text().strip(), port=self.port.value(),
                    username=self.user.text().strip(),
                    password=self.pw.text(), key_path=self.key.text().strip())


class MainWindow(QMainWindow):
    sig_connected = pyqtSignal(bool, str)

    def __init__(self, is_admin=False):
        super().__init__()
        self.is_admin = is_admin
        self.setWindowTitle("SSHH")
        self.resize(1180, 760)

        self.theme = profiles.get_setting("theme", "blue")
        self.mode = profiles.get_setting("mode", "proxy")
        self.ui_scale = float(profiles.get_setting("ui_scale", 1.0) or 1.0)
        self.demo_mode = bool(profiles.get_setting("demo_mode", False))
        self.notify_enabled = bool(profiles.get_setting("notify", True))
        self.kill_switch = bool(profiles.get_setting("kill_switch", False))
        self.auto_reconnect = bool(profiles.get_setting("auto_reconnect", False))
        self.layout_mode = profiles.get_setting("layout_mode", "horizontal")
        self._reconnect_profile = None
        self.tunnel = None; self.tun = None
        self.active_id = None
        self.stats = Stats()
        self.connecting = False
        self._last_persist_down = 0
        self._last_persist_up = 0
        self._max_speed = 0.0
        self._last_uptime_persist = 0

        self._build_ui()
        self.apply_theme()
        self.sig_connected.connect(self._on_connect_result)

        self.timer = QTimer(self); self.timer.timeout.connect(self._tick)
        self.timer.start(1000)
        self.ping_timer = QTimer(self)
        self.ping_timer.timeout.connect(self._ping_all_async)
        self.ping_timer.start(20000)
        QTimer.singleShot(800, self._ping_all_async)
        self.refresh_profiles()
        self.refresh_totals()
        self._apply_layout_mode()

    # ---------- UI ----------
    def _build_ui(self):
        root = QWidget(); root.setObjectName("root")
        self.setCentralWidget(root)
        self.bg = AnimatedBackground(BG[self.theme])
        self.bg.setParent(root); self.bg.lower()
        h = QHBoxLayout(root); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)

        side = QFrame(); side.setObjectName("sidebar"); side.setFixedWidth(238)
        sv = QVBoxLayout(side); sv.setContentsMargins(16, 22, 16, 16)
        logo = QLabel("[+]  SSHH"); logo.setObjectName("logoText")
        sv.addWidget(logo); sv.addSpacing(20)

        self.menu_group = QButtonGroup(self)
        self.pages = QStackedWidget()
        menu = [("Dashboard", self._page_dashboard),
                ("Profiles", self._page_profiles),
                ("Statistics", self._page_stats),
                ("Logs", self._page_logs),
                ("Settings", self._page_settings),
                ("About", self._page_about)]
        for i, (name, builder) in enumerate(menu):
            b = QPushButton("   " + name); b.setObjectName("menuItem")
            b.setCheckable(True); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, idx=i: self.pages.setCurrentIndex(idx))
            self.menu_group.addButton(b, i)
            sv.addWidget(b)
            self.pages.addWidget(builder())
            if name == "About": self._about_index = i
        self.menu_group.button(0).setChecked(True)
        sv.addStretch(1)

        sv.addWidget(self._build_totals_panel())
        sv.addSpacing(8)
        self.conn_dot = QLabel("Disconnected")
        self.conn_dot.setStyleSheet("color:#6b7a99;font-size:12px;")
        sv.addWidget(self.conn_dot)
        h.addWidget(side)

        main = QFrame(); main.setObjectName("main")
        mv = QVBoxLayout(main); mv.setContentsMargins(26, 22, 26, 22)
        top = QHBoxLayout(); tt = QVBoxLayout()
        self.page_title = QLabel("Dashboard"); self.page_title.setObjectName("pageTitle")
        self.page_sub = QLabel("Overview & quick connect"); self.page_sub.setObjectName("pageSub")
        tt.addWidget(self.page_title); tt.addWidget(self.page_sub)
        top.addLayout(tt); top.addStretch(1)

        # demo (eye) toggle
        self.eye_btn = QPushButton("(*) Hide IPs" if not self.demo_mode else "(o) Show IPs")
        self.eye_btn.setProperty("class", "chip"); self.eye_btn.setCheckable(True)
        self.eye_btn.setChecked(self.demo_mode)
        self.eye_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.eye_btn.clicked.connect(self._toggle_demo)
        top.addWidget(self.eye_btn)

        self.chip_admin = QPushButton("admin" if self.is_admin else "user")
        self.chip_mode = QPushButton(self.mode)
        for c in (self.chip_admin, self.chip_mode):
            c.setProperty("class", "chip"); c.setEnabled(False)
        top.addWidget(self.chip_admin); top.addWidget(self.chip_mode)
        mv.addLayout(top); mv.addSpacing(10); mv.addWidget(self.pages, 1)
        h.addWidget(main, 1)
        self.pages.currentChanged.connect(self._on_page_changed)

    def _build_totals_panel(self):
        card = QFrame(); card.setObjectName("totalsCard")
        v = QVBoxLayout(card); v.setContentsMargins(14, 12, 14, 12); v.setSpacing(5)
        title = QLabel("GLOBAL TOTALS"); title.setObjectName("totLabel")
        v.addWidget(title)
        self.tot_labels = {}
        rows = [("total", "Total Data"), ("down", "Downloaded"),
                ("up", "Uploaded"), ("avgspeed", "Speed"),
                ("maxspeed", "Max Speed"), ("uptime", "Uptime"),
                ("totuptime", "Total Uptime"), ("count", "Configs"),
                ("sessions", "Connections")]
        for key, label in rows:
            r = QHBoxLayout()
            l = QLabel(label); l.setObjectName("totLabel")
            val = QLabel("-"); val.setObjectName("totVal")
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            r.addWidget(l); r.addStretch(1); r.addWidget(val)
            v.addLayout(r)
            self.tot_labels[key] = val
        return card

    def refresh_totals(self):
        g = profiles.global_totals()
        total = g["down"] + g["up"]
        # live uptime + cumulative
        cur_uptime = self.stats.uptime() if (self.tunnel and self.tunnel.is_alive()) else 0
        avg_speed = self.stats.speed_down + self.stats.speed_up \
            if (self.tunnel and self.tunnel.is_alive()) else 0
        self.tot_labels["total"].setText(fmt_bytes(total))
        self.tot_labels["down"].setText(fmt_bytes(g["down"]))
        self.tot_labels["up"].setText(fmt_bytes(g["up"]))
        self.tot_labels["avgspeed"].setText(
            fmt_speed(avg_speed) if avg_speed else "-")
        self.tot_labels["maxspeed"].setText(
            fmt_speed(self._max_speed) if self._max_speed else "-")
        self.tot_labels["uptime"].setText(fmt_time(cur_uptime))
        self.tot_labels["totuptime"].setText(fmt_time(g["total_uptime"]))
        self.tot_labels["count"].setText(str(g["count"]))
        self.tot_labels["sessions"].setText(str(g["sessions"]))

    def resizeEvent(self, e):
        if hasattr(self, "bg"):
            self.bg.setGeometry(self.centralWidget().rect())
        super().resizeEvent(e)

    def _toggle_demo(self):
        self.demo_mode = self.eye_btn.isChecked()
        profiles.set_setting("demo_mode", self.demo_mode)
        self.eye_btn.setText("(o) Show IPs" if self.demo_mode else "(*) Hide IPs")
        self.refresh_profiles()
        self._on_combo_changed(0)
        if self.pages.currentIndex() == 2:
            self.refresh_stats()

    def _disp_addr(self, text):
        return mask_ip(text) if self.demo_mode else text

    def _page_dashboard(self):
        w = QWidget(); g = QGridLayout(w); g.setSpacing(16)
        pc = QFrame(); pc.setObjectName("card")
        pcv = QVBoxLayout(pc); pcv.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.power = PowerButton(ACCENTS[self.theme])
        self.power.clicked.connect(self._toggle_connection)
        self.power_status = QLabel("Disconnected")
        self.power_status.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.power_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.power_sub = QLabel("Tap to connect"); self.power_sub.setObjectName("statSub")
        self.power_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pcv.addWidget(self.power, alignment=Qt.AlignmentFlag.AlignCenter)
        pcv.addSpacing(8); pcv.addWidget(self.power_status); pcv.addWidget(self.power_sub)

        mode_row = QHBoxLayout()
        self.btn_proxy = QPushButton("Proxy"); self.btn_proxy.setProperty("class", "btn")
        self.btn_vpn = QPushButton("VPN (TUN)"); self.btn_vpn.setProperty("class", "btn")
        for b in (self.btn_proxy, self.btn_vpn):
            b.setCheckable(True)
        self.btn_proxy.clicked.connect(lambda: self._set_mode("proxy"))
        self.btn_vpn.clicked.connect(lambda: self._set_mode("vpn"))
        mode_row.addWidget(self.btn_proxy); mode_row.addWidget(self.btn_vpn)
        pcv.addSpacing(10); pcv.addLayout(mode_row)
        g.addWidget(pc, 0, 0, 2, 2)

        ac = QFrame(); ac.setObjectName("card"); acv = QVBoxLayout(ac)
        acv.addWidget(self._h("ACTIVE SERVER"))
        self.active_combo = QComboBox()
        self.active_combo.currentIndexChanged.connect(self._on_combo_changed)
        acv.addWidget(self.active_combo)
        self.active_info = QLabel("No profile selected.")
        self.active_info.setWordWrap(True); self.active_info.setObjectName("statSub")
        acv.addWidget(self.active_info); acv.addStretch(1)
        g.addWidget(ac, 0, 2, 2, 4)

        self.card_down = StatCard("DOWNLOAD", ACCENTS[self.theme])
        self.card_up = StatCard("UPLOAD", ACCENTS[self.theme])
        self.card_uptime = StatCard("UPTIME", ACCENTS[self.theme])
        g.addWidget(self.card_down, 2, 0, 1, 2)
        g.addWidget(self.card_up, 2, 2, 1, 2)
        g.addWidget(self.card_uptime, 2, 4, 1, 2)

        chc = QFrame(); chc.setObjectName("card"); chv = QVBoxLayout(chc)
        chv.addWidget(self._h("REAL-TIME TRAFFIC  (last 60s)"))
        self.chart = TrafficChart(ACCENTS[self.theme], ACCENTS2[self.theme])
        chv.addWidget(self.chart)
        g.addWidget(chc, 3, 0, 1, 6)
        g.setRowStretch(4, 1)
        return w

    def _h(self, t):
        l = QLabel(t); l.setObjectName("statLabel"); return l

    def _page_profiles(self):
        w = QWidget(); v = QVBoxLayout(w); bar = QHBoxLayout()
        add = QPushButton("Add Profile(s)"); add.setProperty("class", "btn primary")
        add.clicked.connect(self._add_profile)
        edit = QPushButton("Edit"); edit.setProperty("class", "btn")
        edit.clicked.connect(self._edit_profile)
        dele = QPushButton("Delete"); dele.setProperty("class", "btn danger")
        dele.clicked.connect(self._delete_profile)
        delall = QPushButton("Delete All"); delall.setProperty("class", "btn danger")
        delall.clicked.connect(self._delete_all)
        ping = QPushButton("Test All (ping)"); ping.setProperty("class", "btn")
        ping.clicked.connect(self._ping_all_async)
        imp = QPushButton("Import"); imp.setProperty("class", "btn")
        imp.clicked.connect(self._import_profiles)
        exp = QPushButton("Export Sel."); exp.setProperty("class", "btn")
        exp.clicked.connect(self._export_selected)
        expall = QPushButton("Export All"); expall.setProperty("class", "btn")
        expall.clicked.connect(self._export_all)
        conn = QPushButton("Connect Selected"); conn.setProperty("class", "btn primary")
        conn.clicked.connect(self._connect_selected)
        for b in (add, edit, dele, delall, ping, imp, exp, expall):
            bar.addWidget(b)
        bar.addStretch(1); bar.addWidget(conn); v.addLayout(bar)
        self.ptable = QTableWidget(0, 6)
        self.ptable.setHorizontalHeaderLabels(
            ["Name", "Address", "User", "Ping", "Status", "Total Traffic"])
        self.ptable.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.ptable.verticalHeader().setVisible(False)
        self.ptable.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.ptable.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.ptable.doubleClicked.connect(lambda *_: self._edit_profile())
        v.addWidget(self.ptable)
        return w

    def _page_stats(self):
        w = QWidget(); v = QVBoxLayout(w); grid = QGridLayout()
        self.s_total_down = StatCard("TOTAL DOWNLOADED")
        self.s_total_up = StatCard("TOTAL UPLOADED")
        self.s_avg = StatCard("SPEED (MB/s)")
        self.s_sessions = StatCard("SESSIONS")
        grid.addWidget(self.s_total_down, 0, 0); grid.addWidget(self.s_total_up, 0, 1)
        grid.addWidget(self.s_avg, 0, 2); grid.addWidget(self.s_sessions, 0, 3)
        v.addLayout(grid); v.addWidget(self._h("PER-PROFILE USAGE"))
        self.stable = QTableWidget(0, 6)
        self.stable.setHorizontalHeaderLabels(
            ["Profile", "Address (IP)", "Sessions", "Down", "Up", "Total"])
        self.stable.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.stable.verticalHeader().setVisible(False)
        self.stable.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        v.addWidget(self.stable)
        return w

    def _page_logs(self):
        w = QWidget(); v = QVBoxLayout(w)
        clear = QPushButton("Clear"); clear.setProperty("class", "btn")
        self.log_box = QPlainTextEdit(); self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("font-family:Consolas;font-size:12px;color:#cad6ea;")
        clear.clicked.connect(lambda: self.log_box.clear())
        v.addWidget(clear); v.addWidget(self.log_box)
        return w

    def _page_settings(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(self._h("THEME"))
        trow = QHBoxLayout()
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(THEMES.keys()))
        self.theme_combo.setCurrentText(self.theme)
        self.theme_combo.currentTextChanged.connect(self._change_theme)
        trow.addWidget(self.theme_combo); trow.addStretch(1); v.addLayout(trow)

        v.addSpacing(16); v.addWidget(self._h("UI SCALE"))
        srow = QHBoxLayout()
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.7, 2.0); self.scale_spin.setSingleStep(0.1)
        self.scale_spin.setValue(self.ui_scale); self.scale_spin.setSuffix("  x")
        apply_scale = QPushButton("Apply"); apply_scale.setProperty("class", "btn primary")
        apply_scale.clicked.connect(self._apply_scale)
        srow.addWidget(self.scale_spin); srow.addWidget(apply_scale)
        srow.addStretch(1); v.addLayout(srow)

        v.addSpacing(16); v.addWidget(self._h("SYSTEM PROXY"))
        pr = QHBoxLayout()
        clearp = QPushButton("Force Disconnect & Clear Proxy")
        clearp.setProperty("class", "btn danger")
        clearp.clicked.connect(self._force_clear)
        pr.addWidget(clearp); pr.addStretch(1); v.addLayout(pr)

        v.addSpacing(16); v.addWidget(self._h("RESET"))
        rr = QHBoxLayout()
        rs = QPushButton("Reset Settings"); rs.setProperty("class", "btn danger")
        rs.clicked.connect(self._reset_settings)
        rd = QPushButton("Reset Data (traffic stats)"); rd.setProperty("class", "btn danger")
        rd.clicked.connect(self._reset_data)
        rr.addWidget(rs); rr.addWidget(rd); rr.addStretch(1); v.addLayout(rr)

        v.addSpacing(16); v.addWidget(self._h("NOTIFICATIONS"))
        self.cb_notify = QCheckBox("Show a Windows notification on connect / disconnect")
        self.cb_notify.setChecked(self.notify_enabled)
        self.cb_notify.stateChanged.connect(self._toggle_notify)
        v.addWidget(self.cb_notify)

        v.addSpacing(16); v.addWidget(self._h("LAYOUT"))
        lrow = QHBoxLayout()
        self.btn_horiz = QPushButton("Horizontal"); self.btn_horiz.setProperty("class", "btn")
        self.btn_vert = QPushButton("Vertical"); self.btn_vert.setProperty("class", "btn")
        self.btn_horiz.setCheckable(True); self.btn_vert.setCheckable(True)
        self.btn_horiz.setChecked(self.layout_mode == "horizontal")
        self.btn_vert.setChecked(self.layout_mode == "vertical")
        def _lh():
            self.btn_horiz.setChecked(True); self.btn_vert.setChecked(False)
            self._set_layout_mode("horizontal")
        def _lv():
            self.btn_vert.setChecked(True); self.btn_horiz.setChecked(False)
            self._set_layout_mode("vertical")
        self.btn_horiz.clicked.connect(_lh); self.btn_vert.clicked.connect(_lv)
        lrow.addWidget(self.btn_horiz); lrow.addWidget(self.btn_vert)
        lrow.addStretch(1); v.addLayout(lrow)

        v.addSpacing(16); v.addWidget(self._h("EXTRAS"))
        self.cb_kill = QCheckBox("Kill-switch: keep system proxy off until reconnect "
                                 "(blocks leaks if the tunnel drops)")
        self.cb_kill.setChecked(self.kill_switch)
        self.cb_kill.stateChanged.connect(self._toggle_kill_switch)
        v.addWidget(self.cb_kill)
        self.cb_reconnect = QCheckBox("Auto-reconnect if the connection drops")
        self.cb_reconnect.setChecked(self.auto_reconnect)
        self.cb_reconnect.stateChanged.connect(self._toggle_auto_reconnect)
        v.addWidget(self.cb_reconnect)

        v.addSpacing(16); v.addWidget(self._h("TROUBLESHOOT"))
        drow = QHBoxLayout()
        diag = QPushButton("Run Diagnostics / Troubleshoot")
        diag.setProperty("class", "btn primary")
        diag.clicked.connect(self._show_diagnostics)
        drow.addWidget(diag); drow.addStretch(1)
        v.addLayout(drow)

        v.addSpacing(16); v.addWidget(self._h("MODES"))
        info = QLabel(
            "Proxy: Windows system proxy (HTTP + SOCKS over SSH).\n\n"
            "VPN (TUN): full system tunnel via tun2socks (needs the\n"
            "tun2socks.exe in /bin and Administrator).")
        info.setObjectName("statSub"); info.setWordWrap(True); v.addWidget(info)
        v.addStretch(1)
        return w

    def _page_about(self):
        w = QWidget(); v = QVBoxLayout(w)
        card = QFrame(); card.setObjectName("card"); cv = QVBoxLayout(card)
        cv.setContentsMargins(26, 26, 26, 26)
        title = QLabel("SSHH"); title.setStyleSheet(
            f"font-size:32px;font-weight:800;color:{ACCENTS[self.theme]};")
        cv.addWidget(title)
        slogan = QLabel("Tunnel boldly. The free internet belongs to everyone.")
        slogan.setStyleSheet("font-size:14px;color:#aab6d4;font-style:italic;")
        cv.addWidget(slogan); cv.addSpacing(14)
        desc = QLabel(
            "SSHH is a lightweight, open-source SSH-based VPN / proxy client for "
            "Windows. It turns any SSH server into a secure tunnel: add your "
            "servers as profiles, connect with a single tap, and route your "
            "traffic safely through an encrypted SSH connection.\n\n"
            "Three modes are available - Proxy (system proxy over SSH), "
            "VPN (TUN) and Full VPN (a real system-wide tunnel via a virtual "
            "TUN adapter, so every application including Discord and Telegram "
            "is tunneled).\n\n"
            "Profiles can be exported / imported as .sshh files. A locked file "
            "is encrypted and its contents stay private - imported locked "
            "profiles are read-only and cannot be viewed or edited.")
        desc.setWordWrap(True); desc.setObjectName("statSub")
        cv.addWidget(desc); cv.addSpacing(16)
        gh = QLabel('Project repository: '
            f'<a style="color:{ACCENTS[self.theme]};" href="{GITHUB_URL}">'
            f'{GITHUB_URL}</a>')
        gh.setOpenExternalLinks(True); gh.setTextFormat(Qt.TextFormat.RichText)
        cv.addWidget(gh); cv.addSpacing(16)
        ct = QLabel("Special thanks")
        ct.setStyleSheet("font-size:15px;font-weight:800;color:#e9eefc;")
        cv.addWidget(ct)
        credits = QLabel(
            'Huge thanks to '
            '<a style="color:%s;" href="https://github.com/omidmousavi">'
            'Omid Mousavi (omidmousavi)</a> and '
            '<a style="color:%s;" href="https://github.com/mohsen-tahmasebi">'
            'Mohsen Tahmasebi (mohsen-tahmasebi)</a> for the original project '
            '<a style="color:%s;" href="https://github.com/omidmousavi/csharp-ssh-vpn">'
            'csharp-ssh-vpn</a>, which inspired SSHH.'
            % (ACCENTS[self.theme], ACCENTS[self.theme], ACCENTS[self.theme]))
        credits.setWordWrap(True); credits.setObjectName("statSub")
        credits.setOpenExternalLinks(True); credits.setTextFormat(Qt.TextFormat.RichText)
        cv.addWidget(credits); cv.addSpacing(16)
        ver = QLabel("SSHH v1.3  -  SOCKS5 + HTTP + Full VPN (tun2socks) over SSH  -  PyQt6")
        ver.setObjectName("statSub"); cv.addWidget(ver)
        v.addWidget(card); v.addStretch(1)
        return w

    # ---------- helpers ----------
    def log(self, msg):
        ts = time.strftime("%H:%M:%S")
        if hasattr(self, "log_box"):
            self.log_box.appendPlainText(f"[{ts}] {msg}")

    def apply_theme(self):
        self.setStyleSheet(stylesheet(self.theme, self.ui_scale))
        if hasattr(self, "bg"): self.bg.set_colors(BG[self.theme])
        if hasattr(self, "power"): self.power.set_accent(ACCENTS[self.theme])
        if hasattr(self, "chart"):
            self.chart.set_accent(ACCENTS[self.theme], ACCENTS2[self.theme])
        self.chip_mode.setText(self.mode); self._sync_mode_buttons()
        # rebuild About so its accent-colored text follows the theme
        if hasattr(self, "_about_index") and hasattr(self, "pages"):
            try:
                old = self.pages.widget(self._about_index)
                neww = self._page_about()
                self.pages.insertWidget(self._about_index, neww)
                self.pages.removeWidget(old); old.deleteLater()
            except Exception:
                pass

    def _change_theme(self, name):
        self.theme = name; profiles.set_setting("theme", name); self.apply_theme()

    def _apply_scale(self):
        self.ui_scale = round(self.scale_spin.value(), 2)
        profiles.set_setting("ui_scale", self.ui_scale)
        self.apply_theme(); self.log(f"UI scale set to {self.ui_scale}x")

    def _set_mode(self, mode):
        self.mode = mode; profiles.set_setting("mode", mode)
        self.chip_mode.setText(mode); self._sync_mode_buttons()

    def _sync_mode_buttons(self):
        if hasattr(self, "btn_proxy"):
            self.btn_proxy.setChecked(self.mode == "proxy")
            self.btn_vpn.setChecked(self.mode == "vpn")

    def _on_page_changed(self, idx):
        titles = [("Dashboard", "Overview & quick connect"),
                  ("Profiles", "Manage your SSH servers"),
                  ("Statistics", "Traffic & usage per profile"),
                  ("Logs", "Live application log"),
                  ("Settings", "Theme, scale & behaviour"),
                  ("About", "Info, credits & links")]
        self.page_title.setText(titles[idx][0])
        self.page_sub.setText(titles[idx][1])
        if idx == 2: self.refresh_stats()

    def _on_combo_changed(self, idx):
        pid = self.active_combo.currentData()
        if pid is None:
            self.active_info.setText("No profile selected."); return
        p = profiles.get_profile(pid)
        if p:
            addr = self._disp_addr(f"{p['host']}:{p['port']}")
            self.active_info.setText(
                f"{p['name']}\n{addr}   user: "
                f"{self._disp_addr(p['username'])}\nping: {p['last_ms']} ms")

    # ---------- profile CRUD ----------
    def _add_profile(self):
        d = BulkAddDialog(self)
        if d.exec():
            rows = d.results()
            if not rows:
                QMessageBox.warning(self, "SSHH", "Nothing to add."); return
            n = 0
            for data in rows:
                if not data["host"] or not data["username"]:
                    continue
                profiles.add_profile(**data); n += 1
            self.refresh_profiles(); self.refresh_totals()
            self.log(f"Added {n} profile(s)")
            if n == 0:
                QMessageBox.warning(self, "SSHH", "Host and username required.")

    def _edit_profile(self):
        pid = self._selected_pid()
        if pid is None: return
        p = profiles.get_profile(pid)
        ro = bool(p.get("locked"))
        d = ProfileDialog(self, p, read_only=ro)
        if ro:
            d.exec()  # view-only; ignore result
            return
        if d.exec():
            profiles.update_profile(pid, **d.data()); self.refresh_profiles()

    def _delete_profile(self):
        pid = self._selected_pid()
        if pid is None: return
        if QMessageBox.question(self, "SSHH", "Delete this profile?") \
                == QMessageBox.StandardButton.Yes:
            profiles.delete_profile(pid); self.refresh_profiles(); self.refresh_totals()

    def _delete_all(self):
        if not profiles.list_profiles():
            QMessageBox.information(self, "SSHH", "No profiles to delete."); return
        if QMessageBox.question(self, "SSHH",
            "Delete ALL profiles? This cannot be undone.") \
                == QMessageBox.StandardButton.Yes:
            profiles.delete_all_profiles()
            self.refresh_profiles(); self.refresh_totals()
            self.log("Deleted all profiles.")

    def _selected_pid(self):
        row = self.ptable.currentRow()
        if row < 0: return None
        item = self.ptable.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # ---------- import / export ----------
    def _ask_lock(self):
        """Return (locked: bool, password: str|None)."""
        lock = QMessageBox.question(
            self, "Lock file?",
            "Lock (encrypt) this file?\n\n"
            "Yes -> contents encrypted & NOT viewable after import (read-only).\n"
            "No  -> plain file you can view and edit later.")
        if lock != QMessageBox.StandardButton.Yes:
            return False, None
        # password is OPTIONAL
        use_pw = QMessageBox.question(
            self, "Password?",
            "Protect the locked file with a password too?\n"
            "(Optional - either way the file is encrypted.)")
        password = None
        if use_pw == QMessageBox.StandardButton.Yes:
            pw, ok = QInputDialog.getText(
                self, "Password", "Enter a password:", QLineEdit.EchoMode.Password)
            if ok and pw:
                password = pw
        return True, password

    def _do_export(self, plist, default_name):
        if not plist:
            QMessageBox.information(self, "SSHH", "No profiles to export."); return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export profiles", default_name, "SSHH files (*.sshh)")
        if not path: return
        if not path.lower().endswith(".sshh"): path += ".sshh"
        locked, password = self._ask_lock()
        try:
            profile_io.export_profiles(path, plist, locked=locked, password=password)
            self.log(f"Exported {len(plist)} profiles -> {os.path.basename(path)}"
                     + (" (locked)" if locked else ""))
            QMessageBox.information(self, "SSHH",
                f"Exported {len(plist)} profiles.\n"
                + ("Locked/encrypted." if locked else "Unlocked.")
                + (" (password set)" if password else ""))
        except Exception as e:
            QMessageBox.critical(self, "SSHH", f"Export failed:\n{e}")

    def _export_all(self):
        self._do_export(profiles.list_profiles(), "all_profiles.sshh")

    def _export_selected(self):
        pid = self._selected_pid()
        if pid is None:
            QMessageBox.information(self, "SSHH", "Select a profile first."); return
        p = profiles.get_profile(pid)
        if p.get("locked"):
            QMessageBox.information(self, "SSHH",
                "This profile is locked and cannot be re-exported."); return
        self._do_export([p], (p["name"] or "profile") + ".sshh")

    def _import_profiles(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import profiles", "", "SSHH files (*.sshh);;All files (*)")
        if not path: return
        try:
            locked, has_pw = profile_io.inspect(path)
        except Exception as e:
            QMessageBox.critical(self, "SSHH", f"Invalid file:\n{e}"); return
        password = None
        if locked and has_pw:
            pw, ok = QInputDialog.getText(
                self, "Locked file", "This file needs a password:",
                QLineEdit.EchoMode.Password)
            if not ok or not pw:
                QMessageBox.information(self, "SSHH", "Import cancelled."); return
            password = pw
        try:
            imported, was_locked = profile_io.import_profiles(path, password=password)
        except PermissionError as e:
            QMessageBox.critical(self, "SSHH", str(e)); return
        except Exception as e:
            QMessageBox.critical(self, "SSHH", f"Import failed:\n{e}"); return
        n = 0
        for p in imported:
            try:
                profiles.add_profile(
                    name=p.get("name", "Imported"), host=p.get("host", ""),
                    port=int(p.get("port", 22) or 22),
                    username=p.get("username", ""),
                    password=p.get("password", ""), key_path=p.get("key_path", ""),
                    locked=1 if was_locked else 0)
                n += 1
            except Exception:
                pass
        self.refresh_profiles(); self.refresh_totals()
        self.log(f"Imported {n} profiles from {os.path.basename(path)}"
                 + (" (locked / read-only)" if was_locked else ""))
        QMessageBox.information(self, "SSHH",
            f"Imported {n} profiles."
            + ("\nThese are LOCKED: read-only & not viewable." if was_locked else ""))

    def refresh_profiles(self):
        plist = profiles.list_profiles()
        self.ptable.setRowCount(len(plist))
        for r, p in enumerate(plist):
            lock_tag = " [locked]" if p.get("locked") else ""
            name = QTableWidgetItem(p["name"] + lock_tag)
            name.setData(Qt.ItemDataRole.UserRole, p["id"])
            self.ptable.setItem(r, 0, name)
            addr = "**** locked ****" if p.get("locked") else \
                   self._disp_addr(f"{p['host']}:{p['port']}")
            self.ptable.setItem(r, 1, QTableWidgetItem(addr))
            usr = "****" if p.get("locked") else self._disp_addr(p["username"])
            self.ptable.setItem(r, 2, QTableWidgetItem(usr))
            ms = p["last_ms"]
            self.ptable.setItem(r, 3, QTableWidgetItem(f"{ms} ms" if ms >= 0 else "-"))
            status = "ACTIVE" if p["id"] == self.active_id else \
                     ("UP" if p["last_ok"] else "-")
            self.ptable.setItem(r, 4, QTableWidgetItem(status))
            self.ptable.setItem(r, 5, QTableWidgetItem(
                fmt_bytes(p["total_down"] + p["total_up"])))
        cur = self.active_combo.currentData()
        self.active_combo.blockSignals(True); self.active_combo.clear()
        self.active_combo.addItem("- Select profile -", None)
        for p in plist:
            label = "**** locked ****" if p.get("locked") else f"({p['host']})"
            self.active_combo.addItem(f"{p['name']}  {label}", p["id"])
        if cur is not None:
            i = self.active_combo.findData(cur)
            if i >= 0: self.active_combo.setCurrentIndex(i)
        self.active_combo.blockSignals(False)

    # ---------- reset ----------
    def _reset_settings(self):
        if QMessageBox.question(self, "SSHH",
            "Reset ALL settings (theme, scale, mode, demo)?\n"
            "Profiles and traffic stats are kept.") \
                != QMessageBox.StandardButton.Yes:
            return
        profiles.reset_settings()
        self.theme = "blue"; self.mode = "proxy"; self.ui_scale = 1.0
        self.demo_mode = False
        self.scale_spin.setValue(1.0); self.theme_combo.setCurrentText("blue")
        self.eye_btn.setChecked(False); self.eye_btn.setText("(*) Hide IPs")
        self.apply_theme(); self.refresh_profiles()
        QMessageBox.information(self, "SSHH", "Settings reset.")

    def _reset_data(self):
        if QMessageBox.question(self, "SSHH",
            "Reset ALL traffic, uptime & session statistics?\n"
            "Profiles are kept, counters are zeroed.") \
                != QMessageBox.StandardButton.Yes:
            return
        profiles.reset_data()
        self._max_speed = 0.0
        self.refresh_profiles(); self.refresh_totals()
        if self.pages.currentIndex() == 2: self.refresh_stats()
        QMessageBox.information(self, "SSHH", "Data reset.")

    # ---------- pinging ----------
    def _ping_all_async(self):
        threading.Thread(target=self._ping_all, daemon=True).start()

    def _ping_all(self):
        for p in profiles.list_profiles():
            if p.get("locked"):
                continue  # don't probe locked hosts (kept private)
            ms = tcp_ping(p["host"], p["port"])
            profiles.set_ping(p["id"], ms, ms >= 0)
        QTimer.singleShot(0, self.refresh_profiles)

    # ---------- connection ----------
    def _toggle_connection(self):
        if self.tunnel and self.tunnel.is_alive():
            self._disconnect()
        else:
            self._connect_selected()

    def _connect_selected(self):
        pid = self.active_combo.currentData()
        if pid is None: pid = self._selected_pid()
        if pid is None:
            QMessageBox.information(self, "SSHH", "Select a profile first."); return
        if self.connecting: return
        if self.mode == "vpn" and not self.is_admin:
            QMessageBox.warning(self, "SSHH",
                f"{self.mode.upper()} mode needs Administrator. Restart as admin, "
                "or use Proxy mode.")
            return
        p = profiles.get_profile(pid)
        self.connecting = True
        self.power.set_state(False, connecting=True)
        self.power_status.setText("Connecting...")
        self.log(f"Connecting to {p['name']} in {self.mode} mode ...")
        threading.Thread(target=self._do_connect, args=(p,), daemon=True).start()

    def _do_connect(self, p):
        try:
            t = SSHTunnel(p["host"], p["port"], p["username"], p["password"],
                          p["key_path"], local_port=LOCAL_PORT, http_port=HTTP_PORT)
            t.connect()
            self.tunnel = t; self.active_id = p["id"]
            self._last_persist_down = 0; self._last_persist_up = 0
            self._last_uptime_persist = 0

            if self.mode == "vpn" and tun_available():
                self.tun = TunMode("127.0.0.1", LOCAL_PORT); self.tun.start()
            else:
                win_proxy.set_proxy("127.0.0.1", HTTP_PORT, LOCAL_PORT)

            profiles.bump_session(p["id"]); self.stats.begin()
            self.sig_connected.emit(True, p["name"])
        except Exception as e:
            self.sig_connected.emit(False, str(e))

    def _on_connect_result(self, ok, msg):
        self.connecting = False
        if ok:
            self.power.set_state(True)
            label = {"vpn": "VPN Active",
                     "proxy": "Proxy Active"}.get(self.mode, "Connected")
            self.power_status.setText(label)
            self.power_sub.setText("Tap to disconnect")
            shown = self._disp_addr(msg)
            self.conn_dot.setText("Connected: " + shown)
            self.conn_dot.setStyleSheet(f"color:{ACCENTS[self.theme]};font-size:12px;")
            self.log(f"Connected ({self.mode}): {msg}")
            notify.notify("SSHH connected",
                          f"{label} - {self._disp_addr(msg)}",
                          self.notify_enabled)
            self.refresh_profiles(); self.refresh_totals()
        else:
            self.power.set_state(False)
            self.power_status.setText("Disconnected")
            self.power_sub.setText("Tap to connect")
            self.log(f"Connect failed: {msg}")
            QMessageBox.critical(self, "SSHH", f"Connection failed:\n{msg}")
            self._cleanup_network()

    def _disconnect(self):
        self.log("Disconnecting...")
        self._persist_traffic(force=True)
        self._persist_uptime(force=True)
        self._cleanup_network()
        if self.tunnel: self.tunnel.close(); self.tunnel = None
        self.active_id = None
        self.power.set_state(False)
        self.power_status.setText("Disconnected")
        self.power_sub.setText("Tap to connect")
        self.conn_dot.setText("Disconnected")
        self.conn_dot.setStyleSheet("color:#6b7a99;font-size:12px;")
        notify.notify("SSHH disconnected", "Tunnel closed.",
                      self.notify_enabled)
        self.refresh_profiles(); self.refresh_totals()

    def _cleanup_network(self):
        if self.tun: self.tun.stop(); self.tun = None
        win_proxy.clear_proxy()

    def _force_clear(self):
        self._disconnect(); win_proxy.clear_proxy()
        QMessageBox.information(self, "SSHH", "Disconnected & system proxy cleared.")

    def _persist_traffic(self, force=False):
        if not (self.tunnel and self.active_id): return
        c = self.tunnel.counter
        dd = c.down - self._last_persist_down
        du = c.up - self._last_persist_up
        if dd < 0: dd = 0
        if du < 0: du = 0
        if force or dd > 65536 or du > 65536:
            if dd or du:
                profiles.add_traffic(self.active_id, dd, du)
                self._last_persist_down = c.down
                self._last_persist_up = c.up

    def _persist_uptime(self, force=False):
        """Accumulate session uptime into the profile's total_uptime."""
        if not (self.tunnel and self.active_id): return
        up = self.stats.uptime()
        delta = up - self._last_uptime_persist
        if delta <= 0: return
        if force or delta >= 5:
            profiles.add_uptime(self.active_id, delta)
            self._last_uptime_persist = up

    # ---------- tick ----------
    def _tick(self):
        if self.tunnel and self.tunnel.is_alive():
            c = self.tunnel.counter
            self.stats.tick(c.down, c.up)
            cur_speed = self.stats.speed_down + self.stats.speed_up
            if cur_speed > self._max_speed:
                self._max_speed = cur_speed
            self.card_down.set(fmt_speed(self.stats.speed_down),
                               "Session: " + fmt_bytes(self.stats.session_down))
            self.card_up.set(fmt_speed(self.stats.speed_up),
                             "Session: " + fmt_bytes(self.stats.session_up))
            self.card_uptime.set(fmt_time(self.stats.uptime()),
                                 f"avg {self.stats.avg_speed_mbps():.2f} MB/s")
            self.chart.set_data(self.stats.history)
            self._persist_traffic()
            self._persist_uptime()
            self.refresh_totals()
            if self.pages.currentIndex() == 2:
                self.refresh_stats()
        elif self.tunnel and not self.tunnel.is_alive():
            self.log("Connection dropped.")
            prof = profiles.get_profile(self.active_id) if self.active_id else None
            self._disconnect()
            if self.auto_reconnect and prof:
                self.log("Auto-reconnect in 3s...")
                QTimer.singleShot(3000, lambda p=prof: self._reconnect_to(p))

    def refresh_stats(self):
        plist = profiles.list_profiles()
        td = sum(p["total_down"] for p in plist)
        tu = sum(p["total_up"] for p in plist)
        sess = sum(p["sessions"] for p in plist)
        self.s_total_down.set(fmt_bytes(td))
        self.s_total_up.set(fmt_bytes(tu))
        self.s_sessions.set(str(sess))
        avg = self.stats.avg_speed_mbps() if self.tunnel else 0
        self.s_avg.set(f"{avg:.2f}")
        self.stable.setRowCount(len(plist))
        for r, p in enumerate(plist):
            self.stable.setItem(r, 0, QTableWidgetItem(p["name"]))
            addr = "**** locked ****" if p.get("locked") else self._disp_addr(p["host"])
            self.stable.setItem(r, 1, QTableWidgetItem(addr))
            self.stable.setItem(r, 2, QTableWidgetItem(str(p["sessions"])))
            self.stable.setItem(r, 3, QTableWidgetItem(fmt_bytes(p["total_down"])))
            self.stable.setItem(r, 4, QTableWidgetItem(fmt_bytes(p["total_up"])))
            self.stable.setItem(r, 5, QTableWidgetItem(
                fmt_bytes(p["total_down"] + p["total_up"])))


    def _show_diagnostics(self):
        pid = self.active_combo.currentData()
        prof = profiles.get_profile(pid) if pid else None
        try:
            report = diagnostics.collect(
                tunnel=self.tunnel, fullvpn=None,
                mode=self.mode, profile=prof)
        except Exception as e:
            report = f"Diagnostics error: {e}"
        dlg = QDialog(self); dlg.setWindowTitle("Diagnostics / Troubleshoot")
        dlg.setMinimumSize(760, 560); dlg.setStyleSheet(self.styleSheet())
        v = QVBoxLayout(dlg)
        box = QPlainTextEdit(); box.setReadOnly(True); box.setPlainText(report)
        box.setStyleSheet("font-family:Consolas;font-size:12px;color:#cad6ea;")
        v.addWidget(box)
        row = QHBoxLayout()
        copy = QPushButton("Copy to clipboard"); copy.setProperty("class", "btn primary")
        save = QPushButton("Save to file"); save.setProperty("class", "btn")
        close = QPushButton("Close"); close.setProperty("class", "btn")
        def _copy():
            QApplication.clipboard().setText(report)
            self.log("Diagnostics copied to clipboard.")
        def _save():
            path, _ = QFileDialog.getSaveFileName(
                dlg, "Save report", "sshh_diagnostics.txt", "Text (*.txt)")
            if path:
                with open(path, "w", encoding="utf-8") as f: f.write(report)
                self.log(f"Diagnostics saved -> {path}")
        copy.clicked.connect(_copy); save.clicked.connect(_save)
        close.clicked.connect(dlg.accept)
        row.addWidget(copy); row.addWidget(save); row.addStretch(1); row.addWidget(close)
        v.addLayout(row)
        dlg.exec()

    def _toggle_notify(self, state):
        self.notify_enabled = bool(state)
        profiles.set_setting("notify", self.notify_enabled)

    def _toggle_kill_switch(self, state):
        self.kill_switch = bool(state)
        profiles.set_setting("kill_switch", self.kill_switch)

    def _toggle_auto_reconnect(self, state):
        self.auto_reconnect = bool(state)
        profiles.set_setting("auto_reconnect", self.auto_reconnect)

    def _set_layout_mode(self, mode):
        self.layout_mode = mode
        profiles.set_setting("layout_mode", mode)
        self._apply_layout_mode()

    def _apply_layout_mode(self):
        if getattr(self, "layout_mode", "horizontal") == "vertical":
            self.resize(560, 940)
        else:
            self.resize(1180, 760)

    def _reconnect_to(self, prof):
        if self.tunnel and self.tunnel.is_alive(): return
        i = self.active_combo.findData(prof["id"])
        if i >= 0: self.active_combo.setCurrentIndex(i)
        self._connect_selected()

    def closeEvent(self, e):
        self._persist_traffic(force=True)
        self._persist_uptime(force=True)
        self._cleanup_network()
        if self.tunnel: self.tunnel.close()
        e.accept()
