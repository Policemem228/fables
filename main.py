import os
import json
import requests
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

STATE_FILE = "last_state.json"

RPC = "https://rpc.mainnet.chain.robinhood.com"
POOL_MANAGER = "0x8366a39cc670b4001a1121b8f6a443a643e40951"
SWAP_TOPIC = "0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f"

PONS_POOL = "0x486435a1f76cd58193f854c6e6213cd05fd58d637865d02065ff558b387fa6ea"
ETH_POOL = "0xbac3aa3b91584a53a579b3c999a56756e954e59247e497bad1d25a4334bde551"

LP_RANGES = {
    "PONS/USDG": {"low": 0.4909, "high": 0.7338},
    "ETH/USDG": {"low": 2401.90, "high": 2901.56},
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


def sqrt_to_price(value):
    if isinstance(value, str):
        value = int(value, 16) if value.startswith("0x") else int(value)
    raw_price = (value / (2**96))**2
    # token0 uses 18 decimals and token1 uses 6 decimals in these pools.
    return raw_price * (10 ** (18 - 6))


def rpc_request(method, params):
    response = requests.post(
        "https://rpc.mainnet.chain.robinhood.com",
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    if "error" in body:
        error = body["error"]
        raise RuntimeError("RPC {} error {}: {}".format(method, error.get("code"), error.get("message")))
    if body.get("result") is None:
        raise ValueError("RPC {} вернул пустой результат".format(method))
    return body["result"]


def first_block_at_or_after(timestamp, latest_number, latest_timestamp):
    low = max(0, latest_number - 1_000_000)
    high = latest_number
    if latest_timestamp < timestamp:
        return latest_number + 1

    def block_timestamp(number):
        block = rpc_request("eth_getBlockByNumber", [hex(number), False])
        return int(block["timestamp"], 16)

    if block_timestamp(low) >= timestamp:
        return low
    while low + 1 < high:
        middle = (low + high) // 2
        if block_timestamp(middle) < timestamp:
            low = middle
        else:
            high = middle
    return high


def get_hour_activity(pools):
    hour_start = int(datetime.now(timezone.utc).timestamp())
    hour_start -= hour_start % 3600
    latest = rpc_request("eth_getBlockByNumber", ["latest", False])
    latest_number = int(latest["number"], 16)
    from_block = first_block_at_or_after(
        hour_start, latest_number, int(latest["timestamp"], 16)
    )
    activity = {
        pool.lower(): {"prices": [], "fees0": 0, "fees1": 0}
        for pool in pools
    }
    if from_block > latest_number:
        return activity

    for start in range(from_block, latest_number + 1, 10_000):
        end = min(start + 9_999, latest_number)
        logs = rpc_request(
            "eth_getLogs",
            [{
                "address": POOL_MANAGER,
                "fromBlock": hex(start),
                "toBlock": hex(end),
                "topics": [SWAP_TOPIC, [pool.lower() for pool in pools]],
            }],
        )
        for log in logs:
            pool = log["topics"][1].lower()
            data = log["data"][2:]
            if len(data) < 384:
                continue

            def signed_word(offset):
                value = int(data[offset:offset + 64], 16)
                return value - (1 << 256) if value >= (1 << 255) else value

            amount0 = signed_word(0)
            amount1 = signed_word(64)
            sqrt_price_x96 = int(data[128:192], 16)
            fee_pips = int(data[320:384], 16)
            activity[pool]["prices"].append(sqrt_to_price(sqrt_price_x96))
            if amount0 > 0:
                activity[pool]["fees0"] += amount0 * fee_pips // 1_000_000
            elif amount1 > 0:
                activity[pool]["fees1"] += amount1 * fee_pips // 1_000_000
    return activity


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


def report(name, pool, state, activity):

    hour = get_pool_hour(pool)

    if "closeSqrtPriceX96" not in hour:
        raise ValueError("API не вернул цену закрытия текущего часа (closeSqrtPriceX96)")
    current = sqrt_to_price(hour["closeSqrtPriceX96"])

    swaps = activity.get(pool.lower(), {})
    prices = swaps.get("prices", [])
    low_text = f"{min(prices + [current]):.8f}"
    high_text = f"{max(prices + [current]):.8f}"

    prev = state.get(name)
    change_text = f"{(current - prev) / prev * 100:+.2f}%" if prev else "нет предыдущих данных"
    state[name] = current

    lp_range = LP_RANGES[name]
    position_low = lp_range["low"]
    position_high = lp_range["high"]
    if current < position_low:
        position_status = "ниже диапазона"
    elif current > position_high:
        position_status = "выше диапазона"
    else:
        position_status = "в диапазоне"
    low_delta = (position_low / current - 1) * 100
    high_delta = (position_high / current - 1) * 100

    fee0_text = f"{swaps.get('fees0', 0) / 1e18:.6f}"
    fee1_text = f"{swaps.get('fees1', 0) / 1e6:.6f}"

    return f"""🟢 {name}

💵 Цена: {current:.8f}
📈 Изменение: {change_text}

📍 Мой LP-диапазон
⬇️ {position_low:.8f} USDG ({low_delta:+.2f}% от текущей цены)
⬆️ {position_high:.8f} USDG ({high_delta:+.2f}% от текущей цены)
Статус: {position_status}

🎯 Диапазон часа
⬇ {low_text}
⬆ {high_text}

💰 Комиссии часа
• token0: {fee0_text}
• token1: {fee1_text}"""


state = load_state()
try:
    hour_activity = get_hour_activity([PONS_POOL, ETH_POOL])
    activity_error = None
except Exception as e:
    hour_activity = {}
    activity_error = str(e)

text = f"📊 Fables LP Report\n{datetime.utcnow().strftime('%d.%m.%Y %H:%M UTC')}\n\n"

for name, pool in [
    ("PONS/USDG", PONS_POOL),
    ("ETH/USDG", ETH_POOL),
]:
    try:
        if activity_error:
            raise RuntimeError(f"Не удалось получить свопы за час: {activity_error}")
        text += report(name, pool, state, hour_activity) + "\n\n"
    except Exception as e:
        text += f"❌ {name}\n{e}\n\n"

save_state(state)
send(text)
