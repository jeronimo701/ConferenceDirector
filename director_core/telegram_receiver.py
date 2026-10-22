from __future__ import annotations
import re
import urllib.parse
import urllib.request
from pathlib import Path
from PySide6.QtCore import QThread, Signal
from .telegram_connect_dialog import telegram_api_json
SAFE_NAME_RE = re.compile('[<>:"/\\\\|?*\\x00-\\x1f]')

def safe_filename(name: str, fallback: str) -> str:
    name = SAFE_NAME_RE.sub('_', name or '').strip(' .')
    return name or fallback

def unique_path(directory: Path, filename: str) -> Path:
    path = directory / filename
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = directory / f'{stem} ({counter}){suffix}'
        if not candidate.exists():
            return candidate
        counter += 1

class TelegramReceiver(QThread):
    file_saved = Signal(str)
    status_changed = Signal(str)
    error = Signal(str)
    offset_changed = Signal(int)
    def __init__(self, token: str, chat_id: str, download_dir: Path, offset: int=0):
        super().__init__()
        self.token = token
        self.chat_id = str(chat_id).strip()
        self.download_dir = Path(download_dir)
        self.offset = int(offset or 0)
        self._stopping = False

    def stop(self):
        self._stopping = True
        self.requestInterruption()

    def run(self):
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.status_changed.emit('Telegram: слушаю новые файлы')
        while not self._stopping and not self.isInterruptionRequested():
            try:
                data = telegram_api_json(self.token, 'getUpdates', {'offset': self.offset, 'timeout': 2, 'allowed_updates': '["message","channel_post"]'}, timeout=8)
                for update in data.get('result', []):
                    update_id = int(update.get('update_id', 0))
                    self.offset = max(self.offset, update_id + 1)
                    self.offset_changed.emit(self.offset)
                    self._handle_update(update)
            except Exception as exc:
                if not self._stopping:
                    self.error.emit(f'Telegram: {exc}')
                    self.msleep(3000)
        self.status_changed.emit('Telegram: остановлен')

    def _handle_update(self, update: dict):
        message = update.get('message') or update.get('channel_post') or {}
        chat = message.get('chat') or {}
        if self.chat_id and str(chat.get('id')) != self.chat_id:
            return
        payload = self._message_file_payload(message)
        if not payload:
            return
        file_id, filename = payload
        saved_path = self._download_file(file_id, filename)
        self.file_saved.emit(str(saved_path))

    def _message_file_payload(self, message: dict):
        document = message.get('document')
        if isinstance(document, dict):
            return document.get('file_id'), safe_filename(document.get('file_name'), 'telegram_file')
        video = message.get('video') or message.get('animation')
        if isinstance(video, dict):
            return video.get('file_id'), safe_filename(video.get('file_name'), 'telegram_video.mp4')
        photos = message.get('photo')
        if isinstance(photos, list) and photos:
            largest = photos[-1]
            caption = safe_filename(message.get('caption', ''), 'telegram_photo')
            return largest.get('file_id'), f'{Path(caption).stem}.jpg'
        return None

    def _download_file(self, file_id: str, filename: str) -> Path:
        meta = telegram_api_json(self.token, 'getFile', {'file_id': file_id}, timeout=20)
        file_path = meta['result']['file_path']
        source_url = f'https://api.telegram.org/file/bot{self.token}/{urllib.parse.quote(file_path)}'
        target_path = unique_path(self.download_dir, safe_filename(filename, Path(file_path).name))
        with urllib.request.urlopen(source_url, timeout=120) as response:
            target_path.write_bytes(response.read())
        return target_path


