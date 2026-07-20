#!/usr/bin/env python3
"""
Tailscale GUI - Ultimate muOS Edition (Fixed Paths)
RG35XX H / RG40XXV (640x480)
Uses SDL2 via ctypes - Pure Python, Zero pip dependencies
Optimized by IR Minoru / SPDW Factory Lab
"""

import ctypes
import ctypes.util
import subprocess
import os
import sys
import json
import threading
import time
import datetime
import math
import random

# --- CONFIGURAZIONE PATH LOCALI ---
APP_VERSION = "3.0.4"
W, H = 640, 480
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(SCRIPT_DIR, "font.ttf")
LOGO_PATH = os.path.join(SCRIPT_DIR, "tailscale.png")
LOG_FILE = os.path.join(SCRIPT_DIR, "error_log.txt")

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write("%s: %s\n" % (datetime.datetime.now(), msg))
    print(msg)

# --- QR Code Generator (Reed-Solomon Pure Python) ---------------------------

_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x; _LOG[_x] = _i
    _x <<= 1
    if _x & 256: _x ^= 0x11D
for _i in range(255, 512): _EXP[_i] = _EXP[_i - 255]

def _mul(a, b):
    return 0 if not a or not b else _EXP[_LOG[a] + _LOG[b]]

def _rs_enc(data, n_ec):
    g = [1]
    for i in range(n_ec):
        ng = [0] * (len(g) + 1)
        for j, gj in enumerate(g):
            ng[j]   ^= gj
            ng[j+1] ^= _mul(gj, _EXP[i])
        g = ng
    msg = list(data) + [0] * n_ec
    for i in range(len(data)):
        c = msg[i]
        if c:
            for j in range(len(g)):
                msg[i + j] ^= _mul(g[j], c)
    return msg[len(data):]

_CAP = {
    1:  (14,  10, 1, 16, 0,  0),
    2:  (26,  16, 1, 28, 0,  0),
    3:  (42,  26, 1, 44, 0,  0),
    4:  (62,  18, 2, 32, 0,  0),
    5:  (84,  24, 2, 43, 0,  0),
    6:  (106, 16, 4, 27, 0,  0),
    7:  (122, 18, 4, 31, 0,  0),
    8:  (152, 22, 2, 38, 2, 39),
    9:  (180, 22, 3, 36, 2, 37),
    10: (214, 26, 4, 43, 1, 44),
}

def _pick_version(n):
    for v, cap in _CAP.items():
        if cap[0] >= n:
            return v
    raise ValueError("data too long")

def _make_codewords(data_bytes, version):
    max_dc, ec, nb1, dc1, nb2, dc2 = _CAP[version]
    total_dc = nb1 * dc1 + nb2 * dc2
    bits = []
    def ab(v, l):
        for i in range(l - 1, -1, -1): bits.append((v >> i) & 1)

    ab(4, 4)
    ab(len(data_bytes), 8)
    for b in data_bytes: ab(b, 8)
    cap_bits = total_dc * 8
    for _ in range(min(4, cap_bits - len(bits))): bits.append(0)
    while len(bits) % 8: bits.append(0)
    pi = 0
    while len(bits) < cap_bits:
        ab([0xEC, 0x11][pi & 1], 8); pi += 1

    cw = [int(''.join(str(b) for b in bits[i*8:(i+1)*8]), 2)
          for i in range(total_dc)]

    pos = 0
    dblks, eblks = [], []
    for _ in range(nb1):
        blk = cw[pos:pos+dc1]; dblks.append(blk)
        eblks.append(_rs_enc(blk, ec)); pos += dc1
    for _ in range(nb2):
        blk = cw[pos:pos+dc2]; dblks.append(blk)
        eblks.append(_rs_enc(blk, ec)); pos += dc2

    final = []
    for i in range(max(len(b) for b in dblks)):
        for b in dblks:
            if i < len(b): final.append(b[i])
    for i in range(ec):
        for b in eblks:
            if i < len(b): final.append(b[i])
    return final

_FMT = {
    0: 0b101010000010010, 1: 0b101000100100101, 2: 0b101111001111100, 3: 0b101101101001011,
    4: 0b100010111111001, 5: 0b100000011001110, 6: 0b100111110010111, 7: 0b100101010100000,
}

_ALIGN = {
    2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34],
    7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50],
}

_MASKS = [
    lambda r, c: (r + c) % 2 == 0, lambda r, c: r % 2 == 0, lambda r, c: c % 3 == 0,
    lambda r, c: (r + c) % 3 == 0, lambda r, c: (r // 2 + c // 3) % 2 == 0,
    lambda r, c: (r * c) % 2 + (r * c) % 3 == 0, lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
    lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
]

def _place_finder(mat, r, c):
    pat = [
        [1,1,1,1,1,1,1], [1,0,0,0,0,0,1], [1,0,1,1,1,0,1], [1,0,1,1,1,0,1],
        [1,0,1,1,1,0,1], [1,0,0,0,0,0,1], [1,1,1,1,1,1,1],
    ]
    sz = len(mat)
    for dr in range(7):
        for dc in range(7):
            nr, nc = r + dr, c + dc
            if 0 <= nr < sz and 0 <= nc < sz:
                mat[nr][nc] = pat[dr][dc]
    for dr in range(-1, 8):
        for dc in range(-1, 8):
            if 0 <= dr <= 6 and 0 <= dc <= 6: continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < sz and 0 <= nc < sz and mat[nr][nc] is None:
                mat[nr][nc] = 0

def _place_align(mat, cr, cc):
    pat = [
        [1,1,1,1,1], [1,0,0,0,1], [1,0,1,0,1], [1,0,0,0,1], [1,1,1,1,1],
    ]
    for dr in range(-2, 3):
        for dc in range(-2, 3):
            mat[cr + dr][cc + dc] = pat[dr + 2][dc + 2]

def _place_format(mat, sz, mask_id):
    f = _FMT[mask_id]
    bits = [(f >> (14 - i)) & 1 for i in range(15)]
    for i, c in enumerate([0, 1, 2, 3, 4, 5, 7, 8]): mat[8][c] = bits[i]
    for i, r in enumerate([7, 5, 4, 3, 2, 1, 0]): mat[r][8] = bits[8 + i]
    mat[sz - 8][8] = 1
    for i in range(8): mat[8][sz - 8 + i] = bits[7 - i]
    for i in range(7): mat[sz - 7 + i][8] = bits[8 + i]

def _place_data(mat, codewords, sz, mask_fn):
    bits = []
    for cw in codewords:
        for i in range(7, -1, -1): bits.append((cw >> i) & 1)
    bi = 0
    col = sz - 1
    going_up = True
    while col > 0:
        if col == 6: col -= 1
        rows = range(sz - 1, -1, -1) if going_up else range(sz)
        for row in rows:
            for dc in (0, 1):
                c = col - dc
                if mat[row][c] is None:
                    bit = bits[bi] if bi < len(bits) else 0
                    bi += 1
                    mat[row][c] = bit ^ (1 if mask_fn(row, c) else 0)
        col -= 2
        going_up = not going_up

def build_qr(text):
    data = text.encode('iso-8859-1')
    version = _pick_version(len(data))
    sz = version * 4 + 17
    codewords = _make_codewords(data, version)
    best_mat, best_score = None, 10**9

    for mask_id in range(8):
        mat = [[None] * sz for _ in range(sz)]
        _place_finder(mat, 0, 0); _place_finder(mat, 0, sz - 7); _place_finder(mat, sz - 7, 0)
        ap = _ALIGN.get(version, [])
        for ar in ap:
            for ac in ap:
                if (ar <= 8 and ac <= 8) or (ar <= 8 and ac >= sz - 9) or (ar >= sz - 9 and ac <= 8): continue
                _place_align(mat, ar, ac)
        for i in range(8, sz - 8):
            if mat[6][i] is None: mat[6][i] = i % 2 == 0
            if mat[i][6] is None: mat[i][6] = i % 2 == 0
        mat[sz - 8][8] = 1
        _place_format(mat, sz, mask_id)
        _place_data(mat, codewords, sz, _MASKS[mask_id])
        for r in range(sz):
            for c in range(sz):
                if mat[r][c] is None: mat[r][c] = 0
        best_mat = [row[:] for row in mat]
        break
    return best_mat

# --- System & Tailscale Core Commands ----------------------------------------

def is_wifi_connected():
    try:
        with open("/sys/class/net/wlan0/operstate", "r") as f:
            return f.read().strip() == "up"
    except:
        return False

def is_daemon_running():
    try:
        return subprocess.call(["pidof", "tailscaled"], stdout=subprocess.DEVNULL) == 0
    except:
        return False

TS     = "/opt/muos/bin/tailscale"
SOCKET = "/run/tailscale/tailscaled.sock"

def ts_run(*args, timeout=8):
    try:
        r = subprocess.run([TS, "--socket=" + SOCKET] + list(args), capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip()
    except Exception as e: return "", str(e)

def ts_get_state():
    out, _ = ts_run("status", "--json", timeout=3)
    try: return json.loads(out).get("BackendState", "unknown")
    except: return "unknown"

def ts_status_json():
    out, _ = ts_run("status", "--json", timeout=4)
    try: return json.loads(out)
    except: return {}

def ts_netcheck_json():
    out, _ = ts_run("netcheck", "--json", timeout=10)
    try: return json.loads(out)
    except: return {}

def ts_receive_files_to(directory):
    out, err = ts_run("file", "get", directory + "/", timeout=30)
    return out or err

def ts_send_file(target, filepath):
    out, err = ts_run("file", "cp", filepath, target + ":", timeout=30)
    return out or err

def ts_connect(use_ssh=False):
    import re
    url_re = re.compile(r'https://login\.tailscale\.com/\S+')
    args = ["up", "--accept-dns=true", "--accept-routes=true"]
    if use_ssh:
        args.append("--ssh=true")
    
    try:
        proc = subprocess.Popen([TS, "--socket=" + SOCKET] + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        url, msg, done_ev = None, "", threading.Event()
        def _reader():
            nonlocal url, msg
            try:
                for line in proc.stdout:
                    line = line.strip()
                    if not line: continue
                    m = url_re.search(line)
                    if m: url = m.group(0); done_ev.set(); return
                    msg = line
            finally: done_ev.set()
        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        done_ev.wait(timeout=15)
        if url: return url, msg
        proc.wait(timeout=3)
        if ts_get_state() == "Running": return None, "Connected successfully."
        return None, msg or "No response from tailscale up."
    except Exception as e: return None, str(e)

def ts_down(): return ts_run("down", timeout=5)

def ts_logout():
    try:
        proc = subprocess.Popen([TS, "--socket=" + SOCKET, "logout"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try: proc.communicate(timeout=4)
        except subprocess.TimeoutExpired: proc.kill(); return "logout sent"
        return "logged out"
    except Exception as e: return str(e)

def ts_set_exit_node(node_ip_or_empty):
    if node_ip_or_empty:
        return ts_run("set", "--exit-node=" + node_ip_or_empty, "--exit-node-allow-lan-access=true", timeout=8)
    return ts_run("set", "--exit-node=", timeout=8)

def ts_toggle_ssh(enable_ssh):
    return ts_run("set", f"--ssh={'true' if enable_ssh else 'false'}", timeout=8)

def ts_ping(target):
    return ts_run("ping", "-c", "1", target, timeout=8)

def ts_version():
    out, _ = ts_run("version", timeout=3)
    return out.splitlines()[0].strip() if out else "Unknown"

# --- SDL2 Setup --------------------------------------------------------------

# --- SDL2 E LIBRERIE ---
try:
    SDL2 = ctypes.CDLL("libSDL2-2.0.so.0")
    SDL2_TTF = ctypes.CDLL("libSDL2_ttf-2.0.so.0")
    SDL2_IMAGE = ctypes.CDLL("libSDL2_image-2.0.so.0")
    SDL2_TTF.TTF_SetFontStyle.argtypes = [ctypes.c_void_p, ctypes.c_int]
    SDL2_IMAGE.IMG_Init(0x00000002)
    SDL2_IMAGE.IMG_Load.restype = ctypes.c_void_p
    SDL2_IMAGE.IMG_Load.argtypes = [ctypes.c_char_p]
except Exception as e:
    log("ERRORE LIBRERIE: %s" % e)
    sys.exit(1)

SDL_INIT_VIDEO, SDL_INIT_JOYSTICK, SDL_INIT_GAMECONTROLLER = 0x00000020, 0x00000200, 0x00002000
SDL_WINDOW_SHOWN = 0x00000004
SDL_RENDERER_ACCELERATED, SDL_RENDERER_SOFTWARE = 0x00000002, 0x00000001
SDL_QUIT, SDL_KEYDOWN, SDL_JOYBUTTONDOWN = 0x100, 0x300, 0x603
SDL_JOYAXISMOTION, SDL_JOYHATMOTION = 0x600, 0x602

SDLK_UP, SDLK_DOWN, SDLK_LEFT, SDLK_RIGHT = 1073741906, 1073741905, 1073741904, 1073741903
SDLK_RETURN, SDLK_ESCAPE, SDLK_SPACE, SDLK_a, SDLK_b, SDLK_x, SDLK_y = 13, 27, 32, 97, 98, 120, 121

BTN_A, BTN_B, BTN_X, BTN_Y = 3, 4, 2, 5
BTN_L1, BTN_R1, BTN_START = 6, 7, 11
HAT_UP, HAT_DOWN, HAT_LEFT, HAT_RIGHT = 1, 4, 8, 2

W, H = 640, 480

# --- Theme Engine -----------------------------------------------------------

THEMES = {
    "tailscale": {
        "BG": (28, 28, 30, 255), "BG2": (36, 36, 38, 255), "PANEL": (44, 44, 46, 255),
        "BORDER": (60, 60, 64, 255), "TEXT": (250, 250, 250, 255), "TEXT_DIM": (170, 170, 175, 255),
        "ACCENT": (75, 81, 198, 255), "GREEN": (46, 170, 95, 255), "RED": (235, 87, 87, 255),
        "ORANGE": (242, 153, 74, 255), "SEL_BG": (58, 58, 60, 255), "SEL_TEXT": (255, 255, 255, 255),
        "SELECTED": (75, 81, 198, 180), "MAGENTA": (140, 110, 220, 255),
        "HUD": False, "SCAN": False,
    },
    "spdw": {
        "BG": (10, 10, 16, 255), "BG2": (15, 15, 24, 255), "PANEL": (18, 18, 28, 255),
        "BORDER": (0, 255, 204, 140), "TEXT": (220, 255, 250, 255), "TEXT_DIM": (110, 150, 150, 255),
        "ACCENT": (0, 255, 204, 255), "GREEN": (60, 255, 160, 255), "RED": (255, 60, 110, 255),
        "ORANGE": (255, 180, 40, 255), "SEL_BG": (35, 20, 45, 255), "SEL_TEXT": (255, 255, 255, 255),
        "SELECTED": (255, 0, 255, 160), "MAGENTA": (255, 0, 255, 255),
        "HUD": True, "SCAN": True,
    },
    "hybrid": {
        "BG": (16, 16, 21, 255), "BG2": (23, 23, 30, 255), "PANEL": (27, 27, 35, 255),
        "BORDER": (0, 210, 190, 120), "TEXT": (245, 245, 250, 255), "TEXT_DIM": (150, 160, 170, 255),
        "ACCENT": (0, 220, 190, 255), "GREEN": (46, 190, 110, 255), "RED": (235, 87, 87, 255),
        "ORANGE": (242, 153, 74, 255), "SEL_BG": (38, 38, 48, 255), "SEL_TEXT": (255, 255, 255, 255),
        "SELECTED": (0, 220, 190, 160), "MAGENTA": (255, 0, 190, 255),
        "HUD": True, "SCAN": False,
    },
}
THEME_ORDER = ["tailscale", "spdw", "hybrid"]
THEME_NAMES = {"tailscale": "Tailscale Classic", "spdw": "SPDW Cyberpunk", "hybrid": "SPDW Hybrid"}
CURRENT_THEME = "hybrid"

def apply_theme(name):
    global CURRENT_THEME, THEME_HUD, THEME_SCAN
    global C_BG, C_BG2, C_PANEL, C_BORDER, C_TEXT, C_TEXT_DIM
    global C_ACCENT, C_GREEN, C_RED, C_ORANGE, C_SEL_BG, C_SEL_TEXT, C_SELECTED, C_MAGENTA
    t = THEMES.get(name, THEMES["hybrid"])
    CURRENT_THEME = name if name in THEMES else "hybrid"
    C_BG, C_BG2, C_PANEL, C_BORDER = t["BG"], t["BG2"], t["PANEL"], t["BORDER"]
    C_TEXT, C_TEXT_DIM = t["TEXT"], t["TEXT_DIM"]
    C_ACCENT, C_GREEN, C_RED, C_ORANGE = t["ACCENT"], t["GREEN"], t["RED"], t["ORANGE"]
    C_SEL_BG, C_SEL_TEXT, C_SELECTED = t["SEL_BG"], t["SEL_TEXT"], t["SELECTED"]
    C_MAGENTA = t["MAGENTA"]
    THEME_HUD, THEME_SCAN = t["HUD"], t["SCAN"]

apply_theme(CURRENT_THEME)

RECEIVE_DIR = "/mnt/mmc/ROMS/Taildrop"
CONFIG_PATH = "/mnt/mmc/MUOS/application/Tailscale/config.ini"

class SDL_Rect(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int), ("w", ctypes.c_int), ("h", ctypes.c_int)]

class SDL_Color(ctypes.Structure):
    _fields_ = [("r", ctypes.c_uint8), ("g", ctypes.c_uint8), ("b", ctypes.c_uint8), ("a", ctypes.c_uint8)]

class SDL_Event(ctypes.Union):
    class _key(ctypes.Structure):
        class _keysym(ctypes.Structure): _fields_ = [("scancode", ctypes.c_int), ("sym", ctypes.c_int), ("mod", ctypes.c_uint16), ("unused", ctypes.c_uint32)]
        _fields_ = [("type", ctypes.c_uint32), ("timestamp", ctypes.c_uint32), ("windowID", ctypes.c_uint32), ("state", ctypes.c_uint8), ("repeat", ctypes.c_uint8), ("padding2", ctypes.c_uint8), ("padding3", ctypes.c_uint8), ("keysym", _keysym)]
    class _jbutton(ctypes.Structure): _fields_ = [("type", ctypes.c_uint32), ("timestamp", ctypes.c_uint32), ("which", ctypes.c_int32), ("button", ctypes.c_uint8), ("state", ctypes.c_uint8), ("padding1", ctypes.c_uint8), ("padding2", ctypes.c_uint8)]
    class _jaxis(ctypes.Structure): _fields_ = [("type", ctypes.c_uint32), ("timestamp", ctypes.c_uint32), ("which", ctypes.c_int32), ("axis", ctypes.c_uint8), ("padding1", ctypes.c_uint8), ("padding2", ctypes.c_uint8), ("padding3", ctypes.c_uint8), ("value", ctypes.c_int16), ("padding4", ctypes.c_uint16)]
    class _jhat(ctypes.Structure): _fields_ = [("type", ctypes.c_uint32), ("timestamp", ctypes.c_uint32), ("which", ctypes.c_int32), ("hat", ctypes.c_uint8), ("value", ctypes.c_uint8), ("padding1", ctypes.c_uint8), ("padding2", ctypes.c_uint8)]
    _fields_ = [("type", ctypes.c_uint32), ("key", _key), ("jbutton", _jbutton), ("jaxis", _jaxis), ("jhat", _jhat), ("padding", ctypes.c_uint8 * 56)]

def load_config():
    cfg = {"receive_dir": RECEIVE_DIR, "theme": CURRENT_THEME, "ssh": "false"}
    try:
        with open(CONFIG_PATH) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip()
    except: pass
    return cfg

def save_config(cfg):
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            for k, v in cfg.items(): f.write(f"{k} = {v}\n")
    except: pass

# --- Custom Renderer ---------------------------------------------------------

class Renderer:
    def __init__(self, renderer, font_small, font_med, font_large):
        self.r  = renderer
        self.fs = font_small
        self.fm = font_med
        self.fl = font_large
        self.logo_tex = None

        # Caricamento Logo
        if SDL2_IMAGE and os.path.exists(LOGO_PATH):
            surf_ptr = SDL2_IMAGE.IMG_Load(LOGO_PATH.encode())
            if surf_ptr:
                self.logo_tex = SDL2.SDL_CreateTextureFromSurface(self.r, ctypes.c_void_p(surf_ptr))
                SDL2.SDL_FreeSurface(ctypes.c_void_p(surf_ptr))
            else:
                log("Logo tailscale.png non caricabile.")

    def clear(self, color=None):
        c = color or C_BG
        SDL2.SDL_SetRenderDrawColor(self.r, c[0], c[1], c[2], c[3] if len(c) > 3 else 255)
        SDL2.SDL_RenderClear(self.r)

    def rect(self, x, y, w, h, color, fill=True):
        SDL2.SDL_SetRenderDrawColor(self.r, color[0], color[1], color[2], color[3] if len(color) > 3 else 255)
        rct = SDL_Rect(int(x), int(y), int(w), int(h))
        if fill: SDL2.SDL_RenderFillRect(self.r, ctypes.byref(rct))
        else: SDL2.SDL_RenderDrawRect(self.r, ctypes.byref(rct))

    def line(self, x1, y1, x2, y2, color):
        SDL2.SDL_SetRenderDrawColor(self.r, color[0], color[1], color[2], color[3] if len(color) > 3 else 255)
        SDL2.SDL_RenderDrawLine(self.r, int(x1), int(y1), int(x2), int(y2))

    def text(self, font, txt, x, y, color, center=False, right=False):
        if not font or not SDL2_TTF or not txt: return
        try: txt_bytes = str(txt).encode("utf-8", errors="replace")
        except: txt_bytes = b"?"
        col = SDL_Color(color[0], color[1], color[2], 255)
        surf = SDL2_TTF.TTF_RenderUTF8_Blended(font, txt_bytes, col)
        if not surf: return
        tex = SDL2.SDL_CreateTextureFromSurface(self.r, surf)
        SDL2.SDL_FreeSurface(surf)
        if not tex: return
        w_out, h_out = ctypes.c_int(0), ctypes.c_int(0)
        SDL2.SDL_QueryTexture(tex, None, None, ctypes.byref(w_out), ctypes.byref(h_out))
        tw, th = w_out.value, h_out.value
        rx = x - tw // 2 if center else x - tw if right else x
        dst = SDL_Rect(int(rx), int(y - th // 2) if center else int(y), tw, th)
        SDL2.SDL_RenderCopy(self.r, tex, None, ctypes.byref(dst))
        SDL2.SDL_DestroyTexture(tex)

    def scrollbar(self, x, y, h, total, visible, current):
        if total <= visible: return
        self.rect(x, y, 4, h, C_BG2)
        thumb_h = max(10, int(h * (visible / total)))
        thumb_y = y + int((h - thumb_h) * (current / max(1, total - 1)))
        self.rect(x, thumb_y, 4, thumb_h, C_ACCENT)

    def present(self):
        SDL2.SDL_RenderPresent(self.r)

    def header(self, title, state=None, wifi_ok=True, daemon_ok=True):
        self.rect(0, 0, W, 50, C_BG2)
        title_x = 16
        if self.logo_tex:
            dst = SDL_Rect(12, 10, 30, 30)
            SDL2.SDL_RenderCopy(self.r, self.logo_tex, None, ctypes.byref(dst))
            title_x = 52

        self.text(self.fl, "Rt:Tailscale", title_x, 10, C_TEXT)
        if title:
            self.line(175, 10, 175, 40, C_BORDER)
            self.text(self.fm, title, 188, 15, C_TEXT_DIM)
        self.line(0, 50, W, 50, C_BORDER)
        
        stat_x = W - 190
        self.rect(stat_x, 21, 8, 8, C_GREEN if wifi_ok else C_RED)
        self.text(self.fs, "WIFI", stat_x + 14, 18, C_TEXT_DIM)
        
        self.rect(stat_x + 60, 21, 8, 8, C_GREEN if daemon_ok else C_RED)
        self.text(self.fs, "DAEMON", stat_x + 74, 18, C_TEXT_DIM)

    def footer(self, hints):
        self.rect(0, H - 36, W, 36, C_BG2)
        self.line(0, H - 36, W, H - 36, C_BORDER)
        x = 12
        for btn, lbl in hints:
            badge_w = max(24, len(btn) * 9 + 8)
            self.rect(x, H - 28, badge_w, 22, C_PANEL)
            self.rect(x, H - 28, badge_w, 22, C_BORDER, fill=False)
            self.text(self.fs, btn, x + badge_w // 2, H - 18, C_TEXT, center=True)
            x += badge_w + 8
            self.text(self.fs, lbl, x, H - 18, C_TEXT_DIM)
            x += len(lbl) * 8 + 16

    def panel(self, x, y, w, h, border_col, bg_col):
        self.rect(x, y, w, h, bg_col)
        self.rect(x, y, w, h, border_col, fill=False)
        if THEME_HUD: self.corners(x, y, w, h)

    def corners(self, x, y, w, h, color=None, ln=10):
        col = color or C_ACCENT
        for (cx, cy, dx, dy) in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
            self.line(cx, cy, cx + dx * ln, cy, col)
            self.line(cx, cy, cx, cy + dy * ln, col)

    def scanlines(self):
        for y in range(0, H, 3):
            self.line(0, y, W, y, (0, 0, 0, 35))

    def button(self, x, y, w, h, label, selected, font=None):
        f = font or self.fm
        if selected:
            self.rect(x, y, w, h, C_ACCENT)
            self.text(f, label, x + w // 2, y + h // 2, C_SEL_TEXT, center=True)
        else:
            self.rect(x, y, w, h, C_PANEL)
            self.rect(x, y, w, h, C_BORDER, fill=False)
            self.text(f, label, x + w // 2, y + h // 2, C_TEXT, center=True)

# --- App State & Logic Class -------------------------------------------------

class App:
    def __init__(self):
        self.screen = "bootanim"
        self.boot_start = time.time()
        self.boot_nodes = [(random.randint(50, W-50), random.randint(80, H-80), random.choice([-1.5,1.5]), random.choice([-1.5,1.5])) for _ in range(12)]
        self.sel = 0
        self.running = True
        self.state_cache = "unknown"
        self.ip_cache = ""
        self.peers_cache = []
        self.wifi_ok = False
        self.daemon_ok = False
        self.status_msg = ""
        self.last_refresh = 0
        self.cfg = load_config()
        self.receive_dir = self.cfg.get("receive_dir", RECEIVE_DIR)
        self.ssh_enabled = self.cfg.get("ssh", "false").lower() == "true"
        self.theme = self.cfg.get("theme", CURRENT_THEME)
        self.theme_sel = THEME_ORDER.index(self.theme) if self.theme in THEME_ORDER else 0
        apply_theme(self.theme)
        
        self.browse_path = "/mnt/mmc/ROMS"
        self.browse_entries = []
        self.browse_sel = 0
        self.browse_marked = set()
        self.browse_mode = "send"
        self.send_target = ""
        
        self.loading_msg = ""
        self.loading_start = 0
        self.exit_pending = False
        
        self.login_url = None
        self.qr_matrix = None
        self.qr_error = None
        self.result_msg = ""
        
        self.status_sel = 0
        self.tailnet_name = ""
        self.magicdns_on = False
        self.key_expiry_days = None
        self.exit_node_active = None
        self.exit_sel = 0
        self.peer_detail_target = None
        self.peer_detail_msg = ""
        self.ts_version = ts_version()
        self.netcheck_data = {}
        self.axis_timer = {}

        self._refresh_status()

    def _days_until(self, iso_str):
        if not iso_str or iso_str.startswith("0001-01-01"): return None
        try:
            dt = datetime.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            now = datetime.datetime.now(datetime.timezone.utc)
            return (dt - now).days
        except: return None

    def _fetch_status_now(self):
        self.wifi_ok = is_wifi_connected()
        self.daemon_ok = is_daemon_running()
        try:
            j = ts_status_json() 
            if j:
                backend = j.get("BackendState", "unknown")
                self.state_cache = {
                    "Running": "Running", "NeedsLogin": "NeedsLogin",
                    "Stopped": "Stopped", "NoState": "Stopped",
                }.get(backend, backend)
                
                me = j.get("Self", {})
                ips = me.get("TailscaleIPs", [])
                self.ip_cache = ips[0] if ips else ""

                tailnet = j.get("CurrentTailnet", {}) or {}
                self.tailnet_name = tailnet.get("Name", "")
                self.magicdns_on = bool(tailnet.get("MagicDNSEnabled", False))
                self.key_expiry_days = self._days_until(me.get("KeyExpiry", ""))

                peers = []
                my_name = me.get("HostName", me.get("DNSName", "This Device")).split(".")[0]
                peers.append({
                    "name": f"{my_name} (This Device)",
                    "ip": self.ip_cache,
                    "online": True,
                    "os": me.get("OS", "linux"),
                    "relay": "", "last_seen": "", "exit_option": False, "exit_active": False,
                })
                
                exit_active_name = None
                for v in j.get("Peer", {}).values():
                    dns = v.get("DNSName", "")
                    name = dns.split(".")[0] if dns else v.get("HostName", "?")
                    p_ips = v.get("TailscaleIPs", [])
                    is_exit_active = bool(v.get("ExitNode", False))
                    if is_exit_active: exit_active_name = name
                    peers.append({
                        "name": name,
                        "online": bool(v.get("Online", False)),
                        "ip": p_ips[0] if p_ips else "",
                        "os": v.get("OS", ""),
                        "relay": v.get("Relay", "") or "",
                        "last_seen": v.get("LastSeen", "") or "",
                        "exit_option": bool(v.get("ExitNodeOption", False)),
                        "exit_active": is_exit_active,
                    })
                self.peers_cache = peers
                self.exit_node_active = exit_active_name
            else:
                self.state_cache, self.ip_cache, self.peers_cache = "unknown", "", []
        except:
            self.state_cache, self.ip_cache, self.peers_cache = "unknown", "", []
        self.last_refresh = time.time()

    def _refresh_status(self):
        t = threading.Thread(target=self._fetch_status_now, daemon=True)
        t.start()

    def handle_input(self, action):
        if self.screen == "bootanim": self.screen, self.sel = "main", 0
        elif self.screen == "main": self._handle_main(action)
        elif self.screen == "connection_mgr": self._handle_connection_mgr(action)
        elif self.screen == "status": self._handle_status(action)
        elif self.screen == "filetransfer": self._handle_filetransfer(action)
        elif self.screen == "netcheck": self._handle_netcheck(action)
        elif self.screen == "options": self._handle_options(action)
        elif self.screen == "send_pick_device": self._handle_send_device(action)
        elif self.screen == "browse": self._handle_browse(action)
        elif self.screen == "result": self._handle_result(action)
        elif self.screen == "qr": self._handle_qr(action)
        elif self.screen == "exit_node": self._handle_exit_node(action)
        elif self.screen == "peer_detail": self._handle_peer_detail(action)
        elif self.screen == "theme_select": self._handle_theme_select(action)
        elif self.screen == "netinfo": self._handle_netinfo(action)

    # --- Handlers ------------------------------------------------------------

    def _handle_main(self, action):
        items = 6
        if action == "UP": self.sel = (self.sel - 1) % items
        elif action == "DOWN": self.sel = (self.sel + 1) % items
        elif action == "CONFIRM":
            if self.sel == 0: self.screen, self.sel = "connection_mgr", 0
            elif self.sel == 1: self._refresh_status(); self.status_sel = 0; self.screen = "status"
            elif self.sel == 2: self.screen, self.sel = "filetransfer", 0
            elif self.sel == 3: self._start_netcheck()
            elif self.sel == 4: self.screen, self.sel = "options", 0
            elif self.sel == 5: self._start_exit()
        elif action == "BACK": self._start_exit()

    def _start_exit(self):
        self.loading_msg = "Shutting Down GUI"
        self.loading_start = time.time()
        self.screen, self.exit_pending = "loading", True

    def _handle_connection_mgr(self, action):
        items = 4
        if action == "UP": self.sel = (self.sel - 1) % items
        elif action == "DOWN": self.sel = (self.sel + 1) % items
        elif action == "CONFIRM":
            if self.sel == 0: # Toggle Connect/Disconnect
                if self.state_cache == "Running":
                    self.loading_msg = "Disconnecting Tailscale..."
                    self.screen = "loading"
                    def _do_down():
                        ts_down()
                        time.sleep(1)
                        self._fetch_status_now()
                        self.result_msg = "Tailscale Disconnected."
                        self.screen = "result"
                    threading.Thread(target=_do_down, daemon=True).start()
                else:
                    if not self.wifi_ok or not self.daemon_ok:
                        self.result_msg = "ERROR: Wi-Fi or Tailscale Daemon offline."
                        self.screen = "result"
                        return
                    self.loading_msg = "Connecting Tailscale..."
                    self.loading_start = time.time()
                    self.screen = "loading"
                    def _connect():
                        url, msg = ts_connect(use_ssh=self.ssh_enabled)
                        if url:
                            self.login_url = url
                            short = url.replace("https://login.tailscale.com/", "")
                            self.result_msg = f"Auth Required!\n\nVisit URL on device:\nhttps://login.tailscale.com/{short}\n\nPress Y for QR code"
                        else:
                            self._fetch_status_now()
                            self.result_msg = f"Connected!\nIP: {self.ip_cache}" if self.state_cache == "Running" else (msg or "Done.")
                        self.screen = "result"
                    threading.Thread(target=_connect, daemon=True).start()
            elif self.sel == 1: # Toggle SSH
                self.ssh_enabled = not self.ssh_enabled
                self.cfg["ssh"] = "true" if self.ssh_enabled else "false"
                save_config(self.cfg)
                self.loading_msg = f"{'Enabling' if self.ssh_enabled else 'Disabling'} Tailscale SSH..."
                self.screen = "loading"
                def _do_ssh():
                    ts_toggle_ssh(self.ssh_enabled)
                    self.result_msg = f"Tailscale SSH is now {'ENABLED' if self.ssh_enabled else 'DISABLED'}."
                    self.screen = "result"
                threading.Thread(target=_do_ssh, daemon=True).start()
            elif self.sel == 2: # Re-authenticate / Re-login
                self.loading_msg = "Requesting new auth key..."
                self.screen = "loading"
                def _reauth():
                    url, msg = ts_connect(use_ssh=self.ssh_enabled)
                    if url:
                        self.login_url = url
                        self.result_msg = f"Scan QR code or open link:\n{url}"
                    else:
                        self.result_msg = "Re-authentication failed or unnecessary."
                    self.screen = "result"
                threading.Thread(target=_reauth, daemon=True).start()
            elif self.sel == 3: self.screen, self.sel = "main", 0
        elif action == "BACK": self.screen, self.sel = "main", 0

    def _start_netcheck(self):
        self.loading_msg = "Running Netcheck..."
        self.loading_start = time.time()
        self.screen = "loading"
        def _check():
            self.netcheck_data = ts_netcheck_json()
            self.screen = "netcheck"
        threading.Thread(target=_check, daemon=True).start()

    def _handle_netcheck(self, action):
        if action in ("BACK", "CONFIRM"): self.screen, self.sel = "main", 3

    def _handle_status(self, action):
        items = len(self.peers_cache)
        if action == "BACK": self.screen, self.sel = "main", 1
        elif action == "CONFIRM" and items:
            self.peer_detail_target = self.peers_cache[self.status_sel]
            self.peer_detail_msg = ""
            self.screen = "peer_detail"
        elif action == "UP" and items: self.status_sel = (self.status_sel - 1) % items
        elif action == "DOWN" and items: self.status_sel = (self.status_sel + 1) % items
        elif action == "NEW_FOLDER":
            self.loading_msg = "Refreshing status"
            self.loading_start = time.time()
            self.screen = "loading"
            def _ref():
                self._fetch_status_now()
                self.screen = "status"
            threading.Thread(target=_ref, daemon=True).start()

    def _handle_options(self, action):
        items = 6
        if action == "UP": self.sel = (self.sel - 1) % items
        elif action == "DOWN": self.sel = (self.sel + 1) % items
        elif action == "CONFIRM":
            if self.sel == 0:
                self.browse_mode = "pick_dir"
                self._load_browse("/mnt/mmc", dirs_only=True)
                self.browse_sel, self.screen = 0, "browse"
            elif self.sel == 1: self.exit_sel = 0; self.screen = "exit_node"
            elif self.sel == 2: self.screen = "netinfo"
            elif self.sel == 3:
                self.theme_sel = THEME_ORDER.index(self.theme) if self.theme in THEME_ORDER else 0
                self.screen = "theme_select"
            elif self.sel == 4:
                self.loading_msg = "Logging out..."
                self.screen = "loading"
                def _do_logout():
                    ts_logout()
                    time.sleep(1)
                    self._fetch_status_now()
                    self.result_msg = "Logged out successfully."
                    self.screen = "result"
                threading.Thread(target=_do_logout, daemon=True).start()
            elif self.sel == 5: self.screen, self.sel = "main", 4
        elif action == "BACK": self.screen, self.sel = "main", 4

    def _handle_exit_node(self, action):
        options = [p for p in self.peers_cache if p.get("exit_option") and "(This Device)" not in p["name"]]
        items = len(options) + 1
        if action == "UP": self.exit_sel = (self.exit_sel - 1) % items
        elif action == "DOWN": self.exit_sel = (self.exit_sel + 1) % items
        elif action == "CONFIRM":
            target_ip = "" if self.exit_sel == 0 else options[self.exit_sel - 1]["ip"]
            target_label = "Direct Access" if self.exit_sel == 0 else options[self.exit_sel - 1]["name"]
            self.loading_msg = "Updating Exit Node..."
            self.loading_start = time.time()
            self.screen = "loading"
            def _set():
                ts_set_exit_node(target_ip)
                self._fetch_status_now()
                self.result_msg = f"Exit Node set to:\n{target_label}"
                self.screen = "result"
            threading.Thread(target=_set, daemon=True).start()
        elif action == "BACK": self.screen, self.sel = "options", 1

    def _handle_peer_detail(self, action):
        peer = self.peer_detail_target or {}
        is_self = "(This Device)" in peer.get("name", "")
        if action == "BACK": self.screen = "status"
        elif action == "CONFIRM" and not is_self and peer.get("ip"):
            self.peer_detail_msg = "Pinging..."
            def _do_ping():
                out, err = ts_ping(peer["ip"])
                self.peer_detail_msg = (out or err or "No ping response.").strip()
            threading.Thread(target=_do_ping, daemon=True).start()
        elif action == "NEW_FOLDER" and not is_self and peer.get("exit_option"):
            is_active = peer.get("exit_active")
            target_ip = "" if is_active else peer["ip"]
            self.loading_msg = "Toggling Exit Node..."
            self.screen = "loading"
            def _toggle():
                ts_set_exit_node(target_ip)
                self._fetch_status_now()
                self.result_msg = f"Exit node {'disabled' if is_active else 'enabled'}."
                self.screen = "result"
            threading.Thread(target=_toggle, daemon=True).start()

    def _handle_theme_select(self, action):
        items = len(THEME_ORDER)
        if action == "UP": self.theme_sel = (self.theme_sel - 1) % items
        elif action == "DOWN": self.theme_sel = (self.theme_sel + 1) % items
        elif action == "CONFIRM":
            chosen = THEME_ORDER[self.theme_sel]
            apply_theme(chosen)
            self.theme = chosen
            self.cfg["theme"] = chosen
            save_config(self.cfg)
            self.screen, self.sel = "options", 3
        elif action == "BACK": self.screen, self.sel = "options", 3

    def _handle_netinfo(self, action):
        if action in ("BACK", "CONFIRM"): self.screen, self.sel = "options", 2

    def _handle_filetransfer(self, action):
        items = 3
        if action == "UP": self.sel = (self.sel - 1) % items
        elif action == "DOWN": self.sel = (self.sel + 1) % items
        elif action == "CONFIRM":
            if self.sel == 0:
                self.loading_msg = "Checking incoming Taildrop files..."
                self.screen = "loading"
                def _recv():
                    msg = ts_receive_files_to(self.receive_dir)
                    self.result_msg = f"Receive complete:\n\n{msg}\n\nSaved to:\n{self.receive_dir}"
                    self.screen = "result"
                threading.Thread(target=_recv, daemon=True).start()
            elif self.sel == 1:
                online = [p for p in self.peers_cache if p["online"] and "(This Device)" not in p["name"]]
                if not online:
                    self.result_msg = "No remote devices online."
                    self.screen = "result"
                else: self.screen, self.send_sel = "send_pick_device", 0
            elif self.sel == 2: self.screen, self.sel = "main", 2
        elif action == "BACK": self.screen, self.sel = "main", 2

    def _handle_send_device(self, action):
        online = [p for p in self.peers_cache if p["online"] and "(This Device)" not in p["name"]]
        items = len(online) + 1
        if action == "UP": self.send_sel = (self.send_sel - 1) % items
        elif action == "DOWN": self.send_sel = (self.send_sel + 1) % items
        elif action == "CONFIRM":
            if self.send_sel < len(online):
                self.send_target = online[self.send_sel]["name"]
                self.browse_marked = set()
                self._load_browse(self.browse_path)
                self.screen, self.browse_sel = "browse", 0
            else: self.screen, self.sel = "filetransfer", 1
        elif action == "BACK": self.screen, self.sel = "filetransfer", 1

    def _load_browse(self, path, dirs_only=False):
        self.browse_path = path
        self.browse_dirs_only = dirs_only
        entries = []
        try:
            if path != "/mnt/mmc": entries.append((".. (back)", "dir", ".."))
            for item in sorted(os.listdir(path)):
                full = os.path.join(path, item)
                if os.path.isdir(full): entries.append((item + "/", "dir", full))
                elif not dirs_only:
                    sz = self._fmt_size(os.path.getsize(full)) if os.path.exists(full) else "?"
                    entries.append((f"{item} ({sz})", "file", full))
        except Exception as e: entries.append((f"Error: {e}", "err", ""))
        self.browse_entries = entries

    def _fmt_size(self, b):
        if b < 1024: return f"{b}B"
        if b < 1024*1024: return f"{b//1024}KB"
        return f"{b//(1024*1024)}MB"

    def _handle_browse(self, action):
        items = len(self.browse_entries)
        if items == 0 and action == "BACK":
            self.screen = "options" if self.browse_mode == "pick_dir" else "send_pick_device"
            return
        if action == "UP": self.browse_sel = (self.browse_sel - 1) % items
        elif action == "DOWN": self.browse_sel = (self.browse_sel + 1) % items
        elif action == "CONFIRM":
            name, kind, full_path = self.browse_entries[self.browse_sel]
            if kind == "dir":
                parent = os.path.dirname(self.browse_path) if full_path == ".." else full_path
                self._load_browse(parent, dirs_only=self.browse_dirs_only)
                self.browse_sel = 0
            elif kind == "file" and self.browse_mode == "send":
                if full_path in self.browse_marked: self.browse_marked.discard(full_path)
                else: self.browse_marked.add(full_path)
        elif action == "NEW_FOLDER" and self.browse_mode == "send":
            to_send = list(self.browse_marked)
            if not to_send and self.browse_entries:
                name, kind, full_path = self.browse_entries[self.browse_sel]
                if kind == "file": to_send = [full_path]
            if not to_send: return
            target = self.send_target
            self.loading_msg = f"Sending {len(to_send)} file(s)..."
            self.screen = "loading"
            def _send_many():
                res = [f"{'OK' if 'error' not in ts_send_file(target, fp).lower() else 'ERR'} {os.path.basename(fp)}" for fp in to_send]
                self.browse_marked = set()
                self.result_msg = f"Taildrop to {target}:\n\n" + "\n".join(res[:10])
                self.screen = "result"
            threading.Thread(target=_send_many, daemon=True).start()
        elif action == "LEFT" and self.browse_mode == "pick_dir":
            os.makedirs(self.browse_path, exist_ok=True)
            self.receive_dir = self.browse_path
            self.cfg["receive_dir"] = self.browse_path
            save_config(self.cfg)
            self.result_msg = f"Download directory set to:\n{self.browse_path}"
            self.screen = "result"
        elif action == "BACK":
            self.screen = "options" if self.browse_mode == "pick_dir" else "send_pick_device"

    def _handle_result(self, action):
        if action == "NEW_FOLDER" and self.login_url:
            try: self.qr_matrix, self.qr_error = build_qr(self.login_url), None
            except Exception as e: self.qr_matrix, self.qr_error = None, str(e)
            self.screen = "qr"
        elif action in ("CONFIRM", "BACK"): self.login_url, self.screen, self.sel = None, "main", 0

    def _handle_qr(self, action):
        if action in ("CONFIRM", "BACK", "NEW_FOLDER"): self.screen = "result"

    # --- Rendering Routines --------------------------------------------------

    def draw(self, rnd):
        rnd.clear()
        if self.screen == "bootanim": self._draw_bootanim(rnd)
        elif self.screen == "main": self._draw_main(rnd)
        elif self.screen == "connection_mgr": self._draw_connection_mgr(rnd)
        elif self.screen == "status": self._draw_status(rnd)
        elif self.screen == "filetransfer": self._draw_filetransfer(rnd)
        elif self.screen == "netcheck": self._draw_netcheck(rnd)
        elif self.screen == "options": self._draw_options(rnd)
        elif self.screen == "send_pick_device": self._draw_send_device(rnd)
        elif self.screen == "browse": self._draw_browse(rnd)
        elif self.screen == "result": self._draw_result(rnd)
        elif self.screen == "qr": self._draw_qr(rnd)
        elif self.screen == "loading": self._draw_loading(rnd)
        elif self.screen == "exit_node": self._draw_exit_node(rnd)
        elif self.screen == "peer_detail": self._draw_peer_detail(rnd)
        elif self.screen == "theme_select": self._draw_theme_select(rnd)
        elif self.screen == "netinfo": self._draw_netinfo(rnd)
        if THEME_SCAN and self.screen != "bootanim": rnd.scanlines()
        rnd.present()

    def _draw_bootanim(self, rnd):
        rnd.rect(0, 0, W, H, C_BG)
        elapsed = time.time() - self.boot_start

        # Draw Mesh Connections
        for i, (x1, y1, vx1, vy1) in enumerate(self.boot_nodes):
            nx1 = (x1 + vx1 * elapsed * 20) % W
            ny1 = (y1 + vy1 * elapsed * 20) % H
            for j, (x2, y2, vx2, vy2) in enumerate(self.boot_nodes[i+1:]):
                nx2 = (x2 + vx2 * elapsed * 20) % W
                ny2 = (y2 + vy2 * elapsed * 20) % H
                dist = math.hypot(nx1 - nx2, ny1 - ny2)
                if dist < 140:
                    rnd.line(nx1, ny1, nx2, ny2, C_BORDER)
            rnd.rect(nx1 - 3, ny1 - 3, 6, 6, C_ACCENT)

        rnd.text(rnd.fl, "Rt:TAILSCALE", W // 2, H // 2 - 40, C_TEXT, center=True)
        rnd.text(rnd.fm, "muOS Node Control Unit", W // 2, H // 2, C_ACCENT, center=True)
        rnd.text(rnd.fs, f"v{APP_VERSION} - SPDW Factory Lab Engine", W // 2, H // 2 + 35, C_TEXT_DIM, center=True)

        bar_w = int(W * min(1.0, elapsed / 3.5))
        rnd.rect(0, H - 6, bar_w, 6, C_ACCENT)
        rnd.text(rnd.fs, "Press ANY key to skip...", W // 2, H - 26, C_TEXT_DIM, center=True)

    def _draw_main(self, rnd):
        state = self.state_cache
        rnd.header("", state, self.wifi_ok, self.daemon_ok)

        sy = 65
        rnd.panel(20, sy, W - 40, 80, C_BORDER, C_BG2)

        if state == "Running":
            rnd.rect(40, sy + 25, 12, 12, C_GREEN)
            rnd.text(rnd.fl, "Node Active", 64, sy + 16, C_TEXT)
            rnd.text(rnd.fm, f"IP: {self.ip_cache}", 64, sy + 46, C_TEXT_DIM)
        else:
            rnd.rect(40, sy + 25, 12, 12, C_RED if state == "Stopped" else C_ORANGE)
            rnd.text(rnd.fl, state.upper(), 64, sy + 16, C_TEXT)
            rnd.text(rnd.fm, "Select Connection Manager to start", 64, sy + 46, C_TEXT_DIM)

        online = sum(1 for p in self.peers_cache if p["online"])
        rnd.text(rnd.fs, f"{online}/{len(self.peers_cache)} Peers Online", W - 40, sy + 16, C_TEXT_DIM, right=True)

        menu = [
            ("Connection Manager", "Toggle Connect / SSH / Auth"),
            ("Network Devices", "View status, peers & ping"),
            ("Taildrop", "Send & receive files via mesh"),
            ("Netcheck Diagnostics", "NAT, DERP Latency & UDP test"),
            ("System Options", "Themes, download path & auth"),
            ("Exit to OS", "Close application"),
        ]
        my, mh = sy + 92, 45
        for i, (label, sub) in enumerate(menu):
            sel = (i == self.sel)
            if sel:
                rnd.rect(20, my + i * mh, W - 40, mh - 4, C_SEL_BG)
                rnd.rect(20, my + i * mh, 4, mh - 4, C_ACCENT)
                rnd.text(rnd.fm, label, 36, my + i * mh + 8, C_TEXT)
                if sub: rnd.text(rnd.fs, sub, W - 32, my + i * mh + 10, C_TEXT_DIM, right=True)
            else:
                rnd.rect(20, my + i * mh, W - 40, mh - 4, C_BG)
                rnd.text(rnd.fm, label, 36, my + i * mh + 8, C_TEXT)
                if sub: rnd.text(rnd.fs, sub, W - 32, my + i * mh + 10, C_TEXT_DIM, right=True)
            rnd.line(20, my + i * mh + mh - 2, W - 20, my + i * mh + mh - 2, C_BG2)

        rnd.footer([("D-Pad", "Navigate"), ("A", "Select")])

    def _draw_connection_mgr(self, rnd):
        rnd.header("Connection Manager", self.state_cache, self.wifi_ok, self.daemon_ok)

        conn_status = "Connected" if self.state_cache == "Running" else "Disconnected"
        ssh_status = "ENABLED" if self.ssh_enabled else "DISABLED"

        opts = [
            (f"Tailscale Connection: {conn_status}", "Toggle mesh network status"),
            (f"Tailscale SSH: {ssh_status}", "Allow secure SSH shell access via Tailnet"),
            ("Re-Authenticate Node", "Generate new web login URL / QR code"),
            ("Back to Main Menu", ""),
        ]

        by, rh = 75, 65
        for i, (label, sub) in enumerate(opts):
            sel = (i == self.sel)
            if sel:
                rnd.rect(20, by + i * rh, W - 40, rh - 4, C_SEL_BG)
                rnd.rect(20, by + i * rh, 4, rh - 4, C_ACCENT)
            else:
                rnd.rect(20, by + i * rh, W - 40, rh - 4, C_BG)
            rnd.text(rnd.fm, label, 36, by + i * rh + 10, C_TEXT)
            if sub: rnd.text(rnd.fs, sub, 36, by + i * rh + 36, C_TEXT_DIM)
            rnd.line(20, by + i * rh + rh - 2, W - 20, by + i * rh + rh - 2, C_BG2)

        rnd.footer([("A", "Toggle/Execute"), ("B", "Back")])

    def _draw_netcheck(self, rnd):
        rnd.header("Netcheck Diagnostics", self.state_cache, self.wifi_ok, self.daemon_ok)
        rnd.panel(20, 65, W - 40, H - 140, C_BORDER, C_BG2)

        nc = self.netcheck_data
        rows = [
            ("UDP Access", "YES" if nc.get("UDP") else "NO", C_GREEN if nc.get("UDP") else C_RED),
            ("IPv4", "YES" if nc.get("IPv4") else "NO", C_GREEN if nc.get("IPv4") else C_RED),
            ("IPv6", "YES" if nc.get("IPv6") else "NO", C_GREEN if nc.get("IPv6") else C_TEXT_DIM),
            ("Mapping Vary / NAT", nc.get("MappingVariesByDestIP", "Unknown"), C_TEXT),
            ("Hairpinning", str(nc.get("HairPinning", "Unknown")), C_TEXT),
            ("Preferred DERP Relay", str(nc.get("PreferredDERP", "None")), C_ACCENT),
        ]

        for i, (k, v, col) in enumerate(rows):
            yy = 80 + i * 32
            rnd.text(rnd.fs, k, 36, yy, C_TEXT_DIM)
            rnd.text(rnd.fm, str(v), 260, yy - 4, col)

        rnd.footer([("A/B", "Back")])

    def _draw_status(self, rnd):
        rnd.header("Network Peers", self.state_cache, self.wifi_ok, self.daemon_ok)
        py = 65
        rnd.text(rnd.fs, "PEERS ON TAILNET", 20, py, C_TEXT_DIM)
        rnd.line(20, py + 22, W - 20, py + 22, C_BORDER)

        visible = 8
        total = len(self.peers_cache)
        start = max(0, min(self.status_sel - visible + 3, max(0, total - visible)))
        for i, peer in enumerate(self.peers_cache[start:start + visible]):
            real_i = start + i
            sel = (real_i == self.status_sel)
            row_y = py + 32 + i * 36
            if sel:
                rnd.rect(20, row_y - 2, W - 40, 34, C_SEL_BG)
                rnd.rect(20, row_y - 2, 4, 34, C_ACCENT)
            rnd.rect(26, row_y + 10, 8, 8, C_GREEN if peer["online"] else C_BORDER)

            p_name = peer["name"]
            rnd.text(rnd.fm, p_name, 44, row_y, C_TEXT if peer["online"] else C_TEXT_DIM)
            rnd.text(rnd.fs, peer["ip"], 44, row_y + 18, C_TEXT_DIM)
            if peer.get("exit_active"): rnd.text(rnd.fs, "EXIT NODE", W - 100, row_y + 8, C_ACCENT, right=True)
            rnd.text(rnd.fs, peer["os"].capitalize(), W - 20, row_y + 8, C_TEXT_DIM, right=True)
            rnd.line(44, row_y + 34, W - 20, row_y + 34, C_BG2)

        rnd.scrollbar(W - 12, py + 32, 36 * min(visible, total), total, visible, self.status_sel)
        rnd.footer([("D-Pad", "Nav"), ("A", "Details / Ping"), ("Y", "Refresh"), ("B", "Back")])

    def _draw_filetransfer(self, rnd):
        rnd.header("Taildrop File Sharing", self.state_cache, self.wifi_ok, self.daemon_ok)
        opts = [
            ("Receive Incoming Files", f"Fetch files sent to: {self.receive_dir.replace('/mnt/mmc', 'SD:')}"),
            ("Send File to Peer", "Select files from SD card and dispatch"),
            ("Back to Main Menu", "")
        ]
        by = 90
        for i, (label, sub) in enumerate(opts):
            sel = (i == self.sel)
            if sel:
                rnd.rect(20, by + i * 66, W - 40, 60, C_SEL_BG)
                rnd.rect(20, by + i * 66, 4, 60, C_ACCENT)
            else:
                rnd.rect(20, by + i * 66, W - 40, 60, C_BG)
            rnd.text(rnd.fm, label, 36, by + i * 66 + 12, C_TEXT)
            if sub: rnd.text(rnd.fs, sub, 36, by + i * 66 + 36, C_TEXT_DIM)
            rnd.line(20, by + i * 66 + 62, W - 20, by + i * 66 + 62, C_BG2)

        rnd.footer([("A", "Select"), ("B", "Back")])

    def _draw_options(self, rnd):
        rnd.header("Options", self.state_cache, self.wifi_ok, self.daemon_ok)
        opts = [
            ("Change Download Location", f"Current: {self.receive_dir.replace('/mnt/mmc', 'SD:')}"),
            ("Exit Node Settings", f"Current: {self.exit_node_active or 'Disabled'}"),
            ("Network Information", "View MagicDNS, Key Expiry & Tailnet info"),
            ("Theme Selection", THEME_NAMES.get(self.theme, self.theme)),
            ("Force Account Logout", "Unlink this device from Tailscale account"),
            ("Back", ""),
        ]
        by, rh = 65, 58
        for i, (label, sub) in enumerate(opts):
            sel = (i == self.sel)
            if sel:
                rnd.rect(20, by + i * rh, W - 40, rh - 4, C_SEL_BG)
                rnd.rect(20, by + i * rh, 4, rh - 4, C_ACCENT)
            else:
                rnd.rect(20, by + i * rh, W - 40, rh - 4, C_BG)
            rnd.text(rnd.fm, label, 36, by + i * rh + 8, C_TEXT)
            if sub: rnd.text(rnd.fs, sub, 36, by + i * rh + 30, C_TEXT_DIM)
            rnd.line(20, by + i * rh + rh - 2, W - 20, by + i * rh + rh - 2, C_BG2)

        rnd.footer([("A", "Select"), ("B", "Back")])

    def _draw_peer_detail(self, rnd):
        peer = self.peer_detail_target or {}
        rnd.header("Peer Details", self.state_cache, self.wifi_ok, self.daemon_ok)
        rnd.panel(20, 64, W - 40, H - 140, C_BORDER, C_BG2)

        lines = [
            ("Host Name", peer.get("name", "?")),
            ("Tailscale IP", peer.get("ip") or "?"),
            ("Operating System", (peer.get("os") or "?").capitalize()),
            ("Status", "Online" if peer.get("online") else "Offline"),
            ("Relay DERP", peer.get("relay") or "Direct WireGuard"),
            ("Exit Node Capable", "Yes" if peer.get("exit_option") else "No"),
        ]

        for i, (k, v) in enumerate(lines):
            yy = 80 + i * 30
            rnd.text(rnd.fs, k, 36, yy, C_TEXT_DIM)
            rnd.text(rnd.fm, str(v), 240, yy - 4, C_TEXT)

        if self.peer_detail_msg:
            rnd.line(36, 260, W - 36, 260, C_BORDER)
            rnd.text(rnd.fs, "Diagnostic Output:", 36, 270, C_TEXT_DIM)
            rnd.text(rnd.fm, self.peer_detail_msg[:50], 36, 290, C_ACCENT)

        rnd.footer([("A", "Ping Peer"), ("Y", "Toggle Exit Node"), ("B", "Back")])

    def _draw_exit_node(self, rnd):
        rnd.header("Exit Node", self.state_cache, self.wifi_ok, self.daemon_ok)
        options = [p for p in self.peers_cache if p.get("exit_option") and "(This Device)" not in p["name"]]
        rows = [("Disabled (Direct Internet Access)", "")] + [(p["name"], p["ip"]) for p in options]

        for i, (label, sub) in enumerate(rows[:7]):
            sel = (i == self.exit_sel)
            is_active = (i == 0 and not self.exit_node_active) or (i > 0 and options[i-1]["name"] == self.exit_node_active)
            row_y = 80 + i * 44
            if sel:
                rnd.rect(20, row_y, W - 40, 40, C_SEL_BG)
                rnd.rect(20, row_y, 4, 40, C_ACCENT)
            rnd.text(rnd.fm, label, 36, row_y + 4, C_GREEN if is_active else C_TEXT)
            if sub: rnd.text(rnd.fs, sub, 36, row_y + 24, C_TEXT_DIM)

        rnd.footer([("A", "Apply Exit Node"), ("B", "Back")])

    def _draw_theme_select(self, rnd):
        rnd.header("Theme Selection", self.state_cache, self.wifi_ok, self.daemon_ok)
        for i, key in enumerate(THEME_ORDER):
            sel = (i == self.theme_sel)
            active = (key == self.theme)
            row_y = 80 + i * 60
            if sel:
                rnd.rect(20, row_y, W - 40, 54, C_SEL_BG)
                rnd.rect(20, row_y, 4, 54, C_ACCENT)
            rnd.text(rnd.fm, THEME_NAMES[key] + (" (Active)" if active else ""), 36, row_y + 12, C_GREEN if active else C_TEXT)

        rnd.footer([("A", "Apply Theme"), ("B", "Back")])

    def _draw_netinfo(self, rnd):
        rnd.header("Network Info", self.state_cache, self.wifi_ok, self.daemon_ok)
        rnd.panel(20, 64, W - 40, H - 140, C_BORDER, C_BG2)

        rows = [
            ("Current Tailnet", self.tailnet_name or "-", C_TEXT),
            ("MagicDNS Status", "Enabled" if self.magicdns_on else "Disabled", C_TEXT),
            ("Device IP", self.ip_cache or "-", C_TEXT),
            ("Tailscale Version", self.ts_version, C_TEXT),
            ("Key Expiry", f"Expires in {self.key_expiry_days} days" if self.key_expiry_days else "No Expiry", C_TEXT),
        ]
        for i, (k, v, col) in enumerate(rows):
            yy = 80 + i * 32
            rnd.text(rnd.fs, k, 36, yy, C_TEXT_DIM)
            rnd.text(rnd.fm, str(v), 240, yy - 4, col)

        rnd.footer([("A/B", "Back")])

    def _draw_send_device(self, rnd):
        rnd.header("Select Target Device", self.state_cache, self.wifi_ok, self.daemon_ok)
        online = [p for p in self.peers_cache if p["online"] and "(This Device)" not in p["name"]]
        for i, peer in enumerate(online[:6]):
            sel = (i == self.send_sel)
            row_y = 90 + i * 46
            if sel:
                rnd.rect(20, row_y, W - 40, 42, C_SEL_BG)
                rnd.rect(20, row_y, 4, 42, C_ACCENT)
            rnd.text(rnd.fm, peer["name"], 36, row_y + 4, C_TEXT)
            rnd.text(rnd.fs, f"{peer['ip']} ({peer['os']})", 36, row_y + 22, C_TEXT_DIM)

        rnd.footer([("A", "Select Target"), ("B", "Back")])

    def _draw_browse(self, rnd):
        rnd.header("Browse Files", self.state_cache, self.wifi_ok, self.daemon_ok)
        rnd.text(rnd.fs, self.browse_path.replace("/mnt/mmc", "SD:"), 20, 60, C_TEXT_DIM)
        rnd.line(20, 78, W - 20, 78, C_BORDER)

        visible = 9
        start = max(0, self.browse_sel - visible + 3)
        for i, (name, kind, full_path) in enumerate(self.browse_entries[start:start+visible]):
            real_i = start + i
            sel = (real_i == self.browse_sel)
            row_y = 82 + i * 36
            if sel:
                rnd.rect(20, row_y, W - 40, 34, C_SEL_BG)
                rnd.rect(20, row_y, 4, 34, C_ACCENT)

            marked = self.browse_mode == "send" and full_path in self.browse_marked
            prefix = "[x] " if marked else ("[D] " if kind == "dir" else "[F] ")
            rnd.text(rnd.fm, prefix + name, 36, row_y + 6, C_ACCENT if marked else C_TEXT)

        rnd.scrollbar(W - 12, 82, 36 * min(visible, len(self.browse_entries)), len(self.browse_entries), visible, self.browse_sel)

        if self.browse_mode == "pick_dir":
            rnd.footer([("A", "Open"), ("<", "Select Here"), ("B", "Back")])
        else:
            rnd.footer([("A", "Mark File"), ("Y", f"Send ({len(self.browse_marked)})"), ("B", "Back")])

    def _draw_loading(self, rnd):
        rnd.header("Processing...", self.state_cache, self.wifi_ok, self.daemon_ok)
        elapsed = time.time() - self.loading_start
        rnd.panel(60, 140, W - 120, 160, C_BORDER, C_BG2)

        cx, cy = W // 2, 195
        seg = int(elapsed * 8) % 8
        positions = [(0,-18),(12,-12),(18,0),(12,12),(0,18),(-12,12),(-18,0),(-12,-12)]
        for i, (dx, dy) in enumerate(positions):
            col = C_ACCENT if i == seg or i == (seg-1)%8 else C_BORDER
            rnd.rect(cx+dx-4, cy+dy-4, 8, 8, col)

        rnd.text(rnd.fm, self.loading_msg, W // 2, 230, C_TEXT, center=True)

    def _draw_result(self, rnd):
        rnd.header("Result Output", self.state_cache, self.wifi_ok, self.daemon_ok)
        rnd.panel(20, 70, W - 40, H - 140, C_BORDER, C_BG2)
        for i, line in enumerate(self.result_msg.split("\n")[:11]):
            color = C_ACCENT if i == 0 else C_TEXT
            if "error" in line.lower() or "fail" in line.lower(): color = C_RED
            elif "success" in line.lower() or "connected" in line.lower(): color = C_GREEN
            rnd.text(rnd.fm if i == 0 else rnd.fs, line, 36, 88 + i * 26, color)

        hints = [("A", "OK")]
        if self.login_url: hints.append(("Y", "Show QR Code"))
        rnd.footer(hints)

    def _draw_qr(self, rnd):
        rnd.header("Scan to Authenticate", self.state_cache, self.wifi_ok, self.daemon_ok)
        if not self.qr_matrix:
            rnd.text(rnd.fm, "QR Code Generation Failed", W//2, H//2, C_RED, center=True)
            rnd.footer([("B", "Back")])
            return

        mat, qr_size, quiet = self.qr_matrix, len(self.qr_matrix), 2
        max_w, max_h = W - 20, H - 90
        module_px = max(4, min(max_w, max_h) // (qr_size + quiet * 2))
        total_px = (qr_size + quiet * 2) * module_px
        ox, oy = (W - total_px) // 2, 50 + (max_h - total_px) // 2

        rnd.rect(ox, oy, total_px, total_px, (255, 255, 255))
        for r in range(qr_size):
            for c in range(qr_size):
                if mat[r][c]: rnd.rect(ox + (quiet + c) * module_px, oy + (quiet + r) * module_px, module_px, module_px, (0, 0, 0))
        rnd.footer([("B", "Back")])

# --- Main Initialization & Loop ----------------------------------------------

def find_font():
    # Priorita' al font locale
    if os.path.exists(FONT_PATH):
        return FONT_PATH
    # Fallback a font di sistema
    candidates = [
        "/mnt/mmc/MUOS/application/.terminal/res/SourceCodePro-Regular.ttf",
        "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    for c in candidates:
        if os.path.exists(c): return c
    return None

def main():
    log("Inizio avvio...")
    os.environ["SDL_VIDEODRIVER"], os.environ["DISPLAY"] = "x11", ":0"
    for driver in ["x11", "directfb", "fbcon", ""]:
        if driver: os.environ["SDL_VIDEODRIVER"] = driver
        else: os.environ.pop("SDL_VIDEODRIVER", None)
        if SDL2.SDL_Init(SDL_INIT_VIDEO | SDL_INIT_JOYSTICK | SDL_INIT_GAMECONTROLLER) == 0: break
    else:
        log("SDL_Init fallito con tutti i driver")
        sys.exit(1)
    log("SDL_Init OK")

    if SDL2_TTF.TTF_Init() != 0:
        log("TTF_Init fallito")
        sys.exit(1)
    log("TTF_Init OK")

    # Caricamento Font Locale
    font_path = find_font()
    if not font_path:
        log("ERRORE: nessun font trovato")
        sys.exit(1)
    log("Font caricato: %s" % font_path)

    SDL2.SDL_ShowCursor(0)
    window = SDL2.SDL_CreateWindow(b"Tailscale Ultimate", 0x1FFF0000, 0x1FFF0000, W, H, SDL_WINDOW_SHOWN)
    if not window:
        log("Window creation fail")
        sys.exit(1)
    log("Window creato OK")

    renderer = SDL2.SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED | SDL_RENDERER_SOFTWARE)
    if not renderer:
        renderer = SDL2.SDL_CreateRenderer(window, -1, SDL_RENDERER_SOFTWARE)
    if not renderer:
        log("Renderer creation fail")
        sys.exit(1)
    log("Renderer creato OK")

    try: SDL2.SDL_SetRenderDrawBlendMode(renderer, 1)
    except: pass

    SDL2.SDL_JoystickOpen(0)

    fp = font_path.encode()
    font_small = SDL2_TTF.TTF_OpenFont(fp, 16)
    font_med   = SDL2_TTF.TTF_OpenFont(fp, 20)
    font_large = SDL2_TTF.TTF_OpenFont(fp, 26)
    if not font_med:
        log("ERRORE: font non apribile")
        sys.exit(1)

    rnd = Renderer(renderer, font_small, font_med, font_large)
    app = App()
    event, _last_keepalive = SDL_Event(), time.time()
    log("Tutto ok, avvio loop.")

    while app.running:
        while SDL2.SDL_PollEvent(ctypes.byref(event)):
            t = event.type
            if t == SDL_QUIT: app.running = False
            elif t == SDL_KEYDOWN:
                sym = event.key.sym
                if sym == SDLK_UP: app.handle_input("UP")
                elif sym == SDLK_DOWN: app.handle_input("DOWN")
                elif sym == SDLK_LEFT: app.handle_input("LEFT")
                elif sym == SDLK_RIGHT: app.handle_input("RIGHT")
                elif sym in (SDLK_RETURN, SDLK_a, SDLK_SPACE): app.handle_input("CONFIRM")
                elif sym in (SDLK_ESCAPE, SDLK_b): app.handle_input("BACK")
            elif t == SDL_JOYBUTTONDOWN:
                btn = event.jbutton.button
                if btn == BTN_A: app.handle_input("CONFIRM")
                elif btn == BTN_B: app.handle_input("BACK")
                elif btn == BTN_Y: app.handle_input("NEW_FOLDER")
                elif btn == BTN_START: app.handle_input("BACK")
            elif t == SDL_JOYHATMOTION:
                val = event.jhat.value
                if val == HAT_UP: app.handle_input("UP")
                elif val == HAT_DOWN: app.handle_input("DOWN")
                elif val == HAT_LEFT: app.handle_input("LEFT")
                elif val == HAT_RIGHT: app.handle_input("RIGHT")

        now = time.time()
        if app.screen == "main" and now - app.last_refresh > 10:
            app.last_refresh = now; app._refresh_status()

        if app.exit_pending and time.time() - app.loading_start > 0.8: app.running = False
        app.draw(rnd)
        SDL2.SDL_Delay(16)

    if SDL2_TTF: SDL2_TTF.TTF_Quit()
    SDL2.SDL_DestroyRenderer(renderer)
    SDL2.SDL_DestroyWindow(window)
    SDL2.SDL_Quit()

if __name__ == "__main__":
    main()
