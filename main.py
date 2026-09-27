
import os
import json
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
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
    # Здесь подключим Fables API после того,
    # как ты пришлёшь адрес кошелька.
    return [
        {"name": "LP #1", "value": 100},
        {"name": "LP #2", "value": 200},
    ]

state = load_state()
positions = get_positions()

changes = []

for p in positions:
    old = state.get(p["name"])
    if old is None:
        changes.append(f"🆕 {p['name']}: ${p['value']}")
    elif old != p["value"]:
        diff = p["value"] - old
        emoji = "🟢" if diff > 0 else "🔴"
        changes.append(f"{emoji} {p['name']}: {old} → {p['value']} ({diff:+.2f})")

state = {p["name"]: p["value"] for p in positions}
save_state(state)

if changes:
    send("\n".join(changes))
