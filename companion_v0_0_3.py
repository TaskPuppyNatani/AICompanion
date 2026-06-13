import sys
import pyttsx3
import random

from PyQt6.QtWidgets import QApplication, QLabel
from PyQt6.QtGui import QPixmap, QGuiApplication
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox
from PyQt6.QtCore import QTimer

app = QApplication(sys.argv)

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
    "OCR processing completed.",
    "Ratchet reports all services healthy.",
    "Container restarted successfully.",
]


def notify(message):
    print(f"NOTIFICATION: {message}")

    QMessageBox.information(
        label,
        "Notification",
        message
    )
    
class Companion(QLabel):
    def mousePressEvent(self, event):
        phrase = random.choice(responses)

        print(phrase)

        QMessageBox.information(
            self,
            "Lombax",
            phrase
        )

label = Companion()

pixmap = QPixmap(r"C:\AICompanion\lombax.png")
pixmap = pixmap.scaled(
    300,
    300,
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

sys.exit(app.exec())