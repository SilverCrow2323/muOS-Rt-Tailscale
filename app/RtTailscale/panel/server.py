#!/usr/bin/env python3
"""Rt:Tailscale-M :: web control panel (standard library only).

Exposes the Tailscale CLI over HTTP + PIN: status, peers, exit node, settings,
Taildrop, Serve/Funnel, ping/netcheck/whois/dns, CLI console, service
management and binary updates.

Run with --update to update the Tailscale binaries from the command line.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import shlex
import signal
import subprocess
import sys
import tarfile
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
CONF = os.path.join(APP, "config", "rt.conf")
PIN_FILE = os.path.join(APP, "config", "panel.pin")
KEY_FILE = os.path.join(APP, "config", "panel.key")
RT = os.path.join(APP, "rt")
BIN_DIR = os.path.join(APP, "bin")
TS = os.path.join(BIN_DIR, "tailscale")
SOCK = os.environ.get("RT_SOCK", "/var/run/tailscale/tailscaled.sock")
RUN = os.environ.get("RT_RUN", "/tmp/rttailscale")
TS_LOG = "/tmp/tailscaled.log"
SESSION_TTL = 7 * 86400
MAX_JSON = 1 << 20

os.makedirs(RUN, exist_ok=True)

# ----------------------------------------------------------------- config ---
CONF_RULES = {
    "PANEL": r"^[01]$",
    "PANEL_PORT": r"^(102[4-9]|10[3-9]\d|1[1-9]\d\d|[2-9]\d{3}|[1-5]\d{4}|6[0-4]\d{3}|65[0-4]\d\d|655[0-2]\d|6553[0-5])$",
    "PANEL_BIND": r"^(127\.0\.0\.1|0\.0\.0\.0)$",
    "WATCHDOG": r"^[01]$",
    "TAILDROP": r"^[01]$",
    "TAILDROP_DIR": r"^(/[\w.\- ]+)*$",
    "TS_MODE": r"^(auto|tun|userspace)$",
    "LOGIN_SERVER": r"^(https?://[\w.\-]+(:\d{1,5})?(/[\w.\-/]*)?)?$",
    "SOCKS5": r"^([\w.\-\[\]:]+:\d{1,5})?$",
    "HTTP_PROXY": r"^([\w.\-\[\]:]+:\d{1,5})?$",
    "TS_EXTRA": r"^[\w.\-=:/, ]{0,200}$",
    "WIFI_WAIT": r"^\d{1,3}$",
}
CONF_DEFAULT = {
    "PANEL": "1", "PANEL_PORT": "8077",
    "PANEL_BIND": "0.0.0.0", "WATCHDOG": "1", "TAILDROP": "1",
    "TAILDROP_DIR": "", "TS_MODE": "auto", "LOGIN_SERVER": "", "SOCKS5": "",
    "HTTP_PROXY": "", "TS_EXTRA": "", "WIFI_WAIT": "120",
}
conf_lock = threading.Lock()


def conf_read():
    out = dict(CONF_DEFAULT)
    try:
        with open(CONF, "r") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k in CONF_DEFAULT:
                    out[k] = v
    except OSError:
        pass
    return out


def conf_write(updates):
    """Validate and save the allowed keys. Returns (ok, error)."""
    for k, v in updates.items():
        if k not in CONF_RULES:
            return False, "key not allowed: %s" % k
        if not isinstance(v, str) or not re.match(CONF_RULES[k], v) or ".." in v:
            return False, "invalid value for %s" % k
    with conf_lock:
        cur = conf_read()
        cur.update(updates)
        tmp = CONF + ".tmp"
        with open(tmp, "w") as f:
            f.write("# Rt:Tailscale-M :: configuration (KEY=VALUE, one per line)\n")
            for k in CONF_DEFAULT:
                f.write("%s=%s\n" % (k, cur[k]))
        os.replace(tmp, CONF)
    return True, ""


# ------------------------------------------------------------------- auth ---
def _read(path):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except OSError:
        return ""


def ensure_secrets():
    if not _read(PIN_FILE):
        with open(PIN_FILE, "w") as f:
            f.write("%08d" % secrets.randbelow(100000000))
    if not _read(KEY_FILE):
        with open(KEY_FILE, "w") as f:
            f.write(secrets.token_hex(32))
    for p in (PIN_FILE, KEY_FILE):
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass


def make_token():
    exp = str(int(time.time()) + SESSION_TTL)
    sig = hmac.new(_read(KEY_FILE).encode(), exp.encode(), hashlib.sha256).hexdigest()
    return "%s.%s" % (exp, sig)


def valid_token(tok):
    try:
        exp, sig = tok.split(".", 1)
        if int(exp) < time.time():
            return False
        good = hmac.new(_read(KEY_FILE).encode(), exp.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, good)
    except (ValueError, AttributeError):
        return False


fails = {}  # ip -> (count, lock_until)
fails_lock = threading.Lock()


def locked(ip):
    with fails_lock:
        c, until = fails.get(ip, (0, 0))
        return until > time.time(), int(until - time.time())


def record_fail(ip):
    with fails_lock:
        c, until = fails.get(ip, (0, 0))
        c += 1
        if c >= 5:
            until = time.time() + min(60 * (c - 4), 900)
        fails[ip] = (c, until)


def record_ok(ip):
    with fails_lock:
        fails.pop(ip, None)


# --------------------------------------------------------------- tailscale ---
def run(cmd, timeout=20, stdin=None):
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           universal_newlines=True, timeout=timeout, input=stdin)
        return {"ok": p.returncode == 0, "rc": p.returncode, "out": p.stdout, "err": p.stderr}
    except subprocess.TimeoutExpired:
        return {"ok": False, "rc": -1, "out": "", "err": "timeout after %ss" % timeout}
    except OSError as e:
        return {"ok": False, "rc": -2, "out": "", "err": str(e)}


def ts(args, timeout=20):
    return run([TS, "--socket", SOCK] + args, timeout)


def rt(*args, timeout=45):
    return run([RT] + list(args), timeout)


def autostart_enabled():
    """True when the muOS init script (/run/muos/storage/init/rttailscale.sh) is installed."""
    return rt("autostart", "status", timeout=8).get("out", "").strip() == "on"


def daemon_running():
    """tailscaled alive: process name or one of the first two argv entries (covers wrappers/interpreters)."""
    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                with open("/proc/%s/comm" % pid) as f:
                    if f.read().strip() == "tailscaled":
                        return True
                with open("/proc/%s/cmdline" % pid, "rb") as f:
                    argv = f.read().split(b"\0")[:2]
                if any(os.path.basename(x.decode(errors="replace")) == "tailscaled" for x in argv):
                    return True
            except OSError:
                continue
    except OSError:
        pass
    return False


def pf_alive(name, pat):
    try:
        pid = int(_read(os.path.join(RUN, name)))
        os.kill(pid, 0)
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            return pat in f.read().replace(b"\0", b" ").decode(errors="replace")
    except (ValueError, OSError):
        return False


def jloads(txt):
    try:
        return json.loads(txt)
    except (ValueError, TypeError):
        return None


def summarize_status():
    d = {"daemon": daemon_running(), "state": "Daemon" if not daemon_running() else "NoState"}
    if not d["daemon"]:
        return d
    r = ts(["status", "--json"], timeout=8)
    j = jloads(r["out"]) if r["ok"] else None
    if not j:
        d["error"] = (r["err"] or r["out"]).strip()[:300]
        return d
    users = j.get("User") or {}

    def user_name(uid):
        u = users.get(str(uid)) or {}
        return u.get("LoginName") or u.get("DisplayName") or ""

    me = j.get("Self") or {}
    d.update({
        "state": j.get("BackendState", "NoState"),
        "authUrl": j.get("AuthURL") or "",
        "version": j.get("Version", ""),
        "health": j.get("Health") or [],
        "tailnet": (j.get("CurrentTailnet") or {}).get("Name", ""),
        "magicDns": (j.get("CurrentTailnet") or {}).get("MagicDNSSuffix", ""),
        "self": {
            "name": me.get("HostName", ""), "dns": (me.get("DNSName") or "").rstrip("."),
            "ips": me.get("TailscaleIPs") or [], "os": me.get("OS", ""),
            "online": me.get("Online", False), "user": user_name(me.get("UserID")),
            "relay": me.get("Relay", ""), "tags": me.get("Tags") or [],
        },
    })
    peers = []
    for p in (j.get("Peer") or {}).values():
        peers.append({
            "id": p.get("ID", ""), "name": p.get("HostName", ""),
            "dns": (p.get("DNSName") or "").rstrip("."), "ips": p.get("TailscaleIPs") or [],
            "os": p.get("OS", ""), "online": bool(p.get("Online")), "active": bool(p.get("Active")),
            "exit": bool(p.get("ExitNode")), "exitOption": bool(p.get("ExitNodeOption")),
            "relay": p.get("Relay", ""), "curAddr": p.get("CurAddr", ""),
            "rx": p.get("RxBytes", 0), "tx": p.get("TxBytes", 0),
            "lastSeen": p.get("LastSeen", ""), "tags": p.get("Tags") or [],
            "user": user_name(p.get("UserID")), "routes": p.get("PrimaryRoutes") or [],
            "ssh": bool(p.get("sshHostKeys") or p.get("SSH_HostKeys")),
        })
    peers.sort(key=lambda x: (not x["online"], x["name"].lower()))
    d["peers"] = peers
    es = j.get("ExitNodeStatus")
    d["exitNode"] = {"online": es.get("Online"), "ips": es.get("TailscaleIPs") or []} if es else None
    pr = ts(["debug", "prefs"], timeout=8)
    prefs = jloads(pr["out"]) if pr["ok"] else None
    if prefs:
        routes = prefs.get("AdvertiseRoutes") or []
        d["prefs"] = {
            "accept-routes": bool(prefs.get("RouteAll")),
            "accept-dns": bool(prefs.get("CorpDNS")),
            "shields-up": bool(prefs.get("ShieldsUp")),
            "ssh": bool(prefs.get("RunSSH")),
            "exit-node-allow-lan-access": bool(prefs.get("ExitNodeAllowLANAccess")),
            "advertise-exit-node": "0.0.0.0/0" in routes,
            "webclient": bool(prefs.get("RunWebClient")),
            "hostname": prefs.get("Hostname", ""),
            "advertise-routes": ",".join(r for r in routes if r not in ("0.0.0.0/0", "::/0")),
            "operator": prefs.get("OperatorUser", ""),
            "controlUrl": prefs.get("ControlURL", ""),
            "wantRunning": bool(prefs.get("WantRunning")),
            "autoUpdate": bool((prefs.get("AutoUpdate") or {}).get("Apply")),
        }
    return d


# ---------------------------------------------------------------- sysinfo ---
def sysinfo():
    info = {"conf": conf_read()}
    try:
        info["hostname"] = open("/proc/sys/kernel/hostname").read().strip()
        info["uptime"] = int(float(open("/proc/uptime").read().split()[0]))
        info["load"] = open("/proc/loadavg").read().split()[:3]
        mem = {}
        for line in open("/proc/meminfo"):
            k, v = line.split(":", 1)
            mem[k] = int(v.split()[0])
        info["memTotal"] = mem.get("MemTotal", 0) * 1024
        info["memFree"] = mem.get("MemAvailable", 0) * 1024
    except (OSError, ValueError, IndexError):
        pass
    bat = ""
    try:
        base = "/sys/class/power_supply"
        for n in sorted(os.listdir(base)):
            p = os.path.join(base, n, "capacity")
            if os.path.exists(p) and "bat" in n.lower():
                bat = _read(p)
                break
    except OSError:
        pass
    info["battery"] = bat
    r = run(["ip", "-4", "-o", "addr", "show", "scope", "global"], 4)
    lan = []
    for line in r["out"].splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[1] != "tailscale0":
            lan.append(parts[3].split("/")[0])
    info["lan"] = lan
    info["tun"] = os.path.exists("/sys/class/net/tailscale0")
    info["python"] = sys.version.split()[0]
    info["services"] = {
        "daemon": daemon_running(),
        "panel": True,
        "watchdog": pf_alive("watchdog.pid", "watchdog"),
        "taildrop": pf_alive("drop.pid", "file get"),
        "autostart": autostart_enabled(),
        "stopped": os.path.exists(os.path.join(RUN, "stopped")),
    }
    v = ts(["version"], 5)
    info["version"] = v["out"].strip().replace("\n", " | ") if v["ok"] else ""
    return info


# ------------------------------------------------------------------ login ---
login_state = {"proc": None, "out": "", "running": False, "started": 0}
login_lock = threading.Lock()


def _login_reader(proc):
    buf = []
    try:
        for line in proc.stdout:
            buf.append(line)
            with login_lock:
                login_state["out"] = "".join(buf)[-4000:]
    except (OSError, ValueError):
        pass
    proc.wait()
    with login_lock:
        login_state["running"] = False
        login_state["out"] = "".join(buf)[-4000:] + "\n[exit %s]" % proc.returncode


def login_stop():
    with login_lock:
        p = login_state["proc"]
    if p and p.poll() is None:
        p.terminate()
        try:
            p.wait(3)
        except subprocess.TimeoutExpired:
            p.kill()
    with login_lock:
        login_state["running"] = False


def login_start(body):
    mode = body.get("mode", "login")
    server = body.get("server", conf_read()["LOGIN_SERVER"])
    key = body.get("authkey", "")
    host = body.get("hostname", "")
    if server and not re.match(CONF_RULES["LOGIN_SERVER"], server):
        return False, "invalid login server"
    if key and not re.match(r"^[\w\-]{10,250}$", key):
        return False, "invalid auth key"
    if host and not re.match(r"^[A-Za-z0-9\-]{1,63}$", host):
        return False, "invalid hostname"
    if not daemon_running():
        return False, "daemon not running"
    login_stop()
    args = [TS, "--socket", SOCK, "up" if mode == "up" else "login"]
    if mode != "up":
        if server:
            args.append("--login-server=" + server)
        if key:
            args.append("--auth-key=" + key)
        if host:
            args.append("--hostname=" + host)
    if server:
        conf_write({"LOGIN_SERVER": server})
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            universal_newlines=True, stdin=subprocess.DEVNULL)
    with login_lock:
        login_state.update({"proc": proc, "out": "", "running": True, "started": time.time()})
    threading.Thread(target=_login_reader, args=(proc,), daemon=True).start()
    return True, ""


# ------------------------------------------------------------------- misc ---
SET_BOOL = {"accept-routes", "accept-dns", "shields-up", "ssh", "advertise-exit-node",
            "exit-node-allow-lan-access", "webclient", "auto-update", "update-check"}
SET_STR = {
    "hostname": r"^[A-Za-z0-9\-]{0,63}$",
    "advertise-routes": r"^([0-9a-fA-F.:/]+(,[0-9a-fA-F.:/]+)*)?$",
    "operator": r"^[\w\-]{0,32}$",
    "exit-node": r"^[\w.\-:]{0,255}$",
}
HOST_RE = r"^[\w.\-:]{1,255}$"
DENY_CLI = {"ssh", "web", "serve", "funnel"}


def tail_file(path, lines=200):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 65536))
            data = f.read().decode(errors="replace")
        return "\n".join(data.splitlines()[-lines:])
    except OSError:
        return ""


def drop_dir():
    d = conf_read()["TAILDROP_DIR"] or os.path.join(APP, "taildrop")
    os.makedirs(d, exist_ok=True)
    return d


def safe_name(name):
    name = os.path.basename(urllib.parse.unquote(name or "")).strip().replace("\0", "")
    name = re.sub(r"[^\w.\- ()\[\]]", "_", name)
    return name[:200] or "file"


def latest_version():
    try:
        req = urllib.request.Request("https://pkgs.tailscale.com/stable/?mode=json",
                                     headers={"User-Agent": "Shin-RtTailscale"})
        with urllib.request.urlopen(req, timeout=8) as r:
            j = json.loads(r.read().decode())
        return {"ok": True, "version": j.get("TarballsVersion", ""), "tarball": (j.get("Tarballs") or {}).get("arm64", "")}
    except Exception as e:  # no network, missing CAs, etc.
        return {"ok": False, "error": str(e)[:200]}


def do_update():
    """Download the latest official arm64 tarball, verify sha256, replace the binaries."""
    lv = latest_version()
    if not lv.get("ok") or not re.match(r"^tailscale_[0-9.]+_arm64\.tgz$", lv.get("tarball", "")):
        return {"ok": False, "err": lv.get("error", "unrecognized tarball")}
    base = "https://pkgs.tailscale.com/stable/" + lv["tarball"]
    tgz = os.path.join(RUN, lv["tarball"])
    try:
        with urllib.request.urlopen(base, timeout=60) as r, open(tgz, "wb") as f:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                f.write(chunk)
        want = ""
        try:
            with urllib.request.urlopen(base + ".sha256", timeout=15) as r:
                want = r.read().decode().split()[0].strip().lower()
        except Exception:
            want = ""
        h = hashlib.sha256()
        with open(tgz, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        if not want:
            return {"ok": False, "err": "sha256 checksum unavailable: update cancelled"}
        if h.hexdigest() != want:
            return {"ok": False, "err": "sha256 mismatch: update cancelled"}
        with tarfile.open(tgz, "r:gz") as t:
            for m in t.getmembers():
                nm = os.path.basename(m.name)
                if nm in ("tailscale", "tailscaled") and m.isfile():
                    data = t.extractfile(m).read()
                    dst = os.path.join(BIN_DIR, nm)
                    if os.path.exists(dst):
                        os.replace(dst, dst + ".bak")
                    with open(dst + ".new", "wb") as o:
                        o.write(data)
                    os.chmod(dst + ".new", 0o755)
                    os.replace(dst + ".new", dst)
        os.remove(tgz)
    except Exception as e:
        return {"ok": False, "err": str(e)[:300]}
    r = rt("daemon", "restart")
    return {"ok": True, "version": lv["version"], "out": r["out"] + r["err"]}


def detach(cmd):
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL, start_new_session=True)


# ------------------------------------------------------------- HTTP layer ---
class Handler(BaseHTTPRequestHandler):
    server_version = "RtTailscale/1.0"

    def log_message(self, fmt, *a):
        pass

    # ---- helpers
    def ip(self):
        return self.client_address[0]

    def send_json(self, code, obj, extra=None):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or []):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def body_json(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n > MAX_JSON:
            self.rfile.read(min(n, MAX_JSON))
            return {}
        raw = self.rfile.read(n) if n else b""
        j = jloads(raw.decode(errors="replace")) if raw else {}
        return j if isinstance(j, dict) else {}

    def authed(self):
        ck = self.headers.get("Cookie", "")
        for part in ck.split(";"):
            k, _, v = part.strip().partition("=")
            if k == "rt_session":
                return valid_token(v)
        return False

    def csrf_ok(self):
        return self.headers.get("X-Rt") == "1"

    # ---- routing
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path in ("/", "/index.html"):
            return self.serve_index()
        if not u.path.startswith("/api/"):
            return self.send_json(404, {"error": "not found"})
        if not self.authed():
            return self.send_json(401, {"error": "auth"})
        q = urllib.parse.parse_qs(u.query)
        p = u.path
        if p == "/api/status":
            return self.send_json(200, summarize_status())
        if p == "/api/sysinfo":
            return self.send_json(200, sysinfo())
        if p == "/api/logs":
            which = (q.get("which") or ["daemon"])[0]
            path = {"daemon": TS_LOG, "rt": os.path.join(RUN, "rt.log"),
                    "panel": os.path.join(RUN, "panel.log"), "drop": os.path.join(RUN, "drop.log")}.get(which)
            if not path:
                return self.send_json(400, {"error": "unknown log"})
            return self.send_json(200, {"text": tail_file(path)})
        if p == "/api/up/state":
            with login_lock:
                s = {"running": login_state["running"], "out": login_state["out"]}
            return self.send_json(200, s)
        if p == "/api/netcheck":
            return self.send_json(200, ts(["netcheck"], 40))
        if p == "/api/dns":
            return self.send_json(200, ts(["dns", "status"], 15))
        if p == "/api/whois":
            t = (q.get("ip") or [""])[0]
            if not re.match(HOST_RE, t):
                return self.send_json(400, {"error": "invalid target"})
            return self.send_json(200, ts(["whois", t], 15))
        if p == "/api/serve":
            r = ts(["serve", "status", "--json"], 10)
            return self.send_json(200, {"ok": r["ok"], "json": jloads(r["out"]) if r["ok"] else None,
                                         "text": r["out"] or r["err"]})
        if p == "/api/latest":
            return self.send_json(200, latest_version())
        if p == "/api/drop/inbox":
            d = drop_dir()
            items = []
            for n in os.listdir(d):
                fp = os.path.join(d, n)
                if os.path.isfile(fp):
                    st = os.stat(fp)
                    items.append({"name": n, "size": st.st_size, "mtime": int(st.st_mtime)})
            items.sort(key=lambda x: -x["mtime"])
            return self.send_json(200, {"dir": d, "items": items})
        if p == "/api/drop/dl":
            return self.drop_download((q.get("name") or [""])[0])
        return self.send_json(404, {"error": "not found"})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        p = u.path
        if p == "/api/login":
            return self.api_login()
        if not self.authed():
            return self.send_json(401, {"error": "auth"})
        if not self.csrf_ok():
            return self.send_json(403, {"error": "csrf"})
        b = self.body_json()
        try:
            return self.post_route(p, b)
        except Exception as e:  # never let the thread die without answering
            return self.send_json(500, {"error": str(e)[:300]})

    def do_PUT(self):
        u = urllib.parse.urlparse(self.path)
        if not self.authed():
            return self.send_json(401, {"error": "auth"})
        if not self.csrf_ok():
            return self.send_json(403, {"error": "csrf"})
        if u.path == "/api/drop/send":
            return self.drop_send(urllib.parse.parse_qs(u.query))
        return self.send_json(404, {"error": "not found"})

    def serve_index(self):
        try:
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                data = f.read()
        except OSError:
            return self.send_json(500, {"error": "index.html missing"})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def api_login(self):
        ip = self.ip()
        is_locked, wait = locked(ip)
        if is_locked:
            return self.send_json(429, {"error": "too many attempts, retry in %ds" % wait})
        b = self.body_json()
        pin = str(b.get("pin", ""))
        if pin and hmac.compare_digest(pin, _read(PIN_FILE)):
            record_ok(ip)
            cookie = "rt_session=%s; HttpOnly; SameSite=Strict; Path=/; Max-Age=%d" % (make_token(), SESSION_TTL)
            return self.send_json(200, {"ok": True}, [("Set-Cookie", cookie)])
        record_fail(ip)
        time.sleep(0.6)
        return self.send_json(403, {"error": "wrong PIN"})

    def post_route(self, p, b):
        if p == "/api/logout":
            return self.send_json(200, {"ok": True}, [("Set-Cookie", "rt_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0")])
        if p == "/api/daemon":
            act = b.get("action")
            if act not in ("start", "stop", "restart"):
                return self.send_json(400, {"error": "invalid action"})
            return self.send_json(200, rt("daemon", act))
        if p == "/api/up":
            ok, err = login_start(b)
            return self.send_json(200 if ok else 400, {"ok": ok, "error": err})
        if p == "/api/up/cancel":
            login_stop()
            return self.send_json(200, {"ok": True})
        if p == "/api/down":
            return self.send_json(200, ts(["down"], 20))
        if p == "/api/logout-node":
            return self.send_json(200, ts(["logout"], 20))
        if p == "/api/set":
            args = []
            for k, v in b.items():
                if k in SET_BOOL:
                    args.append("--%s=%s" % (k, "true" if v in (True, "true", 1) else "false"))
                elif k in SET_STR and isinstance(v, str) and re.match(SET_STR[k], v):
                    args.append("--%s=%s" % (k, v))
                else:
                    return self.send_json(400, {"error": "invalid parameter: %s" % k})
            if not args:
                return self.send_json(400, {"error": "nothing to set"})
            return self.send_json(200, ts(["set"] + args, 20))
        if p == "/api/ping":
            t = str(b.get("target", ""))
            if not re.match(HOST_RE, t):
                return self.send_json(400, {"error": "invalid target"})
            return self.send_json(200, ts(["ping", "-c", "4", "--timeout=3s", t], 30))
        if p == "/api/serve":
            return self.api_serve(b)
        if p == "/api/cli":
            try:
                args = shlex.split(str(b.get("args", "")))
            except ValueError as e:
                return self.send_json(400, {"error": str(e)})
            if not args or args[0] in DENY_CLI or args[0].startswith("-"):
                return self.send_json(400, {"error": "command not allowed (ssh/web are interactive)"})
            return self.send_json(200, ts(args, 40))
        if p == "/api/config":
            upd = {k: str(v) for k, v in b.items() if k in CONF_RULES}
            ok, err = conf_write(upd) if upd else (False, "nothing to save")
            if ok and "PANEL_PORT" in upd:
                detach(["sh", "-c", 'sleep 1; exec "$0" panel restart', RT])
            return self.send_json(200 if ok else 400, {"ok": ok, "error": err})
        if p == "/api/service":
            return self.api_service(b)
        if p == "/api/pin/new":
            r = rt("pin", "new")
            return self.send_json(200, {"ok": r["ok"], "pin": r["out"].strip()},
                                  [("Set-Cookie", "rt_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0")])
        if p == "/api/drop/delete":
            f = os.path.join(drop_dir(), safe_name(str(b.get("name", ""))))
            if os.path.isfile(f):
                os.remove(f)
                return self.send_json(200, {"ok": True})
            return self.send_json(404, {"error": "file not found"})
        if p == "/api/update":
            return self.send_json(200, do_update())
        return self.send_json(404, {"error": "not found"})

    def api_service(self, b):
        what, act = b.get("what"), b.get("action")
        if what == "autostart" and act in ("on", "off"):
            r = rt("autostart", act)
            return self.send_json(200, r)
        if what in ("watchdog", "drop") and act in ("start", "stop", "restart"):
            return self.send_json(200, rt(what, act))
        if what == "panel" and act == "restart":
            detach(["sh", "-c", 'sleep 1; exec "$0" panel restart', RT])
            return self.send_json(200, {"ok": True, "out": "panel restart in progress", "err": ""})
        if what == "all" and act == "restart":
            detach(["sh", "-c", 'sleep 1; exec "$0" restart', RT])
            return self.send_json(200, {"ok": True, "out": "full restart in progress", "err": ""})
        if what == "doctor":
            return self.send_json(200, rt("doctor"))
        return self.send_json(400, {"error": "invalid request"})

    def api_serve(self, b):
        act = b.get("action", "set")
        if act == "reset":
            return self.send_json(200, ts(["serve", "reset"], 15))
        mode = b.get("mode", "serve")
        target = str(b.get("target", ""))
        if mode not in ("serve", "funnel") or not re.match(r"^(\d{1,5}|https?://[\w.\-:\[\]]+(/[\w./\-]*)?|https\+insecure://[\w.\-:\[\]]+(/[\w./\-]*)?)$", target):
            return self.send_json(400, {"error": "invalid mode or target"})
        args = [mode, "--bg"]
        https = str(b.get("https", ""))
        if https:
            if not re.match(r"^\d{2,5}$", https):
                return self.send_json(400, {"error": "invalid https port"})
            args.append("--https=" + https)
        path = str(b.get("path", ""))
        if path:
            if not re.match(r"^/[\w./\-]*$", path):
                return self.send_json(400, {"error": "invalid path"})
            args.append("--set-path=" + path)
        args.append(target)
        return self.send_json(200, ts(args, 30))

    def drop_send(self, q):
        target = (q.get("to") or [""])[0]
        name = safe_name((q.get("name") or [""])[0])
        if not re.match(HOST_RE, target):
            return self.send_json(400, {"error": "invalid recipient"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0:
            return self.send_json(400, {"error": "empty file"})
        updir = os.path.join(RUN, "up")
        os.makedirs(updir, exist_ok=True)
        path = os.path.join(updir, name)
        left = n
        with open(path, "wb") as f:
            while left > 0:
                chunk = self.rfile.read(min(65536, left))
                if not chunk:
                    break
                f.write(chunk)
                left -= len(chunk)
        if left > 0:
            os.remove(path)
            return self.send_json(400, {"error": "upload interrupted"})
        r = ts(["file", "cp", path, target + ":"], 900)
        try:
            os.remove(path)
        except OSError:
            pass
        return self.send_json(200, r)

    def drop_download(self, name):
        fp = os.path.join(drop_dir(), safe_name(name))
        if not os.path.isfile(fp):
            return self.send_json(404, {"error": "file not found"})
        size = os.path.getsize(fp)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", 'attachment; filename="%s"' % os.path.basename(fp).replace('"', "_"))
        self.end_headers()
        with open(fp, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)


class Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--update":
        print(json.dumps(do_update()))
        return
    ensure_secrets()
    port = int(conf_read()["PANEL_PORT"])
    with open(os.path.join(RUN, "panel.pid"), "w") as f:
        f.write(str(os.getpid()))
    srv = Server((conf_read()["PANEL_BIND"], port), Handler)

    def stop(*_):
        threading.Thread(target=srv.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print("[panel] listening on :%d" % port, flush=True)
    try:
        srv.serve_forever()
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
