import threading
from flask import Flask, request
from werkzeug.serving import make_server

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


def start_notification_server(host="127.0.0.1", port=5000, chat_resolver=None):
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


@_flask_app.route("/notify", methods=["POST"])
def receive_notification():
    data = request.json or {}

    event = data.get("event")
    sender = data.get("sender")

    resolver = _chat_resolver

    if event == "discord" and resolver is not None:
        message = resolver(event, sender)
    else:
        message = data.get(
            "message",
            "Notification received"
        )

    print(f"RECEIVED: {message}")

    callback = _notify_callback

    if callback is not None:
        callback(message)

    return {"status": "ok"}
