"""
aura.extractor — LLM-Powered Context Extraction

Takes raw conversation exports and uses an LLM to deeply extract
structured facts. This is the technical moat — pattern matching catches
the obvious stuff, but the LLM catches nuance:

  - "I've been burned by NoSQL before" → constraint: "Prefers relational DBs"
  - Consistently asks for short functions → style: "Prefers small functions"
  - Always corrects AI on semicolons → rule: "No semicolons in Python"

Supports: OpenAI, Groq, Ollama (local), any OpenAI-compatible API.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from aura.importers.chatgpt import _extract_user_messages, _load_from_zip
from aura.schema import ContextPack, Fact, PackMeta, Rule

EXTRACTION_SYSTEM_PROMPT = """You are an expert at analyzing conversations to extract structured facts about a person.

Given a batch of messages written by a user in AI conversations, extract factual information about them.

## Rules:
1. Only extract facts the user EXPLICITLY states or strongly implies
2. Do NOT infer personality traits or make assumptions
3. Confidence: high (explicitly stated), medium (strongly implied), low (mentioned once)
4. Categories: identity, skill, preference, style, constraint, context
5. Use dot-notation keys (e.g. "languages.primary", "style.tone")
6. Deduplicate — Python mentioned in 15 messages = ONE fact, high confidence
7. Extract behavioral rules the user consistently demonstrates

## Output strict JSON:
{
  "facts": [
    {"key": "languages.primary", "value": ["Python", "TypeScript"], "type": "skill", "confidence": "high", "evidence": "Mentioned Python in 23 messages"}
  ],
  "rules": [
    {"instruction": "Prefers functional programming patterns", "priority": 6, "evidence": "Consistently requests functional approaches"}
  ],
  "summary": "Brief 2-sentence profile of this user"
}

Output ONLY valid JSON. No markdown fences, no explanation."""


EXTRACTION_USER_TEMPLATE = """Analyze these {count} messages from a user's AI conversations.

Focus scope: {scope}

## Messages:
{messages}

Extract structured facts and rules. Strict JSON only."""


class Extractor:
    """LLM-powered context extractor."""

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url or self._default_base_url(provider)

    @staticmethod
    def _default_base_url(provider: str) -> str:
        return {
            "openai": "https://api.openai.com/v1",
            "groq": "https://api.groq.com/openai/v1",
            "ollama": "http://localhost:11434/v1",
        }.get(provider, "https://api.openai.com/v1")

    def _call_llm(self, system: str, user: str) -> str:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("Install extraction deps: pip install aura-ctx[extract]")

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
            max_tokens=4000,
        )
        return response.choices[0].message.content or ""

    def extract_from_messages(
        self,
        messages: list[str],
        scope: str = "general",
        batch_size: int = 50,
        max_batches: int = 10,
    ) -> dict:
        all_facts: list[dict] = []
        all_rules: list[dict] = []
        summaries: list[str] = []

        # Prioritize longer messages (richer identity signal)
        sorted_msgs = sorted(messages, key=len, reverse=True)
        total = min(len(sorted_msgs), batch_size * max_batches)
        selected = sorted_msgs[:total]
        batches = [selected[i:i + batch_size] for i in range(0, len(selected), batch_size)]

        for i, batch in enumerate(batches):
            formatted = "\n---\n".join(
                f"[{j+1}]: {msg[:500]}" for j, msg in enumerate(batch)
            )
            user_prompt = EXTRACTION_USER_TEMPLATE.format(
                count=len(batch), scope=scope, messages=formatted,
            )
            try:
                raw = self._call_llm(EXTRACTION_SYSTEM_PROMPT, user_prompt)
                parsed = self._parse_response(raw)
                if parsed:
                    all_facts.extend(parsed.get("facts", []))
                    all_rules.extend(parsed.get("rules", []))
                    if parsed.get("summary"):
                        summaries.append(parsed["summary"])
            except Exception as e:
                print(f"  ⚠ Batch {i+1} failed: {e}")
                continue

        merged_facts = self._merge_facts(all_facts)
        merged_rules = self._merge_rules(all_rules)

        return {
            "facts": merged_facts,
            "rules": merged_rules,
            "summary": summaries[0] if summaries else None,
            "stats": {
                "total_messages": len(messages),
                "messages_processed": total,
                "batches": len(batches),
                "facts_extracted": len(merged_facts),
                "rules_extracted": len(merged_rules),
            },
        }

    def extract_from_chatgpt_export(
        self, source: str | Path, scope: str = "general",
        pack_name: str = "extracted", **kwargs,
    ) -> ContextPack:
        source = Path(source)
        if source.suffix == ".zip":
            conversations = _load_from_zip(source)
        elif source.suffix == ".json":
            with open(source) as f:
                conversations = json.load(f)
        else:
            raise ValueError(f"Unsupported format: {source.suffix}")

        messages = _extract_user_messages(conversations)
        result = self.extract_from_messages(messages, scope=scope, **kwargs)

        facts = [Fact(
            key=f["key"], value=f["value"],
            type=f.get("type", "context"),
            confidence=f.get("confidence", "medium"),
            source="llm-extraction",
        ) for f in result["facts"]]

        rules = [Rule(
            instruction=r["instruction"],
            priority=r.get("priority", 5),
        ) for r in result["rules"]]

        stats = result["stats"]
        desc = f"LLM-extracted from {stats['total_messages']} messages ({stats['facts_extracted']} facts, {stats['rules_extracted']} rules)"
        if result.get("summary"):
            desc += f"\n{result['summary']}"

        return ContextPack(
            name=pack_name, scope=scope, facts=facts, rules=rules,
            meta=PackMeta(description=desc, tags=["extracted", "llm", scope]),
        )

    @staticmethod
    def _parse_response(raw: str) -> Optional[dict]:
        cleaned = re.sub(r'^```(?:json)?\s*', '', raw.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r'\{[\s\S]*\}', cleaned)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return None

    @staticmethod
    def _merge_facts(facts: list[dict]) -> list[dict]:
        merged: dict[str, dict] = {}
        rank = {"high": 3, "medium": 2, "low": 1}
        for fact in facts:
            key = fact.get("key", "")
            if not key:
                continue
            if key in merged:
                if rank.get(fact.get("confidence", "low"), 0) > rank.get(merged[key].get("confidence", "low"), 0):
                    merged[key] = fact
                elif isinstance(fact.get("value"), list) and isinstance(merged[key].get("value"), list):
                    existing = set(merged[key]["value"])
                    merged[key]["value"].extend(v for v in fact["value"] if v not in existing)
            else:
                merged[key] = fact
        return list(merged.values())

    @staticmethod
    def _merge_rules(rules: list[dict]) -> list[dict]:
        seen: set[str] = set()
        unique: list[dict] = []
        for rule in rules:
            normalized = re.sub(r'[^a-z0-9\s]', '', rule.get("instruction", "").lower().strip())
            if normalized not in seen:
                seen.add(normalized)
                unique.append(rule)
        return unique


# ---------------------------------------------------------------------------
# Convenience function for CLI
# ---------------------------------------------------------------------------
def extract_context(
    messages: list[str],
    pack_name: str = "extracted",
    scope: str = "general",
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    on_progress: Optional[callable] = None,
) -> ContextPack:
    """
    High-level extraction function used by the CLI.

    Tries Ollama first (local, free), falls back to env vars for cloud APIs.
    """
    import os

    # Resolve provider settings
    _base_url = base_url or os.environ.get("AURA_LLM_URL", "http://localhost:11434/v1")
    _model = model or os.environ.get("AURA_LLM_MODEL", "llama3.2")
    _api_key = os.environ.get("AURA_LLM_KEY", "ollama")  # Ollama doesn't need a key

    # Detect provider from URL
    provider = "ollama"
    if "openai.com" in _base_url:
        provider = "openai"
    elif "groq.com" in _base_url:
        provider = "groq"

    extractor = Extractor(
        provider=provider,
        model=_model,
        api_key=_api_key,
        base_url=_base_url,
    )

    # Run extraction with progress callback
    all_facts: list[dict] = []
    all_rules: list[dict] = []
    summaries: list[str] = []

    sorted_msgs = sorted(messages, key=len, reverse=True)
    batch_size = 50
    max_batches = 10
    total = min(len(sorted_msgs), batch_size * max_batches)
    selected = sorted_msgs[:total]
    batches = [selected[i:i + batch_size] for i in range(0, len(selected), batch_size)]

    for i, batch in enumerate(batches):
        formatted = "\n---\n".join(f"[{j+1}]: {msg[:500]}" for j, msg in enumerate(batch))
        user_prompt = EXTRACTION_USER_TEMPLATE.format(
            count=len(batch), scope=scope, messages=formatted,
        )
        try:
            raw = extractor._call_llm(EXTRACTION_SYSTEM_PROMPT, user_prompt)
            parsed = extractor._parse_response(raw)
            if parsed:
                all_facts.extend(parsed.get("facts", []))
                all_rules.extend(parsed.get("rules", []))
                if parsed.get("summary"):
                    summaries.append(parsed["summary"])
        except Exception as e:
            if "Connection" in str(type(e).__name__) or "connect" in str(e).lower():
                raise ConnectionError(str(e))
            if on_progress:
                on_progress(i, len(batches), len(all_facts))
            continue

        if on_progress:
            on_progress(i, len(batches), len(all_facts))

    if on_progress:
        on_progress(len(batches), len(batches), len(all_facts))

    merged_facts = Extractor._merge_facts(all_facts)
    merged_rules = Extractor._merge_rules(all_rules)

    facts = [Fact(
        key=f["key"], value=f["value"],
        type=f.get("type", "context"),
        confidence=f.get("confidence", "medium"),
        source="llm-extraction",
    ) for f in merged_facts]

    rules = [Rule(
        instruction=r["instruction"],
        priority=r.get("priority", 5),
    ) for r in merged_rules]

    desc = f"LLM-extracted from {len(messages)} messages ({len(facts)} facts, {len(rules)} rules)"
    if summaries:
        desc += f"\n{summaries[0]}"

    return ContextPack(
        name=pack_name, scope=scope, facts=facts, rules=rules,
        meta=PackMeta(description=desc, tags=["extracted", "llm", scope]),
    )
