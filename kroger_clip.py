#!/usr/bin/env python3
"""Kroger Coupon Clipper v3.2 — полный фикс"""

import asyncio, json, sys, time, ctypes
from pathlib import Path
from playwright.async_api import async_playwright

EMAIL = "lizanddima@gmail.com"
PASSWORD = "***"
ALT_ID = "F41393474808"

STATE_DIR = Path.home() / ".kroger-clipper"
STATE_FILE = STATE_DIR / "state.json"
PROFILE = str(STATE_DIR / "profile")

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BROWSER = Path(EDGE) if Path(EDGE).exists() else Path(CHROME) if Path(CHROME).exists() else None

def msgbox(t, x):
    try: ctypes.windll.user32.MessageBoxW(0, x, t, 0x40)
    except: pass

async def find_el(p, sel):
    el = p.locator(sel).first
    for _ in range(60):
        try:
            if await el.count() > 0:
                try:
                    if await el.is_visible(): return el
                except: return el
        except: pass
        await p.wait_for_timeout(250)
    for f in p.frames:
        try:
            el = f.locator(sel).first
            if await el.count() > 0: return el
        except: continue
    return None

async def click_text(p, texts):
    for t in texts:
        b = p.locator(f"button:has-text('{t}')").first
        if await b.count() > 0:
            try:
                await b.click(force=True, timeout=3000)
                return t
            except: pass
        for f in p.frames:
            try:
                b = f.locator(f"button:has-text('{t}')").first
                if await b.count() > 0:
                    await b.click(force=True, timeout=3000)
                    return t
            except: continue
    return None

async def login(page):
    print("\n=== Login ===")
    await page.goto("https://www.kroger.com/savings/cl/coupons/", wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(8000)
    try:
        w = page.locator("[data-testid='WelcomeButtonDesktop']").first
        if await w.count() > 0:
            t = (await w.text_content()).strip().lower()
            if t not in ("sign in", "sign in / register", ""):
                print(f"✅ Already logged in ({t})")
                return True
    except: pass
    print("Navigating to signin...")
    await page.goto("https://www.kroger.com/signin", wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(8000)
    # email
    email_el = await find_el(page, "input[type='email']")
    if not email_el: email_el = await find_el(page, "input[name='loginfmt']")
    if not email_el: email_el = await find_el(page, "input#email")
    if not email_el:
        for f in [page] + page.frames:
            try:
                for inp in await f.locator("input:not([type='hidden'])").all():
                    try:
                        if await inp.is_visible():
                            t = await inp.get_attribute("type")
                            if t in (None, "", "text", "email"): email_el = inp; break
                    except: continue
            except: continue
    if email_el:
        await email_el.fill(EMAIL); await page.wait_for_timeout(1000); print("✅ Email filled")
    else: print("❌ Email not found"); return False
    await click_text(page, ["Continue", "Next", "Sign in", "Submit"])
    await page.wait_for_timeout(3000)
    # password
    pwd = await find_el(page, "input[type='password']")
    if not pwd: pwd = await find_el(page, "input[name='passwd']")
    if pwd:
        await pwd.fill(PASSWORD); await page.wait_for_timeout(500)
        await click_text(page, ["Sign In", "Sign in", "Submit", "Log in", "Continue"])
        await page.wait_for_timeout(10000)
    else: print("❌ Password not found"); return False
    # Alternate ID
    for _ in range(25):
        try:
            body = (await page.text_content("body")).lower()
            if "alternate" in body:
                alt = page.locator("input#alternateId").first
                if await alt.count() > 0:
                    await alt.fill(ALT_ID); await page.wait_for_timeout(500)
                    await click_text(page, ["Continue", "Submit"]); await page.wait_for_timeout(3000)
                    print("✅ Alt ID set"); break
        except: pass
        await page.wait_for_timeout(1000)
    await page.wait_for_timeout(5000)
    print("✅ Login complete")
    return True

async def clip_all(page):
    print("\n=== Clipping ===")
    await page.goto("https://www.kroger.com/savings/cl/coupons/", wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(15000)  # ждём полную загрузку после логина

    # Click "All Coupons"
    print("Clicking 'All Coupons'...")
    try:
        all_btn = page.locator("button:has-text('All Coupons')").first
        if await all_btn.count() > 0:
            await all_btn.click(force=True, timeout=5000)
            print("✅ All Coupons clicked")
            await page.wait_for_timeout(5000)
    except: pass

    # Закрываем возможные диалоги
    try:
        await page.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close())")
    except: pass

    # Долгая прокрутка
    print("Scrolling...")
    prev = 0
    for i in range(200):
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except: break
        await page.wait_for_timeout(1500)
        try:
            h = await page.evaluate("document.body.scrollHeight")
            if h == prev: break
            prev = h
        except: break
        if i % 10 == 0: print(f"  scroll {i}")

    try:
        await page.evaluate("window.scrollTo(0, 0)")
    except: pass
    await page.wait_for_timeout(3000)

    # POISK CLIP — перебираем все button во всех фреймах по тексту
    print("Looking for Clip buttons...")
    seen = 0
    for f in [page] + page.frames:
        try:
            all_btns = await f.locator("button").all()
            for btn in all_btns:
                try:
                    txt = (await btn.text_content() or "").strip().lower()
                    if txt == "clip":
                        await btn.click(force=True, timeout=5000)
                        seen += 1
                        if seen % 5 == 0:
                            print(f"  clipped {seen}")
                except:
                    continue
        except:
            continue

    if seen == 0:
        # Fallback: ищем aria-label, class, data-testid
        print("Fallback: trying alternative selectors...")
        for sel in [
            "button[class*='clip']",
            "button[class*='Clip']",
            "[data-testid*='clip']",
            "[aria-label*='Clip']",
            "button div:has-text('Clip')",
        ]:
            try:
                els = page.locator(sel)
                n = await els.count()
                if n > 0:
                    print(f"  {sel}: {n}")
                    for i in range(n):
                        try:
                            await els.nth(i).click(force=True, timeout=5000)
                            seen += 1
                            if seen % 5 == 0: print(f"  clipped {seen}")
                        except: pass
                    if seen > 0: break
            except: continue

    return seen

async def main():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    print("="*45)
    print("  Kroger Clipper v3.2")
    print("="*45)
    bp = str(BROWSER) if BROWSER else None
    async with async_playwright() as p:
        args = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/149.0.0.0 Safari/537.36"
        if bp:
            ctx = await p.chromium.launch_persistent_context(
                user_data_dir=PROFILE, headless=False, executable_path=bp, args=args,
                viewport={"width": 1280, "height": 900}, user_agent=ua, locale="en-US", timezone_id="America/Detroit")
        else:
            ctx = await p.chromium.launch_persistent_context(
                user_data_dir=PROFILE, headless=False, args=args, viewport={"width": 1280, "height": 900}, user_agent=ua)
        try:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
            if not await login(page):
                print("\n❌ Login failed")
                msgbox("Kroger Clipper", "Login failed!")
                return
            clipped = await clip_all(page)
            print(f"\n→ Clipped: {clipped}")
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
