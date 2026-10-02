"""Unit tests for Gemini API status classifier and network dispatcher."""

import io
import json
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

from gemini_nexus.core.checker import (
    build_proxy_opener,
    check_api_key,
    classify_google_response,
)


def test_classify_ok():
    """Verify 200 status code yields OK."""
    status, detail = classify_google_response(200, {"candidates": [{"content": {"parts": [{"text": "hello"}]}}]})
    assert status == "OK"
    assert "успешно" in detail.lower() or "ok" in detail.lower()

    status_none, detail_none = classify_google_response(200, None)
    assert status_none == "OK"


def test_classify_resource_exhausted():
    """Verify 429 quota exhaustion yields RESOURCE_EXHAUSTED."""
    payload = {"error": {"code": 429, "message": "Resource has been exhausted (e.g. check quota)."}}
    status, detail = classify_google_response(429, payload)
    assert status == "RESOURCE_EXHAUSTED"
    assert "исчерпан" in detail.lower() or "лимит" in detail.lower() or "exhausted" in detail.lower()

    # Also test error status flag if code is 400 or other but status is RESOURCE_EXHAUSTED
    payload_status = {"error": {"code": 400, "status": "RESOURCE_EXHAUSTED", "message": "Rate limit"}}
    status_flag, _ = classify_google_response(400, payload_status)
    assert status_flag == "RESOURCE_EXHAUSTED"


def test_classify_unrestricted_policy():
    """Verify 403 unrestricted API callers yields UNRESTRICTED."""
    payload = {"error": {"code": 403, "message": "Method doesn't allow unregistered callers (caller: unrestricted)"}}
    status, detail = classify_google_response(403, payload)
    assert status == "UNRESTRICTED"
    assert "19 июня" in detail or "google cloud" in detail.lower() or "unrestricted" in detail.lower()


def test_classify_permission_denied():
    """Verify standard 403 yields PERMISSION_DENIED."""
    payload = {"error": {"code": 403, "message": "API key not valid. Please pass a valid API key."}}
    status, detail = classify_google_response(403, payload)
    assert status == "PERMISSION_DENIED"
    assert "запрещен" in detail.lower() or "отказано" in detail.lower() or "доступ" in detail.lower()

    status_no_data, _ = classify_google_response(403, None)
    assert status_no_data == "PERMISSION_DENIED"


def test_classify_failed_precondition():
    """Verify 400 region/billing error yields FAILED_PRECONDITION."""
    payload = {"error": {"code": 400, "message": "User location is not supported for the API use."}}
    status, detail = classify_google_response(400, payload)
    assert status == "FAILED_PRECONDITION"
    assert (
        "регион" in detail.lower()
        or "биллинг" in detail.lower()
        or "предусловие" in detail.lower()
        or "precondition" in detail.lower()
    )


def test_classify_unauthorized():
    """Verify 401 invalid key yields UNAUTHORIZED."""
    payload = {"error": {"code": 401, "message": "API key not valid."}}
    status, detail = classify_google_response(401, payload)
    assert status == "UNAUTHORIZED"
    assert "не существует" in detail.lower() or "отозван" in detail.lower() or "unauthorized" in detail.lower()


def test_classify_not_found():
    """Verify 404 model not found yields NOT_FOUND."""
    payload = {"error": {"code": 404, "message": "models/unknown-model is not found."}}
    status, detail = classify_google_response(404, payload)
    assert status == "NOT_FOUND"
    assert "не найдена" in detail.lower() or "not found" in detail.lower()


def test_classify_server_errors():
    """Verify 500, 502, 503, 504 server errors."""
    status_500, _ = classify_google_response(500, {"error": {"message": "Internal error"}})
    assert status_500 == "INTERNAL_ERROR"

    status_502, _ = classify_google_response(502, {"error": {"message": "Bad gateway"}})
    assert status_502 == "SERVICE_UNAVAILABLE"

    status_503, _ = classify_google_response(503, {"error": {"message": "Service unavailable"}})
    assert status_503 == "SERVICE_UNAVAILABLE"

    status_504, _ = classify_google_response(504, {"error": {"message": "Gateway timeout"}})
    assert status_504 == "DEADLINE_EXCEEDED"


def test_classify_unknown_http_code():
    """Verify non-standard status codes yield HTTP_XXX."""
    status, detail = classify_google_response(418, {"error": {"message": "Teapot"}})
    assert status == "HTTP_418"
    assert "Teapot" in detail


def test_check_api_key_ok():
    """Verify check_api_key returns OK when request succeeds with 200."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    mock_opener = MagicMock()
    mock_opener.open.return_value = mock_resp

    with patch("urllib.request.build_opener", return_value=mock_opener):
        status, detail = check_api_key(
            key="AIzaSyMockKeyForUnitTestingOnly12345",
            model="gemini-3.8-flash",
            timeout=5.0,
        )
        assert status == "OK"

        # Verify call arguments
        mock_opener.open.assert_called_once()
        req = mock_opener.open.call_args[0][0]
        assert isinstance(req, urllib.request.Request)
        assert "key=AIzaSyMockKeyForUnitTestingOnly12345" in req.full_url
        assert "models/gemini-3.8-flash:generateContent" in req.full_url
        assert req.get_method() == "POST"
        assert req.headers.get("Content-type") == "application/json"


def test_check_api_key_http_error_429():
    """Verify check_api_key parses HTTPError 429 response body."""
    error_payload = {
        "error": {
            "code": 429,
            "message": "Resource has been exhausted (e.g. check quota).",
            "status": "RESOURCE_EXHAUSTED",
        }
    }
    raw_json = json.dumps(error_payload).encode("utf-8")
    fp = io.BytesIO(raw_json)

    http_error = urllib.error.HTTPError(
        url="https://generativelanguage.googleapis.com",
        code=429,
        msg="Too Many Requests",
        hdrs={},
        fp=fp,
    )

    mock_opener = MagicMock()
    mock_opener.open.side_effect = http_error

    with patch("urllib.request.build_opener", return_value=mock_opener):
        status, detail = check_api_key(
            key="AIzaSyMockKey429",
            model="gemini-3.8-flash",
        )
        assert status == "RESOURCE_EXHAUSTED"
        assert "исчерпан" in detail.lower() or "лимит" in detail.lower() or "exhausted" in detail.lower()


def test_check_api_key_timeout():
    """Verify check_api_key maps URLError or TimeoutError to TIMEOUT."""
    mock_opener = MagicMock()
    mock_opener.open.side_effect = urllib.error.URLError("Connection timed out")

    with patch("urllib.request.build_opener", return_value=mock_opener):
        status, detail = check_api_key("AIzaSyMockKeyTimeout", "gemini-3.8-flash")
        assert status == "TIMEOUT"
        assert "сетевая ошибка" in detail.lower() or "таймаут" in detail.lower()

    # Also test standard TimeoutError
    mock_opener.open.side_effect = TimeoutError("Request timed out")
    with patch("urllib.request.build_opener", return_value=mock_opener):
        status2, detail2 = check_api_key("AIzaSyMockKeyTimeout2", "gemini-3.8-flash")
        assert status2 == "TIMEOUT"


def test_check_api_key_internal_error():
    """Verify check_api_key maps generic unexpected exceptions to INTERNAL_ERROR."""
    mock_opener = MagicMock()
    mock_opener.open.side_effect = RuntimeError("Fatal system failure")

    with patch("urllib.request.build_opener", return_value=mock_opener):
        status, detail = check_api_key("AIzaSyMockKeyErr", "gemini-3.8-flash")
        assert status == "INTERNAL_ERROR"
        assert "Fatal system failure" in detail


def test_build_proxy_opener_http():
    """Verify build_proxy_opener constructs ProxyHandler for HTTP/HTTPS."""
    opener = build_proxy_opener("http://127.0.0.1:8080")
    assert isinstance(opener, urllib.request.OpenerDirector)


def test_build_proxy_opener_socks_import_error():
    """Verify build_proxy_opener raises ImportError if PySocks is missing."""
    with patch.dict("sys.modules", {"socks": None, "sockshandler": None}):
        with pytest.raises(ImportError) as exc_info:
            build_proxy_opener("socks5://127.0.0.1:1080")
        assert "pysocks" in str(exc_info.value).lower()
