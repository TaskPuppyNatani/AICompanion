def _coerce_text(value):
    if isinstance(value, str):
        return value.strip()

    if value is None:
        return ""

    return str(value).strip()


def is_telegram_notification_source(source):
    return _coerce_text(source).lower() == "telegram"


def telegram_notification_event_from_payload(data):
    summary = _coerce_text(data.get("summary"))

    if not summary:
        summary = _coerce_text(data.get("message"))

    return {
        "source": "telegram",
        "sender": _coerce_text(data.get("sender")),
        "summary": summary,
    }


def format_telegram_notification_message(sender="", summary=""):
    sender_text = _coerce_text(sender)
    summary_text = _coerce_text(summary)

    if sender_text and summary_text:
        return f"Telegram message from {sender_text}. {summary_text}"

    if sender_text:
        return f"Telegram message from {sender_text}."

    if summary_text:
        return f"Telegram message received. {summary_text}"

    return "Telegram message received."