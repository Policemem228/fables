import os
import json
import requests
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

STATE_FILE = "last_state.json"

POOLS = {
    "PONS/USDG": {
        "id": "0x486435a1f76cd58193f854c6e6213cd05fd58d637865d02065ff558b387fa6ea",
    },
    "ETH/USDG": {
        "id": "0xbac3aa3b91584a53a579b3c999a56756e954e59247e497bad1d25a4334bde551",
    }
}


def send(text):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text}
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
    r.raise_for_status()
    return r.json()


def get_mark(pool):
    return get_json(
        f"https://www.fables.fi/api/indexer?op=marks&ids={pool}"
    )


def get_hour(pool):
    return get_json(
        f"https://www.fables.fi/api/indexer?op=feehours&ids={pool}"
    )


def get_day(pool):
    return get_json(
        f"https://www.fables.fi/api/indexer?op=feedays&ids={pool}"
    )


state = load_state()
report = []

now = datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC")
report.append(f"📊 Fables LP Report\n{now}\n")

for name, info in POOLS.items():

    pool = info["id"]

    mark = get_mark(pool)
    hour = get_hour(pool)
    day = get_day(pool)

    price = float(mark["data"]["Pool"][0]["usd0"])

    prev = state.get(pool, price)
    change = (price - prev) / prev * 100 if prev else 0

    state[pool] = price

    h = hour["data"]["PoolHour"][-1]

    low = h["lowSqrtPriceX96"]
    high = h["highSqrtPriceX96"]

    fees0 = int(h["fees0"])
    fees1 = int(h["fees1"])

    status = "🟢 In Range"

    arrow = "📈" if change >= 0 else "📉"

    report.append(
f"""{status}

{name}
Цена сейчас: {price:.8f}
Изменение за час: {arrow} {change:+.2f}%

Комиссии часа:
• token0: {fees0}
• token1: {fees1}

Диапазон часа (sqrt):
{low}
→
{high}
""")

save_state(state)
send("\n".join(report))
