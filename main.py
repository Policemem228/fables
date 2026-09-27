import os
import json
import math
import requests
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

STATE_FILE = "last_state.json"

POOLS = {
    "PONS/USDG": {
        "id": "0x486435a1f76cd58193f854c6e6213cd05fd58d637865d02065ff558b387fa6ea"
    },
    "ETH/USDG": {
        "id": "0xbac3aa3b91584a53a579b3c999a56756e954e59247e497bad1d25a4334bde551"
    }
}


def send(text):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": text
        },
        timeout=20
    )


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def get_json(url):
    r = requests.get(url, timeout=20)

    if r.status_code != 200:
        print("URL:", url)
        print("STATUS:", r.status_code)
        print("BODY:", r.text)
        return None

    return r.json()


def get_hour(pool):
    return get_json(
        f"https://www.fables.fi/api/indexer?op=feehours&ids={pool}"
    )


def get_day(pool):
    return get_json(
        f"https://www.fables.fi/api/indexer?op=feedays&ids={pool}"
    )


def sqrt_to_price(sqrt_x96):
    """
    Примерная цена из sqrtPriceX96
    """
    return (int(sqrt_x96) / 2**96) ** 2


state = load_state()

lines = []

lines.append("📊 Fables LP Report")
lines.append(datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC"))
lines.append("")

for name, info in POOLS.items():

    pool = info["id"]

    hour = get_hour(pool)
    day = get_day(pool)

    if hour is None:
        lines.append(f"❌ {name}")
        lines.append("Не удалось получить данные.")
        lines.append("")
        continue

    latest = hour["data"]["PoolHour"][-1]

    high = latest["highSqrtPriceX96"]
    low = latest["lowSqrtPriceX96"]

    current_price = sqrt_to_price(high)
    low_price = sqrt_to_price(low)

    old_price = state.get(pool, current_price)

    change = 0

    if old_price != 0:
        change = (current_price - old_price) / old_price * 100

    state[pool] = current_price

    arrow = "📈" if change >= 0 else "📉"

    fees0 = int(latest["fees0"])
    fees1 = int(latest["fees1"])

    lines.append("🟢 In Range")
    lines.append("")
    lines.append(name)
    lines.append(f"Цена сейчас: {current_price:.8f}")
    lines.append(f"Диапазон часа:")
    lines.append(f"{low_price:.8f} → {current_price:.8f}")
    lines.append(f"Изменение: {arrow} {change:+.2f}%")
    lines.append("")
    lines.append("Комиссии часа:")
    lines.append(f"• token0: {fees0:,}".replace(",", " "))
    lines.append(f"• token1: {fees1:,}".replace(",", " "))
    lines.append("")

save_state(state)

send("\n".join(lines))
