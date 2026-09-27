
import json
import os
import time
from pathlib import Path

import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

STATE = Path("state.json")

BASE = "https://www.fables.fi/api/indexer"

PONS_POOL = "0x486435a1f76cd58193f854c6e6213cd05fd58d637865d02065ff558b387fa6ea"
ETH_POOL = "0xbac3aa3b91584a53a579b3c999a56756e954e59247e497bad1d25a4334bde551"


def tg(text):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text},
        timeout=30,
    )


def load():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {}


def save(data):
    STATE.write_text(json.dumps(data))


def get_fees():
    now = int(time.time())
    since = now - (now % 3600) - 3600

    r = requests.get(
        BASE,
        params={
            "op": "feehours",
            "ids": f"{PONS_POOL},{ETH_POOL}",
            "since": since,
            "off": 0,
        },
        timeout=30,
    )

    r.raise_for_status()
    return r.json()["data"]["PoolHour"]


def decode_price_from_sqrt(sqrt_price_x96):
    sqrt = int(sqrt_price_x96)
    price = (sqrt / 2**96) ** 2
    return price


def build():
    state = load()
    fees = get_fees()

    msg = "📊 Fables LP Report\n"
    msg += time.strftime("%d.%m.%Y %H:%M UTC", time.gmtime())
    msg += "\n\n"

    latest = {}

    for item in fees:
        latest[item["pool_id"]] = item

    pools = [
        ("PONS/USDG", PONS_POOL),
        ("ETH/USDG", ETH_POOL),
    ]

    for name, pool in pools:
        if pool not in latest:
            continue

        p = latest[pool]

        current_price = decode_price_from_sqrt(p["highSqrtPriceX96"])
        low_price = decode_price_from_sqrt(p["lowSqrtPriceX96"])

        old = state.get(name, current_price)

        diff = current_price - old
        pct = diff / old * 100 if old else 0

        emoji = "🟢" if diff >= 0 else "🔴"

        msg += (
            f"{emoji} {name}\n"
            f"Цена сейчас: {current_price:.8f}\n"
            f"Диапазон часа:\n"
            f"{low_price:.8f} → {current_price:.8f}\n"
            f"Изменение: {pct:+.2f}%\n"
            f"Комиссии:\n"
            f"• token0: {p['fees0']}\n"
            f"• token1: {p['fees1']}\n\n"
        )

        state[name] = current_price

    save(state)

    return msg


tg(build())
