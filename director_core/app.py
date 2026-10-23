import os
import random
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QFileDialog, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QDialog, QMainWindow, QMessageBox, QPushButton, QSpinBox, QTabWidget, QTextEdit,
    QButtonGroup, QSlider, QVBoxLayout, QWidget,
)

from director_core.executables import edge_extra_paths, existing_exe, powerpoint_extra_paths
from director_core.image_show import FullScreenImage
from director_core.paths import ROOT
from director_core.process_manager import ProcessManager
from director_core.project_scanner import list_project_dirs, scan_project
from director_core.screens import app_screens, display_switch, move_widget_to_screen, screen_index_of_widget, screen_title
from director_core.settings import load_settings, save_settings
from director_core.telegram_connect_dialog import TelegramChatFinderDialog, telegram_api_json
from director_core.telegram_receiver import TelegramReceiver
from director_core.timer import FullScreenTimer, TimerLogic


class ConferenceDirector(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Conference Director")
        self.resize(1180, 760)
        self.settings = load_settings()
        self.pdf_fit_width = bool(self.settings.get("pdf_fit_width", True))
        self.pdf_fit_width_checkboxes = []
        self.sort_modes = {
            "presentation_sort": self.settings.get("presentation_sort", "name"),
            "image_sort": self.settings.get("image_sort", "name"),
            "video_sort": self.settings.get("video_sort", "name"),
        }
        self.presentation_mode = self.settings["presentation_mode"]
        self.projects_root = Path(self.settings.get("projects_root") or ROOT)
        self.processes = ProcessManager()
        self.telegram_receiver = None
        self.telegram_token_edit = QLineEdit(self.settings["telegram_token"])
        self.telegram_chat_id_edit = QLineEdit(self.settings["telegram_chat_id"])
        self.telegram_token_edit.setEchoMode(QLineEdit.Password)
        self.timer_logic = TimerLogic()
        self.timer_window = None
        self.image_window = None
        self.carousel_paths = []
        self.carousel_index = 0
        self.carousel_timer = QTimer()
        self.carousel_timer.timeout.connect(self.next_carousel_image)

        self.audio = QAudioOutput()
        self.alarm = QMediaPlayer()
        self.alarm.setAudioOutput(self.audio)
        self.audio.setVolume(float(self.settings["timer_volume"]) / 100.0)
        self.load_alarm_sound(self.settings.get("timer_sound_path", ""))
        self.music_audio = QAudioOutput()
        self.music_player = QMediaPlayer()
        self.music_player.setAudioOutput(self.music_audio)
        self.music_audio.setVolume(float(self.settings["music_volume"]) / 100.0)
        self.music_player.mediaStatusChanged.connect(self.on_music_media_status_changed)
        self.music_process = None
        self.music_history = []

        self.timer_logic.time_changed.connect(self.on_timer_changed)
        self.timer_logic.finished.connect(self.on_timer_finished)
        self.timer_logic.pre_alert.connect(self.play_alarm)

        self.build_ui()
        self.refresh_screens()
        self.refresh_projects()

    def build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)

        top = QHBoxLayout()
        self.project_combo = QComboBox()
        self.project_combo.currentIndexChanged.connect(self.load_selected_project)
        self.projects_root_label = QLabel("")
        self.screen_combo = QComboBox()
        self.screen_combo.currentIndexChanged.connect(self.update_control_screen_status)
        select_projects_root_btn = QPushButton("Папка проектов")
        refresh_projects_btn = QPushButton("Обновить папки")
        refresh_screens_btn = QPushButton("Обновить мониторы")
        close_btn = QPushButton("Закрыть вывод")
        select_projects_root_btn.clicked.connect(self.select_projects_root)
        refresh_projects_btn.clicked.connect(self.refresh_projects)
        refresh_screens_btn.clicked.connect(self.refresh_screens)
        close_btn.clicked.connect(self.close_output)
        top.addWidget(QLabel("Проект"))
        top.addWidget(self.project_combo, 2)
        top.addWidget(select_projects_root_btn)
        top.addWidget(refresh_projects_btn)
        top.addWidget(QLabel("Вывод"))
        top.addWidget(self.screen_combo, 3)
        top.addWidget(refresh_screens_btn)
        top.addWidget(close_btn)
        root.addLayout(top)
        root.addWidget(self.projects_root_label)

        displays = QHBoxLayout()
        clone_btn = QPushButton("Дублировать экраны")
        extend_btn = QPushButton("Расширить экраны")
        swap_btn = QPushButton("Поменять местами пульт и вывод")
        clone_btn.clicked.connect(lambda: self.switch_display("/clone"))
        extend_btn.clicked.connect(lambda: self.switch_display("/extend"))
        swap_btn.clicked.connect(self.swap_control_and_output_screens)
        displays.addWidget(clone_btn)
        displays.addWidget(extend_btn)
        displays.addWidget(swap_btn)
        displays.addStretch()
        root.addLayout(displays)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.make_control_tab(), "Пульт")
        self.tabs.addTab(self.make_music_tab(), "Музыка")
        self.tabs.addTab(self.make_presentations_tab(), "Презентации")
        self.tabs.addTab(self.make_images_tab(), "Картинки")
        self.tabs.addTab(self.make_videos_tab(), "Видео")
        self.tabs.addTab(self.make_timer_tab(), "Таймер")
        self.tabs.addTab(self.make_quiz_tab(), "Квиз")
        self.tabs.addTab(self.make_telegram_tab(), "Telegram")
        self.tabs.addTab(self.make_settings_tab(), "Настройки")
        root.addWidget(self.tabs, 1)

        self.status_label = QLabel("Готово")
        self.last_received_label = QLabel("Принятые файлы: пока ничего не принимали")
        self.control_screen_label = QLabel("")
        root.addWidget(self.control_screen_label)
        root.addWidget(self.status_label)
        root.addWidget(self.last_received_label)
        self.setCentralWidget(central)
        self.update_control_screen_status()

    def make_control_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("Очередь конференции. Добавляйте сюда нужные файлы из вкладок ниже, ставьте порядок и запускайте по одному."))

        self.run_list = QListWidget()
        self.run_list.itemDoubleClicked.connect(lambda _: self.launch_selected_run_item())
        layout.addWidget(self.run_list, 1)

        run_buttons = QHBoxLayout()
        start_btn = QPushButton("ПУСК")
        start_btn.setMinimumHeight(64)
        start_btn.setStyleSheet("QPushButton { background: #14883f; color: white; font-size: 26px; font-weight: 700; }")
        start_btn.clicked.connect(self.launch_selected_run_item)
        close_btn = QPushButton("ЗАКРЫТЬ ОКНО")
        close_btn.setMinimumHeight(64)
        close_btn.setStyleSheet("QPushButton { background: #b3261e; color: white; font-size: 22px; font-weight: 700; }")
        close_btn.clicked.connect(self.close_output)
        run_buttons.addWidget(start_btn, 2)
        run_buttons.addWidget(close_btn, 1)
        layout.addLayout(run_buttons)

        queue_buttons = QHBoxLayout()
        next_btn = QPushButton("СЛЕДУЮЩЕЕ")
        next_btn.setMinimumSize(180, 64)
        next_btn.setStyleSheet("QPushButton { font-size: 22px; font-weight: 700; }")
        next_btn.clicked.connect(self.launch_next_run_item)
        quiz_btn = QPushButton("КВИЗ")
        quiz_btn.setMinimumSize(180, 64)
        quiz_btn.setStyleSheet("QPushButton { background: #1267b3; color: white; font-size: 22px; font-weight: 700; }")
        quiz_btn.clicked.connect(self.launch_primary_quiz)
        move_buttons = QVBoxLayout()
        up_btn = QPushButton("Вверх")
        down_btn = QPushButton("Вниз")
        up_btn.clicked.connect(lambda: self.move_current_item(self.run_list, -1))
        down_btn.clicked.connect(lambda: self.move_current_item(self.run_list, 1))
        move_buttons.addWidget(up_btn)
        move_buttons.addWidget(down_btn)
        queue_buttons.addWidget(next_btn)
        queue_buttons.addWidget(quiz_btn)
        queue_buttons.addLayout(move_buttons)
        remove_btn = QPushButton("УБРАТЬ ИЗ ОЧЕРЕДИ")
        remove_btn.setMinimumSize(220, 64)
        remove_btn.setStyleSheet("QPushButton { font-size: 18px; font-weight: 700; }")
        remove_btn.clicked.connect(self.remove_selected_run_item)
        queue_buttons.addWidget(remove_btn)
        layout.addLayout(queue_buttons)

        timer_buttons = QHBoxLayout()
        timer_buttons.addWidget(QLabel("Таймер"))
        for minutes in (15, 30, 45, 60, 75, 90):
            btn = QPushButton(f"{minutes} мин")
            btn.clicked.connect(lambda checked=False, value=minutes: self.start_timer_preset(value))
            timer_buttons.addWidget(btn)
        timer_buttons.addStretch()
        telegram_btn = QPushButton("Telegram старт")
        telegram_btn.clicked.connect(self.start_telegram_receiver)
        timer_buttons.addWidget(telegram_btn)
        layout.addLayout(timer_buttons)

        self.pdf_fit_width_control_checkbox = QCheckBox("PDF: по ширине (FitH)")
        self.register_pdf_fit_checkbox(self.pdf_fit_width_control_checkbox)
        layout.addWidget(self.pdf_fit_width_control_checkbox)
        return tab

    def make_music_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        top = QHBoxLayout()
        self.music_folder_label = QLabel(self.settings.get("music_folder") or "Папка музыки не выбрана")
        folder_btn = QPushButton("Выбрать папку")
        folder_btn.clicked.connect(self.select_music_folder)
        top.addWidget(folder_btn)
        top.addWidget(self.music_folder_label, 1)
        layout.addLayout(top)

        lists = QHBoxLayout()
        local_box = QVBoxLayout()
        link_box = QVBoxLayout()
        local_box.addWidget(QLabel("Файлы из папки"))
        link_box.addWidget(QLabel("Ссылки: YouTube / Яндекс / VK / другое"))
        self.music_file_list = QListWidget()
        self.music_file_list.itemDoubleClicked.connect(lambda _: self.play_selected_music_file())
        self.music_link_list = QListWidget()
        self.music_link_list.itemDoubleClicked.connect(lambda _: self.play_selected_music_link())
        local_box.addWidget(self.music_file_list, 1)
        link_box.addWidget(self.music_link_list, 1)
        lists.addLayout(local_box, 1)
        lists.addLayout(link_box, 1)
        layout.addLayout(lists, 1)

        self.music_url_edit = QLineEdit()
        self.music_url_edit.setPlaceholderText("https://music.yandex.ru/... или https://youtube.com/...")
        layout.addWidget(self.music_url_edit)

        options = QHBoxLayout()
        self.music_shuffle_checkbox = QCheckBox("Шафл")
        self.music_shuffle_checkbox.setChecked(bool(self.settings["music_shuffle"]))
        self.music_repeat_combo = QComboBox()
        self.music_repeat_combo.addItem("повторять весь плейлист", "all")
        self.music_repeat_combo.addItem("повторять один трек", "one")
        self.music_repeat_combo.addItem("не повторять", "none")
        self.music_repeat_combo.setCurrentIndex(max(0, self.music_repeat_combo.findData(self.settings["music_repeat_mode"])))
        self.music_volume_slider = QSlider(Qt.Horizontal)
        self.music_volume_slider.setRange(0, 100)
        self.music_volume_slider.setValue(int(self.settings["music_volume"]))
        self.music_volume_slider.valueChanged.connect(self.set_music_volume)
        self.music_shuffle_checkbox.toggled.connect(self.persist_settings)
        self.music_repeat_combo.currentIndexChanged.connect(self.persist_settings)
        for widget in (self.music_shuffle_checkbox, QLabel("Повтор"), self.music_repeat_combo, QLabel("Громкость"), self.music_volume_slider):
            options.addWidget(widget)
        layout.addLayout(options)

        transport = QHBoxLayout()
        file_play_btn = QPushButton("ПУСК ФАЙЛ")
        file_play_btn.setMinimumHeight(60)
        file_play_btn.setStyleSheet("QPushButton { background: #14883f; color: white; font-size: 22px; font-weight: 700; }")
        file_play_btn.clicked.connect(self.play_selected_music_file)
        link_play_btn = QPushButton("ПУСК ССЫЛКА")
        link_play_btn.setMinimumHeight(60)
        link_play_btn.setStyleSheet("QPushButton { background: #1267b3; color: white; font-size: 22px; font-weight: 700; }")
        link_play_btn.clicked.connect(self.play_selected_music_link)
        stop_btn = QPushButton("СТОП")
        stop_btn.setMinimumHeight(60)
        stop_btn.setStyleSheet("QPushButton { background: #b3261e; color: white; font-size: 22px; font-weight: 700; }")
        stop_btn.clicked.connect(self.stop_music)
        transport.addWidget(file_play_btn)
        transport.addWidget(link_play_btn)
        transport.addWidget(stop_btn)
        layout.addLayout(transport)

        buttons = QHBoxLayout()
        for label, handler in (
            ("Следующий файл", self.play_next_music_file),
            ("Убрать файл из списка", self.remove_selected_music_file),
            ("Добавить ссылку", self.add_music_link),
            ("Убрать ссылку", self.remove_selected_music_link),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            buttons.addWidget(btn)
        layout.addLayout(buttons)

        self.music_now_label = QLabel("Музыка: ничего не играет")
        layout.addWidget(self.music_now_label)
        self.load_music_playlists()
        return tab

    def make_presentations_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.presentation_list = QListWidget()
        self.presentation_list.itemDoubleClicked.connect(lambda _: self.launch_selected_presentation())
        layout.addWidget(QLabel("Порядок можно менять. PDF -> Edge kiosk, PPT/PPTX -> PowerPoint /S."))
        self.pdf_fit_width_presentations_checkbox = QCheckBox("PDF: подгонять по ширине (FitH)")
        self.register_pdf_fit_checkbox(self.pdf_fit_width_presentations_checkbox)
        layout.addWidget(self.pdf_fit_width_presentations_checkbox)
        layout.addWidget(self.sort_button_row("presentation_sort"))
        layout.addWidget(self.presentation_list, 1)
        buttons = QHBoxLayout()
        for label, handler in (
            ("Вверх", self.move_presentation_up),
            ("Вниз", self.move_presentation_down),
            ("Добавить в пульт", self.add_selected_presentation_to_run_list),
            ("Запустить выбранную", self.launch_selected_presentation),
            ("Следующая", self.launch_next_presentation),
            ("Закрыть окно", self.close_output),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            buttons.addWidget(btn)
        layout.addLayout(buttons)
        return tab

    def make_images_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.image_list = QListWidget()
        self.image_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.image_list.itemDoubleClicked.connect(lambda _: self.show_selected_image())
        self.carousel_spin = QSpinBox()
        self.carousel_spin.setRange(1, 240)
        self.carousel_spin.setValue(int(self.settings["carousel_minutes"]))
        self.carousel_spin.setSuffix(" мин")
        layout.addWidget(self.sort_button_row("image_sort"))
        layout.addWidget(self.image_list, 1)
        buttons = QHBoxLayout()
        show_btn = QPushButton("Показать выбранную")
        add_btn = QPushButton("Добавить в пульт")
        carousel_btn = QPushButton("Карусель выбранных")
        next_btn = QPushButton("Следующая картинка")
        close_btn = QPushButton("Закрыть окно")
        show_btn.clicked.connect(self.show_selected_image)
        add_btn.clicked.connect(self.add_selected_image_to_run_list)
        carousel_btn.clicked.connect(self.start_carousel)
        next_btn.clicked.connect(self.next_carousel_image)
        close_btn.clicked.connect(self.close_output)
        for widget in (show_btn, add_btn, QLabel("Интервал"), self.carousel_spin, carousel_btn, next_btn, close_btn):
            buttons.addWidget(widget)
        layout.addLayout(buttons)
        return tab

    def make_videos_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.video_list = QListWidget()
        self.video_list.itemDoubleClicked.connect(lambda _: self.launch_selected_video())
        launch_btn = QPushButton("Запустить видео")
        add_btn = QPushButton("Добавить в пульт")
        close_btn = QPushButton("Закрыть окно")
        launch_btn.clicked.connect(self.launch_selected_video)
        add_btn.clicked.connect(self.add_selected_video_to_run_list)
        close_btn.clicked.connect(self.close_output)
        layout.addWidget(self.sort_button_row("video_sort"))
        layout.addWidget(self.video_list, 1)
        layout.addWidget(add_btn)
        layout.addWidget(launch_btn)
        layout.addWidget(close_btn)
        return tab

    def sort_button_row(self, setting_key):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Сортировка"))

        group = QButtonGroup(widget)
        group.setExclusive(True)
        for label, mode in (("Название", "name"), ("Новые", "time_desc"), ("Старые", "time_asc")):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(self.sort_modes.get(setting_key, "name") == mode)
            btn.clicked.connect(lambda checked=False, key=setting_key, value=mode: self.set_sort_mode(key, value))
            group.addButton(btn)
            layout.addWidget(btn)
        layout.addStretch()
        return widget

    def set_sort_mode(self, setting_key, sort_mode):
        self.sort_modes[setting_key] = sort_mode
        self.settings[setting_key] = sort_mode
        save_settings(self.settings)
        self.load_selected_project()

    def register_pdf_fit_checkbox(self, checkbox):
        checkbox.setChecked(self.pdf_fit_width)
        checkbox.toggled.connect(
            lambda checked, source=checkbox: self.on_pdf_fit_width_toggled(source, checked)
        )
        self.pdf_fit_width_checkboxes.append(checkbox)

    def on_pdf_fit_width_toggled(self, source, checked):
        self.pdf_fit_width = bool(checked)
        for checkbox in self.pdf_fit_width_checkboxes:
            if checkbox is source:
                continue
            blocked = checkbox.blockSignals(True)
            checkbox.setChecked(self.pdf_fit_width)
            checkbox.blockSignals(blocked)
        self.settings["pdf_fit_width"] = self.pdf_fit_width
        save_settings(self.settings)

    def populate_font_combo(self):
        scalable = {family for family in QFontDatabase.families() if QFontDatabase.isSmoothlyScalable(family)}
        families = sorted(scalable | {"Arial"})
        for family in families:
            self.font_combo.addItem(f"{family}    12:34", family)
            row = self.font_combo.count() - 1
            self.font_combo.setItemData(row, QFont(family, 14), Qt.FontRole)

    def set_current_font_from_settings(self):
        saved_font = self.settings.get("timer_font", "Arial")
        index = self.font_combo.findData(saved_font)
        if index < 0:
            index = self.font_combo.findData("Arial")
        if index >= 0:
            self.font_combo.setCurrentIndex(index)

    def save_timer_font(self):
        self.settings["timer_font"] = self.font_combo.currentData() or self.font_combo.currentText()
        save_settings(self.settings)

    def load_music_playlists(self):
        self.music_file_list.clear()
        for path_text in self.settings.get("music_files", []):
            path = Path(path_text)
            if path.exists():
                self.add_music_file_item(path)
        self.music_link_list.clear()
        for url in self.settings.get("music_links", []):
            self.add_music_link_item(url)

    def add_music_file_item(self, path):
        item = QListWidgetItem(path.name)
        item.setData(Qt.UserRole, str(path))
        item.setToolTip(str(path))
        self.music_file_list.addItem(item)
        if self.music_file_list.currentRow() < 0:
            self.music_file_list.setCurrentRow(0)

    def add_music_link_item(self, url):
        item = QListWidgetItem(url)
        item.setData(Qt.UserRole, url)
        self.music_link_list.addItem(item)
        if self.music_link_list.currentRow() < 0:
            self.music_link_list.setCurrentRow(0)

    def select_music_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Папка с музыкой",
            self.settings.get("music_folder") or str(ROOT),
        )
        if not folder:
            return
        self.settings["music_folder"] = folder
        self.music_folder_label.setText(folder)
        paths = self.scan_music_folder(Path(folder))
        self.music_file_list.clear()
        for path in paths:
            self.add_music_file_item(path)
        self.save_music_playlists()

    def scan_music_folder(self, folder):
        audio_exts = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma"}
        return sorted(
            [path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in audio_exts],
            key=lambda path: path.name.lower(),
        )

    def save_music_playlists(self):
        self.settings["music_files"] = [
            self.music_file_list.item(row).data(Qt.UserRole)
            for row in range(self.music_file_list.count())
        ]
        self.settings["music_links"] = [
            self.music_link_list.item(row).data(Qt.UserRole)
            for row in range(self.music_link_list.count())
        ]
        self.settings["music_folder"] = self.music_folder_label.text() if self.settings.get("music_folder") else ""
        save_settings(self.settings)

    def selected_music_file_path(self):
        item = self.music_file_list.currentItem()
        return Path(item.data(Qt.UserRole)) if item else None

    def selected_music_link(self):
        item = self.music_link_list.currentItem()
        return item.data(Qt.UserRole) if item else ""

    def play_selected_music_file(self):
        path = self.selected_music_file_path()
        if not path:
            return
        self.play_music_file(path)

    def play_music_file(self, path):
        self.stop_music_link()
        self.music_player.setSource(QUrl.fromLocalFile(str(path)))
        self.music_player.play()
        self.music_now_label.setText(f"Музыка: {path.name}")
        self.save_music_playlists()

    def play_selected_music_link(self):
        url = self.selected_music_link() or self.music_url_edit.text().strip()
        if not url:
            return
        if "://" not in url:
            url = "https://" + url
        self.stop_music()
        exe = existing_exe(self.edge_path.text().strip(), ["msedge.exe"], edge_extra_paths())
        geo = self.selected_screen().availableGeometry()
        width = max(640, geo.width() // 2)
        height = max(420, geo.height() // 2)
        left = geo.x() + geo.width() - width
        top = geo.y()
        try:
            self.music_process = subprocess.Popen([
                exe,
                "--new-window",
                f"--window-position={left},{top}",
                f"--window-size={width},{height}",
                url,
            ])
            self.music_now_label.setText(f"Музыка-ссылка: {url}")
        except OSError as exc:
            QMessageBox.warning(self, "Музыка", f"Не удалось открыть ссылку:\n{exc}")

    def add_music_link(self):
        url = self.music_url_edit.text().strip()
        if not url:
            return
        if "://" not in url:
            url = "https://" + url
        if url not in self.settings.get("music_links", []):
            self.add_music_link_item(url)
        self.music_url_edit.clear()
        self.save_music_playlists()

    def remove_selected_music_file(self):
        row = self.music_file_list.currentRow()
        if row >= 0:
            self.music_file_list.takeItem(row)
            self.save_music_playlists()

    def remove_selected_music_link(self):
        row = self.music_link_list.currentRow()
        if row >= 0:
            self.music_link_list.takeItem(row)
            self.save_music_playlists()

    def set_music_volume(self, value):
        self.music_audio.setVolume(float(value) / 100.0)
        self.settings["music_volume"] = int(value)
        save_settings(self.settings)

    def stop_music(self):
        self.music_player.stop()
        self.stop_music_link()
        self.music_now_label.setText("Музыка: стоп")

    def stop_music_link(self):
        if self.music_process and self.music_process.poll() is None:
            self.processes.close_process(self.music_process)
        self.music_process = None

    def on_music_media_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia:
            repeat_mode = self.music_repeat_combo.currentData() if hasattr(self, "music_repeat_combo") else "all"
            if repeat_mode == "one":
                self.play_selected_music_file()
            elif repeat_mode == "all":
                self.play_next_music_file()

    def play_next_music_file(self):
        if not self.music_file_list.count():
            return
        if self.music_shuffle_checkbox.isChecked() and self.music_file_list.count() > 1:
            row = self.music_file_list.currentRow()
            choices = [i for i in range(self.music_file_list.count()) if i != row]
            next_row = random.choice(choices)
        else:
            row = self.music_file_list.currentRow()
            next_row = 0 if row < 0 or row + 1 >= self.music_file_list.count() else row + 1
        self.music_file_list.setCurrentRow(next_row)
        self.play_selected_music_file()

    def make_timer_tab(self):
        tab = QWidget()
        layout = QGridLayout(tab)
        self.timer_label = QLabel("00:00:00")
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setStyleSheet("font-size: 42px; font-weight: bold;")
        self.time_spin = QSpinBox()
        self.time_spin.setRange(1, 300)
        self.time_spin.setValue(45)
        self.time_spin.setSuffix(" мин")
        self.pre_alert_spin = QSpinBox()
        self.pre_alert_spin.setRange(1, 60)
        self.pre_alert_spin.setValue(5)
        self.pre_alert_spin.setSuffix(" мин до конца")
        self.font_combo = QComboBox()
        self.populate_font_combo()
        self.set_current_font_from_settings()
        self.font_combo.currentIndexChanged.connect(self.save_timer_font)
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(40, 400)
        self.font_size_spin.setValue(200)
        self.outline_width_spin = QSpinBox()
        self.outline_width_spin.setRange(0, 30)
        self.outline_width_spin.setValue(4)
        self.text_color = QColor("white")
        self.outline_color = QColor("black")
        self.change_color_checkbox = QCheckBox("Красный цвет в конце")
        self.change_color_checkbox.setChecked(True)
        self.gradient_checkbox = QCheckBox("Плавно краснеть к концу")

        preset_layout = QHBoxLayout()
        for minutes in (15, 30, 45, 60, 75):
            btn = QPushButton(f"{minutes} мин")
            btn.clicked.connect(lambda checked=False, value=minutes: self.time_spin.setValue(value))
            preset_layout.addWidget(btn)

        start_btn = QPushButton("Старт таймера на экран")
        pause_btn = QPushButton("Пауза")
        reset_btn = QPushButton("Сброс")
        bg_btn = QPushButton("Фон таймера")
        text_btn = QPushButton("Цвет цифр")
        outline_btn = QPushButton("Цвет обводки")
        sound_btn = QPushButton("Звук таймера")
        test_sound_btn = QPushButton("Проверить звук")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(self.settings["timer_volume"]))
        start_btn.clicked.connect(self.start_timer)
        pause_btn.clicked.connect(self.timer_logic.pause_toggle)
        reset_btn.clicked.connect(self.timer_logic.reset)
        bg_btn.clicked.connect(self.select_timer_background)
        text_btn.clicked.connect(self.pick_text_color)
        outline_btn.clicked.connect(self.pick_outline_color)
        sound_btn.clicked.connect(self.select_alarm_sound)
        test_sound_btn.clicked.connect(self.play_alarm)
        self.volume_slider.valueChanged.connect(self.set_alarm_volume)

        layout.addWidget(self.timer_label, 0, 0, 1, 4)
        layout.addWidget(QLabel("Время"), 1, 0)
        layout.addWidget(self.time_spin, 1, 1)
        layout.addWidget(QLabel("Предупреждение"), 1, 2)
        layout.addWidget(self.pre_alert_spin, 1, 3)
        layout.addLayout(preset_layout, 2, 0, 1, 4)
        layout.addWidget(QLabel("Шрифт"), 3, 0)
        layout.addWidget(self.font_combo, 3, 1, 1, 3)
        layout.addWidget(QLabel("Размер"), 4, 0)
        layout.addWidget(self.font_size_spin, 4, 1)
        layout.addWidget(QLabel("Обводка"), 4, 2)
        layout.addWidget(self.outline_width_spin, 4, 3)
        layout.addWidget(bg_btn, 5, 0)
        layout.addWidget(text_btn, 5, 1)
        layout.addWidget(outline_btn, 5, 2)
        layout.addWidget(self.change_color_checkbox, 6, 0, 1, 2)
        layout.addWidget(self.gradient_checkbox, 6, 2, 1, 2)
        layout.addWidget(sound_btn, 7, 0)
        layout.addWidget(test_sound_btn, 7, 1)
        layout.addWidget(QLabel("Громкость"), 7, 2)
        layout.addWidget(self.volume_slider, 7, 3)
        layout.addWidget(start_btn, 8, 0, 1, 2)
        layout.addWidget(pause_btn, 8, 2)
        layout.addWidget(reset_btn, 8, 3)
        close_btn = QPushButton("Закрыть окно")
        close_btn.clicked.connect(self.close_output)
        layout.addWidget(close_btn, 9, 0, 1, 4)
        layout.setRowStretch(10, 1)
        return tab

    def make_quiz_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("Ссылки сохраняются. Запуск идет в Edge kiosk на выбранный монитор."))
        self.quiz_list = QListWidget()
        self.quiz_list.currentItemChanged.connect(lambda *_: self.update_primary_quiz_label())
        self.quiz_list.itemDoubleClicked.connect(lambda _: self.launch_selected_quiz())
        self.primary_quiz_label = QLabel("")
        self.quiz_url = QLineEdit()
        self.quiz_url.setPlaceholderText("https://...")
        buttons = QHBoxLayout()
        add_btn = QPushButton("Добавить ссылку")
        remove_btn = QPushButton("Удалить")
        primary_btn = QPushButton("Сделать основной")
        launch_btn = QPushButton("Запустить квиз")
        close_btn = QPushButton("Закрыть окно")
        add_btn.clicked.connect(self.add_quiz_link)
        remove_btn.clicked.connect(self.remove_quiz_link)
        primary_btn.clicked.connect(self.set_selected_quiz_primary)
        launch_btn.clicked.connect(self.launch_selected_quiz)
        close_btn.clicked.connect(self.close_output)
        for widget in (add_btn, remove_btn, primary_btn, launch_btn, close_btn):
            buttons.addWidget(widget)
        layout.addWidget(self.primary_quiz_label)
        layout.addWidget(self.quiz_list, 1)
        layout.addWidget(self.quiz_url)
        layout.addLayout(buttons)
        self.refresh_quiz_links()
        return tab

    def make_telegram_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.telegram_info_label = QLabel("")
        self.telegram_info_label.setWordWrap(True)
        layout.addWidget(self.telegram_info_label)
        layout.addWidget(self.telegram_box())

        self.telegram_bot_link_label = QLabel("Ссылка на бота: нажми 'Получить ссылку на бота'")
        self.telegram_bot_link_label.setOpenExternalLinks(True)
        self.telegram_bot_link_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        layout.addWidget(self.telegram_bot_link_label)

        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setPlainText(
            "Как передать файл через Telegram:\n\n"
            "1. Один раз открой вкладку 'Настройки' и вставь Bot token.\n"
            "2. Нажми 'Найти чат'. Если список пустой - сначала напиши любое сообщение боту или в группу с ботом.\n"
            "3. Выбери найденный chat_id. Настройки сохранятся автоматически.\n"
            "4. Выбери сверху нужный проект/конференцию. Файлы будут попадать именно в эту папку.\n"
            "5. Нажми 'Старт приема'. После этого можно отправлять боту pptx, pdf, картинки, видео и другие документы.\n"
            "6. Когда файл скачался, он появится в своей вкладке: презентации, картинки или видео. Чтобы поставить его в программу конференции, добавь его в пульт из этой вкладки.\n\n"
            "Важно: кнопка 'Telegram старт' не отправляет файл. Она включает приемник. Файлы отправляешь обычным сообщением в Telegram."
        )
        layout.addWidget(instructions, 1)

        self.update_telegram_tab_info()
        return tab

    def make_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.powerpoint_path = QLineEdit(self.settings["powerpoint_path"])
        self.edge_path = QLineEdit(self.settings["edge_path"])
        self.video_player_path = QLineEdit(self.settings["video_player_path"])
        self.video_preset_combo = QComboBox()
        self.video_preset_combo.addItems(["VLC", "PotPlayer", "KMPlayer", "Windows Media Player", "Custom"])
        self.video_preset_combo.setCurrentText(self.settings["video_preset"])
        self.powerpoint_mode_combo = QComboBox()
        self.powerpoint_mode_combo.addItem("Только показ / без окна редактора", "slide_show")
        self.powerpoint_mode_combo.addItem("Открыть окно PowerPoint / я нажму F5 сам", "edit_window")
        self.powerpoint_mode_combo.setCurrentIndex(
            max(0, self.powerpoint_mode_combo.findData(self.settings["presentation_mode"]))
        )
        self.pdf_fit_width_checkbox = QCheckBox("PDF: подгонять по ширине (FitH)")
        self.register_pdf_fit_checkbox(self.pdf_fit_width_checkbox)
        layout.addWidget(self.path_box("PowerPoint EXE", self.powerpoint_path, self.browse_powerpoint))
        layout.addWidget(self.powerpoint_mode_box())
        layout.addWidget(self.pdf_fit_width_checkbox)
        layout.addWidget(self.path_box("Microsoft Edge EXE", self.edge_path, self.browse_edge))
        layout.addWidget(self.video_box())
        note = QTextEdit()
        note.setReadOnly(True)
        note.setMaximumHeight(140)
        note.setPlainText(
            "PowerPoint: в режиме показа программа запускает POWERPNT.EXE с ключом /S. Если показ открылся не там, перетащи окно или выбери нужный монитор внутри PowerPoint.\n\n"
            "PDF/квиз: Edge запускается с --kiosk и координатами выбранного монитора. "
            "Для PDF можно включать/выключать подгонку по ширине.\n\n"
            "Видео: выберите пресет и, если программа не находится автоматически, укажите путь к EXE."
        )
        layout.addWidget(note)
        save_btn = QPushButton("Сохранить настройки")
        save_btn.clicked.connect(self.persist_settings)
        close_btn = QPushButton("Закрыть окно вывода")
        close_btn.clicked.connect(self.close_output)
        layout.addWidget(save_btn)
        layout.addWidget(close_btn)
        layout.addStretch()
        return tab

    def powerpoint_mode_box(self):
        box = QGroupBox("Режим запуска PowerPoint")
        layout = QVBoxLayout(box)
        layout.addWidget(self.powerpoint_mode_combo)
        return box

    def telegram_box(self):
        box = QGroupBox("Telegram бот: прием файлов в текущий проект")
        layout = QGridLayout(box)
        connect_btn = QPushButton("Найти чат")
        start_btn = QPushButton("Старт приема")
        stop_btn = QPushButton("Стоп")
        link_btn = QPushButton("Получить ссылку на бота")
        save_btn = QPushButton("Сохранить")
        connect_btn.clicked.connect(self.open_telegram_connect_dialog)
        start_btn.clicked.connect(self.start_telegram_receiver)
        stop_btn.clicked.connect(lambda: self.stop_telegram_receiver(wait=True))
        link_btn.clicked.connect(self.fetch_telegram_bot_link)
        save_btn.clicked.connect(self.persist_settings)
        layout.addWidget(QLabel("Bot token"), 0, 0)
        layout.addWidget(self.telegram_token_edit, 0, 1, 1, 3)
        layout.addWidget(connect_btn, 0, 4)
        layout.addWidget(QLabel("Chat ID"), 1, 0)
        layout.addWidget(self.telegram_chat_id_edit, 1, 1, 1, 3)
        layout.addWidget(save_btn, 1, 4)
        layout.addWidget(start_btn, 2, 1)
        layout.addWidget(stop_btn, 2, 2)
        layout.addWidget(link_btn, 2, 3, 1, 2)
        return box

    def path_box(self, title, line_edit, browse_handler):
        box = QGroupBox(title)
        layout = QHBoxLayout(box)
        browse_btn = QPushButton("Обзор")
        browse_btn.clicked.connect(browse_handler)
        layout.addWidget(line_edit, 1)
        layout.addWidget(browse_btn)
        return box

    def video_box(self):
        box = QGroupBox("Видео-плеер")
        layout = QGridLayout(box)
        browse_btn = QPushButton("Обзор")
        browse_btn.clicked.connect(self.browse_video_player)
        layout.addWidget(QLabel("Пресет"), 0, 0)
        layout.addWidget(self.video_preset_combo, 0, 1, 1, 2)
        layout.addWidget(QLabel("Путь"), 1, 0)
        layout.addWidget(self.video_player_path, 1, 1)
        layout.addWidget(browse_btn, 1, 2)
        return box

    def refresh_projects(self):
        current = self.project_combo.currentData()
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        for path in list_project_dirs(self.projects_root):
            self.project_combo.addItem(path.name, str(path))
        self.project_combo.blockSignals(False)
        self.projects_root_label.setText(f"Папка проектов: {self.projects_root}")
        preferred = current or self.settings.get("last_project_path", "")
        index = self.project_combo.findData(preferred) if preferred else 0
        if index >= 0:
            self.project_combo.setCurrentIndex(index)
        self.load_selected_project()

    def select_projects_root(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Папка с проектами",
            str(self.projects_root if self.projects_root.exists() else ROOT),
        )
        if not folder:
            return
        self.projects_root = Path(folder)
        self.settings["projects_root"] = str(self.projects_root)
        save_settings(self.settings)
        self.refresh_projects()

    def refresh_screens(self):
        self.screen_combo.clear()
        for index, screen in enumerate(app_screens()):
            self.screen_combo.addItem(screen_title(screen, index), index)
        if self.screen_combo.count() > 1:
            self.screen_combo.setCurrentIndex(1)
        self.update_control_screen_status()

    def update_control_screen_status(self):
        if not hasattr(self, "control_screen_label"):
            return
        screens = app_screens()
        if not screens:
            self.control_screen_label.setText("Мониторы не найдены")
            return
        control_index = screen_index_of_widget(self)
        output_index = self.screen_combo.currentData() if hasattr(self, "screen_combo") else 0
        if output_index is None:
            output_index = 0
        self.control_screen_label.setText(
            f"Пульт сейчас на мониторе {control_index + 1}. Вывод выбран: монитор {int(output_index) + 1}."
        )

    def moveEvent(self, event):
        super().moveEvent(event)
        QTimer.singleShot(0, self.update_control_screen_status)

    def load_selected_project(self):
        data = self.project_combo.currentData()
        if not data:
            return
        project = scan_project(data)
        resolved_path = str(project.path.resolve())
        if self.settings.get("last_project_path") != resolved_path:
            self.settings["last_project_path"] = resolved_path
            save_settings(self.settings)
        self.fill_file_list(self.presentation_list, self.sorted_paths(project.presentations, self.sort_modes["presentation_sort"]))
        self.fill_file_list(self.image_list, self.sorted_paths(project.images, self.sort_modes["image_sort"]))
        self.fill_file_list(self.video_list, self.sorted_paths(project.videos, self.sort_modes["video_sort"]))
        self.load_project_queue(project.path)
        self.update_telegram_tab_info()
        self.set_status(
            f"Проект: {project.path.name}. Презентаций: {self.presentation_list.count()}, "
            f"картинок: {self.image_list.count()}, видео: {self.video_list.count()}"
        )

    def fill_file_list(self, widget, paths):
        widget.clear()
        for path in paths:
            item = QListWidgetItem(self.file_list_title(path))
            item.setData(Qt.UserRole, str(path))
            item.setToolTip(str(path))
            widget.addItem(item)
        if widget.count():
            widget.setCurrentRow(0)

    def sorted_paths(self, paths, sort_mode):
        if sort_mode == "time_desc":
            return sorted(paths, key=self.path_mtime, reverse=True)
        if sort_mode == "time_asc":
            return sorted(paths, key=self.path_mtime)
        return sorted(paths, key=lambda path: path.name.lower())

    def path_mtime(self, path):
        try:
            return path.stat().st_mtime
        except OSError:
            return 0

    def file_list_title(self, path):
        try:
            stamp = datetime.fromtimestamp(path.stat().st_mtime).strftime("%H:%M %d.%m.%y")
        except OSError:
            stamp = "--:-- --.--.--"
        return f"{path.name}        {stamp}"

    def selected_screen(self):
        screens = app_screens()
        index = self.screen_combo.currentData()
        if index is None or index >= len(screens):
            return screens[0]
        return screens[index]

    def selected_project_dir(self):
        data = self.project_combo.currentData()
        return Path(data) if data else None

    def selected_project_key(self):
        project_dir = self.selected_project_dir()
        return str(project_dir.resolve()) if project_dir else ""

    def selected_path(self, list_widget):
        item = list_widget.currentItem()
        return Path(item.data(Qt.UserRole)) if item else None

    def update_telegram_tab_info(self):
        if not hasattr(self, "telegram_info_label"):
            return
        project_dir = self.selected_project_dir()
        project_name = project_dir.name if project_dir else "не выбран"
        token_status = "указан" if self.settings.get("telegram_token") or getattr(self, "telegram_token_edit", None) and self.telegram_token_edit.text().strip() else "не указан"
        chat_id = self.settings.get("telegram_chat_id", "")
        if hasattr(self, "telegram_chat_id_edit") and self.telegram_chat_id_edit.text().strip():
            chat_id = self.telegram_chat_id_edit.text().strip()
        receiver_status = "прием включен" if self.telegram_receiver else "прием выключен"
        self.telegram_info_label.setText(
            f"Проект для загрузки: {project_name}. Token: {token_status}. Chat ID: {chat_id or 'не выбран'}. Сейчас: {receiver_status}."
        )

    def close_output(self):
        self.carousel_timer.stop()
        self.timer_logic.stop()
        self.processes.close_all()
        if self.timer_window:
            try:
                self.timer_logic.time_changed.disconnect(self.timer_window.update_time)
            except RuntimeError:
                pass
            self.timer_window.close()
            self.timer_window = None
        if self.image_window:
            self.image_window.close()
            self.image_window = None
        self.set_status("Вывод закрыт")

    def launch_selected_presentation(self):
        path = self.selected_path(self.presentation_list)
        if path:
            self.launch_presentation(path)

    def add_selected_presentation_to_run_list(self):
        path = self.selected_path(self.presentation_list)
        if path:
            self.add_run_item("presentation", path, self.run_item_title("presentation", path))

    def add_selected_image_to_run_list(self):
        for item in self.image_list.selectedItems():
            path = Path(item.data(Qt.UserRole))
            self.add_run_item("image", path, self.run_item_title("image", path))

    def add_selected_video_to_run_list(self):
        path = self.selected_path(self.video_list)
        if path:
            self.add_run_item("video", path, self.run_item_title("video", path))

    def add_run_item(self, kind, path, title):
        item = QListWidgetItem(title)
        item.setData(Qt.UserRole, {"kind": kind, "path": str(path)})
        self.run_list.addItem(item)
        if self.run_list.currentRow() < 0:
            self.run_list.setCurrentRow(0)
        self.save_current_queue()

    def remove_selected_run_item(self):
        row = self.run_list.currentRow()
        if row >= 0:
            self.run_list.takeItem(row)
            if self.run_list.count():
                self.run_list.setCurrentRow(min(row, self.run_list.count() - 1))
            self.save_current_queue()

    def load_project_queue(self, project_dir):
        if not hasattr(self, "run_list"):
            return
        self.run_list.clear()
        queues = self.settings.get("project_queues", {})
        queue = queues.get(str(project_dir.resolve()), queues.get(project_dir.name, []))
        for saved in queue:
            path = Path(saved.get("path", ""))
            kind = saved.get("kind", "")
            if not path.exists() or kind not in {"presentation", "image", "video"}:
                continue
            self.add_run_item(kind, path, self.run_item_title(kind, path))
        if self.run_list.count():
            self.run_list.setCurrentRow(0)

    def save_current_queue(self):
        key = self.selected_project_key()
        if not key or not hasattr(self, "run_list"):
            return
        self.settings.setdefault("project_queues", {})[key] = [
            self.run_list.item(row).data(Qt.UserRole)
            for row in range(self.run_list.count())
        ]
        save_settings(self.settings)

    def run_item_title(self, kind, path):
        labels = {"presentation": "Презентация", "image": "Картинка", "video": "Видео"}
        return f"{labels.get(kind, kind)}: {path.name}"

    def launch_selected_run_item(self):
        item = self.run_list.currentItem()
        if not item:
            return
        data = item.data(Qt.UserRole)
        self.launch_run_data(data)

    def launch_next_run_item(self):
        if not self.run_list.count():
            return
        row = self.run_list.currentRow()
        next_row = 0 if row < 0 or row + 1 >= self.run_list.count() else row + 1
        self.run_list.setCurrentRow(next_row)
        self.launch_selected_run_item()

    def launch_run_data(self, data):
        kind = data["kind"]
        path = Path(data["path"])
        if kind == "presentation":
            self.launch_presentation(path)
        elif kind == "image":
            self.show_image(path)
        elif kind == "video":
            self.launch_video(path)

    def launch_next_presentation(self):
        if not self.presentation_list.count():
            return
        row = self.presentation_list.currentRow()
        next_row = 0 if row < 0 or row + 1 >= self.presentation_list.count() else row + 1
        self.presentation_list.setCurrentRow(next_row)
        self.launch_selected_presentation()

    def launch_presentation(self, path):
        if path.suffix.lower() == ".pdf":
            self.launch_edge_kiosk(self.pdf_kiosk_url(path))
            self.set_status(f"PDF: {path.name}")
            return

        self.close_output()
        exe = existing_exe(self.powerpoint_path.text().strip(), ["POWERPNT.EXE", "powerpnt.exe"], powerpoint_extra_paths())
        mode = self.powerpoint_mode_combo.currentData()
        if mode == "slide_show":
            args = [exe, "/S", str(path)]
        else:
            args = [exe, str(path)]
        try:
            self.processes.start(args)
            mode_text = "показ" if mode == "slide_show" else "окно редактора"
            self.set_status(f"PowerPoint {mode_text}: {path.name}")
        except OSError as exc:
            QMessageBox.warning(self, "PowerPoint", f"Не удалось запустить показ:\n{exc}\n\nУкажите путь к POWERPNT.EXE в настройках.")

    def pdf_kiosk_url(self, path):
        fragment = "#toolbar=0&navpanes=0&scrollbar=0"
        if self.pdf_fit_width:
            fragment += "&view=FitH"
        return path.as_uri() + fragment

    def launch_edge_kiosk(self, url):
        self.close_output()
        screen = self.selected_screen()
        geo = screen.geometry()
        exe = existing_exe(self.edge_path.text().strip(), ["msedge.exe"], edge_extra_paths())
        args = [
            exe, "--new-window", "--no-first-run", "--kiosk", url,
            "--edge-kiosk-type=fullscreen",
            f"--window-position={geo.x()},{geo.y()}",
            f"--window-size={geo.width()},{geo.height()}",
        ]
        try:
            self.processes.start(args)
        except OSError as exc:
            QMessageBox.warning(self, "Edge", f"Не удалось запустить Edge:\n{exc}\n\nУкажите путь к msedge.exe в настройках.")

    def show_selected_image(self):
        path = self.selected_path(self.image_list)
        if path:
            self.show_image(path)

    def show_image(self, path):
        self.close_output()
        self.image_window = FullScreenImage(self.selected_screen())
        self.image_window.show_image(str(path))
        self.set_status(f"Картинка: {path.name}")

    def start_carousel(self):
        paths = [Path(item.data(Qt.UserRole)) for item in self.image_list.selectedItems()]
        if not paths:
            path = self.selected_path(self.image_list)
            paths = [path] if path else []
        if not paths:
            return
        self.close_output()
        self.carousel_paths = paths
        self.carousel_index = -1
        self.image_window = FullScreenImage(self.selected_screen())
        self.carousel_timer.start(self.carousel_spin.value() * 60 * 1000)
        self.next_carousel_image()
        self.persist_settings()

    def next_carousel_image(self):
        if not self.carousel_paths:
            return
        if not self.image_window:
            self.image_window = FullScreenImage(self.selected_screen())
        self.carousel_index = (self.carousel_index + 1) % len(self.carousel_paths)
        path = self.carousel_paths[self.carousel_index]
        self.image_window.show_image(str(path))
        self.set_status(f"Карусель: {path.name}")

    def launch_selected_video(self):
        path = self.selected_path(self.video_list)
        if not path:
            return
        self.launch_video(path)

    def launch_video(self, path):
        self.close_output()
        try:
            self.processes.start(self.video_args(path))
            self.persist_settings()
            self.set_status(f"Видео: {path.name}")
        except OSError as exc:
            QMessageBox.warning(self, "Видео", f"Не удалось запустить плеер:\n{exc}")

    def video_args(self, path):
        preset = self.video_preset_combo.currentText()
        custom = self.video_player_path.text().strip()
        if preset == "VLC":
            return [existing_exe(custom, ["vlc.exe"]), "--fullscreen", "--no-video-title-show", str(path)]
        if preset == "PotPlayer":
            return [existing_exe(custom, ["PotPlayerMini64.exe", "PotPlayerMini.exe"]), "/fullscreen", str(path)]
        if preset == "KMPlayer":
            return [existing_exe(custom, ["KMPlayer.exe"]), str(path)]
        if preset == "Windows Media Player":
            wmplayer = Path(os.environ.get("ProgramFiles", "")) / "Windows Media Player/wmplayer.exe"
            return [existing_exe(custom, ["wmplayer.exe"], [wmplayer]), "/fullscreen", str(path)]
        return [custom, str(path)] if custom else [str(path)]

    def start_timer(self):
        self.close_output()
        timer_settings = {
            "bg_path": self.settings["timer_background"],
            "text_color": self.text_color,
            "outline_color": self.outline_color,
            "font": self.font_combo.currentData() or self.font_combo.currentText(),
            "font_size": self.font_size_spin.value(),
            "outline_width": self.outline_width_spin.value(),
        }
        self.timer_window = FullScreenTimer(self.selected_screen(), timer_settings)
        self.timer_logic.time_changed.connect(self.timer_window.update_time)
        self.timer_logic.start(self.time_spin.value() * 60, self.pre_alert_spin.value())
        self.set_status("Таймер запущен")

    def start_timer_preset(self, minutes):
        self.time_spin.setValue(minutes)
        self.start_timer()

    def on_timer_changed(self, text):
        self.timer_label.setText(text)
        if not self.timer_window:
            return
        if self.gradient_checkbox.isChecked() and self.timer_logic.duration:
            ratio = max(0, min(1, 1 - self.timer_logic.time_left / self.timer_logic.duration))
            self.timer_window.label.text_color = QColor(255, int(255 * (1 - ratio)), int(255 * (1 - ratio)))
            self.timer_window.label.update()
        if self.change_color_checkbox.isChecked() and self.timer_logic.time_left <= self.pre_alert_spin.value() * 60:
            self.timer_window.label.text_color = QColor("red")
            self.timer_window.label.update()

    def on_timer_finished(self):
        if self.timer_window:
            self.timer_window.label.text_color = QColor("red")
            self.timer_window.label.start_blink()
        self.play_alarm()
        self.set_status("Время вышло")

    def play_alarm(self):
        if self.alarm.source().isEmpty():
            return
        self.alarm.stop()
        self.alarm.play()

    def refresh_quiz_links(self):
        if not hasattr(self, "quiz_list"):
            return
        self.quiz_list.clear()
        for url in self.settings["quiz_links"]:
            prefix = "★ " if url == self.settings.get("primary_quiz_url", "") else ""
            item = QListWidgetItem(prefix + url)
            item.setData(Qt.UserRole, url)
            self.quiz_list.addItem(item)
        if self.quiz_list.count():
            self.quiz_list.setCurrentRow(0)
        self.update_primary_quiz_label()

    def add_quiz_link(self):
        url = self.quiz_url.text().strip()
        if not url:
            return
        if "://" not in url:
            url = "https://" + url
        if url not in self.settings["quiz_links"]:
            self.settings["quiz_links"].append(url)
        if not self.settings.get("primary_quiz_url"):
            self.settings["primary_quiz_url"] = url
        self.quiz_url.clear()
        self.refresh_quiz_links()
        self.persist_settings()

    def remove_quiz_link(self):
        item = self.quiz_list.currentItem()
        if not item:
            return
        url = item.data(Qt.UserRole)
        self.settings["quiz_links"] = [saved for saved in self.settings["quiz_links"] if saved != url]
        if self.settings.get("primary_quiz_url") == url:
            self.settings["primary_quiz_url"] = self.settings["quiz_links"][0] if self.settings["quiz_links"] else ""
        self.refresh_quiz_links()
        self.persist_settings()

    def set_selected_quiz_primary(self):
        item = self.quiz_list.currentItem()
        if not item:
            return
        self.settings["primary_quiz_url"] = item.data(Qt.UserRole)
        self.refresh_quiz_links()
        self.persist_settings()

    def update_primary_quiz_label(self):
        if not hasattr(self, "primary_quiz_label"):
            return
        primary = self.settings.get("primary_quiz_url", "")
        self.primary_quiz_label.setText(f"Основной квиз для кнопки на пульте: {primary or 'не выбран'}")

    def launch_primary_quiz(self):
        url = self.settings.get("primary_quiz_url", "")
        if not url:
            QMessageBox.warning(self, "Квиз", "Основной квиз не выбран. Открой вкладку 'Квиз', выбери ссылку и нажми 'Сделать основной'.")
            return
        self.launch_quiz_url(url)

    def launch_selected_quiz(self):
        item = self.quiz_list.currentItem()
        url = item.data(Qt.UserRole) if item else self.quiz_url.text().strip()
        if not url:
            return
        self.launch_quiz_url(url)

    def launch_quiz_url(self, url):
        if "://" not in url:
            url = "https://" + url
        self.launch_edge_kiosk(url)
        self.set_status(f"Квиз: {url}")

    def move_presentation_up(self):
        self.move_current_item(self.presentation_list, -1)

    def move_presentation_down(self):
        self.move_current_item(self.presentation_list, 1)

    def move_current_item(self, widget, delta):
        row = widget.currentRow()
        new_row = row + delta
        if row < 0 or new_row < 0 or new_row >= widget.count():
            return
        item = widget.takeItem(row)
        widget.insertItem(new_row, item)
        widget.setCurrentRow(new_row)
        if widget is self.run_list:
            self.save_current_queue()

    def select_timer_background(self):
        path, _ = QFileDialog.getOpenFileName(self, "Фон таймера", str(ROOT), "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.settings["timer_background"] = path
            self.persist_settings()

    def pick_text_color(self):
        color = QColorDialog.getColor(self.text_color, self)
        if color.isValid():
            self.text_color = color

    def pick_outline_color(self):
        color = QColorDialog.getColor(self.outline_color, self)
        if color.isValid():
            self.outline_color = color

    def select_alarm_sound(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Звук таймера",
            "C:\\Windows\\Media",
            "Audio (*.wav *.mp3 *.m4a *.wma);;All files (*.*)",
        )
        if path:
            self.settings["timer_sound_path"] = path
            self.load_alarm_sound(path)
            self.persist_settings()

    def load_alarm_sound(self, path):
        candidates = []
        if path:
            candidates.append(Path(path))
        candidates.extend([
            Path(__file__).resolve().parent / "alarm.mp3",
            ROOT / "alarm.mp3",
            Path("C:/Windows/Media/Alarm01.wav"),
        ])
        for sound_path in candidates:
            if sound_path.exists():
                self.alarm.setSource(QUrl.fromLocalFile(str(sound_path)))
                return

    def set_alarm_volume(self, value):
        self.audio.setVolume(float(value) / 100.0)
        self.settings["timer_volume"] = int(value)
        save_settings(self.settings)

    def browse_powerpoint(self):
        self.browse_exe_into(self.powerpoint_path)

    def browse_edge(self):
        self.browse_exe_into(self.edge_path)

    def browse_video_player(self):
        self.browse_exe_into(self.video_player_path)

    def browse_exe_into(self, line_edit):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите программу", str(ROOT), "Programs (*.exe);;All files (*.*)")
        if path:
            line_edit.setText(path)

    def open_telegram_connect_dialog(self):
        dialog = TelegramChatFinderDialog(self.telegram_token_edit.text().strip(), parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        if not dialog.selected_chat_id:
            QMessageBox.warning(self, "Telegram", "Chat ID не выбран.")
            return
        self.telegram_token_edit.setText(dialog.selected_token)
        self.telegram_chat_id_edit.setText(dialog.selected_chat_id)
        self.persist_settings()
        self.update_telegram_tab_info()
        self.set_status(f"Telegram чат выбран: {dialog.selected_chat_id}")
        QMessageBox.information(self, "Telegram", f"Подключение сохранено.\nChat ID: {dialog.selected_chat_id}")

    def fetch_telegram_bot_link(self):
        token = self.telegram_token_edit.text().strip()
        if not token:
            QMessageBox.warning(self, "Telegram", "Сначала вставь Bot token.")
            return
        try:
            data = telegram_api_json(token, "getMe", timeout=15)
            bot = data.get("result", {})
            username = bot.get("username")
            if not username:
                QMessageBox.warning(self, "Telegram", "Telegram ответил, но username бота не найден.")
                return
            url = f"https://t.me/{username}"
            self.telegram_bot_link_label.setText(f'Ссылка на бота: <a href="{url}">{url}</a>')
            self.set_status(f"Telegram бот: @{username}")
        except Exception as exc:
            QMessageBox.critical(self, "Telegram", f"Не удалось получить ссылку на бота:\n{exc}")

    def start_telegram_receiver(self):
        token = self.telegram_token_edit.text().strip()
        chat_id = self.telegram_chat_id_edit.text().strip()
        project_dir = self.selected_project_dir()
        if not token:
            QMessageBox.warning(self, "Telegram", "Укажи bot token в настройках.")
            return
        if not chat_id:
            QMessageBox.warning(self, "Telegram", "Выбери chat_id через кнопку 'Найти чат'.")
            return
        if not project_dir:
            QMessageBox.warning(self, "Telegram", "Выбери проект/конференцию.")
            return

        self.stop_telegram_receiver(wait=True)
        self.persist_settings()
        self.telegram_receiver = TelegramReceiver(
            token=token,
            chat_id=chat_id,
            download_dir=project_dir,
            offset=int(self.settings.get("telegram_update_offset") or 0),
        )
        self.telegram_receiver.file_saved.connect(self.on_telegram_file_saved)
        self.telegram_receiver.status_changed.connect(self.set_status)
        self.telegram_receiver.error.connect(self.set_status)
        self.telegram_receiver.offset_changed.connect(self.on_telegram_offset_changed)
        self.telegram_receiver.start()
        self.update_telegram_tab_info()
        self.set_status(f"Telegram принимает файлы в папку: {project_dir.name}")

    def stop_telegram_receiver(self, wait=True):
        if not self.telegram_receiver:
            return
        receiver = self.telegram_receiver
        receiver.stop()
        self.set_status("Telegram останавливается...")
        if wait:
            if not receiver.wait(12000):
                self.telegram_receiver = receiver
                self.set_status("Telegram еще завершает сетевой запрос. Повтори стоп через несколько секунд.")
                self.update_telegram_tab_info()
                return
        if self.telegram_receiver is receiver:
            self.telegram_receiver = None
        self.update_telegram_tab_info()
        self.set_status("Telegram прием остановлен")

    def on_telegram_file_saved(self, path):
        filename = Path(path).name
        message = f"Принят файл: {filename}"
        self.set_status(f"Telegram файл принят: {filename}")
        self.last_received_label.setText(message)
        self.load_selected_project()

    def on_telegram_offset_changed(self, offset):
        self.settings["telegram_update_offset"] = int(offset)
        self.settings["telegram_token"] = self.telegram_token_edit.text().strip()
        self.settings["telegram_chat_id"] = self.telegram_chat_id_edit.text().strip()
        save_settings(self.settings)
        self.update_telegram_tab_info()

    def switch_display(self, mode):
        try:
            display_switch(mode)
            self.set_status("Переключаю режим экранов")
            QTimer.singleShot(2500, self.refresh_screens)
        except OSError as exc:
            QMessageBox.warning(self, "Мониторы", f"Не удалось вызвать DisplaySwitch:\n{exc}")

    def swap_control_and_output_screens(self):
        screens = app_screens()
        if len(screens) < 2:
            QMessageBox.information(self, "Мониторы", "Сейчас доступен только один монитор.")
            return
        control_index = screen_index_of_widget(self)
        output_index = self.screen_combo.currentData()
        if output_index is None or output_index >= len(screens):
            output_index = 0 if control_index != 0 else 1

        move_widget_to_screen(self, screens[output_index])
        self.screen_combo.setCurrentIndex(self.screen_combo.findData(control_index))
        self.update_control_screen_status()
        self.set_status("Пульт и выбранный экран вывода поменяны местами")

    def persist_settings(self):
        self.settings["video_preset"] = self.video_preset_combo.currentText()
        self.settings["video_player_path"] = self.video_player_path.text().strip()
        self.settings["powerpoint_path"] = self.powerpoint_path.text().strip()
        self.settings["edge_path"] = self.edge_path.text().strip()
        self.settings["telegram_token"] = self.telegram_token_edit.text().strip()
        self.settings["telegram_chat_id"] = self.telegram_chat_id_edit.text().strip()
        self.settings["presentation_mode"] = self.powerpoint_mode_combo.currentData()
        self.settings["pdf_fit_width"] = self.pdf_fit_width
        if self.settings.get("primary_quiz_url") not in self.settings.get("quiz_links", []):
            self.settings["primary_quiz_url"] = self.settings["quiz_links"][0] if self.settings["quiz_links"] else ""
        self.settings["carousel_minutes"] = self.carousel_spin.value()
        self.settings["timer_sound_path"] = self.alarm.source().toLocalFile()
        self.settings["timer_volume"] = self.volume_slider.value()
        self.settings["timer_font"] = self.font_combo.currentData() or self.font_combo.currentText()
        self.settings["music_volume"] = self.music_volume_slider.value()
        self.settings["music_shuffle"] = self.music_shuffle_checkbox.isChecked()
        self.settings["music_repeat_mode"] = self.music_repeat_combo.currentData()
        self.settings["presentation_sort"] = self.sort_modes["presentation_sort"]
        self.settings["image_sort"] = self.sort_modes["image_sort"]
        self.settings["video_sort"] = self.sort_modes["video_sort"]
        self.save_music_playlists()
        self.save_current_queue()
        save_settings(self.settings)
        self.update_telegram_tab_info()
        self.set_status("Настройки сохранены")

    def set_status(self, text):
        self.status_label.setText(text)

    def closeEvent(self, event):
        self.stop_telegram_receiver(wait=True)
        self.stop_music()
        self.persist_settings()
        self.close_output()
        event.accept()


def run():
    app = QApplication(sys.argv)
    window = ConferenceDirector()
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
