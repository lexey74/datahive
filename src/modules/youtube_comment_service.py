#!/usr/bin/env python3
"""
YouTube Comments Downloader

Скачивает комментарии с YouTube видео и Shorts используя youtube-comment-downloader.
Поддерживает:
- Основные комментарии
- Ответы на комментарии
- Сортировку по популярности и времени
- Ограничение количества комментариев
- Форматирование в Markdown
"""

import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from youtube_comment_downloader import (
    YoutubeCommentDownloader,
    SORT_BY_POPULAR,
    SORT_BY_RECENT,
)


class YouTubeCommentService:
    """Сервис для скачивания комментариев YouTube"""

    def __init__(self):
        """Инициализация"""
        self.downloader = YoutubeCommentDownloader()

    def extract_video_id(self, url: str) -> Optional[str]:
        """
        Извлекает video ID из URL YouTube

        Поддерживаемые форматы:
        - https://youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://youtube.com/shorts/VIDEO_ID
        - https://m.youtube.com/watch?v=VIDEO_ID
        """
        patterns = [
            r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
            r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
            r"youtube\.com/v/([a-zA-Z0-9_-]{11})",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    def download_comments(
        self,
        url: str,
        output_file: Optional[Path] = None,
        max_comments: Optional[int] = None,
        sort_by: str = "popular",
        include_replies: bool = True,
    ) -> Dict[str, Any]:
        """
        Скачивает комментарии с YouTube видео

        Args:
            url: URL YouTube видео или Shorts
            output_file: Путь к файлу для сохранения (если None, не сохраняет)
            max_comments: Максимальное количество комментариев (None = все)
            sort_by: Сортировка ('popular' или 'recent')
            include_replies: Включать ли ответы на комментарии

        Returns:
            Dict с информацией о комментариях:
            {
                'video_id': str,
                'url': str,
                'total_comments': int,
                'comments': List[Dict],
                'output_file': Optional[Path]
            }
        """
        # Извлекаем video ID
        video_id = self.extract_video_id(url)
        if not video_id:
            raise ValueError(f"Не удалось извлечь video ID из URL: {url}")

        # Определяем сортировку
        sort_mode = SORT_BY_POPULAR if sort_by == "popular" else SORT_BY_RECENT

        # Скачиваем комментарии
        print(f"💬 Скачивание комментариев: {video_id}")
        print(f"   Сортировка: {sort_by}")
        if max_comments:
            print(f"   Лимит: {max_comments} комментариев")

        comments = []
        try:
            comment_generator = self.downloader.get_comments_from_url(
                url, sort_by=sort_mode
            )

            for i, comment in enumerate(comment_generator, 1):
                # Добавляем комментарий
                comments.append(comment)

                # Проверяем лимит
                if max_comments and i >= max_comments:
                    break

                # Показываем прогресс каждые 50 комментариев
                if i % 50 == 0:
                    print(f"   Загружено: {i} комментариев...")

        except Exception as e:
            print(f"⚠️  Ошибка при скачивании комментариев: {e}")

        print(f"✅ Загружено: {len(comments)} комментариев")

        # Сохраняем в файл, если указан
        if output_file and comments:
            self.save_to_markdown(comments, output_file, video_id, url)

        return {
            "video_id": video_id,
            "url": url,
            "total_comments": len(comments),
            "comments": comments,
            "output_file": output_file if output_file and comments else None,
        }

    def save_to_markdown(
        self, comments: List[Dict[str, Any]], output_file: Path, video_id: str, url: str
    ):
        """
        Сохраняет комментарии в Markdown файл

        Args:
            comments: Список комментариев
            output_file: Путь к файлу
            video_id: ID видео
            url: URL видео
        """
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            # Заголовок
            f.write("# Комментарии YouTube\n\n")
            f.write(f"**Video ID:** {video_id}\n")
            f.write(f"**URL:** {url}\n")
            f.write(f"**Всего комментариев:** {len(comments)}\n")
            f.write(
                f"**Дата скачивания:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )
            f.write("---\n\n")

            # Комментарии
            for i, comment in enumerate(comments, 1):
                # Основная информация
                author = comment.get("author", "Unknown")
                text = comment.get("text", "").strip()
                votes = comment.get("votes", 0)
                time = comment.get("time", "")

                # Проверка на ответ
                is_reply = comment.get("parent", None) is not None
                indent = "  " if is_reply else ""

                # Заголовок комментария
                f.write(f"{indent}## {i}. {author}\n\n")

                # Метаинформация
                f.write(f"{indent}**Лайков:** {votes}")
                if time:
                    f.write(f" • **Время:** {time}")
                if is_reply:
                    f.write(f" • **Ответ на:** #{comment.get('parent')}")
                f.write("\n\n")

                # Текст комментария
                f.write(f"{indent}{text}\n\n")

                # Разделитель
                if not is_reply:
                    f.write("---\n\n")

        print(f"💾 Сохранено в: {output_file}")

    def get_comment_stats(self, comments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Получает статистику по комментариям

        Args:
            comments: Список комментариев

        Returns:
            Dict со статистикой
        """
        if not comments:
            return {
                "total": 0,
                "replies": 0,
                "top_comments": 0,
                "total_votes": 0,
                "avg_votes": 0,
                "most_liked": None,
            }

        # Считаем статистику
        replies = sum(1 for c in comments if c.get("parent"))
        top_comments = len(comments) - replies

        # Преобразуем votes в int (могут быть строками)
        def get_votes(comment):
            votes = comment.get("votes", 0)
            if isinstance(votes, str):
                # Убираем запятые и преобразуем в int
                votes = votes.replace(",", "").replace(" ", "")
                try:
                    return int(votes)
                except ValueError:
                    return 0
            return int(votes) if votes else 0

        total_votes = sum(get_votes(c) for c in comments)
        avg_votes = total_votes / len(comments) if comments else 0

        # Находим самый популярный комментарий
        most_liked = max(comments, key=lambda c: get_votes(c))

        return {
            "total": len(comments),
            "replies": replies,
            "top_comments": top_comments,
            "total_votes": total_votes,
            "avg_votes": round(avg_votes, 1),
            "most_liked": {
                "author": most_liked.get("author"),
                "text": most_liked.get("text", "")[:100] + "..."
                if len(most_liked.get("text", "")) > 100
                else most_liked.get("text", ""),
                "votes": get_votes(most_liked),
            },
        }


def main():
    """Точка входа для тестирования"""
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: python youtube_comments_downloader.py <youtube_url> [max_comments]"
        )
        print("\nExample:")
        print("  python youtube_comments_downloader.py https://youtu.be/VIDEO_ID 100")
        sys.exit(1)

    url = sys.argv[1]
    max_comments = int(sys.argv[2]) if len(sys.argv) > 2 else None

    # Создаем downloader
    downloader = YouTubeCommentService()

    # Скачиваем комментарии
    output_file = Path("comments.md")
    result = downloader.download_comments(
        url=url, output_file=output_file, max_comments=max_comments, sort_by="popular"
    )

    # Показываем статистику
    if result["comments"]:
        stats = downloader.get_comment_stats(result["comments"])

        print("\n" + "=" * 70)
        print("📊 СТАТИСТИКА КОММЕНТАРИЕВ")
        print("=" * 70)
        print(f"📝 Всего комментариев: {stats['total']}")
        print(f"💬 Основных: {stats['top_comments']}")
        print(f"↪️  Ответов: {stats['replies']}")
        print(f"❤️  Всего лайков: {stats['total_votes']:,}")
        print(f"📈 Средние лайки: {stats['avg_votes']}")
        print()
        print("🏆 Самый популярный комментарий:")
        print(f"   Автор: {stats['most_liked']['author']}")
        print(f"   Лайков: {stats['most_liked']['votes']:,}")
        print(f"   Текст: {stats['most_liked']['text']}")
        print("=" * 70)


if __name__ == "__main__":
    main()
