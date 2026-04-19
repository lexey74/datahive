"""
LocalBrain - Анализ контента через локальную LLM (llama.cpp server)
"""

import json
import logging
from typing import Dict, List, Optional
from urllib import error as url_error
from urllib import request as url_request

logger = logging.getLogger(__name__)


class LlamaCppClient:
    """Минимальный OpenAI-совместимый клиент для llama.cpp server."""

    def __init__(self, host: str, timeout: int = 180) -> None:
        self.host = host.rstrip("/")
        self.timeout = timeout

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        options: Optional[Dict] = None,
        format: Optional[str] = None,
        think: Optional[bool] = None,
    ) -> Dict:
        del think  # совместимость с вызовами в проекте

        payload: Dict = {
            "model": model,
            "messages": messages,
        }

        options = options or {}
        if "temperature" in options:
            payload["temperature"] = options["temperature"]
        if "num_predict" in options:
            payload["max_tokens"] = options["num_predict"]
        if "top_p" in options:
            payload["top_p"] = options["top_p"]

        if format == "json":
            payload["response_format"] = {"type": "json_object"}

        body = json.dumps(payload).encode("utf-8")
        endpoint = self._build_chat_endpoint()
        req = url_request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with url_request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except url_error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="ignore")
            raise ConnectionError(f"HTTP {e.code} llama.cpp: {raw}") from e
        except url_error.URLError as e:
            raise ConnectionError(f"llama.cpp недоступен: {e}") from e

        content = ""
        try:
            content = data["choices"][0]["message"]["content"]
        except Exception as e:
            raise ValueError(f"Некорректный ответ llama.cpp: {data}") from e

        return {"message": {"content": content}}

    def ping(self) -> None:
        """Проверка доступности llama.cpp сервера."""
        endpoints = (
            f"{self.host}/health",
            f"{self.host}/v1/models",
        )
        last_error: Optional[Exception] = None

        for endpoint in endpoints:
            req = url_request.Request(endpoint, method="GET")
            try:
                with url_request.urlopen(req, timeout=5):
                    return
            except (
                Exception
            ) as e:  # pragma: no cover - только для диагностики окружения
                last_error = e

        raise ConnectionError(
            f"Не удалось подключиться к llama.cpp ({self.host}): {last_error}"
        )

    def _build_chat_endpoint(self) -> str:
        if self.host.endswith("/v1"):
            return f"{self.host}/chat/completions"
        return f"{self.host}/v1/chat/completions"


class LocalBrain:
    """Интеллектуальная обработка через llama.cpp"""

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

    def __init__(
        self, model: str = "llama3.2", base_url: str = "http://localhost:8080"
    ) -> None:
        """
        Инициализация LLM клиента

        Args:
            model: Название модели в llama.cpp server
            base_url: URL llama.cpp сервера
        """
        self.model = model
        self.base_url = base_url
        self.client: Optional[LlamaCppClient] = None
        self.num_threads = None
        self.num_ctx = None

    def initialize(self) -> None:
        """Инициализация клиента llama.cpp"""
        try:
            self.client = LlamaCppClient(host=self.base_url)
            self.client.ping()
            logger.info(f"✅ llama.cpp подключен: {self.model} @ {self.base_url}")
        except Exception as e:
            raise ConnectionError(f"Не удалось подключиться к llama.cpp: {e}")

    def warm_up(self) -> bool:
        """Прогрев модели (загрузка в память)"""
        if self.client is None:
            self.initialize()
        if self.client is None:
            return False

        try:
            logger.info(f"🔥 Прогрев модели {self.model}...")
            self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                options={
                    "num_predict": 10,
                    "num_thread": self.num_threads if self.num_threads else 8,
                    "num_ctx": 512,
                },
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
        known_tags: str,
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
        if self.client is None:
            logger.error("❌ LLM клиент не инициализирован")
            return None

        user_prompt = self._build_prompt(caption, transcript, comments, author)
        system_prompt = self.SYSTEM_PROMPT.replace("{known_tags}", known_tags)

        logger.info("🧠 Анализ контента через llama.cpp...")

        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                format="json",
                options={
                    "temperature": 0.7,
                    "num_predict": 500,
                    "num_thread": self.num_threads if self.num_threads else 8,
                    "num_ctx": self.num_ctx if self.num_ctx else 8192,
                },
            )

            logger.info("✅ Анализ завершён")

            result_text = response["message"]["content"]
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
        self, caption: str, transcript: str, comments: List[str], author: str
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
