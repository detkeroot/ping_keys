"""Core configuration and constants for Gemini Nexus DB."""

from pathlib import Path

APP_NAME: str = "Gemini Nexus DB"
APP_VERSION: str = "14.0.0"
AUTHOR: str = "NeuroStarNet"
DEFAULT_DB_FILE: str = "gemini_keys.db"
DEFAULT_DB_PATH: Path = Path(DEFAULT_DB_FILE)

# Gemini 3.x flagship line + standard models
DEFAULT_MODELS: list[str] = [
    "gemini-3.8-flash",
    "gemini-3.8-flash-high",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite-preview",
    "gemma-3-27b-it",
]

STATUS_RU: dict[str, str] = {
    "OK": "Работает",
    "UNCHECKED": "Не проверен",
    "RESOURCE_EXHAUSTED": "Лимит (429)",
    "UNRESTRICTED": "Ограничен Google (19 июня)",
    "SERVICE_UNAVAILABLE": "Сервис недоступен (503)",
    "INTERNAL_ERROR": "Ошибка сервера Google (500)",
    "DEADLINE_EXCEEDED": "Таймаут генерации (504)",
    "TIMEOUT": "Таймаут соединения",
    "FAILED_PRECONDITION": "Регион/Оплата (400)",
    "PERMISSION_DENIED": "Бан/Нет доступа (403)",
    "UNAUTHORIZED": "Не существует (401)",
    "NOT_FOUND": "Модель не найдена (404)",
}

STATUS_COLORS: dict[str, str] = {
    "OK": "#2ecc71",
    "UNCHECKED": "#7f8c8d",
    "RESOURCE_EXHAUSTED": "#f39c12",
    "UNRESTRICTED": "#e67e22",
    "SERVICE_UNAVAILABLE": "#f1c40f",
    "INTERNAL_ERROR": "#e74c3c",
    "DEADLINE_EXCEEDED": "#e67e22",
    "TIMEOUT": "#95a5a6",
    "FAILED_PRECONDITION": "#c0392b",
    "PERMISSION_DENIED": "#c0392b",
    "UNAUTHORIZED": "#962d22",
    "NOT_FOUND": "#e74c3c",
}
