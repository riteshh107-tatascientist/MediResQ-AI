"""Generate local SVG illustrations (offline-safe). Run: python scripts/make_assets.py
To use real photos instead, drop hero.jpg / feature_inventory.jpg / feature_forecast.jpg / feature_logistics.jpg /
feature_recovery.jpg (or .png/.webp) into assets/images/ - the app prefers photos when present."""
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets" / "images"
OUT.mkdir(parents=True, exist_ok=True)
PAL = ["#38bdf8", "#22d3ee", "#60a5fa", "#a5b4fc", "#34d399", "#fbbf24", "#f8fafc"]
defs = """<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#071a3a"/><stop offset="1" stop-color="#0b3a75"/></linearGradient>
<linearGradient id="glow" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#22d3ee" stop-opacity="0"/><stop offset=".5" stop-color="#22d3ee" stop-opacity=".55"/><stop offset="1" stop-color="#22d3ee" stop-opacity="0"/></linearGradient>
<linearGradient id="shelf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1e4f8f"/><stop offset="1" stop-color="#0d2f5e"/></linearGradient>
<linearGradient id="floor" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0e3a73"/><stop offset="1" stop-color="#061633"/></linearGradient>
<radialGradient id="spot" cx=".5" cy=".4" r=".6"><stop offset="0" stop-color="#38bdf8" stop-opacity=".35"/><stop offset="1" stop-color="#38bdf8" stop-opacity="0"/></radialGradient>
<filter id="blur"><feGaussianBlur stdDeviation="6"/></filter></defs>"""


def svg(w, h, body, title):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="{title}"><title>{title}</title>{defs}<rect width="{w}" height="{h}" fill="url(#bg)"/>{body}</svg>'


def boxes(x, y, w, h, rnd, n):
    s, bw = "", w / n
    for i in range(n):
        bh = rnd.uniform(.45, .9) * h
        c = rnd.choice(PAL)
        s += f'<rect x="{x + i * bw + 2:.1f}" y="{y + h - bh:.1f}" width="{bw - 4:.1f}" height="{bh:.1f}" rx="2" fill="{c}" opacity=".88"/><rect x="{x + i * bw + 2:.1f}" y="{y + h - bh:.1f}" width="{bw - 4:.1f}" height="4" fill="#fff" opacity=".35"/>'
        s += f'<rect x="{x + i * bw + bw / 2 - 4:.1f}" y="{y + h - bh / 2 - 5:.1f}" width="8" height="10" rx="1" fill="#0b3a75" opacity=".55"/>'
    return s


def shelf_unit(x, y, w, h, rnd, rows=4, n=7):
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="url(#shelf)" stroke="#38bdf8" stroke-opacity=".35"/>'
    rh = h / rows
    for r in range(rows):
        s += boxes(x + 6, y + r * rh + 6, w - 12, rh - 12, rnd, n)
        s += f'<rect x="{x}" y="{y + (r + 1) * rh - 4}" width="{w}" height="5" fill="#7dd3fc" opacity=".55"/>'
    return s


def cross(x, y, r, op=1):
    return f'<g opacity="{op}"><rect x="{x - r}" y="{y - r / 3}" width="{2 * r}" height="{2 * r / 3}" rx="{r / 5}" fill="#fff"/><rect x="{x - r / 3}" y="{y - r}" width="{2 * r / 3}" height="{2 * r}" rx="{r / 5}" fill="#fff"/></g>'


def net(pts, edges, color="#22d3ee"):
    s = ""
    for a, b in edges:
        (x1, y1), (x2, y2) = pts[a], pts[b]
        s += f'<path d="M{x1},{y1} Q{(x1 + x2) / 2},{min(y1, y2) - 40} {x2},{y2}" fill="none" stroke="{color}" stroke-width="2" stroke-dasharray="6 6" opacity=".8"/>'
    for x, y in pts:
        s += f'<circle cx="{x}" cy="{y}" r="14" fill="{color}" opacity=".25"/><circle cx="{x}" cy="{y}" r="6" fill="#fff"/><circle cx="{x}" cy="{y}" r="3" fill="{color}"/>'
    return s


def truck(x, y, s=1.0, c="#f8fafc"):
    return (f'<g transform="translate({x},{y}) scale({s})"><rect width="120" height="56" rx="6" fill="{c}"/><rect x="122" y="14" width="44" height="42" rx="6" fill="#38bdf8"/>'
            f'<rect x="132" y="20" width="26" height="16" rx="3" fill="#0b3a75"/>{cross(60, 28, 16)[:0]}<rect x="40" y="14" width="40" height="28" rx="4" fill="#0b6bcb" opacity=".15"/>'
            f'<rect x="52" y="22" width="16" height="4" fill="#0b6bcb"/><rect x="58" y="16" width="4" height="16" fill="#0b6bcb"/><circle cx="28" cy="60" r="10" fill="#0a1f44"/><circle cx="28" cy="60" r="4" fill="#94a3b8"/>'
            f'<circle cx="138" cy="60" r="10" fill="#0a1f44"/><circle cx="138" cy="60" r="4" fill="#94a3b8"/></g>')


def hero():
    r = random.Random(11)
    b = '<rect width="1200" height="560" fill="url(#spot)"/>'
    b += '<rect y="380" width="1200" height="180" fill="url(#floor)"/>'
    for i in range(-6, 14):  # perspective floor lines
        b += f'<line x1="{600 + i * 40}" y1="380" x2="{600 + i * 130}" y2="560" stroke="#38bdf8" stroke-opacity=".16"/>'
    for yy in (410, 450, 505):
        b += f'<line x1="0" y1="{yy}" x2="1200" y2="{yy}" stroke="#38bdf8" stroke-opacity=".14"/>'
    b += '<rect x="60" y="90" width="1080" height="300" rx="10" fill="#0a2a57" opacity=".65" stroke="#38bdf8" stroke-opacity=".3"/>'
    for i in range(5):
        b += shelf_unit(95 + i * 205, 125, 185, 250, r, 4, 6)
    b += '<rect x="60" y="388" width="1080" height="8" fill="#22d3ee" opacity=".5"/>'
    b += f'<rect x="0" y="380" width="1200" height="14" fill="url(#glow)" opacity=".7"/>'
    b += truck(760, 440, 1.5) + truck(380, 470, 1.1, "#bae6fd")
    pts = [(150, 70), (420, 40), (700, 62), (980, 38), (1100, 90)]
    b += net(pts, [(0, 1), (1, 2), (2, 3), (3, 4)])
    b += '<g filter="url(#blur)" opacity=".5"><circle cx="1010" cy="120" r="70" fill="#22d3ee"/></g>' + cross(1010, 120, 42, .95)
    for i in range(14):  # floating capsules
        x, y, a = r.randint(40, 1160), r.randint(20, 360), r.randint(0, 180)
        b += f'<g transform="translate({x},{y}) rotate({a})" opacity=".5"><rect width="26" height="10" rx="5" fill="{r.choice(PAL)}"/><rect width="13" height="10" rx="5" fill="#fff" opacity=".6"/></g>'
    return svg(1200, 560, b, "Modern pharmaceutical warehouse with medicine shelving, delivery trucks and a connected supply-chain network")


def inventory():
    r = random.Random(3)
    b = shelf_unit(40, 50, 300, 260, r, 4, 6)
    for i, (t, c) in enumerate([("EXP 21d", "#fbbf24"), ("EXP 240d", "#34d399"), ("EXPIRED", "#f87171")]):
        y = 60 + i * 78
        b += f'<rect x="370" y="{y}" width="190" height="62" rx="10" fill="#0a2a57" stroke="#38bdf8" stroke-opacity=".4"/><rect x="384" y="{y + 12}" width="80" height="8" rx="4" fill="#7dd3fc" opacity=".7"/><rect x="384" y="{y + 30}" width="120" height="6" rx="3" fill="#7dd3fc" opacity=".35"/><rect x="384" y="{y + 42}" width="70" height="6" rx="3" fill="#7dd3fc" opacity=".35"/><rect x="480" y="{y + 10}" width="68" height="20" rx="10" fill="{c}"/>'
    b += '<circle cx="470" cy="305" r="34" fill="none" stroke="#38bdf8" stroke-opacity=".25" stroke-width="9"/><path d="M436,305 A34,34 0 1 1 495,326" fill="none" stroke="#22d3ee" stroke-width="9" stroke-linecap="round"/>'
    return svg(600, 360, b, "Medicine inventory shelves with batch expiry labels and a stock gauge")


def forecast():
    b = '<rect x="30" y="30" width="540" height="300" rx="14" fill="#0a2a57" stroke="#38bdf8" stroke-opacity=".35"/>'
    for i in range(5):
        b += f'<line x1="50" y1="{70 + i * 55}" x2="550" y2="{70 + i * 55}" stroke="#38bdf8" stroke-opacity=".15"/>'
    hist = "M50,240 L80,215 L110,235 L140,190 L170,205 L200,170 L230,185 L260,150 L290,165"
    b += f'<path d="M290,165 L330,140 L370,150 L410,120 L450,135 L490,105 L540,115 L540,175 L490,170 L450,190 L410,185 L370,205 L330,195 L290,165 Z" fill="#22d3ee" opacity=".22"/>'
    b += f'<path d="{hist}" fill="none" stroke="#f8fafc" stroke-width="3.5" stroke-linejoin="round"/><path d="M290,165 L330,168 L370,178 L410,152 L450,162 L490,138 L540,145" fill="none" stroke="#22d3ee" stroke-width="3.5" stroke-dasharray="9 7"/>'
    b += '<line x1="290" y1="55" x2="290" y2="300" stroke="#fbbf24" stroke-dasharray="4 4"/><rect x="298" y="50" width="70" height="20" rx="10" fill="#fbbf24"/>'
    b += '<rect x="60" y="305" width="60" height="8" rx="4" fill="#7dd3fc" opacity=".5"/><rect x="450" y="42" width="100" height="22" rx="11" fill="#34d399"/>'
    return svg(600, 360, b, "Demand forecast chart with history, forecast line and confidence band")


def logistics():
    r = random.Random(5)
    b = ""
    for i in range(12):
        b += f'<line x1="{i * 55}" y1="0" x2="{i * 55}" y2="360" stroke="#38bdf8" stroke-opacity=".12"/><line x1="0" y1="{i * 34}" x2="600" y2="{i * 34}" stroke="#38bdf8" stroke-opacity=".12"/>'
    pts = [(70, 270), (190, 130), (330, 220), (450, 90), (540, 250)]
    b += net(pts, [(0, 1), (1, 2), (2, 3), (3, 4)])
    b += truck(235, 245, .6) + '<circle cx="450" cy="90" r="30" fill="#f87171" opacity=".3"/><rect x="418" y="40" width="64" height="22" rx="11" fill="#f87171"/><text x="450" y="56" font-size="13" font-weight="700" text-anchor="middle" fill="#fff" font-family="Arial">+7 DAYS</text>'
    b += '<rect x="30" y="30" width="150" height="46" rx="10" fill="#0a2a57" stroke="#38bdf8" stroke-opacity=".4"/><rect x="44" y="44" width="90" height="8" rx="4" fill="#34d399"/><rect x="44" y="58" width="60" height="6" rx="3" fill="#7dd3fc" opacity=".5"/>'
    return svg(600, 360, b, "Logistics network map with shipment route, delivery truck and delay warning")


def recovery():
    b = ""
    nodes = {"W": (110, 180), "A": (480, 80), "B": (480, 180), "C": (480, 280), "S": (110, 70)}
    for k, (x, y) in nodes.items():
        col = {"W": "#22d3ee", "S": "#fbbf24"}.get(k, "#60a5fa")
        b += f'<circle cx="{x}" cy="{y}" r="36" fill="{col}" opacity=".2"/><circle cx="{x}" cy="{y}" r="24" fill="#0a2a57" stroke="{col}" stroke-width="3"/>' + cross(x, y, 11)
    for a, c, lab, col in [("W", "A", "+700", "#34d399"), ("W", "B", "+240", "#34d399"), ("C", "A", "+120", "#34d399")]:
        (x1, y1), (x2, y2) = nodes[a], nodes[c]
        b += f'<path d="M{x1 + 26},{y1} C{(x1 + x2) / 2},{y1} {(x1 + x2) / 2},{y2} {x2 - 26},{y2}" fill="none" stroke="{col}" stroke-width="3" stroke-dasharray="8 6"/><rect x="{(x1 + x2) / 2 - 24}" y="{(y1 + y2) / 2 - 11}" width="48" height="22" rx="11" fill="{col}"/><text x="{(x1 + x2) / 2}" y="{(y1 + y2) / 2 + 5}" font-size="12" font-weight="700" text-anchor="middle" fill="#052e1b" font-family="Arial">{lab}</text>'
    b += '<path d="M110,94 L110,156" stroke="#f87171" stroke-width="3" stroke-dasharray="4 5"/><circle cx="110" cy="125" r="11" fill="#f87171"/><text x="110" y="130" font-size="14" font-weight="700" text-anchor="middle" fill="#fff" font-family="Arial">!</text>'
    b += '<rect x="215" y="300" width="170" height="38" rx="19" fill="#34d399"/><path d="M240,319 l9,9 l17,-18" stroke="#052e1b" stroke-width="4" fill="none" stroke-linecap="round"/><rect x="278" y="313" width="86" height="8" rx="4" fill="#052e1b" opacity=".6"/>'
    return svg(600, 360, b, "Inventory recovery network showing redistribution between warehouse and hospitals with human approval")


for name, fn in [("hero", hero), ("feature_inventory", inventory), ("feature_forecast", forecast), ("feature_logistics", logistics), ("feature_recovery", recovery)]:
    (OUT / f"{name}.svg").write_text(fn(), encoding="utf-8")
    print("wrote", name)
