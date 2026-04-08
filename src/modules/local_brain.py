"""
LocalBrain - Анализ контента через локальную LLM (Ollama)
"""
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class LocalBrain:
    """Интеллектуальная обработка через Ollama"""
    
    SYSTEM_PROMPT = """Role: You are a Librarian for a personal Knowledge Base.

Input Data:
1. Post Text & Author
2. Video Transcript (with timestamps)
3. User Comments
4. KNOWN TAGS LIST: [{known_tags}]

Tasks:
1. Analyze: Understand the core meaning of the content.

2. Tagging (Priority):
   - Check the KNOWN TAGS LIST first. If a tag fits, USE IT. Do not create synonyms (e.g., if 'coding' exists, do not create 'programming').
   - Create NEW tags only if the topic is completely new.
   - Format: English, lowercase, snake_case.
   - Limit: Max 15 tags total.

3. Categorize: Choose ONE Category (Tutorial, Opinion, News, Life, Humor).

4. Summary: Create a concise bullet-point summary (3-5 points) in Russian. Use timestamps [MM:SS] if referring to video parts.

5. Filter Comments: Keep ONLY comments that add value (critique, personal experience, alternative tools). Remove generic praise ("cool", "thanks").

6. Wiki-Links: In the summary field, wrap key terms, names, tools, and concepts in Obsidian wiki-links: [[term]].
   - Only wrap significant nouns/proper names (not verbs or common words).
   - Examples: [[Python]], [[Andrej Karpathy]], [[Transformer]], [[RAG]].

Output: strictly JSON.
{
  "summary": "markdown string with bullet points and [[wiki-links]] for key terms",
  "category": "string",
  "tags": ["tag1", "tag2"],
  "valuable_comments": ["user: text", "user: text"]
}
"""
    
    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434") -> None:
        """
        Инициализация LLM клиента
        
        Args:
            model: Название модели Ollama
            base_url: URL Ollama сервера
        """
        self.model = model
        self.base_url = base_url
        self.client = None
        self.num_threads = None
        self.num_ctx = None
    
    def initialize(self) -> None:
        """Инициализация клиента Ollama"""
        try:
            import ollama
            self.client = ollama.Client(host=self.base_url)
            logger.info(f"✅ Ollama подключен: {self.model} @ {self.base_url}")

        except ImportError:
            raise ImportError(
                "Библиотека ollama не установлена. "
                "Установите: pip install ollama"
            )
        except Exception as e:
            raise ConnectionError(f"Не удалось подключиться к Ollama: {e}")
    
    def warm_up(self) -> bool:
        """Прогрев модели (загрузка в память)"""
        if self.client is None:
            self.initialize()

        try:
            logger.info(f"🔥 Прогрев модели {self.model}...")
            self.client.chat(
                model=self.model,
                messages=[{'role': 'user', 'content': 'Hello'}],
                options={
                    'num_predict': 10,
                    'num_thread': self.num_threads if self.num_threads else 8,
                    'num_ctx': 512,
                }
            )
            logger.info("✅ Модель готова к работе")
            return True
        except Exception as e:
            logger.warning(f"⚠️  Прогрев не удался: {e}")
            return False
    
    def analyze(
        self,
        caption: str,
        transcript: str,
        comments: List[str],
        author: str,
        known_tags: str
    ) -> Optional[Dict]:
        """
        Анализ контента через LLM
        
        Args:
            caption: Текст поста
            transcript: Транскрипт с таймкодами
            comments: Список комментариев
            author: Автор поста
            known_tags: Строка с известными тегами
            
        Returns:
            Словарь с результатами анализа
        """
        if self.client is None:
            self.initialize()

        user_prompt = self._build_prompt(caption, transcript, comments, author)
        system_prompt = self.SYSTEM_PROMPT.replace("{known_tags}", known_tags)

        logger.info("🧠 Анализ контента через LLM...")

        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                format='json',
                options={
                    'temperature': 0.7,
                    'num_predict': 500,
                    'num_thread': self.num_threads if self.num_threads else 8,
                    'num_ctx': self.num_ctx if self.num_ctx else 8192
                }
            )

            logger.info("✅ Анализ завершён")

            result_text = response['message']['content']
            return json.loads(result_text)

        except TimeoutError as e:
            logger.error(f"⏱️  Timeout при запросе к LLM: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON от LLM: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка LLM: {e}")
            return None
    
    def _build_prompt(
        self,
        caption: str,
        transcript: str,
        comments: List[str],
        author: str
    ) -> str:
        """Сборка промпта для LLM"""
        
        parts = [
            f"**Author:** {author}\n",
            f"**Post Caption:**\n{caption}\n" if caption else "",
            f"**Transcript:**\n{transcript}\n" if transcript else "",
        ]
        
        if comments:
            comments_text = "\n".join(f"- {c}" for c in comments[:50])  # Лимит 50
            parts.append(f"**Comments:**\n{comments_text}\n")
        
        return "\n".join(filter(None, parts))
