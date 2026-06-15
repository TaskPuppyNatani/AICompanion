import sys
import winsound
import random
import threading
import time
import tempfile
from pathlib import Path

from PyQt6.QtGui import QPixmap, QGuiApplication
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QInputDialog,
    QMessageBox,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer
from companion_app.local_notify_server import (
    register_notify_callback,
    start_notification_server,
    stop_notification_server,
)

from config_store import config, saved_avatar_position, save_avatar_position
from companion_app import api_client, note_workflow

try:
    import numpy as np
    import sounddevice as sd
    import soundfile as sf_audio
except Exception:
    np = None
    sd = None
    sf_audio = None

app = QApplication(sys.argv)


speaking = False


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
        audio_content = api_client.speak(message)

        with open("speech.wav", "wb") as f:
            f.write(audio_content)

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
        response = api_client.chat(event, sender)

        return response["response"]

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


is_shutting_down = False
register_notify_callback(bridge.notify_signal.emit)


def clean_exit():
    global is_shutting_down

    if is_shutting_down:
        return

    is_shutting_down = True

    notification_label.hide()
    label.hide()

    stop_notification_server(timeout=3)

    app.quit()

class Companion(QLabel):

    def __init__(self):
        super().__init__()

        self.last_click = 0
        self.drag_offset = None
        self.dragged = False
        self.transcribing_dialog = None
        self.context_menu = QMenu(self)

        exit_action = self.context_menu.addAction("Exit")
        exit_action.triggered.connect(clean_exit)

        reload_action = self.context_menu.addAction("Reload Personality")
        reload_action.triggered.connect(self.reload_personality)

        mute_action = self.context_menu.addAction("Mute Voice")
        mute_action.triggered.connect(self.mute_voice)

        add_note_action = self.context_menu.addAction("Add Note")
        add_note_action.triggered.connect(self.add_note_dialog)

        voice_note_action = self.context_menu.addAction("Voice Note")
        voice_note_action.triggered.connect(self.voice_note_dialog)

    def reload_personality(self):
        print("Reload Personality selected (placeholder)")
        notify("Reload Personality is not implemented yet.")

    def mute_voice(self):
        print("Mute Voice selected (placeholder)")
        notify("Mute Voice is not implemented yet.")

    def add_note_dialog(self):
        note_text, ok = QInputDialog.getText(
            self,
            "Add Note",
            "Enter note:"
        )

        if not ok:
            return

        note_text = note_text.strip()

        if not note_text:
            return

        self.finalize_note_workflow(note_text)

    def pick_note_category(self, note_text):
        category = None

        try:
            suggested_category = note_workflow.request_category_suggestion(note_text)
        except Exception as e:
            print(f"Suggest category error: {e}")
            suggested_category = None

        decision_dialog = QMessageBox(self)
        decision_dialog.setWindowTitle("Add Note Category")

        if isinstance(suggested_category, str) and suggested_category.strip():
            decision_dialog.setText(
                f"Suggested category: {suggested_category.strip()}"
            )
        else:
            decision_dialog.setText(
                "No category suggestion found."
            )

        accept_button = decision_dialog.addButton(
            "Accept",
            QMessageBox.ButtonRole.AcceptRole
        )
        change_button = decision_dialog.addButton(
            "Change",
            QMessageBox.ButtonRole.ActionRole
        )
        skip_button = decision_dialog.addButton(
            "Skip Category",
            QMessageBox.ButtonRole.RejectRole
        )

        decision_dialog.setDefaultButton(accept_button)
        decision_dialog.exec()

        clicked = decision_dialog.clickedButton()

        if clicked is None:
            return None, False

        if clicked == change_button:
            changed_category, changed_ok = QInputDialog.getText(
                self,
                "Change Category",
                "Enter category (optional):"
            )

            if changed_ok and changed_category.strip():
                category = changed_category.strip()

        elif clicked == accept_button:
            if isinstance(suggested_category, str) and suggested_category.strip():
                category = suggested_category.strip()

        elif clicked == skip_button:
            category = None

        return category, True

    def finalize_note_workflow(self, note_text):
        category, should_continue = self.pick_note_category(note_text)

        try:
            did_save, payload = note_workflow.finalize_note_workflow(
                note_text,
                category,
                should_continue
            )

            if not did_save:
                return

            message = payload.get("message", "Note saved.")
            notify(message)

        except Exception as e:
            print(f"Add note error: {e}")
            notify("Could not save note right now.")

    def clear_transcribing_dialog(self):
        if self.transcribing_dialog is None:
            return

        try:
            self.transcribing_dialog.hide()
            self.transcribing_dialog.close()
            self.transcribing_dialog.deleteLater()
        finally:
            self.transcribing_dialog = None

    def voice_note_dialog(self):
        if np is None or sd is None or sf_audio is None:
            notify("Voice Note requires sounddevice, soundfile, and numpy.")
            return

        sample_rate = 16000
        audio_frames = []
        recording_state = {"stopped": False}

        def audio_callback(indata, frames, callback_time, status):
            if status:
                print(f"Recording status: {status}")
            audio_frames.append(indata.copy())

        record_dialog = QDialog(self)
        record_dialog.setWindowTitle("Voice Note")
        record_dialog.setModal(True)

        dialog_layout = QVBoxLayout(record_dialog)
        dialog_layout.addWidget(QLabel("Recording..."))

        button_layout = QHBoxLayout()
        stop_button = QPushButton("Stop")
        cancel_button = QPushButton("Cancel")
        button_layout.addWidget(stop_button)
        button_layout.addWidget(cancel_button)
        dialog_layout.addLayout(button_layout)

        def on_stop_clicked():
            recording_state["stopped"] = True
            record_dialog.accept()

        stop_button.clicked.connect(on_stop_clicked)
        cancel_button.clicked.connect(record_dialog.reject)

        stream = None

        try:
            stream = sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                callback=audio_callback
            )
            stream.start()
            record_dialog.exec()
        except Exception as e:
            print(f"Voice recording error: {e}")
            notify("Could not start voice recording.")
            return
        finally:
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception as close_error:
                    print(f"Voice stream close error: {close_error}")

        if not recording_state["stopped"]:
            return

        if not audio_frames:
            notify("No audio captured.")
            return

        temp_audio_path = None
        transcript_text = ""

        try:
            waveform = np.concatenate(audio_frames, axis=0)

            temp_audio = tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False
            )
            temp_audio_path = temp_audio.name
            temp_audio.close()

            sf_audio.write(temp_audio_path, waveform, sample_rate)

            # Ensure no stale status dialog remains before showing a new one.
            self.clear_transcribing_dialog()

            self.transcribing_dialog = QMessageBox(self)
            self.transcribing_dialog.setWindowTitle("Voice Note")
            self.transcribing_dialog.setText("Transcribing...")
            self.transcribing_dialog.setStandardButtons(
                QMessageBox.StandardButton.NoButton
            )
            self.transcribing_dialog.setModal(True)
            self.transcribing_dialog.show()
            QApplication.processEvents()

            transcript_text = note_workflow.request_transcription(temp_audio_path)

        except Exception as e:
            print(f"Voice transcription error: {e}")
            notify("Could not transcribe voice note right now.")
            return
        finally:
            self.clear_transcribing_dialog()

            if temp_audio_path:
                try:
                    Path(temp_audio_path).unlink()
                except OSError:
                    pass

        if not transcript_text:
            notify("No speech detected.")
            return

        reviewed_text, reviewed_ok = QInputDialog.getMultiLineText(
            self,
            "Review Transcript",
            "Edit note:",
            transcript_text
        )

        if not reviewed_ok:
            return

        reviewed_text = reviewed_text.strip()

        if not reviewed_text:
            return

        self.finalize_note_workflow(reviewed_text)

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

start_notification_server(
    host="127.0.0.1",
    port=5000,
    chat_resolver=ask_ratchet
)

app.aboutToQuit.connect(clean_exit)

sys.exit(app.exec())
