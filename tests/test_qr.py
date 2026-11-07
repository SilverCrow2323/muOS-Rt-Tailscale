#!/usr/bin/env python3
"""Cross-check the Lua QR encoder: exact matrix equality with python-qrcode (same version/mask,
byte mode, level M) and a real decode with OpenCV."""
import os, random, string, subprocess, sys, tempfile
import numpy as np
import cv2
import qrcode
from qrcode.util import QRData, MODE_8BIT_BYTE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
random.seed(7)
samples = ["a", "hello", "https://login.tailscale.com/a/1a2b3c4d5e6f",
           "http://192.168.1.50:8077", "http://100.101.102.103:8077"]
for n in (30, 50, 62, 80, 100, 122, 150, 180, 213):
    samples.append("".join(random.choice(string.ascii_letters + string.digits + "/:.-_") for _ in range(n)))

with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
    f.write("\n".join(samples) + "\n")
out = subprocess.run(["luajit", "tests/qr_dump.lua", f.name], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()

i, fails, versions = 0, 0, set()
det = cv2.QRCodeDetector()
for text in samples:
    h = out[i].split(); assert h[0] == "HEADER", out[i]
    ver, mask, size = int(h[1]), int(h[2]), int(h[3])
    rows = out[i + 1:i + 1 + size]; i += 1 + size
    mine = [[c == "1" for c in r] for r in rows]
    q = qrcode.QRCode(version=ver, error_correction=qrcode.constants.ERROR_CORRECT_M, mask_pattern=mask, border=0)
    q.add_data(QRData(text, mode=MODE_8BIT_BYTE)); q.make(fit=False)
    same = q.modules == mine
    # decode with OpenCV (scale up + quiet zone)
    def decode(mods):
        img = np.pad(np.array([[0 if c else 255 for c in r] for r in mods], dtype=np.uint8), 4, constant_values=255)
        dec = ""
        for scale in (8, 12, 16, 24):  # OpenCV's detector needs bigger modules on dense codes
            big = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
            dec, _, _ = det.detectAndDecode(big)
            if dec == text:
                break
        return dec
    dec = decode(mine)
    # OpenCV cannot decode some dense (v10) codes, not even python-qrcode's own: only require
    # a successful decode where the reference code decodes too.
    ok = same and (dec == text or decode(q.modules) != text)
    versions.add(ver)
    fails += (not ok)
    print(("PASS" if ok else "FAIL"), f"v{ver} mask{mask} len={len(text):3d} exact={same} decode={dec == text}")
print("versions covered:", sorted(versions))
sys.exit(1 if fails else 0)
