#!/usr/bin/env python3
"""fizzyappy lab — generates every panel of the profile README.

Commands
  python scripts/lab.py build        rebuild all SVGs + README from lab/*.json
  python scripts/lab.py grow         fetch contributions + latest repo (needs GITHUB_TOKEN), then build
  python scripts/lab.py inoculate    add a visitor colony from ISSUE_TITLE / ISSUE_USER, then build

Needs: pip install fonttools uharfbuzz pillow   (pillow only for the art shelf)
"""
import base64, datetime as dt, hashlib, html, json, math, os, random, re, sys, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from textpath import outline, measure, font_for

ROOT = Path(__file__).resolve().parent.parent
LAB, ASSETS, ART = ROOT / "lab", ROOT / "assets", ROOT / "art"
W = 840

# ───────────────────────────── palette ─────────────────────────────
THEMES = {
    # night pond: indigo water, marigold + rani pink + peacock
    "dark": dict(bg="#0b1026", panel="#0f1631", panel2="#151e42", line="#28325e", ink="#f8efe1",
                 mute="#9ca3c8", faint="#4f5888", agar1="#3b2c13", agar2="#1a1309", glass="#ffffff",
                 pink="#ff4d94", lime="#9be15d", blue="#2ec4b6", orange="#ffb020", violet="#a993ff",
                 yellow="#ffd84d", red="#ff5a3c", water1="#173563", water2="#0b1736", pad="#2f7d4f",
                 shadow="#000000", grain=0.035, mirror="#dfe6ff", kolam="#ffb020"),
    # handmade paper: cream, deep brown ink, same jewel accents a little deeper
    "light": dict(bg="#f6ecda", panel="#f3faf7", panel2="#e6f3ee", line="#d3e8df", ink="#2b1a12",
                  mute="#7a6250", faint="#c2a984", agar1="#f8e7b7", agar2="#e9cd8c", glass="#2b1a12",
                  pink="#d6125c", lime="#4f8f12", blue="#0f8b86", orange="#e07b00", violet="#5b48c8",
                  yellow="#b98f00", red="#d63a1a", water1="#d3ece6", water2="#a8d5cf", pad="#5a9b4b",
                  shadow="#8a6f50", grain=0.08, mirror="#9aa3b8", kolam="#8fd3cb"),
}
ICONS = json.loads((LAB / "icons.json").read_text())

BASE_CSS = """
.serif{font-family:'Fizz Serif',Georgia,serif;font-style:italic}
.sans{font-family:'Fizz Grotesk','Segoe UI',Helvetica,Arial,sans-serif}
.mono{font-family:'Fizz Mono',ui-monospace,Menlo,Consolas,monospace}
.b{font-weight:700}
@media (prefers-reduced-motion: reduce){*{animation:none!important}}
"""

def esc(s):
    return html.escape(str(s), quote=True)

def svg(w, h, body, css="", fonts=(), t=None):
    return outline(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'fill="none" role="img">\n<style>\n{BASE_CSS}\n{css}\n</style>\n{body}\n</svg>\n')

def panel(w, h, t, r=22, extra=""):
    """Panel with a handmade-paper grain."""
    return (f'<defs><filter id="grain" x="0" y="0" width="100%" height="100%">'
            f'<feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="7"/>'
            f'<feColorMatrix values="0 0 0 0 {0.17 if t is THEMES["light"] else 1} 0 0 0 0 {0.1 if t is THEMES["light"] else 1} 0 0 0 0 {0.07 if t is THEMES["light"] else 1} 0 0 0 {t["grain"]*6} -{t["grain"]*2.6}"/>'
            f'<feComposite in2="SourceGraphic" operator="in"/></filter></defs>'
            f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="{r}" fill="{t["panel"]}" stroke="{t["line"]}" {extra}/>'
            f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="{r}" fill="{t["panel"]}" filter="url(#grain)"/>')

def icon(name, x, y, size, color=None):
    """Brand logo from simple-icons (24-unit viewBox)."""
    ic = ICONS.get(name)
    if not ic: return ""
    k = size / 24
    return f'<path transform="translate({x:.1f} {y:.1f}) scale({k:.3f})" d="{ic["d"]}" fill="{color or ic["hex"]}"/>'

def brand_color(name, t):
    c = ICONS.get(name, {}).get("hex", t["ink"])
    return t["ink"] if c.lower() in ("#000000", "#181717", "#ffffff") else c

def mandala(cx, cy, r, c, op=0.12, spin=60, petals=12):
    """Faint rotating mandala — rings of petals and dots."""
    out = []
    for ring, (rr, n, pl) in enumerate([(r, petals, r * .32), (r * .66, petals, r * .26), (r * .36, petals // 2, r * .2)]):
        for i in range(n):
            a = 360 * i / n + (ring % 2) * 180 / n
            out.append(f'<ellipse cx="0" cy="{-rr+pl/2:.1f}" rx="{pl*.36:.1f}" ry="{pl/2:.1f}" transform="rotate({a:.1f})" stroke="{c}" stroke-width="1.1"/>')
        out.append(f'<circle r="{rr:.1f}" stroke="{c}" stroke-width=".8" stroke-dasharray="1 5" stroke-linecap="round"/>')
    out.append(f'<circle r="{r*.1:.1f}" fill="{c}"/>')
    return (f'<g transform="translate({cx} {cy})" opacity="{op}"><g style="animation:spin {spin}s linear infinite">'
            + "".join(out) + '</g></g>')

SPIN_CSS = "@keyframes spin{to{transform:rotate(360deg)}}"

def kolam_border(w, h, t, inset=14, c=None, op=.45):
    c = c or t["kolam"]
    dots = (f'<rect x="{inset}" y="{inset}" width="{w-2*inset}" height="{h-2*inset}" rx="14" stroke="{c}" stroke-opacity="{op}" '
            f'stroke-width="2.2" stroke-dasharray="0 9" stroke-linecap="round"/>')
    corners = ""
    for (x, y, sx, sy) in [(inset, inset, 1, 1), (w-inset, inset, -1, 1), (inset, h-inset, 1, -1), (w-inset, h-inset, -1, -1)]:
        g = "".join(f'<circle cx="{10+i*10}" cy="{10+j*10}" r="1.6" fill="{c}"/>' for i in range(3) for j in range(3))
        loop = f'<path d="M5 20 C5 0, 35 0, 35 20 C35 40, 5 40, 5 20 Z M20 5 C40 5, 40 35, 20 35 C0 35, 0 5, 20 5 Z" stroke="{c}" stroke-width="1.2"/>'
        corners += f'<g transform="translate({x} {y}) scale({sx} {sy}) translate(6 6)" opacity="{op+.2:.2f}">{g}{loop}</g>'
    return dots + corners


def clip_panel(w, h, r=22, cid="pc"):
    return f'<clipPath id="{cid}"><rect x="0" y="0" width="{w}" height="{h}" rx="{r}"/></clipPath>'

def rng(seed):
    return random.Random(int(hashlib.sha256(str(seed).encode()).hexdigest()[:12], 16))

def wrap(text, maxw, cls="sans", size=14):
    """Wrap by real measured width (px)."""
    fn = font_for(cls)
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        cand = f"{cur} {w_}" if cur else w_
        if cur and measure(cand, fn, size) > maxw:
            lines.append(cur); cur = w_
        else:
            cur = cand
    if cur: lines.append(cur)
    return lines

def bubbles(r, n, x0, x1, ybot, ytop, t, color=None, rmin=2, rmax=7, dur=(6, 13), cls="bub", op=0.55):
    """Rising, wobbling, popping bubbles."""
    out = []
    for i in range(n):
        x = r.uniform(x0, x1); rad = r.uniform(rmin, rmax); d = r.uniform(*dur); dl = -r.uniform(0, d)
        c = color or t["ink"]
        wob = r.choice(["wobA", "wobB"])
        out.append(
            f'<g style="animation:{cls} {d:.1f}s linear {dl:.1f}s infinite">'
            f'<g style="animation:{wob} {r.uniform(2.2,3.6):.1f}s ease-in-out {dl:.1f}s infinite alternate">'
            f'<circle cx="{x:.1f}" cy="{ybot:.1f}" r="{rad:.1f}" stroke="{c}" stroke-opacity="{op}" stroke-width="1.2"/>'
            f'<circle cx="{x-rad*0.35:.1f}" cy="{ybot-rad*0.35:.1f}" r="{max(rad*0.22,0.8):.1f}" fill="{c}" fill-opacity="{op*0.9}"/>'
            f'</g></g>')
    rise = ybot - ytop
    css = (f"@keyframes {cls}{{0%{{transform:translateY(0);opacity:0}}8%{{opacity:1}}85%{{opacity:1}}"
           f"100%{{transform:translateY(-{rise:.0f}px);opacity:0}}}}"
           "@keyframes wobA{from{transform:translateX(-3px)}to{transform:translateX(3px)}}"
           "@keyframes wobB{from{transform:translateX(3px)}to{transform:translateX(-4px)}}")
    return "\n".join(out), css


# ───────────────────────────── LIVING POND: time, weather, festivals, feeding ─────────────────────────────
FESTIVALS = {  # date → (name, mode). Edit freely.
    "2026-11-08": ("diwali", "diwali"), "2026-11-07": ("diwali", "diwali"), "2026-11-09": ("diwali", "diwali"),
    "2027-01-14": ("makar sankranti", "kites"), "2027-01-26": ("republic day", "kites"),
    "2027-03-22": ("holi", "holi"), "2027-03-21": ("holi", "holi"),
    "2027-08-15": ("independence day", "kites"),
    "2027-10-28": ("diwali", "diwali"), "2027-10-29": ("diwali", "diwali"), "2027-10-30": ("diwali", "diwali"),
}

def ist_now():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))

def sky_phase(hour):
    if 5 <= hour < 7: return "dawn"
    if 7 <= hour < 17: return "day"
    if 17 <= hour < 19: return "dusk"
    return "night"

def feeds_today(dishd):
    today = ist_now().date().isoformat()
    return [f for f in dishd.get("feeds", []) if f.get("day") == today]

def pond_extras(t, state, dishd, w, h):
    """Returns (under_fish, over_fish, chip_text, feed_spot) SVG fragments."""
    sky = state.get("sky", {})
    phase = sky.get("phase") or sky_phase(ist_now().hour)
    weather = sky.get("weather", "clear")
    temp = sky.get("temp")
    fest = FESTIVALS.get(ist_now().date().isoformat())
    r = rng("extras" + ist_now().date().isoformat())
    under, over = [], []

    # time of day tint
    # no colour tint: the pond keeps its own colours at every hour
    if phase == "night":
        over.append('<circle cx="760" cy="70" r="20" fill="#fff6d8" opacity=".9"/><circle cx="752" cy="64" r="20" fill="#060a24" opacity=".0"/>'
                    '<ellipse cx="760" cy="200" rx="26" ry="6" fill="#fff6d8" opacity=".12" style="animation:shimmer 3s ease-in-out infinite alternate"/>')
        for i in range(16):  # fireflies
            x, y = r.uniform(300, 820), r.uniform(40, 410); d = r.uniform(5, 9)
            over.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="2" fill="#f7ff9e" style="animation:fly{i%3} {d:.1f}s ease-in-out {-r.uniform(0,d):.1f}s infinite alternate">'
                        f'<animate attributeName="opacity" values=".1;1;.1" dur="{r.uniform(1.5,3):.1f}s" repeatCount="indefinite"/></circle>')
    # weather
    if weather == "rain":
        for i in range(26):
            x, y, b = r.uniform(20, 820), r.uniform(20, 410), r.uniform(0, 2.5)
            under.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="1" stroke="{t["ink"]}" stroke-width="1" fill="none" opacity="0">'
                         f'<animate attributeName="r" values="1;14" dur="1.4s" begin="{b:.1f}s" repeatCount="indefinite"/>'
                         f'<animate attributeName="opacity" values=".5;0" dur="1.4s" begin="{b:.1f}s" repeatCount="indefinite"/></circle>')
        for i in range(40):
            x, d = r.uniform(0, 860), r.uniform(.5, .9)
            over.append(f'<line x1="{x:.0f}" y1="-20" x2="{x-6:.0f}" y2="-4" stroke="{t["ink"]}" stroke-opacity=".25" '
                        f'style="animation:rain {d:.2f}s linear {-r.uniform(0,d):.2f}s infinite"/>')
    if weather in ("fog", "smog"):
        for i in range(3):
            over.append(f'<ellipse cx="{200+i*260}" cy="{120+i*110}" rx="260" ry="60" fill="#d9d4cc" opacity=".22" '
                        f'style="animation:fogdrift {30+i*8}s ease-in-out infinite alternate"/>')
    # festivals
    if fest and fest[1] == "diwali":
        for i in range(7):
            x, y = r.uniform(380, 800), r.uniform(60, 400); d = r.uniform(14, 24)
            over.append(f'<g transform="translate({x:.0f} {y:.0f})"><g style="animation:diya {d:.0f}s ease-in-out infinite alternate">'
                        f'<path d="M-10,0 Q0,9 10,0 Z" fill="#c2551d"/><ellipse cx="0" cy="-4" rx="2.6" ry="5" fill="#ffd34d">'
                        f'<animate attributeName="ry" values="5;6.5;5" dur=".6s" repeatCount="indefinite"/></ellipse>'
                        f'<circle cx="0" cy="-4" r="12" fill="#ffb020" opacity=".18"/></g></g>')
        for i in range(10):  # marigold petals
            x, y = r.uniform(300, 830), r.uniform(30, 410)
            over.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r.uniform(3,5):.1f}" fill="{t["orange"]}" opacity=".85"/>')
    if fest and fest[1] == "holi":
        cols = [t["pink"], t["orange"], t["lime"], t["blue"], t["violet"], t["yellow"]]
        for i in range(14):
            x, y, c = r.uniform(300, 830), r.uniform(30, 410), r.choice(cols)
            under.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r.uniform(20,46):.0f}" fill="{c}" opacity=".22"/>')
    if fest and fest[1] == "kites":
        for i, c in enumerate([t["orange"], "#ffffff", t["lime"]]):
            x = 560 + i * 90
            over.append(f'<g style="animation:kite {4+i}s ease-in-out infinite alternate"><path d="M{x},40 l14,18 l-14,22 l-14,-22 Z" fill="{c}" stroke="{t["ink"]}" stroke-opacity=".4"/>'
                        f'<path d="M{x},80 q10,30 -6,60" stroke="{t["ink"]}" stroke-opacity=".3"/></g>')
    # feeding
    fed = feeds_today(dishd)
    spot = None
    if fed:
        sr = rng("spot" + ist_now().date().isoformat())
        spot = (sr.uniform(430, 720), sr.uniform(140, 330))
        n = min(30, 6 + 3 * len(fed))
        for i in range(n):
            a, d = sr.uniform(0, 6.28), sr.uniform(4, 34)
            px, py = spot[0] + math.cos(a) * d, spot[1] + math.sin(a) * d
            under.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2.2" fill="#c98a3a" style="animation:pellet {sr.uniform(2,4):.1f}s ease-in-out infinite alternate"/>')
        under.append(f'<circle cx="{spot[0]:.0f}" cy="{spot[1]:.0f}" r="6" stroke="{t["ink"]}" fill="none" opacity="0">'
                     f'<animate attributeName="r" values="6;50" dur="3s" repeatCount="indefinite"/>'
                     f'<animate attributeName="opacity" values=".5;0" dur="3s" repeatCount="indefinite"/></circle>')
    bits = ["delhi", phase]
    if temp is not None: bits.insert(1, f"{temp}°")
    if weather != "clear": bits.append(weather)
    if fest: bits.append(f"happy {fest[0]}!")
    if fed: bits.append(f"fed {len(fed)}× today")
    return "".join(under), "".join(over), " · ".join(bits), spot

EXTRAS_CSS = ("@keyframes fly0{to{transform:translate(18px,-14px)}}@keyframes fly1{to{transform:translate(-16px,10px)}}@keyframes fly2{to{transform:translate(10px,16px)}}"
              "@keyframes rain{from{transform:translateY(0)}to{transform:translateY(460px)}}"
              "@keyframes fogdrift{from{transform:translateX(-60px)}to{transform:translateX(60px)}}"
              "@keyframes diya{from{transform:translate(0,0)}to{transform:translate(-40px,12px)}}"
              "@keyframes kite{from{transform:translate(0,0) rotate(-4deg)}to{transform:translate(8px,6px) rotate(5deg)}}"
              "@keyframes pellet{from{transform:translateY(0)}to{transform:translateY(2px)}}"
              "@keyframes shimmer{from{opacity:.06}to{opacity:.18}}")

def fetch_sky():
    """Delhi weather + air from open-meteo (no key needed)."""
    def get(u):
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "fizzyappy-lab"}), timeout=20) as r:
            return json.loads(r.read())
    sky = {"phase": sky_phase(ist_now().hour), "weather": "clear"}
    try:
        cw = get("https://api.open-meteo.com/v1/forecast?latitude=28.61&longitude=77.21&current=temperature_2m,weather_code")["current"]
        code = cw["weather_code"]; sky["temp"] = round(cw["temperature_2m"])
        if code in (45, 48): sky["weather"] = "fog"
        elif 51 <= code <= 67 or 80 <= code <= 82 or code >= 95: sky["weather"] = "rain"
    except Exception as e:
        print("weather skipped:", e)
    try:
        aq = get("https://air-quality-api.open-meteo.com/v1/air-quality?latitude=28.61&longitude=77.21&current=pm2_5")["current"]
        if sky["weather"] == "clear" and aq.get("pm2_5", 0) > 150: sky["weather"] = "smog"
    except Exception as e:
        print("air skipped:", e)
    return sky

# ───────────────────────────── HERO: the koi pond ─────────────────────────────
KOI = {  # body colour, patch colours, label
    "kohaku":   ("#fff4e6", ["red"], "kohaku"),
    "marigold": ("orange", ["yellow"], "marigold"),
    "rani":     ("pink", ["#fff4e6"], "rani"),
    "sumi":     ("#1d1a24", ["orange", "#fff4e6"], "sumi"),
    "peacock":  ("blue", ["yellow"], "peacock"),
}

def col(c, t):
    return t.get(c, c)

def koi_fish(kind, t, uid, scale=1.0):
    body, patches, _ = KOI[kind]
    r = rng("koi" + uid)
    bd = "M24,0 C24,-7 14,-9.5 2,-9 C-8,-8.5 -15,-4 -18,0 C-15,4 -8,8.5 2,9 C14,9.5 24,7 24,0 Z"
    ps = "".join(f'<ellipse cx="{r.uniform(-12,16):.1f}" cy="{r.uniform(-6,6):.1f}" rx="{r.uniform(4,8):.1f}" '
                 f'ry="{r.uniform(3,6):.1f}" fill="{col(patches[i % len(patches)], t)}"/>' for i in range(r.randint(2, 4)))
    bc = col(body, t)
    def flap(y, sg):
        return (f'<g><ellipse cx="6" cy="{y}" rx="7" ry="2.6" transform="rotate({sg*35} 10 {y})" fill="{bc}" opacity=".75"/>'
                f'<animateTransform attributeName="transform" type="rotate" values="0 12 {y};{sg*25} 12 {y};0 12 {y}" dur="1.1s" repeatCount="indefinite"/></g>')
    return (f'<g transform="scale({scale})"><g>'
            f'<clipPath id="kb{esc(uid)}"><path d="{bd}"/></clipPath>'
            f'<ellipse cx="4" cy="7" rx="22" ry="8" fill="#000" opacity=".16"/>'
            f'<g><path d="M-17,0 C-24,-3 -30,-10 -37,-12 C-33,-5 -33,5 -37,12 C-30,10 -24,3 -17,0 Z" fill="{bc}" opacity=".8"/>'
            f'<animateTransform attributeName="transform" type="rotate" values="-16 -17 0;16 -17 0;-16 -17 0" dur=".9s" repeatCount="indefinite"/></g>'
            f'{flap(-8, -1)}{flap(8, 1)}'
            f'<path d="{bd}" fill="{bc}"/>'
            f'<g clip-path="url(#kb{esc(uid)})">{ps}</g>'
            f'<path d="M-6,-1 C2,-2 12,-2 20,0" stroke="#000" stroke-opacity=".12" stroke-width="1.2"/>'
            f'<circle cx="18" cy="-3.6" r="1.3" fill="#120d10"/><circle cx="18" cy="3.6" r="1.3" fill="#120d10"/>'
            f'<animateTransform attributeName="transform" type="rotate" values="-5;5;-5" dur="1.8s" repeatCount="indefinite"/>'
            f'</g></g>')

def wander(seed, x0, y0, x1, y1, n=6):
    r = rng(seed)
    cx_, cy_ = (x0 + x1) / 2, (y0 + y1) / 2
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n + r.uniform(-.4, .4)
        pts.append((cx_ + math.cos(a) * (x1 - x0) / 2 * r.uniform(.45, 1),
                    cy_ + math.sin(a) * (y1 - y0) / 2 * r.uniform(.45, 1)))
    if r.random() < .5: pts.reverse()
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f} "
    for i in range(n):  # closed Catmull-Rom → Bézier, so the swim is smooth
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f} "
    return d + "Z"

def lotus_pad(x, y, rr, t, i):
    notch = (f"M0,0 L{rr*math.cos(-.25):.1f},{rr*math.sin(-.25):.1f} "
             f"A{rr},{rr} 0 1 0 {rr*math.cos(.25):.1f},{rr*math.sin(.25):.1f} Z")
    veins = "".join(f'<line x1="0" y1="0" x2="{rr*.85*math.cos(a):.1f}" y2="{rr*.85*math.sin(a):.1f}" stroke="#000" stroke-opacity=".12"/>'
                    for a in [0.8 + k * 0.75 for k in range(7)])
    return (f'<g transform="translate({x} {y})"><g style="animation:padspin {40+i*13}s ease-in-out infinite alternate">'
            f'<ellipse cx="3" cy="5" rx="{rr}" ry="{rr*.92:.1f}" fill="#000" opacity=".15"/>'
            f'<path d="{notch}" fill="{t["pad"]}"/>{veins}'
            f'<circle r="{rr*.8:.1f}" stroke="#fff" stroke-opacity=".14" stroke-dasharray="2 6"/></g></g>')

def lotus_flower(x, y, t):
    petals = "".join(f'<ellipse cx="0" cy="-11" rx="5.5" ry="12" transform="rotate({a})" fill="{t["pink"]}" opacity="{o}"/>'
                     for a, o in [(-60, .65), (60, .65), (-30, .85), (30, .85), (0, 1)])
    return (f'<g transform="translate({x} {y})"><g style="animation:bob 4s ease-in-out infinite alternate">{petals}'
            f'<ellipse cx="0" cy="-4" rx="6" ry="3" fill="{t["yellow"]}"/></g></g>')

def hero(cfg, t, mode, dishd=None, state=None):
    w, h = W, 430
    dishd = dishd or {}
    under, over, chip, spot = pond_extras(t, state or {}, dishd, w, h)
    caus = "".join(
        f'<path d="M-70,{y} ' + "q35,-10 70,0 t70,0 " * 14 + f'" stroke="{t["ink"]}" stroke-opacity=".07" stroke-width="1.4" '
        f'style="animation:drift {14+i*3}s linear infinite {-i*2}s"/>' for i, y in enumerate(range(60, 430, 52)))
    rip = "".join(
        f'<circle cx="{x}" cy="{y}" r="2" stroke="{t["ink"]}" stroke-width="1.2" fill="none" opacity="0">'
        f'<animate attributeName="r" values="2;42" dur="5s" begin="{b}s" repeatCount="indefinite"/>'
        f'<animate attributeName="opacity" values=".45;0" dur="5s" begin="{b}s" repeatCount="indefinite"/></circle>'
        for x, y, b in [(560, 120, 0), (720, 300, 1.6), (380, 380, 3.1), (220, 70, 4.2), (800, 200, 2.4)])
    fish, labels = [], []
    residents = [("kohaku", "r1"), ("marigold", "r2"), ("rani", "r3"), ("sumi", "r4"), ("kohaku", "r5")]
    visitors = [v for v in (dishd.get("koi") or []) if v.get("koi") in KOI][-int(load("config.json").get("max_visitor_koi", 10)):]
    allk = [(k, u, None, 1.05, "") for k, u in residents] + [(v["koi"], "v" + v["user"], v["user"], .9, v.get("name", "")) for v in visitors]
    for kind, uid, user, sc, name in allk:
        rr = rng("path" + uid)
        if spot and not user:   # fed today: residents gather around the food
            d = wander("path" + uid + "fed", spot[0]-120, spot[1]-90, spot[0]+120, spot[1]+90, n=rr.choice([5, 6]))
        else:
            d = wander("path" + uid, 40, 40, 800, 395, n=rr.choice([5, 6, 7]))
        dur = rr.uniform(26, 44); beg = -rr.uniform(0, dur)
        fish.append(f'<g>{koi_fish(kind, t, uid, sc)}'
                    f'<animateMotion path="{d}" dur="{dur:.1f}s" begin="{beg:.1f}s" repeatCount="indefinite" rotate="auto"/></g>')
        if user:
            labels.append(f'<g><g transform="translate(0 -20)"><text x="0" y="0" text-anchor="middle" class="mono" font-size="10" '
                          f'fill="{t["mute"]}" opacity=".6">{esc(name + " · ") if name else ""}@{esc(user)}</text></g>'
                          f'<animateMotion path="{d}" dur="{dur:.1f}s" begin="{beg:.1f}s" repeatCount="indefinite"/></g>')
    pads = (lotus_pad(640, 352, 40, t, 0) + lotus_pad(778, 96, 28, t, 1) + lotus_pad(92, 380, 24, t, 2)
            + lotus_pad(500, 398, 18, t, 3) + lotus_pad(712, 398, 20, t, 4))
    roles = cfg["roles"]; n = len(roles); per = 3.2; total = per * n
    role_txt = "".join(
        f'<text x="54" y="262" class="sans" font-size="27" fill="{t["pink"]}" '
        f'style="animation:role {total}s infinite {i*per - total:.1f}s;opacity:0">{esc(ro)}</text>'
        for i, ro in enumerate(roles))
    p1 = 100 / n
    role_css = (f"@keyframes role{{0%{{opacity:0;transform:translateY(10px)}}{p1*0.12:.1f}%{{opacity:1;transform:translateY(0)}}"
                f"{p1*0.85:.1f}%{{opacity:1;transform:translateY(0)}}{p1:.1f}%{{opacity:0;transform:translateY(-10px)}}100%{{opacity:0}}}}")
    um = measure("~/" + cfg["user"], "mono", 13 * 1.2)
    body = f"""<defs>{clip_panel(w, h)}
<radialGradient id="water" cx=".35" cy=".3" r=".9"><stop offset="0" stop-color="{t["water1"]}"/><stop offset="1" stop-color="{t["water2"]}"/></radialGradient>
<linearGradient id="fade" x1="0" x2="1"><stop offset="0" stop-color="{t["water2"]}" stop-opacity=".78"/><stop offset=".58" stop-color="{t["water2"]}" stop-opacity="0"/></linearGradient>
</defs>
{panel(w, h, t)}
<g clip-path="url(#pc)">
  <rect width="{w}" height="{h}" fill="url(#water)"/>
  {caus}{rip}{under}
  {"".join(fish)}
  {pads}
  {lotus_flower(640, 346, t)}
  <rect width="{w}" height="{h}" fill="url(#fade)"/>
  {"".join(labels)}
  {over}
  {mandala(w-20, 20, 120, t["kolam"], .22, 90)}
</g>
<g transform="translate({w-30} {h-26})"><text x="0" y="0" text-anchor="end" class="mono" font-size="10.5" fill="{t["ink"]}" opacity=".75">{esc(chip)}</text></g>
{kolam_border(w, h, t)}
<text x="54" y="74" class="mono" font-size="13" fill="{t["mute"]}">~/{esc(cfg["user"])}</text>
<circle cx="{62+um:.0f}" cy="69.5" r="4" fill="{t["kolam"]}" style="animation:blink 1.6s ease-in-out infinite"/>
<text x="{72+um:.0f}" y="74" class="mono" font-size="13" fill="{t["mute"]}">pond &amp; lab notebook, vol. {dt.date.today():%y}</text>
<text x="50" y="188" class="serif" font-size="88" data-max="540" fill="{t["ink"]}" letter-spacing="-1">{esc(cfg["name"])}</text>
<text x="54" y="226" class="sans" font-size="17" fill="{t["mute"]}">hi, i'm a</text>
{role_txt}
<text x="54" y="314" class="sans" font-size="15" fill="{t["ink"]}" opacity=".8">{esc(cfg["tagline"])}</text>
<g transform="translate(54 342)">
  <rect width="190" height="24" rx="12" fill="{t["panel"]}" fill-opacity=".75" stroke="{t["kolam"]}" stroke-opacity=".9"/>
  <circle cx="13" cy="12" r="3" fill="{t["pink"]}" style="animation:blink 1.6s ease-in-out infinite"/>
  <text x="23" y="16" class="mono" font-size="9.5" fill="{t["ink"]}">release your own koi below ↓</text>
</g>"""
    css = (role_css + SPIN_CSS + EXTRAS_CSS +
           "@keyframes drift{from{transform:translateX(0)}to{transform:translateX(-140px)}}"
           "@keyframes padspin{from{transform:rotate(-14deg)}to{transform:rotate(18deg) translate(5px,-4px)}}"
           "@keyframes bob{from{transform:translateY(0) rotate(-3deg)}to{transform:translateY(-3px) rotate(3deg)}}"
           "@keyframes blink{0%,100%{opacity:1}50%{opacity:.25}}")
    return svg(w, h, body, css)

# ───────────────────────────── LIPPAN DIVIDER ─────────────────────────────
def divider(cfg, t, mode):
    w, h = W, 46
    n = 21; step = (w - 60) / (n - 1)
    out = []
    for i in range(n):
        x = 30 + i * step; y = h / 2
        shape = i % 3
        if shape == 0:   # diamond with mirror
            out.append(f'<path d="M{x},{y-15} L{x+11},{y} L{x},{y+15} L{x-11},{y} Z" stroke="{t["kolam"]}" stroke-width="1.6"/>')
            out.append(f'<circle cx="{x}" cy="{y}" r="5" fill="url(#mir)"/>')
            out.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#fff" style="animation:glint 4.2s ease-in-out {i*0.2:.1f}s infinite;opacity:0"/>')
        elif shape == 1:
            out.append(f'<circle cx="{x}" cy="{y}" r="3.2" fill="url(#mir)" stroke="{t["pink"]}" stroke-width="1.2"/>')
        else:
            out.append(f'<path d="M{x-6},{y} q6,-9 12,0 q-6,9 -12,0" stroke="{t["blue"]}" stroke-width="1.4"/>')
    body = (f'<defs><radialGradient id="mir" cx=".35" cy=".35"><stop offset="0" stop-color="#ffffff"/>'
            f'<stop offset=".6" stop-color="{t["mirror"]}"/><stop offset="1" stop-color="#6b7390"/></radialGradient></defs>'
            f'<line x1="10" y1="{h/2}" x2="{w-10}" y2="{h/2}" stroke="{t["kolam"]}" stroke-opacity=".5" stroke-dasharray="1 6" stroke-linecap="round" stroke-width="2"/>'
            + "".join(out))
    return svg(w, h, body, "@keyframes glint{0%,100%{opacity:0}8%{opacity:.95}18%{opacity:0}}")

# ───────────────────────────── READOUTS ─────────────────────────────
def readouts(cfg, t, mode):
    w, h = W, 150
    items = cfg["readouts"]; cw = w / len(items)
    cells = []
    for i, it in enumerate(items):
        x = i * cw
        col = t[it["color"]]
        live = (f'<circle cx="{x+cw-34}" cy="34" r="5" fill="{col}" style="animation:blink 1.4s infinite"/>'
                f'<text x="{x+cw-44}" y="38" text-anchor="end" class="mono" font-size="10" fill="{t["mute"]}">live</text>') if it.get("live") else ""
        sep = f'<line x1="{x}" y1="28" x2="{x}" y2="{h-28}" stroke="{t["line"]}"/>' if i else ""
        cells.append(f'''{sep}{live}
<text x="{x+30}" y="86" class="serif" font-size="62" fill="{col}">{esc(it["value"])}</text>
<text x="{x+30}" y="112" class="sans" font-size="14" fill="{t["ink"]}">{esc(it["label"][0])}</text>
<text x="{x+30}" y="130" class="sans" font-size="14" fill="{t["mute"]}">{esc(it["label"][1])}</text>''')
    body = panel(w, h, t) + "".join(cells)
    return svg(w, h, body, "@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}", ("serif-italic", "grotesk", "mono"))

# ───────────────────────────── PERIODIC TABLE ─────────────────────────────
CUSTOM = {
    "Ag": "M12 2 L14 10 L22 12 L14 14 L12 22 L10 14 L2 12 L10 10 Z",
    "Dg": "M4 20c3 0 5-2 5-5l9-9a2 2 0 0 0-3-3l-9 9c-3 0-5 2-5 5z",
    "Br": "M12 3a9 9 0 1 0 0 18c1.5 0 2-1 2-2s-1-1.5-1-2.5 1-1.5 2-1.5h2a4 4 0 0 0 4-4c0-4.5-4-8-9-8z M7.5 11h.01 M10 7h.01 M15 7h.01",
    "Po": "M5 3h14v18H5z M8 7h8 M8 11h8 M8 15h5",
    "Wd": "M3 5h18v14H3z M3 9h18 M6 7h.01 M9 7h.01",
    "Bp": "M8 3h8 M10 3v5l-5 10a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-10V3 M7 15h10",
    "Ek": "M12 3a9 9 0 1 0 9 9h-9z M15 3v6h6",
    "Mm": "M6 6m-2.2 0a2.2 2.2 0 1 0 4.4 0a2.2 2.2 0 1 0-4.4 0 M18 6m-2.2 0a2.2 2.2 0 1 0 4.4 0a2.2 2.2 0 1 0-4.4 0 M12 18m-2.2 0a2.2 2.2 0 1 0 4.4 0a2.2 2.2 0 1 0-4.4 0 M8.2 6h7.6 M7 8l4 8 M17 8l-4 8",
    "Sp": "M2 14c2-9 4-9 5 0s3 9 5 0 3-9 5 0 3 9 5 0",
    "Pi": "M3 12h5 M16 12h5 M8 7v10l8-10v10z",
    "Sq": "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6 M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
    "Rs": "M8 4l-5 8 5 8 M16 4l5 8-5 8 M10 12h4",
    "Aw": "M5 21l6-12-2.5-5H5 M11 9l6 12h3 M8.5 4H11",
    "Xl": "M4 4h16v16H4z M4 9h16 M4 15h16 M10 4v16 M13 11l4 6 M17 11l-4 6",
    "Mp": "M3 3v18h18 M7 15l4-5 3 3 6-7 M7 19v-3 M12 19v-6 M17 19v-9",
    "Nl": "M4 5h16v10H9l-5 4z M8 9h8 M8 12h5",
    "Cv": "M18 8a7 7 0 1 0 0 8 M12 3a9 9 0 1 1 0 18",
    "Hb": "M7 7m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0 M17 9m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0 M10 17m-2.5 0a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0-5 0 M9 8l6 1 M8 9l1.5 5.5 M15.5 11l-4 4",
}
BRAND = {"Py": "Python", "Js": "JavaScript", "Ts": "TypeScript", "Ja": "Java", "Re": "React", "Nd": "Node", "Ht": "HTML",
         "Vc": "Vercel", "Gm": "Gemini", "Gt": "Git", "Gh": "GitHub", "Fa": "FastAPI", "At": "Airtable", "Pd": "pandas",
         "Np": "NumPy", "Sk": "scikit-learn", "Tf": "TensorFlow", "Ju": "Jupyter", "Fg": "Figma"}

def periodic(cfg, t, mode):
    els = cfg["elements"]; cols = 9
    tw, th, gap, y0 = 82, 104, 7, 92
    x0 = (W - (cols * tw + (cols - 1) * gap)) / 2
    rows = math.ceil(len(els) / cols)
    w, h = W, y0 + rows * (th + gap) + 34
    gc = {"code": t["blue"], "data": t["orange"], "design": t["pink"], "bio": t["lime"]}
    tiles = []
    n = len(els); cyc = 9.0
    for i, (sym, name, g) in enumerate(els):
        cx_, cy_ = x0 + (i % cols) * (tw + gap), y0 + (i // cols) * (th + gap)
        c = gc[g]
        tiles.append(f'''<g transform="translate({cx_} {cy_})">
<rect width="{tw}" height="{th}" rx="10" fill="{c}" fill-opacity=".08" stroke="{c}" stroke-opacity=".45"/>
<rect width="{tw}" height="{th}" rx="10" fill="{c}" style="animation:glow {cyc}s ease-in-out {i*cyc/n - cyc:.2f}s infinite;opacity:0"/>
<text x="9" y="18" class="mono" font-size="10" fill="{t["mute"]}">{i+1}</text>
{icon(BRAND[sym], tw/2-13, 22, 26, brand_color(BRAND[sym], t)) if sym in BRAND else (f'<path transform="translate({tw/2-13} 22) scale(1.083)" d="{CUSTOM[sym]}" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>' if sym in CUSTOM else "")}
<text x="{tw-9}" y="18" text-anchor="end" class="sans b" font-size="15" fill="{t["ink"]}">{esc(sym)}</text>
<text x="{tw/2}" y="74" text-anchor="middle" class="sans b" font-size="12.5" fill="{t["ink"]}">{esc(name if len(name) < 13 else name.split()[0])}</text>
<text x="{tw/2}" y="91" text-anchor="middle" class="mono" font-size="8.5" fill="{c}">{esc(g)}</text>
</g>''')
    legend = "".join(
        f'<circle cx="{450+i*90}" cy="54" r="5" fill="{gc[k]}"/><text x="{461+i*90}" y="58" class="sans" font-size="13" fill="{t["mute"]}">{k}</text>'
        for i, k in enumerate(["code", "data", "design", "bio"]))
    body = f'''{panel(w, h, t)}
{mandala(W-40, 40, 70, t["orange"], .12, 80)}
<text x="28" y="60" class="serif" font-size="32" data-max="380" fill="{t["ink"]}">periodic table of me</text>
{legend}
{"".join(tiles)}
<text x="28" y="{h-14}" class="mono" font-size="11" fill="{t["faint"]}">no. 37 not yet discovered · stable at room temperature · reacts well with deadlines</text>'''
    css = SPIN_CSS + "@keyframes glow{0%{opacity:0}6%{opacity:.28}16%{opacity:0}100%{opacity:0}}"
    return svg(w, h, body, css, ("serif-italic", "grotesk", "grotesk-bold", "mono"))

# ───────────────────────────── PROJECT CARDS ─────────────────────────────
def motif(kind, c, t):
    if kind == "chart":
        bars = "".join(f'<rect x="{i*12}" y="{40-hh}" width="8" height="{hh}" rx="2" fill="{c}" opacity="{0.35+i*0.1:.2f}" '
                       f'style="animation:bar 2.4s ease-in-out {i*0.18:.2f}s infinite alternate;transform-box:fill-box;transform-origin:bottom"/>'
                       for i, hh in enumerate([14, 24, 18, 32, 40]))
        return bars
    if kind == "orb":
        return (f'<circle cx="28" cy="22" r="11" fill="{c}" style="animation:pulse 2.2s ease-in-out infinite;transform-box:fill-box;transform-origin:center"/>'
                f'<circle cx="28" cy="22" r="18" stroke="{c}" stroke-opacity=".5" style="animation:ring 2.2s ease-out infinite;transform-box:fill-box;transform-origin:center"/>'
                f'<circle cx="28" cy="22" r="26" stroke="{c}" stroke-opacity=".25" style="animation:ring 2.2s ease-out .6s infinite;transform-box:fill-box;transform-origin:center"/>')
    if kind == "element":
        return (f'<rect x="6" y="0" width="44" height="48" rx="7" stroke="{c}" stroke-width="1.5"/>'
                f'<text x="11" y="12" class="mono" font-size="8" fill="{c}">8</text>'
                f'<text x="28" y="36" text-anchor="middle" class="sans b" font-size="20" fill="{c}">O</text>'
                f'<circle cx="28" cy="24" r="30" stroke="{c}" stroke-opacity=".35" stroke-dasharray="3 5" style="animation:spin 12s linear infinite;transform-box:fill-box;transform-origin:center"/>')
    if kind == "nib":
        return (f'<path d="M28 2 L44 26 L28 46 L12 26 Z" stroke="{c}" stroke-width="1.6" fill="{c}" fill-opacity=".12"/>'
                f'<line x1="28" y1="18" x2="28" y2="46" stroke="{c}" stroke-width="1.4"/><circle cx="28" cy="18" r="3" fill="{c}"/>'
                f'<path d="M-6 54 q12 -8 22 0 t22 0 t22 0" stroke="{c}" stroke-width="1.6" stroke-dasharray="80" '
                f'style="animation:draw 3s ease-in-out infinite"/>')
    if kind == "brush":
        return (f'<text x="4" y="40" class="serif" font-size="40" fill="{c}">Ss</text>'
                f'<path d="M2 48 C 18 42, 36 52, 54 44" stroke="{c}" stroke-width="3" stroke-linecap="round" opacity=".7"/>')
    if kind == "brush_old":
        return (f'<path d="M0 40 C 14 6, 34 52, 56 12" stroke="{c}" stroke-width="7" stroke-linecap="round" stroke-dasharray="90" '
                f'style="animation:draw 3.4s ease-in-out infinite"/>'
                f'<circle cx="56" cy="12" r="4" fill="{t["ink"]}"/>')
    if kind == "line":
        sticks = [(6, 30, 40, 26, 36, 1), (18, 22, 36, 24, 32, 0), (30, 14, 30, 18, 26, 1), (42, 6, 22, 8, 16, 1)]
        out = ""
        for x, hi, lo, o, c_, up in sticks:
            cc = c if up else t["pink"]
            out += f'<line x1="{x+3}" y1="{hi}" x2="{x+3}" y2="{lo}" stroke="{cc}" stroke-width="1.4"/><rect x="{x}" y="{min(o,c_)}" width="6" height="{abs(o-c_)+3}" rx="1" fill="{cc}"/>'
        return out + f'<line x1="0" y1="48" x2="54" y2="48" stroke="{c}" stroke-opacity=".4"/>'
    if kind == "line_old":
        return (f'<polyline points="0,40 10,34 18,38 28,20 38,26 48,8 58,14" stroke="{c}" stroke-width="2" stroke-dasharray="90" '
                f'style="animation:draw 3s ease-in-out infinite"/>'
                f'<line x1="0" y1="46" x2="58" y2="46" stroke="{t["line"]}"/>')
    return ""

CARD_CSS = ("@keyframes bar{from{transform:scaleY(.55)}to{transform:scaleY(1)}}"
            "@keyframes pulse{0%,100%{transform:scale(.85)}50%{transform:scale(1.05)}}"
            "@keyframes ring{0%{transform:scale(.6);opacity:1}100%{transform:scale(1.4);opacity:0}}"
            "@keyframes spin{to{transform:rotate(360deg)}}"
            "@keyframes draw{0%{stroke-dashoffset:90}60%,100%{stroke-dashoffset:0}}"
            "@keyframes sheen{0%{transform:translateX(-300px)}100%{transform:translateX(700px)}}")

def logo_img(p, w):
    f = LAB / f"{p['id']}-logo.svg"
    if not f.exists(): return ""
    b64 = base64.b64encode(f.read_bytes()).decode()
    return f'<image href="data:image/svg+xml;base64,{b64}" x="{w-84}" y="28" width="52" height="52"/>'

def card(p, t, mode):
    w, h = 412, 236
    c = t[p["color"]]
    lines = wrap(p["blurb"], 352, "sans", 14.5)[:4]
    blurb = "".join(f'<text x="26" y="{112+i*21}" class="sans" font-size="14.5" fill="{t["mute"]}">{esc(l)}</text>' for i, l in enumerate(lines))
    tx, tags = 26, []
    for tg in p["tags"]:
        has = tg in ICONS
        tw = 18 + measure(tg, "mono", 10.5) + (16 if has else 0)
        tags.append(f'<rect x="{tx}" y="{h-44}" width="{tw}" height="22" rx="11" fill="{c}" fill-opacity=".12"/>'
                    + (icon(tg, tx + 8, h - 39, 12, brand_color(tg, t)) if has else "")
                    + f'<text x="{tx+tw/2+(8 if has else 0)}" y="{h-29}" text-anchor="middle" class="mono" font-size="10.5" fill="{c}">{esc(tg)}</text>')
        tx += tw + 6
    body = f'''<defs>{clip_panel(w, h, 20)}
<linearGradient id="sh" x1="0" x2="1"><stop offset="0" stop-color="{t["ink"]}" stop-opacity="0"/><stop offset=".5" stop-color="{t["ink"]}" stop-opacity=".06"/><stop offset="1" stop-color="{t["ink"]}" stop-opacity="0"/></linearGradient></defs>
{panel(w, h, t, 20)}
<g clip-path="url(#pc)">
  <circle cx="{w-30}" cy="10" r="110" fill="{c}" opacity=".08"/>
  <rect x="0" y="0" width="160" height="{h}" fill="url(#sh)" transform="skewX(-20)" style="animation:sheen 7s ease-in-out {int(p["no"])*0.9:.1f}s infinite"/>
</g>
<text x="26" y="40" class="mono" font-size="11" fill="{c}">No. {esc(p["no"])}</text>
<text x="70" y="40" class="mono" font-size="11" fill="{t["mute"]}">{esc(p["kind"])}</text>
<text x="24" y="82" class="serif" font-size="38" data-max="272" fill="{t["ink"]}">{esc(p["title"])}</text>
<rect x="{w-90}" y="22" width="64" height="64" rx="16" fill="{c}" fill-opacity=".10" stroke="{c}" stroke-opacity=".45"/>
{logo_img(p, w) or (f'<text x="{w-58}" y="70" text-anchor="middle" class="serif" font-size="40" fill="{c}">{esc(p["title"][:1].upper())}</text>' if p["motif"] == "initial" else f'<g transform="translate({w-86} 32) scale(.92)">{motif(p["motif"], c, t)}</g>')}
{blurb}
{"".join(tags)}
<text x="{w-26}" y="{h-28}" text-anchor="end" class="sans b" font-size="13" fill="{t["ink"]}">{esc(p["cta"])} ↗</text>'''
    return svg(w, h, body, CARD_CSS, ("serif-italic", "grotesk", "grotesk-bold", "mono"))

# ───────────────────────────── WET LAB ─────────────────────────────
def wet_icon(kind, c, t):
    if kind == "dish":
        return (f'<circle cx="26" cy="26" r="24" stroke="{c}" stroke-width="1.6"/><circle cx="26" cy="26" r="19" stroke="{c}" stroke-opacity=".4"/>'
                + "".join(f'<circle cx="{x}" cy="{y}" r="{r_}" fill="{c}" opacity=".8" style="animation:breath 3s ease-in-out {i*0.4}s infinite;transform-box:fill-box;transform-origin:center"/>'
                          for i, (x, y, r_) in enumerate([(19, 20, 4), (32, 30, 5), (24, 34, 2.5), (33, 17, 2)])))
    if kind == "leaf":
        return (f'<path d="M6 46 C 6 16, 30 4, 48 4 C 48 26, 34 46, 6 46 Z" stroke="{c}" stroke-width="1.6" fill="{c}" fill-opacity=".1"/>'
                f'<path d="M6 46 L 38 14" stroke="{c}" stroke-width="1.3"/>'
                f'<polyline points="0,58 8,58 12,50 16,64 20,54 26,58 52,58" stroke="{c}" stroke-width="1.4" stroke-dasharray="80" style="animation:draw 3s ease-in-out infinite"/>')
    if kind == "pid":
        return (f'<circle cx="12" cy="26" r="10" stroke="{c}" stroke-width="1.6"/><rect x="32" y="10" width="20" height="34" rx="6" stroke="{c}" stroke-width="1.6"/>'
                f'<line x1="22" y1="26" x2="32" y2="26" stroke="{c}" stroke-width="1.6"/>'
                f'<line x1="42" y1="44" x2="42" y2="58" stroke="{c}" stroke-width="1.6"/><circle cx="42" cy="51" r="3" fill="{c}"/>'
                f'<circle cx="12" cy="26" r="3" fill="{c}" style="animation:flow 2s linear infinite"/>')
    return ""

def wetlab(cfg, t, mode):
    w, h = W, 250
    cols = ["lime", "pink", "blue"]
    cw = (w - 56) / 3
    items = []
    for i, it in enumerate(cfg["wetlab"]):
        x = 28 + i * cw; c = t[cols[i]]
        items.append(f'''<g transform="translate({x} 96)">
<g transform="translate(4 0)">{wet_icon(it["icon"], c, t)}</g>
<text x="70" y="22" class="sans b" font-size="16" fill="{t["ink"]}">{esc(it["title"])}</text>
{"".join(f'<text x="70" y="{46+j*19}" class="sans" font-size="13" fill="{t["mute"]}">{esc(l)}</text>' for j, l in enumerate(it["lines"]))}
</g>''')
    body = f'''{panel(w, h, t)}
<text x="28" y="58" class="serif" font-size="30" fill="{t["ink"]}">wet lab</text>
<text x="170" y="57" class="sans" font-size="14" fill="{t["mute"]}">the bench work behind the code. no repo, just gloves.</text>
<line x1="28" y1="76" x2="{w-28}" y2="76" stroke="{t["line"]}"/>
{"".join(items)}'''
    css = ("@keyframes breath{0%,100%{transform:scale(.8)}50%{transform:scale(1.15)}}"
           "@keyframes draw{0%{stroke-dashoffset:80}60%,100%{stroke-dashoffset:0}}"
           "@keyframes flow{0%{transform:translate(0,0)}40%{transform:translate(30px,0)}70%{transform:translate(30px,25px)}100%{transform:translate(30px,25px);opacity:0}}")
    return svg(w, h, body, css, ("serif-italic", "grotesk", "grotesk-bold"))

# ───────────────────────────── PETRI DISH ─────────────────────────────
def phase(total):
    if total < 50: return "lag phase", "adapting to the medium. exponential growth loading…"
    if total < 300: return "exponential phase", "growth rate near its peak. do not open the incubator."
    if total < 900: return "stationary phase", "dense, happy, shipping."
    return "time to subculture", "this plate is full. new plate, who dis."

def ago(iso):
    try:
        d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return ""
    s = (dt.datetime.now(dt.timezone.utc) - d).total_seconds()
    days = int(s // 86400)
    return "today" if days == 0 else "yesterday" if days == 1 else f"{days}d ago"

def microbe_mark(shape, x, y, c, s=1.0):
    if shape == "chain":
        return "".join(f'<circle cx="{x-4*s+i*4*s:.1f}" cy="{y+(i%2)*1.5*s:.1f}" r="{1.6*s:.1f}" fill="{c}"/>' for i in range(3))
    if shape == "rod":
        return f'<rect x="{x-5*s:.1f}" y="{y-1.6*s:.1f}" width="{10*s:.1f}" height="{3.2*s:.1f}" rx="{1.6*s:.1f}" fill="{c}" transform="rotate(-25 {x} {y})"/>'
    if shape == "short":
        return "".join(f'<rect x="{x-6*s+i*6*s:.1f}" y="{y-1.5*s:.1f}" width="{4.5*s:.1f}" height="3" rx="1.5" fill="{c}"/>' for i in range(2))
    if shape == "bud":
        return f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{3.4*s:.1f}" ry="{2.8*s:.1f}" fill="{c}"/><circle cx="{x+3.6*s:.1f}" cy="{y-2.4*s:.1f}" r="{1.6*s:.1f}" fill="{c}"/>'
    return ""

def dish(cfg, state, dishd, t, mode):
    w, h = W, 520
    cx, cy, R = 250, 260, 205
    today = dt.date.today()
    placed, cols = [], []

    def place(seed, rad, tries=60):
        rr = rng(seed)
        best = None
        for _ in range(tries):
            a = rr.uniform(0, 2 * math.pi); d = math.sqrt(rr.uniform(0, 1)) * (R - 22 - rad)
            x, y = cx + d * math.cos(a), cy + d * math.sin(a)
            gap = min((math.hypot(x - px, y - py) - rad - pr for px, py, pr in placed), default=99)
            if gap > 3: placed.append((x, y, rad)); return x, y
            if best is None or gap > best[0]: best = (gap, x, y)
        placed.append((best[1], best[2], rad)); return best[1], best[2]

    # own colonies — one per active day, size ∝ √contributions, growth ∝ logistic(age)
    days = sorted(state.get("days", {}).items())
    own = []
    for ds, n in days:
        if n <= 0: continue
        age = (today - dt.date.fromisoformat(ds)).days
        grow = 0.45 + 0.55 / (1 + math.exp(-(age - 3) / 2.5))
        rad = (6 + 3.1 * math.sqrt(n)) * grow
        x, y = place("own" + ds, rad)
        own.append((x, y, rad, ds, n))
    newest = days[-1][0] if days else None

    cl = []
    for i, (x, y, rad, ds, n) in enumerate(own):
        rr = rng("lobes" + ds)
        lobes = "".join(
            f'<circle cx="{x+math.cos(a)*rad*0.78:.1f}" cy="{y+math.sin(a)*rad*0.78:.1f}" r="{rad*rr.uniform(.28,.42):.1f}" fill="url(#own)"/>'
            for a in [k * 2 * math.pi / 7 + rr.uniform(-.3, .3) for k in range(7)])
        fresh = ds == newest
        grad = "old" if (today - dt.date.fromisoformat(ds)).days > 90 else "own"
        lobes = lobes.replace("url(#own)", f"url(#{grad})")
        cl.append(f'''<g style="animation:breath {rng(ds).uniform(3.5,6):.1f}s ease-in-out {-i*0.7:.1f}s infinite;transform-box:fill-box;transform-origin:center">
{lobes}<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad:.1f}" fill="url(#{grad})"/>
<circle cx="{x-rad*.25:.1f}" cy="{y-rad*.3:.1f}" r="{rad*.32:.1f}" fill="#fff" opacity=".22"/>
</g>''' + (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad+6:.1f}" stroke="{t["pink"]}" stroke-width="1.4" style="animation:ping 2.4s ease-out infinite;transform-box:fill-box;transform-origin:center"/>' if fresh else ""))

    # visitor colonies
    mic = cfg["microbes"]; vis = dishd.get("visitors", [])[-cfg.get("max_visitor_colonies", 12):]
    for i, v in enumerate(vis):
        m = mic.get(v["microbe"]);
        if not m: continue
        c = t[m["color"]]
        try:
            age_h = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(v["at"].replace("Z", "+00:00"))).total_seconds() / 3600
        except Exception:
            age_h = 48
        rad = 7.5 + 7 / (1 + math.exp(-(age_h - 12) / 8))
        x, y = place("v" + v["user"], rad)
        marks = "".join(microbe_mark(m["shape"], x + math.cos(a) * rad * .45, y + math.sin(a) * rad * .45, t["panel"], .7)
                        for a in (0.3, 2.4, 4.4))
        cl.append(f'''<g style="animation:breath {rng(v["user"]).uniform(3,5):.1f}s ease-in-out {-i*0.5:.1f}s infinite;transform-box:fill-box;transform-origin:center">
<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad+2.5:.1f}" fill="{c}" opacity=".25"/>
<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad:.1f}" fill="{c}" opacity=".9"/>{marks}</g>''')


    total = state.get("total", sum(n for _, n in days))
    ph, quip = phase(total)
    # growth curve (logistic) with a dot where she is
    gx, gy, gw, gh = 500, 300, 300, 64
    pts = []
    for k in range(61):
        u = k / 60; yv = 1 / (1 + math.exp(-(u - 0.5) * 11))
        pts.append(f"{gx+u*gw:.1f},{gy+gh-yv*gh:.1f}")
    pos = min(0.97, max(0.05, math.log10(total + 1) / math.log10(1500)))
    py_ = gy + gh - gh / (1 + math.exp(-(pos - 0.5) * 11))
    marks = "".join(
        f'<text x="{gx+gw*u}" y="{gy+gh+18}" text-anchor="middle" class="mono" font-size="9.5" fill="{t["faint"]}">{lab}</text>'
        for u, lab in [(0.12, "lag"), (0.5, "exponential"), (0.88, "stationary")])

    log = []
    for j, v in enumerate(list(reversed(vis))[:5]):
        m = mic.get(v["microbe"], {}); c = t[m.get("color", "ink")]
        log.append(f'<circle cx="506" cy="{412+j*0}" r="0"/>')
    from collections import Counter
    tally = Counter(v["microbe"] for v in vis if v["microbe"] in mic)
    rows = "".join(
        f'<circle cx="506" cy="{450+j*18}" r="4" fill="{t[mic[k]["color"]]}"/>'
        f'<text x="518" y="{454+j*18}" class="mono" font-size="11" fill="{t["ink"]}">{esc(mic[k]["name"])}</text>'
        f'<text x="680" y="{454+j*18}" class="mono" font-size="11" fill="{t["mute"]}">× {c_}</text>'
        for j, (k, c_) in enumerate(tally.most_common(3)))
    if not vis:
        rows = (f'<text x="500" y="456" class="sans" font-size="13" fill="{t["mute"]}">no visitors yet. the plate is all yours:</text>'
                f'<text x="500" y="476" class="sans b" font-size="13" fill="{t["pink"]}">be the first to inoculate ↓</text>')
    body = f'''<defs>
{clip_panel(w, h)}
<radialGradient id="agar" cx=".42" cy=".38" r=".7"><stop offset="0" stop-color="{t["agar1"]}"/><stop offset="1" stop-color="{t["agar2"]}"/></radialGradient>
<radialGradient id="own" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="{t["orange"]}" stop-opacity=".95"/><stop offset="1" stop-color="{t["pink"]}" stop-opacity=".75"/></radialGradient>
<radialGradient id="old" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="{t["pink"]}" stop-opacity=".8"/><stop offset="1" stop-color="{t["violet"]}" stop-opacity=".6"/></radialGradient>
<linearGradient id="glass" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".35"/><stop offset=".3" stop-color="#fff" stop-opacity="0"/></linearGradient>
<clipPath id="plate"><circle cx="{cx}" cy="{cy}" r="{R-8}"/></clipPath>
<filter id="blur8"><feGaussianBlur stdDeviation="14"/></filter>
</defs>
{panel(w, h, t)}
<g clip-path="url(#pc)"><circle cx="{cx}" cy="{cy}" r="240" fill="{t["orange"]}" opacity=".10" filter="url(#blur8)"/>{mandala(W-30, h-30, 110, t["pink"], .10, 100)}</g>
<ellipse cx="{cx+8}" cy="{cy+R+6}" rx="{R-10}" ry="12" fill="{t["shadow"]}" opacity=".35"/>
<g transform="translate({cx} {cy})"><g style="animation:spin 120s linear infinite">
{"".join(f'<g transform="rotate({k*15})"><circle cx="0" cy="{-R-16}" r="{3 if k%2 else 2}" fill="{t["orange"] if k%2 else t["pink"]}"/>' + (f'<ellipse cx="0" cy="{-R-16}" rx="4" ry="8" stroke="{t["blue"]}" stroke-width="1.2" opacity=".7"/>' if k%4==0 else "") + '</g>' for k in range(24))}
</g></g>
<circle cx="{cx}" cy="{cy}" r="{R}" fill="{t["panel2"]}" stroke="{t["glass"]}" stroke-opacity=".35" stroke-width="2"/>
<circle cx="{cx}" cy="{cy}" r="{R-8}" fill="url(#agar)"/>
<g clip-path="url(#plate)">{"".join(cl)}</g>
<circle cx="{cx}" cy="{cy}" r="{R-8}" stroke="{t["glass"]}" stroke-opacity=".18"/>
<g style="animation:spin 30s linear infinite;transform-origin:{cx}px {cy}px">
  <path d="M{cx-R+18},{cy-30} A{R-18},{R-18} 0 0 1 {cx-30},{cy-R+18}" stroke="#fff" stroke-opacity=".45" stroke-width="5" stroke-linecap="round"/>
</g>
<text x="{cx}" y="{cy+R-24}" text-anchor="middle" class="mono" font-size="10" fill="{t["ink"]}" opacity=".55">{esc(cfg["user"].upper())} · LB AGAR · 37°C</text>

<text x="500" y="70" class="mono" font-size="12" fill="{t["mute"]}">plate no. {today:%j} · {today:%d %b %Y}</text>
<text x="498" y="112" class="serif" font-size="40" data-max="310" fill="{t["ink"]}">the living culture</text>
<text x="500" y="146" class="sans" font-size="14" fill="{t["mute"]}">every day I push code, a colony grows here.</text>
<text x="500" y="166" class="sans" font-size="14" fill="{t["mute"]}">visitors can drop in a microbe of their own.</text>
<text x="500" y="222" class="serif" font-size="46" fill="{t["pink"]}">{total}</text>
<text x="500" y="244" class="sans" font-size="12" fill="{t["mute"]}">contributions</text>
<text x="620" y="222" class="serif" font-size="46" fill="{t["lime"]}">{len(own)}</text>
<text x="620" y="244" class="sans" font-size="12" fill="{t["mute"]}">colonies</text>
<text x="716" y="222" class="serif" font-size="46" fill="{t["blue"]}">{len(vis)}</text>
<text x="716" y="244" class="sans" font-size="12" fill="{t["mute"]}">visitors</text>
<polyline points="{" ".join(pts)}" stroke="{t["faint"]}" stroke-width="1.5"/>
<circle cx="{gx+pos*gw:.1f}" cy="{py_:.1f}" r="6" fill="{t["pink"]}"/>
<circle cx="{gx+pos*gw:.1f}" cy="{py_:.1f}" r="6" stroke="{t["pink"]}" style="animation:ping 2s ease-out infinite;transform-box:fill-box;transform-origin:center"/>
<text x="{gx+pos*gw+12:.1f}" y="{py_+4:.1f}" class="sans b" font-size="12" fill="{t["ink"]}">{esc(ph)}</text>
{marks}
<text x="500" y="{gy-16}" class="mono" font-size="10.5" fill="{t["mute"]}">{esc(quip)}</text>
<line x1="500" y1="402" x2="{w-30}" y2="402" stroke="{t["line"]}"/>
<text x="500" y="428" class="mono" font-size="11" fill="{t["mute"]}">on the plate</text>
{rows}'''
    css = (SPIN_CSS + "@keyframes breath{0%,100%{transform:scale(.96)}50%{transform:scale(1.04)}}"
           "@keyframes ping{0%{transform:scale(.9);opacity:.9}100%{transform:scale(1.8);opacity:0}}"
           "@keyframes spin{to{transform:rotate(360deg)}}")
    return svg(w, h, body, css, ("serif-italic", "grotesk", "grotesk-bold", "mono"))

# ───────────────────────────── INOCULATE BUTTONS ─────────────────────────────
def button(key, m, t, mode):
    w, h = 160, 74
    c = t[m["color"]]
    marks = "".join(microbe_mark(m["shape"], 30 + dx, 37 + dy, c, 1.25) for dx, dy in [(-6, -7), (6, 1), (-3, 10)])
    body = f'''<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="37" fill="{t["panel"]}"/>
<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="37" fill="{c}" fill-opacity=".12" stroke="{c}" stroke-opacity=".22"/>
<circle cx="30" cy="37" r="20" fill="{c}" fill-opacity=".12"/>
<g style="animation:jig 1.8s ease-in-out infinite;transform-box:fill-box;transform-origin:center">{marks}</g>
<text x="58" y="34" class="sans b" font-size="14" fill="{t["ink"]}">{esc(m["name"])}</text>
<text x="58" y="52" class="mono" font-size="10.5" fill="{c}">+ inoculate</text>'''
    css = "@keyframes jig{0%,100%{transform:rotate(-8deg) translateX(-1px)}50%{transform:rotate(8deg) translateX(1px)}}"
    return svg(w, h, body, css, ("grotesk-bold", "mono"))

def koi_button(kind, t, mode):
    w, h = 160, 74
    PASTEL = {"kohaku": "#fdecec", "marigold": "#fff1e2", "rani": "#fde6ef", "sumi": "#ecebf3", "peacock": "#e0f4f0"}
    ACC = {"kohaku": "red", "marigold": "orange", "rani": "pink", "sumi": "violet", "peacock": "blue"}
    ring = t[ACC[kind]]
    fill = PASTEL[kind] if t is THEMES["light"] else t["panel"]
    body = f'''<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="37" fill="{fill}" stroke="{ring}" stroke-opacity=".22"/>
<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="37" fill="{ring}" fill-opacity="{0 if t is THEMES["light"] else .10}"/>
<circle cx="32" cy="37" r="22" fill="#ffffff" fill-opacity=".7"/>
<g transform="translate(34 37) rotate(-20)">{koi_fish(kind, t, "btn" + kind, .62)}</g>
<text x="62" y="34" class="sans b" font-size="14" fill="{t["ink"]}">{KOI[kind][2]}</text>
<text x="62" y="52" class="mono" font-size="10.5" fill="{ring}">+ release koi</text>'''
    return svg(w, h, body)

# ───────────────────────────── BREWING ─────────────────────────────
def brewing(cfg, state, t, mode):
    w, h = W, 120
    rp = state.get("latest_repo") or {}
    bb, bcss = bubbles(rng("brew"), 8, 46, 82, 92, 30, t, color=t["lime"], rmin=1.5, rmax=4, dur=(1.6, 3), cls="riseB", op=0.9)
    body = f'''{panel(w, h, t)}
<path d="M40 28 L40 86 Q40 96 50 96 L78 96 Q88 96 88 86 L88 28" stroke="{t["ink"]}" stroke-width="2"/>
<line x1="34" y1="28" x2="94" y2="28" stroke="{t["ink"]}" stroke-width="2"/>
<rect x="42" y="58" width="44" height="36" rx="6" fill="{t["lime"]}" opacity=".85"/>
{bb}
<text x="124" y="44" class="mono" font-size="12" fill="{t["mute"]}">currently brewing</text>
<text x="122" y="82" class="serif" font-size="36" data-max="300" fill="{t["ink"]}">{esc(rp.get("name","something new"))}</text>
<text x="{134 + measure(rp.get("name","something new"), "serif-italic", 36):.0f}" y="80" class="mono" font-size="12" fill="{t["mute"]}">{esc(rp.get("language") or "")}{" · pushed " + ago(rp["pushed_at"]) if rp.get("pushed_at") else ""}</text>
<line x1="520" y1="28" x2="520" y2="{h-28}" stroke="{t["line"]}"/>
<text x="546" y="44" class="mono" font-size="12" fill="{t["mute"]}">off the screen</text>
{"".join(f'<text x="546" y="{72+i*20}" class="sans" font-size="14.5" fill="{t["ink"]}">{esc(l)}</text>' for i, l in enumerate(wrap(cfg["now"], 250, "sans", 14.5)[:2]))}'''
    return svg(w, h, body, bcss, ("serif-italic", "grotesk", "mono"))

# ───────────────────────────── ART SHELF (optional) ─────────────────────────────
def shelf(cfg, t, mode):
    imgs = sorted(p for p in ART.glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))[:4]
    if not imgs: return None
    try:
        from PIL import Image
    except ImportError:
        print("Pillow missing: skipping art shelf"); return None
    import io
    caps = {}
    if (ART / "captions.json").exists(): caps = json.loads((ART / "captions.json").read_text())
    w, h = W, 360; n = len(imgs); fw = (w - 56 - (n - 1) * 16) / n; fh = 230
    frames = []
    for i, p in enumerate(imgs):
        im = Image.open(p).convert("RGB"); im.thumbnail((700, 700))
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=82)
        b64 = base64.b64encode(buf.getvalue()).decode()
        x = 28 + i * (fw + 16); tilt = [-1.5, 1.2, -0.8, 1.6][i]
        cap = caps.get(p.name, p.stem.replace("-", " ").replace("_", " "))
        frames.append(f'''<g transform="rotate({tilt} {x+fw/2} 200)" style="animation:hang 5s ease-in-out {i*0.6}s infinite alternate;transform-box:fill-box;transform-origin:top center">
<line x1="{x+fw/2}" y1="74" x2="{x+fw/2}" y2="90" stroke="{t["faint"]}"/>
<rect x="{x-6}" y="90" width="{fw+12}" height="{fh+40}" rx="4" fill="{t["panel2"]}" stroke="{t["line"]}"/>
<image href="data:image/jpeg;base64,{b64}" x="{x}" y="96" width="{fw}" height="{fh}" preserveAspectRatio="xMidYMid slice"/>
<text x="{x+fw/2}" y="{96+fh+24}" text-anchor="middle" class="sans" font-size="12" fill="{t["mute"]}">{esc(cap)}</text></g>''')
    body = f'''{panel(w, h, t)}
<text x="28" y="58" class="serif" font-size="34" fill="{t["ink"]}">design shelf</text>
<line x1="20" y1="74" x2="{w-20}" y2="74" stroke="{t["ink"]}" stroke-opacity=".5" stroke-width="2"/>
{"".join(frames)}'''
    return svg(w, h, body, "@keyframes hang{from{transform:rotate(-.8deg)}to{transform:rotate(.8deg)}}", ("serif-italic", "grotesk"))

# ───────────────────────────── FOOTER ─────────────────────────────
def footer(cfg, t, mode):
    w, h = W, 150
    bb, bcss = bubbles(rng("foot"), 22, 20, 820, 170, 0, t, color=t["pink"], rmin=1.5, rmax=5, dur=(5, 10), cls="riseZ", op=0.5)
    body = f'''<defs>{clip_panel(w, h)}</defs>{panel(w, h, t)}<g clip-path="url(#pc)">{bb}</g>
<text x="{w/2}" y="70" text-anchor="middle" class="serif" font-size="30" data-max="700" fill="{t["ink"]}">thanks for visiting the lab</text>
<text x="{w/2}" y="100" text-anchor="middle" class="sans" font-size="14" fill="{t["mute"]}">come back tomorrow. the culture will have grown.</text>
<text x="{w/2}" y="128" text-anchor="middle" class="mono" font-size="11" fill="{t["faint"]}">© {dt.date.today().year} {esc(cfg["name"].lower())} · made with fizz · no bacteria were harmed</text>'''
    return svg(w, h, body, bcss, ("serif-italic", "grotesk", "mono"))

# ───────────────────────────── README ─────────────────────────────
def ver(path):
    """Content hash, so every changed image gets a fresh address and no cache can show an old one."""
    p = ASSETS / path
    return hashlib.sha1(p.read_bytes()).hexdigest()[:8] if p.exists() else "0"

def pic(name, alt, width="100%"):
    lt, dk = f"{name}-light.svg", f"{name}-dark.svg"
    return (f'<picture><source media="(prefers-color-scheme: light)" srcset="assets/{lt}?v={ver(lt)}">'
            f'<img src="assets/{dk}?v={ver(dk)}" alt="{esc(alt)}" width="{width}"></picture>')

def readme(cfg, has_shelf):
    repo = cfg["repo"]
    def issue(key, m):
        title = f"🧫 inoculate: {key}"
        body = (f"Inoculating the plate with {m['full']}.\n\nJust press **Create**. "
                "A lab robot grows your colony and closes this issue in about a minute.")
        from urllib.parse import quote
        return f"https://github.com/{repo}/issues/new?title={quote(title)}&body={quote(body)}"
    cards = cfg["projects"]
    card_rows = "\n".join(
        '<p align="center">\n' + "\n".join(
            f'<a href="{esc(p["url"])}">{pic("card-" + p["id"], p["title"] + ": " + p["blurb"], "49%")}</a>' for p in cards[i:i+2])
        + "\n</p>" for i in range(0, len(cards), 2))
    def release(kind):
        from urllib.parse import quote
        title = f"🎏 release: {kind}"
        body = f"Releasing a {kind} koi into the pond.\n\nJust press **Create**. It starts swimming with your name in about a minute."
        return f"https://github.com/{repo}/issues/new?title={quote(title)}&body={quote(body)}"
    from urllib.parse import quote as _q
    feed_url = f"https://github.com/{repo}/issues/new?title={_q('🍙 feed the koi')}&body={_q('Scattering pellets. Just press **Create**.')}"
    koi_buttons = "\n".join(f'<a href="{release(k)}">{pic("koi-" + k, "release a " + k + " koi", "19%")}</a>' for k in KOI)
    div = f'<p align="center">{pic("divider", "")}</p>'
    buttons = "\n".join(
        f'<a href="{issue(k, m)}">{pic("btn-" + k, "inoculate " + m["name"], "19%")}</a>' for k, m in cfg["microbes"].items())
    links = cfg.get("links", {})
    labels = {"website": "website", "linkedin": "linkedin", "email": "email", "instagram": "instagram", "behance": "behance"}
    link_line = " &nbsp;·&nbsp; ".join(
        f'<a href="{("mailto:" + v) if k == "email" else v}">{labels[k]}</a>' for k, v in links.items() if v)
    return f'''<!--
  hi, source reader. you found the secret bench.
  everything below is drawn by scripts/lab.py and regrown daily by a github action.
  the pond and the petri dish are real: open an issue titled "🎏 release: rani" and watch.
-->

<p align="center">
{pic("hero", cfg["name"] + ": " + ", ".join(cfg["roles"]))}
</p>

<h3 align="center">🎏 release a koi into my pond</h3>
<p align="center"><sub>pick a koi → press <b>Create</b> on the issue that opens → it swims in the pond above, with your name, in about a minute</sub></p>
<p align="center">
{koi_buttons}
</p>
<p align="center"><a href="{feed_url}"><b>🍙 or feed the koi</b></a> &nbsp;·&nbsp; <sub>the pond follows delhi's clock and weather, and dresses up for festivals</sub></p>

{div}

<p align="center">
{pic("readouts", "lab readouts")}
</p>

<p align="center">
{pic("brewing", "currently brewing")}
</p>

<p align="center">
{pic("periodic", "periodic table of my skills")}
</p>

{div}

{card_rows}

<p align="center">
{pic("wetlab", "wet lab projects")}
</p>

<p align="center">
<a href="#the-living-culture">{pic("dish", "a live petri dish: one colony per day of commits, plus visitor colonies")}</a>
</p>

<h3 align="center" id="the-living-culture">🧫 or drop a microbe into my petri dish</h3>
<p align="center"><sub>pick one → press <b>Create</b> on the issue that opens → your colony appears on the plate in about a minute</sub></p>

<p align="center">
{buttons}
</p>
{f"""
<p align="center">
{pic("shelf", "design shelf: some of my posters and art")}
</p>
""" if has_shelf else ""}
<details>
<summary><b>🧪 do not open the lab fridge</b></summary>
<br>

| shelf | contents | status |
|---|---|---|
| top | 3 agar plates, labelled in handwriting nobody can read | ⚠️ |
| middle | a forgotten *S. mutans* culture | do not lick |
| bottom | my sleep schedule | expired, final year |
| door | one (1) can of fizzy drink | the only thing keeping this lab running |

</details>

<p align="center">
{pic("footer", "thanks for visiting the lab")}
</p>
{f'<p align="center"><sub>{link_line}</sub></p>' if link_line else ""}
'''

# ───────────────────────────── build / grow / inoculate ─────────────────────────────
def load(name):
    return json.loads((LAB / name).read_text())

def all_projects(cfg, state):
    """Curated cards from config, then a card for every other public repo (newest first)."""
    projects = list(cfg["projects"])
    have = {p.get("repo", "").lower() for p in projects}
    hide = {h.lower() for h in cfg.get("hide_repos", [])}
    colors = ["blue", "pink", "lime", "orange", "violet", "yellow"]
    n = len(projects)
    for r in state.get("repos", []):
        nm = r["name"]
        if r.get("fork") or nm.lower() in have or nm.lower() in hide:
            continue
        n += 1
        lang = r.get("language")
        tags = ([lang] if lang else []) + [t for t in (r.get("topics") or []) if t][:2]
        projects.append({
            "id": "repo-" + re.sub(r"[^a-z0-9]+", "-", nm.lower()).strip("-"), "no": f"{n:02d}",
            "title": re.sub(r"[-_]+", " ", nm).strip(), "kind": "repo · " + (lang or "code").lower(),
            "blurb": r.get("description") or "A new experiment, fresh out of the incubator.",
            "tags": tags or ["new"], "cta": "open the app" if r.get("homepage") else "view repo",
            "url": r.get("homepage") or r["html_url"], "color": colors[n % len(colors)], "motif": "initial"})
        if n >= cfg.get("max_cards", 12): break
    return projects

def build():
    cfg, state, dishd = load("config.json"), load("state.json"), load("dish.json")
    cfg["projects"] = all_projects(cfg, state)
    ASSETS.mkdir(exist_ok=True)
    has_shelf = False
    for mode, t in THEMES.items():
        out = {"hero": hero(cfg, t, mode, dishd, state), "divider": divider(cfg, t, mode), "readouts": readouts(cfg, t, mode), "periodic": periodic(cfg, t, mode),
               "wetlab": wetlab(cfg, t, mode), "dish": dish(cfg, state, dishd, t, mode),
               "brewing": brewing(cfg, state, t, mode), "footer": footer(cfg, t, mode)}
        for p in cfg["projects"]: out["card-" + p["id"]] = card(p, t, mode)
        for k, m in cfg["microbes"].items(): out["btn-" + k] = button(k, m, t, mode)
        for k in KOI: out["koi-" + k] = koi_button(k, t, mode)
        s = shelf(cfg, t, mode)
        if s: out["shelf"] = s; has_shelf = True
        for k, v in out.items(): (ASSETS / f"{k}-{mode}.svg").write_text(v)
    (ROOT / "README.md").write_text(readme(cfg, has_shelf))
    print("built", len(list(ASSETS.glob("*.svg"))), "svgs")

def gh(url, data=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None,
                                 headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}",
                                          "Accept": "application/vnd.github+json", "User-Agent": "fizzyappy-lab"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def fetch_repos(user, state):
    repos = gh(f"https://api.github.com/users/{user}/repos?sort=pushed&per_page=100")
    state["repos"] = [{"name": r["name"], "description": r["description"], "language": r["language"],
                       "homepage": r["homepage"], "html_url": r["html_url"], "pushed_at": r["pushed_at"],
                       "fork": r["fork"], "topics": r.get("topics", [])} for r in repos]
    return repos

def grow():
    cfg = load("config.json"); state = load("state.json"); user = cfg["user"]
    if os.environ.get("SKY_ONLY"):        # hourly run: time of day, weather, and new repos
        state["sky"] = fetch_sky()
        try: fetch_repos(user, state)
        except Exception as e: print("repos skipped:", e)
        (LAB / "state.json").write_text(json.dumps(state, indent=2)); return build()
    q = {"query": "query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}",
         "variables": {"u": user}}
    cal = gh("https://api.github.com/graphql", q)["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    state["total"] = cal["totalContributions"]
    state["days"] = {d["date"]: d["contributionCount"] for wk in cal["weeks"] for d in wk["contributionDays"] if d["contributionCount"]}
    repos = fetch_repos(user, state)
    for r in repos:
        if r["name"].lower() != user.lower() and not r["fork"]:
            state["latest_repo"] = {"name": r["name"], "language": r["language"], "pushed_at": r["pushed_at"], "url": r["html_url"]}
            break
    state["sky"] = fetch_sky()
    state["updated"] = dt.date.today().isoformat()
    (LAB / "state.json").write_text(json.dumps(state, indent=2))
    build()

def inoculate():
    """Handles both visitor actions: '🧫 inoculate: <microbe>' and '🎏 release: <koi>'."""
    cfg = load("config.json"); dishd = load("dish.json"); dishd.setdefault("koi", [])
    title = os.environ.get("ISSUE_TITLE", ""); user = os.environ.get("ISSUE_USER", "")
    msg_out = os.environ.get("GITHUB_OUTPUT")
    def reply(msg):
        print(msg)
        if msg_out:
            with open(msg_out, "a") as f: f.write("reply<<EOF\n" + msg + "\nEOF\n")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", user):
        return reply("Hmm, I couldn't read your username. Nothing changed.")
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    low = title.lower()
    if "feed the koi" in low:
        today = ist_now().date().isoformat()
        dishd["feeds"] = [f for f in dishd.get("feeds", []) if f.get("day") == today] + [{"user": user, "day": today}]
        (LAB / "dish.json").write_text(json.dumps(dishd, indent=2)); build()
        n = len(dishd["feeds"])
        return reply(f"🍙 Pellets in! The koi are crowding around the food. They've been fed {n}× today.\n\n"
                     f"Refresh https://github.com/{cfg['user']} in a minute to watch them gather.")
    m = re.search(r"release:\s*(.+)", title, re.I)
    if m:
        words = re.findall(r"[A-Za-z0-9][A-Za-z0-9 _.'-]*", m.group(1))
        raw = " ".join(words).strip()
        parts = raw.split()
        kind = parts[0].lower() if parts and parts[0].lower() in KOI else None
        name = " ".join(parts[1:] if kind else parts)[:16].strip()
        if not kind:   # any name works: colour chosen from the name
            kinds = list(KOI); kind = kinds[int(hashlib.sha256((name or user).lower().encode()).hexdigest(), 16) % len(kinds)]
        keep = cfg.get("max_visitor_koi", 10) - 1   # pond full? the oldest visitor koi swims away
        dishd["koi"] = [v for v in dishd["koi"] if v["user"].lower() != user.lower()][-keep:] + [{"user": user, "koi": kind, "name": name, "at": now}]
        (LAB / "dish.json").write_text(json.dumps(dishd, indent=2)); build()
        who = f"**{name}**, your {kind} koi," if name else f"Your {kind} koi"
        return reply(f"🎏 {who} is in the pond now, swimming with your name on it.\n\n"
                     f"Refresh https://github.com/{cfg['user']} in a minute to see it. Thank you for visiting ✨")
    m = re.search(r"inoculate:\s*([a-z]+)", low)
    key = m.group(1) if m else ""
    if key not in cfg["microbes"]:
        return reply("That microbe isn't in the fridge. Try one of: " + ", ".join(cfg["microbes"]) + ".")
    vis = [v for v in dishd["visitors"] if v["user"].lower() != user.lower()]
    vis.append({"user": user, "microbe": key, "at": now})
    dishd["visitors"] = vis[-cfg.get("max_visitor_colonies", 12):]   # crowded? oldest colonies are removed first
    (LAB / "dish.json").write_text(json.dumps(dishd, indent=2)); build()
    name = cfg["microbes"][key]["full"]
    reply(f"🧫 Inoculated! *{name}* is now growing on the plate as @{user}'s colony.\n\n"
          f"Refresh https://github.com/{cfg['user']} in a minute to see it. Thanks for visiting the lab ✨")

if __name__ == "__main__":
    {"build": build, "grow": grow, "inoculate": inoculate}[sys.argv[1] if len(sys.argv) > 1 else "build"]()
