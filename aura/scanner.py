"""
aura.scanner — Local machine intelligence.

Scans your development environment to auto-generate context packs
without writing a single line of YAML.

Detects:
  - Git repos → languages, frameworks, project names
  - Package files → exact dependencies (package.json, requirements.txt, Cargo.toml, etc.)
  - Config files → editor, shell, existing .cursorrules
  - Git identity → name, email
  - Installed tools → editors, CLI tools, runtimes
  - OS & environment → platform, shell, terminal
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

from aura.schema import Confidence, ContextPack, Fact, FactType, PackMeta, Rule


# ---------------------------------------------------------------------------
# Main scanner
# ---------------------------------------------------------------------------
class Scanner:
    """Scans the local machine and builds a ContextPack."""

    def __init__(self, scan_dirs: Optional[list[str]] = None, max_repos: int = 20,
                 incremental: bool = True):
        self.scan_dirs = scan_dirs or self._default_scan_dirs()
        self.max_repos = max_repos
        self.incremental = incremental
        self.facts: list[Fact] = []
        self.rules: list[Rule] = []
        self._cache_updates: dict[str, str] = {}  # source_key -> hash
        self._skipped: int = 0

    def _should_scan(self, source_key: str, content: str) -> bool:
        """Check if this source needs re-scanning based on content hash."""
        if not self.incremental:
            return True
        try:
            from aura.scan_cache import has_changed, hash_content
            content_hash = hash_content(content)
            self._cache_updates[source_key] = content_hash
            if not has_changed(source_key, content_hash):
                self._skipped += 1
                return False
        except ImportError:
            pass
        return True

    def _should_scan_file(self, source_key: str, filepath: Path) -> bool:
        """Check if a file needs re-scanning based on file hash."""
        if not self.incremental:
            return True
        try:
            from aura.scan_cache import has_changed, hash_file
            file_hash = hash_file(filepath)
            if file_hash is None:
                return True
            self._cache_updates[source_key] = file_hash
            if not has_changed(source_key, file_hash):
                self._skipped += 1
                return False
        except ImportError:
            pass
        return True

    def _flush_cache(self):
        """Write all accumulated cache updates to disk."""
        if not self.incremental or not self._cache_updates:
            return
        try:
            from aura.scan_cache import update_cache
            update_cache(self._cache_updates)
        except ImportError:
            pass

    def scan(self) -> ContextPack:
        """Run all scanners and return a populated ContextPack."""
        self._scan_git_identity()
        self._scan_installed_tools()
        self._scan_repos()
        self._scan_existing_rules()
        self._scan_system_info()

        # Flush cache after successful scan
        self._flush_cache()

        return ContextPack(
            name="scanned",
            scope="development",
            facts=self.facts,
            rules=self.rules,
            meta=PackMeta(
                description=f"Auto-scanned from your machine on {datetime.now().strftime('%Y-%m-%d')}",
                tags=["scanned", "auto", platform.system().lower()],
            ),
        )

    # ------------------------------------------------------------------
    # Git identity
    # ------------------------------------------------------------------
    def _scan_git_identity(self):
        """Extract name and email from git config."""
        name = _run_cmd("git config --global user.name")
        email = _run_cmd("git config --global user.email")

        content = f"{name or ''}|{email or ''}"
        if not self._should_scan("git-identity", content):
            return

        if name:
            self.facts.append(Fact(
                key="identity.name", value=name,
                type=FactType.IDENTITY, confidence=Confidence.HIGH,
                source="git-config",
            ))
        if email:
            self.facts.append(Fact(
                key="identity.email", value=email,
                type=FactType.IDENTITY, confidence=Confidence.HIGH,
                source="git-config",
            ))

    # ------------------------------------------------------------------
    # Installed tools
    # ------------------------------------------------------------------
    def _scan_installed_tools(self):
        """Detect installed editors, runtimes, and tools."""
        # Editors
        editors_found = []
        editor_checks = {
            "Cursor": ["/Applications/Cursor.app", _which("cursor")],
            "VS Code": ["/Applications/Visual Studio Code.app", _which("code")],
            "Vim": [_which("vim"), _which("nvim")],
            "Neovim": [_which("nvim")],
            "Emacs": [_which("emacs")],
            "Sublime Text": ["/Applications/Sublime Text.app"],
            "Zed": ["/Applications/Zed.app", _which("zed")],
        }
        for name, paths in editor_checks.items():
            if any(p and (Path(p).exists() if p.startswith("/") else True) for p in paths if p):
                editors_found.append(name)

        if editors_found:
            primary = editors_found[0]  # First found is likely primary
            self.facts.append(Fact(
                key="editor", value=primary,
                type=FactType.PREFERENCE, confidence=Confidence.MEDIUM,
                source="tool-scan",
            ))
            if len(editors_found) > 1:
                self.facts.append(Fact(
                    key="editors.installed", value=editors_found,
                    type=FactType.CONTEXT, confidence=Confidence.HIGH,
                    source="tool-scan",
                ))

        # Runtimes
        runtimes = {}
        runtime_checks = {
            "Node.js": "node --version",
            "Python": "python3 --version",
            "Rust": "rustc --version",
            "Go": "go version",
            "Java": "java -version",
            "Ruby": "ruby --version",
            "Deno": "deno --version",
            "Bun": "bun --version",
        }
        for name, cmd in runtime_checks.items():
            version = _run_cmd(cmd)
            if version:
                runtimes[name] = version.split("\n")[0].strip()

        if runtimes:
            self.facts.append(Fact(
                key="runtimes.installed",
                value=list(runtimes.keys()),
                type=FactType.SKILL, confidence=Confidence.HIGH,
                source="tool-scan",
            ))

        # Package managers
        pkg_managers = []
        for tool in ["npm", "yarn", "pnpm", "pip", "cargo", "brew", "go"]:
            if _which(tool):
                pkg_managers.append(tool)
        if pkg_managers:
            self.facts.append(Fact(
                key="package_managers", value=pkg_managers,
                type=FactType.CONTEXT, confidence=Confidence.HIGH,
                source="tool-scan",
            ))

        # AI tools
        ai_tools = []
        ai_checks = {
            "Claude Desktop": "/Applications/Claude.app",
            "ChatGPT Desktop": "/Applications/ChatGPT.app",
            "Cursor": "/Applications/Cursor.app",
            "GitHub Copilot": None,  # Detected via VS Code extensions
        }
        for name, path in ai_checks.items():
            if path and Path(path).exists():
                ai_tools.append(name)
        if _which("claude"):
            ai_tools.append("Claude Code")
        if _which("ollama"):
            ai_tools.append("Ollama")

        if ai_tools:
            self.facts.append(Fact(
                key="ai_tools", value=ai_tools,
                type=FactType.PREFERENCE, confidence=Confidence.HIGH,
                source="tool-scan",
            ))

    # ------------------------------------------------------------------
    # Repository scanning
    # ------------------------------------------------------------------
    def _scan_repos(self):
        """Find git repos and analyze their tech stacks."""
        repos = self._find_repos()
        if not repos:
            return

        lang_counter: Counter = Counter()
        framework_counter: Counter = Counter()
        project_names: list[str] = []

        for repo in repos[:self.max_repos]:
            analysis = self._analyze_repo(repo)
            for lang, count in analysis.get("languages", {}).items():
                lang_counter[lang] += count
            for fw in analysis.get("frameworks", []):
                framework_counter[fw] += 1
            if analysis.get("name"):
                project_names.append(analysis["name"])

        # Languages (top 5 by file count)
        if lang_counter:
            top_langs = [lang for lang, _ in lang_counter.most_common(5)]
            self.facts.append(Fact(
                key="languages.primary", value=top_langs,
                type=FactType.SKILL, confidence=Confidence.HIGH,
                source="repo-scan",
            ))

        # Frameworks (appearing in 1+ repos)
        if framework_counter:
            top_frameworks = [fw for fw, count in framework_counter.most_common(10) if count >= 1]
            if top_frameworks:
                self.facts.append(Fact(
                    key="frameworks", value=top_frameworks,
                    type=FactType.SKILL, confidence=Confidence.HIGH,
                    source="repo-scan",
                ))

        # Recent projects
        if project_names:
            self.facts.append(Fact(
                key="projects.recent", value=project_names[:8],
                type=FactType.CONTEXT, confidence=Confidence.MEDIUM,
                source="repo-scan",
            ))

    def _find_repos(self) -> list[Path]:
        """Find git repositories in scan directories."""
        repos = []
        for scan_dir in self.scan_dirs:
            base = Path(scan_dir).expanduser()
            if not base.exists():
                continue
            # Look for .git dirs up to 2 levels deep
            for depth_pattern in ["*/.git", "*/*/.git"]:
                for git_dir in base.glob(depth_pattern):
                    repo_dir = git_dir.parent
                    if not any(skip in str(repo_dir) for skip in ["node_modules", ".cache", "venv", ".venv"]):
                        repos.append(repo_dir)
        # Sort by most recently modified
        repos.sort(key=lambda r: r.stat().st_mtime, reverse=True)
        return repos

    def _analyze_repo(self, repo_path: Path) -> dict:
        """Analyze a single repository for languages and frameworks."""
        result = {"name": repo_path.name, "languages": {}, "frameworks": []}

        # Detect languages by file extension
        ext_to_lang = {
            ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
            ".js": "JavaScript", ".jsx": "JavaScript",
            ".rs": "Rust", ".go": "Go", ".java": "Java",
            ".rb": "Ruby", ".php": "PHP", ".swift": "Swift",
            ".kt": "Kotlin", ".cs": "C#", ".cpp": "C++",
            ".c": "C", ".dart": "Dart", ".lua": "Lua",
            ".zig": "Zig", ".ex": "Elixir", ".hs": "Haskell",
        }

        try:
            for f in repo_path.rglob("*"):
                if f.is_file() and not any(skip in str(f) for skip in [
                    "node_modules", ".git", "venv", ".venv", "__pycache__",
                    "dist", "build", ".next", "target",
                ]):
                    lang = ext_to_lang.get(f.suffix)
                    if lang:
                        result["languages"][lang] = result["languages"].get(lang, 0) + 1
        except PermissionError:
            pass

        # Detect frameworks from config files
        framework_files = {
            "package.json": self._detect_js_frameworks,
            "requirements.txt": self._detect_python_frameworks,
            "Pipfile": self._detect_python_frameworks_pipfile,
            "pyproject.toml": self._detect_python_frameworks_pyproject,
            "Cargo.toml": lambda p: ["Rust"],
            "go.mod": lambda p: ["Go"],
            "Gemfile": lambda p: self._detect_ruby_frameworks(p),
        }

        for filename, detector in framework_files.items():
            filepath = repo_path / filename
            if filepath.exists():
                try:
                    frameworks = detector(filepath)
                    result["frameworks"].extend(frameworks)
                except Exception:
                    pass

        return result

    def _detect_js_frameworks(self, package_json_path: Path) -> list[str]:
        """Detect JS/TS frameworks from package.json."""
        try:
            with open(package_json_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

        all_deps = {}
        all_deps.update(data.get("dependencies", {}))
        all_deps.update(data.get("devDependencies", {}))

        frameworks = []
        framework_map = {
            "next": "Next.js",
            "react": "React",
            "vue": "Vue.js",
            "nuxt": "Nuxt",
            "svelte": "Svelte",
            "@sveltejs/kit": "SvelteKit",
            "angular": "Angular",
            "@angular/core": "Angular",
            "express": "Express",
            "fastify": "Fastify",
            "nestjs": "NestJS",
            "@nestjs/core": "NestJS",
            "tailwindcss": "Tailwind CSS",
            "framer-motion": "Framer Motion",
            "prisma": "Prisma",
            "@prisma/client": "Prisma",
            "drizzle-orm": "Drizzle",
            "supabase": "Supabase",
            "@supabase/supabase-js": "Supabase",
            "firebase": "Firebase",
            "electron": "Electron",
            "tauri": "Tauri",
            "recharts": "Recharts",
            "d3": "D3.js",
            "three": "Three.js",
        }

        for dep, fw_name in framework_map.items():
            if dep in all_deps:
                frameworks.append(fw_name)

        # Detect TypeScript
        if "typescript" in all_deps or (package_json_path.parent / "tsconfig.json").exists():
            frameworks.append("TypeScript")

        return list(set(frameworks))

    def _detect_python_frameworks(self, requirements_path: Path) -> list[str]:
        """Detect Python frameworks from requirements.txt."""
        try:
            content = requirements_path.read_text().lower()
        except IOError:
            return []

        frameworks = []
        framework_map = {
            "fastapi": "FastAPI",
            "django": "Django",
            "flask": "Flask",
            "starlette": "Starlette",
            "sqlalchemy": "SQLAlchemy",
            "pandas": "pandas",
            "numpy": "numpy",
            "scipy": "scipy",
            "torch": "PyTorch",
            "tensorflow": "TensorFlow",
            "langchain": "LangChain",
            "llamaindex": "LlamaIndex",
            "supabase": "Supabase",
            "pydantic": "Pydantic",
            "celery": "Celery",
            "pytest": "pytest",
        }

        for dep, fw_name in framework_map.items():
            if dep in content:
                frameworks.append(fw_name)

        return frameworks

    def _detect_python_frameworks_pipfile(self, path: Path) -> list[str]:
        """Detect from Pipfile."""
        return self._detect_python_frameworks(path)

    def _detect_python_frameworks_pyproject(self, path: Path) -> list[str]:
        """Detect from pyproject.toml."""
        return self._detect_python_frameworks(path)

    def _detect_ruby_frameworks(self, gemfile_path: Path) -> list[str]:
        """Detect Ruby frameworks from Gemfile."""
        try:
            content = gemfile_path.read_text().lower()
        except IOError:
            return []
        frameworks = []
        if "rails" in content:
            frameworks.append("Rails")
        if "sinatra" in content:
            frameworks.append("Sinatra")
        return frameworks

    # ------------------------------------------------------------------
    # Existing rules detection
    # ------------------------------------------------------------------
    def _scan_existing_rules(self):
        """Look for existing .cursorrules, AGENTS.md, etc."""
        rules_files = [
            (".cursorrules", "cursorrules"),
            ("AGENTS.md", "agents-md"),
            (".editorconfig", "editorconfig"),
        ]

        for scan_dir in self.scan_dirs:
            base = Path(scan_dir).expanduser()
            if not base.exists():
                continue
            try:
                entries = list(base.iterdir())
            except (PermissionError, OSError):
                continue
            for repo in entries:
                if not repo.is_dir():
                    continue
                for filename, source in rules_files:
                    filepath = repo / filename
                    try:
                        if filepath.exists() and filepath.is_file():
                            cache_key = f"rules:{filepath}"
                            if not self._should_scan_file(cache_key, filepath):
                                continue
                            content = filepath.read_text()[:500]
                            self.facts.append(Fact(
                                key=f"existing_rules.{source}",
                                value=f"Found in {repo.name}: {content[:100]}...",
                                type=FactType.CONTEXT, confidence=Confidence.HIGH,
                                source=f"file-scan-{source}",
                            ))
                            break  # One per type is enough
                    except (PermissionError, OSError, IOError):
                        continue

    # ------------------------------------------------------------------
    # System info
    # ------------------------------------------------------------------
    def _scan_system_info(self):
        """Collect basic system information."""
        system = platform.system()
        machine = platform.machine()

        self.facts.append(Fact(
            key="system.os", value=f"{system} ({machine})",
            type=FactType.CONTEXT, confidence=Confidence.HIGH,
            source="system",
        ))

        shell = os.environ.get("SHELL", "")
        if shell:
            self.facts.append(Fact(
                key="system.shell", value=Path(shell).name,
                type=FactType.CONTEXT, confidence=Confidence.HIGH,
                source="system",
            ))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _default_scan_dirs() -> list[str]:
        """Default directories to scan for repos."""
        home = str(Path.home())
        candidates = [
            f"{home}/Documents",
            f"{home}/Projects",
            f"{home}/projects",
            f"{home}/Code",
            f"{home}/code",
            f"{home}/dev",
            f"{home}/Developer",
            f"{home}/repos",
            f"{home}/src",
            f"{home}/workspace",
            f"{home}/Desktop",
        ]
        return [d for d in candidates if Path(d).exists()]


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------
def _run_cmd(cmd: str) -> Optional[str]:
    """Run a shell command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            cmd.split(),
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _which(cmd: str) -> Optional[str]:
    """Check if a command exists in PATH."""
    return _run_cmd(f"which {cmd}")
