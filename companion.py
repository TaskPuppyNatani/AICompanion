import sys
import requests
import winsound
import random
import threading
import json
import time
from pathlib import Path

from PyQt6.QtGui import QPixmap, QGuiApplication
from PyQt6.QtWidgets import QApplication, QLabel
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer
from flask import Flask, request

app = QApplication(sys.argv)

app_server = Flask(__name__)

CONFIG_PATH = Path(__file__).parent / "config.json"

speaking = False

with open(CONFIG_PATH, "r") as f:
    config = json.load(f)


class NotificationBridge(QObject):
    notify_signal = pyqtSignal(str)


bridge = NotificationBridge()

responses = [
    "Hello Pup.",
    "How are you doing?",
    "Ratchet seems quiet today.",
    "Rivet seems to be fine.",
    "How is Danny doing?",
    "Danny sent you a Discord message and Ratchet is generating speech through Kokoro.",
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
    "Danny sent you a Discord message.",
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
          
def ask_ratchet(event="click"):
    try:
        response = requests.post(
            "http://192.168.1.4:5001/chat",
            json={
                "event": event
            },
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


@app_server.route("/notify", methods=["POST"])
def receive_notification():
    data = request.json

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

    def mousePressEvent(self, event):

        if time.time() - self.last_click < 0.5:
            return

        self.last_click = time.time()

        phrase = ask_ratchet()

        print(phrase)

        notify(phrase)

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

threading.Thread(
    target=lambda: app_server.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False
    ),
    daemon=True
).start()

sys.exit(app.exec())