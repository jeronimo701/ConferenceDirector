from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class TimerLogic(QObject):
    time_changed = Signal(str)
    finished = Signal()
    pre_alert = Signal()

    def __init__(self):
        super().__init__()
        self.duration = 0
        self.time_left = 0
        self.pre_alert_time = 0
        self.pre_alert_triggered = False
        self.is_paused = False
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)

    def start(self, duration, pre_alert_minutes):
        self.duration = duration
        self.time_left = duration
        self.pre_alert_time = pre_alert_minutes * 60
        self.pre_alert_triggered = False
        self.is_paused = False
        self.timer.start(1000)
        self.emit_time()

    def tick(self):
        if self.is_paused:
            return
        if self.time_left > 0:
            self.time_left -= 1
            self.emit_time()
            if self.time_left <= self.pre_alert_time and not self.pre_alert_triggered:
                self.pre_alert_triggered = True
                self.pre_alert.emit()
            return
        self.timer.stop()
        self.emit_time()
        self.finished.emit()

    def emit_time(self):
        minutes, seconds = divmod(self.time_left, 60)
        hours, minutes = divmod(minutes, 60)
        self.time_changed.emit(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    def pause_toggle(self):
        self.is_paused = not self.is_paused

    def reset(self):
        self.time_left = self.duration
        self.pre_alert_triggered = False
        self.emit_time()

    def stop(self):
        self.timer.stop()


class OutlinedLabel(QWidget):
    def __init__(self):
        super().__init__()
        self.text = "00:00:00"
        self.font = QFont("Arial", 160)
        self.text_color = QColor("white")
        self.outline_color = QColor("black")
        self.outline_width = 4
        self.visible = True
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self.toggle_visibility)

    def set_text(self, text):
        self.text = text
        self.update()

    def set_style(self, font, text_color, outline_color, outline_width):
        self.font = font
        self.text_color = text_color
        self.outline_color = outline_color
        self.outline_width = outline_width
        self.update()

    def start_blink(self):
        self.blink_timer.start(500)

    def stop_blink(self):
        self.blink_timer.stop()
        self.visible = True
        self.update()

    def toggle_visibility(self):
        self.visible = not self.visible
        self.update()

    def paintEvent(self, event):
        if not self.visible:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(self.font)
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance("00:00:00")
        x = (self.width() - text_width) // 2
        y = (self.height() + metrics.height()) // 2 - metrics.descent()
        painter.setPen(self.outline_color)
        for dx in range(-self.outline_width, self.outline_width + 1):
            for dy in range(-self.outline_width, self.outline_width + 1):
                if dx or dy:
                    painter.drawText(x + dx, y + dy, self.text)
        painter.setPen(self.text_color)
        painter.drawText(x, y, self.text)


class FullScreenTimer(QWidget):
    def __init__(self, screen, settings):
        super().__init__()
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setStyleSheet("background-color: black;")
        self.setScreen(screen)
        self.setGeometry(screen.geometry())

        self.background = QLabel(self)
        self.background.setScaledContents(True)
        self.background.setGeometry(self.rect())
        if settings["bg_path"]:
            self.background.setPixmap(QPixmap(settings["bg_path"]))

        self.label = OutlinedLabel()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
        self.label.set_style(
            QFont(settings["font"], settings["font_size"]),
            settings["text_color"],
            settings["outline_color"],
            settings["outline_width"],
        )
        self.showFullScreen()
        self.setGeometry(screen.geometry())

    def resizeEvent(self, event):
        self.background.setGeometry(self.rect())

    def update_time(self, text):
        self.label.set_text(text)
