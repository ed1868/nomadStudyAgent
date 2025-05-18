# send_texts.py

import os
import requests
from dotenv import load_dotenv

# Load environment vars
load_dotenv()
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TEXTBELT_API_KEY = os.getenv("TEXTBELT_API_KEY", "textbelt")

# Airtable config
TABLE_NAME = "Users"
AIRTABLE_ENDPOINT = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{TABLE_NAME}"
HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_KEY}"
}

def fetch_all_users():
    """Fetch all records from Airtable Users table."""
    users = []
    params = {"pageSize": 100}
    url = AIRTABLE_ENDPOINT

    while True:
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        data = resp.json()
        users.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
        params["offset"] = offset

    return users

def send_text(phone, message):
    """Send a text via Textbelt."""
    payload = {
        "phone": phone,
        "message": message,
        "key": TEXTBELT_API_KEY
    }
    resp = requests.post("https://textbelt.com/text", data=payload)
    return resp.json()

def main():
    msg = "Hey there! This is a test message from your Python script 😉"
    users = fetch_all_users()
    print(f"Fetched {len(users)} user(s). Starting texts…")

    for rec in users:
        fields = rec.get("fields", {})
        phone = fields.get("Phone")
        if not phone:
            print(f"Record {rec['id']} has no phone – skipping.")
            continue

        result = send_text(phone, msg)
        status = "OK" if result.get("success") else "FAIL"
        print(f"To {phone}: {status} – {result.get('error', 'sent!')}")

if __name__ == "__main__":
    main()
