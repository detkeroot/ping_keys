"""Information and documentation view for Gemini Nexus DB."""

from PyQt6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

from gemini_nexus.core.config import APP_NAME, APP_VERSION, AUTHOR


class InfoView(QWidget):
    """Documentation and reference guide explaining statuses, models, and usage guidelines."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setStyleSheet("""
            QTextBrowser {
                background-color: #161619;
                color: #d8d8d8;
                border: 1px solid #28282e;
                border-radius: 8px;
                padding: 16px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                font-size: 13px;
                line-height: 1.6;
            }
        """)

        html_content = self._generate_html()
        self.browser.setHtml(html_content)
        layout.addWidget(self.browser)

    def get_info_text(self) -> str:
        """Return plain text representation of documentation for automated testing and search."""
        return self.browser.toPlainText()

    def _generate_html(self) -> str:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                h1 {{ color: #3498db; margin-top: 0; font-size: 22px; border-bottom: 2px solid #2980b9; padding-bottom: 6px; }}
                h2 {{ color: #2ecc71; margin-top: 20px; font-size: 16px; border-bottom: 1px solid #27ae60; padding-bottom: 4px; }}
                h3 {{ color: #f39c12; margin-top: 14px; font-size: 14px; }}
                p, li {{ line-height: 1.6; color: #cccccc; }}
                code {{ background-color: #202025; color: #1abc9c; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 12px; }}
                .badge-ok {{ color: #2ecc71; font-weight: bold; }}
                .badge-limit {{ color: #f39c12; font-weight: bold; }}
                .badge-dead {{ color: #e74c3c; font-weight: bold; }}
                .badge-sys {{ color: #3498db; font-weight: bold; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                th, td {{ border: 1px solid #2a2a30; padding: 6px 10px; text-align: left; }}
                th {{ background-color: #1f1f24; color: #e0e0e0; }}
                tr:nth-child(even) {{ background-color: #1a1a1f; }}
                .footer {{ margin-top: 30px; font-size: 11px; color: #777777; border-top: 1px solid #2a2a30; padding-top: 10px; }}
            </style>
        </head>
        <body>
            <h1>{APP_NAME} v{APP_VERSION}</h1>
            <p>
                <b>{APP_NAME}</b> — профессиональная модульная система управления, верификации и Round-Robin
                балансировки пула API ключей Google Gemini с нативной поддержкой Wayland HiDPI.
            </p>

            <h2>🎯 Поддерживаемые модели Gemini 3.x</h2>
            <p>Система валидирует и балансирует ключи для линейки моделей третьего поколения:</p>
            <ul>
                <li><code>gemini-3.8-flash</code> — флагманская скоростная мультимодальная модель следующего поколения.</li>
                <li><code>gemini-3.8-flash-high</code> — высокопроизводительный вариант с расширенным окном рассуждений.</li>
                <li><code>gemini-3.7-flash</code> — стабильная быстрая модель общего назначения.</li>
                <li><code>gemini-3.5-flash</code> — оптимизированная модель для потоковых запросов.</li>
                <li><code>gemini-3.1-flash-lite-preview</code> — ультралегкая модель с минимальными задержками.</li>
                <li><code>gemma-3-27b-it</code> — открытая 27B модель Google DeepMind с инструктивной оптимизацией.</li>
            </ul>

            <h2>📊 Классификатор статусов валидации</h2>
            <table>
                <tr>
                    <th>Код статуса</th>
                    <th>Значение</th>
                    <th>Действие</th>
                </tr>
                <tr>
                    <td><span class="badge-ok">OK</span></td>
                    <td>Ключ полностью активен и генерирует контент</td>
                    <td>Готов к использованию и сплиттеру</td>
                </tr>
                <tr>
                    <td><span class="badge-limit">RESOURCE_EXHAUSTED</span></td>
                    <td>Лимит запросов исчерпан (HTTP 429)</td>
                    <td>Временное ограничение (RPM/TPM). Рекомендуется пауза.</td>
                </tr>
                <tr>
                    <td><span class="badge-limit">UNRESTRICTED</span></td>
                    <td>Ограничен Google (политика ограничений)</td>
                    <td>Проверить доступность проекта в Google AI Studio.</td>
                </tr>
                <tr>
                    <td><span class="badge-dead">PERMISSION_DENIED</span></td>
                    <td>Блокировка или запрет доступа (HTTP 403)</td>
                    <td>Удалить через «Удалить мёртвые».</td>
                </tr>
                <tr>
                    <td><span class="badge-dead">UNAUTHORIZED</span></td>
                    <td>Ключ не существует или отозван (HTTP 401)</td>
                    <td>Удалить из базы.</td>
                </tr>
                <tr>
                    <td><span class="badge-dead">FAILED_PRECONDITION</span></td>
                    <td>Региональные ограничения / проблемы биллинга (HTTP 400)</td>
                    <td>Требуется прокси поддерживаемого региона.</td>
                </tr>
                <tr>
                    <td><span class="badge-sys">SERVICE_UNAVAILABLE</span></td>
                    <td>Сервис Google временно перегружен (HTTP 503)</td>
                    <td>Повторить проверку позже.</td>
                </tr>
                <tr>
                    <td><span class="badge-sys">DEADLINE_EXCEEDED</span></td>
                    <td>Таймаут генерации (HTTP 504)</td>
                    <td>Проверить сетевой маршрут или поднять таймаут.</td>
                </tr>
            </table>

            <h2>👥 Рекомендации по работе с донатерами</h2>
            <ul>
                <li><b>Добавление донатеров:</b> Всегда группируйте ключи по авторам/донатерам для удобства учёта.</li>
                <li><b>Игнорирование:</b> Используйте функцию «Игнорировать» (👁️) для временного исключения ключей из пула без их удаления.</li>
                <li><b>Пакетный ввод:</b> Поле добавления принимает списки ключей в произвольном количестве (по одному в строке). Дубликаты отсеиваются автоматически.</li>
            </ul>

            <h2>🔀 Рекомендации по сплиттеру и анти-лимитам</h2>
            <ul>
                <li><b>Задержки:</b> Рекомендуемый интервал проверки — от <code>7.0</code> до <code>10.0</code> секунд на ключ во избежание срабатывания Cloud Quota.</li>
                <li><b>Балансировка:</b> Инструмент «Сплиттер» разделяет активные ключи по алгоритму Round-Robin на N независимых файлов потоков (<code>stream_1.txt</code>, <code>stream_2.txt</code>...).</li>
                <li><b>Прокси:</b> При проверке из регионов с геоблокировкой активируйте SOCKS5/HTTP прокси в настройках чекера.</li>
            </ul>

            <h2>🔒 Безопасность и хранение данных</h2>
            <p>
                Все ключи хранятся локально в реляционной базе данных SQLite с режимом журнала <b>WAL (Write-Ahead Logging)</b>
                и целостностью внешних ключей. Никакие данные не передаются на сторонние серверы, кроме прямого API Google.
            </p>

            <div class="footer">
                Разработано: <b>{AUTHOR}</b> | Проект под лицензией MIT | Архитектура PyQt6 Wayland HiDPI
            </div>
        </body>
        </html>
        """
