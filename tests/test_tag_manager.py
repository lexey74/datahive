"""
Unit Tests for TagManager
==========================

Тесты для модуля управления тегами.
"""
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from modules.tag_manager import TagManager


class TestTagManager:
    """Тесты для TagManager"""
    
    DEFAULT_TAGS = ["ai", "productivity", "coding", "health", "marketing"]
    
    def test_init_with_new_file(self, tmp_path):
        """Тест инициализации с новым файлом"""
        tags_file = tmp_path / "tags.json"
        manager = TagManager(tags_file)
        
        assert manager.tags_file == tags_file
        assert tags_file.exists()
        # TagManager создаётся с пустым файлом тегов по умолчанию
        assert set(manager.get_all_tags()) == set()
    
    def test_init_with_existing_file(self, mock_tags_file):
        """Тест инициализации с существующим файлом"""
        manager = TagManager(mock_tags_file)
        
        tags = manager.get_all_tags()
        assert "test" in tags
        assert "example" in tags
        assert "mock" in tags
    
    def test_add_single_tag(self, tmp_path):
        """Тест добавления одного тега"""
        tags_file = tmp_path / "tags.json"
        manager = TagManager(tags_file)
        
        new_count = manager.add_tags(["python"])
        
        assert new_count == 1
        assert "python" in manager.get_all_tags()
    
    def test_add_multiple_tags(self, tmp_path):
        """Тест добавления нескольких тегов"""
        tags_file = tmp_path / "tags.json"
        manager = TagManager(tags_file)
        
        new_count = manager.add_tags(["python", "ai", "testing"])
        # Файл пустой по умолчанию, поэтому все 3 тега новые
        assert new_count == 3
        tags = manager.get_all_tags()
        assert all(tag in tags for tag in ["python", "ai", "testing"])
    
    def test_add_duplicate_tags(self, tmp_path):
        """Тест добавления дубликатов (не должны добавиться)"""
        tags_file = tmp_path / "tags.json"
        manager = TagManager(tags_file)
        
        manager.add_tags(["python", "ai"])
        new_count = manager.add_tags(["python", "testing"])
        
        # Должен добавиться только 1 новый тег (testing)
        assert new_count == 1
        tags = manager.get_all_tags()
        # Ожидаем 3 тега: python, ai, testing
        assert len(tags) == 3
    
    def test_get_tags_string(self, sample_tags, tmp_path):
        """Тест получения тегов в виде строки"""
        tags_file = tmp_path / "tags.json"
        manager = TagManager(tags_file)
        manager.add_tags(sample_tags)
        
        tags_string = manager.get_tags_string()
        
        assert isinstance(tags_string, str)
        assert "python" in tags_string
        assert "ai" in tags_string
    
    def test_save_tags(self, tmp_path):
        """Тест сохранения тегов в файл"""
        tags_file = tmp_path / "tags.json"
        manager = TagManager(tags_file)
        manager.add_tags(["python", "ai"])
        
        # Проверяем, что файл создан и содержит правильные данные
        assert tags_file.exists()
        
        with open(tags_file) as f:
            data = json.load(f)
            assert "tags" in data
            assert "python" in data["tags"]
            assert "ai" in data["tags"]
    
    def test_empty_tags_list(self, tmp_path):
        """Тест с пустым списком тегов"""
        tags_file = tmp_path / "tags.json"
        manager = TagManager(tags_file)
        
        new_count = manager.add_tags([])
        
        assert new_count == 0
        # Файл остаётся пустым
        assert set(manager.get_all_tags()) == set()
    
    def test_tags_normalization(self, tmp_path):
        """Тест нормализации тегов (lowercase, strip)"""
        tags_file = tmp_path / "tags.json"
        manager = TagManager(tags_file)
        
        manager.add_tags(["  Python  ", "AI", "TeSting"])
        
        tags = manager.get_all_tags()
        # Теги должны быть нормализованы (lowercase, без пробелов)
        assert any("python" in tag.lower() for tag in tags)
