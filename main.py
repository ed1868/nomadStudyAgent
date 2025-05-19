import os
import requests
import random
import re
import json
from datetime import datetime
from dotenv import load_dotenv

# ─── ENV & CONFIG ───────────────────────────────────────────────────────────────
load_dotenv()
API_KEY     = os.getenv("AIRTABLE_API_KEY")
BASE_ID     = os.getenv("AIRTABLE_BASE_ID")
TB_KEY      = os.getenv("TEXTBELT_API_KEY", "textbelt")
WEBHOOK_URL = os.getenv("REPLY_WEBHOOK_URL")

HEADERS = {"Authorization": f"Bearer {API_KEY}"}

TABLE_IDS = {
    "users":        "tblZTtziTPLoYM2c9",   # ← your Users table ID
    "questions":    "tbliMfvRbo6DmNdN7",   # ← your Tech Questions table ID
    "sms_log":      "tbl5wP3XkAtACe72Z",  # SMS Messages (already correct)
    "user_results": "tblbgCUm7zzMhCgNR"   # User Results (already correct)
}

def endpoint_for(key):
    return f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_IDS[key]}"

# ─── HELPERS ────────────────────────────────────────────────────────────────────
def fetch_all(key):
    out, params = [], {"pageSize": 100}
    url = endpoint_for(key)
    while True:
        r = requests.get(url, headers=HEADERS, params=params)
        r.raise_for_status()
        j = r.json()
        out += j.get("records", [])
        if not j.get("offset"):
            break
        params["offset"] = j["offset"]
    return out

def create_record(key, fields):
    url = endpoint_for(key)
    r = requests.post(url, json={"fields": fields}, headers=HEADERS)
    if not r.ok:
        print(f"\n🚨 Airtable error on POST {url}: {r.status_code}")
        print(r.text)    # this is your clue to correct the field names
        r.raise_for_status()
    return r.json()

def clean_phone(raw):
    digits = re.sub(r"\D", "", raw or "")
    return digits if len(digits) >= 10 else None

def send_text(phone, body, webhook_data=None):
    payload = {"phone": phone, "message": body, "key": TB_KEY}
    if WEBHOOK_URL:
        payload["replyWebhookUrl"] = WEBHOOK_URL
    if webhook_data:
        payload["webhookData"] = json.dumps(webhook_data)[:100]
    r = requests.post("https://textbelt.com/text", data=payload)
    return r.json()

# ─── MAIN FLOW ─────────────────────────────────────────────────────────────────
def main():
    users     = fetch_all("users")
    questions = fetch_all("questions")
    if not questions:
        print("❌ No questions found—exiting.")
        return

    summary = {"sent": 0, "fail": 0, "skip": 0}

    for u in users:
        phone = clean_phone(u["fields"].get("phone"))
        if not phone:
            summary["skip"] += 1
            continue

        # 1) Pick a random question
        q_rec = random.choice(questions)
        q_id  = q_rec["id"]
        f     = q_rec["fields"]
        text  = f.get("Question", "")
        opts  = [
            f"{c}. {f.get('Option '+c)}"
            for c in ("A","B","C","D")
            if f.get("Option "+c)
        ]
        body  = text + "\n" + "\n".join(opts)

        # 2) Send SMS with webhookData
        webhook_data = {"user": u["id"], "question": q_id}
        resp         = send_text(phone, body, webhook_data)
        ok           = resp.get("success", False)
        error_msg    = resp.get("error", "")

        # 3) Log to SMS Messages
        #    👉 Replace these keys with your actual field names!
        sms_fields = {
            "From":         "PythonBot",              # e.g. your “Sender” field
            "To":           phone,                    # your “Receiver” field
            "Content":      body,                     # your “Message Content”
            "Sent At":      datetime.utcnow().isoformat(),
            "Textbelt ID":  resp.get("textId", "")
        }
        try:
            sms_rec = create_record("sms_log", sms_fields)
            sms_id  = sms_rec["id"]
        except Exception:
            sms_id = None

        # 4) Log to User Results
        #    👉 Again, swap these with the exact names in your schema!
        ur_fields = {
            "User":           [u["id"]],
            "Question":       [q_id],
            "SMS Record":     [sms_id] if sms_id else [],
            "Sent Time":      datetime.utcnow().isoformat(),
            "Status":         "Sent" if ok else "Failed",
            "Error Detail":   error_msg
        }
        try:
            create_record("user_results", ur_fields)
        except Exception:
            pass

        # 5) Tally
        if ok:
            summary["sent"] += 1
        else:
            summary["fail"] += 1
            print(f"✖️ Send to {phone} failed: {error_msg}")

    print(f"\n✅ Done. Sent={summary['sent']} Fail={summary['fail']} Skipped={summary['skip']}")

if __name__ == "__main__":
    main()
