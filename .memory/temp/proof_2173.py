"""Proof for #2219 (REQ-DACT-003): a cancelled (Storniert) row in the Trefferliste keeps its
"Ansehen" (open) button ENABLED — only "Stornieren" is disabled. Drives the real search flow.
Run:  .venv/Scripts/python.exe .memory/temp/proof_2173.py
"""
import json, sys
from playwright.sync_api import sync_playwright

API = "https://localhost:7098"; OUT = ".memory/temp"
BOOT = {
    "/account/me": {"fullName": "Max Mustermann", "organizationUnit": "Customer Support", "role": "Admin"},
    "/directives/orders/Unpaid/count": 165,
    "/system/info": {"version": "1.0.0.0", "currentDate": "2026-07-01T08:00:00.000Z", "opalConnection": "offline"},
}
# Cancelled hit gets the NEWEST date so it sorts to row 0 (validFrom desc).
ROWS = [
    {"id": "c0000000-0000-0000-0000-000000000001", "formulaNumber": "9/0126", "type": "DropOffAuthorization",
     "customerLastName": "Storno", "addressSummary": "Rochusplatz 1, 1030 Wien",
     "validFrom": "2026-06-01T00:00:00Z", "validTo": None, "status": "Cancelled"},
    {"id": "a0000000-0000-0000-0000-000000000002", "formulaNumber": "8/0125", "type": "DropOffAuthorization",
     "customerLastName": "Muster", "addressSummary": "Ringstrasse 2, 1010 Wien",
     "validFrom": "2025-01-01T00:00:00Z", "validTo": "2027-01-01T00:00:00Z", "status": "Active"},
]

def handle(route):
    p = route.request.url.split(API, 1)[-1].split("?")[0]
    if p in BOOT: body = BOOT[p]
    elif p.startswith("/lookups/"): body = []
    elif p.startswith("/directives/orders/search"): body = {"items": ROWS, "count": len(ROWS)}
    else: print("UNMATCHED", p); body = []
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(ignore_https_errors=True, viewport={"width": 1280, "height": 1024})
    pg = ctx.new_page(); pg.route(f"{API}/**", handle)
    pg.goto("http://localhost:3000/directive-orders/search", wait_until="networkidle")
    pg.wait_for_selector('[data-testid="directive-search-submit"]'); pg.wait_for_timeout(400)
    pg.click('[data-testid="directive-search-submit"]')
    pg.wait_for_selector('[data-testid="open-order-0"]'); pg.wait_for_timeout(600)

    open0 = pg.query_selector('[data-testid="open-order-0"]')
    cancel0 = pg.query_selector('[data-testid="cancel-order-0"]')
    open_enabled = open0 is not None and not open0.is_disabled()
    cancel_disabled = cancel0 is not None and cancel0.is_disabled()
    storniert = pg.query_selector("text=Storniert") is not None
    print("ASSERT cancelled-row open (Ansehen) ENABLED:", open_enabled)
    print("ASSERT cancelled-row cancel (Stornieren) DISABLED:", cancel_disabled)
    print("ASSERT Storniert status shown:", storniert)

    try:
        pg.query_selector('[data-testid="trefferliste-results"]').scroll_into_view_if_needed()
    except Exception:
        pass
    pg.wait_for_timeout(300)
    for w, h in [(1280, 1024), (1920, 1680)]:
        pg.set_viewport_size({"width": w, "height": h}); pg.wait_for_timeout(400)
        pg.screenshot(path=f"{OUT}/proof_2173_{w}.png")
    pg.screenshot(path=f"{OUT}/proof_2173_full.png", full_page=True)
    b.close()
    print("PROOF", "OK" if (open_enabled and cancel_disabled and storniert) else "CHECK")
    sys.exit(0 if (open_enabled and cancel_disabled and storniert) else 1)
