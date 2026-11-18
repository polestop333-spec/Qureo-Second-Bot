
import os
import json
import time
import urllib.request
import urllib.error

# =====================================
# CONFIGURATION
# =====================================

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID_RAW = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

MODEL = "gemini-3.8-flash"

TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN}"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"

# =====================================
# CHECK SETTINGS
# =====================================

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is missing")

if not CHAT_ID_RAW:
    raise ValueError("TELEGRAM_CHAT_ID is missing")

if not CHAT_ID_RAW.lstrip("-").isdigit():
    raise ValueError("TELEGRAM_CHAT_ID must be numeric")

if not GEMINI_KEY:
    raise ValueError("GEMINI_API_KEY is missing")

CHAT_ID = int(CHAT_ID_RAW)

# =====================================
# CONVERSATION MEMORY
# =====================================

previous_interaction_id = None
offset = 0

# =====================================
# TELEGRAM REQUEST
# =====================================

def telegram(method, data=None):

    payload = json.dumps(data or {}).encode("utf-8")

    request = urllib.request.Request(
        f"{TELEGRAM_URL}/{method}",
        data=payload,
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            request, timeout=45
        ) as response:

            result = json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:

        details = error.read().decode(
            "utf-8", errors="replace"
        )

        raise RuntimeError(
            f"Telegram HTTP {error.code}: {details[:1000]}"
        )

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram error: {result}"
        )

    return result


# =====================================
# GEMINI REQUEST
# =====================================

def ask_gemini(message):

    global previous_interaction_id

    body = {
        "model": MODEL,
        "input": message
    }

    if previous_interaction_id:
        body["previous_interaction_id"] = (
            previous_interaction_id
        )

    request = urllib.request.Request(
        GEMINI_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_KEY
        },
        method="POST"
    )

    try:

        with urllib.request.urlopen(
            request, timeout=120
        ) as response:

            result = json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:

        details = error.read().decode(
            "utf-8", errors="replace"
        )

        raise RuntimeError(
            f"Gemini HTTP {error.code}: {details[:2000]}"
        )

    if result.get("status") == "failed":

        raise RuntimeError(
            f"Gemini interaction failed: {result}"
        )

    answer_parts = []

    for step in result.get("steps", []):

        if step.get("type") == "model_output":

            for part in step.get("content", []):

                if part.get("type") == "text":

                    text = part.get("text", "")

                    if text:
                        answer_parts.append(text)

    answer = "\n".join(answer_parts).strip()

    if not answer:

        raise RuntimeError(
            f"Gemini returned no text: {result}"
        )

    interaction_id = result.get("id")

    if not interaction_id:

        raise RuntimeError(
            "Gemini did not return interaction ID"
        )

    previous_interaction_id = interaction_id

    return answer


# =====================================
# SEND TELEGRAM MESSAGE
# =====================================

def send_message(chat_id, message):

    if not message:
        return

    for start in range(0, len(message), 4000):

        part = message[start:start + 4000]

        telegram("sendMessage", {
            "chat_id": chat_id,
            "text": part
        })


# =====================================
# START BOT
# =====================================

print("================================")
print("Telegram Gemini Bot is starting")
print("================================")

telegram("getMe")

print("Telegram connection successful")
print("Gemini model:", MODEL)
print("Bot is ready")

# =====================================
# MAIN LOOP
# =====================================

while True:

    try:

        updates = telegram("getUpdates", {
            "offset": offset,
            "timeout": 30,
            "allowed_updates": ["message"]
        })

        for update in updates.get("result", []):

            offset = update["update_id"] + 1

            msg = update.get("message", {})

            chat = msg.get("chat", {})
            sender = msg.get("from", {})

            # Only your authorized private account

            if chat.get("type") != "private":
                continue

            if chat.get("id") != CHAT_ID:
                continue

            if sender.get("id") != CHAT_ID:
                continue

            message = msg.get("text", "").strip()

            if not message:
                continue

            # START COMMAND

            if message == "/start":

                send_message(
                    CHAT_ID,
                    "أهلاً بك! 🤖\n\n"
                    "أنا مساعدك الشخصي المدعوم "
                    "بواسطة Google Gemini.\n\n"
                    "ابعت لي أي سؤال وسأرد عليك."
                )

                continue

            # CLEAR CONVERSATION

            if message == "/clear":

                previous_interaction_id = None

                send_message(
                    CHAT_ID,
                    "تم مسح ذاكرة المحادثة. 🧹\n"
                    "نبدأ من جديد!"
                )

                continue

            # ASK GEMINI

            try:

                print("New message received")

                send_message(
                    CHAT_ID,
                    "جاري التفكير... 🤖"
                )

                answer = ask_gemini(message)

                send_message(CHAT_ID, answer)

                print("Gemini response sent successfully")

            except Exception as error:

                print("Gemini error:", str(error))

                send_message(
                    CHAT_ID,
                    "حدث خطأ أثناء الاتصال بـ Gemini.\n\n"
                    "يرجى مراجعة إعدادات API Key "
                    "وسجل الأخطاء في GitHub."
                )

    except Exception as error:

        error_text = str(error)

        print("Connection error:", error_text)

        # Stop if another bot instance is polling Telegram

        if "409" in error_text or "Conflict" in error_text:

            print(
                "Another bot instance is using this token. "
                "Stop the other workflow before restarting."
            )

            raise SystemExit(1)

        time.sleep(5)
