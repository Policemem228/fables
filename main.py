import os
import json
import requests
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

STATE_FILE = "last_state.json"

PONS_POOL = "0x486435a1f76cd58193f854c6e6213cd05fd58d637865d02065ff558b387fa6ea"
ETH_POOL = "0xbac3aa3b91584a53a579b3c999a56756e954e59247e497bad1d25a4334bde551"


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


def sqrt_to_price(value):
    if isinstance(value, str):
        value = int(value, 16) if value.startswith("0x") else int(value)
    raw_price = (value / (2**96))**2
    # token0 uses 18 decimals and token1 uses 6 decimals in these pools.
    return raw_price * (10 ** (18 - 6))


def get_pool_hour(pool):
    now = int(datetime.now(timezone.utc).timestamp())
    now -= now % 3600

    url = f"https://www.fables.fi/api/indexer?op=hours&ids={pool}&since={now}&off=0"

    r = requests.get(url, timeout=30)
    r.raise_for_status()

    data = r.json()["data"]["PoolHour"]

    if not data:
        raise Exception("Нет данных PoolHour")

    return data[-1]


def report(name, pool, state):

    hour = get_pool_hour(pool)

    if "closeSqrtPriceX96" not in hour:
        raise ValueError("API не вернул цену закрытия текущего часа (closeSqrtPriceX96)")
    current = sqrt_to_price(hour["closeSqrtPriceX96"])

    if "lowSqrtPriceX96" in hour and "highSqrtPriceX96" in hour:
        low = sqrt_to_price(hour["lowSqrtPriceX96"])
        high = sqrt_to_price(hour["highSqrtPriceX96"])
    else:
        low = current
        high = current

    prev = state.get(name, current)
    change = (current - prev) / prev * 100 if prev else 0
    state[name] = current

    fee0 = int(hour.get("fees0", 0)) / 1e18
    fee1 = int(hour.get("fees1", 0)) / 1e6

    return f"""🟢 {name}

💵 Цена: {current:.8f}
📈 Изменение: {change:+.2f}%

🎯 Диапазон часа
⬇ {low:.8f}
⬆ {high:.8f}

💰 Комиссии часа
• token0: {fee0:.6f}
• token1: {fee1:.6f}"""


state = load_state()

text = f"📊 Fables LP Report\n{datetime.utcnow().strftime('%d.%m.%Y %H:%M UTC')}\n\n"

for name, pool in [
    ("PONS/USDG", PONS_POOL),
    ("ETH/USDG", ETH_POOL),
]:
    try:
        text += report(name, pool, state) + "\n\n"
    except Exception as e:
        text += f"❌ {name}\n{e}\n\n"

save_state(state)
send(text)
