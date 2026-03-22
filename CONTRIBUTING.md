# Contributing to aura

Thanks for your interest in contributing to aura. Here's how to get started.

## Setup

```bash
git clone https://github.com/WozGeek/BettaAura.git
cd aura
pip install -e ".[dev]"
```

## Running tests

```bash
pytest tests/ -v
```

## Linting

```bash
ruff check aura/
```

## What to work on

Check the [Issues](https://github.com/WozGeek/BettaAura/issues) tab. Good first contributions:

- **New export formats** — Windsurf, GitHub Copilot, Gemini, AGENTS.md
- **New importers** — Claude exports, Gemini exports
- **Template packs** — domain-specific templates (data-science, design, devops, etc.)
- **Documentation** — usage examples, tutorials, translations

## Adding an exporter

1. Create a new file in `aura/exporters/your_format.py`
2. Implement an export function that takes `list[ContextPack]` and returns a string
3. Add the format to `ExportFormat` enum in `aura/cli.py`
4. Wire it into the `export` command's if/elif chain
5. Add tests in `tests/test_core.py`

## Adding an importer

1. Create a new file in `aura/importers/your_platform.py`
2. Implement an import function that returns a `ContextPack`
3. Add the source to `ImportSource` enum in `aura/cli.py`
4. Wire it into the `import` command
5. Add tests

## Code style

- Python 3.10+, type hints everywhere
- Ruff for linting
- Keep functions focused and well-documented
- Tests for every new feature

## Pull requests

- One feature per PR
- Include tests
- Update README if adding user-facing features
- Keep commits clean and descriptive

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
