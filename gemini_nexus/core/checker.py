"""Network dispatcher and Google API status classifier for Gemini Nexus DB."""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def classify_google_response(
    status_code: int,
    error_data: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Classify Google Generative Language API HTTP status code and response payload.

    Args:
        status_code: HTTP response status code.
        error_data: Parsed response JSON dictionary if available.

    Returns:
        Tuple of (status_tag, status_detail_message).
    """
    if status_code == 200:
        return "OK", "Ключ успешно прошел генерацию"

    error_msg = ""
    error_status = ""
    if error_data and isinstance(error_data, dict):
        if "error" in error_data and isinstance(error_data["error"], dict):
            err = error_data["error"]
            error_msg = str(err.get("message", ""))
            error_status = str(err.get("status", ""))
        else:
            error_msg = str(error_data.get("message", ""))
            error_status = str(error_data.get("status", ""))

    if status_code == 429 or "RESOURCE_EXHAUSTED" in error_status:
        detail = f"Лимит квоты исчерпан: {error_msg}" if error_msg else "Превышен лимит RPM/TPM (разгрузится)"
        return "RESOURCE_EXHAUSTED", detail

    if status_code == 403:
        if "unrestricted" in error_msg.lower() or "unregistered callers" in error_msg.lower():
            detail = (
                f"Требуется ограничение API в Google Cloud Console (политика от 19 июня): {error_msg}"
                if error_msg
                else "Требуется ограничение API в Google Cloud Console (политика от 19 июня)"
            )
            return "UNRESTRICTED", detail
        detail = f"Доступ запрещен: {error_msg}" if error_msg else "Отказано в доступе / Ключ заблокирован"
        return "PERMISSION_DENIED", detail

    if status_code == 400:
        detail = (
            f"Региональное ограничение / Биллинг: {error_msg}" if error_msg else "Региональный блок / Требуется биллинг"
        )
        return "FAILED_PRECONDITION", detail

    if status_code == 401:
        detail = f"Ключ не существует или отозван: {error_msg}" if error_msg else "Ключ не существует или отозван"
        return "UNAUTHORIZED", detail

    if status_code == 404:
        detail = f"Модель не найдена: {error_msg}" if error_msg else "Модель не найдена"
        return "NOT_FOUND", detail

    if status_code == 500:
        detail = (
            f"Внутренняя ошибка сервера Google (500): {error_msg}"
            if error_msg
            else "Внутренняя ошибка сервера Google (500)"
        )
        return "INTERNAL_ERROR", detail

    if status_code in (502, 503):
        detail = (
            f"Сервис Google временно перегружен ({status_code}): {error_msg}"
            if error_msg
            else f"Сервис Google временно перегружен ({status_code})"
        )
        return "SERVICE_UNAVAILABLE", detail

    if status_code == 504:
        detail = (
            f"Таймаут генерации на стороне Google (504): {error_msg}"
            if error_msg
            else "Таймаут генерации на стороне Google (504)"
        )
        return "DEADLINE_EXCEEDED", detail

    return f"HTTP_{status_code}", error_msg or f"Код ответа Google: {status_code}"


def build_proxy_opener(proxy_url: str) -> urllib.request.OpenerDirector:
    """Build an urllib OpenerDirector supporting HTTP, HTTPS, SOCKS4, and SOCKS5 proxies.

    Args:
        proxy_url: Complete proxy URL (e.g. 'http://...', 'socks5://...').

    Returns:
        urllib.request.OpenerDirector configured with proxy handler.
    """
    parsed = urllib.parse.urlparse(proxy_url)
    scheme = parsed.scheme.lower()

    if "socks" in scheme:
        try:
            import socks
            from sockshandler import SocksiPyHandler
        except ImportError:
            raise ImportError(
                "Для работы SOCKS прокси требуется библиотека PySocks. Установите её: pip install PySocks"
            ) from None

        stype = (
            getattr(socks, "PROXY_TYPE_SOCKS5", getattr(socks, "SOCKS5", 2))
            if "5" in scheme
            else getattr(socks, "PROXY_TYPE_SOCKS4", getattr(socks, "SOCKS4", 1))
        )
        handler = SocksiPyHandler(
            stype,
            parsed.hostname,
            parsed.port,
            True,
            parsed.username,
            parsed.password,
        )
        return urllib.request.build_opener(handler)

    proxy_handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
    return urllib.request.build_opener(proxy_handler)


def check_api_key(
    key: str,
    model: str,
    proxy_url: str | None = None,
    timeout: float = 12.0,
) -> tuple[str, str]:
    """Test a Google Gemini API key by sending a minimal generateContent request.

    Args:
        key: Gemini API key string.
        model: Model name/identifier (e.g. 'gemini-3.8-flash').
        proxy_url: Optional proxy URL for network routing.
        timeout: Socket connection/read timeout in seconds.

    Returns:
        Tuple of (status_tag, status_detail_message).
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    payload = {"contents": [{"parts": [{"text": "hi"}]}]}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        opener = build_proxy_opener(proxy_url) if proxy_url else urllib.request.build_opener()
        with opener.open(req, timeout=timeout) as resp:
            status_code = getattr(resp, "status", 200)
            return classify_google_response(status_code)
    except urllib.error.HTTPError as e:
        raw_body = ""
        try:
            raw_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass

        err_json = None
        if raw_body:
            try:
                err_json = json.loads(raw_body)
            except Exception:
                err_json = None

        return classify_google_response(e.code, err_json)
    except (urllib.error.URLError, TimeoutError) as e:
        return "TIMEOUT", f"Сетевая ошибка / таймаут соединения: {e!s}"
    except Exception as e:
        return "INTERNAL_ERROR", f"Непредвиденное исключение: {e!s}"
