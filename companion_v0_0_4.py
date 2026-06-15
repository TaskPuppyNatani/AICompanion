import sys
import pyttsx3
import random
import threading
from pathlib import Path
import json



from PyQt6.QtGui import QPixmap, QGuiApplication
from PyQt6.QtWidgets import QApplication, QLabel
from PyQt6.QtCore import QTimer
from flask import Flask, request
from PyQt6.QtCore import Qt, QObject, pyqtSignal


app = QApplication(sys.argv)

app_server = Flask(__name__)

CONFIG_PATH = Path(__file__).parent / "config.json"

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


def notify(message):
    print(f"NOTIFICATION: {message}")

    notification_label.setText(message)
    notification_label.adjustSize()

    bubble_x = x + 40
    bubble_y = y - notification_label.height() - 10

    notification_label.move(
        bubble_x,
        bubble_y
    )

    notification_label.show()

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
    def mousePressEvent(self, event):
        phrase = random.choice(responses)

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

notification_label.setWindowFlags(
    Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
    | Qt.WindowType.Tool
)

notification_label.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

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

label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

label.show()

engine = pyttsx3.init()

startup_phrase = random.choice(startup_responses)

print(startup_phrase)

engine.say(startup_phrase)
engine.runAndWait()

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