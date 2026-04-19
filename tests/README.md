# Unit Tests

Pytest-based unit test suite for Data Hive modules.

## Test Results ✅

**Total: 23 unit tests** | **Status: All Passing**

- ✅ TagManager: 9 tests (86% coverage)
- ✅ LocalEars (Whisper): 4 tests (76% coverage)  
- ✅ LocalBrain (AI): 5 tests (28% coverage)
- ✅ HybridGrabber (Downloader): 5 tests (38% coverage)

## Structure

```
tests/
├── __init__.py              # Package initialization
├── conftest.py              # Pytest fixtures and shared mocks
├── test_tag_manager.py      # TagManager tests (9 tests)
├── test_local_ears.py       # LocalEars/Whisper tests (4 tests)
├── test_local_brain.py      # LocalBrain/AI tests (5 tests)
└── test_hybrid_grabber.py   # HybridGrabber/Downloaders tests (5 tests)
```

## Running Tests

### Install development dependencies:
```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### Run all tests:
```bash
make test
```

### Run lint:
```bash
make lint
```

### Format code:
```bash
make format
```

### Run specific test file:
```bash
venv/bin/python3 -m pytest tests/test_tag_manager.py
venv/bin/python3 -m pytest tests/test_local_ears.py -v
```

### Run with coverage:
```bash
venv/bin/python3 -m pytest --cov=src --cov-report=html tests/
```

### Run with verbose output:
```bash
venv/bin/python3 -m pytest -v tests/
```

### Run type checks (mypy):
```bash
make typecheck
```

### Run full local verification:
```bash
make check
```

Текущий охват: весь проект (`src`, `scripts`, `tests`) и legacy shim-модули совместимости.

## Test Coverage

- **TagManager** (9 tests, 86% coverage):
  - Initialization with new/existing files
  - Adding single/multiple/duplicate tags
  - Tag normalization (lowercase, strip)
  - get_tags_string() functionality
  - File save/load operations

- **LocalEars/Whisper** (4 tests, 76% coverage):
  - Initialization with default/custom configs
  - Basic transcription with mocked WhisperModel
  - Timestamp formatting (MM:SS format)

- **LocalBrain/AI** (5 tests, 28% coverage):
  - Model initialization (default/custom)
  - Prompt building with caption/transcript/comments
  - Core logic without actual LLM calls

- **HybridGrabber/Downloaders** (5 tests, 38% coverage):
  - Grabber initialization
  - Username extraction from URLs
  - Gallery-dl integration (mocked)
  - InstagramContent dataclass

## Fixtures (conftest.py)

- `temp_dir` - Temporary directory for tests
- `mock_tags_file` - Mock tags JSON file
- `sample_tags` - Sample tag list
- `sample_transcript` - Sample transcription text
- `sample_description` - Sample content description
- `mock_llama_cpp_response` - Mock AI response
- `mock_whisper_result` - Mock Whisper transcription result

## Mocking Strategy

- **WhisperModel**: Mocked with `@patch('modules.local_ears.WhisperModel')`
- **llama.cpp client**: Mocked at HTTP/client layer in `local_brain`
- **subprocess.run**: Mocked for downloader tests
- **File I/O**: Using `tmp_path` fixture for safe file operations

## CI/CD Integration

Repository workflow:
```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
jobs:
  checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: python -m pip install -r requirements.txt -r requirements-dev.txt
      - run: python -m ruff check src tests module2_transcribe.py module3_analyze.py scripts
      - run: python -m mypy --config-file mypy.ini
      - run: python -m pytest tests -q
```

## Best Practices

✅ Use fixtures for shared test data  
✅ Mock external dependencies (llama.cpp, Whisper, downloaders)  
✅ Use `tmp_path` for file operations  
✅ Test both success and error cases  
✅ Use descriptive test names  
✅ Keep tests isolated and independent  

## Notes

- Tests use mocks to avoid real API calls
- No actual downloads or AI inference during tests
- All file operations use temporary directories
- Tests are fast and can run offline
