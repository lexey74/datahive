"""
Advanced YouTube Grabber - С обходом блокировок и ротацией прокси
"""
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
import subprocess
import json
import re
import time
import random
from datetime import datetime, timedelta


@dataclass
class YouTubeContent:
    """Структура данных YouTube видео"""
    video_id: str
    title: str
    author: str
    description: str
    duration: int
    upload_date: str
    view_count: int
    like_count: int
    comment_count: int
    tags: List[str]
    categories: List[str]
    video_path: Optional[Path] = None
    audio_path: Optional[Path] = None
    thumbnail_path: Optional[Path] = None
    comments: List[Dict] = None
    
    def __post_init__(self):
        if self.comments is None:
            self.comments = []


class ProxyManager:
    """Менеджер прокси-серверов"""
    
    def __init__(self, proxies_file: Optional[Path] = None):
        """
        Args:
            proxies_file: Файл с прокси в формате: http://user:pass@host:port
        """
        self.proxies: List[str] = []
        self.current_index = 0
        self.failed_proxies: set = set()
        
        if proxies_file and proxies_file.exists():
            self.load_proxies(proxies_file)
    
    def load_proxies(self, file_path: Path) -> None:
        """Загружает прокси из файла"""
        try:
            with open(file_path, 'r') as f:
                self.proxies = [line.strip() for line in f if line.strip()]
            print(f"✅ Загружено {len(self.proxies)} прокси")
        except Exception as e:
            print(f"❌ Ошибка загрузки прокси: {e}")
    
    def get_next_proxy(self) -> Optional[str]:
        """Возвращает следующий рабочий прокси"""
        if not self.proxies:
            return None
        
        # Пробуем найти рабочий прокси
        attempts = 0
        while attempts < len(self.proxies):
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            
            if proxy not in self.failed_proxies:
                return proxy
            
            attempts += 1
        
        # Если все прокси отказали, сбрасываем список неудач
        self.failed_proxies.clear()
        return self.proxies[0] if self.proxies else None
    
    def mark_failed(self, proxy: str) -> None:
        """Помечает прокси как неработающий"""
        self.failed_proxies.add(proxy)


class AdvancedYouTubeGrabber:
    """
    Продвинутый загрузчик YouTube с обходом блокировок:
    - Ротация User-Agent
    - Поддержка прокси
    - Задержки между запросами
    - Имитация браузера
    - Автоматическая смена cookies
    """
    
    # Список реалистичных User-Agent
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    
    def __init__(
        self,
        output_dir: Path = Path('temp'),
        cookies_files: Optional[List[Path]] = None,
        proxies_file: Optional[Path] = None,
        min_delay: float = 2.0,
        max_delay: float = 5.0
    ):
        """
        Args:
            output_dir: Директория для сохранения
            cookies_files: Список файлов с cookies (для ротации)
            proxies_file: Файл с прокси-серверами
            min_delay: Минимальная задержка между запросами (сек)
            max_delay: Максимальная задержка между запросами (сек)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Cookies management
        self.cookies_files = cookies_files or []
        self.current_cookie_index = 0
        self.cookie_usage = {}  # Отслеживаем использование cookies
        
        # Proxy management
        self.proxy_manager = ProxyManager(proxies_file)
        
        # Rate limiting
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.last_request_time = 0
        
        # Stats
        self.total_requests = 0
        self.failed_requests = 0
        
        self._check_ytdlp()
    
    def _check_ytdlp(self) -> None:
        """Проверка yt-dlp"""
        try:
            result = subprocess.run(
                ['yt-dlp', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"✅ yt-dlp версия: {result.stdout.strip()}")
            else:
                raise FileNotFoundError
        except (FileNotFoundError, subprocess.TimeoutExpired):
            raise RuntimeError("yt-dlp не установлен. Установите: pip install yt-dlp")
    
    def _apply_rate_limit(self) -> None:
        """Применяет задержку между запросами"""
        if self.last_request_time > 0:
            elapsed = time.time() - self.last_request_time
            delay = random.uniform(self.min_delay, self.max_delay)
            
            if elapsed < delay:
                sleep_time = delay - elapsed
                print(f"⏱️  Задержка {sleep_time:.1f} сек (имитация человека)")
                time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _get_next_cookies(self) -> Optional[Path]:
        """Возвращает следующий файл cookies для ротации"""
        if not self.cookies_files:
            return None
        
        # Выбираем файл с наименьшим использованием
        min_usage = float('inf')
        best_cookie = None
        best_index = 0
        
        for i, cookie_file in enumerate(self.cookies_files):
            usage = self.cookie_usage.get(str(cookie_file), 0)
            if usage < min_usage:
                min_usage = usage
                best_cookie = cookie_file
                best_index = i
        
        if best_cookie:
            self.cookie_usage[str(best_cookie)] = min_usage + 1
            self.current_cookie_index = best_index
            print(f"🍪 Используем cookies: {best_cookie.name} (использований: {min_usage + 1})")
        
        return best_cookie
    
    def _get_random_user_agent(self) -> str:
        """Возвращает случайный User-Agent"""
        return random.choice(self.USER_AGENTS)
    
    def _build_base_command(self) -> List[str]:
        """Строит базовую команду yt-dlp с обходом блокировок"""
        cmd = ['yt-dlp']
        
        # User-Agent
        user_agent = self._get_random_user_agent()
        cmd.extend(['--user-agent', user_agent])
        
        # Cookies
        cookies_file = self._get_next_cookies()
        if cookies_file:
            cmd.extend(['--cookies', str(cookies_file)])
        
        # Proxy
        proxy = self.proxy_manager.get_next_proxy()
        if proxy:
            cmd.extend(['--proxy', proxy])
            print(f"🌐 Используем прокси: {proxy}")
        
        # Дополнительные опции для обхода блокировок
        cmd.extend([
            '--no-warnings',
            '--sleep-interval', str(self.min_delay),
            '--max-sleep-interval', str(self.max_delay),
            # Имитация браузера
            '--add-header', 'Accept:text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            '--add-header', 'Accept-Language:en-US,en;q=0.9',
            '--add-header', 'Accept-Encoding:gzip, deflate, br',
            '--add-header', 'DNT:1',
            '--add-header', 'Connection:keep-alive',
            '--add-header', 'Upgrade-Insecure-Requests:1',
        ])
        
        return cmd
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """Извлекает video ID из URL"""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            r'youtube\.com/v/([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def get_metadata(self, url: str, max_retries: int = 3) -> Optional[Dict]:
        """
        Получает метаданные с повторными попытками
        
        Args:
            url: YouTube URL
            max_retries: Количество попыток
        """
        print(f"📊 Получение метаданных: {url}")
        
        for attempt in range(max_retries):
            try:
                self._apply_rate_limit()
                self.total_requests += 1
                
                cmd = self._build_base_command()
                cmd.extend(['--dump-json', url])
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0:
                    error_msg = result.stderr.lower()
                    
                    # Определяем тип ошибки
                    if 'sign in' in error_msg or 'bot' in error_msg:
                        print(f"🚫 Попытка {attempt + 1}/{max_retries}: Блокировка cookies")
                        # Пробуем другие cookies
                        continue
                    elif 'geo' in error_msg or 'location' in error_msg:
                        print(f"🌍 Попытка {attempt + 1}/{max_retries}: Гео-блокировка, пробуем прокси")
                        continue
                    else:
                        print(f"❌ Ошибка: {result.stderr}")
                        self.failed_requests += 1
                        return None
                
                metadata = json.loads(result.stdout)
                print(f"✅ Метаданные получены: {metadata.get('title', 'Unknown')}")
                return metadata
                
            except subprocess.TimeoutExpired:
                print(f"⏱️  Попытка {attempt + 1}/{max_retries}: Timeout")
                continue
            except json.JSONDecodeError as e:
                print(f"❌ Ошибка парсинга JSON: {e}")
                self.failed_requests += 1
                return None
            except Exception as e:
                print(f"❌ Попытка {attempt + 1}/{max_retries}: {e}")
                continue
        
        print(f"❌ Все {max_retries} попыток неудачны")
        self.failed_requests += 1
        return None
    
    def download_video(
        self,
        url: str,
        quality: str = 'best',
        max_retries: int = 3
    ) -> Optional[Path]:
        """
        Скачивает видео с повторными попытками
        
        Args:
            url: YouTube URL
            quality: Качество видео
            max_retries: Количество попыток
        """
        print(f"📥 Загрузка видео: {url}")
        
        video_id = self._extract_video_id(url)
        if not video_id:
            print("❌ Не удалось извлечь video ID")
            return None
        
        output_template = str(self.output_dir / f"{video_id}.%(ext)s")
        
        for attempt in range(max_retries):
            try:
                self._apply_rate_limit()
                self.total_requests += 1
                
                cmd = self._build_base_command()
                cmd.extend([
                    '-f', quality,
                    '-o', output_template,
                    url
                ])
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600
                )
                
                if result.returncode != 0:
                    print(f"🔄 Попытка {attempt + 1}/{max_retries} не удалась")
                    continue
                
                # Ищем скачанный файл
                video_files = list(self.output_dir.glob(f"{video_id}.*"))
                if video_files:
                    video_path = video_files[0]
                    print(f"✅ Видео загружено: {video_path.name}")
                    return video_path
                
            except subprocess.TimeoutExpired:
                print(f"⏱️  Попытка {attempt + 1}/{max_retries}: Timeout")
                continue
            except Exception as e:
                print(f"❌ Попытка {attempt + 1}/{max_retries}: {e}")
                continue
        
        print(f"❌ Все {max_retries} попыток неудачны")
        self.failed_requests += 1
        return None
    
    def print_stats(self) -> None:
        """Выводит статистику"""
        success_rate = 0
        if self.total_requests > 0:
            success_rate = ((self.total_requests - self.failed_requests) / self.total_requests) * 100
        
        print("\n" + "="*60)
        print("📊 СТАТИСТИКА ЗАГРУЗЧИКА")
        print("="*60)
        print(f"Всего запросов: {self.total_requests}")
        print(f"Успешных: {self.total_requests - self.failed_requests}")
        print(f"Неудачных: {self.failed_requests}")
        print(f"Success Rate: {success_rate:.1f}%")
        print(f"Cookies файлов: {len(self.cookies_files)}")
        print(f"Прокси: {len(self.proxy_manager.proxies)}")
        print("="*60)
