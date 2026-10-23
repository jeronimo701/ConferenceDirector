import json

from .paths import SETTINGS_PATH


def default_settings():
    return {
        "quiz_links": [],
        "primary_quiz_url": "",
        "video_preset": "VLC",
        "video_player_path": "",
        "powerpoint_path": "",
        "edge_path": "",
        "presentation_mode": "slide_show",
        "pdf_fit_width": True,
        "carousel_minutes": 1,
        "timer_background": "",
        "telegram_token": "",
        "telegram_chat_id": "",
        "telegram_update_offset": 0,
        "timer_sound_path": "",
        "timer_volume": 80,
        "timer_font": "Arial",
        "project_queues": {},
        "presentation_sort": "name",
        "image_sort": "name",
        "video_sort": "name",
        "music_folder": "",
        "music_files": [],
        "music_links": [],
        "music_volume": 60,
        "music_shuffle": False,
        "music_repeat_mode": "all",
        "projects_root": "",
        "last_project_path": "",
    }


def load_settings():
    settings = default_settings()
    if SETTINGS_PATH.exists():
        try:
            settings.update(json.loads(SETTINGS_PATH.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass
    return settings


def save_settings(settings):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
