"""Unit tests for Gemini Nexus PyQt6 core UI components and worker."""

from typing import Any

import pytest
from PyQt6.QtWidgets import QApplication

from gemini_nexus.ui.widgets.log_viewer import LogViewer
from gemini_nexus.ui.widgets.status_badge import StatusBadge
from gemini_nexus.ui.workers.check_worker import CheckWorker


@pytest.fixture(scope="session")
def qapp():
    """Ensure a headless offscreen QApplication exists for widget testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app


def test_status_badge(qapp):
    """Verify StatusBadge text formatting, localization, and CSS styling."""
    badge = StatusBadge("OK")
    assert badge.text() == "Работает"
    style = badge.styleSheet()
    assert "#2ecc71" in style

    badge.set_status("RESOURCE_EXHAUSTED")
    assert badge.text() == "Лимит (429)"
    assert "#f39c12" in badge.styleSheet()

    # Unknown status should fallback to status name and default gray
    badge.set_status("CUSTOM_UNKNOWN")
    assert badge.text() == "CUSTOM_UNKNOWN"
    assert "#7f8c8d" in badge.styleSheet()

    # None or empty status should default to UNCHECKED
    badge.set_status(None)
    assert badge.text() == "Не проверен"
    assert "#7f8c8d" in badge.styleSheet()


def test_log_viewer(qapp):
    """Verify LogViewer initialization, read-only mode, and colored log appending."""
    viewer = LogViewer()
    assert viewer.isReadOnly() is True

    viewer.append_log("Тестовое успешное сообщение", "OK")
    viewer.append_log("Предупреждение о квоте", "WARN")
    viewer.append_log("Фатальная ошибка ключа", "ERROR")
    viewer.append_log("Системное уведомление", "SYS")
    viewer.append_log("Обычный лог", "INFO")

    plain_content = viewer.toPlainText()
    assert "Тестовое успешное сообщение" in plain_content
    assert "Предупреждение о квоте" in plain_content
    assert "Фатальная ошибка ключа" in plain_content
    assert "Системное уведомление" in plain_content
    assert "Обычный лог" in plain_content
    assert "[OK]" in plain_content
    assert "[WARN]" in plain_content
    assert "[ERROR]" in plain_content
    assert "[SYS]" in plain_content
    assert "[INFO]" in plain_content

    viewer.clear_log()
    assert viewer.toPlainText().strip() == ""


def test_check_worker_lifecycle(qapp):
    """Verify CheckWorker instantiation and pause/resume/stop flag transitions."""
    keys: list[dict[str, Any]] = [
        {"id": 1, "key_string": "AIzaSyDummyKeyForWorkerTest12345678"},
        {"id": 2, "key_string": "AIzaSyDummyKeyForWorkerTest87654321"},
    ]
    worker = CheckWorker(
        keys_to_check=keys,
        model="gemini-3.8-flash",
        proxy_url=None,
        delay_min=0.1,
        delay_max=0.2,
    )

    assert worker.keys == keys
    assert worker.model == "gemini-3.8-flash"
    assert worker._is_running is True
    assert worker._is_paused is False

    worker.pause()
    assert worker._is_paused is True

    worker.resume()
    assert worker._is_paused is False

    worker.stop()
    assert worker._is_running is False
    assert worker._is_paused is False


def test_check_worker_execution(qapp, monkeypatch):
    """Verify CheckWorker thread execution and signal emission with mocked checker."""
    keys: list[dict[str, Any]] = [
        {"id": 10, "key_string": "AIzaSyTestKeyOneForWorkerLifecycle"},
        {"id": 20, "key_string": "AIzaSyTestKeyTwoForWorkerLifecycle"},
    ]

    mock_results = {
        "AIzaSyTestKeyOneForWorkerLifecycle": ("OK", "Ключ успешно проверен"),
        "AIzaSyTestKeyTwoForWorkerLifecycle": ("RESOURCE_EXHAUSTED", "Лимит исчерпан"),
    }

    def fake_check(key_str: str, model: str, proxy: Any = None):
        return mock_results.get(key_str, ("INTERNAL_ERROR", "Unknown"))

    monkeypatch.setattr("gemini_nexus.ui.workers.check_worker.check_api_key", fake_check)

    worker = CheckWorker(
        keys_to_check=keys,
        model="gemini-3.8-flash",
        proxy_url=None,
        delay_min=0.01,
        delay_max=0.02,
    )

    progress_events = []
    stats_events = []
    log_events = []
    key_events = []
    finished_called = []

    worker.progress_updated.connect(lambda current, total: progress_events.append((current, total)))
    worker.stats_updated.connect(lambda s: stats_events.append(dict(s)))
    worker.log_emitted.connect(lambda msg, tag: log_events.append((msg, tag)))
    worker.key_finished.connect(lambda k_id, status, detail: key_events.append((k_id, status, detail)))
    worker.all_finished.connect(lambda: finished_called.append(True))

    worker.run()

    assert len(finished_called) == 1
    assert len(key_events) == 2
    assert key_events[0] == (10, "OK", "Ключ успешно проверен")
    assert key_events[1] == (20, "RESOURCE_EXHAUSTED", "Лимит исчерпан")

    assert len(progress_events) == 2
    assert progress_events[-1] == (2, 2)

    assert len(stats_events) >= 2
    final_stats = stats_events[-1]
    assert final_stats["total"] == 2
    assert final_stats["checked"] == 2
    assert final_stats["ok"] == 1
    assert final_stats["limits"] == 1

    assert any(tag == "SYS" for _, tag in log_events)
    assert any(tag == "OK" for _, tag in log_events)
    assert any(tag == "WARN" for _, tag in log_events)


def test_check_worker_stop_during_run(qapp, monkeypatch):
    """Verify CheckWorker terminates loop when stop() is invoked."""
    keys: list[dict[str, Any]] = [
        {"id": 1, "key_string": "AIzaSyKeyFirstToProcess"},
        {"id": 2, "key_string": "AIzaSyKeySecondShouldNotProcess"},
        {"id": 3, "key_string": "AIzaSyKeyThirdShouldNotProcess"},
    ]

    def fake_check(key_str: str, model: str, proxy: Any = None):
        return "OK", "Valid"

    monkeypatch.setattr("gemini_nexus.ui.workers.check_worker.check_api_key", fake_check)

    worker = CheckWorker(
        keys_to_check=keys,
        model="gemini-3.8-flash",
        delay_min=0.01,
        delay_max=0.02,
    )

    key_events = []
    log_events = []

    def on_key_finished(k_id, status, detail):
        key_events.append(k_id)
        # Stop worker after first key
        worker.stop()

    worker.key_finished.connect(on_key_finished)
    worker.log_emitted.connect(lambda msg, tag: log_events.append((msg, tag)))

    worker.run()

    # Should only have processed key 1 before stopping
    assert len(key_events) == 1
    assert key_events[0] == 1
    assert any("остановлена" in msg for msg, _ in log_events)
