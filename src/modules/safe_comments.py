#!/usr/bin/env python3
"""
SafeComments - Безопасный парсинг комментариев Instagram через Playwright
Эмулирует настоящий браузер, перехватывает GraphQL запросы
"""

import json
import time
import random
from pathlib import Path
from typing import List, Dict
from playwright.sync_api import sync_playwright, Page, BrowserContext


class SafeCommentsScraper:
    """Безопасный скрапер комментариев Instagram"""

    def __init__(
        self, cookies_file: str = "instagram_cookies.json", headless: bool = False
    ):
        """
        Инициализация скрапера

        Args:
            cookies_file: Путь к файлу с cookies
            headless: Запускать браузер в фоновом режиме (False = видимое окно)
        """
        self.cookies_file = Path(cookies_file)
        self.headless = headless
        self.captured_data: List[dict] = []

    def _handle_response(self, response):
        """
        Обработчик ответов от Instagram API
        Перехватывает GraphQL запросы с комментариями
        """
        # Фильтруем только запросы к GraphQL API комментариев
        if "graphql/query" in response.url and response.status == 200:
            try:
                data = response.json()

                # Проверяем, есть ли в ответе комментарии
                if "data" in data:
                    # Ищем структуру с комментариями
                    # Instagram использует edge_media_to_parent_comment или edge_media_preview_comment
                    has_comments = self._extract_comments_from_response(data)

                    if has_comments:
                        print("   📦 Перехвачен пакет с комментариями")
                        self.captured_data.append(data)

            except Exception:
                # Игнорируем ошибки парсинга
                pass

    def _extract_comments_from_response(self, data: dict) -> bool:
        """
        Проверяет, содержит ли ответ комментарии

        Args:
            data: JSON ответ от Instagram

        Returns:
            True если найдены комментарии
        """
        try:
            # Рекурсивный поиск ключей с комментариями
            def search_comments(obj):
                if isinstance(obj, dict):
                    # Ключи, которые указывают на комментарии
                    comment_keys = [
                        "edge_media_to_parent_comment",
                        "edge_threaded_comments",
                        "edge_media_preview_comment",
                        "edges",
                    ]

                    for key in comment_keys:
                        if key in obj and "edges" in str(obj[key]):
                            return True

                    for value in obj.values():
                        if search_comments(value):
                            return True

                elif isinstance(obj, list):
                    for item in obj:
                        if search_comments(item):
                            return True

                return False

            return search_comments(data)

        except Exception:
            return False

    def _load_cookies(self, context: BrowserContext) -> bool:
        """
        Загружает cookies из файла

        Args:
            context: Контекст браузера Playwright

        Returns:
            True если cookies загружены успешно
        """
        if not self.cookies_file.exists():
            print("   ⚠️  Cookies не найдены")
            return False

        try:
            with open(self.cookies_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
                context.add_cookies(cookies)
                print("   ✅ Cookies загружены")
                return True
        except Exception as e:
            print(f"   ⚠️  Ошибка загрузки cookies: {e}")
            return False

    def _save_cookies(self, context: BrowserContext):
        """
        Сохраняет cookies в файл

        Args:
            context: Контекст браузера Playwright
        """
        try:
            cookies = context.cookies()
            self.cookies_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.cookies_file, "w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=2)

            print("   ✅ Cookies сохранены")
        except Exception as e:
            print(f"   ⚠️  Ошибка сохранения cookies: {e}")

    def _emulate_human_behavior(self, page: Page, duration: int = 10):
        """
        Эмулирует поведение человека: скроллинг, паузы

        Args:
            page: Страница Playwright
            duration: Длительность эмуляции в секундах
        """
        print(f"   🤖 Эмуляция поведения пользователя ({duration} сек)...")

        start_time = time.time()
        scroll_count = 0

        while time.time() - start_time < duration:
            # Случайный скролл вниз
            scroll_distance = random.randint(300, 700)
            page.mouse.wheel(0, scroll_distance)
            scroll_count += 1

            # Случайная пауза
            time.sleep(random.uniform(1.5, 3.5))

            # Иногда пытаемся найти и нажать "Показать еще комментарии"
            if scroll_count % 3 == 0:
                try:
                    # Ищем кнопки по разным селекторам
                    selectors = [
                        'button:has-text("View more comments")',
                        'button:has-text("Load more comments")',
                        'button[type="button"]',
                        'svg[aria-label="Load more comments"]',
                    ]

                    for selector in selectors:
                        try:
                            if page.locator(selector).count() > 0:
                                page.locator(selector).first.click(timeout=1000)
                                print("   ⬇️  Нажата кнопка загрузки комментариев")
                                time.sleep(random.uniform(2, 4))
                                break
                        except Exception:
                            pass

                except Exception:
                    pass

            # PageDown иногда
            if scroll_count % 5 == 0:
                page.keyboard.press("PageDown")
                time.sleep(random.uniform(1, 2))

        print(f"   ✅ Эмуляция завершена (скроллов: {scroll_count})")

    def scrape_comments(self, post_url: str, scroll_duration: int = 15) -> List[Dict]:
        """
        Основной метод: скрапит комментарии с поста

        Args:
            post_url: URL поста Instagram
            scroll_duration: Сколько секунд скроллить (больше = больше комментариев)

        Returns:
            Список комментариев в формате [{'user': str, 'text': str}, ...]
        """
        print("🎭 Запуск безопасного браузера...")

        self.captured_data = []

        with sync_playwright() as p:
            # Запуск браузера с антидетект параметрами
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",  # Скрываем автоматизацию
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ],
            )

            # Создаем контекст с реалистичными параметрами
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                timezone_id="America/New_York",
            )

            # Загружаем cookies
            self._load_cookies(context)

            # Создаем страницу
            page = context.new_page()

            # Подключаем перехватчик ответов
            page.on("response", self._handle_response)

            # Переходим на пост с увеличенным timeout
            print(f"🔗 Переход на: {post_url}")
            try:
                page.goto(post_url, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                print(f"   ⚠️  Загрузка заняла больше времени: {e}")
                # Продолжаем даже если timeout - страница может быть частично загружена

            # Ждем загрузки
            time.sleep(random.uniform(3, 5))

            # Проверяем, не требуется ли логин
            if (
                "login" in page.url
                or page.locator('input[name="username"]').count() > 0
            ):
                print("   🔐 Требуется авторизация!")

                if not self.headless:
                    print("   ⏳ Войдите вручную в открывшемся окне (60 секунд)...")
                    time.sleep(60)

                    # Сохраняем cookies после входа
                    self._save_cookies(context)
                else:
                    print(
                        "   ❌ Не могу войти в headless режиме. Используйте headless=False"
                    )
                    browser.close()
                    return []

            # Эмулируем поведение человека
            self._emulate_human_behavior(page, duration=scroll_duration)

            # Закрываем браузер
            browser.close()

        print(f"   📊 Перехвачено пакетов данных: {len(self.captured_data)}")

        # Парсим комментарии из перехваченных данных
        comments = self._parse_comments_from_captured_data()

        print(f"   💬 Извлечено комментариев: {len(comments)}")

        return comments

    def _parse_comments_from_captured_data(self) -> List[Dict]:
        """
        Парсит комментарии из перехваченных GraphQL ответов

        Returns:
            Список комментариев [{'user': str, 'text': str, 'likes': int}, ...]
        """
        all_comments = []
        seen_ids = set()  # Дедупликация

        for data in self.captured_data:
            try:
                comments = self._extract_comments_recursive(data)

                for comment in comments:
                    # Дедупликация по ID
                    comment_id = comment.get("id", hash(comment["text"]))
                    if comment_id not in seen_ids:
                        seen_ids.add(comment_id)
                        all_comments.append(comment)

            except Exception as e:
                print(f"   ⚠️  Ошибка парсинга: {e}")
                continue

        return all_comments

    def _extract_comments_recursive(self, obj, comments=None) -> List[Dict]:
        """
        Рекурсивно извлекает комментарии из JSON структуры

        Args:
            obj: JSON объект
            comments: Аккумулятор комментариев

        Returns:
            Список комментариев
        """
        if comments is None:
            comments = []

        if isinstance(obj, dict):
            # Проверяем, это комментарий?
            if "node" in obj and isinstance(obj["node"], dict):
                node = obj["node"]

                # Извлекаем данные комментария
                if "text" in node:
                    comment = {
                        "id": node.get("id", ""),
                        "user": node.get("owner", {}).get("username", "unknown"),
                        "text": node.get("text", ""),
                        "likes": node.get("edge_liked_by", {}).get("count", 0),
                        "created_at": node.get("created_at", 0),
                    }
                    comments.append(comment)

            # Рекурсивно обходим все значения
            for value in obj.values():
                self._extract_comments_recursive(value, comments)

        elif isinstance(obj, list):
            for item in obj:
                self._extract_comments_recursive(item, comments)

        return comments

    def save_raw_data(self, filepath: str = "raw_comments_data.json"):
        """
        Сохраняет сырые перехваченные данные в файл

        Args:
            filepath: Путь к файлу для сохранения
        """
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.captured_data, f, ensure_ascii=False, indent=2)
            print(f"   💾 Сырые данные сохранены: {filepath}")
        except Exception as e:
            print(f"   ⚠️  Ошибка сохранения: {e}")


# Пример использования
if __name__ == "__main__":
    scraper = SafeCommentsScraper(
        cookies_file="instagram_cookies.json",
        headless=False,  # Видимое окно для первого запуска
    )

    post_url = "https://www.instagram.com/p/EXAMPLE/"
    comments = scraper.scrape_comments(post_url, scroll_duration=15)

    print("\n📊 Результат:")
    for i, comment in enumerate(comments[:10], 1):
        print(f"{i}. {comment['user']}: {comment['text'][:50]}...")

    # Сохраняем сырые данные для анализа
    scraper.save_raw_data()
