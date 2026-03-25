<p align="center">
  <br />
  <strong><code>✦ aura</code></strong>
  <br />
  <em>Your AI identity, portable across every tool.</em>
  <br /><br />
  <a href="https://pypi.org/project/aura-ctx/"><img alt="PyPI" src="https://img.shields.io/pypi/v/aura-ctx?color=blue&label=PyPI" /></a>
  <a href="https://github.com/WozGeek/BettaAura/actions"><img alt="CI" src="https://github.com/WozGeek/BettaAura/actions/workflows/ci.yml/badge.svg" /></a>
  <a href="https://github.com/WozGeek/BettaAura/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-green" /></a>
  <a href="https://pypi.org/project/aura-ctx/"><img alt="Python" src="https://img.shields.io/pypi/pyversions/aura-ctx" /></a>
  <a href="https://github.com/WozGeek/BettaAura/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/WozGeek/BettaAura?style=flat" /></a>
</p>

<p align="center">
  <a href="https://wozgeek.github.io/BettaAura">Website</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#supported-tools">Supported Tools</a> •
  <a href="#commands">Commands</a> •
  <a href="#security">Security</a>
</p>

---

## Why aura

Every AI tool starts from scratch. Claude doesn't know what ChatGPT learned.
Cursor doesn't know your writing style. Gemini has no idea what framework you
prefer. You re-explain yourself — every session, every tool, every time.

The industry is building memory and context solutions, but they solve the wrong
layer:

| Layer                   | What it solves                      | Examples                     |
| ----------------------- | ----------------------------------- | ---------------------------- |
| **Memory**              | What happened in past conversations | Mem0, Zep, DeltaMemory       |
| **Context engineering** | What the AI should know right now   | LACP, Claudesidian, OpenClaw |
| **Identity**            | Who you are, across everything      | **aura**                     |

Memory is session history. Context is prompt engineering. **Identity is who you
are** — your stack, your style, your rules, your role — structured, portable,
and owned by you.

aura is the identity layer. One CLI. One source of truth. Every AI tool.

## Quick Start

```bash
pip install aura-ctx
aura quickstart
```

`quickstart` scans your machine, asks 5 questions, configures your AI tools,
runs a security audit, and starts serving — one command.

30 seconds. No Docker. No database. No cloud account.

## How It Works

```
You
 │
 ├── aura scan          Detects languages, frameworks, tools, projects
 ├── aura onboard       5 questions → writing style, role, rules
 ├── aura import        Pulls context from ChatGPT & Claude exports
 │
 ▼
Context Packs (YAML)    ~/.aura/packs/developer.yaml
 │                      ~/.aura/packs/writer.yaml
 │                      ~/.aura/packs/work.yaml
 │
 ▼
MCP Server              localhost:3847
 │
 ├──▶ Claude Desktop    (auto-configured)
 ├──▶ ChatGPT Desktop   (SSE)
 ├──▶ Cursor IDE        (auto-configured)
 └──▶ Gemini CLI        (auto-configured)
```

### Context Packs

Your identity is organized into scoped YAML files. Each pack covers a domain —
development, writing, work, or anything custom:

```yaml
# ~/.aura/packs/developer.yaml
name: developer
scope: development
facts:
  - key: languages.primary
    value: [TypeScript, Python]
    type: skill
    confidence: high
  - key: editor
    value: Cursor
    type: preference
  - key: frameworks
    value: [Next.js, FastAPI, Tailwind, Supabase]
    type: skill
rules:
  - instruction: Always use TypeScript strict mode — no 'any'
    priority: 9
  - instruction: Dark theme by default, CSS variables for all colors
    priority: 8
```

You own these files. Human-readable. Git-friendly. They never leave your machine
unless you choose otherwise.

### Three-Level Token Delivery

AI tools have limited context windows. aura serves your identity at the right
depth:

| Level | MCP Tool            | Tokens   | Use                               |
| ----- | ------------------- | -------- | --------------------------------- |
| 1     | `get_identity_card` | ~50–100  | Auto-called at conversation start |
| 2     | `get_user_profile`  | ~200–500 | When the AI needs more detail     |
| 3     | `get_all_context`   | ~1000+   | Only when explicitly asked        |

The server instructs AI clients to start with the identity card and drill down
only when needed.

## Supported Tools

| Tool                | Setup                        | Transport       |
| ------------------- | ---------------------------- | --------------- |
| **Claude Desktop**  | `aura setup` — auto          | Streamable HTTP |
| **Cursor IDE**      | `aura setup` — auto          | Streamable HTTP |
| **Gemini CLI**      | `aura setup` — auto          | SSE             |
| **ChatGPT Desktop** | Developer Mode → add SSE URL | SSE             |
| **Any MCP client**  | Point to `localhost:3847`    | HTTP or SSE     |

```bash
aura setup   # writes config for all detected tools
aura serve   # starts MCP server on localhost:3847
```

<details>
<summary><strong>Claude Desktop</strong></summary>

Auto-configured by `aura setup`. Manual config:

```json
{
  "mcpServers": {
    "aura": { "url": "http://localhost:3847/mcp" }
  }
}
```

</details>

<details>
<summary><strong>Cursor IDE</strong></summary>

Auto-configured by `aura setup`. Manual config:

```json
{
  "mcpServers": {
    "aura": { "url": "http://localhost:3847/mcp" }
  }
}
```

</details>

<details>
<summary><strong>ChatGPT Desktop</strong></summary>

Settings → Connectors → Advanced → Developer Mode:

```
SSE URL: http://localhost:3847/sse
```

</details>

<details>
<summary><strong>Gemini CLI</strong></summary>

Auto-configured by `aura setup`. Manual config:

```json
{
  "mcpServers": {
    "aura": { "uri": "http://localhost:3847/sse" }
  }
}
```

</details>

## Commands

### Getting started

| Command              | What it does                                               |
| -------------------- | ---------------------------------------------------------- |
| `aura quickstart`    | Full setup: scan → onboard → setup → audit → serve         |
| `aura scan`          | Auto-detect your stack from tools, repos, and config files |
| `aura onboard`       | 5 questions to generate your context packs                 |
| `aura setup`         | Auto-configure Claude Desktop, Cursor, Gemini              |
| `aura serve`         | Start the MCP server                                       |
| `aura serve --watch` | Start with hot-reload on YAML changes                      |

### Managing packs

| Command                            | What it does                    |
| ---------------------------------- | ------------------------------- |
| `aura list`                        | List all context packs          |
| `aura show <pack>`                 | Display a pack's contents       |
| `aura add <pack> <key> <value>`    | Add a fact without editing YAML |
| `aura edit <pack>`                 | Open a pack in `$EDITOR`        |
| `aura create <name>`               | Create a new empty pack         |
| `aura create <name> -t <template>` | Create from a built-in template |
| `aura delete <pack>`               | Delete a pack                   |
| `aura diff <a> <b>`                | Compare two packs               |

### Health & maintenance

| Command            | What it does                                                |
| ------------------ | ----------------------------------------------------------- |
| `aura doctor`      | Check pack health — bloat, stale facts, duplicates, secrets |
| `aura audit`       | Scan packs for leaked API keys, tokens, credentials         |
| `aura audit --fix` | Auto-redact critical secrets                                |
| `aura consolidate` | Merge duplicate facts, find contradictions across packs     |
| `aura decay`       | Remove expired facts based on type-aware TTL                |

### Import & export

| Command                               | What it does                                       |
| ------------------------------------- | -------------------------------------------------- |
| `aura import -s chatgpt <file>`       | Import from a ChatGPT data export                  |
| `aura import -s claude <file>`        | Import from a Claude data export                   |
| `aura extract <file>`                 | Extract facts from conversations using a local LLM |
| `aura export <pack> -f system-prompt` | Universal LLM system prompt                        |
| `aura export <pack> -f cursorrules`   | `.cursorrules` file                                |
| `aura export <pack> -f chatgpt`       | ChatGPT custom instructions                        |
| `aura export <pack> -f claude`        | Claude memory statements                           |

## Security

aura is local-first. Your context never leaves your machine.

```bash
aura serve                              # localhost only, open
aura serve --token my-secret            # require Bearer token
aura serve --packs developer,writer     # expose only specific packs
aura serve --read-only                  # block all writes via MCP
aura serve --watch                      # auto-reload on pack changes
```

**Secret detection** — `aura audit` scans every fact and rule for leaked
credentials before they reach an LLM. Catches 30+ patterns: AWS keys, GitHub
tokens, OpenAI/Anthropic API keys, Slack tokens, database URLs, private keys,
Bearer tokens, and more. The MCP server scrubs critical secrets automatically at
serve time — even if you forget to audit.

- Binds to `127.0.0.1` only — not reachable from the network
- Optional Bearer token auth (`--token` or `AURA_TOKEN` env var)
- Scoped serving — control which packs each tool sees
- Read-only mode — AI reads your context, never writes to it
- **No telemetry. No analytics. No cloud. No tracking.**

## Architecture

```
aura/
├── cli.py           # 22 commands (Typer + Rich)
├── schema.py        # ContextPack, Fact, Rule (Pydantic)
├── mcp_server.py    # FastAPI MCP server (HTTP + SSE)
├── scanner.py       # Machine scanner with incremental hashing
├── onboard.py       # Interactive onboarding
├── pack.py          # Pack CRUD + templates
├── audit.py         # Secret detection engine (30+ patterns)
├── scan_cache.py    # SHA-256 content hashing for fast re-scans
├── watcher.py       # File watcher for hot-reload
├── doctor.py        # Pack health checker
├── consolidate.py   # Dedup + contradiction detection
├── extractor.py     # LLM-based extraction (Ollama / OpenAI)
├── diff.py          # Pack comparison
├── setup.py         # Auto-config for Claude, Cursor, Gemini
├── exporters/       # system-prompt, cursorrules, chatgpt, claude
└── importers/       # ChatGPT + Claude data importers
```

7,600+ lines of Python · 151 tests · 22 commands · MIT license

## Roadmap

### Shipped

- [x] Machine scanner — languages, frameworks, tools, projects, git identity
- [x] Context packs with typed facts, confidence levels, sources
- [x] MCP server — resources, tools, prompt templates
- [x] Auto-config for Claude Desktop, Cursor, Gemini CLI
- [x] ChatGPT Desktop support via SSE
- [x] Token auth, scoped serving, read-only mode
- [x] Import from ChatGPT + Claude data exports
- [x] LLM-based extraction (Ollama, OpenAI)
- [x] Pack health checker + consolidation engine
- [x] Memory decay with type-aware TTL
- [x] Secret detection and auto-redaction
- [x] Incremental scan with content hashing
- [x] File watcher (`aura serve --watch`)
- [x] Three-level token delivery

### Next

- [ ] TypeScript / npm package — `npx aura-ctx`
- [ ] JSON Schema spec for context packs
- [ ] Usage-based fact priority
- [ ] Per-agent permissions
- [ ] Pack templates (`--template frontend`, `--template data-scientist`)
- [ ] Share via GitHub Gist
- [ ] GraphRAG local knowledge graph
- [ ] Cloud sync (opt-in, encrypted)
- [ ] Team sharing

## Contributing

```bash
git clone https://github.com/WozGeek/BettaAura.git
cd BettaAura
pip install -e ".[dev]"
pytest
```

Good first contributions: new export formats (Windsurf, Copilot, AGENTS.md), new
importers (Gemini), template packs, docs. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) — © Enoch Afanwoubo
