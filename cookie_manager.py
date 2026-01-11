#!/usr/bin/env python3
"""
Cookie Manager - Управление множественными cookies для обхода блокировок
"""
from pathlib import Path
from datetime import datetime, timedelta
import json
from typing import List, Dict, Optional


class CookieManager:
    """Менеджер cookies файлов"""
    
    def __init__(self, cookies_dir: Path = Path('cookies')):
        """
        Args:
            cookies_dir: Директория с cookies файлами
        """
        self.cookies_dir = Path(cookies_dir)
        self.cookies_dir.mkdir(exist_ok=True)
        
        self.stats_file = self.cookies_dir / 'stats.json'
        self.stats = self._load_stats()
    
    def _load_stats(self) -> Dict:
        """Загружает статистику использования cookies"""
        if self.stats_file.exists():
            try:
                with open(self.stats_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _save_stats(self) -> None:
        """Сохраняет статистику"""
        with open(self.stats_file, 'w') as f:
            json.dump(self.stats, f, indent=2)
    
    def add_cookies(self, source_file: Path, name: Optional[str] = None) -> Path:
        """
        Добавляет новый файл cookies
        
        Args:
            source_file: Исходный файл cookies
            name: Имя для cookies (опционально)
        
        Returns:
            Путь к добавленному файлу
        """
        if name is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            name = f'youtube_cookies_{timestamp}.txt'
        
        dest_file = self.cookies_dir / name
        
        # Копируем файл
        import shutil
        shutil.copy2(source_file, dest_file)
        
        # Инициализируем статистику
        self.stats[name] = {
            'added': datetime.now().isoformat(),
            'last_used': None,
            'usage_count': 0,
            'success_count': 0,
            'fail_count': 0,
            'blocked': False
        }
        self._save_stats()
        
        print(f"✅ Cookies добавлены: {name}")
        return dest_file
    
    def mark_used(self, cookie_file: str, success: bool = True) -> None:
        """
        Отмечает использование cookies
        
        Args:
            cookie_file: Имя файла cookies
            success: Успешность использования
        """
        if cookie_file not in self.stats:
            self.stats[cookie_file] = {
                'added': datetime.now().isoformat(),
                'last_used': None,
                'usage_count': 0,
                'success_count': 0,
                'fail_count': 0,
                'blocked': False
            }
        
        self.stats[cookie_file]['last_used'] = datetime.now().isoformat()
        self.stats[cookie_file]['usage_count'] += 1
        
        if success:
            self.stats[cookie_file]['success_count'] += 1
        else:
            self.stats[cookie_file]['fail_count'] += 1
            
            # Если 3+ неудачи подряд, помечаем как заблокированный
            if self.stats[cookie_file]['fail_count'] >= 3:
                self.stats[cookie_file]['blocked'] = True
                print(f"⚠️  Cookies {cookie_file} заблокированы")
        
        self._save_stats()
    
    def get_best_cookies(self) -> Optional[Path]:
        """
        Возвращает лучший (наименее использованный и незаблокированный) cookies
        
        Returns:
            Путь к файлу cookies или None
        """
        cookies_files = list(self.cookies_dir.glob('*.txt'))
        if not cookies_files:
            return None
        
        best_score = float('inf')
        best_file = None
        
        for cookie_file in cookies_files:
            name = cookie_file.name
            
            # Пропускаем заблокированные
            if self.stats.get(name, {}).get('blocked', False):
                continue
            
            # Считаем score (меньше = лучше)
            usage_count = self.stats.get(name, {}).get('usage_count', 0)
            fail_count = self.stats.get(name, {}).get('fail_count', 0)
            score = usage_count * 10 + fail_count * 100
            
            if score < best_score:
                best_score = score
                best_file = cookie_file
        
        return best_file
    
    def get_all_cookies(self) -> List[Path]:
        """
        Возвращает все незаблокированные cookies
        
        Returns:
            Список путей к cookies файлам
        """
        all_cookies = []
        
        for cookie_file in self.cookies_dir.glob('*.txt'):
            name = cookie_file.name
            if not self.stats.get(name, {}).get('blocked', False):
                all_cookies.append(cookie_file)
        
        # Сортируем по количеству использований (меньше = выше)
        all_cookies.sort(key=lambda f: self.stats.get(f.name, {}).get('usage_count', 0))
        
        return all_cookies
    
    def unblock_all(self) -> None:
        """Разблокирует все cookies (после обновления)"""
        for name in self.stats:
            self.stats[name]['blocked'] = False
            self.stats[name]['fail_count'] = 0
        self._save_stats()
        print("✅ Все cookies разблокированы")
    
    def remove_old(self, days: int = 7) -> None:
        """
        Удаляет старые cookies
        
        Args:
            days: Старше скольких дней удалять
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        removed = 0
        
        for name, info in list(self.stats.items()):
            added_date = datetime.fromisoformat(info['added'])
            if added_date < cutoff_date:
                cookie_file = self.cookies_dir / name
                if cookie_file.exists():
                    cookie_file.unlink()
                del self.stats[name]
                removed += 1
        
        self._save_stats()
        print(f"🗑️  Удалено {removed} старых cookies")
    
    def print_stats(self) -> None:
        """Выводит статистику всех cookies"""
        print("\n" + "="*80)
        print("🍪 СТАТИСТИКА COOKIES")
        print("="*80)
        
        if not self.stats:
            print("Нет cookies файлов")
            return
        
        for name, info in sorted(self.stats.items()):
            status = "🚫 BLOCKED" if info['blocked'] else "✅ OK"
            added = datetime.fromisoformat(info['added']).strftime('%Y-%m-%d %H:%M')
            
            last_used = "Никогда"
            if info['last_used']:
                last_used = datetime.fromisoformat(info['last_used']).strftime('%Y-%m-%d %H:%M')
            
            print(f"\n{status} {name}")
            print(f"  Добавлен: {added}")
            print(f"  Последнее использование: {last_used}")
            print(f"  Всего использований: {info['usage_count']}")
            print(f"  Успешных: {info['success_count']}")
            print(f"  Неудачных: {info['fail_count']}")
            
            if info['usage_count'] > 0:
                success_rate = (info['success_count'] / info['usage_count']) * 100
                print(f"  Success Rate: {success_rate:.1f}%")
        
        print("="*80)


def main():
    """CLI интерфейс"""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Cookie Manager для YouTube')
    parser.add_argument('action', choices=['add', 'list', 'unblock', 'clean', 'stats'],
                       help='Действие')
    parser.add_argument('--file', type=str, help='Файл cookies для добавления')
    parser.add_argument('--name', type=str, help='Имя для cookies')
    parser.add_argument('--days', type=int, default=7, help='Дней для clean')
    
    args = parser.parse_args()
    
    manager = CookieManager()
    
    if args.action == 'add':
        if not args.file:
            print("❌ Укажите --file для добавления")
            sys.exit(1)
        
        source = Path(args.file)
        if not source.exists():
            print(f"❌ Файл не найден: {source}")
            sys.exit(1)
        
        manager.add_cookies(source, args.name)
    
    elif args.action == 'list':
        cookies = manager.get_all_cookies()
        print(f"\n📋 Найдено {len(cookies)} активных cookies:")
        for cookie in cookies:
            print(f"  - {cookie.name}")
    
    elif args.action == 'unblock':
        manager.unblock_all()
    
    elif args.action == 'clean':
        manager.remove_old(args.days)
    
    elif args.action == 'stats':
        manager.print_stats()


if __name__ == '__main__':
    main()
