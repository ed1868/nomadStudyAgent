# webhook_server.py

from flask import Flask, request, abort
import os
import re                       # ← add this
import hmac
import hashlib
import json
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv()
TEXTBELT_KEY        = os.getenv("TEXTBELT_API_KEY")
AIRTABLE_KEY        = os.getenv("AIRTABLE_API_KEY")
BASE_ID             = os.getenv("AIRTABLE_BASE_ID")
USER_RESULTS_TABLE  = "tblbgCUm7zzMhCgNR"
QUESTIONS_TABLE     = "tbliMfvRbo6DmNdN7"
USER_RESULTS_URL    = f"https://api.airtable.com/v0/{BASE_ID}/{USER_RESULTS_TABLE}"
QUESTIONS_URL       = f"https://api.airtable.com/v0/{BASE_ID}/{QUESTIONS_TABLE}"
HEADERS             = {
    "Authorization": f"Bearer {AIRTABLE_KEY}",
    "Content-Type":  "application/json"
}

app = Flask(__name__)

def now_z():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

@app.route("/api/webhook", methods=["POST"])
def handle_reply():
    ts         = request.headers.get("X-textbelt-timestamp","")
    sig        = request.headers.get("X-textbelt-signature","")
    raw        = request.get_data()
    payload    = request.get_json(force=True)
    reply_text = payload.get("text","").strip().upper()
    text_id    = payload.get("textId")
    data       = json.loads(payload.get("data","{}"))
    from_num   = payload.get("fromNumber")

    user_id     = data.get("user")
    question_id = data.get("question")

    print(f"\n▶ Reply from {from_num}:")
    print(f"  user_id:  {user_id}")
    print(f"  question: {question_id}")
    print(f"  answer:   {reply_text}")

    # 1) Fetch correct answer
    q_resp = requests.get(f"{QUESTIONS_URL}/{question_id}", headers=HEADERS)
    q_resp.raise_for_status()
    correct    = q_resp.json()["fields"].get("Correct Answer","").strip().upper()
    is_correct = (reply_text == correct)
    score      = 1 if is_correct else 0
    print(f"  correct? {is_correct} (expected {correct})")

    # 2) Find User Results record by User & Question
    formula    = f"AND({{User}}='{user_id}',{{Question}}='{question_id}')"
    search_url = USER_RESULTS_URL + "?filterByFormula=" + requests.utils.quote(formula)
    ur_resp    = requests.get(search_url, headers=HEADERS)
    ur_resp.raise_for_status()
    records    = ur_resp.json().get("records", [])
    if not records:
        print("  ⚠ No matching User Results record found!")
        return "No matching record", 404

    ur_id = records[0]["id"]
    print(f"  updating User Results record {ur_id}")

    # 3) Patch that record
    update_fields = {
        "fields": {
            "User Response": reply_text,
            "Response Time": now_z(),
            "Is Correct":    is_correct,
            "Score":         score
        }
    }
    requests.patch(f"{USER_RESULTS_URL}/{ur_id}", json=update_fields, headers=HEADERS).raise_for_status()
    print("  ✓ Airtable updated")

    # 4) If wrong, send “Wrong answer!” SMS
    if not is_correct and from_num:
        clean_phone = re.sub(r"\D", "", from_num)
        warn_payload = {
            "phone":   clean_phone,
            "message": "Wrong answer! 😢 Try again next time.",
            "key":     TEXTBELT_KEY
        }
        print(f"▶ Sending WRONG-ANSWER SMS to {clean_phone}")
        warn_resp = requests.post("https://textbelt.com/text", data=warn_payload).json()
        print("  ↳ Textbelt response:", warn_resp)

    return "OK", 200

if __name__ == "__main__":
    app.run(port=6000)
