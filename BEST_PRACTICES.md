1. Ruff (Linter + Formatter) - Replaces ESLint + Prettier in one tool. Extremely fast (written in Rust).

```toml
# pyproject.toml
[tool.ruff]
line-length = 88
select = [
    "E",    # pycodestyle errors
    "F",    # pyflakes
    "I",    # isort (import sorting)
    "UP",   # pyupgrade (modern syntax)
    "B",    # bugbear (common pitfalls)
    "SIM",  # simplify
]
fix = true  # auto-fix on run

[tool.ruff.format]
quote-style = "double"
```

2. pre-commit (Git Hooks — like Husky + lint-staged)

```bash
uv add pre-commit --dev
```

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]
```