#!/usr/bin/env python3
"""Kroger Coupon Clipper v2 — работает через Azure B2C login"""

import asyncio, json, sys, time, ctypes
from pathlib import Path
from playwright.async_api import async_playwright

EMAIL = "lizanddima@gmail.com"
PASSWORD = "produkti2024"
ALT_ID = "F41393474808"

STATE_DIR = Path.home() / ".kroger-clipper"
STATE_FILE = STATE_DIR / "state.json"
SCRIPT_DIR = Path(__file__).parent

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BROWSER = Path(EDGE) if Path(EDGE).exists() else Path(CHROME) if Path(CHROME).exists() else None


def msgbox(title, text):
    try:
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)
    except:
        pass


def dlog(page, msg):
    """Print with page URL"""
    url = page.url[:100] if page else "?"
    print(f"  [{url}] {msg}")


async def wait_visible(page, selector, timeout=10):
    """Wait up to `timeout` seconds for element to be visible. Return locator or None."""
    el = page.locator(selector).first
    for _ in range(timeout * 4):
        try:
            if await el.count() > 0 and await el.is_visible():
                return el
        except:
            pass
        await page.wait_for_timeout(250)
    return None


async def find_in_all_frames(page, selector):
    """Search page + all frames for a visible element."""
    for f in [page] + page.frames:
        try:
            el = f.locator(selector).first
            if await el.count() > 0:
                vis = False
                try:
                    vis = await el.is_visible()
                except:
                    vis = True
                if vis:
                    return el, f
        except:
            continue
    return None, None


async def login(page):
    dlog(page, "Navigating to coupons page...")
    await page.goto("https://www.kroger.com/savings/cl/coupons/",
                    wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(8000)

    # Check if already logged in
    try:
        welcome = page.locator("[data-testid='WelcomeButtonDesktop']").first
        if await welcome.count() > 0:
            wtext = (await welcome.text_content()).strip().lower()
            if wtext not in ("sign in", "sign in / register", ""):
                dlog(page, f"Already logged in ({wtext})")
                return True
    except:
        pass

    dlog(page, "Navigating to signin...")
    await page.goto("https://www.kroger.com/signin",
                    wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(10000)

    # Debug: list all frames and forms
    for i, f in enumerate([page] + page.frames):
        try:
            html = await f.evaluate("document.body?.innerHTML?.substring(0, 200) || ''")
            if html:
                dlog(page, f"Frame {i}: {html[:100]}")
        except:
            pass

    # Try multiple selectors for email
    for sel in [
        "input[type='email']",
        "input[name='email']",
        "input#email",
        "input[placeholder*='Email']",
        "input[placeholder*='email']",
        "input[placeholder*='Phone']",
        "input[name='loginfmt']",  # Microsoft login
        "input[name='passwd']",    # Microsoft password
    ]:
        el, f = await find_in_all_frames(page, sel)
        if el:
            fname = f.url[:50] if f != page else "main"
            dlog(page, f"Found '{sel}' in frame {fname}")
            # Type email
            await el.fill(EMAIL)
            await page.wait_for_timeout(1000)

            # Look for Continue / Next / Sign In button near it
            for btntxt in ["Continue", "Next", "Sign In", "Submit"]:
                for f2 in [page] + page.frames:
                    try:
                        btn = f2.locator(f"button:has-text('{btntxt}')").first
                        if await btn.count() > 0 and await btn.is_visible():
                            await btn.click()
                            dlog(page, f"Clicked '{btntxt}'")
                            await page.wait_for_timeout(3000)
                            break
                    except:
                        continue
                else:
                    continue
                break
            break
    else:
        dlog(page, "❌ NO email field found in any frame")
        return False

    # Wait for password field
    dlog(page, "Looking for password field...")
    await page.wait_for_timeout(3000)
    pwd = None
    for sel in [
        "input[type='password']", "input[name='passwd']", "input#password",
        "input[name='Password']", "input[placeholder*='Password']",
    ]:
        el, f = await find_in_all_frames(page, sel)
        if el:
            pwd = el
            await pwd.fill(PASSWORD)
            dlog(page, "Password filled")
            await page.wait_for_timeout(500)

            # Find Sign In / Submit
            for btntxt in ["Sign In", "Submit", "Log in", "Continue"]:
                for f2 in [page] + page.frames:
                    try:
                        btn = f2.locator(f"button:has-text('{btntxt}')").first
                        if await btn.count() > 0 and await btn.is_visible():
                            await btn.click()
                            dlog(page, f"Clicked '{btntxt}' for password")
                            await page.wait_for_timeout(8000)
                            break
                    except:
                        continue
                else:
                    continue
                break
            break

    if pwd is None:
        dlog(page, "❌ NO password field found")
        return False

    # Alternate ID screen
    for _ in range(25):
        try:
            body = (await page.text_content("body")).lower()
            if "alternate" in body:
                alt = page.locator("input#alternateId").first
                if await alt.count() > 0:
                    await alt.fill(ALT_ID)
                    await page.wait_for_timeout(500)
                    await page.locator("button:has-text('Continue')").first.click()
                    await page.wait_for_timeout(3000)
                    dlog(page, "Alternate ID done")
                    break
        except:
            pass
        await page.wait_for_timeout(1000)

    await page.wait_for_timeout(5000)
    dlog(page, "✅ Login complete")
    return True


async def clip_all(page):
    dlog(page, "Going to coupons page...")
    await page.goto("https://www.kroger.com/savings/cl/coupons/",
                    wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(10000)

    # Close overlays
    closed = await page.evaluate("""
        document.querySelectorAll('dialog[open]').forEach(d=>d.close());
        document.querySelectorAll('.Page-overlay').forEach(o=>o.remove());
    """)

    # All Coupons tab
    for txt in ["All Coupons", "All"]:
        btn = page.locator(f"button:has-text('{txt}')").first
        if await btn.count() > 0:
            try:
                await btn.click(force=True, timeout=5000)
                await page.wait_for_timeout(2000)
                break
            except:
                continue

    # Check if no coupons
    try:
        body = await page.text_content("body")
        b = body.lower() if body else ""
        if "not finding any coupons" in b:
            print("  No coupons available")
            return 0
    except:
        pass

    # Scroll
    print("  Loading coupons via scroll...")
    prev = 0
    for i in range(200):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1500)
        h = await page.evaluate("document.body.scrollHeight")
        if h == prev:
            break
        prev = h
        if i % 10 == 0:
            print(f"    scroll {i} height={h}")

    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(1500)

    btns = page.locator("button:has-text('Clip')")
    total = await btns.count()
    print(f"  Found {total} Clip buttons")

    if total == 0:
        print("  No Clip buttons")
        return 0

    clipped = 0
    for i in range(total):
        try:
            b = btns.nth(i)
            t = (await b.text_content()).strip().lower()
            if t == "clip":
                await b.click(force=True, timeout=5000)
                clipped += 1
                if clipped % 10 == 0:
                    print(f"    clipped {clipped}/{total}")
                await page.wait_for_timeout(100)
        except:
            continue

    return clipped


async def main():
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 45)
    print("    🛒 Kroger Coupon Clipper v2")
    print("=" * 45)

    browser_path = str(BROWSER) if BROWSER else None
    if browser_path:
        print(f"  Browser: {browser_path}")
    else:
        print("  Browser: Playwright Chromium bundled")

    async with async_playwright() as p:
        args = [
            "--no-sandbox", "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
        ]
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/149.0.0.0 Safari/537.36"

        if browser_path:
            ctx = await p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR, headless=False,
                executable_path=browser_path, args=args,
                viewport={"width": 1280, "height": 900},
                user_agent=ua, locale="en-US",
                timezone_id="America/Detroit",
            )
        else:
            ctx = await p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR, headless=False,
                args=args, viewport={"width": 1280, "height": 900},
                user_agent=ua,
            )

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # Anti-detection
        await page.add_init_script("""
            Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
            Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});
            Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});
            window.chrome = { runtime: {} };
        """)

        if not await login(page):
            print("\n❌ Login failed")
            msgbox("Kroger Clipper", "Login failed! Check CMD window for details.")
            await ctx.close()
            input("\nPress Enter to exit...")
            sys.exit(1)

        clipped = await clip_all(page)
        print(f"\n→ Clipped: {clipped} coupons")

        st = {"clipped": clipped, "run": time.strftime("%Y-%m-%d %H:%M:%S")}
        with open(STATE_FILE, "w") as f:
            json.dump(st, f)

        msgbox("Kroger Clipper", f"Clipped {clipped} coupons!")

        await ctx.close()

    print("\nDone!")
    time.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
