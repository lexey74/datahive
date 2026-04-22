"""
BM25 индекс для keyword search.

Простая реализация без внешних зависимостей.
Используется как дополнительный сигнал в гибридном поиске RAGEngine.
"""

from __future__ import annotations

import json
import math
import re
import logging
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Паттерн для удаления пунктуации
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def _tokenize(text: str) -> List[str]:
    """Простая токенизация: lowercase + удаление пунктуации + split."""
    text = _PUNCT_RE.sub(" ", text.lower())
    return [t for t in text.split() if len(t) > 1]


class BM25Index:
    """Простой BM25 индекс для keyword search."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b

        # Данные индекса
        self._doc_ids: List[str] = []
        self._doc_lengths: List[int] = []
        self._total_dl: int = 0
        self._avg_dl: float = 0.0
        # inverted index: token -> {doc_index -> term_frequency}
        self._inverted: Dict[str, Dict[int, int]] = {}
        # общее кол-во документов
        self._n_docs: int = 0
        # Множество известных doc_id для дедупликации при re-index
        self._known_ids: set[str] = set()

    def add_documents(self, doc_ids: List[str], texts: List[str]) -> None:
        """Токенизация + построение inverted index.

        Деду��ликация: если doc_id уже в индексе, пропускаем (ChromaDB делает upsert,
        BM25 — skip, чтобы не накапливать дубликаты).
        """
        for doc_id, text in zip(doc_ids, texts):
            # Дедупликация при повторном index_folder
            if doc_id in self._known_ids:
                continue
            self._known_ids.add(doc_id)

            idx = self._n_docs
            self._doc_ids.append(doc_id)

            tokens = _tokenize(text)
            self._doc_lengths.append(len(tokens))
            self._total_dl += len(tokens)
            self._n_docs += 1

            # Подсчёт частот токенов
            tf: Dict[str, int] = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1

            for token, freq in tf.items():
                if token not in self._inverted:
                    self._inverted[token] = {}
                self._inverted[token][idx] = freq

        # Пересчёт средней длины документа
        if self._n_docs > 0:
            self._avg_dl = self._total_dl / self._n_docs

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Вернуть top_k (doc_id, score) пар."""
        if self._n_docs == 0:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores: Dict[int, float] = {}

        for token in query_tokens:
            if token not in self._inverted:
                continue

            postings = self._inverted[token]
            # IDF: log((N - df + 0.5) / (df + 0.5) + 1)
            df = len(postings)
            idf = math.log((self._n_docs - df + 0.5) / (df + 0.5) + 1.0)

            for doc_idx, tf in postings.items():
                dl = self._doc_lengths[doc_idx]
                # BM25 TF-компонент
                tf_norm = (tf * (self.k1 + 1)) / (
                    tf + self.k1 * (1 - self.b + self.b * dl / self._avg_dl)
                )
                score = idf * tf_norm
                scores[doc_idx] = scores.get(doc_idx, 0.0) + score

        # Сортировка по убыванию score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [(self._doc_ids[idx], score) for idx, score in ranked]

    def save(self, path: Path) -> None:
        """Сохр��нить индекс в JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "doc_ids": self._doc_ids,
            "doc_lengths": self._doc_lengths,
            "inverted": {
                token: {str(k): v for k, v in postings.items()}
                for token, postings in self._inverted.items()
            },
            "n_docs": self._n_docs,
            "k1": self.k1,
            "b": self.b,
        }
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        logger.debug("BM25 индекс сохранён: %s (%d документов)", path, self._n_docs)

    def load(self, path: Path) -> None:
        """Загрузить индекс из JSON."""
        path = Path(path)
        if not path.exists():
            logger.debug("BM25 индекс не найден: %s", path)
            return

        data = json.loads(path.read_text(encoding="utf-8"))
        self._doc_ids = data["doc_ids"]
        self._doc_lengths = data["doc_lengths"]
        self._inverted = {
            token: {int(k): v for k, v in postings.items()}
            for token, postings in data["inverted"].items()
        }
        self._n_docs = data["n_docs"]
        self.k1 = data.get("k1", 1.5)
        self.b = data.get("b", 0.75)

        # Восстановить _known_ids и _total_dl
        self._known_ids = set(self._doc_ids)
        self._total_dl = sum(self._doc_lengths)
        if self._n_docs > 0:
            self._avg_dl = self._total_dl / self._n_docs

        logger.debug("BM25 индекс загружен: %s (%d документов)", path, self._n_docs)
