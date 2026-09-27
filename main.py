import os
import json
import math
import requests
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

RPC = "https://rpc.mainnet.chain.robinhood.com"

STATE_FILE = "last_state.json"

PONS_POOL = "0x486435a1f76cd58193f854c6e6213cd05fd58d637865d02065ff558b387fa6ea"
ETH_POOL = "0xbac3aa3b91584a53a579b3c999a56756e954e59247e497bad1d25a4334bde551"

PONS_CALL = "0xf7b7da000000000000000000000000000000000000000000000000000000000000000040000000000000000000000000000000000000000000000000000000000046b62df00000000000000000000000000000000000000000000000000000000018dcdfb000000000000000000000000000000000000000000000000000000006ab95dad0000000000000000000000000000000000000000000000000000000000000001000000000000000000000000503b3082e7e03b31fe2d223bb6c8a81b39868c600000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000bb1c293b15045"

ETH_CALL = "0xf7b7da000000000000000000000000000000000000000000000000000000000000000040000000000000000000000000000000000000000000000000000000000046b62df00000000000000000000000000000000000000000000000000000000018dcdfb000000000000000000000000000000000000000000000000000000006ab95dad000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000020000000000000000000000000b9972ca7188e511174947e3936a5315ac7073277"


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


def rpc_call(data):
    payload = [{
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{
            "to": "0xE44c0BAb43BdD47e7Ab40236bC183dCc77A9ED6c",
            "data": data
        }, "latest"]
    }]
    r = requests.post(RPC, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()[0]["result"]


def sqrt_to_price(x):
    return (int(x,16)/(2**96))**2


def pool_hour(pool):
    now = int(datetime.now(timezone.utc).timestamp())
    now = now - now % 3600
    url = f"https://www.fables.fi/api/indexer?op=hours&ids={pool}&since={now}&off=0"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()["data"]["PoolHour"][-1]


def report(name,pool,call,state):

    p = pool_hour(pool)

    low = sqrt_to_price(hex(int(p["lowSqrtPriceX96"])) )
    high = sqrt_to_price(hex(int(p["highSqrtPriceX96"])) )

    current = sqrt_to_price(rpc_call(call)[130:194])

    prev = state.get(name,current)
    change = (current-prev)/prev*100 if prev else 0
    state[name]=current

    return f"""🟢 {name}

Цена: {current:.8f}
Изменение: {change:+.2f}%

Диапазон:
{low:.8f}
⬇
{high:.8f}

Комиссии часа:
token0 {int(p["fees0"])/1e18:.6f}
token1 {int(p["fees1"])/1e6:.6f}"""


state=load_state()

text=f"📊 Fables LP Report\n{datetime.utcnow().strftime('%d.%m.%Y %H:%M UTC')}\n\n"

for n,p,c in [
    ("PONS/USDG",PONS_POOL,PONS_CALL),
    ("ETH/USDG",ETH_POOL,ETH_CALL)
]:
    try:
        text+=report(n,p,c,state)+"\n\n"
    except Exception as e:
        text+=f"❌ {n}\n{e}\n\n"

save_state(state)
send(text)
