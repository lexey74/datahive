"""
Module 4 - RAG / Oracle

Provides RAGEngine for indexing folders into a per-user ChromaDB and
running semantic search + answer generation via LocalBrain.

Гибридный поиск: Semantic (ChromaDB) + BM25 (keyword) + Graph traversal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Dict, Optional, Tuple
import os
import json
import hashlib
import logging

from src.modules.bm25 import BM25Index

logger = logging.getLogger(__name__)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_scores(scores: List[Tuple[str, float]]) -> Dict[str, float]:
    """Нормализация scores в диапазон [0, 1]."""
    if not scores:
        return {}
    max_score = max(s for _, s in scores)
    min_score = min(s for _, s in scores)
    rng = max_score - min_score
    if rng == 0:
        # Все scores одинаковые — ставим 1.0
        return {doc_id: 1.0 for doc_id, _ in scores}
    return {doc_id: (s - min_score) / rng for doc_id, s in scores}


class RAGEngine:
    """A small RAG engine using chromadb + sentence-transformers.

    Гибридный поиск: semantic + BM25 + graph expansion.

    Usage:
        rag = RAGEngine(user_root_path)
        rag.index_folder(folder_path)
        answer = rag.query(question)
    """

    def __init__(self, user_root: Optional[Path] = None) -> None:
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
            from langchain_text_splitters import RecursiveCharacterTextSplitter
        except Exception as e:  # pragma: no cover - import-time check
            raise ImportError(
                "RAG dependencies not available. Install chromadb, sentence-transformers and langchain-text-splitters"
            ) from e

        self.chromadb = chromadb
        self.EmbedModel = SentenceTransformer
        self.TextSplitter = RecursiveCharacterTextSplitter

        self.embedding_model_name = os.getenv("RAG_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.top_k = int(os.getenv("RAG_SEARCH_TOP_K", "5"))

        # user_root is the downloads/{userfolder}
        self.user_root = Path(user_root) if user_root else None

        # client will be lazily created
        self._client: Optional[Any] = None
        self._collection: Optional[Any] = None
        self._embedder: Optional[Any] = None

        # BM25 индекс — ленивая инициализация
        self._bm25: Optional[BM25Index] = None

        # Кэш графа
        self._graph_cache: Optional[Dict] = None

        # Веса гибридного скоринга
        self._weight_semantic: float = 0.4
        self._weight_bm25: float = 0.4
        self._weight_graph: float = 0.2

    def _init_client(self) -> None:
        if self._client is None:
            # ensure user_root exists
            if not self.user_root:
                raise ValueError("user_root must be provided to initialize RAGEngine")

            vector_path = self.user_root / "vector_db"
            vector_path.mkdir(parents=True, exist_ok=True)

            # Persistent client pointing to per-user folder
            self._client = self.chromadb.PersistentClient(path=str(vector_path))
            # single collection for all user docs
            self._collection = self._client.get_or_create_collection(name="datahive")

        if self._embedder is None:
            # load sentence-transformers model (CPU)
            self._embedder = self.EmbedModel(self.embedding_model_name)

    def _init_bm25(self) -> BM25Index:
        """Инициализация BM25 индекса с загрузкой из файла."""
        if self._bm25 is None:
            self._bm25 = BM25Index()
            if self.user_root:
                bm25_path = self.user_root / "vector_db" / "bm25_index.json"
                self._bm25.load(bm25_path)
        return self._bm25

    def _save_bm25(self) -> None:
        """Сохранить BM25 индекс на диск."""
        if self._bm25 is not None and self.user_root:
            bm25_path = self.user_root / "vector_db" / "bm25_index.json"
            self._bm25.save(bm25_path)

    def _load_graph(self) -> Optional[Dict]:
        """Загрузить graph.json для graph-based retrieval.

        Совместим с форматом GraphManager:
        {
            "nodes": { "article:folder_name": {...}, "concept:slug": {...} },
            "edges": [ {"from": "article:...", "to": "concept:...", "type": "discusses"} ]
        }

        Если файл не найден — возвращает None (graceful fallback).
        """
        # Возвращаем кэш если есть
        if self._graph_cache is not None:
            return self._graph_cache

        if not self.user_root:
            return None

        # Поиск graph.json
        candidates = [
            self.user_root / "wiki" / "graph.json",
            self.user_root.parent / "wiki" / "graph.json",
        ]
        for path in candidates:
            if path.exists():
                try:
                    self._graph_cache = json.loads(path.read_text(encoding="utf-8"))
                    return self._graph_cache
                except Exception as e:
                    logger.warning("Ошибка загрузки graph.json (%s): %s", path, e)
                    return None
        return None

    def _graph_expand(self, folder_names: List[str], max_extra: int = 3) -> List[str]:
        """Расширить результаты поиска через граф связей.

        Совместим с форматом GraphManager (nodes/edges).
        Для каждого folder_name находит связанные concepts через edges,
        затем для каждого concept — другие articles.
        """
        graph = self._load_graph()
        if not graph:
            return []

        edges = graph.get("edges", [])
        if not edges:
            return []

        # Собираем все concepts, связанные с найденными folders
        related_concepts: set[str] = set()
        for fn in folder_names:
            article_id = f"article:{fn}"
            for edge in edges:
                if edge.get("from") == article_id and edge.get("to", "").startswith("concept:"):
                    related_concepts.add(edge["to"])
                elif edge.get("to") == article_id and edge.get("from", "").startswith("concept:"):
                    related_concepts.add(edge["from"])

        # Для каждого concept — находим связанные articles (кроме уже известных)
        existing = set(folder_names)
        extra_folders: List[str] = []
        for concept_id in related_concepts:
            for edge in edges:
                folder = None
                if edge.get("from") == concept_id and edge.get("to", "").startswith("article:"):
                    folder = edge["to"].removeprefix("article:")
                elif edge.get("to") == concept_id and edge.get("from", "").startswith("article:"):
                    folder = edge["from"].removeprefix("article:")

                if folder and folder not in existing and folder not in extra_folders:
                    extra_folders.append(folder)
                    if len(extra_folders) >= max_extra:
                        return extra_folders

        return extra_folders

    def index_folder(self, folder: Path) -> int:
        """Index files from a folder into the user's ChromaDB and BM25.

        Returns number of chunks indexed (added or upserted).
        """
        folder = Path(folder)
        # discover user_root if not provided: look for ancestor named like 'digits_'
        if self.user_root is None:
            for p in folder.parents:
                # New structure: users/{username}/downloads/
                if p.name == "downloads":
                    try:
                        if p.parent.parent.name == "users":
                            self.user_root = p
                            break
                    except Exception:
                        pass

                # Compatibility logic
                if p.name and (p.parent.name == "downloads" or "_" in p.name):
                    self.user_root = p
                    break
            if self.user_root is None:
                # fallback to folder.parent
                self.user_root = folder.parent

        self._init_client()

        texts: List[str] = []
        metadatas: List[Dict] = []
        ids: List[str] = []

        # Prioritise files: Knowledge.md, description.md, transcript.md
        priority_files = ["Knowledge.md", "description.md", "transcript.md"]

        for fname in priority_files:
            fpath = folder / fname
            if fpath.exists() and fpath.is_file():
                content = fpath.read_text(encoding="utf-8")
                source_type = "unknown"
                if fname == "Knowledge.md":
                    source_type = "summary"
                elif fname == "description.md":
                    source_type = "description"
                elif fname == "transcript.md":
                    source_type = "transcript"

                # Split into chunks
                splitter = self.TextSplitter(chunk_size=1000, chunk_overlap=150)
                chunks = splitter.split_text(content)
                for idx, chunk in enumerate(chunks):
                    chunk_id = _hash_text(f"{fname}:{idx}:{chunk[:64]}")
                    texts.append(chunk)
                    metadatas.append(
                        {
                            "folder_name": folder.name,
                            "file_path": str(fpath),
                            "source_type": source_type,
                        }
                    )
                    ids.append(chunk_id)

        if not texts:
            return 0

        # compute embeddings
        self._init_client()
        if self._embedder is None or self._collection is None:
            raise RuntimeError("RAG engine не инициализирован")
        embeddings = self._embedder.encode(texts, show_progress_bar=False)

        # Upsert into ChromaDB
        try:
            if hasattr(self._collection, "upsert"):
                self._collection.upsert(
                    ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings
                )
            else:
                self._collection.add(
                    ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings
                )
        except Exception:
            self._collection.add(
                ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings
            )

        # Индексация в BM25
        try:
            bm25 = self._init_bm25()
            bm25.add_documents(ids, texts)
            self._save_bm25()
        except Exception as e:
            logger.warning("Ошибка индексации BM25: %s", e)

        # Инвалидировать кэш графа (мог измениться при ingest)
        self._graph_cache = None

        return len(texts)

    def _semantic_search(self, question: str) -> Tuple[List[str], List[str], List[Dict], List[float]]:
        """Семантический поиск через ChromaDB.

        Returns:
            (doc_ids, texts, metadatas, distances)
        """
        self._init_client()
        if self._embedder is None or self._collection is None:
            raise RuntimeError("RAG engine не инициализирован")

        q_emb = self._embedder.encode([question])[0]

        try:
            results = self._collection.query(
                query_embeddings=[q_emb],
                n_results=self.top_k,
                include=["documents", "metadatas", "distances"],
            )
        except TypeError:
            results = self._collection.query(
                query_texts=[question],
                n_results=self.top_k,
                include=["documents", "metadatas", "distances"],
            )

        docs: List[str] = []
        metadatas: List[Dict] = []
        distances: List[float] = []
        ids: List[str] = []

        try:
            docs = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results.get("distances", [[]])[0]
            ids = results.get("ids", [[]])[0]
        except Exception:
            docs = results.get("documents", [])
            metadatas = results.get("metadatas", [])
            distances = results.get("distances", [])
            ids = results.get("ids", [])

        return ids, docs, metadatas, distances

    def _bm25_search(self, question: str) -> List[Tuple[str, float]]:
        """BM25 keyword search.

        Returns:
            Список (doc_id, score) пар.
        """
        try:
            bm25 = self._init_bm25()
            return bm25.search(question, top_k=self.top_k)
        except Exception as e:
            logger.warning("BM25 search fallback: %s", e)
            return []

    def hybrid_query(self, question: str) -> Dict:
        """Гибридный поиск: semantic + BM25 + graph.

        Returns:
            {'answer': str, 'sources': [folder_names], 'chunks': [texts]}
        """
        if self.user_root is None:
            raise ValueError("user_root must be set for query()")

        # 1. Semantic search
        sem_ids, sem_docs, sem_metas, sem_distances = self._semantic_search(question)

        # Создаём маппинг doc_id -> (text, metadata) для быстрого доступа
        doc_map: Dict[str, Tuple[str, Dict]] = {}
        for doc_id, text, meta in zip(sem_ids, sem_docs, sem_metas):
            doc_map[doc_id] = (text, meta)

        # Semantic scores: ChromaDB distances — чем меньше, тем лучше.
        # Конвертируем в similarity: score = 1 / (1 + distance)
        sem_scores: List[Tuple[str, float]] = []
        for doc_id, dist in zip(sem_ids, sem_distances):
            similarity = 1.0 / (1.0 + dist) if dist >= 0 else 1.0
            sem_scores.append((doc_id, similarity))

        # 2. BM25 search
        bm25_scores = self._bm25_search(question)

        # Добавляем BM25 результаты в doc_map (если их там нет — подтянем из ChromaDB)
        bm25_doc_ids_to_fetch = [
            doc_id for doc_id, _ in bm25_scores if doc_id not in doc_map
        ]
        if bm25_doc_ids_to_fetch and self._collection is not None:
            try:
                extra = self._collection.get(
                    ids=bm25_doc_ids_to_fetch,
                    include=["documents", "metadatas"],
                )
                for i, doc_id in enumerate(extra.get("ids", [])):
                    text = extra["documents"][i] if extra.get("documents") else ""
                    meta = extra["metadatas"][i] if extra.get("metadatas") else {}
                    doc_map[doc_id] = (text, meta)
            except Exception as e:
                logger.warning("Не удалось получить BM25-документы из ChromaDB: %s", e)

        # 3. Нормализация scores
        norm_sem = _normalize_scores(sem_scores)
        norm_bm25 = _normalize_scores(bm25_scores)

        # 4. Собираем уникальные folder_names из top результатов
        top_folders: List[str] = []
        for doc_id in list(norm_sem.keys()) + [d for d, _ in bm25_scores]:
            if doc_id in doc_map:
                fn = doc_map[doc_id][1].get("folder_name", "")
                if fn and fn not in top_folders:
                    top_folders.append(fn)

        # 5. Graph expansion
        graph_expanded = self._graph_expand(top_folders)
        graph_folder_set = set(graph_expanded)

        # 6. Объединённый scoring
        all_doc_ids = set(norm_sem.keys()) | set(norm_bm25.keys())
        final_scores: Dict[str, float] = {}

        for doc_id in all_doc_ids:
            s_sem = norm_sem.get(doc_id, 0.0)
            s_bm25 = norm_bm25.get(doc_id, 0.0)

            # Graph boost: если folder связан через граф с другими top результатами
            graph_boost = 0.0
            if doc_id in doc_map:
                fn = doc_map[doc_id][1].get("folder_name", "")
                if fn in graph_folder_set:
                    graph_boost = 1.0

            final_scores[doc_id] = (
                self._weight_semantic * s_sem
                + self._weight_bm25 * s_bm25
                + self._weight_graph * graph_boost
            )

        # 7. Re-rank
        ranked = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)

        # Собираем chunks и folders для ответа
        chunks: List[str] = []
        folders: List[str] = []
        for doc_id, _ in ranked[: self.top_k]:
            if doc_id in doc_map:
                text, meta = doc_map[doc_id]
                chunks.append(text)
                fn = meta.get("folder_name", "")
                if fn and fn not in folders:
                    folders.append(fn)

        # Добавляем graph-expanded folders в sources (только если есть matching chunks)
        for fn in graph_expanded:
            if fn not in folders:
                folders.append(fn)

        # 8. Генерация ответа через LLM
        answer = self._generate_answer(question, chunks)

        return {
            "answer": answer,
            "sources": folders,
            "chunks": chunks,
        }

    def _generate_answer(self, question: str, chunks: List[str]) -> str:
        """Генерация ответа через LocalBrain на основе контекста."""
        try:
            from src.modules.local_brain import LocalBrain

            lb = LocalBrain()
            system = """
Ты — умный помощник. Отвечай на вопрос ТОЛЬКО на основе приведенного ниже контекста.
Если в контексте нет ответа, скажи "Я не нашел информации в вашей базе".
Не выдумывай факты.
"""
            context_text = "\n\n".join(chunks[: self.top_k])
            user_prompt = f"КОНТЕКСТ:\n{context_text}\n\nВОПРОС: {question}"

            lb.initialize()
            if lb.client is None:
                raise RuntimeError("LLM клиент не инициализирован")
            response = lb.client.chat(
                model=lb.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
                options={"temperature": 0.0},
            )
            return response["message"]["content"]
        except Exception as e:
            return f"Ошибка при генерации ответа: {e}"

    def query(self, question: str) -> Dict:
        """Run hybrid search and generate an answer using LocalBrain.

        Обратно-совместимый API: возвращает {'answer': str, 'sources': [folder_names], 'chunks': [texts]}.
        Внутри использует hybrid_query (semantic + BM25 + graph).
        """
        return self.hybrid_query(question)
