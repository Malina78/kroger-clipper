#!/usr/bin/env python3
"""Kroger Coupon Clipper v4 — только клипинг, без логина"""

import asyncio, json, sys, time, ctypes
from pathlib import Path
from playwright.async_api import async_playwright

STATE_DIR = Path.home() / ".kroger-clipper"
STATE_FILE = STATE_DIR / "state.json"
PROFILE = str(STATE_DIR / "profile")

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BROWSER = Path(EDGE) if Path(EDGE).exists() else None

def msgbox(t, x):
    try: ctypes.windll.user32.MessageBoxW(0, x, t, 0x40)
    except: pass

async def clip_all(page):
    print("\n=== Clipping ===")
    max_refresh = 8
    
    for attempt in range(1, max_refresh + 1):
        print(f"\n--- Attempt {attempt}/{max_refresh} ---")
        await page.goto("https://www.kroger.com/savings/cl/coupons/", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(12000)
        
        # Close dialogs
        try: await page.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close())")
        except: pass
        
        # Click All Coupons
        try:
            all_btn = page.locator("button:has-text('All Coupons')").first
            if await all_btn.count() > 0:
                await all_btn.click(force=True, timeout=5000)
                print("✅ All Coupons clicked")
                await page.wait_for_timeout(5000)
        except: pass
        
        # Check if coupons loaded
        try:
            text = (await page.text_content("body") or "").lower()
            if "not finding any coupons" not in text:
                # Look for Clip buttons
                btns = page.locator("button:has-text('Clip')")
                if await btns.count() > 0:
                    print("✅ Coupons found!")
                    break
                if "coupons clipped" in text or "loaded savings" in text:
                    print("✅ Coupons found!")
                    break
        except: pass
        
        print("⚠️  No coupons yet, refreshing...")
        if attempt < max_refresh: await page.wait_for_timeout(3000)
    else:
        print("❌ Coupons not found after 8 refreshes")
        return 0
    
    # Scroll all coupons
    print("Scrolling to load all coupons...")
    prev = 0
    for i in range(200):
        try: await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except: break
        await page.wait_for_timeout(1500)
        try:
            h = await page.evaluate("document.body.scrollHeight")
            if h == prev: break
            prev = h
        except: break
        if i % 10 == 0: print(f"  scroll {i}")
    try: await page.evaluate("window.scrollTo(0, 0)")
    except: pass
    await page.wait_for_timeout(3000)
    
    # Find and click Clip buttons
    print("Looking for Clip buttons...")
    seen = 0
    
    # Method 1: text=Clip in all frames
    for f in [page] + page.frames:
        try:
            for btn in await f.locator("button").all():
                try:
                    txt = (await btn.text_content() or "").strip().lower()
                    if txt == "clip":
                        await btn.click(force=True, timeout=5000)
                        seen += 1
                        if seen % 5 == 0: print(f"  clipped {seen}")
                except: continue
        except: continue
    
    # Method 2: fallback selectors
    if seen == 0:
        print("Fallback selectors...")
        for sel in [
            "button[class*='clip']", "button[class*='Clip']",
            "[data-testid*='clip']", "[data-testid*='Clip']",
            "[aria-label*='Clip']",
        ]:
            try:
                els = page.locator(sel)
                n = await els.count()
                if n > 0:
                    print(f"  {sel}: {n}")
                    for i in range(n):
                        try: await els.nth(i).click(force=True, timeout=5000); seen += 1
                        except: pass
                    if seen > 0: break
            except: continue
    
    return seen

async def main():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 50)
    print("  Kroger Clipper v4 — no login")
    print("=" * 50)
    print("\n⚠️  Make sure you're logged into Kroger in this Edge profile!")
    print("   Opening browser in 3 seconds...\n")
    await asyncio.sleep(3)
    
    bp = str(BROWSER) if BROWSER else None
    if not bp:
        print("❌ Edge not found!")
        msgbox("Kroger Clipper", "Microsoft Edge not found!")
        return
    
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE, headless=False,
            executable_path=bp,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/149.0.0.0 Safari/537.36",
            locale="en-US", timezone_id="America/Detroit",
        )
        try:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
            
            # Check if logged in
            await page.goto("https://www.kroger.com/savings/cl/coupons/", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(8000)
            
            try:
                w = page.locator("[data-testid='WelcomeButtonDesktop']").first
                if await w.count() > 0:
                    btn_text = (await w.text_content()).strip().lower()
                    if btn_text in ("sign in", "sign in / register", ""):
                        print("\n❌ Not logged in!")
                        print("   Log in manually in the Edge window, then press Enter in this CMD window...")
                        input("\n   Press Enter after logging in...")
                        await page.wait_for_timeout(3000)
                    else:
                        print(f"✅ Logged in as '{btn_text}'")
            except: pass
            
            clipped = await clip_all(page)
            print(f"\n→ Clipped: {clipped} coupons")
            
            with open(STATE_FILE, "w") as f:
                json.dump({"clipped": clipped, "run": time.strftime("%Y-%m-%d %H:%M:%S")}, f)
            
            msgbox("Kroger Clipper 🛒", f"Clipped {clipped} coupons!")
        finally:
            try: await ctx.close()
            except: pass
    
    print("\nDone!")
    time.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
