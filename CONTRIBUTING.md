# Contributing

Thanks for your interest in contributing to Create Pull Request Action (Python).

## Development Setup

```bash
git clone https://github.com/dikshant-devops/create-pull-request.git
cd create-pull-request
pip install -r requirements.txt
pip install pytest pytest-cov pytest-mock ruff mypy pre-commit
pre-commit install
```

## Running the Same Checks as CI

These commands match what runs in `.github/workflows/test.yml`:

```bash
# Unit tests (Python 3.9 / 3.10 / 3.11)
PYTHONPATH=src pytest tests/unit/ -v

# Integration tests (requires git configured)
git config --global user.name "Test"
git config --global user.email "test@example.com"
PYTHONPATH=src pytest tests/integration/ -v

# Coverage report
PYTHONPATH=src pytest tests/ -v --cov=src/create_pull_request --cov-report=term

# Lint
ruff check src/

# Format check
ruff format --check src/

# Type check
mypy src/create_pull_request --ignore-missing-imports

# Docker build + module verification
docker build -t cpr-test .
docker run --rm --entrypoint python cpr-test -c "from create_pull_request.main import run; print('OK')"
```

## Pull Request Process

1. Fork the repository and create a feature branch from `master`.
2. Add tests for any new functionality.
3. Ensure **all** checks above pass locally.
4. Submit a pull request -- CI will run the same checks automatically.

## Code Style

- Follow existing patterns in the codebase.
- Use type hints for all function signatures.
- Keep functions focused and small.

## Required CI Checks

Every PR must pass these status checks before merge:

| Check | What it does |
|-------|-------------|
| Unit Tests | `pytest tests/unit/` across Python 3.9, 3.10, 3.11 |
| Integration Tests | `pytest tests/integration/` with real git operations |
| Docker Build | Builds the image and verifies module import |
| Lint and Type Check | `ruff check`, `ruff format --check`, `mypy` |
| CodeQL | Python static analysis (security) |
| Container Scan | Trivy vulnerability scan on Docker image |
