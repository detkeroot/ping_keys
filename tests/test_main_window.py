"""Unit and integration tests for Gemini Nexus PyQt6 MainWindow and application entrypoint."""

from unittest.mock import MagicMock

import pytest
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QApplication, QStackedWidget

from gemini_nexus.core.config import APP_NAME, AUTHOR
from gemini_nexus.core.db import Database
from gemini_nexus.ui.main_window import MainWindow
from gemini_nexus.ui.views import (
    CheckerView,
    InfoView,
    ManagerView,
    SplitterView,
)


@pytest.fixture(scope="session")
def qapp():
    """Ensure a headless offscreen QApplication exists for widget testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app


@pytest.fixture
def test_db(tmp_path):
    """Fixture providing an initialized temporary database."""
    db_path = tmp_path / "test_main_window.db"
    db = Database(str(db_path))
    db.init_db()
    return db


def test_main_window_init(qapp, test_db):
    """Test MainWindow initialization, title, views in QStackedWidget, and default index."""
    window = MainWindow(test_db)
    assert window is not None

    # Title check
    title = window.windowTitle()
    assert APP_NAME in title
    assert AUTHOR in title

    # Stacked widget check
    assert hasattr(window, "stacked_widget")
    assert isinstance(window.stacked_widget, QStackedWidget)
    assert window.stacked_widget.count() == 4

    assert isinstance(window.stacked_widget.widget(0), ManagerView)
    assert isinstance(window.stacked_widget.widget(1), CheckerView)
    assert isinstance(window.stacked_widget.widget(2), SplitterView)
    assert isinstance(window.stacked_widget.widget(3), InfoView)

    assert window.stacked_widget.currentIndex() == 0


def test_sidebar_navigation(qapp, test_db):
    """Test that sidebar buttons switch QStackedWidget views and update active states."""
    window = MainWindow(test_db)

    # Click Checker button -> index 1
    window.btn_nav_checker.click()
    assert window.stacked_widget.currentIndex() == 1
    assert isinstance(window.stacked_widget.currentWidget(), CheckerView)

    # Click Splitter button -> index 2
    window.btn_nav_splitter.click()
    assert window.stacked_widget.currentIndex() == 2
    assert isinstance(window.stacked_widget.currentWidget(), SplitterView)

    # Click Info button -> index 3
    window.btn_nav_info.click()
    assert window.stacked_widget.currentIndex() == 3
    assert isinstance(window.stacked_widget.currentWidget(), InfoView)

    # Click Manager button -> index 0
    window.btn_nav_manager.click()
    assert window.stacked_widget.currentIndex() == 0
    assert isinstance(window.stacked_widget.currentWidget(), ManagerView)


def test_close_event_without_worker(qapp, test_db):
    """Test closeEvent when no worker is running."""
    window = MainWindow(test_db)
    event = QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted()


def test_close_event_with_running_worker(qapp, test_db):
    """Test closeEvent stops running worker in CheckerView."""
    window = MainWindow(test_db)

    # Mock a running worker on checker view
    mock_worker = MagicMock()
    mock_worker.isRunning.return_value = True
    window.checker_view.worker = mock_worker

    event = QCloseEvent()
    window.closeEvent(event)

    mock_worker.stop.assert_called_once()
    assert event.isAccepted()


def test_counter_badge_update(qapp, test_db):
    """Test that key counter summary label correctly reflects database keys count."""
    owner_id = test_db.add_owner("Donor1")
    test_db.add_keys(owner_id, ["AIzaSyTestKey1", "AIzaSyTestKey2"])

    window = MainWindow(test_db)
    assert hasattr(window, "lbl_key_counter")
    window.update_status_summary()
    assert "2" in window.lbl_key_counter.text()


def test_main_entrypoint(monkeypatch, tmp_path):
    """Test that main() initializes database, applies dark theme, shows window, and returns exit code."""
    temp_db_path = str(tmp_path / "main_entrypoint.db")
    monkeypatch.setattr("gemini_nexus.main.Database", lambda: Database(temp_db_path))
    monkeypatch.setattr("PyQt6.QtWidgets.QApplication.exec", lambda self: 0)

    from gemini_nexus.main import main

    exit_code = main(["-platform", "offscreen"])
    assert exit_code == 0
