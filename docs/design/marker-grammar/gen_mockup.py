import json, random

symbols = open("/home/elder/.hermes/cache/scratch/symbols.html").read()
GLYPHS = json.load(open("/home/elder/.hermes/cache/scratch/glyphs.json"))

LOCS = [
 ("Megaton","settlement","home-group","trade","low","normal"),
 ("Rivet City","settlement","home-group","trade","low","selected"),
 ("Junktown","settlement","home-group","trade","low","normal"),
 ("Shady Sands","settlement","home-group","trade","low","transit"),
 ("New Reno","city","city","trade","medium","normal"),
 ("Diamond City","city","city","trade","medium","normal"),
 ("The Hub","city","city","trade","medium","unscouted"),
 ("Red Rocket","gas_station","gas-station","clear","low","normal"),
 ("Poseidon Station","gas_station","gas-station","clear","low","cleared"),
 ("Super Duper Mart","supermarket","cart","clear","low","salvage"),
 ("Fallon's","supermarket","cart","clear","low","normal"),
 ("Corvega","factory","factory","clear","medium","normal"),
 ("Saugus Ironworks","factory","factory","clear","medium","transit"),
 ("College Square","metro","subway-variant","clear","medium","normal"),
 ("Raven Rock","military","shield-sword","clear","high","selected"),
 ("Fort Strong","military","shield-sword","clear","high","normal"),
 ("Hidden Valley","brotherhood_outpost","shield","clear","high","unscouted"),
 ("Big MT","research","flask","clear","high","normal"),
 ("The Institute","research","flask","clear","high","transit"),
 ("Power Relay 4","power","lightning-bolt","clear","medium","normal"),
 ("Mass Fusion","power","lightning-bolt","clear","medium","cleared"),
 ("Galaxy News","entertainment","ferris-wheel","clear","low","normal"),
 ("Nuka-World","entertainment","ferris-wheel","clear","low","normal"),
 ("Jefferson Memorial","landmark","bank","look","medium","normal"),
 ("Bunker Hill","landmark","bank","look","medium","salvage"),
 ("Vault 111","vault_tec","radioactive","clear","medium","unscouted"),
 ("Vault 87","vault_tec","radioactive","clear","medium","normal"),
 ("Quincy","ruin","wall","clear","medium","cleared"),
 ("Lexington","ruin","wall","clear","medium","normal"),
 ("Concord","ruin","wall","clear","medium","normal"),
 ("the Capital Wasteland","region","map","look","high","normal"),
 ("the Glowing Sea","region","map","look","high","normal"),
 ("the Pitt","region","map","look","high","cleared"),
 ("Far Harbor","region","map","look","high","normal"),
 ("Point Lookout","region","map","look","high","unscouted"),
 ("Zion Canyon","region","map","look","high","normal"),
 ("The Quiet Zone","exclusion_zone","fence","clear","high","normal"),
 ("ArcJet Systems","observation_facility","monitor-eye","clear","medium","normal"),
 ("Tenpenny Tower","vertical_refuge","office-building","clear","medium","normal"),
 ("Scrapyard","wasteland_site","sign-direction","clear","low","normal"),
 ("Old Olney","wasteland_site","sign-direction","clear","low","unscouted"),
 ("The Combat Zone","combat_zone","sword-cross","look","high","normal"),
 ("Your Vault","home","home-group","home","low","normal"),
 # --- expanded archetype set ---
 ("Mass Bay Hospital","hospital","hospital","clear","medium","normal"),
 ("Federal Prison","prison","handcuffs","clear","high","unscouted"),
 ("Dunwich School","school","school","clear","medium","normal"),
 ("Warwick Stadium","stadium","stadium","clear","medium","salvage"),
 ("Boston Airport","airport","airplane","clear","high","normal"),
 ("Scituate Dam","dam","waves","clear","medium","cleared"),
 ("Granite Quarry","quarry","pickaxe","clear","medium","normal"),
 ("Marlborough Farm","farm","farm","clear","low","normal"),
 ("Starlight Drive-In","drive_in","drive-in","clear","low","normal"),
 ("All Faiths Chapel","church","church","look","low","normal"),
 ("Police Precinct","police","police","clear","medium","transit"),
 ("Nahant Shipyard","shipyard","shipyard","clear","high","normal"),
 ("Raider Camp","raider","raider","clear","high","normal"),
 ("Skull Hollow","mutant","mutant","clear","high","unscouted"),
]

ICON2KEY = {"home-group":"settlement","city":"city","gas-station":"gas_station","cart":"supermarket",
 "factory":"factory","subway-variant":"metro","shield-sword":"military","shield":"brotherhood","flask":"research",
 "lightning-bolt":"power","ferris-wheel":"entertainment","bank":"landmark","radioactive":"vault_tec","wall":"ruin",
 "map":"region","fence":"exclusion_zone","sign-direction":"wasteland_site","monitor-eye":"observation_facility",
 "office-building":"vertical_refuge","sword-cross":"combat_zone","hospital":"hospital","handcuffs":"prison",
 "school":"school","stadium":"stadium","airplane":"airport","waves":"dam","pickaxe":"quarry","barley":"farm",
 "drive-in":"drive_in","church":"chapel","police-badge":"police","anchor":"shipyard","skull":"raider","skull-crossbones":"mutant"}
LOCS = [(n,g,ICON2KEY.get(i,i),p_,r,st) for (n,g,i,p_,r,st) in LOCS]
KEY2ICON = {v: k for k, v in ICON2KEY.items()}
LOCS = [(n,g,KEY2ICON.get(i,i),p_,r,st) for (n,g,i,p_,r,st) in LOCS]
GLYPHS = {}          # prod icon set (material symbols), not the drawn set
SYM = {"airplane":"airport","anchor":"shipyard","barley":"farm","drive-in":"drive_in",
       "movie-open":"drive_in","police-badge":"police","skull":"raider","skull-crossbones":"mutant",
       "waves":"dam","pickaxe":"quarry","military":"shield-sword"}
GL = set()
LOCS = [l for l in LOCS if (not GL) or l[2] in GL or l[3]=='home']
random.seed(31)
W, H = 1010, 880
cols, rows = 7, 7
pts = []
for i in range(len(LOCS)):
    c, r = i % cols, i // cols
    x = 62 + c * (W - 124) / (cols - 1) + random.uniform(-11, 11)
    y = 70 + r * (H - 150) / (rows - 1) + random.uniform(-10, 10)
    pts.append((round(x, 1), round(y, 1)))

SHAPE = {"clear": "circle", "trade": "diamond", "look": "hexagon", "home": "square"}


def body(purpose, r=4.2):
    kind = SHAPE[purpose]
    if kind == "circle":
        return f'<circle class="mb" r="{r}"/>'
    if kind == "diamond":
        return f'<path class="mb" d="M 0 {-r} L {r} 0 L 0 {r} L {-r} 0 Z"/>'
    if kind == "hexagon":
        h = round(r * 1.1, 3); dx = round(h * (3 ** 0.5) / 2, 3); dy = round(h / 2, 3)
        return f'<path class="mb mb-open" d="M 0 {-h} L {dx} {-dy} L {dx} {dy} L 0 {h} L {-dx} {dy} L {-dx} {-dy} Z"/>'
    return f'<rect class="mb" x="{-r}" y="{-r}" width="{r*2}" height="{r*2}" rx="{round(r*0.32,2)}"/>'


def marker(loc, size=84, label=False):
    name, grp, icon, purpose, risk, state = loc
    cls = f"m risk-{risk}" + (" cleared" if state == "cleared" else "") + (" locked" if state == "unscouted" else "")
    o = [f'<svg class="{cls}" width="{size}" height="{size}" viewBox="-7 -7 14 14">', body(purpose)]
    if state == "unscouted":
        o.append('<use href="#i-help" class="gly" x="-2.2" y="-2.2" width="4.4" height="4.4"/>')
    else:
        o.append(f'<use href="#i-{SYM.get(icon, icon)}" class="gly" x="-2.2" y="-2.2" width="4.4" height="4.4"/>')
    if state == "salvage":
        o.append('<g transform="translate(3.1,-3.1)"><circle class="crate" r="2"/><use href="#i-package-variant" class="cratei" x="-1.35" y="-1.35" width="2.7" height="2.7"/></g>')
    if state == "cleared":
        o.append('<g transform="translate(3.1,-3.1)"><circle class="chk" r="1.9"/><path class="chki" d="M -1 .1 L -.3 .8 L 1 -.6"/></g>')
    if state == "transit":
        o.append('<circle class="pulse" r="4.7" opacity=".55"/><g transform="translate(3.1,-3.1)"><circle class="pip" r="2"/><use href="#i-walk" class="pipi" x="-1.3" y="-1.3" width="2.6" height="2.6"/></g>')
    if state == "selected":
        o.append('<circle class="selring" r="5.4"/><circle class="ping" r="5.4" opacity=".85" transform="scale(1.22)"/>')
    if state == "unscouted":
        o.append('<circle class="dash" r="5.4"/>')
    o.append("</svg>")
    lab = f'<div class="mlabel">{name}</div>' if label else ""
    return f'<div class="mk">{"".join(o)}{lab}</div>'


lab_set = {"Raven Rock", "Rivet City", "New Reno", "the Glowing Sea", "Your Vault", "Nuka-World",
           "Vault 111", "Junktown", "Mass Bay Hospital", "Warwick Stadium", "All Faiths Chapel", "Raider Camp"}
cards = [f'<div style="position:absolute;left:{x-42}px;top:{y-42}px">{marker(l, label=l[0] in lab_set)}</div>'
         for l, (x, y) in zip(LOCS, pts)]

LEG_SHAPE = [("clear", "CLEAR", "raid · salvage"), ("trade", "TRADE", "caravan"),
             ("look", "LOOK", "landmark"), ("home", "HOME", "your vault")]

LEGACY = [("home-group", "settlement"), ("city", "city"), ("gas-station", "gas station"), ("cart", "supermarket"),
          ("factory", "factory"), ("subway-variant", "metro"), ("shield-sword", "military"), ("shield", "brotherhood"),
          ("flask", "research"), ("lightning-bolt", "power"), ("ferris-wheel", "entertainment"), ("bank", "landmark"),
          ("radioactive", "vault-tec"), ("wall", "ruin"), ("map", "region"), ("fence", "exclusion"),
          ("sign-direction", "wasteland"), ("monitor-eye", "observation"), ("office-building", "refuge"), ("sword-cross", "combat zone")]
NEWG = [("hospital", "hospital"), ("barley", "farm"), ("movie-open", "drive-in"), ("church", "chapel")]

LEG_RISK = [("LOW", "#5dff8f"), ("MEDIUM", "#ffc14d"), ("HIGH", "#ff5f57")]

shapes = "".join(
    f'<div class="lg"><svg width="46" height="46" viewBox="-7 -7 14 14" class="risk-low">{body(p)}'
    f'<circle r="1" style="fill:var(--low);opacity:.85"/></svg><b>{n}</b><i>{d}</i></div>'
    for p, n, d in LEG_SHAPE)

def gcell(i, n):
    if i in GLYPHS:
        inner = f'<svg width="24" height="24" viewBox="-3 -3 6 6" class="gc">{GLYPHS[i]}</svg>'
    else:
        inner = f'<svg width="30" height="30" viewBox="-2 -2 28 28" class="gonly"><use href="#i-{SYM.get(i,i)}" width="30" height="30"/></svg>'
    return f'<div class="lg g">{inner}<i>{n}</i></div>'

glyphs = "".join(gcell(i, n) for i, n in LEGACY + NEWG)
risks = "".join(f'<div class="lg"><span class="chip" style="--c:{c}"></span><i>{n}</i></div>' for n, c in LEG_RISK)
annot = marker(("Raven Rock", "military", "shield-sword", "clear", "high", "selected"), size=104)
sizestrip = "".join(
    f'<div class="lg">{marker(("x","military","shield-sword","clear","high","normal"), size=sz)}<i>{sz}px</i></div>'
    for sz in (56, 72, 84, 96))

html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
:root{{--bg:#07100b;--panel:#0b1610;--line:#1b3626;--green:#5dff8f;--gd:#2f7a4f;--gf:#163a26;--ink:#a7f8c4;--low:#5dff8f;--medium:#ffc14d;--high:#ff5f57;--unk:#8a9a92}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font-family:ui-monospace,Menlo,monospace;padding:18px 22px}}
h1{{font-size:13px;letter-spacing:.24em;color:var(--green);margin:0 0 3px;font-weight:600}}
.sub{{font-size:11px;color:var(--gd);letter-spacing:.05em;margin-bottom:12px}}
.wrap{{display:grid;grid-template-columns:1010px 1fr;gap:16px}}
.map{{position:relative;height:880px;border:1px solid var(--line);overflow:hidden;
 background:radial-gradient(700px 420px at 30% 20%,#0d2216 0%,transparent 65%),radial-gradient(600px 380px at 78% 74%,#0c1e14 0%,transparent 60%),#08130d}}
.grid{{position:absolute;inset:0;background-image:linear-gradient(var(--gf) 1px,transparent 1px),linear-gradient(90deg,var(--gf) 1px,transparent 1px);background-size:58px 58px;opacity:.45}}
.road{{position:absolute;inset:0;opacity:.26}}
.mk{{position:relative;display:flex;flex-direction:column;align-items:center}}
.mlabel{{font-size:8px;letter-spacing:.03em;color:var(--ink);background:rgba(4,12,8,.9);border:1px solid var(--line);padding:0 3px;white-space:nowrap;margin-top:1px}}
svg.m{{overflow:visible}}
.mb{{fill:#0a1410;stroke:var(--c);stroke-width:.36;filter:drop-shadow(0 0 1.3px color-mix(in srgb,var(--c) 70%,transparent))}}
.mb-open{{fill:none}}
.gly{{color:var(--c);fill:var(--c);opacity:.92}}
.risk-low{{--c:var(--low)}} .risk-medium{{--c:var(--medium)}} .risk-high{{--c:var(--high)}}
.cleared{{opacity:.45}}
.locked .mb{{stroke:var(--unk);filter:none}} .locked .gly{{fill:var(--unk)}}
.dash{{fill:none;stroke:var(--unk);stroke-width:.26;stroke-dasharray:.85 .7;opacity:.85}}
.selring{{fill:none;stroke:var(--green);stroke-width:.42}} .ping{{fill:none;stroke:var(--green);stroke-width:.4;opacity:.85}}
.pulse{{fill:none;stroke:var(--c);stroke-width:.45}}
.pip{{fill:#0a1410;stroke:var(--medium);stroke-width:.28}} .pipi{{fill:var(--medium)}}
.crate{{fill:#0a1410;stroke:var(--low);stroke-width:.26}} .cratei{{fill:var(--low);opacity:.9}}
.chk{{fill:#0a1410;stroke:var(--gd);stroke-width:.26}} .chki{{fill:none;stroke:var(--gd);stroke-width:.5}}
.panel{{border:1px solid var(--line);background:linear-gradient(180deg,rgba(93,255,143,.05),rgba(93,255,143,.012));padding:9px 11px;margin-bottom:9px}}
.panel h3{{font-size:9px;letter-spacing:.2em;color:var(--green);margin:0 0 7px;font-weight:600}}
.row{{display:flex;gap:10px;align-items:flex-start;flex-wrap:wrap}}
.glyph-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:9px 5px}}
.lg{{display:flex;flex-direction:column;align-items:center;gap:2px;min-width:42px}}
.lg b{{font-size:8px;letter-spacing:.1em;color:var(--ink);font-weight:600}}
.lg i{{font-size:7.5px;color:var(--gd);font-style:normal;letter-spacing:.01em;text-align:center;line-height:1.15}}
.gonly use{{fill:var(--green);opacity:.9}}
.gly-c{{stroke:var(--c);fill:none;stroke-width:.62;stroke-linecap:round;stroke-linejoin:round}}
.gc path,.gc rect,.gc circle{{stroke:var(--green);fill:none;stroke-width:.62;stroke-linecap:round;stroke-linejoin:round;opacity:.92}}
.chip{{width:20px;height:20px;border-radius:3px;background:color-mix(in srgb,var(--c) 18%,transparent);border:1px solid var(--c);box-shadow:0 0 8px color-mix(in srgb,var(--c) 40%,transparent)}}
.annot{{display:grid;grid-template-columns:120px 1fr;gap:9px;align-items:center;border:1px solid var(--line);padding:8px;background:rgba(93,255,143,.03)}}
.annot .t{{font-size:8px;line-height:1.7;color:var(--ink)}} .annot .t em{{color:var(--green);font-style:normal}}
.split{{display:flex;gap:10px;margin-top:5px}} .split div{{flex:1;font-size:7.5px;color:var(--gd);border-top:1px solid var(--gf);padding-top:4px}}
</style></head><body>
<h1>WASTELAND MAP · MARKER GRAMMAR — v10</h1>
<div class="sub">shape = what you can do · glyph = what it is · colour = how dangerous · ring/badge = what is happening now · production glyph set · 25 archetypes · 84px markers</div>
<div class="wrap">
 <div class="map"><div class="grid"></div>
  <svg class="road" viewBox="0 0 1010 880"><path d="M-20 640 C 180 600, 300 680, 470 600 S 760 470, 1040 500" fill="none" stroke="#1d4a30" stroke-width="2" stroke-dasharray="7 9"/><path d="M180 -20 C 240 180, 150 360, 300 520 S 520 740, 560 900" fill="none" stroke="#163a26" stroke-width="1.6" stroke-dasharray="5 11"/></svg>
  {''.join(cards)}
 </div>
 <div>
  <div class="panel"><h3>SHAPE · AFFORDANCE</h3><div class="row">{shapes}</div></div>
  <div class="panel"><h3>GLYPH · MATERIAL SET (PRODUCTION TODAY)</h3><div class="glyph-grid">{glyphs}</div>
    <div class="split"><div>21 shipped archetypes</div><div>4 proposed: hospital · farm · drive-in · chapel</div></div></div>
  <div class="panel"><h3>MARKER SIZE</h3><div class="row">{sizestrip}</div></div>
  <div class="panel"><h3>COLOUR · DANGER</h3><div class="row">{risks}</div></div>
  <div class="panel"><h3>STATE · ANIMATION &amp; BADGES</h3><div class="row">
    <div class="lg"><svg width="40" height="40" viewBox="-7 -7 14 14" class="locked"><circle class="mb" r="4.2" style="stroke:var(--unk)"/><use href="#i-help" class="gly" x="-1.9" y="-1.9" width="3.8" height="3.8" style="fill:var(--unk)"/><circle class="dash" r="5.4"/></svg><i>unscouted</i></div>
    <div class="lg"><svg width="40" height="40" viewBox="-7 -7 14 14" class="risk-medium"><circle class="mb" r="4.2"/><use href="#i-flask" class="gly" x="-1.75" y="-1.75" width="3.5" height="3.5"/><circle class="pulse" r="4.7" opacity=".6"/><g transform="translate(3.1,-3.1)"><circle class="pip" r="2"/><use href="#i-walk" class="pipi" x="-1.3" y="-1.3" width="2.6" height="2.6"/></g></svg><i>en route</i></div>
    <div class="lg"><svg width="40" height="40" viewBox="-7 -7 14 14" class="risk-high"><circle class="mb" r="4.2"/><use href="#i-shield-sword" class="gly" x="-1.75" y="-1.75" width="3.5" height="3.5"/><circle class="selring" r="5.4"/><circle class="ping" r="5.4" opacity=".85" transform="scale(1.22)"/></svg><i>selected</i></div>
    <div class="lg"><svg width="40" height="40" viewBox="-7 -7 14 14" class="risk-low"><circle class="mb" r="4.2"/><use href="#i-cart" class="gly" x="-1.75" y="-1.75" width="3.5" height="3.5"/><g transform="translate(3.1,-3.1)"><circle class="crate" r="2"/><use href="#i-package-variant" class="cratei" x="-1.35" y="-1.35" width="2.7" height="2.7"/></g></svg><i>salvage</i></div>
    <div class="lg"><svg width="40" height="40" viewBox="-7 -7 14 14" class="risk-medium cleared"><circle class="mb" r="4.2"/><use href="#i-wall" class="gly" x="-1.75" y="-1.75" width="3.5" height="3.5"/><g transform="translate(3.1,-3.1)"><circle class="chk" r="1.9"/><path class="chki" d="M -1 .1 L -.3 .8 L 1 -.6"/></g></svg><i>cleared</i></div></div></div>
  <div class="annot">{annot}<div class="t"><em>● circle</em> → you can raid it<br><em>⚔ military</em> → shielded, worth the trip<br><em style="color:#ff5f57">red</em> → high risk, full party<br><em>◌ ping</em> → the site you selected</div></div>
 </div>
</div>
<svg width="0" height="0" style="position:absolute">{symbols}</svg>
</body></html>"""

open("/home/elder/.hermes/cache/scratch/map-grammar10.html", "w").write(html)
print("written:", len(html), "| locations:", len(LOCS))
