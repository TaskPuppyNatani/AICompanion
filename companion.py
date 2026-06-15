import sys
import requests
import winsound
import random
import threading
import json
import time
from pathlib import Path

from PyQt6.QtGui import QPixmap, QGuiApplication
from PyQt6.QtWidgets import QApplication, QLabel, QMenu
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer
from flask import Flask, request
from werkzeug.serving import make_server

app = QApplication(sys.argv)

app_server = Flask(__name__)

CONFIG_PATH = Path(__file__).parent / "config.json"

speaking = False

with open(CONFIG_PATH, "r") as f:
    config = json.load(f)


def saved_avatar_position():
    position = config.get("avatar_position")

    if not isinstance(position, dict):
        return None

    try:
        return int(position["x"]), int(position["y"])
    except (KeyError, TypeError, ValueError):
        return None


def save_avatar_position(new_x, new_y):
    config["avatar_position"] = {
        "x": int(new_x),
        "y": int(new_y)
    }

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)
        f.write("\n")


def set_avatar_position(new_x, new_y):
    global x, y

    x = int(new_x)
    y = int(new_y)

    label.move(x, y)


class NotificationBridge(QObject):
    notify_signal = pyqtSignal(str)


bridge = NotificationBridge()

responses = [
    "Hello Pup.",
    "How are you doing?",
    "Ratchet seems quiet today.",
    "Rivet seems to be fine.",
    "No emergencies detected.",
    "All systems nominal.",
]

startup_responses = [
    "Hello Pup.",
    "Good evening Pup.",
    "Nice to see you again.",
    "Systems online.",
]

notifications = [
    "New email received.",
    "Rivet reports all services healthy.",
    "Ratchet reports all services healthy.",
    "Container restarted successfully.",
]

def speak(message):

    global speaking

    if speaking:
        return

    speaking = True

    try:
        response = requests.post(
            "http://192.168.1.4:5001/speak",
            json={"text": message},
            timeout=30
        )

        with open("speech.wav", "wb") as f:
            f.write(response.content)

        winsound.PlaySound(
            "speech.wav",
            winsound.SND_FILENAME
        )

    except Exception as e:
        print(f"Speech error: {e}")

    finally:
        speaking = False

def ask_ratchet(event="click", sender=None):
    try:
        payload = {
            "event": event
        }

        if sender:
            payload["sender"] = sender

        response = requests.post(
            "http://192.168.1.4:5001/chat",
            json=payload,
            timeout=10
        )

        return response.json()["response"]

    except Exception as e:
        print(f"Chat error: {e}")
        return "Ratchet seems to be thinking too hard right now."
        
def notify(message):
    print(f"NOTIFICATION: {message}")

    notification_label.setText(message)
    notification_label.adjustSize()

    bubble_x = x + 60
    bubble_y = y - notification_label.height() - 10

    notification_label.move(
        bubble_x,
        bubble_y
    )

    notification_label.show()

    threading.Thread(
        target=speak,
        args=(message,),
        daemon=True
    ).start()

    QTimer.singleShot(
        config["notification_duration"],
        notification_label.hide
    )


bridge.notify_signal.connect(notify)


class NotificationServerThread(threading.Thread):

    def __init__(self, flask_app, host, port):
        super().__init__(daemon=False)
        self.server = make_server(host, port, flask_app)

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()
        self.server.server_close()


is_shutting_down = False
notification_server_thread = None


def clean_exit():
    global is_shutting_down

    if is_shutting_down:
        return

    is_shutting_down = True

    notification_label.hide()
    label.hide()

    if notification_server_thread is not None:
        notification_server_thread.shutdown()
        notification_server_thread.join(timeout=3)

    app.quit()


@app_server.route("/notify", methods=["POST"])
def receive_notification():
    data = request.json or {}

    event = data.get("event")
    sender = data.get("sender")

    if event == "discord":
        message = ask_ratchet(event, sender)
    else:
        message = data.get(
            "message",
            "Notification received"
        )

    print(f"RECEIVED: {message}")

    bridge.notify_signal.emit(message)

    return {"status": "ok"}


class Companion(QLabel):

    def __init__(self):
        super().__init__()

        self.last_click = 0
        self.drag_offset = None
        self.dragged = False
        self.context_menu = QMenu(self)

        exit_action = self.context_menu.addAction("Exit")
        exit_action.triggered.connect(clean_exit)

        reload_action = self.context_menu.addAction("Reload Personality")
        reload_action.triggered.connect(self.reload_personality)

        mute_action = self.context_menu.addAction("Mute Voice")
        mute_action.triggered.connect(self.mute_voice)

    def reload_personality(self):
        print("Reload Personality selected (placeholder)")
        notify("Reload Personality is not implemented yet.")

    def mute_voice(self):
        print("Mute Voice selected (placeholder)")
        notify("Mute Voice is not implemented yet.")

    def show_context_menu(self, event):
        self.context_menu.exec(event.globalPosition().toPoint())

    def mousePressEvent(self, event):

        if event.button() == Qt.MouseButton.RightButton:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.show_context_menu(event)
                event.accept()
                return

            self.drag_offset = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )
            self.dragged = False
            event.accept()
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        if time.time() - self.last_click < 0.5:
            return

        self.last_click = time.time()

        phrase = ask_ratchet()

        print(phrase)

        notify(phrase)

    def mouseMoveEvent(self, event):

        if (
            self.drag_offset is None
            or not event.buttons() & Qt.MouseButton.RightButton
        ):
            return

        new_position = event.globalPosition().toPoint() - self.drag_offset
        set_avatar_position(new_position.x(), new_position.y())
        self.dragged = True
        event.accept()

    def mouseReleaseEvent(self, event):

        if event.button() != Qt.MouseButton.RightButton:
            return

        if self.dragged:
            save_avatar_position(x, y)

        self.drag_offset = None
        self.dragged = False
        event.accept()
label = Companion()

notification_label = QLabel("")

notification_label.setStyleSheet("""
    background-color: white;
    border: 2px solid black;
    border-radius: 20px;
    padding: 10px;
""")
        
notification_label.setWordWrap(True)
notification_label.setMaximumWidth(250)

notification_label.setWindowFlags(
    Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
    | Qt.WindowType.Tool
)

notification_label.setAttribute(
    Qt.WidgetAttribute.WA_ShowWithoutActivating
)

notification_label.hide()

IMAGE_PATH = Path(__file__).parent / config["avatar"]

pixmap = QPixmap(str(IMAGE_PATH))

pixmap = pixmap.scaled(
    config["avatar_size"],
    config["avatar_size"],
    Qt.AspectRatioMode.KeepAspectRatio,
    Qt.TransformationMode.SmoothTransformation
)

label.setPixmap(pixmap)

screen = QGuiApplication.primaryScreen()
geometry = screen.availableGeometry()

x = geometry.width() - pixmap.width() - 20
y = geometry.height() - pixmap.height() - 20

saved_position = saved_avatar_position()

if saved_position is not None:
    x, y = saved_position

label.move(x, y)

label.setWindowFlags(
    Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
    | Qt.WindowType.Tool
)

label.setAttribute(
    Qt.WidgetAttribute.WA_TranslucentBackground
)

label.show()

startup_phrase = ask_ratchet("startup")

notify(startup_phrase)

print(startup_phrase)

QTimer.singleShot(
    10000,
    lambda: notify(random.choice(notifications))
)

notification_server_thread = NotificationServerThread(
    flask_app=app_server,
    host="127.0.0.1",
    port=5000
)

notification_server_thread.start()

app.aboutToQuit.connect(clean_exit)

sys.exit(app.exec())
