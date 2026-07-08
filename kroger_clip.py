#!/usr/bin/env python3
"""Kroger Coupon Clipper v3 — работает через Azure B2C login"""

import asyncio, json, sys, time, ctypes
from pathlib import Path
from playwright.async_api import async_playwright

EMAIL = "lizanddima@gmail.com"
PASSWORD = "PASSWORD = "produkti2024"
ALT_ID = "F41393474808"

STATE_DIR = Path.home() / ".kroger-clipper"
STATE_FILE = STATE_DIR / "state.json"
PROFILE = str(STATE_DIR / "profile")

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BROWSER = Path(EDGE) if Path(EDGE).exists() else Path(CHROME) if Path(CHROME).exists() else None


def msgbox(title, text):
    try:
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)
    except:
        pass


async def find_el(page, selector):
    """Search page + all frames for an element."""
    el = page.locator(selector).first
    for _ in range(60):
        try:
            if await el.count() > 0:
                try:
                    if await el.is_visible():
                        return el
                except:
                    return el
        except:
            pass
        await page.wait_for_timeout(250)
    for f in page.frames:
        try:
            el = f.locator(selector).first
            if await el.count() > 0:
                return el
        except:
            continue
    return None


async def click_button_near(page, text_list):
    for txt in text_list:
        btn = page.locator(f"button:has-text('{txt}')").first
        if await btn.count() > 0:
            try:
                await btn.click(force=True, timeout=3000)
                return txt
            except:
                pass
        for f in page.frames:
            try:
                btn = f.locator(f"button:has-text('{txt}')").first
                if await btn.count() > 0:
                    await btn.click(force=True, timeout=3000)
                    return txt
            except:
                continue
    return None


async def login(page):
    print("\n=== Login ===")
    await page.goto("https://www.kroger.com/savings/cl/coupons/", wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(8000)

    # Already logged in?
    try:
        w = page.locator("[data-testid='WelcomeButtonDesktop']").first
        if await w.count() > 0:
            t = (await w.text_content()).strip().lower()
            if t not in ("sign in", "sign in / register", ""):
                print(f"✅ Already logged in ({t})")
                return True
    except:
        pass

    print("Navigating to signin...")
    await page.goto("https://www.kroger.com/signin", wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(8000)

    print(f"URL: {page.url[:80]}")
    print(f"Frames: {len(page.frames)}")

    # Log frame info for debugging
    for i, f in enumerate([page] + page.frames):
        try:
            fu = f.url
            if 'kroger' in fu or 'microsoft' in fu or 'login' in fu:
                snippet = await f.evaluate("document.body?.innerText?.substring(0, 100) || ''")
                print(f"  Frame {i}: {fu[:60]} -> {snippet[:80]}")
        except:
            pass

    # Email field
    print("Searching for email field...")
    email_el = await find_el(page, "input[type='email']")
    if email_el:
        print("✅ Email found")
    else:
        email_el = await find_el(page, "input[name='loginfmt']")
    if not email_el:
        email_el = await find_el(page, "input[placeholder*='Email'], input[placeholder*='email'], input#email")
    if not email_el:
        email_el = await find_el(page, "input[name='email'], input[id*='email']")

    if not email_el:
        # Last resort: take any text input that's visible
        for f in [page] + page.frames:
            try:
                inputs = await f.locator("input:not([type='hidden'])").all()
                for inp in inputs:
                    try:
                        if await inp.is_visible():
                            t = await inp.get_attribute("type")
                            if t in (None, "", "text", "email"):
                                email_el = inp
                                print(f"  Using fallback input in frame {f.url[:40]}")
                                break
                    except:
                        continue
            except:
                continue

    if email_el:
        await email_el.fill(EMAIL)
        print("Email filled")
        await page.wait_for_timeout(1000)
    else:
        print("❌ Email field not found!")
        return False

    # Continue / Next / Sign In
    clicked = await click_button_near(page, ["Continue", "Next", "Sign in", "Submit"])
    if clicked:
        print(f"Clicked '{clicked}'")
        await page.wait_for_timeout(4000)

    # Password
    print("Looking for password...")
    pwd = await find_el(page, "input[type='password']")
    if not pwd:
        pwd = await find_el(page, "input[name='passwd']")
    if not pwd:
        pwd = await find_el(page, "input[name='password'], input#password, input[id*='pass']")

    if pwd:
        await pwd.fill(PASSWORD)
        print("Password filled")
        await page.wait_for_timeout(500)
        clicked = await click_button_near(page, ["Sign In", "Sign in", "Submit", "Log in", "Continue"])
        if clicked:
            print(f"Clicked '{clicked}' for login")
            await page.wait_for_timeout(10000)
    else:
        print("❌ Password field not found!")
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
                    print("Alternate ID set")
                    break
        except:
            pass
        await page.wait_for_timeout(1000)

    await page.wait_for_timeout(5000)
    print("✅ Login complete")
    return True


async def clip_all(page):
    print("\n=== Clipping ===")
    await page.goto("https://www.kroger.com/savings/cl/coupons/", wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(8000)

    # Close overlays
    try:
        await page.evaluate("""() => {
            document.querySelectorAll('dialog[open]').forEach(d=>d.close());
            document.querySelectorAll('.Page-overlay, [class*=overlay]').forEach(o=>o.remove());
        }""")
    except:
        pass

    # All Coupons tab
    for txt in ["All Coupons", "All"]:
        try:
            btn = page.locator(f"button:has-text('{txt}')").first
            if await btn.count() > 0:
                await btn.click(force=True, timeout=5000)
                await page.wait_for_timeout(2000)
                break
        except:
            pass

    # No coupons?
    try:
        body = (await page.text_content("body")).lower()
        if "not finding any coupons" in body:
            print("No coupons available")
            return 0
    except:
        pass

    # Scroll all coupons
    print("Loading coupons (scroll)...")
    prev = 0
    for i in range(200):
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except:
            break
        await page.wait_for_timeout(1500)
        try:
            h = await page.evaluate("document.body.scrollHeight")
            if h == prev:
                break
            prev = h
        except:
            break
        if i % 10 == 0:
            print(f"  scroll {i} height={prev}")

    try:
        await page.evaluate("window.scrollTo(0, 0)")
    except:
        pass
    await page.wait_for_timeout(1500)

    btns = page.locator("button:has-text('Clip')")
    total = await btns.count()
    print(f"Found {total} Clip buttons")

    if total == 0:
        print("No Clip buttons")
        return 0

    clipped = 0
    print("Clipping...")
    for i in range(total):
        try:
            b = btns.nth(i)
            t = (await b.text_content()).strip().lower()
            if t == "clip":
                await b.click(force=True, timeout=5000)
                clipped += 1
                if clipped % 10 == 0:
                    print(f"  {clipped}/{total}")
        except:
            continue

    return clipped


async def main():
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 45)
    print("  🛒 Kroger Coupon Clipper v3")
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
                user_data_dir=PROFILE, headless=False,
                executable_path=browser_path, args=args,
                viewport={"width": 1280, "height": 900},
                user_agent=ua, locale="en-US",
                timezone_id="America/Detroit",
            )
        else:
            ctx = await p.chromium.launch_persistent_context(
                user_data_dir=PROFILE, headless=False,
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
            msgbox("Kroger Clipper", "Login failed! Check CMD window.")
            await ctx.close()
            input("\nEnter to exit...")
            sys.exit(1)

        clipped = await clip_all(page)
        print(f"\n→ Clipped: {clipped} coupons")

        st = {"clipped": clipped, "run": time.strftime("%Y-%m-%d %H:%M:%S")}
        with open(STATE_FILE, "w") as f:
            json.dump(st, f)

        msgbox("Kroger Clipper 🛒", f"Clipped {clipped} coupons!")

        await ctx.close()

    print("\nDone!")
    time.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
#!/usr/bin/env python3
"""Kroger Coupon Clipper v3 — работает через Azure B2C login"""

import asyncio, json, sys, time, ctypes
from pathlib import Path
from playwright.async_api import async_playwright

EMAIL = "lizanddima@gmail.com"
PASSWORD = ""
ALT_ID = "F41393474808"

STATE_DIR = Path.home() / ".kroger-clipper"
STATE_FILE = STATE_DIR / "state.json"
PROFILE = str(STATE_DIR / "profile")

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BROWSER = Path(EDGE) if Path(EDGE).exists() else Path(CHROME) if Path(CHROME).exists() else None


def msgbox(title, text):
    try:
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)
    except:
        pass


async def find_el(page, selector):
    """Search page + all frames for an element."""
    el = page.locator(selector).first
    for _ in range(60):
        try:
            if await el.count() > 0:
                try:
                    if await el.is_visible():
                        return el
                except:
                    return el
        except:
            pass
        await page.wait_for_timeout(250)
    for f in page.frames:
        try:
            el = f.locator(selector).first
            if await el.count() > 0:
                return el
        except:
            continue
    return None


async def click_button_near(page, text_list):
    for txt in text_list:
        btn = page.locator(f"button:has-text('{txt}')").first
        if await btn.count() > 0:
            try:
                await btn.click(force=True, timeout=3000)
                return txt
            except:
                pass
        for f in page.frames:
            try:
                btn = f.locator(f"button:has-text('{txt}')").first
                if await btn.count() > 0:
                    await btn.click(force=True, timeout=3000)
                    return txt
            except:
                continue
    return None


async def login(page):
    print("\n=== Login ===")
    await page.goto("https://www.kroger.com/savings/cl/coupons/", wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(8000)

    # Already logged in?
    try:
        w = page.locator("[data-testid='WelcomeButtonDesktop']").first
        if await w.count() > 0:
            t = (await w.text_content()).strip().lower()
            if t not in ("sign in", "sign in / register", ""):
                print(f"✅ Already logged in ({t})")
                return True
    except:
        pass

    print("Navigating to signin...")
    await page.goto("https://www.kroger.com/signin", wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(8000)

    print(f"URL: {page.url[:80]}")
    print(f"Frames: {len(page.frames)}")

    # Log frame info for debugging
    for i, f in enumerate([page] + page.frames):
        try:
            fu = f.url
            if 'kroger' in fu or 'microsoft' in fu or 'login' in fu:
                snippet = await f.evaluate("document.body?.innerText?.substring(0, 100) || ''")
                print(f"  Frame {i}: {fu[:60]} -> {snippet[:80]}")
        except:
            pass

    # Email field
    print("Searching for email field...")
    email_el = await find_el(page, "input[type='email']")
    if email_el:
        print("✅ Email found")
    else:
        email_el = await find_el(page, "input[name='loginfmt']")
    if not email_el:
        email_el = await find_el(page, "input[placeholder*='Email'], input[placeholder*='email'], input#email")
    if not email_el:
        email_el = await find_el(page, "input[name='email'], input[id*='email']")

    if not email_el:
        # Last resort: take any text input that's visible
        for f in [page] + page.frames:
            try:
                inputs = await f.locator("input:not([type='hidden'])").all()
                for inp in inputs:
                    try:
                        if await inp.is_visible():
                            t = await inp.get_attribute("type")
                            if t in (None, "", "text", "email"):
                                email_el = inp
                                print(f"  Using fallback input in frame {f.url[:40]}")
                                break
                    except:
                        continue
            except:
                continue

    if email_el:
        await email_el.fill(EMAIL)
        print("Email filled")
        await page.wait_for_timeout(1000)
    else:
        print("❌ Email field not found!")
        return False

    # Continue / Next / Sign In
    clicked = await click_button_near(page, ["Continue", "Next", "Sign in", "Submit"])
    if clicked:
        print(f"Clicked '{clicked}'")
        await page.wait_for_timeout(4000)

    # Password
    print("Looking for password...")
    pwd = await find_el(page, "input[type='password']")
    if not pwd:
        pwd = await find_el(page, "input[name='passwd']")
    if not pwd:
        pwd = await find_el(page, "input[name='password'], input#password, input[id*='pass']")

    if pwd:
        await pwd.fill(PASSWORD)
        print("Password filled")
        await page.wait_for_timeout(500)
        clicked = await click_button_near(page, ["Sign In", "Sign in", "Submit", "Log in", "Continue"])
        if clicked:
            print(f"Clicked '{clicked}' for login")
            await page.wait_for_timeout(10000)
    else:
        print("❌ Password field not found!")
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
                    print("Alternate ID set")
                    break
        except:
            pass
        await page.wait_for_timeout(1000)

    await page.wait_for_timeout(5000)
    print("✅ Login complete")
    return True


async def clip_all(page):
    print("\n=== Clipping ===")
    await page.goto("https://www.kroger.com/savings/cl/coupons/", wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(8000)

    # Close overlays
    try:
        await page.evaluate("""() => {
            document.querySelectorAll('dialog[open]').forEach(d=>d.close());
            document.querySelectorAll('.Page-overlay, [class*=overlay]').forEach(o=>o.remove());
        }""")
    except:
        pass

    # All Coupons tab
    for txt in ["All Coupons", "All"]:
        try:
            btn = page.locator(f"button:has-text('{txt}')").first
            if await btn.count() > 0:
                await btn.click(force=True, timeout=5000)
                await page.wait_for_timeout(2000)
                break
        except:
            pass

    # No coupons?
    try:
        body = (await page.text_content("body")).lower()
        if "not finding any coupons" in body:
            print("No coupons available")
            return 0
    except:
        pass

    # Scroll all coupons
    print("Loading coupons (scroll)...")
    prev = 0
    for i in range(200):
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except:
            break
        await page.wait_for_timeout(1500)
        try:
            h = await page.evaluate("document.body.scrollHeight")
            if h == prev:
                break
            prev = h
        except:
            break
        if i % 10 == 0:
            print(f"  scroll {i} height={prev}")

    try:
        await page.evaluate("window.scrollTo(0, 0)")
    except:
        pass
    await page.wait_for_timeout(1500)

    btns = page.locator("button:has-text('Clip')")
    total = await btns.count()
    print(f"Found {total} Clip buttons")

    if total == 0:
        print("No Clip buttons")
        return 0

    clipped = 0
    print("Clipping...")
    for i in range(total):
        try:
            b = btns.nth(i)
            t = (await b.text_content()).strip().lower()
            if t == "clip":
                await b.click(force=True, timeout=5000)
                clipped += 1
                if clipped % 10 == 0:
                    print(f"  {clipped}/{total}")
        except:
            continue

    return clipped


async def main():
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 45)
    print("  🛒 Kroger Coupon Clipper v3")
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
                user_data_dir=PROFILE, headless=False,
                executable_path=browser_path, args=args,
                viewport={"width": 1280, "height": 900},
                user_agent=ua, locale="en-US",
                timezone_id="America/Detroit",
            )
        else:
            ctx = await p.chromium.launch_persistent_context(
                user_data_dir=PROFILE, headless=False,
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
            msgbox("Kroger Clipper", "Login failed! Check CMD window.")
            await ctx.close()
            input("\nEnter to exit...")
            sys.exit(1)

        clipped = await clip_all(page)
        print(f"\n→ Clipped: {clipped} coupons")

        st = {"clipped": clipped, "run": time.strftime("%Y-%m-%d %H:%M:%S")}
        with open(STATE_FILE, "w") as f:
            json.dump(st, f)

        msgbox("Kroger Clipper 🛒", f"Clipped {clipped} coupons!")

        await ctx.close()

    print("\nDone!")
    time.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
