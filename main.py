import os
import json
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
        json={"chat_id": CHAT_ID, "text": text},
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
        print(f"Ошибка {r.status_code}: {url}")
        print(r.text)
        return None

    return r.json()


def sqrt_to_price(v):
    return (int(v) / 2**96) ** 2


state = load_state()

msg = []
msg.append("📊 Fables LP Report")
msg.append(datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC"))
msg.append("")

for name, info in POOLS.items():

    pool = info["id"]

    hour = get_json(
        f"https://www.fables.fi/api/indexer?op=hours&ids={pool}"
    )

    if hour is None:
        msg.append(f"❌ {name}")
        msg.append("Не удалось получить данные.\n")
        continue

    data = hour["data"]["PoolHour"]

    latest = data[-1]
    prev = data[-2] if len(data) > 1 else latest

    high = sqrt_to_price(latest["highSqrtPriceX96"])
    low = sqrt_to_price(latest["lowSqrtPriceX96"])

    prev_price = sqrt_to_price(prev["highSqrtPriceX96"])

    change = 0
    if prev_price:
        change = (high - prev_price) / prev_price * 100

    fees0 = int(latest["fees0"])
    fees1 = int(latest["fees1"])

    arrow = "📈" if change >= 0 else "📉"

    msg.append("🟢 In Range")
    msg.append("")
    msg.append(name)
    msg.append(f"Цена сейчас: {high:.8f}")
    msg.append(f"Диапазон часа:")
    msg.append(f"{low:.8f} → {high:.8f}")
    msg.append(f"Изменение: {arrow} {change:+.2f}%")
    msg.append("")
    msg.append("Комиссии часа:")
    msg.append(f"• token0: {fees0:,}".replace(',', ' '))
    msg.append(f"• token1: {fees1:,}".replace(',', ' '))
    msg.append("")

    state[pool] = high

save_state(state)

send("\n".join(msg))
