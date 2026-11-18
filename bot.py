
import os
import json
import time
import urllib.request
import urllib.error

# =====================================
# SETTINGS
# =====================================

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID_RAW = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

MODEL = "gemini-3.8-flash"

TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN}"

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/"
    f"v1beta/models/{MODEL}:generateContent"
)

if not TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN")

if not CHAT_ID_RAW:
    raise ValueError("Missing TELEGRAM_CHAT_ID")

if not CHAT_ID_RAW.lstrip("-").isdigit():
    raise ValueError("Invalid TELEGRAM_CHAT_ID")

if not GEMINI_KEY:
    raise ValueError("Missing GEMINI_API_KEY")

CHAT_ID = int(CHAT_ID_RAW)

# =====================================
# MEMORY
# =====================================

conversation_history = []
offset = 0

# =====================================
# TELEGRAM API
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
            f"Telegram HTTP {error.code}: {details}"
        )

    if not result.get("ok"):
        raise RuntimeError(str(result))

    return result


# =====================================
# GEMINI API
# =====================================

def ask_gemini(message):

    global conversation_history

    new_history = conversation_history + [
        {
            "role": "user",
            "parts": [
                {"text": message}
            ]
        }
    ]

    body = {
        "contents": new_history,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096
        }
    }

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

        try:
            error_data = json.loads(details)
            details = error_data.get(
                "error", {}
            ).get("message", details)
        except Exception:
            pass

        raise RuntimeError(
            f"Gemini HTTP {error.code}: {details}"
        )

    candidates = result.get("candidates", [])

    if not candidates:
        raise RuntimeError(
            "Gemini returned no candidates: "
            + json.dumps(result, ensure_ascii=False)[:1500]
        )

    parts = candidates[0].get(
        "content", {}
    ).get("parts", [])

    answer = "\n".join(
        part.get("text", "")
        for part in parts
        if part.get("text")
        and not part.get("thought", False)
    ).strip()

    if not answer:
        raise RuntimeError(
            "Gemini returned an empty response"
        )

    # Save conversation only after successful response

    conversation_history = new_history + [
        {
            "role": "model",
            "parts": [
                {"text": answer}
            ]
        }
    ]

    # Keep memory within reasonable limits

    if len(conversation_history) > 30:
        conversation_history = conversation_history[-30:]

    return answer


# =====================================
# SEND MESSAGE
# =====================================

def send_message(chat_id, message):

    for start in range(0, len(message), 4000):

        telegram("sendMessage", {
            "chat_id": chat_id,
            "text": message[start:start + 4000]
        })


# =====================================
# START
# =====================================

print("Starting Telegram Gemini Bot...")

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

            if chat.get("type") != "private":
                continue

            if chat.get("id") != CHAT_ID:
                continue

            if sender.get("id") != CHAT_ID:
                continue

            message = msg.get("text", "").strip()

            if not message:
                continue

            if message == "/start":

                send_message(
                    CHAT_ID,
                    "أهلاً بك! 🤖\n\n"
                    "أنا مساعدك الشخصي بواسطة "
                    "Google Gemini.\n\n"
                    "اسألني أي سؤال وسأساعدك."
                )

                continue

            if message == "/clear":

                conversation_history = []

                send_message(
                    CHAT_ID,
                    "تم مسح ذاكرة المحادثة! 🧹"
                )

                continue

            try:

                print("New message received")

                send_message(
                    CHAT_ID,
                    "جاري التفكير... 🤖"
                )

                answer = ask_gemini(message)

                send_message(CHAT_ID, answer)

                print("Gemini response successful")

            except Exception as error:

                print(
                    "GEMINI ERROR:",
                    str(error)
                )

                send_message(
                    CHAT_ID,
                    "حدث خطأ أثناء الاتصال بـ Gemini.\n"
                    "راجع سجل GitHub لمعرفة السبب بالتحديد."
                )

    except Exception as error:

        error_text = str(error)

        print("CONNECTION ERROR:", error_text)

        if "409" in error_text or "Conflict" in error_text:
            print("Another bot instance is running.")
            raise SystemExit(1)

        time.sleep(5)
