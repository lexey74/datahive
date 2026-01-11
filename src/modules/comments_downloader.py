"""
Comments Downloader

Универсальный скачиватель комментариев для всех платформ.
Используется другими подмодулями.
"""
import json
import subprocess
from typing import List, Dict, Optional
from pathlib import Path

from .downloader_utils import print_progress, format_count


class CommentsDownloader:
    """
    Универсальный скачиватель комментариев
    
    Поддерживает:
    - YouTube комментарии (через yt-dlp)
    - Instagram комментарии (TODO: через API)
    """
    
    def __init__(
        self,
        youtube_cookies: Optional[Path] = None,
        instagram_cookies: Optional[Path] = None
    ):
        """
        Args:
            youtube_cookies: Путь к YouTube cookies
            instagram_cookies: Путь к Instagram cookies
        """
        self.youtube_cookies = youtube_cookies
        self.instagram_cookies = instagram_cookies
    
    def download_youtube_comments(
        self,
        video_id: str,
        max_comments: int = 100
    ) -> List[Dict]:
        """
        Скачивает комментарии YouTube видео
        
        Args:
            video_id: ID видео
            max_comments: Максимум комментариев
            
        Returns:
            Список комментариев
        """
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            cmd = [
                'yt-dlp',
                '--skip-download',
                '--write-comments',
                '--extractor-args', f'youtube:max_comments={max_comments}',
                '--print', '%(comments)j',
            ]
            
            # Добавляем cookies если есть
            if self.youtube_cookies and self.youtube_cookies.exists():
                cmd.extend(['--cookies', str(self.youtube_cookies)])
            
            cmd.append(url)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=60
            )
            
            # Парсим комментарии
            if result.stdout.strip():
                comments_raw = json.loads(result.stdout)
                return self._format_youtube_comments(comments_raw)
            
            return []
            
        except subprocess.TimeoutExpired:
            print_progress("⚠️  Превышен таймаут скачивания комментариев", "")
            return []
        except subprocess.CalledProcessError as e:
            print_progress(f"⚠️  Ошибка yt-dlp: {e.stderr}", "")
            return []
        except json.JSONDecodeError:
            print_progress("⚠️  Ошибка парсинга комментариев", "")
            return []
    
    def download_instagram_comments(
        self,
        post_id: str,
        max_comments: int = 100
    ) -> List[Dict]:
        """
        Скачивает комментарии Instagram поста/reels
        
        Args:
            post_id: ID поста (shortcode)
            max_comments: Максимум комментариев
            
        Returns:
            Список комментариев
        """
        # TODO: Реализовать через Instagram API или scraping
        # Требует авторизации и работы с GraphQL API
        print_progress("⚠️  Instagram комментарии пока не поддерживаются", "")
        return []
    
    def _format_youtube_comments(self, comments_raw: List[Dict]) -> List[Dict]:
        """
        Форматирует сырые комментарии YouTube
        
        Args:
            comments_raw: Сырые данные от yt-dlp
            
        Returns:
            Отформатированные комментарии
        """
        formatted = []
        
        for comment in comments_raw:
            formatted.append({
                'author': comment.get('author', 'Unknown'),
                'text': comment.get('text', ''),
                'likes': comment.get('like_count', 0),
                'timestamp': comment.get('timestamp'),
                'is_favorited': comment.get('is_favorited', False),
                'parent': comment.get('parent', 'root'),  # root или ID родительского комментария
                'replies_count': comment.get('replies', 0)
            })
        
        return formatted
    
    @staticmethod
    def save_comments_to_file(comments: List[Dict], output_path: Path) -> Path:
        """
        Сохраняет комментарии в файл
        
        Args:
            comments: Список комментариев
            output_path: Путь к файлу
            
        Returns:
            Путь к сохраненному файлу
        """
        # Сохраняем в JSON
        json_path = output_path.with_suffix('.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(comments, f, ensure_ascii=False, indent=2)
        
        # Сохраняем в Markdown для читаемости
        md_path = output_path.with_suffix('.md')
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(f"# Комментарии ({len(comments)})\n\n")
            
            for i, comment in enumerate(comments, 1):
                author = comment['author']
                text = comment['text']
                likes = comment.get('likes', 0)
                
                f.write(f"## {i}. @{author}\n\n")
                f.write(f"{text}\n\n")
                if likes > 0:
                    f.write(f"👍 {format_count(likes)}\n\n")
                f.write("---\n\n")
        
        print_progress(f"💾 Комментарии сохранены: {json_path.name}, {md_path.name}", "")
        return md_path
