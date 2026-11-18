
import os
import json
import time
import urllib.request
import urllib.error

# =========================
# Configuration
# =========================

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID_RAW = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is missing")

if not CHAT_ID_RAW:
    raise ValueError("TELEGRAM_CHAT_ID is empty")

if not CHAT_ID_RAW.lstrip("-").isdigit():
    raise ValueError("TELEGRAM_CHAT_ID must be a number")

if not GEMINI_KEY:
    raise ValueError("GEMINI_API_KEY is missing")

CHAT_ID = int(CHAT_ID_RAW)

TELEGRAM = f"https://api.telegram.org/bot{TOKEN}"
GEMINI = "https://generativelanguage.googleapis.com/v1beta/interactions"
MODEL = "gemini-3.8-flash"

# Conversation state
previous_interaction_id = None
offset = 0


# =========================
# Telegram API
# =========================

def telegram(method, data=None):
    payload = json.dumps(data or {}).encode("utf-8")

    req = urllib.request.Request(
        f"{TELEGRAM}/{method}",
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=40) as response:
        result = json.loads(response.read().decode("utf-8"))

    if not result.get("ok"):
        raise RuntimeError("Telegram API returned an error")

    return result


# =========================
# Gemini API
# =========================

def ask_gemini(message):
    global previous_interaction_id

    body = {
        "model": MODEL,
        "input": message
    }

    if previous_interaction_id:
        body["previous_interaction_id"] = previous_interaction_id

    req = urllib.request.Request(
        GEMINI,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_KEY
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Gemini HTTP {e.code}: {error_body[:1500]}"
        )

    if result.get("status") == "failed":
        raise RuntimeError("Gemini interaction failed")

    answer_parts = []

    for step in result.get("steps", []):
        if step.get("type") == "model_output":
            for part in step.get("content", []):
                if part.get("type") == "text":
                    answer_parts.append(part.get("text", ""))

    answer = "\n".join(
        part for part in answer_parts if part
    ).strip()

    if not answer:
        raise RuntimeError("Gemini returned no text response")

    new_id = result.get("id")

    if not new_id:
        raise RuntimeError("Gemini did not return an interaction ID")

    previous_interaction_id = new_id

    return answer


# =========================
# Send Telegram Messages
# =========================

def send_message(chat_id, message):
    if not message:
        return

    for i in range(0, len(message), 4000):
        telegram("sendMessage", {
            "chat_id": chat_id,
            "text": message[i:i + 4000]
        })


# =========================
# Start Bot
# =========================

print("Telegram Gemini Bot is starting...")

telegram("getMe")
print("Telegram connection successful")

print("Gemini model:", MODEL)
print("Bot is ready")


# =========================
# Main Loop
# =========================

while True:
    try:
        result = telegram("getUpdates", {
            "offset": offset,
            "timeout": 30,
            "allowed_updates": ["message"]
        })

        for update in result.get("result", []):

            offset = update["update_id"] + 1

            msg = update.get("message", {})
            chat = msg.get("chat", {})
            sender = msg.get("from", {})

            # Only authorized private account
            if (
                chat.get("type") != "private"
                or chat.get("id") != CHAT_ID
                or sender.get("id") != CHAT_ID
            ):
                continue

            message = msg.get("text", "").strip()

            if not message:
                continue

            if message == "/start":
                send_message(
                    CHAT_ID,
                    "أهلاً بك! أنا مساعدك الشخصي المدعوم بـ Gemini 3.8 Flash 🤖"
                )
                continue

            if message == "/clear":
                previous_interaction_id = None

                send_message(
                    CHAT_ID,
                    "تم مسح سياق المحادثة. نبدأ من جديد! 🧹"
                )
                continue

            try:
                send_message(CHAT_ID, ask_gemini(message))

            except Exception as e:
                print("Gemini error:", str(e))

                send_message(
                    CHAT_ID,
                    "حصل خطأ أثناء الاتصال بـ Gemini. حاول مرة أخرى."
                )

    except Exception as e:
        print("Connection error:", str(e))
        time.sleep(5)
