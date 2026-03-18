# ✦ aura

**Your portable AI context. Carry your identity across every AI tool.**

---

aura is an open-source CLI that lets you define, manage, and export your personal AI context as structured **context packs** — scoped bundles of facts, preferences, and rules that any AI tool can understand.

Stop re-explaining who you are to every AI. Define it once, export it everywhere.

```bash
pip install aura-ctx
aura init
aura create developer --template developer
aura export developer --format cursorrules -o .cursorrules
```

## The Problem

You use Claude for analysis, ChatGPT for writing, Cursor for coding, Gemini for research. Each one makes you start from scratch. Your preferences, your stack, your style, your constraints — locked inside each platform's proprietary memory, invisible to the others.

**MCP solved tool interoperability. aura solves context interoperability.**

## How It Works

aura introduces **context packs** — portable, scoped YAML files that describe who you are in a specific domain:

```yaml
# ~/.aura/packs/developer.yaml
name: developer
scope: development
facts:
  - key: languages.primary
    value: [Python, TypeScript]
    type: skill
    confidence: high
  - key: frameworks
    value: [Next.js, FastAPI]
    type: skill
  - key: style.comments
    value: "Minimal — only for non-obvious logic"
    type: style
rules:
  - instruction: "Always use strict TypeScript"
    priority: 8
  - instruction: "Prefer functional patterns over OOP"
    priority: 5
```

Then export to any format:

```bash
# For Cursor IDE
aura export developer --format cursorrules -o .cursorrules

# For Claude
aura export developer writer --format claude-memory

# For ChatGPT Custom Instructions
aura export developer writer --format chatgpt-instructions

# For any LLM (generic system prompt)
aura export developer --format system-prompt
```

## Quick Start

```bash
# Install
pip install aura-ctx

# Initialize
aura init

# Create from template
aura create developer --template developer

# Customize
aura edit developer

# Export
aura export developer --format system-prompt
```

## Import from Existing Platforms

Already have context locked in ChatGPT? Extract it:

```bash
# From a ChatGPT data export (Settings → Data Controls → Export)
aura import --source chatgpt chatgpt-export.zip

# Review what was extracted
aura show chatgpt-import

# Edit and refine
aura edit chatgpt-import
```

## Commands

| Command | Description |
|---------|-------------|
| `aura init` | Initialize aura |
| `aura create <name>` | Create a new context pack |
| `aura create <name> -t <template>` | Create from template |
| `aura list` | List all packs |
| `aura show <name>` | Display a pack |
| `aura show <name> --raw` | Show raw YAML |
| `aura edit <name>` | Open in $EDITOR |
| `aura export <names...> -f <format>` | Export to platform format |
| `aura import -s <source> <file>` | Import from platform export |
| `aura delete <name>` | Delete a pack |
| `aura extract -s <source> <file>` | Deep-extract with LLM |
| `aura diff <source> <target>` | Compare two packs |
| `aura serve --mcp` | Start MCP server |
| `aura templates` | List available templates |

## Export Formats

| Format | Flag | Target |
|--------|------|--------|
| System Prompt | `--format system-prompt` | Any LLM |
| Cursor Rules | `--format cursorrules` | Cursor IDE |
| Claude Memory | `--format claude-memory` | Claude |
| ChatGPT Instructions | `--format chatgpt-instructions` | ChatGPT |

## Context Pack Schema

A context pack is a YAML file with this structure:

```yaml
name: string          # Unique identifier (lowercase)
scope: string         # Domain: development, writing, work, research, etc.
meta:
  schema_version: "0.1.0"
  description: string
  tags: [string]
facts:
  - key: string       # Dot-notation key
    value: string | [string]
    type: preference | identity | skill | style | constraint | context
    confidence: high | medium | low
    source: manual | chatgpt-import | claude-import
rules:
  - instruction: string
    priority: 0-10    # Higher = more important
```

**Key design principle:** packs are **scoped by domain**. Your `developer` pack never leaks into a health consultation. Your `work` pack stays separate from your `personal` pack. You control what goes where.

## Philosophy

1. **Local-first.** Your context lives on your machine in `~/.aura/packs/`. No cloud, no account, no tracking.
2. **Schema, not platform.** aura defines a portable format. Exporters adapt it to each tool's native language.
3. **Scoped, not monolithic.** Separate packs for separate domains. No semantic leakage.
4. **Human-readable.** YAML files you can read, edit, version control, and share.
5. **Progressively useful.** Works with zero setup (templates), gets better as you customize.

## Roadmap

- [x] Core schema & context packs
- [x] CLI (create, edit, list, show, export, import, delete, diff)
- [x] Export: system prompt, .cursorrules, Claude memory, ChatGPT instructions
- [x] Import: ChatGPT data export (heuristic extraction)
- [x] MCP server (`aura serve --mcp`) — serve context to any MCP client
- [x] LLM-powered extraction (`aura extract`) — deep context mining with local/cloud models
- [x] `aura diff` — compare packs (local vs platform import)
- [x] 39 tests covering schema, exporters, importers, diff, MCP, extractor
- [ ] Import: Claude conversation export
- [ ] AGENTS.md export — generate AGENTS.md for repos
- [ ] Windsurf / Copilot / Gemini export formats
- [ ] `aura sync` — bidirectional sync via MCP
- [ ] Web dashboard for visual pack editing
- [ ] Rust rewrite for single-binary distribution

## Contributing

aura is MIT-licensed and welcomes contributions. See [CONTRIBUTING.md](CONTRIBUTING.md).

Built by [Distal Inc.](https://distalinc.com) — open infrastructure for the AI era.

## License

MIT
