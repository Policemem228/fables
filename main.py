import base64
import os
import json
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("ZERION_API_KEY")
WALLET = os.getenv("WALLET_ADDRESS")

STATE_FILE = "last_state.json"

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

def save_state(data):
    with open(STATE_FILE, "w") as f:
        json.dump(data, f)



def get_positions():
    auth = base64.b64encode(f"{API_KEY}:".encode()).decode()

    headers = {
        "Authorization": f"Basic {auth}",
        "Accept": "application/json"
    }

    url = f"https://api.zerion.io/v1/wallets/{WALLET}/positions/"

    r = requests.get(
        url,
        headers=headers,
        params={
            "currency": "usd",
            "filter[position_types]": "deposit,staked,locked"
        }
    )

    # Если кошелек еще индексируется
    if r.status_code == 202:
        raise Exception("Wallet is indexing. Run workflow again in 30–60 seconds.")

    r.raise_for_status()

    result = []

    for item in r.json()["data"]:
        attr = item["attributes"]

        result.append({
            "name": attr["name"],
            "value": round(attr["value"], 2)
        })

    return result
state = load_state()
positions = get_positions()

changes=[]

new_state={}

for p in positions:

    new_state[p["name"]] = p["value"]

    if p["name"] not in state:
        changes.append(f"🆕 {p['name']}: ${p['value']}")
    else:
        diff=p["value"]-state[p["name"]]

        if abs(diff)>=0.01:
            emoji="🟢" if diff>0 else "🔴"
            changes.append(
                f"{emoji} {p['name']}\n"
                f"{state[p['name']]} → {p['value']} USD\n"
                f"Изменение: {diff:+.2f}$"
            )

save_state(new_state)

if changes:
    send("\n\n".join(changes))
