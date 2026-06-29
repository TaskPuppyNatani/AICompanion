import sys
import base64
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
    LOG_DIR,
    NOTIFY_SERVER_HOST,
    NOTIFY_SERVER_PORT,
    API_HOST,
    API_PORT,
)


from PyQt6.QtGui import (
    QPixmap,
    QKeySequence,
    QShortcut,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
    QColor,
    QTextOption,
    QImageReader,
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
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QTextEdit,
    QFileDialog,
)
from PyQt6.QtCore import (
    Qt,
    QObject,
    pyqtSignal,
    pyqtSlot,
    QThread,
    QTimer,
    QSize,
    QRectF,
    QByteArray,
    QBuffer,
    QIODevice,
    QEvent,
)
from companion_app.local_notify_server import (
    register_notify_callback,
    start_notification_server,
    stop_notification_server,
)
from companion_app.windows_notification_listener import (
    start_windows_notification_listener,
    stop_windows_notification_listener,
)

from config_store import (
    config,
    saved_avatar_position,
    save_avatar_position,
    set_config_value,
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
# Must exceed the largest profile startup_timeout_seconds so provider-owned
# startup can finish before the desktop gives up on the speech server.
SPEECH_STARTUP_TIMEOUT_SEC = 75
SPEECH_POLL_INTERVAL_SEC = 0.5

PROMPT_IMAGE_MAX_BYTES = 8 * 1024 * 1024
PROMPT_IMAGE_FORMAT_MIME_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}
PROMPT_IMAGE_FILE_FILTER = "Images (*.png *.jpg *.jpeg *.webp)"


def _format_qbytearray(value):
    try:
        return bytes(value).decode("ascii", errors="ignore").lower()
    except Exception:
        return ""


def _attachment_payload_from_image_bytes(image_bytes, mime_type, name):
    return {
        "type": "image",
        "mime_type": mime_type,
        "data_base64": base64.b64encode(image_bytes).decode("ascii"),
        "name": name,
    }


def _find_first_image_file_path(mime_data):
    if mime_data is None or not mime_data.hasUrls():
        return None

    for url in mime_data.urls():
        if not url.isLocalFile():
            continue

        candidate = Path(url.toLocalFile())
        suffix = candidate.suffix.lower().lstrip(".")

        if suffix in PROMPT_IMAGE_FORMAT_MIME_TYPES:
            return candidate

    return None
SPEECH_STARTUP_LOG_MAX_CHARS = 8000

AVATAR_MIN_SIZE = 64
AVATAR_MAX_SIZE = 320
AVATAR_RESIZE_STEP = 8


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


class PromptWindow(QWidget):
    submitRequested = pyqtSignal(str, object, object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rivet Prompt")
        self.setAcceptDrops(True)
        self.attachment = None
        self._base_style = self.styleSheet()
        self._geometry_ready = False

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(14, 14, 14, 14)

        self.prompt_editor = QTextEdit(self)
        self.prompt_editor.setPlaceholderText("Ask Rivet... Ctrl+Enter to submit")
        self.prompt_editor.setToolTip("Enter adds a new line. Ctrl+Enter submits.")
        self.prompt_editor.setAcceptRichText(False)
        self.prompt_editor.setMinimumHeight(120)
        self.prompt_editor.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.prompt_editor.installEventFilter(self)
        layout.addWidget(self.prompt_editor)

        attachment_layout = QHBoxLayout()
        attachment_layout.setSpacing(12)

        thumbnail_layout = QVBoxLayout()
        self.thumbnail_label = QLabel(self)
        self.thumbnail_label.setFixedSize(128, 128)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setText("Drop image")
        thumbnail_layout.addWidget(self.thumbnail_label)

        self.filename_label = QLabel(self)
        self.filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filename_label.setTextFormat(Qt.TextFormat.PlainText)
        self.filename_label.setWordWrap(True)
        self.filename_label.hide()
        thumbnail_layout.addWidget(self.filename_label)
        attachment_layout.addLayout(thumbnail_layout)

        attachment_button_layout = QVBoxLayout()

        browse_button = QPushButton("Attach Image", self)
        browse_button.clicked.connect(self.browse_image)
        attachment_button_layout.addWidget(browse_button)

        paste_button = QPushButton("Paste Image", self)
        paste_button.clicked.connect(self.paste_image)
        attachment_button_layout.addWidget(paste_button)

        self.remove_button = QPushButton("Remove", self)
        self.remove_button.clicked.connect(self.remove_image)
        self.remove_button.setEnabled(False)
        attachment_button_layout.addWidget(self.remove_button)
        attachment_button_layout.addStretch()

        attachment_layout.addLayout(attachment_button_layout)
        attachment_layout.addStretch()
        layout.addLayout(attachment_layout)

        action_layout = QHBoxLayout()

        self.microphone_button = QPushButton("Mic", self)
        self.microphone_button.setEnabled(False)
        self.microphone_button.setToolTip("Reserved for future dictation.")
        action_layout.addWidget(self.microphone_button)

        action_layout.addStretch()

        submit_button = QPushButton("Submit", self)
        submit_button.setToolTip("Submit prompt (Ctrl+Enter)")
        submit_button.clicked.connect(self.submit_prompt)
        action_layout.addWidget(submit_button)

        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.hide)
        action_layout.addWidget(close_button)

        layout.addLayout(action_layout)

        self.response_text = QTextEdit(self)
        self.response_text.setReadOnly(True)
        self.response_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.response_text.setMinimumHeight(260)
        layout.addWidget(self.response_text, 1)

        self.escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        self.escape_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.escape_shortcut.activated.connect(self.hide)

        self.submit_shortcut_return = QShortcut(
            QKeySequence("Ctrl+Return"),
            self,
        )
        self.submit_shortcut_return.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.submit_shortcut_return.activated.connect(self.submit_prompt)

        self.submit_shortcut_enter = QShortcut(
            QKeySequence("Ctrl+Enter"),
            self,
        )
        self.submit_shortcut_enter.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.submit_shortcut_enter.activated.connect(self.submit_prompt)

        self._geometry_save_timer = QTimer(self)
        self._geometry_save_timer.setSingleShot(True)
        self._geometry_save_timer.timeout.connect(self.save_geometry)

        self.restore_geometry()
        self._geometry_ready = True

    def restore_geometry(self):
        geometry = config.get("prompt_window_geometry")

        if isinstance(geometry, dict):
            try:
                x = int(geometry["x"])
                y = int(geometry["y"])
                width = max(480, int(geometry["width"]))
                height = max(420, int(geometry["height"]))
            except (KeyError, TypeError, ValueError):
                x = y = width = height = None

            if None not in (x, y, width, height):
                self.setGeometry(x, y, width, height)
                return

        self.resize(820, 680)

    def schedule_geometry_save(self):
        if not self._geometry_ready:
            return

        if self.isVisible():
            self._geometry_save_timer.start(400)

    def save_geometry(self):
        geometry = self.geometry()
        set_config_value(
            "prompt_window_geometry",
            {
                "x": geometry.x(),
                "y": geometry.y(),
                "width": geometry.width(),
                "height": geometry.height(),
            },
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.schedule_geometry_save()

    def moveEvent(self, event):
        super().moveEvent(event)
        self.schedule_geometry_save()

    def hideEvent(self, event):
        self.save_geometry()
        super().hideEvent(event)

    def closeEvent(self, event):
        self.save_geometry()
        event.ignore()
        self.hide()

    def show_workspace(self, initial_image_path=None):
        self.refresh_profile_title()

        if initial_image_path:
            self.attach_image_file(initial_image_path)

        self.show()
        self.raise_()
        self.activateWindow()
        self.focus_prompt_editor()

    def focus_prompt_editor(self):
        self.prompt_editor.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def refresh_profile_title(self):
        title = "Rivet Prompt"

        try:
            payload = api_client.get_model_profiles()
            profiles = payload.get("profiles", {})
            active_profile = payload.get("active_profile", "")
            profile = profiles.get(active_profile, {}) if isinstance(profiles, dict) else {}
            display_name = profile.get("display_name")

            if isinstance(display_name, str) and display_name.strip():
                title = f"Rivet Prompt • {display_name.strip()}"
        except Exception as e:
            print(f"Prompt profile title error: {e}")

        self.setWindowTitle(title)

    def _set_drop_highlight(self, enabled):
        if enabled:
            self.setStyleSheet("PromptWindow { border: 2px dashed #4f9cff; }")
        else:
            self.setStyleSheet(self._base_style)

    def dragEnterEvent(self, event):
        image_path = _find_first_image_file_path(event.mimeData())

        if image_path is None:
            event.ignore()
            return

        self._set_drop_highlight(True)
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._set_drop_highlight(False)
        event.accept()

    def dropEvent(self, event):
        self._set_drop_highlight(False)
        image_path = _find_first_image_file_path(event.mimeData())

        if image_path is None:
            event.ignore()
            return

        self.attach_image_file(image_path)
        event.acceptProposedAction()

    def eventFilter(self, watched, event):
        if watched is self.prompt_editor and event.type() == QEvent.Type.KeyPress:
            if (
                event.key() == Qt.Key.Key_V
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier
            ):
                clipboard = QGuiApplication.clipboard()
                mime_data = clipboard.mimeData()

                if (
                    _find_first_image_file_path(mime_data) is not None
                    or mime_data.hasImage()
                ):
                    self.paste_image()
                    event.accept()
                    return True

        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        if (
            event.key() == Qt.Key.Key_V
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            clipboard = QGuiApplication.clipboard()
            mime_data = clipboard.mimeData()

            if _find_first_image_file_path(mime_data) is not None or mime_data.hasImage():
                self.paste_image()
                event.accept()
                return

        super().keyPressEvent(event)

    def browse_image(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Attach Image",
            "",
            PROMPT_IMAGE_FILE_FILTER,
        )

        if file_name:
            self.attach_image_file(file_name)

    def paste_image(self):
        clipboard = QGuiApplication.clipboard()
        mime_data = clipboard.mimeData()
        image_path = _find_first_image_file_path(mime_data)

        if image_path is not None:
            self.attach_image_file(image_path)
            return

        image = clipboard.image()

        if image.isNull():
            self._show_image_error("Clipboard does not contain a supported image.")
            return

        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)

        if not image.save(buffer, "PNG"):
            self._show_image_error("Could not read the clipboard image.")
            return

        image_bytes = bytes(byte_array)

        if len(image_bytes) > PROMPT_IMAGE_MAX_BYTES:
            self._show_image_error(
                "Image is too large. Please use an image smaller than 8 MB."
            )
            return

        payload = _attachment_payload_from_image_bytes(
            image_bytes,
            "image/png",
            "clipboard.png",
        )
        pixmap = QPixmap.fromImage(image)
        self.set_attachment(payload, pixmap, None)

    def attach_image_file(self, file_path):
        image_path = Path(file_path)

        if not image_path.is_file():
            self._show_image_error("Image file could not be found.")
            return

        try:
            file_size = image_path.stat().st_size
        except OSError:
            self._show_image_error("Image file could not be read.")
            return

        if file_size > PROMPT_IMAGE_MAX_BYTES:
            self._show_image_error(
                "Image is too large. Please use an image smaller than 8 MB."
            )
            return

        reader = QImageReader(str(image_path))
        reader.setAutoTransform(True)
        image_format = _format_qbytearray(reader.format())
        mime_type = PROMPT_IMAGE_FORMAT_MIME_TYPES.get(image_format)

        if mime_type is None:
            self._show_image_error("Unsupported image type. Use PNG, JPEG, or WebP.")
            return

        image = reader.read()

        if image.isNull():
            self._show_image_error("Image file could not be decoded.")
            return

        try:
            image_bytes = image_path.read_bytes()
        except OSError:
            self._show_image_error("Image file could not be read.")
            return

        payload = _attachment_payload_from_image_bytes(
            image_bytes,
            mime_type,
            image_path.name,
        )
        pixmap = QPixmap.fromImage(image)
        self.set_attachment(payload, pixmap, image_path)

    def set_attachment(self, payload, pixmap, file_path):
        filename = payload.get("name", "image")
        self.attachment = {
            "payload": payload,
            "pixmap": pixmap,
            "path": str(file_path) if file_path is not None else None,
        }
        self.thumbnail_label.setText("")
        self.thumbnail_label.setPixmap(
            pixmap.scaled(
                self.thumbnail_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.filename_label.setText(filename if isinstance(filename, str) else "image")
        self.filename_label.show()
        self.remove_button.setEnabled(True)

    def remove_image(self):
        self.attachment = None
        self.thumbnail_label.clear()
        self.thumbnail_label.setText("Drop image")
        self.filename_label.clear()
        self.filename_label.hide()
        self.remove_button.setEnabled(False)

    def _show_image_error(self, message):
        QMessageBox.warning(self, "Image unavailable", message)

    def prompt_text(self):
        return self.prompt_editor.toPlainText().strip()

    def backend_attachments(self):
        if not self.attachment:
            return []

        return [self.attachment["payload"]]

    def display_attachments(self):
        if not self.attachment:
            return []

        return [self.attachment]

    def submit_prompt(self):
        prompt = self.prompt_text()

        if not prompt:
            self.focus_prompt_editor()
            return

        self.submitRequested.emit(
            prompt,
            self.backend_attachments(),
            self.display_attachments(),
        )

    def clear_after_successful_submit(self):
        self.prompt_editor.clear()
        self.remove_image()
        self.focus_prompt_editor()

    def show_response(self, prompt, response, profile_name=None, attachments=None):
        _ = (prompt, profile_name, attachments)
        self.response_text.setPlainText("" if response is None else str(response))
        self.show_workspace()

notifications = [
    "New email received.",
    "Rivet reports all services healthy.",
    "Ratchet reports all services healthy.",
    "Container restarted successfully.",
]


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
    cwd = speech_server_path.parent

    command = [
        sys.executable,
        str(speech_server_path),
    ]

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stdout_path = LOG_DIR / "speech_server_startup_stdout.log"
    stderr_path = LOG_DIR / "speech_server_startup_stderr.log"

    launch_context = {
        "command": command,
        "python": sys.executable,
        "cwd": str(cwd),
        "speech_server_path": str(speech_server_path),
        "stdout_path": stdout_path,
        "stderr_path": stderr_path,
    }

    stdout_file = None
    stderr_file = None

    try:
        stdout_file = open(stdout_path, "w", encoding="utf-8", errors="replace")
        stderr_file = open(stderr_path, "w", encoding="utf-8", errors="replace")
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=stdout_file,
            stderr=stderr_file,
        )
    except Exception as e:
        raise RuntimeError(
            f"Launch failed for command {command}: {e}"
        ) from e
    finally:
        if stdout_file is not None:
            stdout_file.close()

        if stderr_file is not None:
            stderr_file.close()

    return process, launch_context


def read_speech_server_startup_log(path):
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except Exception as e:
        return f"Could not read log file {path}: {e}"

    if not text:
        return "No output captured."

    if len(text) > SPEECH_STARTUP_LOG_MAX_CHARS:
        return "... [truncated]\n" + text[-SPEECH_STARTUP_LOG_MAX_CHARS:]

    return text


def format_speech_server_exit_diagnostic(launch_context, return_code):
    command = launch_context.get("command", [])
    stdout_path = launch_context.get("stdout_path")
    stderr_path = launch_context.get("stderr_path")

    return (
        "Speech server exited during startup.\n\n"
        "Command:\n"
        f"{subprocess.list2cmdline(command)}\n\n"
        "Python:\n"
        f"{launch_context.get('python')}\n\n"
        "Working directory:\n"
        f"{launch_context.get('cwd')}\n\n"
        "Speech server path:\n"
        f"{launch_context.get('speech_server_path')}\n\n"
        "Exit code:\n"
        f"{return_code}\n\n"
        "stderr:\n"
        f"{read_speech_server_startup_log(stderr_path)}\n\n"
        "stdout:\n"
        f"{read_speech_server_startup_log(stdout_path)}"
    )


def format_speech_server_startup_failure(final_error):
    if final_error and final_error.startswith("Speech server exited during startup."):
        return final_error

    return (
        "Rivet could not confirm the speech server is ready.\n\n"
        "Last probe error:\n"
        f"{final_error or 'Timed out waiting for the speech server health check.'}"
    )


def wait_for_speech_server_ready(timeout_seconds, poll_interval_seconds, process=None, launch_context=None, probe_fn=probe_speech_server_ready):
    deadline = time.monotonic() + timeout_seconds
    last_error = None

    while time.monotonic() < deadline:
        if process is not None:
            return_code = process.poll()

            if return_code is not None:
                if launch_context is not None:
                    return False, format_speech_server_exit_diagnostic(launch_context, return_code)

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

def ask_ratchet(event="click", sender=None, interaction_data=None):
    start_time = time.perf_counter()
    try:
        response = api_client.chat(event, sender, interaction_data=interaction_data)

        return response["response"]

    except Exception as e:
        print(f"Chat error: {e}")
        return "Ratchet seems to be thinking too hard right now."
    finally:
        if event == "click":
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            print(f"[AI CLICK PERF] ask_ratchet {elapsed_ms:.2f} ms")


INTERACTION_NOT_STARTED = object()


class InteractionWorker(QObject):
    interaction_completed = pyqtSignal(str, bool, object)

    @pyqtSlot(str, object)
    def run_interaction(self, kind, args):
        try:
            if kind == "ai_click":
                result = ask_ratchet()
            else:
                raise ValueError(f"Unsupported interaction kind: {kind}")
        except Exception as e:
            print(f"Interaction worker error: {e}")
            self.interaction_completed.emit(kind, False, str(e))
            return

        self.interaction_completed.emit(kind, True, result)


class InteractionManager(QObject):
    interaction_requested = pyqtSignal(str, object)

    def __init__(self):
        super().__init__()
        self.active_interaction = None
        self.active_completion_callback = None
        self.active_interaction_perf_start = None
        self.worker_thread = None
        self.worker = None

    @property
    def current_interaction(self):
        return self.active_interaction

    @property
    def is_busy(self):
        return self.active_interaction is not None

    @property
    def is_interacting(self):
        return self.is_busy

    def begin_interaction(self, kind, **metadata):
        if self.is_busy:
            return False

        interaction = {
            "kind": kind,
            "started_at": datetime.now().isoformat(),
        }
        interaction.update(metadata)

        self.active_interaction = interaction
        return True

    def end_interaction(self):
        self.active_interaction = None

    def execute_interaction(self, kind, handler, *args, **metadata):
        if not self.begin_interaction(kind, **metadata):
            if kind == "ai_click":
                print(f"[AI CLICK PERF] interaction_manager not_started kind={kind}")
            return INTERACTION_NOT_STARTED

        start_time = time.perf_counter()
        try:
            return handler(*args)
        finally:
            if kind == "ai_click":
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                print(
                    f"[AI CLICK PERF] interaction_manager.execute_interaction "
                    f"{elapsed_ms:.2f} ms kind={kind}"
                )
            self.end_interaction()

    def execute_interaction_async(self, kind, on_complete, *args, **metadata):
        if not self.begin_interaction(kind, **metadata):
            if kind == "ai_click":
                print(f"[AI CLICK PERF] interaction_manager not_started kind={kind}")
            return INTERACTION_NOT_STARTED

        self._ensure_worker_started()
        self.active_completion_callback = on_complete
        self.active_interaction_perf_start = time.perf_counter()
        self.interaction_requested.emit(kind, args)
        return None

    def _ensure_worker_started(self):
        if self.worker_thread is not None and self.worker_thread.isRunning():
            return

        self.worker_thread = QThread()
        self.worker = InteractionWorker()
        self.worker.moveToThread(self.worker_thread)
        self.interaction_requested.connect(self.worker.run_interaction)
        self.worker.interaction_completed.connect(self._handle_worker_completion)
        self.worker_thread.finished.connect(self.worker.deleteLater)
        self.worker_thread.start()

    def _handle_worker_completion(self, kind, success, result):
        callback = self.active_completion_callback

        try:
            if callback is not None:
                callback(kind, success, result)
        finally:
            if kind == "ai_click" and self.active_interaction_perf_start is not None:
                elapsed_ms = (
                    time.perf_counter() - self.active_interaction_perf_start
                ) * 1000
                print(
                    f"[AI CLICK PERF] interaction_manager.execute_interaction "
                    f"{elapsed_ms:.2f} ms kind={kind}"
                )

            self.active_completion_callback = None
            self.active_interaction_perf_start = None
            self.end_interaction()

    def shutdown(self):
        if self.worker_thread is not None and self.worker_thread.isRunning():
            self.worker_thread.quit()
            if not self.worker_thread.wait(3000):
                print("Interaction worker thread did not stop before timeout.")


interaction_manager = InteractionManager()


def dispatch_speech(message):
    threading.Thread(
        target=speak,
        args=(message,),
        daemon=True
    ).start()


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

    dispatch_speech(message)

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

    interaction_manager.shutdown()

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
        self.avatar_source_pixmap = None
        self.avatar_size = None
        self.avatar_resized = False
        self.prompt_window = PromptWindow()
        self.prompt_window.submitRequested.connect(self.submit_prompt_from_window)
        self.prompt_shortcut = QShortcut(QKeySequence("Ctrl+Space"), self)
        self.prompt_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.prompt_shortcut.activated.connect(self.open_prompt_dialog)
        self.context_menu = QMenu(self)
        self.model_profiles_menu = self.context_menu.addMenu("Model Profiles")
        self.model_profiles_menu.aboutToShow.connect(
            self.refresh_model_profiles_menu
        )

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

        self.refresh_model_profiles_menu()

    def set_avatar_position(self, new_x, new_y):
        self.avatar_x = int(new_x)
        self.avatar_y = int(new_y)
        self.move(self.avatar_x, self.avatar_y)

        if notification_label is not None and notification_label.isVisible():
            self.update_notification_bubble_position()

    def get_avatar_position(self):
        return self.avatar_x, self.avatar_y

    def resize_avatar(self, new_size: int):
        if self.avatar_source_pixmap is None:
            return

        avatar_size = max(AVATAR_MIN_SIZE, min(AVATAR_MAX_SIZE, int(new_size)))
        self.avatar_size = avatar_size

        pixmap = self.avatar_source_pixmap.scaled(
            avatar_size,
            avatar_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.setPixmap(pixmap)
        self.resize(pixmap.size())

        if notification_label is not None and notification_label.isVisible():
            self.update_notification_bubble_position()

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

    def refresh_model_profiles_menu(self):
        self.model_profiles_menu.clear()

        try:
            payload = api_client.get_model_profiles()
        except Exception as e:
            print(f"Load model profiles error: {e}")
            unavailable_action = self.model_profiles_menu.addAction(
                "Profiles unavailable"
            )
            unavailable_action.setEnabled(False)
            return

        profiles = payload.get("profiles", {})
        active_profile = payload.get("active_profile", "")

        if not isinstance(profiles, dict) or not profiles:
            empty_action = self.model_profiles_menu.addAction("No profiles configured")
            empty_action.setEnabled(False)
            return

        for profile_key, profile in profiles.items():
            if not isinstance(profile, dict):
                continue

            display_name = profile.get("display_name")
            if not isinstance(display_name, str) or not display_name.strip():
                display_name = str(profile_key).replace("_", " ").title()

            action = self.model_profiles_menu.addAction(display_name.strip())
            action.setCheckable(True)
            action.setChecked(profile_key == active_profile)
            action.triggered.connect(
                lambda checked=False, key=profile_key: self.switch_model_profile(key)
            )

    def switch_model_profile(self, profile_key):
        try:
            payload = api_client.set_active_model_profile(profile_key)
        except Exception as e:
            print(f"Switch model profile error: {e}")
            notify("Could not switch model profile.")
            return

        if payload.get("status") != "success":
            notify("Could not switch model profile.")
            return

        profile = payload.get("profile", {})
        display_name = profile.get("display_name")
        if not isinstance(display_name, str) or not display_name.strip():
            display_name = str(profile_key).replace("_", " ").title()

        self.refresh_model_profiles_menu()
        self.prompt_window.refresh_profile_title()
        notify(f"Switched to {display_name.strip()} profile.")

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

    def note_editor_dialog(self, title="Note Editor", note_entry=None):
        editor_dialog = QDialog(self)
        editor_dialog.setWindowTitle(title)
        editor_dialog.setModal(True)

        layout = QVBoxLayout(editor_dialog)

        note_text = QTextEdit(editor_dialog)
        category_input = QLineEdit(editor_dialog)
        category_input.setPlaceholderText("Category (optional)")

        if isinstance(note_entry, dict):
            note_value = note_entry.get("note", "")
            category_value = note_entry.get("category", "")
        elif note_entry is None:
            note_value = ""
            category_value = ""
        else:
            note_value = str(note_entry)
            category_value = ""

        note_text.setPlainText(
            note_value if isinstance(note_value, str) else str(note_value)
        )
        category_input.setText(
            category_value if isinstance(category_value, str) else ""
        )

        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        cancel_button = QPushButton("Cancel")
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)

        result = {
            "accepted": False,
            "note": "",
            "category": "",
        }

        def save_note_edits():
            edited_note = note_text.toPlainText().strip()

            if not edited_note:
                QMessageBox.warning(
                    editor_dialog,
                    "Note Editor",
                    "Note text is required."
                )
                return

            result["accepted"] = True
            result["note"] = edited_note
            result["category"] = category_input.text().strip()
            editor_dialog.accept()

        save_button.clicked.connect(save_note_edits)
        cancel_button.clicked.connect(editor_dialog.reject)

        layout.addWidget(QLabel("Note:", editor_dialog))
        layout.addWidget(note_text)
        layout.addWidget(QLabel("Category:", editor_dialog))
        layout.addWidget(category_input)
        layout.addLayout(button_layout)

        editor_dialog.resize(420, 260)
        editor_dialog.exec()

        return result["note"], result["category"], result["accepted"]

    def view_notes_dialog(self):
        notes_dialog = QDialog(self)
        notes_dialog.setWindowTitle("Notes")
        notes_dialog.setModal(True)

        layout = QVBoxLayout(notes_dialog)
        notes_list = QListWidget(notes_dialog)
        notes_list.setWordWrap(True)

        button_layout = QHBoxLayout()
        edit_button = QPushButton("Edit")
        delete_button = QPushButton("Delete")
        close_button = QPushButton("Close")
        edit_button.setEnabled(False)
        delete_button.setEnabled(False)
        button_layout.addWidget(edit_button)
        button_layout.addWidget(delete_button)
        button_layout.addWidget(close_button)

        def format_note_item(note_entry):
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

            return "\n".join([
                f"Category: {category}",
                f"Note: {note_text_value}",
                f"Timestamp: {timestamp}",
            ])

        def update_delete_button():
            current_item = notes_list.currentItem()
            note_index = None

            if current_item is not None:
                note_index = current_item.data(Qt.ItemDataRole.UserRole)

            has_note_selection = isinstance(note_index, int)
            edit_button.setEnabled(has_note_selection)
            delete_button.setEnabled(has_note_selection)

        def load_note_items():
            notes_list.clear()

            try:
                all_notes = api_client.get_notes()
            except Exception as e:
                print(f"View notes error: {e}")
                notify("Could not load notes.")
                edit_button.setEnabled(False)
                delete_button.setEnabled(False)
                return

            if not isinstance(all_notes, list) or not all_notes:
                empty_item = QListWidgetItem("No notes.")
                empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
                notes_list.addItem(empty_item)
                edit_button.setEnabled(False)
                delete_button.setEnabled(False)
                return

            for note_index in range(len(all_notes) - 1, -1, -1):
                note_entry = all_notes[note_index]
                item = QListWidgetItem(format_note_item(note_entry))
                item.setData(Qt.ItemDataRole.UserRole, note_index)
                item.setData(Qt.ItemDataRole.UserRole + 1, note_entry)
                notes_list.addItem(item)

            update_delete_button()

        def edit_selected_note():
            current_item = notes_list.currentItem()

            if current_item is None:
                return

            note_index = current_item.data(Qt.ItemDataRole.UserRole)
            note_entry = current_item.data(Qt.ItemDataRole.UserRole + 1)

            if not isinstance(note_index, int):
                return

            edited_note, edited_category, accepted = self.note_editor_dialog(
                title="Edit Note",
                note_entry=note_entry
            )

            if not accepted:
                return

            try:
                payload = api_client.update_note(
                    note_index,
                    edited_note,
                    edited_category
                )
            except Exception as e:
                print(f"Update note error: {e}")
                notify("Could not update note.")
                return

            if payload.get("status") != "updated":
                notify("Could not update note.")
                return

            notify("Note updated.")
            load_note_items()

        def delete_selected_note():
            current_item = notes_list.currentItem()

            if current_item is None:
                return

            note_index = current_item.data(Qt.ItemDataRole.UserRole)

            if not isinstance(note_index, int):
                return

            confirmation = QMessageBox.question(
                notes_dialog,
                "Delete Note",
                "Delete the selected note?",
                (
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                ),
                QMessageBox.StandardButton.No
            )

            if confirmation != QMessageBox.StandardButton.Yes:
                return

            try:
                payload = api_client.delete_note(note_index)
            except Exception as e:
                print(f"Delete note error: {e}")
                notify("Could not delete note.")
                return

            if payload.get("status") != "deleted":
                notify("Could not delete note.")
                return

            notify("Note deleted.")
            load_note_items()

        edit_button.clicked.connect(edit_selected_note)
        delete_button.clicked.connect(delete_selected_note)
        close_button.clicked.connect(notes_dialog.accept)
        notes_list.currentItemChanged.connect(
            lambda current, previous: update_delete_button()
        )

        load_note_items()

        layout.addWidget(notes_list)
        layout.addLayout(button_layout)
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

    def open_prompt_dialog(self, initial_image_path=None):
        self.prompt_window.show_workspace(initial_image_path=initial_image_path)

    def submit_prompt_from_window(self, user_prompt, attachments, display_attachments):
        if not user_prompt:
            return

        interaction_data = {
            "prompt": user_prompt,
        }

        if attachments:
            interaction_data["attachments"] = attachments

        phrase = interaction_manager.execute_interaction(
            "prompt",
            lambda: ask_ratchet(
                "prompt",
                interaction_data=interaction_data,
            ),
            prompt=user_prompt
        )

        if phrase is INTERACTION_NOT_STARTED:
            self.prompt_window.focus_prompt_editor()
            return

        print(phrase)

        self.prompt_window.show_response(
            user_prompt,
            phrase,
            attachments=display_attachments,
        )
        self.prompt_window.clear_after_successful_submit()
        dispatch_speech(phrase)

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

        def complete_ai_click(kind, success, result):
            _ = kind
            phrase = result if success else "Ratchet seems to be thinking too hard right now."

            print(phrase)
            notify(phrase)

        started = interaction_manager.execute_interaction_async(
            "ai_click",
            complete_ai_click,
        )

        if started is INTERACTION_NOT_STARTED:
            return

    def wheelEvent(self, event):
        buttons = event.buttons()

        if not buttons & Qt.MouseButton.RightButton:
            buttons = QApplication.mouseButtons()

        if not buttons & Qt.MouseButton.RightButton:
            super().wheelEvent(event)
            return

        delta = event.angleDelta().y()

        if delta == 0:
            event.accept()
            return

        current_size = self.avatar_size

        if current_size is None:
            pixmap = self.pixmap()
            if pixmap is None:
                event.accept()
                return

            current_size = max(pixmap.width(), pixmap.height())

        direction = 1 if delta > 0 else -1
        self.resize_avatar(current_size + (direction * AVATAR_RESIZE_STEP))
        self.avatar_resized = True
        event.accept()

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

        if self.avatar_resized and self.avatar_size is not None:
            set_config_value("avatar_size", self.avatar_size)

        self.drag_offset = None
        self.dragged = False
        self.avatar_resized = False
        event.accept()


class CompanionApplication:

    def __init__(self):
        global app

        app = QApplication(sys.argv)
        self.app = app

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
            launched_process, launch_context = launch_speech_server_process()
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
            launch_context=launch_context,
        )

        if is_ready_after_launch:
            speech_server_owned_by_companion = True
            print("Speech server started by companion.")
            return

        print(
            "Speech server startup failed. "
            f"Command: {launch_context['command']}. "
            f"Final probe error: {final_error}"
        )

        terminate_managed_speech_server(timeout_seconds=2)

        QMessageBox.critical(
            None,
            "Speech Server Unavailable",
            format_speech_server_startup_failure(final_error)
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
        label.avatar_source_pixmap = pixmap
        label.resize_avatar(config["avatar_size"])

        display_pixmap = label.pixmap()

        screen = QGuiApplication.primaryScreen()
        geometry = screen.availableGeometry()

        initial_x = geometry.width() - display_pixmap.width() - 20
        initial_y = geometry.height() - display_pixmap.height() - 20

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
