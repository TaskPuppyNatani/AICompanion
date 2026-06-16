def _coerce_text(value):
    if isinstance(value, str):
        return value.strip()

    if value is None:
        return ""

    return str(value).strip()


def is_discord_notification_source(source):
    return _coerce_text(source).lower() == "discord"


def discord_notification_event_from_payload(data):
    summary = _coerce_text(data.get("summary"))

    if not summary:
        summary = _coerce_text(data.get("message"))

    return {
        "source": "discord",
        "sender": _coerce_text(data.get("sender")),
        "summary": summary,
    }


def format_discord_notification_message(chat_resolver, sender="", summary=""):
    sender_text = _coerce_text(sender)
    summary_text = _coerce_text(summary)

    if sender_text:
        message = chat_resolver("discord", sender_text)

        if summary_text:
            message = f"{message} {summary_text}"

        return message

    if summary_text:
        return summary_text

    return chat_resolver("discord", sender_text)
