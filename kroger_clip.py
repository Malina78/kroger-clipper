#!/usr/bin/env python3
"""Kroger Diag v3"""

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

def msgbox(t, x):
    try: ctypes.windll.user32.MessageBoxW(0, x, t, 0x40)
    except: pass

async def diagnose(page):
    print("\n"+"="*60)
    print("DIAGNOSTICS")
    print("="*60)
    print(f"Title: {await page.title()}")
    print(f"URL: {page.url[:100]}")
    body = (await page.text_content("body") or "")[:2000]
    print(f"\nBody text (2k chars):\n{body}")
    print(f"\nFrames: {len(page.frames)}")
    for i,f in enumerate(page.frames):
        try:
            t = (await f.text_content("body") or "")[:300]
            if t.strip(): print(f"  F{i}: {f.url[:60]} -> {t[:150]}")
        except: pass
    print("\nAll <button> (main, first 30):")
    btns=page.locator("button"); n=await btns.count()
    for i in range(min(n,30)):
        try:
            t=(await btns.nth(i).text_content() or "").strip()[:60]
            v=await btns.nth(i).is_visible()
            print(f"  [{i}] vis={v} '{t}'")
        except: pass
    print("\n'Clip' in all frames:")
    for i,f in enumerate(page.frames):
        try:
            for j in range(await f.locator("button").count()):
                t=(await f.locator("button").nth(j).text_content() or "").strip()
                if "clip" in t.lower(): print(f"  F{i} btn{j}: '{t}'")
        except: pass
    print("\n[data-testid] elements:")
    try:
        for el in await page.locator("[data-testid]").all():
            t=(await el.text_content() or "").strip()[:40]
            tid=await el.get_attribute("data-testid")
            if any(w in (t.lower()) for w in ["clip","coupon","load","save"]):
                print(f"  {tid}: '{t}'")
    except: pass
    print("="*60)

async def main():
    print("="*45+"\n  Kroger Diag v3\n"+"="*45)
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE, headless=False,
            executable_path=EDGE, args=["--no-sandbox","--disable-blink-features=AutomationControlled"],
            viewport={"w":1280,"h":900}, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/149.0.0.0",
            locale="en-US", timezone_id="America/Detroit")
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        await page.goto("https://www.kroger.com/savings/cl/coupons/", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(20000)
        await diagnose(page)
        input("\nPress Enter to close...")
        await ctx.close()
    print("Done!")
if __name__=="__main__": asyncio.run(main())
