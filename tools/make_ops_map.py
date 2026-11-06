"""Components map for the whole Freshroots case (all three problems), in the Case 2 swimlane format.

    python3 tools/make_ops_map.py docs/components_map_ops.svg
"""
import sys
from xml.sax.saxutils import escape

out = sys.argv[1]
W = 1940
NAVY = "#14233c"
COLS = ["Actor", "Trigger", "Input", "Context", "Processing", "AI / Rules", "Output"]
CX = [20, 240, 520, 800, 1080, 1360, 1640, 1920]
ROWS = [
    ("Deepa", "(Head of Operations)", "#fff1e6"),
    ("Team", "(Raghav · CS reps · owners)", "#eaf2ff"),
    ("SAP + WhatsApp", "(sources)", "#f1edff"),
    ("System", "(engine + alerts, Vercel)", "#fff8e1"),
    ("Database", "(Neon Postgres)", "#eaf7ee"),
    ("Zoho Inventory", "(Procurement)", "#fdeef3"),
]
STRIP_Y, STRIP_H = 104, 150
TOP = STRIP_Y + STRIP_H + 26
HEAD, RH = 60, 150
RY = [TOP + HEAD + i * RH for i in range(len(ROWS) + 1)]
STYLE = {"purple": ("#e9e5ff", "#5b4bdb"), "blue": ("#e3efff", "#2f6fd6"), "green": ("#e2f6e7", "#2f9e44"),
         "yellow": ("#fff1cc", "#e8a400"), "pink": ("#ffe3ef", "#d6336c"), "orange": ("#ffe8d9", "#e8590c"),
         "teal": ("#dff5f2", "#0c8f80"), "red": ("#fde2e2", "#c92a2a")}


def wrap(text, n):
    lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + len(w) + 1 > n:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return lines + [cur]


def lines_svg(x, y, items):
    """items: [(text, cls, line_height)] centred at x starting at baseline y."""
    s = []
    for text, cls, lh in items:
        s.append(f'<text x="{x}" y="{y}" text-anchor="middle" class="{cls}">{escape(text)}</text>')
        y += lh
    return s


def box(col, row, title, body, style, h=112):
    x, w = CX[col] + 18, CX[col + 1] - CX[col] - 36
    y = RY[row] + (RH - h) / 2
    fill, stroke = STYLE[style]
    items = [(t, "bt", 20) for t in wrap(title, 24)] + [(t, "bb", 17) for t in wrap(body, 31)] if body else [(t, "bt", 20) for t in wrap(title, 24)]
    total = sum(lh for _, _, lh in items)
    s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="2"/>']
    s += lines_svg(x + w / 2, y + h / 2 - total / 2 + 14, items)
    return "\n".join(s), (x, y, w, h)


def arrow(d, label=None, lx=0, ly=0, anchor="start"):
    s = f'<path d="{d}" fill="none" stroke="{NAVY}" stroke-width="1.8" stroke-dasharray="6 4" marker-end="url(#ah)"/>'
    if label:
        s += f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" class="al">{escape(label)}</text>'
    return s


parts = []

# ---- problem breakdown strip: three problems, each with cost, bottleneck and fix
PROBLEMS = [
    ("1  Demand planning", "₹28–34L a quarter in stockouts and write-offs",
     "Bottleneck: monthly SAP-to-Excel cycle, data 3–4 weeks old", "Fix: twice-weekly rules engine, review only exceptions"),
    ("2  Distributor service", "₹18–25L a year for every distributor lost",
     "Bottleneck: WhatsApp only, no data, after-hours queries wait", "Fix: query log, 2-hour reply clock, handoff, auto-reply"),
    ("3  Operations intelligence", "₹9L write-off from one late signal",
     "Bottleneck: weekly report, nobody owns a mid-week move", "Fix: one owner per metric, alerts with deadlines, escalation"),
]
sw = (CX[-1] - CX[0] - 2 * 24) / 3
for i, (name, cost, neck, fix) in enumerate(PROBLEMS):
    x = CX[0] + i * (sw + 24)
    parts.append(f'<rect x="{x}" y="{STRIP_Y}" width="{sw}" height="{STRIP_H}" rx="10" fill="#fff8f2" stroke="#f3cdb0" stroke-width="1.5"/>')
    parts.append(f'<rect x="{x}" y="{STRIP_Y}" width="6" height="{STRIP_H}" rx="3" fill="#e8590c"/>')
    parts.append(f'<text x="{x + 22}" y="{STRIP_Y + 32}" class="pn">{escape(name)}</text>')
    parts.append(f'<text x="{x + 22}" y="{STRIP_Y + 60}" class="pc">{escape(cost)}</text>')
    parts.append(f'<text x="{x + 22}" y="{STRIP_Y + 92}" class="pb">{escape(neck)}</text>')
    parts.append(f'<text x="{x + 22}" y="{STRIP_Y + 122}" class="pf">{escape(fix)}</text>')

# ---- swimlanes
for i, (_, _, lane) in enumerate(ROWS):
    parts.append(f'<rect x="{CX[1]}" y="{RY[i]}" width="{CX[-1] - CX[1]}" height="{RH}" fill="{lane}"/>')
for x in CX[2:-1]:
    parts.append(f'<line x1="{x}" y1="{RY[0]}" x2="{x}" y2="{RY[-1]}" stroke="#ffffff" stroke-width="2"/>')
for y in RY[1:-1]:
    parts.append(f'<line x1="{CX[1]}" y1="{y}" x2="{CX[-1]}" y2="{y}" stroke="#ffffff" stroke-width="2"/>')
parts.append(f'<rect x="{CX[0]}" y="{TOP}" width="{CX[-1] - CX[0]}" height="{HEAD}" rx="8" fill="{NAVY}"/>')
for i, c in enumerate(COLS):
    parts.append(f'<text x="{(CX[i] + CX[i + 1]) / 2}" y="{TOP + 38}" text-anchor="middle" class="hd">{c}</text>')
parts.append(f'<rect x="{CX[0]}" y="{RY[0]}" width="{CX[1] - CX[0]}" height="{RY[-1] - RY[0]}" fill="{NAVY}"/>')
for i, (name, sub, _) in enumerate(ROWS):
    cy = RY[i] + RH / 2
    parts.append(f'<text x="{(CX[0] + CX[1]) / 2}" y="{cy - 4}" text-anchor="middle" class="an">{escape(name)}</text>')
    parts.append(f'<text x="{(CX[0] + CX[1]) / 2}" y="{cy + 20}" text-anchor="middle" class="as">{escape(sub)}</text>')
    if i:
        parts.append(f'<line x1="{CX[0]}" y1="{RY[i]}" x2="{CX[1]}" y2="{RY[i]}" stroke="#2a3d5e" stroke-width="2"/>')

b = {}
for key, args in {
    "trigger": (1, 2, "Mon & Thu SAP export; a WhatsApp query arrives", "", "purple"),
    "input": (2, 1, "Uploads 3 CSVs; CS rep logs each query", "SKUs, stock, sales; query category", "blue"),
    "context": (3, 3, "Data checks + signed-off rules", "Min/max cover, festival months, owner per metric", "green"),
    "process": (4, 3, "Cover per SKU, reply clock, order-drop check", "", "yellow"),
    "rules": (5, 3, "Flags exceptions, routes each to one owner", "Rules, no LLM", "pink"),
    "store": (5, 4, "Runs, decisions, queries, alerts", "", "teal"),
    "act": (6, 1, "Owner acts by deadline", "Approve order, reply, acknowledge alert", "orange"),
    "dash": (6, 0, "Dashboard: needs action today", "Escalations, problem → fix, Hindi / English", "red"),
    "zoho": (6, 5, "Draft purchase orders", "Approved quantities only", "blue"),
}.items():
    svg, rect = box(*args)
    parts.append(svg)
    b[key] = rect


def R(k): x, y, w, h = b[k]; return x + w, y + h / 2
def L(k): x, y, w, h = b[k]; return x, y + h / 2
def T(k): x, y, w, h = b[k]; return x + w / 2, y
def B(k): x, y, w, h = b[k]; return x + w / 2, y + h


x1, y1 = R("trigger"); x2, y2 = B("input")
parts.append(arrow(f"M{x1} {y1} H{x2} V{y2 + 4}"))
x1, y1 = R("input"); x2, y2 = L("context")
parts.append(arrow(f"M{x1} {y1} H{CX[3] - 4} V{y2} H{x2 - 4}"))
x1, y1 = R("context"); x2, y2 = L("process")
parts.append(arrow(f"M{x1} {y1} H{x2 - 4}"))
x1, y1 = R("process"); x2, y2 = L("rules")
parts.append(arrow(f"M{x1} {y1} H{x2 - 4}"))
x1, y1 = B("rules"); x2, y2 = T("store")
parts.append(arrow(f"M{x1} {y1} V{y2 - 4}"))
x1, y1 = T("rules"); x2, y2 = L("act")
parts.append(arrow(f"M{x1} {y1} V{y2} H{x2 - 4}", "exceptions only", x1 + 8, y2 - 8))
# store feeds Deepa's dashboard (up the right-hand channel of the AI column)
sx, sy = R("store"); dx, dy = L("dash")
parts.append(arrow(f"M{sx} {sy} H{CX[6] + 8} V{dy} H{dx - 4}", "live data", CX[6] + 16, sy + 22))
# not acted on by the deadline -> escalates to Deepa
ax, ay = T("act"); dbx, dby = B("dash")
parts.append(arrow(f"M{ax} {ay} V{dby + 4}", "late → escalates", ax - 10, (ay + dby) / 2 + 4, "end"))
# approved quantities -> Zoho draft POs
ax2, ay2 = B("act"); zx, zy = T("zoho")
parts.append(arrow(f"M{ax2 + 70} {ay2} V{zy - 4}", "approved quantities", ax2 + 62, ay2 + 40, "end"))

H = RY[-1] + 30
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<defs>
  <marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{NAVY}"/></marker>
  <style>
    text {{ font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; fill: {NAVY}; }}
    .tt {{ font-size: 34px; font-weight: 700; }}
    .st {{ font-size: 17px; fill: #4a5a78; }}
    .hd {{ font-size: 21px; font-weight: 600; fill: #ffffff; }}
    .an {{ font-size: 21px; font-weight: 700; fill: #ffffff; }}
    .as {{ font-size: 15px; fill: #c9d4e8; }}
    .bt {{ font-size: 17px; font-weight: 650; }}
    .bb {{ font-size: 14.5px; fill: #33425e; }}
    .al {{ font-size: 13px; font-style: italic; fill: #4a5a78; }}
    .pn {{ font-size: 19px; font-weight: 700; fill: #b3430a; }}
    .pc {{ font-size: 15.5px; font-weight: 600; fill: #c92a2a; }}
    .pb {{ font-size: 15px; fill: #33425e; }}
    .pf {{ font-size: 15px; font-weight: 600; fill: {NAVY}; }}
  </style>
</defs>
<rect width="{W}" height="{H}" fill="#ffffff"/>
<g transform="translate(470 14) scale(0.95)">
  <circle cx="32" cy="32" r="31" fill="#fff4ec" stroke="#f3cdb0" stroke-width="2"/>
  <path d="M32 23 C31 18 31.5 13 33.5 8" fill="none" stroke="#2f9e44" stroke-width="3" stroke-linecap="round"/>
  <path d="M31.5 21 C26 20 21 16 19 10 C25 10 30 14 31.5 21 Z" fill="#40c057"/>
  <path d="M33 19 C35 13 40 9 46 8.5 C45 14.5 40 18.5 33 19 Z" fill="#2f9e44"/>
  <path d="M20.5 25 C25 21.5 39 21.5 43.5 25 C43 35 37.5 47 33 56 C32.4 57.2 31.6 57.2 31 56 C26.5 47 21 35 20.5 25 Z" fill="#e8590c"/>
  <path d="M24.5 31 L30 31 M34.5 37 L40 37 M27 43 L31.5 43" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round"/>
</g>
<text x="548" y="58" class="tt">Case 1 · Freshroots Operations — Components Map</text>
<text x="548" y="86" class="st">Mandate: live in 90 days, within ₹15 lakh, with 3 IT staff and 1 analyst. No AI team: SAP exports and written rules.</text>
{chr(10).join(parts)}
</svg>
'''
open(out, "w").write(svg)
print(out, W, H)
