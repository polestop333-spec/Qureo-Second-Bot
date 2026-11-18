
import os
import json
import time
import urllib.request
import urllib.parse
import urllib.error

TOKEN = os.environ["8960652955:AAFb7D190phzxM2JgPTl-F2ZpEMH2SoKoqQ04:04 PM"]
CHAT_ID = int(os.environ["6184119318"])
GEMINI_KEY = os.environ["AQ.Ab8RN6KRbrV325-OZgoRtJANvy1JPAEI5yRdPecZrcbi_DaSRg
"]

TELEGRAM = f"https://api.telegram.org/bot{TOKEN}"
GEMINI = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-3.8-flash:generateContent"
)

history = []
offset = 0


def telegram(method, data=None):
    payload = json.dumps(data or {}).encode()
    req = urllib.request.Request(
        f"{TELEGRAM}/{method}",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=40) as response:
        return json.loads(response.read())


def ask_gemini(message):
    global history

    history.append({
        "role": "user",
        "parts": [{"text": message}]
    })

    history = history[-20:]

    body = {
        "contents": history,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048
        }
    }

    req = urllib.request.Request(
        GEMINI,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_KEY
        }
    )

    with urllib.request.urlopen(req, timeout=120) as response:
        result = json.loads(response.read())

    answer = "".join(
        part.get("text", "")
        for part in result["candidates"][0]["content"]["parts"]
    )

    history.append({
        "role": "model",
        "parts": [{"text": answer}]
    })

    return answer


def send_message(chat_id, text):
    for i in range(0, len(text), 4000):
        telegram("sendMessage", {
            "chat_id": chat_id,
            "text": text[i:i+4000]
        })


print("BOT STARTED SUCCESSFULLY")

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

            # Only your private account
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
                    "أهلاً بك! أنا مساعدك الشخصي المدعوم بـ Gemini 🤖"
                )
                continue

            if message == "/clear":
                history.clear()
                send_message(CHAT_ID, "تم مسح سياق المحادثة.")
                continue

            try:
                answer = ask_gemini(message)
                send_message(CHAT_ID, answer)

            except Exception as e:
                print("Gemini error:", str(e))
                send_message(
                    CHAT_ID,
                    "حصل خطأ أثناء الاتصال بـ Gemini. حاول مرة أخرى."
                )

    except Exception as e:
        print("Connection error:", str(e))
        time.sleep(5)
