from __future__ import annotations
import json
import urllib.parse
import urllib.request
import webbrowser
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

def telegram_api_json(token: str, method: str, params: dict | None=None, timeout: int=20) -> dict:
    url = f'https://api.telegram.org/bot{token}/{method}'
    if params:
        url += '?' + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))

class TelegramChatFinderDialog(QDialog):
    '''Dialog from the old tool, kept request-free for this app.'''

    def __init__(self, token: str='', parent: QWidget | None=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Поиск группы/канала Telegram')
        self.resize(900, 620)
        self.selected_chat_id = ''
        self.selected_token = token.strip()
        root = QVBoxLayout(self)
        info = QLabel("1) Создай бота через <a href='https://t.me/BotFather'>@BotFather</a>. 2) Добавь бота в группу/канал и отправь туда сообщение. 3) Вставь token, получи updates и выбери chat_id.")
        info.setOpenExternalLinks(True)
        info.setWordWrap(True)
        root.addWidget(info)
        top = QHBoxLayout()
        top.addWidget(QLabel('Bot token:'))
        self.token_edit = QLineEdit(token.strip())
        top.addWidget(self.token_edit)
        self.open_updates_btn = QPushButton('Открыть getUpdates в браузере')
        self.open_updates_btn.clicked.connect(self._open_getupdates_url)
        top.addWidget(self.open_updates_btn)
        root.addLayout(top)
        row = QHBoxLayout()
        self.fetch_btn = QPushButton('Запросить getUpdates')
        self.fetch_btn.clicked.connect(self._fetch_updates)
        row.addWidget(self.fetch_btn)
        self.parse_btn = QPushButton('Разобрать JSON')
        self.parse_btn.clicked.connect(self._parse_raw_json)
        row.addWidget(self.parse_btn)
        row.addStretch(1)
        root.addLayout(row)
        self.raw_edit = QPlainTextEdit()
        self.raw_edit.setPlaceholderText("Сюда попадет JSON. Можно вставить вручную и нажать 'Разобрать JSON'.")
        root.addWidget(self.raw_edit, stretch=1)
        root.addWidget(QLabel('Найденные чаты (выбери строку):'))
        self.candidates = QListWidget()
        self.candidates.itemDoubleClicked.connect((lambda _: self._apply_selected()))
        root.addWidget(self.candidates, stretch=1)
        bottom = QHBoxLayout()
        self.copy_btn = QPushButton('Скопировать выбранный ID')
        self.copy_btn.clicked.connect(self._copy_selected)
        bottom.addWidget(self.copy_btn)
        self.apply_btn = QPushButton('Использовать выбранный ID')
        self.apply_btn.clicked.connect(self._apply_selected)
        bottom.addWidget(self.apply_btn)
        bottom.addStretch(1)
        root.addLayout(bottom)

    def _open_getupdates_url(self) -> None:
        token = self.token_edit.text().strip()
        if not token:
            QMessageBox.warning(self, 'Token', 'Укажи bot token')
            return
        webbrowser.open(f'https://api.telegram.org/bot{token}/getUpdates')

    def _fetch_updates(self) -> None:
        token = self.token_edit.text().strip()
        if not token:
            QMessageBox.warning(self, 'Token', 'Укажи bot token')
            return
        try:
            data = telegram_api_json(token, 'getUpdates')
            self.raw_edit.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))
            self._parse_raw_json()
            return
        except Exception as exc:
            QMessageBox.critical(self, 'Telegram API', f'Ошибка запроса: {exc}')

    def _parse_raw_json(self) -> None:
        self.candidates.clear()
        raw = self.raw_edit.toPlainText().strip()
        if not raw:
            return
        try:
            data = json.loads(raw)
        except Exception as exc:
            QMessageBox.warning(self, 'JSON', f'Не удалось разобрать JSON: {exc}')
            return
        seen = set()
        for update in data.get('result', []):
            for key in ('message', 'channel_post', 'edited_message', 'edited_channel_post'):
                obj = update.get(key)
                if not isinstance(obj, dict):
                    continue
                chat = obj.get('chat', {})
                chat_id = str(chat.get('id', '')).strip()
                if not chat_id or chat_id in seen:
                    continue
                seen.add(chat_id)
                ctype = str(chat.get('type', 'unknown'))
                title = str(chat.get('title') or chat.get('username') or chat.get('first_name') or 'Без названия')
                item = QListWidgetItem(f'{ctype}: {title} | id={chat_id}')
                item.setData(Qt.ItemDataRole.UserRole, chat_id)
                self.candidates.addItem(item)
        if not seen:
            self.candidates.addItem('Пусто: отправь сообщение в нужный чат и повтори getUpdates.')

    def _selected_chat_id(self) -> str:
        item = self.candidates.currentItem()
        if not item:
            return ''
        value = item.data(Qt.ItemDataRole.UserRole)
        if value is not None:
            return str(value).strip()
        return ''

    def _copy_selected(self) -> None:
        chat_id = self._selected_chat_id()
        if chat_id:
            QApplication.clipboard().setText(chat_id)

    def _apply_selected(self) -> None:
        chat_id = self._selected_chat_id()
        if not chat_id:
            return
        self.selected_chat_id = chat_id
        self.selected_token = self.token_edit.text().strip()
        self.accept()


