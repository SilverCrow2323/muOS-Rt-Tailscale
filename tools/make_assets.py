#!/usr/bin/env python3
"""Generate the README artwork and the muOS app icon. Needs: rsvg-convert (librsvg2-bin), Pillow, the Inter font.

  python3 tools/make_assets.py [screenshots_dir]

Outputs:  docs/img/logo.svg|png      project logo (own design: an "M" made of dots, mustard accent)
          docs/img/banner.png        README banner
          docs/img/hero.png          banner + real screenshots
          app/RtTailscale/glyph/rttailscale.png|svg   icon shown in the muOS Applications list (64x64)
The Tailscale mark in the Knulli icon is the official one, UNMODIFIED (geometry from tailscale/tailscale,
client/web/src/assets/icons/tailscale-icon.svg). "Tailscale" is a trademark of Tailscale Inc.
"""
import os
import subprocess
import sys
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "docs", "img")
SHOTS = sys.argv[1] if len(sys.argv) > 1 else "/tmp/shots"
os.makedirs(IMG, exist_ok=True)
os.makedirs(os.path.join(ROOT, "app", "RtTailscale", "glyph"), exist_ok=True)

BG, BG2, BLUE, BLUE_L, TEXT, MUTED = "#1f1e1e", "#2e2d2d", "#f2b01e", "#f2b01e", "#f7f5f4", "#afacab"


def render(svg, png, w=None, h=None):
    cmd = ["rsvg-convert", svg, "-o", png]
    if w:
        cmd += ["-w", str(w)]
    if h:
        cmd += ["-h", str(h)]
    subprocess.run(cmd, check=True)


# ---------------------------------------------------------------- project logo: an M drawn with a 5x5 dot grid
LIT = {(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (4, 0), (4, 1), (4, 2), (4, 3), (4, 4), (1, 1), (3, 1), (2, 2)}   # (col,row)


def logo_group(x, y, size, lit="#f2b01e", dim_opacity=0.2):
    step = size / 5
    out = []
    for r in range(5):
        for c in range(5):
            on = (c, r) in LIT
            out.append(f'<circle cx="{x + step * (c + .5):.2f}" cy="{y + step * (r + .5):.2f}" r="{step * .30:.2f}" '
                       f'fill="{lit if on else "#f7f5f4"}" opacity="{1 if on else dim_opacity}"/>')
    return "\n".join(out)


def tile(size=512, radius=0.22):
    pad = size * 0.2
    return (f'<rect width="{size}" height="{size}" rx="{size * radius}" fill="{BG}"/>'
            f'<rect x="3" y="3" width="{size - 6}" height="{size - 6}" rx="{size * radius - 3}" fill="none" stroke="{BLUE}" stroke-opacity=".55" stroke-width="3"/>'
            + logo_group(pad, pad, size - 2 * pad))


with open(os.path.join(IMG, "logo.svg"), "w") as f:
    f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">{tile()}</svg>')
render(os.path.join(IMG, "logo.svg"), os.path.join(IMG, "logo.png"), 512, 512)

# ---------------------------------------------------------------- banner
def chip(x, y, label, w):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="40" rx="20" fill="#ffffff" fill-opacity=".08" stroke="#ffffff" stroke-opacity=".18"/>'
            f'<text x="{x + w / 2}" y="{y + 26}" text-anchor="middle" font-family="Inter" font-size="19" fill="{TEXT}">{label}</text>')


dots = "".join(f'<circle cx="{40 + i * 36}" cy="{40 + j * 36}" r="2.2" fill="#fff" opacity=".07"/>' for i in range(36) for j in range(11))
banner = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="360" viewBox="0 0 1280 360">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BG}"/><stop offset="1" stop-color="#262a3a"/></linearGradient>
<radialGradient id="glow" cx=".16" cy=".5" r=".6"><stop offset="0" stop-color="{BLUE}" stop-opacity=".45"/><stop offset="1" stop-color="{BLUE}" stop-opacity="0"/></radialGradient></defs>
<rect width="1280" height="360" fill="url(#g)"/><rect width="1280" height="360" fill="url(#glow)"/>{dots}
<g transform="translate(70,70)">{tile(220)}</g>
<text x="330" y="168" font-family="Inter" font-weight="600" font-size="84" fill="{TEXT}">Rt:Tailscale-M</text>
<text x="334" y="216" font-family="Inter" font-size="30" fill="{MUTED}">Tailscale for muOS Andromeda. Made for the D-pad.</text>
{chip(334, 246, "muOS Andromeda", 190)}{chip(538, 246, "L\u00d6VE 11.5", 128)}{chip(680, 246, "arm64", 100)}{chip(794, 246, "Boot script", 150)}{chip(958, 246, "Web panel", 136)}{chip(1108, 246, "MIT", 80)}
</svg>'''
with open(os.path.join(IMG, "banner.svg"), "w") as f:
    f.write(banner)
render(os.path.join(IMG, "banner.svg"), os.path.join(IMG, "banner.png"))
os.remove(os.path.join(IMG, "banner.svg"))

# ---------------------------------------------------------------- hero: banner + real screenshots
def rounded(im, r):
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, im.size[0] - 1, im.size[1] - 1], r, fill=255)
    out = im.convert("RGBA")
    out.putalpha(m)
    return out


def shot(name, scale):
    im = Image.open(os.path.join(SHOTS, name)).convert("RGB")
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    return rounded(im, 18)


hero = Image.open(os.path.join(IMG, "banner.png")).convert("RGBA")
W = hero.width
canvas = Image.new("RGBA", (W, 360 + 520), (31, 30, 30, 255))
canvas.paste(hero, (0, 0))
g = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
d = ImageDraw.Draw(g)
for y in range(360, canvas.height):
    t = (y - 360) / (canvas.height - 360)
    d.line([(0, y), (W, y)], fill=(31 + int(10 * t), 30 + int(12 * t), 30 + int(26 * t), 255))
canvas = Image.alpha_composite(canvas, g)
plan = [("n-02-peers.png", 0.62, 50, 440), ("n-07-dark-peers.png", 0.62, 833, 440), ("n-01-status.png", 0.76, 396, 395)]
for name, sc, x, y in plan:
    sh = shot(name, sc)
    shadow = Image.new("RGBA", (sh.width + 80, sh.height + 80), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([40, 52, sh.width + 40, sh.height + 52], 18, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    canvas.alpha_composite(shadow, (x - 40, y - 40))
    canvas.alpha_composite(sh, (x, y))
canvas.convert("RGB").save(os.path.join(IMG, "hero.png"), optimize=True)

# ---------------------------------------------------------------- muOS Applications icon (official Tailscale mark, unmodified)
CX = [3.8696, 13.0879, 22.1919]
CY = [3.69865, 12.8599, 22.1919]
BRIGHT = {(1, 0), (1, 1), (1, 2), (2, 1)}     # (row, col): middle row + bottom centre are solid
dots = []
S = 330 / 26
for r in range(3):
    for c in range(3):
        dots.append(f'<circle cx="{91 + CX[c] * S:.2f}" cy="{91 + CY[r] * S:.2f}" r="{3.0727 * S:.2f}" fill="#f7f5f4" opacity="{1 if (r, c) in BRIGHT else .2}"/>')
icon = f'''<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
<rect width="512" height="512" rx="96" fill="{BG}"/>
{"".join(dots)}
</svg>'''
gd = os.path.join(ROOT, "app", "RtTailscale", "glyph")
with open(os.path.join(gd, "rttailscale.svg"), "w") as f:
    f.write(icon)
render(os.path.join(gd, "rttailscale.svg"), os.path.join(gd, "rttailscale.png"), 64, 64)
print("assets written")
