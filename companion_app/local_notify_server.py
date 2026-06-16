import threading
from flask import Flask, request
from werkzeug.serving import make_server
from config import (
    NOTIFY_SERVER_HOST,
    NOTIFY_SERVER_PORT,
)


from companion_app.integrations.discord import (
    discord_notification_event_from_payload,
    format_discord_notification_message,
    is_discord_notification_source,
)
from companion_app.integrations.telegram import (
    format_telegram_notification_message,
    is_telegram_notification_source,
    telegram_notification_event_from_payload,
)
from companion_app.integrations.email import (
    email_notification_event_from_payload,
    format_email_notification_message,
    is_email_notification_source,
)

_flask_app = Flask(__name__)
_server_thread = None
_notify_callback = None
_chat_resolver = None
_state_lock = threading.Lock()


class NotificationServerThread(threading.Thread):

    def __init__(self, flask_app, host, port):
        super().__init__(daemon=False)
        self.server = make_server(host, port, flask_app)

    def run(self):
        self.server.serve_forever()


def register_notify_callback(callback):
    global _notify_callback

    with _state_lock:
        _notify_callback = callback


def start_notification_server(host=NOTIFY_SERVER_HOST, port=NOTIFY_SERVER_PORT, chat_resolver=None):
    global _server_thread, _chat_resolver

    with _state_lock:
        _chat_resolver = chat_resolver

        if _server_thread is not None and _server_thread.is_alive():
            return _server_thread

        _server_thread = NotificationServerThread(
            flask_app=_flask_app,
            host=host,
            port=port
        )
        _server_thread.start()
        return _server_thread


def stop_notification_server(timeout=3):
    global _server_thread

    with _state_lock:
        thread = _server_thread

        if thread is None:
            return

        _server_thread = None

    try:
        thread.server.shutdown()
        thread.server.server_close()
    finally:
        thread.join(timeout=timeout)


def _coerce_text(value):
    if isinstance(value, str):
        return value.strip()

    if value is None:
        return ""

    return str(value).strip()


def notification_event_from_payload(data):
    source = _coerce_text(data.get("source"))

    if not source:
        source = _coerce_text(data.get("event"))

    if is_discord_notification_source(source):
        return discord_notification_event_from_payload(data)

    if is_telegram_notification_source(source):
        return telegram_notification_event_from_payload(data)

    if is_email_notification_source(source):
        return email_notification_event_from_payload(data)

    if not source:
        source = "system"

    summary = _coerce_text(data.get("summary"))

    if not summary:
        summary = _coerce_text(data.get("message"))

    return {
        "source": source.lower(),
        "sender": _coerce_text(data.get("sender")),
        "summary": summary,
    }


def process_notification_event(notification_event):
    source = _coerce_text(notification_event.get("source")).lower()
    sender = _coerce_text(notification_event.get("sender"))
    summary = _coerce_text(notification_event.get("summary"))

    resolver = _chat_resolver

    if source == "discord" and resolver is not None:
        message = format_discord_notification_message(
            chat_resolver=resolver,
            sender=sender,
            summary=summary,
        )
    elif source == "telegram":
        message = format_telegram_notification_message(
            sender=sender,
            summary=summary,
        )
    elif source == "email":
        message = format_email_notification_message(
            sender=sender,
            summary=summary,
        )
    elif summary:
        message = summary
    else:
        message = "Notification received"

    print(f"RECEIVED: {message}")

    callback = _notify_callback

    if callback is not None:
        callback(message)

    return message


@_flask_app.route("/notify", methods=["POST"])
def receive_notification():
    data = request.json or {}

    notification_event = notification_event_from_payload(data)
    process_notification_event(notification_event)

    return {"status": "ok"}
