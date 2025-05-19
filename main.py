
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

# ← your real tbl… IDs here
TABLE_IDS = {
    "users":        "tblZTtziTPLoYM2c9",   # ← your Users table ID
    "questions":    "tbliMfvRbo6DmNdN7",   # ← your Tech Questions table ID
    "messages":     "tbl5wP3XkAtACe72Z",  # SMS Messages (already correct)
    "user_results": "tblbgCUm7zzMhCgNR"   # User Results (already correct)
}
def endpoint_for(key):
    return f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_IDS[key]}"

def fetch_all(key):
    out, params = [], {"pageSize": 100}
    url = endpoint_for(key)
    while True:
        r = requests.get(url, headers=HEADERS, params=params)
        r.raise_for_status()
        batch = r.json().get("records", [])
        out += batch
        if not r.json().get("offset"):
            break
        params["offset"] = r.json()["offset"]
    return out

def create_record(key, fields):
    r = requests.post(endpoint_for(key), json={"fields": fields}, headers=HEADERS)
    r.raise_for_status()
    return r.json()

def clean_phone(raw):
    return re.sub(r"\D", "", raw or "")

def send_text(phone, body, webhook_data):
    payload = {
        "phone":          phone,
        "message":        body,
        "key":            TB_KEY,
        "replyWebhookUrl": WEBHOOK_URL,
        "webhookData":    json.dumps(webhook_data)
    }
    print("\n▶ Sending SMS payload:")
    print(json.dumps(payload, indent=2))
    resp = requests.post("https://textbelt.com/text", data=payload).json()
    print("  ↳ Textbelt response:", resp)
    return resp

def now_z():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def insert_user_result(user_id, question_id, sms_id, status, error_msg=""):
    fields = {
        "User":           user_id,
        "Question":       question_id,
        "Sent Time":      now_z(),
        "Delivery Status": status
    }
    if sms_id:
        fields["SMS Message"] = sms_id
    if error_msg:
        fields["Error Message"] = error_msg
    print("\n▶ Inserting User Results payload:")
    print(json.dumps(fields, indent=2))
    return create_record("user_results", fields)

def main():
    users     = fetch_all("users")
    questions = fetch_all("questions")
    for u in users:
        user_id = u["id"]
        phone   = clean_phone(u["fields"].get("phone"))
        if len(phone) < 10:
            continue

        q = random.choice(questions)
        q_id = q["id"]
        f   = q["fields"]
        body = f["Question"] + "\n" + "\n".join(
            f"{c}. {f.get('Option '+c)}"
            for c in ("A","B","C","D") if f.get("Option "+c)
        )

        # build webhookData
        correct_answer = q["fields"]["Correct Answer"]
        webhook_data = {
            "user": user_id,
            "question": q_id,
            "answer": correct_answer,
            "phone": phone
        }

        resp = send_text(phone, body, webhook_data)
        ok   = resp.get("success", False)
        sms_id = None
        if ok:
            # log message
            msg = create_record("messages", {
                "Sender":          "PythonBot",
                "Receiver":        phone,
                "Message Content": body,
                "Sending Time":    now_z(),
                "Textbelt ID":     resp.get("textId")
            })
            sms_id = msg["id"]

        insert_user_result(
            user_id=user_id,
            question_id=q_id,
            sms_id=sms_id,
            status="Sent" if ok else "Failed",
            error_msg=resp.get("error","")
        )

if __name__ == "__main__":
    main()
