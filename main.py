
import asyncio
import json
import os
from pathlib import Path

import requests
from playwright.async_api import async_playwright

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

STATE = Path("state.json")
COOKIE_FILE = "cookies.json"


def tg(text):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text},
        timeout=30,
    )


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {}


def save_state(data):
    STATE.write_text(json.dumps(data))


async def read_portfolio():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context()

        if Path(COOKIE_FILE).exists():
            await context.add_cookies(json.loads(Path(COOKIE_FILE).read_text()))

        page = await context.new_page()

        await page.goto("https://www.fables.fi/portfolio", wait_until="networkidle")

        await page.wait_for_timeout(3000)

        portfolio = await page.locator("text=Portfolio value").locator("..").inner_text()

        body = await page.inner_text("body")

        await browser.close()

        return portfolio, body


def extract(body):
    lines = body.splitlines()

    result = {}

    for i, line in enumerate(lines):
        if "PONS/USDG" in line:
            result["PONS"] = lines[max(0, i-5):i+8]

        if "ETH/USDG" in line:
            result["ETH"] = lines[max(0, i-5):i+8]

    return result


async def main():
    state = load_state()

    portfolio, body = await read_portfolio()

    data = extract(body)

    msg = "📊 Fables LP Report\n\n"

    msg += portfolio + "\n\n"

    for key in ("PONS", "ETH"):
        if key in data:
            msg += f"{key}/USDG\n"
            msg += "\n".join(data[key]) + "\n\n"

    if portfolio != state.get("portfolio"):
        tg(msg)

    state["portfolio"] = portfolio

    save_state(state)


asyncio.run(main())
