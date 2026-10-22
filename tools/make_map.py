"""Draws the Freshroots components map as SVG (same grammar as the Case 2 example)."""
import sys
from xml.sax.saxutils import escape

out = sys.argv[1]
W = 1940
COLS = ["Actor", "Trigger", "Input", "Context", "Processing", "AI / Rules", "Output"]
CX = [20, 240, 520, 800, 1080, 1360, 1640, 1920]          # column edges
ROWS = [  # name, sub, lane colour, actor colour
    ("Raghav", "(Demand Planner)", "#eaf2ff"),
    ("SAP ERP", "(IT team export)", "#f1edff"),
    ("System", "(Engine on Vercel)", "#fff8e1"),
    ("Database", "(Neon Postgres)", "#eaf7ee"),
    ("Zoho Inventory", "(Procurement)", "#fdeef3"),
]
TOP, HEAD, RH = 96, 64, 168
RY = [TOP + HEAD + i * RH for i in range(len(ROWS) + 1)]
NAVY = "#14233c"

LANG = sys.argv[2] if len(sys.argv) > 2 else "en"
HI = {
    "Actor": "भूमिका", "Trigger": "ट्रिगर", "Input": "इनपुट", "Context": "संदर्भ", "Processing": "प्रोसेसिंग",
    "AI / Rules": "AI / नियम", "Output": "आउटपुट",
    "Raghav": "राघव", "(Demand Planner)": "(डिमांड प्लानर)", "(IT team export)": "(IT टीम एक्सपोर्ट)",
    "System": "सिस्टम", "(Engine on Vercel)": "(Vercel पर इंजन)", "Database": "डेटाबेस",
    "Zoho Inventory": "Zoho इन्वेंटरी", "(Procurement)": "(खरीद टीम)",
    "Every Monday & Thursday": "हर सोमवार और गुरुवार",
    "IT team exports SKU master, stock snapshot and weekly sales from SAP": "IT टीम SAP से SKU मास्टर, स्टॉक स्नैपशॉट और साप्ताहिक बिक्री एक्सपोर्ट करती है",
    "Uploads the 3 SAP CSVs": "3 SAP CSV फ़ाइलें अपलोड करते हैं",
    "on the New run page (no manual Excel work)": "New run पेज पर (Excel में हाथ से कोई काम नहीं)",
    "Data checks + signed-off rules": "डेटा जाँच + स्वीकृत नियम",
    "Stale or negative data stops the run. Min/max cover, festival months, lead times from config": "पुराना या नेगेटिव डेटा हो तो रन रुक जाता है। न्यूनतम/अधिकतम कवर, त्योहार के महीने, लीड टाइम config से",
    "Forecast & cover per SKU": "हर SKU का पूर्वानुमान और कवर",
    "12-week baseline, festival uplift on future weeks only, order-up-to quantity": "12 हफ़्ते का बेसलाइन, त्योहार की बढ़त सिर्फ़ आगे के हफ़्तों पर, ऑर्डर-अप-टू मात्रा",
    "Flags exceptions (rules, no LLM)": "अपवाद चिह्नित करता है (नियम, LLM नहीं)",
    "Stockout, overstock, high demand, borderline, uplift-sensitive, volatile → Pass / Review / Blocked": "स्टॉकआउट, ओवरस्टॉक, ज़्यादा मांग, सीमा के पास, uplift पर निर्भर, अस्थिर → Pass / Review / Blocked",
    "Saves every run": "हर रन सेव करता है",
    "Recommendations + append-only decision log with reason codes": "सुझाव + कभी न बदलने वाला निर्णय लॉग, कारण कोड के साथ",
    "Review queue: only flagged SKUs": "रिव्यू कतार: सिर्फ़ चिह्नित SKU",
    "8 of 15 this run. Approve or override with a reason code": "इस रन में 15 में से 8। कारण कोड के साथ मंज़ूर करें या बदलें",
    "Monthly review": "मासिक समीक्षा",
    "Forecast error (WAPE), bias, and whether overrides beat the system (FVA)": "पूर्वानुमान त्रुटि (WAPE), झुकाव (bias), और क्या बदलाव सिस्टम से बेहतर रहे (FVA)",
    "Draft purchase orders": "ड्राफ़्ट परचेज़ ऑर्डर",
    "One per supplier, status Draft, imported into Zoho Inventory": "हर सप्लायर के लिए एक, स्टेटस Draft, Zoho इन्वेंटरी में इम्पोर्ट",
    "flagged SKUs only": "सिर्फ़ चिह्नित SKU", "decisions saved": "निर्णय सेव", "approved quantities": "मंज़ूर मात्राएँ",
    "TITLE": "केस 1 · Freshroots डिमांड प्लानिंग — कंपोनेंट्स मैप",
    "F1B": "चरण 2 (अगली तिमाही):",
    "F1": "3 साल के इतिहास से हर SKU की मौसमी चाल सीखना, सांख्यिकीय सेफ़्टी स्टॉक, बड़े डिस्ट्रीब्यूटर ऑर्डर घटाएँ तो रोज़ाना अलर्ट।",
    "F2B": "खरीद टीम से पुष्टि बाकी:",
    "F2": "सप्लायर लीड टाइम (1 हफ़्ता माना गया), रास्ते में मौजूद ऑर्डर, जल्दी खराब होने वाले सामान की शेल्फ़ लाइफ़।",
}
EN = {
    "TITLE": "Case 1 · Freshroots Demand Planning — Components Map",
    "F1B": "Phase 2 (next quarter):",
    "F1": "per-SKU seasonality learned from 3 years of history, statistical safety stock, daily alert when large distributors cut orders.",
    "F2B": "Still to confirm with procurement:",
    "F2": "supplier lead times (1 week assumed), on-order quantities, shelf life for perishables.",
}


def L(text):
    return HI.get(text, text) if LANG == "hi" else EN.get(text, text)

STYLE = {  # fill, stroke
    "purple": ("#e9e5ff", "#5b4bdb"), "blue": ("#e3efff", "#2f6fd6"), "green": ("#e2f6e7", "#2f9e44"),
    "yellow": ("#fff1cc", "#e8a400"), "pink": ("#ffe3ef", "#d6336c"), "orange": ("#ffe8d9", "#e8590c"),
    "teal": ("#dff5f2", "#0c8f80"),
}


def wrap(text, width_chars):
    lines, cur = [], ""
    for word in text.split():
        if len(cur) + len(word) + 1 > width_chars and cur:
            lines.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    lines.append(cur)
    return lines


def box(col, row, title, body, style, h=124, dy=0):
    x = CX[col] + 18
    w = CX[col + 1] - CX[col] - 36
    y = RY[row] + (RH - h) / 2 + dy
    fill, stroke = STYLE[style]
    t_lines = wrap(L(title), 24)
    b_lines = wrap(L(body), 30) if body else []
    n = len(t_lines) + len(b_lines)
    lh_t, lh_b = 20, 17
    total = len(t_lines) * lh_t + len(b_lines) * lh_b
    ty = y + h / 2 - total / 2 + 14
    s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="2"/>']
    for ln in t_lines:
        s.append(f'<text x="{x + w / 2}" y="{ty}" text-anchor="middle" class="bt">{escape(ln)}</text>')
        ty += lh_t
    for ln in b_lines:
        s.append(f'<text x="{x + w / 2}" y="{ty}" text-anchor="middle" class="bb">{escape(ln)}</text>')
        ty += lh_b
    return "\n".join(s), (x, y, w, h)


def arrow(d, label=None, lx=0, ly=0):
    s = f'<path d="{d}" fill="none" stroke="{NAVY}" stroke-width="1.8" stroke-dasharray="6 4" marker-end="url(#ah)"/>'
    if label:
        s += f'<text x="{lx}" y="{ly}" class="al">{escape(L(label))}</text>'
    return s


parts = []
# lanes and grid
for i, (_, _, lane) in enumerate(ROWS):
    parts.append(f'<rect x="{CX[1]}" y="{RY[i]}" width="{CX[-1] - CX[1]}" height="{RH}" fill="{lane}"/>')
for x in CX[2:-1]:
    parts.append(f'<line x1="{x}" y1="{RY[0]}" x2="{x}" y2="{RY[-1]}" stroke="#ffffff" stroke-width="2"/>')
for y in RY[1:-1]:
    parts.append(f'<line x1="{CX[1]}" y1="{y}" x2="{CX[-1]}" y2="{y}" stroke="#ffffff" stroke-width="2"/>')
# header
parts.append(f'<rect x="{CX[0]}" y="{TOP}" width="{CX[-1] - CX[0]}" height="{HEAD}" rx="8" fill="{NAVY}"/>')
for i, c in enumerate(COLS):
    parts.append(f'<text x="{(CX[i] + CX[i + 1]) / 2}" y="{TOP + 40}" text-anchor="middle" class="hd">{escape(L(c))}</text>')
# actor column
parts.append(f'<rect x="{CX[0]}" y="{RY[0]}" width="{CX[1] - CX[0]}" height="{RY[-1] - RY[0]}" fill="{NAVY}"/>')
for i, (name, sub, _) in enumerate(ROWS):
    cy = RY[i] + RH / 2
    parts.append(f'<text x="{(CX[0] + CX[1]) / 2}" y="{cy - 4}" text-anchor="middle" class="an">{escape(L(name))}</text>')
    parts.append(f'<text x="{(CX[0] + CX[1]) / 2}" y="{cy + 20}" text-anchor="middle" class="as">{escape(L(sub))}</text>')
    if i:
        parts.append(f'<line x1="{CX[0]}" y1="{RY[i]}" x2="{CX[1]}" y2="{RY[i]}" stroke="#2a3d5e" stroke-width="2"/>')

b = {}
for key, args in {
    "trigger": (1, 1, "Every Monday & Thursday", "IT team exports SKU master, stock snapshot and weekly sales from SAP", "purple"),
    "input": (2, 0, "Uploads the 3 SAP CSVs", "on the New run page (no manual Excel work)", "blue"),
    "context": (3, 2, "Data checks + signed-off rules", "Stale or negative data stops the run. Min/max cover, festival months, lead times from config", "green"),
    "process": (4, 2, "Forecast & cover per SKU", "12-week baseline, festival uplift on future weeks only, order-up-to quantity", "yellow"),
    "ai": (5, 2, "Flags exceptions (rules, no LLM)", "Stockout, overstock, high demand, borderline, uplift-sensitive, volatile → Pass / Review / Blocked", "pink"),
    "store": (5, 3, "Saves every run", "Recommendations + append-only decision log with reason codes", "teal"),
    "queue": (6, 0, "Review queue: only flagged SKUs", "8 of 15 this run. Approve or override with a reason code", "orange"),
    "review": (6, 3, "Monthly review", "Forecast error (WAPE), bias, and whether overrides beat the system (FVA)", "teal"),
    "zoho": (6, 4, "Draft purchase orders", "One per supplier, status Draft, imported into Zoho Inventory", "blue"),
}.items():
    svg, rect = box(*args)
    parts.append(svg)
    b[key] = rect


def mid_r(r): return r[0] + r[2], r[1] + r[3] / 2
def mid_l(r): return r[0], r[1] + r[3] / 2
def mid_b(r): return r[0] + r[2] / 2, r[1] + r[3]
def mid_t(r): return r[0] + r[2] / 2, r[1]


x1, y1 = mid_r(b["trigger"]); x2, y2 = mid_b(b["input"])
parts.append(arrow(f"M{x1} {y1} H{x2} V{y2 + 4}"))
x1, y1 = mid_r(b["input"]); x2, y2 = mid_l(b["context"])
parts.append(arrow(f"M{x1} {y1} H{CX[3] - 4} V{y2} H{x2 - 4}"))
x1, y1 = mid_r(b["context"]); x2, y2 = mid_l(b["process"])
parts.append(arrow(f"M{x1} {y1} H{x2 - 4}"))
x1, y1 = mid_r(b["process"]); x2, y2 = mid_l(b["ai"])
parts.append(arrow(f"M{x1} {y1} H{x2 - 4}"))
x1, y1 = mid_b(b["ai"]); x2, y2 = mid_t(b["store"])
parts.append(arrow(f"M{x1} {y1} V{y2 - 4}"))
x1, y1 = mid_t(b["ai"]); x2, y2 = mid_l(b["queue"])
parts.append(arrow(f"M{x1} {y1} V{y2} H{x2 - 4}", "flagged SKUs only", x1 + 8, y2 - 8))
x1, y1 = mid_r(b["store"]); x2, y2 = mid_l(b["review"])
parts.append(arrow(f"M{x1} {y1} H{x2 - 4}"))
qx, qy = mid_b(b["queue"])
parts.append(arrow(f"M{qx - 50} {qy} V{RY[3] + 9} H{b['store'][0] + b['store'][2] - 40} V{b['store'][1] - 4}",
                   "decisions saved", qx - 44, RY[3] - 10))
x2, y2 = mid_t(b["zoho"])
parts.append(arrow(f"M{qx + 60} {qy} V{RY[3] + 6} H{CX[-1] - 8} V{y2 - 24} H{x2} V{y2 - 4}",
                   "approved quantities", CX[-1] - 150, y2 - 30))

foot_y = RY[-1] + 40
parts.append(f'<text x="{CX[0]}" y="{foot_y}" class="ft"><tspan class="fb">{L("F1B")}</tspan> {L("F1")}</text>')
parts.append(f'<text x="{CX[0]}" y="{foot_y + 26}" class="ft"><tspan class="fb">{L("F2B")}</tspan> {L("F2")}</text>')

H = foot_y + 50
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<defs>
  <marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse">
    <path d="M0 0 L10 5 L0 10 z" fill="{NAVY}"/></marker>
  <style>
    text {{ font-family: -apple-system, "Segoe UI", "Kohinoor Devanagari", "Noto Sans Devanagari", "Nirmala UI", Roboto, Helvetica, Arial, sans-serif; fill: {NAVY}; }}
    .tt {{ font-size: 34px; font-weight: 700; }}
    .hd {{ font-size: 21px; font-weight: 600; fill: #ffffff; }}
    .an {{ font-size: 21px; font-weight: 700; fill: #ffffff; }}
    .as {{ font-size: 16px; fill: #c9d4e8; }}
    .bt {{ font-size: 17px; font-weight: 650; }}
    .bb {{ font-size: 14.5px; fill: #33425e; }}
    .al {{ font-size: 13px; font-style: italic; fill: #4a5a78; }}
    .ft {{ font-size: 16px; fill: #33425e; }}
    .fb {{ font-weight: 700; fill: {NAVY}; }}
  </style>
</defs>
<rect width="{W}" height="{H}" fill="#ffffff"/>
<g transform="translate(455 16) scale(0.95)">
  <circle cx="32" cy="32" r="31" fill="#fff4ec" stroke="#f3cdb0" stroke-width="2"/>
  <path d="M32 23 C31 18 31.5 13 33.5 8" fill="none" stroke="#2f9e44" stroke-width="3" stroke-linecap="round"/>
  <path d="M31.5 21 C26 20 21 16 19 10 C25 10 30 14 31.5 21 Z" fill="#40c057"/>
  <path d="M33 19 C35 13 40 9 46 8.5 C45 14.5 40 18.5 33 19 Z" fill="#2f9e44"/>
  <path d="M20.5 25 C25 21.5 39 21.5 43.5 25 C43 35 37.5 47 33 56 C32.4 57.2 31.6 57.2 31 56 C26.5 47 21 35 20.5 25 Z" fill="#e8590c"/>
  <path d="M24.5 31 L30 31 M34.5 37 L40 37 M27 43 L31.5 43" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round"/>
</g>
<text x="533" y="64" class="tt">{L("TITLE")}</text>
{chr(10).join(parts)}
</svg>
'''
open(out, "w").write(svg)
print(out, W, H)
