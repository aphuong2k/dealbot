import os, sys, requests

def tg(text, parse_mode=None):
    t, c = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (t and c):
        try:
            print("[notify]", text)
        except Exception:
            safe_text = text.encode("ascii", errors="backslashreplace").decode("ascii")
            print("[notify]", safe_text)
        return
    try:
        payload = {"chat_id": c, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        requests.post(f"https://api.telegram.org/bot{t}/sendMessage", json=payload, timeout=15)
    except Exception as e:
        print("[notify error]", e)


