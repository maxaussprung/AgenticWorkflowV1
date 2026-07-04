#!/usr/bin/env python
"""Reusable Playwright proof-screenshot harness for the VVF frontend.

WHY: every proof needs the same boilerplate (route-intercept the boot calls so there are zero error
toasts, then capture 3 sizes). This bakes in the invariant parts so an agent only fills the two CONFIG
blocks below instead of rebuilding it. Full rationale + gotchas: ../../00-playwright-proof-howto.md.

RULES (from memory 00): NO MSW (broken in-browser). Route interception only. Backend NOT needed.
`restRequest` returns {data:<body>} so a route body = the RAW payload. `/directives/orders/Unpaid/count`
MUST stay a bare number. Read prefilled inputs with page.input_value(), not get_attribute('value').

RUN (repo venv), with `pnpm dev` already up on :3000:
  C:/Users/jonas.hauser/ROOTPOST/Post/.venv/Scripts/python.exe .memory/tools/scripts/proof_shots.py <out_dir> [--annotate]
`--annotate` also emits `<name>_annotated.png` per viewport shot with red guides at each table column's
data-left (red + "+Npx" label when the header is offset), and prints an ALIGNMENT: OK/MISALIGNED verdict
(the anti-fudge gate for the #1 recurring bug — see 02 #1). Post the annotated shot as a 3rd PR comment.
Copy this file to the scratchpad and edit the two CONFIG blocks; delete your copy when done.
If you improve this harness, update THIS file (self-heal) so the next agent benefits.
"""
import json, sys, pathlib, subprocess
from playwright.sync_api import sync_playwright

API = "https://localhost:7098"
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = pathlib.Path(_args[0] if _args else ".")
ANNOTATE = "--annotate" in sys.argv   # also emit <name>_annotated.png with red column-alignment guides + verdict

def _find_mocks():
    # Robust even when this file is copied to the scratchpad: try (1) next to this file's tools/testdata,
    # (2) the git repo's .memory/tools/testdata. Whichever exists wins.
    here = pathlib.Path(__file__).resolve().parent.parent / "testdata" / "mocks.json"
    if here.exists():
        return here
    try:
        root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
        cand = pathlib.Path(root) / ".memory" / "tools" / "testdata" / "mocks.json"
        if cand.exists():
            return cand
    except Exception:
        pass
    return here  # fall through -> clear FileNotFoundError with the expected path
DATA = json.loads(_find_mocks().read_text(encoding="utf-8"))
BOOT = DATA["boot"]

# UX overlay (see 02 #1): injected into the live DOM then screenshotted (exact coords, no extra deps).
# (a) per-table column guides — green if the header text aligns to its column data, red + "+Npx" if
#     offset >2px. (b) GAP guides with px labels for the UX designer — left/right page margins, vertical
#     gaps between stacked top-level blocks, and the gap to the viewport bottom. Returns {tables, gaps}.
ANNOTATE_JS = r"""() => {
  document.querySelectorAll('.__uxovl').forEach(e => e.remove());
  const rep = {tables: [], gaps: [], clips: []};
  const vw = window.innerWidth, vh = window.innerHeight;
  const mk = (s) => { const d = document.createElement('div'); d.className = '__uxovl';
    Object.assign(d.style, {position:'fixed', zIndex:'2147483647', pointerEvents:'none'}, s);
    document.body.appendChild(d); return d; };
  const lbl = (x, y, t) => { const d = mk({left:Math.max(0,x)+'px', top:Math.max(0,y)+'px'}); d.textContent = t;
    Object.assign(d.style, {color:'#fff', background:'red', font:'bold 11px sans-serif', padding:'0 3px', whiteSpace:'nowrap'}); };
  const vline = (x, y1, y2, c) => mk({left:x+'px', top:Math.max(0,y1)+'px', width:'2px', height:Math.max(0,y2-y1)+'px', background:c});
  const hline = (x1, x2, y, c) => mk({left:Math.max(0,x1)+'px', top:y+'px', width:Math.max(0,x2-x1)+'px', height:'2px', background:c});
  // content-left = where text actually starts. Amarillo MuiTableCell has 16px left padding on BOTH thead
  // and tbody cells, so a box-left vs box-left compare is fine but a label-div vs box compare reports a
  // phantom +16px. Compare content-left vs content-left.
  const contentLeft = (el) => {
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let n, best = null;
    while ((n = w.nextNode())) { if (!n.nodeValue || !n.nodeValue.trim()) continue;
      const r = document.createRange(); r.selectNodeContents(n); const l = r.getBoundingClientRect().left;
      if (best === null || l < best) best = l; }
    if (best !== null) return best;
    const inner = el.querySelector('*'); return (inner || el).getBoundingClientRect().left;
  };
  // (a) table header vs column-data alignment
  document.querySelectorAll('table').forEach((tbl, ti) => {
    const ths = tbl.querySelectorAll('thead th'); const row = tbl.querySelector('tbody tr'); if (!row) return;
    const tds = row.querySelectorAll('td'); const tr = tbl.getBoundingClientRect();
    ths.forEach((th, ci) => { const td = tds[ci]; if (!td) return;
      const lab = th.querySelector('div') || th;
      const hasHeaderText = !!(lab.textContent || '').trim();   // icon-only / rowActions / checkbox column => no label to align
      // An action column (body cell holds a button/link) is not a data column: the header sits over the
      // button's PADDING, not its text, so a small offset is expected — don't flag it (like empty headers).
      const isAction = !hasHeaderText || !!td.querySelector('button, a, [role="button"], input[type="button"], input[type="submit"]');
      const hL = contentLeft(th), bL = contentLeft(td);
      const off = Math.round(hL - bL), bad = Math.abs(off) > 2 && !isAction;
      vline(bL, tr.top, tr.top + tr.height, bad ? 'red' : 'rgba(0,150,0,0.55)');
      if (bad) { vline(hL, tr.top - 18, tr.top + 2, 'red'); lbl(hL, tr.top - 18, (off>0?'+':'') + off + 'px'); }
      rep.tables.push({table: ti, col: ci, header: (lab.textContent||'').trim().slice(0,24), offset: off, action: isAction});
    });
  });
  // (b) gaps between top-level [data-testid] blocks + page-edge margins (px labels for the UX designer)
  const vis = [...document.querySelectorAll('[data-testid]')].filter(e => {
    const r = e.getBoundingClientRect(); return r.width > 40 && r.height > 16 && r.bottom > 0 && r.top < vh; });
  const set = new Set(vis);
  const tops = vis.filter(e => { let p = e.parentElement; while (p) { if (set.has(p)) return false; p = p.parentElement; } return true; });
  const blocks = tops.map(e => e.getBoundingClientRect()).sort((a, b) => a.top - b.top);
  if (blocks.length) {
    const minL = Math.min(...blocks.map(b => b.left)), maxR = Math.max(...blocks.map(b => b.right));
    const midY = Math.min(vh - 8, Math.max(24, blocks[0].top + 20));
    if (minL > 1)      { hline(0, minL, midY, 'red');  lbl(Math.max(0, minL/2 - 10), midY - 16, Math.round(minL) + 'px'); rep.gaps.push({kind:'left', px:Math.round(minL)}); }
    if (vw - maxR > 1) { hline(maxR, vw, midY, 'red'); lbl(maxR + 3, midY - 16, Math.round(vw - maxR) + 'px'); rep.gaps.push({kind:'right', px:Math.round(vw - maxR)}); }
    for (let i = 0; i < blocks.length - 1; i++) { const g = Math.round(blocks[i+1].top - blocks[i].bottom); if (g <= 2) continue;
      const x = Math.round((Math.max(blocks[i].left, blocks[i+1].left) + Math.min(blocks[i].right, blocks[i+1].right)) / 2);
      vline(x, blocks[i].bottom, blocks[i+1].top, 'red'); lbl(x + 3, blocks[i].bottom + Math.max(0, (g-14)/2), g + 'px'); rep.gaps.push({kind:'v-gap', px:g}); }
    const last = blocks[blocks.length - 1], gb = Math.round(vh - last.bottom);
    if (gb > 2) { const x = Math.round((last.left + last.right) / 2); vline(x, last.bottom, vh, 'red'); lbl(x + 3, last.bottom + Math.max(0, (gb-14)/2), gb + 'px'); rep.gaps.push({kind:'bottom', px:gb}); }
  }
  // (c) input-control gaps: horizontal between adjacent controls in a row (Benutzer<->Aktion<->Von<->Bis)
  //     and vertical between control rows (field row -> button). Controls = tagged leaves that are/hold a form control.
  const isCtrl = (el) => el.matches('input,select,textarea,button,[role="button"],[role="combobox"]') ||
                         !!el.querySelector('input,select,textarea,button,[role="button"],[role="combobox"]');
  const leaves = vis.filter(e => isCtrl(e) && !vis.some(o => o !== e && e.contains(o)));
  const items = leaves.map(e => e.getBoundingClientRect()).sort((a, b) => a.top - b.top);
  let s = 0, prevRow = null;
  for (let i = 1; i <= items.length; i++) {
    if (i < items.length && Math.abs(items[i].top - items[s].top) < 14) continue;
    const row = items.slice(s, i).sort((a, b) => a.left - b.left);
    for (let j = 0; j < row.length - 1; j++) { const g = Math.round(row[j+1].left - row[j].right); if (g <= 1) continue;
      const y = Math.round((row[j].top + row[j].bottom) / 2); hline(row[j].right, row[j+1].left, y, 'red');
      lbl(row[j].right + Math.max(0, (g-22)/2), y - 16, g + 'px'); rep.gaps.push({kind:'h-gap', px:g}); }
    if (prevRow) { const rowTop = Math.min(...row.map(r => r.top)), prevBot = Math.max(...prevRow.map(r => r.bottom));
      const vg = Math.round(rowTop - prevBot); if (vg > 1) { const x = Math.round((row[0].left + row[0].right) / 2);
        vline(x, prevBot, rowTop, 'red'); lbl(x + 3, prevBot + Math.max(0, (vg-14)/2), vg + 'px'); rep.gaps.push({kind:'ctrl-v-gap', px:vg}); } }
    prevRow = row; s = i;
  }
  // (d) CUT-OFF / clipping (the "things that get cut" gate — extend this as new spacing/cut-off findings
  //     are learned, see 02 CLOSED LOOP). Two cases: (i) text clipped inside its own box (overflow
  //     hidden/clip or ellipsis while scrollWidth > clientWidth) — e.g. a truncated button label /
  //     table cell; (ii) an element cut at the viewport right edge (right > viewport width at 1280).
  const seenClip = new Set();
  [...document.querySelectorAll('button, td, th, [data-testid]')].forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 8 || r.bottom < 0 || r.top > vh) return;
    const cs = getComputedStyle(el);
    const hidden = cs.overflowX === 'hidden' || cs.overflowX === 'clip' || cs.textOverflow === 'ellipsis';
    const textClipped = hidden && el.scrollWidth > el.clientWidth + 1;
    const pastVp = r.right > vw + 1 && r.left < vw;                 // cut at the viewport right edge
    if (!textClipped && !pastVp) return;
    const key = Math.round(r.left) + ',' + Math.round(r.top) + ',' + el.tagName;
    if (seenClip.has(key)) return; seenClip.add(key);
    const amt = textClipped ? (el.scrollWidth - el.clientWidth) : Math.round(r.right - vw);
    mk({left: Math.max(0, r.left) + 'px', top: Math.max(0, r.top) + 'px',
        width: Math.max(0, Math.min(r.width, vw - r.left)) + 'px', height: r.height + 'px',
        border: '2px solid red', boxSizing: 'border-box'});
    lbl(Math.min(r.right, vw) - 52, r.top - 14, 'CLIP ' + amt + 'px');
    rep.clips.push({tag: el.tagName.toLowerCase(), kind: textClipped ? 'text' : 'viewport',
                    text: (el.textContent || '').trim().slice(0, 24), px: amt});
  });
  return rep;
}"""
CLEAR_JS = "() => document.querySelectorAll('.__uxovl').forEach(e => e.remove())"

# ============ CONFIG 1: the page + how to reach the proof state ============
PAGE = {
    "url": "http://localhost:3000/directive-orders/search",
    # actions run after goto, before shooting: (playwright_page_method, selector)
    "after_goto": [("click", '[data-testid="directive-search-submit"]')],
    "wait_for": '[data-testid="trefferliste-results"]',   # selector proving the fix is on screen
    # "scroll_to": '[data-testid="…"]',                   # optional: scroll this into view before each shot
    #   (for a below-the-fold element like a results table on a page without auto-scroll — so the
    #    --annotate viewport overlay lands on it)
    "shots": [("shot_1280.png", 1280, 1024, False),
              ("shot_1920.png", 1920, 1680, False),
              ("shot_full.png", 1920, 1680, True)],        # True => full_page
}
# ============ CONFIG 2: page-specific mocks (exact path -> raw body) ========
# boot calls + /lookups/* + a catch-all are handled automatically. Add only the page's own endpoints:
PAGE_MOCKS = {
    "/directives/orders/search": {"items": DATA["searchRows"], "count": len(DATA["searchRows"])},
    # "/audit-logs": {"items": DATA["auditLogs"], "count": len(DATA["auditLogs"])},   # Logdaten example
    # "/directives/orders/59-5121": DATA["detail"],
}
# ===========================================================================

def body_for(path):
    if path in PAGE_MOCKS:  return PAGE_MOCKS[path]
    if path in BOOT:        return BOOT[path]
    if path.startswith("/lookups/"): return []
    print("UNMATCHED", path)          # catch-all: never error -> no toast. Add real ones above if needed.
    return []

def handler(route):
    p = route.request.url.split(API, 1)[-1].split("?")[0]
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body_for(p)))

with sync_playwright() as pw:
    br = pw.chromium.launch()
    ctx = br.new_context(ignore_https_errors=True, viewport={"width": 1280, "height": 1024})
    pg = ctx.new_page()
    pg.route(f"{API}/**", handler)
    pg.goto(PAGE["url"], wait_until="networkidle")
    for method, sel in PAGE["after_goto"]:
        getattr(pg, method)(sel)
    if PAGE["wait_for"]:
        pg.wait_for_selector(PAGE["wait_for"])
    pg.wait_for_timeout(800)                              # let smooth-scroll / async render settle
    misaligned = []; clipped = []
    for name, w, h, full in PAGE["shots"]:
        pg.set_viewport_size({"width": w, "height": h})
        pg.wait_for_timeout(300)
        if PAGE.get("scroll_to"):                          # bring a below-the-fold element into the viewport
            pg.evaluate("(s) => document.querySelector(s) && document.querySelector(s).scrollIntoView({block: 'start'})", PAGE["scroll_to"])
            pg.wait_for_timeout(250)
        pg.screenshot(path=str(OUT / name), full_page=full)
        print("shot", name)
        if ANNOTATE and not full:                         # annotate viewport shots (fixed overlay ~ viewport)
            rep = pg.evaluate(ANNOTATE_JS)
            pg.wait_for_timeout(80)
            ann = OUT / (pathlib.Path(name).stem + "_annotated.png")
            pg.screenshot(path=str(ann), full_page=False)
            pg.evaluate(CLEAR_JS)
            print("annotated", ann.name)
            # only real DATA columns count — icon-only rowActions/checkbox (empty header) and action-button
            # columns (header sits over button padding) are excluded, they are not data misalignment
            misaligned += [(name, r["header"], r["offset"]) for r in rep.get("tables", [])
                           if abs(r["offset"]) > 2 and r["header"].strip() and not r.get("action")]
            gaps = rep.get("gaps", [])
            if gaps:
                print(f"   gaps({name}): " + ", ".join(f"{g['kind']}={g['px']}px" for g in gaps))
            clips = rep.get("clips", [])
            clipped += [(name, c["tag"], c["text"], c["px"], c["kind"]) for c in clips]
            if clips:
                print(f"   CLIPS({name}): " + ", ".join(f"{c['tag']}'{c['text']}'={c['px']}px/{c['kind']}" for c in clips))
    br.close()
if ANNOTATE:
    if misaligned:
        print("ALIGNMENT: MISALIGNED (add the DataTable styleOverride — see 02 #1):")
        for n, hdr, off in misaligned: print(f"   {n}: header '{hdr}' offset {off:+}px")
    else:
        print("ALIGNMENT: OK — every table header within 2px of its column data")
    if clipped:
        print("CLIPPED: content cut off (fix + re-annotate — see 02 CLOSED LOOP):")
        for n, tag, txt, px, kind in clipped: print(f"   {n}: <{tag}> '{txt}' cut {px}px ({kind})")
    else:
        print("CLIPPING: OK — no clipped/overflowing content detected")
print("DONE ->", OUT)
