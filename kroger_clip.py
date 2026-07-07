#!/usr/bin/env python3
"""
Kroger Coupon Clipper — Windows standalone.
Logs in, clips all coupons on www.kroger.com
"""

import asyncio, json, sys, time, ctypes
from pathlib import Path

from playwright.async_api import async_playwright

EMAIL = "lizanddima@gmail.com"
PASSWORD = "produkti2024"
ALT_ID = "F41393474808"

STATE_DIR = Path.home() / ".kroger-clipper"
STATE_FILE = STATE_DIR / "state.json"
PROFILE_DIR = str(STATE_DIR / "profile")

EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def msgbox(title, text):
    try:
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)
    except:
        pass


async def close_overlays(page):
    closed = await page.evaluate("""
        () => { let c=0;
        document.querySelectorAll('dialog[open]').forEach(d=>{d.close();c++;});
        document.querySelectorAll('.Page-overlay').forEach(o=>{o.remove();c++;});
        return c; }
    """)
    if closed:
        print(f"  Closed {closed} overlay(s)")


async def find_field(page, selector):
    """Find an element in page or any frame."""
    el = page.locator(selector).first
    for _ in range(40):
        try:
            if await el.count() > 0 and await el.is_visible():
                return el
        except:
            pass
        await page.wait_for_timeout(250)
    # Try frames
    for f in page.frames:
        try:
            el = f.locator(selector).first
            if await el.count() > 0:
                return el
        except:
            continue
    return None


async def login(page):
    print("=== Login ===")
    await page.goto("https://www.kroger.com/savings/cl/coupons/",
                    wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(10000)
    await close_overlays(page)

    # Check if already logged in
    try:
        welcome = page.locator("[data-testid='WelcomeButtonDesktop']")
        if await welcome.count() > 0:
            wtext = (await welcome.first.text_content()).strip().lower()
            if wtext not in ("sign in", "sign in / register", ""):
                print(f"  ✅ Already logged in ({wtext})")
                return True
    except:
        pass

    print("  Going to sign-in page...")
    await page.goto("https://www.kroger.com/signin",
                    wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(10000)
    await close_overlays(page)
    print(f"  URL: {page.url[:80]}")

    # Email
    inp = await find_field(page, "input[type='email']")
    if not inp:
        print("  ❌ Email field not found")
        return False
    await inp.fill(EMAIL)
    await page.wait_for_timeout(1000)
    print("  Email filled")

    # Continue
    btn = page.locator("button:has-text('Continue')").first
    if await btn.count() > 0:
        await btn.click()
        await page.wait_for_timeout(4000)
        print("  Clicked Continue")

    # Password
    pwd = await find_field(page, "input[type='password']")
    if not pwd:
        print("  ❌ Password field not found")
        return False
    await pwd.fill(PASSWORD)
    await page.wait_for_timeout(500)

    # Sign In
    sub = page.locator("button:has-text('Sign In')").first
    if await sub.count() > 0:
        await sub.click()
        await page.wait_for_timeout(10000)
        print("  Submitted login")

    await close_overlays(page)

    # Alternate ID
    for _ in range(25):
        try:
            body = (await page.text_content("body")).lower()
            if "alternate" in body:
                alt = page.locator("input#alternateId").first
                if await alt.count() > 0:
                    await alt.fill(ALT_ID)
                    await page.wait_for_timeout(500)
                    page.locator("button:has-text('Continue')").first.click()
                    await page.wait_for_timeout(3000)
                    print("  Alternate ID set")
                    break
        except:
            pass
        await page.wait_for_timeout(1000)

    await page.wait_for_timeout(5000)
    print("  ✅ Login complete")
    return True


async def clip_all(page):
    print("\n=== Clipping ===")
    await page.goto("https://www.kroger.com/savings/cl/coupons/",
                    wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(10000)
    await close_overlays(page)

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

    # Check no coupons
    try:
        body = (await page.text_content("body")).lower()
        if "not finding any coupons" in body:
            print("  📭 No coupons available")
            return 0
    except:
        pass

    # Scroll all the way down
    print("  Loading all coupons (scrolling)...")
    prev = 0
    for i in range(200):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1500)
        await close_overlays(page)
        h = await page.evaluate("document.body.scrollHeight")
        if h == prev:
            break
        prev = h
        if i % 10 == 0:
            print(f"    scroll {i}, height={h}")

    print(f"  Done scrolling. Height={prev}")

    # Scroll back to top
    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(1500)

    # Count buttons
    btns = page.locator("button:has-text('Clip')")
    total = await btns.count()
    print(f"  Found {total} Clip buttons")

    if total == 0:
        print("  No Clip buttons (maybe all clipped already)")
        return 0

    # Click them all
    clipped = 0
    print("  Clipping...")
    for i in range(total):
        try:
            b = btns.nth(i)
            text = (await b.text_content()).strip().lower()
            if text == "clip":
                await b.click(force=True, timeout=5000)
                clipped += 1
                if clipped % 10 == 0:
                    print(f"    {clipped}/{total}")
                await page.wait_for_timeout(100)
        except:
            continue

    return clipped


def find_browser():
    for p in EDGE_PATHS + CHROME_PATHS:
        if Path(p).exists():
            return p
    return None


async def main():
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 45)
    print("    🛒 Kroger Coupon Clipper")
    print("=" * 45)

    browser_path = find_browser()
    if browser_path:
        print(f"  Browser: {browser_path}")
    else:
        print("  Browser: Playwright Chromium (bundled)")

    async with async_playwright() as p:
        args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--no-default-browser-check",
            "--no-first-run",
        ]
        ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/149.0.0.0 Safari/537.36")

        if browser_path:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                headless=False,
                executable_path=browser_path,
                args=args,
                viewport={"width": 1280, "height": 900},
                user_agent=ua,
                locale="en-US", timezone_id="America/Detroit",
            )
        else:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                headless=False,
                args=args,
                viewport={"width": 1280, "height": 900},
                user_agent=ua,
            )

        page = browser.pages[0]

        # Anti-detection
        await page.add_init_script("""
            Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
            Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});
            Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});
            window.chrome={runtime:{}};
        """)

        if not await login(page):
            print("\n❌ Login failed")
            msgbox("Kroger Clipper", "❌ Login failed!")
            await browser.close()
            input("\nEnter to exit...")
            sys.exit(1)

        clipped = await clip_all(page)
        print(f"\n✨ Total clipped: {clipped}")

        st = {"last_clipped": clipped, "last_run": time.strftime("%Y-%m-%d %H:%M:%S")}
        with open(STATE_FILE, "w") as f:
            json.dump(st, f)

        msgbox("Kroger Clipper 🛒",
               f"Clipped {clipped} coupons!\n\nState saved to:\n{STATE_FILE}")

        await browser.close()

    print("\n🏁 Done!")
    time.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
