import sys
import shutil
import os
import winsound
import random
import threading
import time
import subprocess
from datetime import datetime
from pathlib import Path
import requests
from config import (
    AUDIO_DIR,
    NOTIFY_SERVER_HOST,
    NOTIFY_SERVER_PORT,
    API_HOST,
    API_PORT,
    OLLAMA_HOST,
    OLLAMA_PORT,
    OLLAMA_HEALTH_URL,
)


from PyQt6.QtGui import (
    QPixmap,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
    QColor,
    QTextOption,
)
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QMenu,
    QInputDialog,
    QMessageBox,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTextEdit
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer, QSize, QRectF
from companion_app.local_notify_server import (
    register_notify_callback,
    start_notification_server,
    stop_notification_server,
)
from companion_app.windows_notification_listener import (
    start_windows_notification_listener,
    stop_windows_notification_listener,
)

from config import NOTIFY_SERVER_HOST
from config_store import (
    config,
    saved_avatar_position,
    save_avatar_position,
    voice_enabled,
    save_voice_enabled,
)
from companion_app import api_client, note_workflow
from companion_app import voice_capture

app = None
label = None
notification_label = None


speaking = False
speech_server_process = None
speech_server_owned_by_companion = False

SPEECH_HEALTHCHECK_URL = f"http://{API_HOST}:{API_PORT}/notes/recent"
SPEECH_STARTUP_TIMEOUT_SEC = 45
SPEECH_POLL_INTERVAL_SEC = 0.5

OLLAMA_STARTUP_TIMEOUT_SEC = 15
OLLAMA_FALLBACK_EXE = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"


class NotificationBridge(QObject):
    notify_signal = pyqtSignal(str)


bridge = NotificationBridge()


class ThoughtBubbleWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""
        self._word_wrap = True
        self._padding_x = 12
        self._padding_y = 10
        self._tail_height = 26
        self._corner_radius = 18
        self._border_width = 2
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def setText(self, text):
        self._text = "" if text is None else str(text)
        self.updateGeometry()
        self.update()

    def text(self):
        return self._text

    def setWordWrap(self, enabled):
        self._word_wrap = bool(enabled)
        self.updateGeometry()
        self.update()

    def _effective_max_width(self):
        max_width = self.maximumWidth()

        if max_width >= 16777215:
            return 250

        return max(120, max_width)

    def _text_bounds(self):
        max_width = self._effective_max_width() - (self._padding_x * 2 + 4)
        max_width = max(40, max_width)
        flags = int(Qt.TextFlag.TextWordWrap) if self._word_wrap else 0
        return self.fontMetrics().boundingRect(0, 0, max_width, 10000, flags, self._text)

    def sizeHint(self):
        text_rect = self._text_bounds()
        width = text_rect.width() + (self._padding_x * 2 + 4)
        height = text_rect.height() + (self._padding_y * 2 + 4) + self._tail_height

        effective_max = self._effective_max_width()
        width = min(width, effective_max)

        return QSize(width, height)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        body_rect = QRectF(
            1,
            1,
            max(10, self.width() - 2),
            max(10, self.height() - self._tail_height - 2),
        )

        path = QPainterPath()
        path.addRoundedRect(body_rect, self._corner_radius, self._corner_radius)

        outline_pen = QPen(QColor("black"), self._border_width)
        painter.setPen(outline_pen)
        painter.setBrush(QColor("white"))
        painter.drawPath(path)

        # Thought circles trailing from bubble toward Rivet.
        circle_specs = [
            (7.0, body_rect.left() + 44, body_rect.bottom() + 9),
            (5.0, body_rect.left() + 30, body_rect.bottom() + 17),
            (3.5, body_rect.left() + 18, body_rect.bottom() + 23),
        ]

        for radius, cx, cy in circle_specs:
            painter.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))

        text_rect = body_rect.adjusted(
            self._padding_x,
            self._padding_y,
            -self._padding_x,
            -self._padding_y,
        )

        text_option = QTextOption(Qt.AlignmentFlag.AlignCenter)
        if self._word_wrap:
            text_option.setWrapMode(QTextOption.WrapMode.WordWrap)
        else:
            text_option.setWrapMode(QTextOption.WrapMode.NoWrap)

        painter.setPen(QColor("black"))
        painter.drawText(text_rect, self._text, text_option)

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


def probe_ollama_ready(timeout=1.0):
    try:
        response = requests.get(OLLAMA_HEALTH_URL, timeout=timeout)
        return response.status_code == 200, None
    except Exception as e:
        return False, f"Request failed: {e}"


def _find_ollama_exe():
    found = shutil.which("ollama")
    if found:
        return Path(found)
    if OLLAMA_FALLBACK_EXE.is_file():
        return OLLAMA_FALLBACK_EXE
    return None


def launch_ollama_process():
    exe = _find_ollama_exe()
    if exe is None:
        raise RuntimeError("ollama executable not found on PATH or fallback location")

    command = [str(exe), "serve"]
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        raise RuntimeError(f"Launch failed for command {command}: {e}") from e

    return process, command


def probe_speech_server_ready(timeout=1.0):
    try:
        response = requests.get(
            SPEECH_HEALTHCHECK_URL,
            timeout=timeout
        )
    except Exception as e:
        return False, f"Request failed: {e}"

    if response.status_code != 200:
        return False, f"Unexpected status code: {response.status_code}"

    try:
        payload = response.json()
    except Exception as e:
        return False, f"Invalid JSON response: {e}"

    if not isinstance(payload, list):
        return False, f"Unexpected payload type: {type(payload).__name__}"

    return True, None


def launch_speech_server_process():
    speech_server_path = Path(__file__).resolve().parent / "speech_server.py"

    command = [
        sys.executable,
        str(speech_server_path),
    ]

    try:
        process = subprocess.Popen(
            command,
            cwd=str(speech_server_path.parent)
        )
    except Exception as e:
        raise RuntimeError(
            f"Launch failed for command {command}: {e}"
        ) from e

    return process, command


def wait_for_speech_server_ready(timeout_seconds, poll_interval_seconds, process=None, probe_fn=probe_speech_server_ready):
    deadline = time.monotonic() + timeout_seconds
    last_error = None

    while time.monotonic() < deadline:
        if process is not None:
            return_code = process.poll()

            if return_code is not None:
                return False, f"Speech server exited with code {return_code}"

        is_ready, error = probe_fn()

        if is_ready:
            return True, None

        last_error = error
        time.sleep(poll_interval_seconds)

    return False, last_error


def terminate_managed_speech_server(timeout_seconds=5):
    global speech_server_process
    global speech_server_owned_by_companion

    if not speech_server_owned_by_companion:
        return

    if speech_server_process is None:
        return

    try:
        if speech_server_process.poll() is None:
            speech_server_process.terminate()

            try:
                speech_server_process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                speech_server_process.kill()
                speech_server_process.wait(timeout=2)
    except Exception as e:
        print(f"Speech server shutdown error: {e}")
    finally:
        speech_server_process = None
        speech_server_owned_by_companion = False

def speak(message):

    global speaking

    if not voice_enabled():
        return

    if speaking:
        return

    speaking = True

    try:
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        speech_file_path = AUDIO_DIR / "speech.wav"

        audio_content = api_client.speak(message)

        with open(speech_file_path, "wb") as f:
            f.write(audio_content)

        winsound.PlaySound(
            str(speech_file_path),
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

    if label is not None:
        label.update_notification_bubble_position()
    else:
        avatar_x, avatar_y = 0, 0

        bubble_x = avatar_x + 60
        bubble_y = avatar_y - notification_label.height() - 10

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

    duration_ms = min(
        20000,
        max(config["notification_duration"], len(message) * 55)
    )

    if not hasattr(notification_label, "_hide_timer"):
        notification_label._hide_timer = QTimer()
        notification_label._hide_timer.setSingleShot(True)
        notification_label._hide_timer.timeout.connect(notification_label.hide)

    notification_label._hide_timer.stop()
    notification_label._hide_timer.start(duration_ms)


is_shutting_down = False


def clean_exit():
    global is_shutting_down

    if is_shutting_down:
        return

    is_shutting_down = True

    notification_label.hide()
    label.hide()

    terminate_managed_speech_server(timeout_seconds=5)

    stop_windows_notification_listener(timeout_seconds=3)

    stop_notification_server(timeout=3)

    if app is not None:
        app.quit()

class Companion(QLabel):

    def __init__(self):
        super().__init__()

        self.last_click = 0
        self.drag_offset = None
        self.dragged = False
        self.transcribing_dialog = None
        self.avatar_x = 0
        self.avatar_y = 0
        self.context_menu = QMenu(self)

        exit_action = self.context_menu.addAction("Exit")
        exit_action.triggered.connect(clean_exit)

        reload_action = self.context_menu.addAction("Reload Personality")
        reload_action.triggered.connect(self.reload_personality)

        mute_action = self.context_menu.addAction("Mute Voice")
        mute_action.triggered.connect(self.mute_voice)

        add_note_action = self.context_menu.addAction("Add Note")
        add_note_action.triggered.connect(self.add_note_dialog)

        view_notes_action = self.context_menu.addAction("View Notes")
        view_notes_action.triggered.connect(self.view_notes_dialog)

        voice_note_action = self.context_menu.addAction("Voice Note")
        voice_note_action.triggered.connect(self.voice_note_dialog)

    def set_avatar_position(self, new_x, new_y):
        self.avatar_x = int(new_x)
        self.avatar_y = int(new_y)
        self.move(self.avatar_x, self.avatar_y)

        if notification_label is not None and notification_label.isVisible():
            self.update_notification_bubble_position()

    def get_avatar_position(self):
        return self.avatar_x, self.avatar_y

    def update_notification_bubble_position(self):
        if notification_label is None:
            return

        avatar_x, avatar_y = self.get_avatar_position()

        bubble_x = avatar_x + 60
        bubble_y = avatar_y - notification_label.height() - 10

        notification_label.move(
            bubble_x,
            bubble_y
        )

    def reload_personality(self):
        try:
            api_client.reload_personality()
            notify("Personality reloaded.")
        except Exception as e:
            print(f"Reload personality error: {e}")
            notify("Failed to reload personality.")

    def mute_voice(self):
        enabled = not voice_enabled()
        save_voice_enabled(enabled)

        if not enabled:
            winsound.PlaySound(None, 0)

        if enabled:
            notify("Voice unmuted.")
        else:
            notify("Voice muted.")

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

    def view_notes_dialog(self):
        try:
            recent_notes = api_client.get_recent_notes()
        except Exception as e:
            print(f"View notes error: {e}")
            notify("Could not load notes.")
            return

        notes_dialog = QDialog(self)
        notes_dialog.setWindowTitle("Recent Notes")
        notes_dialog.setModal(True)

        layout = QVBoxLayout(notes_dialog)
        notes_text = QTextEdit(notes_dialog)
        notes_text.setReadOnly(True)

        if not isinstance(recent_notes, list) or not recent_notes:
            notes_text.setPlainText("No recent notes.")
        else:
            entries = []

            for note_entry in recent_notes:
                if isinstance(note_entry, dict):
                    category = note_entry.get("category", "No category")
                    note_text_value = note_entry.get("note", "")
                    timestamp = self.format_note_timestamp_for_display(
                        note_entry.get("timestamp")
                    )
                else:
                    category = "No category"
                    note_text_value = note_entry
                    timestamp = "No timestamp"

                if not isinstance(category, str) or not category.strip():
                    category = "No category"

                if not isinstance(note_text_value, str):
                    note_text_value = str(note_text_value)

                entries.append(
                    "\n".join([
                        f"Category: {category}",
                        f"Note: {note_text_value}",
                        f"Timestamp: {timestamp}",
                    ])
                )

            notes_text.setPlainText("\n\n---\n\n".join(entries))

        layout.addWidget(notes_text)
        notes_dialog.resize(520, 360)
        notes_dialog.exec()

    def format_note_timestamp_for_display(self, timestamp):
        if not isinstance(timestamp, str) or not timestamp.strip():
            return "No timestamp"

        raw_timestamp = timestamp.strip()

        try:
            parsed_timestamp = datetime.fromisoformat(raw_timestamp)
            return parsed_timestamp.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return raw_timestamp

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
        if not voice_capture.audio_dependencies_available():
            notify("Voice Note requires sounddevice, soundfile, and numpy.")
            return

        sample_rate = 16000
        audio_frames = []
        recording_state = {"stopped": False}
        audio_callback = voice_capture.build_audio_callback(audio_frames)

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
            stream = voice_capture.start_input_stream(sample_rate, audio_callback)
            record_dialog.exec()
        except Exception as e:
            print(f"Voice recording error: {e}")
            notify("Could not start voice recording.")
            return
        finally:
            voice_capture.stop_and_close_stream(stream)

        if not recording_state["stopped"]:
            return

        if not audio_frames:
            notify("No audio captured.")
            return

        temp_audio_path = None
        transcript_text = ""

        try:
            temp_audio_path = voice_capture.create_temp_wav_from_frames(
                audio_frames,
                sample_rate
            )

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
            voice_capture.cleanup_temp_audio_file(temp_audio_path)

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
        self.set_avatar_position(new_position.x(), new_position.y())
        self.dragged = True
        event.accept()

    def mouseReleaseEvent(self, event):

        if event.button() != Qt.MouseButton.RightButton:
            return

        if self.dragged:
            avatar_x, avatar_y = self.get_avatar_position()
            save_avatar_position(avatar_x, avatar_y)

        self.drag_offset = None
        self.dragged = False
        event.accept()


class CompanionApplication:

    def __init__(self):
        global app

        app = QApplication(sys.argv)
        self.app = app

        self._ensure_ollama_ready()
        self._ensure_speech_server_ready()

        self._wire_notification_callbacks()
        self._setup_companion_widget()
        self._setup_notification_label()
        self._setup_avatar()
        self._setup_startup_notifications()
        self._setup_notification_server()
        self._create_windows_notification_listener()
        self._setup_shutdown_wiring()

    def _wire_notification_callbacks(self):
        bridge.notify_signal.connect(notify)
        register_notify_callback(bridge.notify_signal.emit)

    def _ensure_ollama_ready(self):
        is_ready, _ = probe_ollama_ready()
        if is_ready:
            print("Ollama already running; no launch needed.")
            return

        try:
            launched_process, command = launch_ollama_process()
        except RuntimeError as e:
            print(f"Ollama launch failed: {e}")
            QMessageBox.warning(
                None,
                "Ollama Unavailable",
                (
                    "Rivet could not start Ollama. "
                    "Please start Ollama manually and try again."
                )
            )
            raise RuntimeError("Ollama failed to launch") from e

        is_ready_after_launch, final_error = wait_for_speech_server_ready(
            timeout_seconds=OLLAMA_STARTUP_TIMEOUT_SEC,
            poll_interval_seconds=SPEECH_POLL_INTERVAL_SEC,
            process=launched_process,
            probe_fn=probe_ollama_ready,
        )

        if is_ready_after_launch:
            print("Ollama started by companion (unowned).")
            return

        print(f"Ollama did not become ready in time. Last error: {final_error}")
        QMessageBox.warning(
            None,
            "Ollama Unavailable",
            (
                "Rivet could not confirm Ollama is running. "
                "Please start Ollama manually and try again."
            )
        )
        raise RuntimeError("Ollama failed to become ready")

    def _ensure_speech_server_ready(self):
        global speech_server_process
        global speech_server_owned_by_companion

        is_ready, _ = probe_speech_server_ready()

        if is_ready:
            speech_server_process = None
            speech_server_owned_by_companion = False
            print("Speech server already running; ownership marked external.")
            return

        try:
            launched_process, command = launch_speech_server_process()
        except RuntimeError as e:
            print(
                "Speech server startup failed. "
                "Command: unavailable. "
                f"Final probe error: {e}"
            )

            QMessageBox.critical(
                None,
                "Speech Server Unavailable",
                (
                    "Rivet could not start the speech server. "
                    "Please ensure dependencies are installed and try again."
                )
            )

            raise RuntimeError("Speech server failed to launch") from e

        speech_server_process = launched_process

        is_ready_after_launch, final_error = wait_for_speech_server_ready(
            timeout_seconds=SPEECH_STARTUP_TIMEOUT_SEC,
            poll_interval_seconds=SPEECH_POLL_INTERVAL_SEC,
            process=launched_process,
        )

        if is_ready_after_launch:
            speech_server_owned_by_companion = True
            print("Speech server started by companion.")
            return

        print(
            "Speech server startup failed. "
            f"Command: {command}. "
            f"Final probe error: {final_error}"
        )

        terminate_managed_speech_server(timeout_seconds=2)

        QMessageBox.critical(
            None,
            "Speech Server Unavailable",
            (
                "Rivet could not start the speech server. "
                "Please ensure dependencies are installed and try again."
            )
        )

        raise RuntimeError("Speech server failed to start")

    def _setup_companion_widget(self):
        global label
        label = Companion()

    def _setup_notification_label(self):
        global notification_label

        notification_label = ThoughtBubbleWidget()

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

    def _setup_avatar(self):
        image_path = Path(__file__).parent / config["avatar"]

        pixmap = QPixmap(str(image_path))

        pixmap = pixmap.scaled(
            config["avatar_size"],
            config["avatar_size"],
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        label.setPixmap(pixmap)

        screen = QGuiApplication.primaryScreen()
        geometry = screen.availableGeometry()

        initial_x = geometry.width() - pixmap.width() - 20
        initial_y = geometry.height() - pixmap.height() - 20

        saved_position = saved_avatar_position()

        if saved_position is not None:
            initial_x, initial_y = saved_position

        label.set_avatar_position(initial_x, initial_y)

        label.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        label.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        label.show()

    def _setup_startup_notifications(self):
        startup_phrase = ask_ratchet("startup")

        notify(startup_phrase)

        print(startup_phrase)

        QTimer.singleShot(
            10000,
            lambda: notify(random.choice(notifications))
        )

    def _setup_notification_server(self):
        start_notification_server(
            host=NOTIFY_SERVER_HOST,
            port=NOTIFY_SERVER_PORT,
            chat_resolver=ask_ratchet
        )

    def _create_windows_notification_listener(self):
        try:
            start_windows_notification_listener()
            print("Windows notification listener started.")
        except Exception as e:
            print(f"Warning: Windows notification listener failed to start: {e}")

    def _setup_shutdown_wiring(self):
        self.app.aboutToQuit.connect(clean_exit)

    def run(self):
        return self.app.exec()


def main():
    try:
        companion_application = CompanionApplication()
    except RuntimeError as e:
        print(f"Startup error: {e}")
        sys.exit(1)

    return_code = companion_application.run()
    sys.exit(return_code)


if __name__ == "__main__":
    main()
