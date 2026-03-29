<p align="center">
  <br />
  <code>✦ aura</code>
  <br /><br />
  <strong>Stop re-explaining yourself to every AI tool.</strong>
  <br />
  <sub>Define who you are once. Serve your identity to every AI — locally, privately, instantly.</sub>
  <br /><br />
  <a href="https://pypi.org/project/aura-ctx/"><img alt="PyPI" src="https://img.shields.io/pypi/v/aura-ctx?color=black&label=aura-ctx" /></a>
  <a href="https://pepy.tech/projects/aura-ctx"><img alt="Downloads" src="https://static.pepy.tech/personalized-badge/aura-ctx?period=total&units=international_system&left_color=black&right_color=black&left_text=downloads" /></a>
  <a href="https://github.com/WozGeek/aura-ctx/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-black" /></a>
  <a href="https://pypi.org/project/aura-ctx/"><img alt="Python" src="https://img.shields.io/pypi/pyversions/aura-ctx?color=black" /></a>
  <a href="https://github.com/WozGeek/aura-ctx/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/WozGeek/aura-ctx?style=flat&color=black" /></a>
</p>

<p align="center">
  <a href="https://wozgeek.github.io/aura-ctx">Website</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#how-it-works">How It Works</a> ·
  <a href="#supported-tools">Supported Tools</a> ·
  <a href="#commands">Commands</a> ·
  <a href="#security">Security</a>
</p>

---

<!-- TODO: terminal recording GIF -->
<!-- Record: asciinema rec demo.cast && agg demo.cast demo.gif -->
<!-- Show: pip install aura-ctx && aura quickstart (30-second flow) -->

## The problem

Every AI tool starts from scratch. Claude doesn't know what ChatGPT learned.
Cursor doesn't know your writing style. Gemini has no idea what framework you
prefer.

You re-explain yourself dozens of times a day — your stack, your rules, your
role, your preferences. Every new conversation. Every new tool. Every new
session.

The industry is building solutions at the wrong layer:

| Layer                   | What it solves                      | Tools                        |
| ----------------------- | ----------------------------------- | ---------------------------- |
| **Memory**              | What happened in past conversations | Mem0, Zep, DeltaMemory       |
| **Context engineering** | What the AI should know right now   | LACP, Claudesidian, OpenClaw |
| **Identity**            | Who you are, across everything      | **aura**                     |

Memory is session history. Context is prompt engineering. **Identity is who you
are** — your stack, your style, your rules, your role — structured, portable,
and owned by you.

**aura is the identity layer.**

---

## How aura solves it

aura scans your machine, asks you five questions, and generates plain YAML
context packs stored locally at `~/.aura/packs/`. It then exposes those packs to
any AI tool through the
[Model Context Protocol](https://modelcontextprotocol.io) — a local MCP server
running on `localhost:3847`.

Every AI that supports MCP can now read your identity. One definition. Every
tool. Zero copy-paste.

```
You
│
├── aura scan          Detects languages, frameworks, tools, git identity
├── aura onboard       5 questions → writing style, role, preferences, rules
├── aura import        Pulls context from ChatGPT & Claude exports
│
▼
Context Packs (YAML)   ~/.aura/packs/developer.yaml
│                      ~/.aura/packs/writer.yaml
│                      ~/.aura/packs/work.yaml
│
▼
MCP Server             localhost:3847
│
├──▶ Claude Desktop    (auto-configured)
├──▶ ChatGPT Desktop   (SSE)
├──▶ Cursor IDE        (auto-configured)
└──▶ Gemini CLI        (auto-configured)
```

100% local. No cloud. No telemetry. No lock-in.

---

## Quick start

```bash
pip install aura-ctx
aura quickstart
```

That's it. Here's what happens in 30 seconds:

```
✦ aura quickstart

Step 1/5 — Scanning your machine...
  ✦ Detected 12 facts about your dev environment

Step 2/5 — Quick questions about you...
  What's your role?                    → Full-stack dev at Acme Corp
  How do you want AI to talk to you?   → 1 (Direct, no fluff)
  What are you working on?             → shipping v2 of our dashboard
  Any rules or pet peeves?             → No corporate jargon, always use TypeScript
  What human languages?                → English and French

  ✦ Created developer  (8 facts, 4 rules)
  ✦ Created writer     (2 facts, 3 rules)
  ✦ Created work       (2 facts, 0 rules)

Step 3/5 — Configuring AI tools...
  ✦ Claude Desktop configured
  ✦ Cursor configured

Step 4/5 — Security audit...
  ✦ All clean — no secrets detected

Step 5/5 — Starting MCP server...
  ✦ http://localhost:3847/mcp
  Restart your AI tools — they know you now.
```

No Docker. No database. No cloud account.

---

## Context packs

Your identity lives in scoped YAML files. Each pack covers a domain —
development, writing, work, or anything you define. Human-readable.
Git-friendly. Fully editable. They never leave your machine unless you choose
otherwise.

```yaml
# ~/.aura/packs/developer.yaml
name: developer
scope: development

facts:
  - key: languages.primary
    value: [TypeScript, Python]
    type: skill
    confidence: high
  - key: frameworks
    value: [Next.js, FastAPI, Tailwind, Supabase]
    type: skill
  - key: editor
    value: Cursor
    type: preference
  - key: style.code
    value: "Explicit types, functional patterns, minimal comments"
    type: style

rules:
  - instruction: Always use TypeScript strict mode — no 'any'
    priority: 9
  - instruction: Dark theme by default, CSS variables for all colors
    priority: 8
  - instruction: Error handling with specific types, not generic catches
    priority: 7
```

### Smart token delivery

aura doesn't dump everything into every context window. It serves your identity
at the right depth, on demand:

| Level | MCP Tool            | Tokens   | When                                    |
| ----- | ------------------- | -------- | --------------------------------------- |
| 1     | `get_identity_card` | ~50–100  | Auto-called at every conversation start |
| 2     | `get_user_profile`  | ~200–500 | When the AI needs more about you        |
| 3     | `get_all_context`   | ~1000+   | Only when explicitly requested          |

Most conversations only ever need Level 1. The AI gets your identity without
burning your context window.

---

## Supported tools

| Tool                | Setup                        | Transport       |
| ------------------- | ---------------------------- | --------------- |
| **Claude Desktop**  | `aura setup` — auto          | Streamable HTTP |
| **Cursor IDE**      | `aura setup` — auto          | Streamable HTTP |
| **Gemini CLI**      | `aura setup` — auto          | SSE             |
| **ChatGPT Desktop** | Developer Mode → add SSE URL | SSE             |
| **Any MCP client**  | Point to `localhost:3847`    | HTTP or SSE     |

```bash
aura setup   # auto-configures all detected tools
aura serve   # starts the MCP server on localhost:3847
```

<details>
<summary>Claude Desktop — manual config</summary>

```json
{
  "mcpServers": {
    "aura": { "url": "http://localhost:3847/mcp" }
  }
}
```

</details>

<details>
<summary>Cursor IDE — manual config</summary>

```json
{
  "mcpServers": {
    "aura": { "url": "http://localhost:3847/mcp" }
  }
}
```

</details>

<details>
<summary>ChatGPT Desktop — manual config</summary>

Settings → Connectors → Advanced → Developer Mode:

```
SSE URL: http://localhost:3847/sse
```

</details>

<details>
<summary>Gemini CLI — manual config</summary>

```json
{
  "mcpServers": {
    "aura": { "uri": "http://localhost:3847/sse" }
  }
}
```

</details>

---

## Commands

### Getting started

| Command              | What it does                                               |
| -------------------- | ---------------------------------------------------------- |
| `aura quickstart`    | Full setup: scan → onboard → configure → audit → serve     |
| `aura scan`          | Auto-detect your stack from tools, repos, and config files |
| `aura onboard`       | 5 questions to generate your context packs                 |
| `aura setup`         | Auto-configure Claude Desktop, Cursor, Gemini CLI          |
| `aura serve`         | Start the MCP server on `localhost:3847`                   |
| `aura serve --watch` | Start with hot-reload on YAML changes                      |

### Managing packs

| Command                            | What it does                    |
| ---------------------------------- | ------------------------------- |
| `aura list`                        | List all context packs          |
| `aura show <pack>`                 | Display a pack's full contents  |
| `aura add <pack> <key> <value>`    | Add a fact without opening YAML |
| `aura edit <pack>`                 | Open a pack in `$EDITOR`        |
| `aura create <name>`               | Create a new empty pack         |
| `aura create <name> -t <template>` | Create from a built-in template |
| `aura templates`                   | List all 14 available templates |
| `aura delete <pack>`               | Delete a pack                   |
| `aura diff <a> <b>`                | Compare two packs               |

### Templates

14 built-in templates — each includes domain-specific facts and AI interaction
rules.

**Stack-specific** — `frontend` · `backend` · `data-scientist` · `mobile` ·
`devops` · `ai-builder`

**Role-specific** — `founder` · `student` · `marketer` · `designer`

**General-purpose** — `developer` · `writer` · `researcher` · `work`

```bash
aura templates                           # list all templates
aura create mydev -t frontend            # frontend dev pack
aura create research -t data-scientist   # data science pack
aura create study -t student             # student pack
```

Every template is a starting point. Edit the generated YAML to match your actual
setup.

### Health & maintenance

| Command            | What it does                                                |
| ------------------ | ----------------------------------------------------------- |
| `aura doctor`      | Check pack health — bloat, stale facts, duplicates, secrets |
| `aura audit`       | Scan packs for leaked API keys, tokens, credentials         |
| `aura audit --fix` | Auto-redact critical secrets                                |
| `aura consolidate` | Merge duplicate facts, resolve contradictions across packs  |
| `aura decay`       | Remove expired facts based on type-aware TTL                |

### Import & export

| Command                               | What it does                                       |
| ------------------------------------- | -------------------------------------------------- |
| `aura import -s chatgpt <file>`       | Import from a ChatGPT data export                  |
| `aura import -s claude <file>`        | Import from a Claude conversation export           |
| `aura extract <file>`                 | Extract facts from conversations using a local LLM |
| `aura export <pack> -f system-prompt` | Universal LLM system prompt                        |
| `aura export <pack> -f cursorrules`   | `.cursorrules` file for Cursor                     |
| `aura export <pack> -f chatgpt`       | ChatGPT custom instructions                        |
| `aura export <pack> -f claude`        | Claude memory statements                           |

---

## Security

aura was built privacy-first from the ground up. Your context never leaves your
machine.

```bash
aura serve                               # localhost only, no auth
aura serve --token my-secret            # require Bearer token
aura serve --packs developer,writer     # expose only specific packs
aura serve --read-only                  # prevent writes via MCP
aura serve --watch                      # hot-reload on changes
```

**Secret detection** — `aura audit` scans every fact and rule for leaked
credentials before they reach an LLM. Catches 30+ patterns: AWS keys, GitHub
tokens, OpenAI/Anthropic API keys, Slack tokens, database URLs, private keys,
and more. The MCP server scrubs critical secrets automatically at serve time,
even if you skip the audit.

| Control           | What it does                                                |
| ----------------- | ----------------------------------------------------------- |
| Localhost binding | Binds to `127.0.0.1` only — not reachable from the network  |
| Bearer token auth | Optional `--token` flag or `AURA_TOKEN` env var             |
| Scoped serving    | Choose which packs each tool can access                     |
| Read-only mode    | AI tools read your context — they can never write to it     |
| No telemetry      | No analytics, no crash reports, no usage tracking. Nothing. |

---

## Architecture

aura is a lean Python CLI with no heavy dependencies. No database. No Docker. No
daemon.

```
aura/
├── cli.py           # 22 commands (Typer + Rich)
├── schema.py        # ContextPack, Fact, Rule (Pydantic)
├── mcp_server.py    # FastAPI MCP server (HTTP + SSE)
├── scanner.py       # Machine scanner with incremental SHA-256 hashing
├── onboard.py       # Interactive onboarding
├── pack.py          # Pack CRUD + template engine
├── audit.py         # Secret detection engine (30+ patterns)
├── scan_cache.py    # Content hashing for fast re-scans
├── watcher.py       # File watcher for hot-reload
├── doctor.py        # Pack health checker
├── consolidate.py   # Dedup + contradiction detection
├── extractor.py     # LLM-based fact extraction (Ollama / OpenAI)
├── diff.py          # Pack diffing
├── setup.py         # Auto-config for Claude Desktop, Cursor, Gemini CLI
├── exporters/       # system-prompt, cursorrules, chatgpt, claude
└── importers/       # ChatGPT + Claude data importers
```

7,800+ lines of Python · 151 tests · 22 commands · 14 templates · MIT license

---

## Roadmap

### Shipped

- [x] Machine scanner — languages, frameworks, tools, projects, git identity
- [x] Context packs — typed facts, confidence levels, sources
- [x] MCP server — resources, tools, prompt templates (HTTP + SSE)
- [x] Auto-config for Claude Desktop, Cursor, Gemini CLI, ChatGPT Desktop
- [x] Token auth, scoped serving, read-only mode
- [x] Import from ChatGPT + Claude data exports
- [x] LLM-based fact extraction (Ollama, OpenAI)
- [x] Pack health checker + consolidation engine
- [x] Memory decay with type-aware TTL
- [x] Secret detection and auto-redaction (30+ patterns)
- [x] Incremental scan with SHA-256 content hashing
- [x] File watcher (`aura serve --watch`)
- [x] Three-level token delivery
- [x] 14 built-in templates

### Next

- [ ] TypeScript / npm package — `npx aura-ctx`
- [ ] JSON Schema spec for context packs
- [ ] Usage-based fact priority
- [ ] Per-agent permissions
- [ ] Share via GitHub Gist
- [ ] GraphRAG local knowledge graph
- [ ] Cloud sync (opt-in, end-to-end encrypted)
- [ ] Team sharing

---

## Contributing

```bash
git clone https://github.com/WozGeek/aura-ctx.git
cd aura-ctx
pip install -e ".[dev]"
pytest
```

**Good first issues:**

- **New export format** — add Windsurf, Continue.dev, or AGENTS.md support
  ([guide](CONTRIBUTING.md#adding-an-exporter))
- **New importer** — Gemini history export parsing
- **Pack templates** — create domain-specific starter packs
- **JSON Schema** — publish `context-pack.schema.json` to formalize the pack
  format
- **Translations** — translate this README to French, Spanish, Portuguese, or
  Chinese

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contribution guide.

---

## License

[MIT](LICENSE) — © Enoch Afanwoubo
