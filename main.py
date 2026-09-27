
import os
import json
import time
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

STATE_FILE = "state.json"

POOL_HOURS = "0x486435a1f76cd58193f854c6e6213cd05fd58d637865d02065ff558b387fa6ea"
POOL_STABLE = "0x29bb26f93fe1bbbf81ee62671cc2a66fbf318f20e6b0757607a2fe3713651fdf"

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



def get_pool(pool_id, op):
    # Fables использует границу часа и обязательный off=0
    now = int(time.time())
    since = now - (now % 3600) - 3600

    r = requests.get(
        BASE,
        params={
            "op": op,
            "ids": pool_id,
            "since": since,
            "off": 0,
        },
        timeout=30,
    )

    # Если снова будет ошибка, выведем ответ сервера в лог GitHub
    print("URL:", r.url)
    print("STATUS:", r.status_code)
    print("BODY:", r.text[:1000])

    r.raise_for_status()

    return r.json()


def extract_value(data):
    if isinstance(data, list) and data:
        last = data[-1]

        if isinstance(last, dict):
            for k in [
                "tvl",
                "value",
                "totalValue",
                "usd",
                "amount",
            ]:
                if k in last:
                    return float(last[k])

    if isinstance(data, dict):
        for k in [
            "tvl",
            "value",
            "totalValue",
            "usd",
            "amount",
        ]:
            if k in data:
                return float(data[k])

    return None


def check(name, op, pool, state):
    value = extract_value(get_pool(pool, op))

    if value is None:
        return None

    old = state.get(name)

    state[name] = value

    if old is None:
        return f"🆕 {name}\nТекущее значение: {value:,.2f}"

    diff = value - old
    pct = diff / old * 100 if old else 0

    emoji = "🟢" if diff >= 0 else "🔴"

    return (
        f"{emoji} {name}\n"
        f"{old:,.2f} → {value:,.2f}\n"
        f"{diff:+,.2f} ({pct:+.2f}%)"
    )


state = load_state()

msgs = []

m = check("LP HOURS", "hours", POOL_HOURS, state)
if m:
    msgs.append(m)

m = check("LP STABLE", "stable", POOL_STABLE, state)
if m:
    msgs.append(m)

save_state(state)

if msgs:
    tg("📊 Fables LP Update\n\n" + "\n\n".join(msgs))
