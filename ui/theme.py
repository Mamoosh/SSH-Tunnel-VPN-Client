THEMES = {
    # --- originals ---
    "blue":     {"accent": "#4f8cff", "accent2": "#7db1ff", "bg1": "#0a0f1a", "bg2": "#16294d", "bg3": "#0d1730"},
    "violet":   {"accent": "#8b5cf6", "accent2": "#a78bfa", "bg1": "#0d0a18", "bg2": "#2b1b54", "bg3": "#150f30"},
    "emerald":  {"accent": "#10b981", "accent2": "#34d399", "bg1": "#06120f", "bg2": "#063a2c", "bg3": "#0a241c"},
    "cyan":     {"accent": "#06b6d4", "accent2": "#38e0f0", "bg1": "#06141a", "bg2": "#0a3a48", "bg3": "#08222c"},
    "rose":     {"accent": "#f43f5e", "accent2": "#fb7185", "bg1": "#160810", "bg2": "#4a0f24", "bg3": "#2a0a18"},
    "amber":    {"accent": "#f59e0b", "accent2": "#fbbf24", "bg1": "#161002", "bg2": "#3f2706", "bg3": "#241702"},
    "midnight": {"accent": "#6366f1", "accent2": "#818cf8", "bg1": "#04061a", "bg2": "#161a52", "bg3": "#0a0d30"},
    "sunset":   {"accent": "#fb7138", "accent2": "#fbb03b", "bg1": "#160a05", "bg2": "#4a2008", "bg3": "#2a1206"},
    "red":      {"accent": "#ef4444", "accent2": "#f87171", "bg1": "#160404", "bg2": "#3b0a0a", "bg3": "#220606"},
    # --- 10 new themes ---
    "hacker":   {"accent": "#22ff66", "accent2": "#7dff9e", "bg1": "#000800", "bg2": "#021a06", "bg3": "#001003"},
    "matrix":   {"accent": "#00ff9c", "accent2": "#5effc4", "bg1": "#000000", "bg2": "#031208", "bg3": "#010a05"},
    "rainbow":  {"accent": "#ff4fd8", "accent2": "#4fd2ff", "bg1": "#0d0716", "bg2": "#2a0e3a", "bg3": "#101030"},
    "ocean":    {"accent": "#2dd4bf", "accent2": "#5eead4", "bg1": "#04141a", "bg2": "#053742", "bg3": "#082530"},
    "lava":     {"accent": "#ff5722", "accent2": "#ff8a50", "bg1": "#1a0600", "bg2": "#3d1100", "bg3": "#260a00"},
    "gold":     {"accent": "#ffd24a", "accent2": "#ffe487", "bg1": "#14100200"[:7], "bg2": "#332702", "bg3": "#1f1801"},
    "ice":      {"accent": "#7dd3fc", "accent2": "#bae6fd", "bg1": "#04101a", "bg2": "#0a2740", "bg3": "#071a2c"},
    "neon":     {"accent": "#e837ff", "accent2": "#ff6bf0", "bg1": "#0a0014", "bg2": "#240040", "bg3": "#16002a"},
    "slate":    {"accent": "#94a3b8", "accent2": "#cbd5e1", "bg1": "#0b0f17", "bg2": "#1e293b", "bg3": "#131a26"},
    "crimson":  {"accent": "#dc143c", "accent2": "#ff4d6d", "bg1": "#16030700"[:7], "bg2": "#400512", "bg3": "#26040b"},
    # --- 5 light themes ---
    "light":      {"accent": "#2563eb", "accent2": "#3b82f6", "bg1": "#eef2f9", "bg2": "#dde6f5", "bg3": "#e7edf7"},
    "snow":       {"accent": "#0ea5e9", "accent2": "#38bdf8", "bg1": "#f4f8fc", "bg2": "#e3eef7", "bg3": "#edf4fa"},
    "mint":       {"accent": "#059669", "accent2": "#10b981", "bg1": "#eef9f3", "bg2": "#d7f0e3", "bg3": "#e6f6ee"},
    "sand":       {"accent": "#d97706", "accent2": "#f59e0b", "bg1": "#faf6ef", "bg2": "#f1e7d6", "bg3": "#f6efe3"},
    "rosewater":  {"accent": "#e11d48", "accent2": "#f43f5e", "bg1": "#fcf2f4", "bg2": "#f7dde3", "bg3": "#fae8ec"},
}
# sanitize any accidental long hex
for _k, _v in THEMES.items():
    for _c in ("bg1", "bg2", "bg3", "accent", "accent2"):
        if len(_v[_c]) > 7:
            _v[_c] = _v[_c][:7]

def stylesheet(name="blue", scale=1.0):
    t = THEMES.get(name, THEMES["blue"])
    a, a2 = t["accent"], t["accent2"]
    _light = name in {"light", "snow", "mint", "sand", "rosewater"}
    txt_main = "#1e293b" if _light else "#e9eefc"
    txt_sub  = "#64748b" if _light else "#6b7a99"
    card_bg  = "rgba(255,255,255,0.75)" if _light else "rgba(22,28,43,0.62)"
    side_bg  = "rgba(255,255,255,0.82)" if _light else "rgba(13,17,28,0.72)"
    field_bg = "rgba(0,0,0,0.05)" if _light else "rgba(0,0,0,0.28)"
    s = float(scale or 1.0)
    def px(v):
        return max(1, int(round(v * s)))
    f_menu  = px(14); f_title = px(24); f_sub = px(13)
    f_stat  = px(28); f_lbl = px(11);  f_body = px(13)
    pad_v   = px(9);  pad_h = px(16)
    return f"""
    * {{ font-family: "Segoe UI", "Inter", "Arial", sans-serif;
         color: {txt_main}; outline: none; font-size: {f_body}px; }}
    QMainWindow {{ background: transparent; }}
    #root {{ background: transparent; }}

    #sidebar {{ background: {side_bg};
                border-right: 1px solid rgba(255,255,255,0.06); }}
    #logoText {{ font-size: {px(20)}px; font-weight: 800; color: {a};
                 letter-spacing: 3px; }}

    QPushButton#menuItem {{ background: transparent; border: none;
        color: #97a3bf; padding: {px(12)}px {pad_h}px; border-radius: 10px;
        text-align: left; font-size: {f_menu}px; font-weight: 600; }}
    QPushButton#menuItem:hover {{ background: rgba(255,255,255,0.06);
        color: #ffffff; }}
    /* === THE REAL FIX ===
       The selected sidebar tab now derives its highlight from THIS theme's
       accent (a) for the left border AND a translucent accent fill, instead
       of the old hard-coded gradient that always looked greenish/blue. */
    QPushButton#menuItem:checked {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {a2}, stop:0.85 {a}55, stop:1 transparent);
        color: #ffffff; border-left: 4px solid {a};
        font-weight: 800; }}

    #main {{ background: rgba(10,14,21,0.35); }}
    #pageTitle {{ font-size: {f_title}px; font-weight: 800; }}
    #pageSub {{ color: #6b7a99; font-size: {f_sub}px; }}

    QFrame#card {{ background: {card_bg};
        border: 1px solid rgba(255,255,255,0.07); border-radius: 16px; }}
    QFrame#totalsCard {{ background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; }}

    QPushButton.btn {{ background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.09); border-radius: 10px;
        padding: {pad_v}px {pad_h}px; font-size: {f_body}px; font-weight: 600; }}
    QPushButton.btn:hover {{ background: rgba(255,255,255,0.12); }}
    QPushButton.primary {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 {a}, stop:1 {a2}); border: none; color: #ffffff; }}
    QPushButton.primary:hover {{ background: {a2}; }}
    QPushButton.danger {{ background: #d23b4e; border: none; color: #fff; }}
    QPushButton.danger:hover {{ background: #e25668; }}
    QPushButton.btn:checked {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
            stop:0 {a}, stop:1 {a2});
        border: 1px solid {a2}; color: #ffffff; font-weight: 700; }}

    QPushButton.chip {{ background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.08); border-radius: 9px;
        padding: {px(5)}px {px(12)}px; font-size: {px(12)}px; color: #97a3bf; }}

    QLineEdit, QSpinBox, QComboBox, QDoubleSpinBox {{ background: {field_bg};
        border: 1px solid rgba(255,255,255,0.09); border-radius: 9px;
        padding: {pad_v}px {px(11)}px; font-size: {f_body}px; }}
    QLineEdit:focus, QComboBox:focus {{ border-color: {a}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{ background: #141a29;
        border: 1px solid rgba(255,255,255,0.1);
        selection-background-color: {a}; border-radius: 8px; }}

    QLabel#statLabel {{ color: #7b88a6; font-size: {f_lbl}px; font-weight: 700;
        letter-spacing: 1.2px; }}
    QLabel#statVal {{ font-size: {f_stat}px; font-weight: 800; }}
    QLabel#statSub {{ color: #6b7a99; font-size: {px(12)}px; }}
    QLabel#totLabel {{ color: #7b88a6; font-size: {px(10)}px; font-weight: 700;
        letter-spacing: 0.4px; }}
    QLabel#totVal {{ color: #e9eefc; font-size: {px(12)}px; font-weight: 700; }}

    QTableWidget {{ background: rgba(22,28,43,0.45);
        border: 1px solid rgba(255,255,255,0.07); border-radius: 14px;
        gridline-color: rgba(255,255,255,0.04); font-size: {f_body}px; }}
    QTableWidget::item {{ padding: 4px; }}
    QHeaderView::section {{ background: transparent; color: #7b88a6;
        border: none; border-bottom: 1px solid rgba(255,255,255,0.06);
        padding: 10px; font-weight: 700; font-size: {f_lbl}px; }}
    QTableWidget::item:selected {{ background: {a}; color: #fff; }}
    QTableWidget QTableCornerButton::section {{ background: transparent; }}

    QPlainTextEdit, QTextEdit {{ background: rgba(0,0,0,0.35);
        border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; }}

    QScrollBar:vertical {{ background: transparent; width: 9px; margin: 4px; }}
    QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.14);
        border-radius: 4px; min-height: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    """

LIGHT_THEMES_SET = {"light", "snow", "mint", "sand", "rosewater"}

ACCENTS = {k: v["accent"] for k, v in THEMES.items()}
ACCENTS2 = {k: v["accent2"] for k, v in THEMES.items()}
BG = {k: (v["bg1"], v["bg2"], v["bg3"]) for k, v in THEMES.items()}
