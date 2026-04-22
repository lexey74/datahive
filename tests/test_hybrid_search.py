"""
Тесты гибридного поиска: BM25 + semantic + graph.
"""

import json
import sys
import types

import pytest

from src.modules.bm25 import BM25Index, _tokenize


# ── BM25 тесты ──────────────────────────────────────────────────────────────


class TestBM25Index:
    """Тесты BM25 индекса."""

    def test_tokenize_basic(self):
        tokens = _tokenize("Hello, World! This is a test.")
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens
        # Пунктуация удалена, однобуквенные отброшены
        assert "," not in tokens
        assert "!" not in tokens
        assert "a" not in tokens

    def test_add_and_search(self):
        idx = BM25Index()
        idx.add_documents(
            ["doc1", "doc2", "doc3"],
            [
                "python programming language guide",
                "javascript web development tutorial",
                "python machine learning deep learning",
            ],
        )

        results = idx.search("python programming", top_k=2)
        assert len(results) > 0
        # doc1 содержит оба слова — должен быть первым
        assert results[0][0] == "doc1"
        # doc3 содержит python — должен быть вторым
        assert results[1][0] == "doc3"

    def test_search_empty_index(self):
        idx = BM25Index()
        results = idx.search("anything", top_k=5)
        assert results == []

    def test_search_no_match(self):
        idx = BM25Index()
        idx.add_documents(["doc1"], ["python programming"])
        results = idx.search("basketball", top_k=5)
        assert results == []

    def test_search_empty_query(self):
        idx = BM25Index()
        idx.add_documents(["doc1"], ["python programming"])
        results = idx.search("", top_k=5)
        assert results == []

    def test_top_k_limit(self):
        idx = BM25Index()
        idx.add_documents(
            [f"doc{i}" for i in range(10)],
            [f"document about topic number {i}" for i in range(10)],
        )
        results = idx.search("document topic", top_k=3)
        assert len(results) <= 3

    def test_save_and_load(self, tmp_path):
        idx = BM25Index()
        idx.add_documents(
            ["doc1", "doc2"],
            ["python programming language", "javascript web framework"],
        )

        save_path = tmp_path / "bm25_index.json"
        idx.save(save_path)
        assert save_path.exists()

        # Загружаем в новый индекс
        idx2 = BM25Index()
        idx2.load(save_path)

        # Результаты поиска должны совпадать
        r1 = idx.search("python", top_k=2)
        r2 = idx2.search("python", top_k=2)
        assert len(r1) == len(r2)
        assert r1[0][0] == r2[0][0]

    def test_load_nonexistent(self, tmp_path):
        """Загрузка несуществующего файла — без ошибок."""
        idx = BM25Index()
        idx.load(tmp_path / "nonexistent.json")
        assert idx._n_docs == 0

    def test_incremental_add(self):
        """Добавление документов порциями."""
        idx = BM25Index()
        idx.add_documents(["doc1"], ["python programming"])
        idx.add_documents(["doc2"], ["python machine learning"])

        results = idx.search("python", top_k=5)
        assert len(results) == 2


# ── Нормализация scores ──────────────────────────────────────────────────────


class TestNormalizeScores:
    """Тесты нормализации scores."""

    def test_normalize_basic(self):
        from src.modules.module4_rag import _normalize_scores

        scores = [("a", 1.0), ("b", 5.0), ("c", 3.0)]
        norm = _normalize_scores(scores)
        assert norm["a"] == 0.0  # минимум
        assert norm["b"] == 1.0  # максимум
        assert 0.0 < norm["c"] < 1.0

    def test_normalize_empty(self):
        from src.modules.module4_rag import _normalize_scores

        assert _normalize_scores([]) == {}

    def test_normalize_single(self):
        from src.modules.module4_rag import _normalize_scores

        norm = _normalize_scores([("a", 5.0)])
        assert norm["a"] == 1.0

    def test_normalize_equal_scores(self):
        from src.modules.module4_rag import _normalize_scores

        norm = _normalize_scores([("a", 3.0), ("b", 3.0)])
        assert norm["a"] == 1.0
        assert norm["b"] == 1.0


# ── Хелпер: фейковое окружение для RAGEngine ────────────────────────────────


def _make_fake_env(monkeypatch):
    """Мокаем chromadb, sentence-transformers, langchain, LocalBrain."""

    # fake sentence_transformers
    class FakeEmbedder:
        def __init__(self, model_name):
            self.model_name = model_name

        def encode(self, texts, show_progress_bar=False):
            return [[0.1] * 8 for _ in texts]

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=FakeEmbedder),
    )

    # fake text splitter
    class FakeSplitter:
        def __init__(self, chunk_size=1000, chunk_overlap=150):
            self.chunk_size = chunk_size

        def split_text(self, text):
            chunks = []
            i = 0
            while i < len(text):
                chunks.append(text[i : i + self.chunk_size])
                i += self.chunk_size
            return chunks if chunks else [text]

    monkeypatch.setitem(
        sys.modules,
        "langchain_text_splitters",
        types.SimpleNamespace(RecursiveCharacterTextSplitter=FakeSplitter),
    )

    # fake chromadb
    class FakeCollection:
        def __init__(self):
            self.docs = []
            self.metadatas = []
            self.ids = []
            self.embeddings = []

        def upsert(self, ids, documents, metadatas, embeddings=None):
            self.ids.extend(ids)
            self.docs.extend(documents)
            self.metadatas.extend(metadatas)
            if embeddings is not None:
                self.embeddings.extend(embeddings)

        def add(self, ids, documents, metadatas, embeddings=None):
            self.upsert(ids, documents, metadatas, embeddings)

        def query(self, query_embeddings=None, n_results=5, include=None, query_texts=None, **kw):
            docs = self.docs[:n_results]
            metas = self.metadatas[:n_results]
            ids = self.ids[:n_results]
            distances = [0.5] * len(docs)  # фейковые расстояния
            return {
                "documents": [docs],
                "metadatas": [metas],
                "ids": [ids],
                "distances": [distances],
            }

        def get(self, ids=None, include=None):
            result_ids = []
            result_docs = []
            result_metas = []
            for doc_id in (ids or []):
                if doc_id in self.ids:
                    i = self.ids.index(doc_id)
                    result_ids.append(doc_id)
                    result_docs.append(self.docs[i])
                    result_metas.append(self.metadatas[i])
            return {"ids": result_ids, "documents": result_docs, "metadatas": result_metas}

    class FakeClient:
        def __init__(self, path=None):
            self._col = FakeCollection()

        def get_or_create_collection(self, name="datahive"):
            return self._col

    monkeypatch.setitem(
        sys.modules, "chromadb", types.SimpleNamespace(PersistentClient=FakeClient)
    )

    # fake LocalBrain
    fake_localbrain_mod = types.ModuleType("src.modules.local_brain")

    class FakeClientInner:
        def chat(self, model=None, messages=None, options=None):
            return {"message": {"content": "Ответ (фейковый)"}}

    class FakeLocalBrain:
        def __init__(self):
            self.model = "fake-model"
            self.client = FakeClientInner()

        def initialize(self):
            return None

    fake_localbrain_mod.LocalBrain = FakeLocalBrain
    monkeypatch.setitem(sys.modules, "src.modules.local_brain", fake_localbrain_mod)


# ── Тесты RAGEngine с гибридным поиском ─────────────────────────────────────


class TestHybridQuery:
    """Тесты гибридного поиска RAGEngine."""

    def _create_rag_with_data(self, monkeypatch, tmp_path):
        """Создаёт RAGEngine с проиндексированными данными."""
        _make_fake_env(monkeypatch)

        user_root = tmp_path / "user_123"
        user_root.mkdir()
        folder = user_root / "2026-01-15_python_tutorial"
        folder.mkdir()

        content = "Python — это язык программирования. Используется для машинного обучения и веб-разработки."
        (folder / "Knowledge.md").write_text(content, encoding="utf-8")

        from src.modules.module4_rag import RAGEngine

        rag = RAGEngine(user_root=user_root)
        rag.index_folder(folder)
        return rag

    def test_query_returns_expected_keys(self, monkeypatch, tmp_path):
        """query() возвращает dict с ключами answer, sources, chunks."""
        rag = self._create_rag_with_data(monkeypatch, tmp_path)

        result = rag.query("что такое Python?")
        assert isinstance(result, dict)
        assert "answer" in result
        assert "sources" in result
        assert "chunks" in result

    def test_hybrid_query_returns_expected_keys(self, monkeypatch, tmp_path):
        """hybrid_query() возвращает тот же формат."""
        rag = self._create_rag_with_data(monkeypatch, tmp_path)

        result = rag.hybrid_query("что такое Python?")
        assert isinstance(result, dict)
        assert "answer" in result
        assert "sources" in result
        assert "chunks" in result

    def test_bm25_indexed_during_index_folder(self, monkeypatch, tmp_path):
        """BM25 индекс создаётся при индексации."""
        rag = self._create_rag_with_data(monkeypatch, tmp_path)

        # BM25 должен быть инициализирован и содержать документы
        assert rag._bm25 is not None
        assert rag._bm25._n_docs > 0

        # Файл BM25 должен быть сохранён
        bm25_path = rag.user_root / "vector_db" / "bm25_index.json"
        assert bm25_path.exists()

    def test_query_without_graph_json(self, monkeypatch, tmp_path):
        """Поиск работает без graph.json (graceful fallback)."""
        rag = self._create_rag_with_data(monkeypatch, tmp_path)

        # graph.json не существует — не должно быть ошибки
        result = rag.query("Python машинное обучение")
        assert isinstance(result, dict)
        assert "answer" in result
        assert len(result["chunks"]) > 0

    def test_graph_expand_with_graph(self, monkeypatch, tmp_path):
        """Graph expansion возвращает связанные folders."""
        rag = self._create_rag_with_data(monkeypatch, tmp_path)

        # Создаём graph.json
        wiki_dir = rag.user_root / "wiki"
        wiki_dir.mkdir()
        # Формат GraphManager: nodes с article:/concept: префиксами, edges массив
        graph = {
            "nodes": {
                "article:2026-01-15_python_tutorial": {"type": "article", "title": "Python Tutorial", "created": "2026-01-15"},
                "article:2026-01-20_ml_basics": {"type": "article", "title": "ML Basics", "created": "2026-01-20"},
                "concept:python": {"type": "concept", "term": "Python", "mentions": 1},
                "concept:machine_learning": {"type": "concept", "term": "Machine Learning", "mentions": 2},
                "concept:neural_networks": {"type": "concept", "term": "Neural Networks", "mentions": 1},
            },
            "edges": [
                {"from": "article:2026-01-15_python_tutorial", "to": "concept:python", "type": "discusses", "created": "2026-01-15"},
                {"from": "article:2026-01-15_python_tutorial", "to": "concept:machine_learning", "type": "discusses", "created": "2026-01-15"},
                {"from": "article:2026-01-20_ml_basics", "to": "concept:machine_learning", "type": "discusses", "created": "2026-01-20"},
                {"from": "article:2026-01-20_ml_basics", "to": "concept:neural_networks", "type": "discusses", "created": "2026-01-20"},
            ],
        }
        (wiki_dir / "graph.json").write_text(json.dumps(graph), encoding="utf-8")

        expanded = rag._graph_expand(["2026-01-15_python_tutorial"])
        assert "2026-01-20_ml_basics" in expanded

    def test_graph_expand_without_graph(self, monkeypatch, tmp_path):
        """Graph expansion без graph.json возвращает пустой список."""
        rag = self._create_rag_with_data(monkeypatch, tmp_path)
        expanded = rag._graph_expand(["some_folder"])
        assert expanded == []

    def test_graph_expand_max_extra(self, monkeypatch, tmp_path):
        """Graph expansion уважает лимит max_extra."""
        rag = self._create_rag_with_data(monkeypatch, tmp_path)

        wiki_dir = rag.user_root / "wiki"
        wiki_dir.mkdir()
        # Формат GraphManager
        graph = {
            "nodes": {
                "article:folder_a": {"type": "article", "title": "A", "created": "2026-01-01"},
                "article:folder_b": {"type": "article", "title": "B", "created": "2026-01-01"},
                "article:folder_c": {"type": "article", "title": "C", "created": "2026-01-01"},
                "article:folder_d": {"type": "article", "title": "D", "created": "2026-01-01"},
                "article:folder_e": {"type": "article", "title": "E", "created": "2026-01-01"},
                "concept:topic": {"type": "concept", "term": "topic", "mentions": 5},
            },
            "edges": [
                {"from": "article:folder_a", "to": "concept:topic", "type": "discusses", "created": "2026-01-01"},
                {"from": "article:folder_b", "to": "concept:topic", "type": "discusses", "created": "2026-01-01"},
                {"from": "article:folder_c", "to": "concept:topic", "type": "discusses", "created": "2026-01-01"},
                {"from": "article:folder_d", "to": "concept:topic", "type": "discusses", "created": "2026-01-01"},
                {"from": "article:folder_e", "to": "concept:topic", "type": "discusses", "created": "2026-01-01"},
            ],
        }
        (wiki_dir / "graph.json").write_text(json.dumps(graph), encoding="utf-8")

        expanded = rag._graph_expand(["folder_a"], max_extra=2)
        assert len(expanded) <= 2

    def test_backward_compatible_query_api(self, monkeypatch, tmp_path):
        """Старый API query() по-прежнему работает и возвращает тот же формат."""
        rag = self._create_rag_with_data(monkeypatch, tmp_path)

        result = rag.query("тестовый вопрос")
        assert set(result.keys()) == {"answer", "sources", "chunks"}
        assert isinstance(result["answer"], str)
        assert isinstance(result["sources"], list)
        assert isinstance(result["chunks"], list)

    def test_multiple_folders_indexed(self, monkeypatch, tmp_path):
        """Индексация нескольких папок — BM25 и semantic работают вместе."""
        _make_fake_env(monkeypatch)

        user_root = tmp_path / "user_456"
        user_root.mkdir()

        # Первая папка — про Python
        folder1 = user_root / "2026-01-10_python_basics"
        folder1.mkdir()
        (folder1 / "Knowledge.md").write_text(
            "Python основы программирования переменные циклы функции", encoding="utf-8"
        )

        # Вторая папка — про JavaScript
        folder2 = user_root / "2026-01-11_javascript_web"
        folder2.mkdir()
        (folder2 / "Knowledge.md").write_text(
            "JavaScript фреймворки React Angular Vue веб-разработка", encoding="utf-8"
        )

        from src.modules.module4_rag import RAGEngine

        rag = RAGEngine(user_root=user_root)
        rag.index_folder(folder1)
        rag.index_folder(folder2)

        # BM25 должен содержать документы из обеих папок
        assert rag._bm25 is not None
        assert rag._bm25._n_docs >= 2

        # Поиск должен работать
        result = rag.query("Python переменные")
        assert isinstance(result, dict)
        assert "answer" in result
