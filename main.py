
import os
import json
import time
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

STATE_FILE = "state.json"

POOL_ID = "0x486435a1f76cd58193f854c6e6213cd05fd58d637865d02065ff558b387fa6ea"

BASE = "https://www.fables.fi/api/indexer"


def tg(text):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text},
        timeout=30,
    )


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def get_price():
    now = int(time.time())
    since = now - (now % 3600) - 3600

    r = requests.get(
        BASE,
        params={
            "op": "hours",
            "ids": POOL_ID,
            "since": since,
            "off": 0,
        },
        timeout=30,
    )

    r.raise_for_status()

    data = r.json()["data"]["PoolHour"]

    latest = data[-1]

    return float(latest["usd1Close"])


state = load_state()

price = get_price()

old = state.get("price")

state["price"] = price

save_state(state)

if old is None:
    tg(
        f"📊 Fables Monitor запущен\n\n"
        f"Текущее значение LP: {price:.8f}"
    )
else:
    diff = price - old
    pct = diff / old * 100

    emoji = "🟢" if diff >= 0 else "🔴"

    tg(
        f"{emoji} LP Update\n\n"
        f"{old:.8f} → {price:.8f}\n"
        f"{diff:+.8f} ({pct:+.2f}%)"
    )
