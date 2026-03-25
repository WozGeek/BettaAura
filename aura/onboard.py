"""
aura.onboard — Interactive conversational onboarding.

Captures what machine scanning can't detect: communication style,
preferences, rules, role context, and personal identity.

5 smart questions → complete context packs.
"""

from __future__ import annotations

from aura.schema import Confidence, ContextPack, Fact, FactType, PackMeta, Rule

# ---------------------------------------------------------------------------
# Onboarding questions
# ---------------------------------------------------------------------------
QUESTIONS = [
    {
        "id": "role",
        "prompt": "What's your role? (e.g. 'Full-stack dev at Acme Corp', 'Freelance designer', 'CS student')",
        "pack": "work",
        "facts": lambda answer: [
            Fact(
                key="role",
                value=answer,
                type=FactType.IDENTITY,
                confidence=Confidence.HIGH,
                source="onboard",
            ),
        ],
    },
    {
        "id": "tone",
        "prompt": "How do you want AI to talk to you? Pick one or describe:\n  [1] Direct — no fluff, challenge me\n  [2] Friendly — supportive, encouraging\n  [3] Technical — precise, detailed\n  [4] Custom (type your own)",
        "pack": "writer",
        "handler": "_handle_tone",
    },
    {
        "id": "priorities",
        "prompt": "What are you working on right now? List your top 1-3 projects or priorities:",
        "pack": "work",
        "facts": lambda answer: [
            Fact(
                key="current_focus",
                value=answer,
                type=FactType.CONTEXT,
                confidence=Confidence.HIGH,
                source="onboard",
            ),
        ],
    },
    {
        "id": "rules",
        "prompt": "Any rules or pet peeves for AI? Things you never want to see?\n  (e.g. 'No corporate jargon', 'Always use TypeScript strict', 'No emojis')\n  Separate with commas, or type 'skip':",
        "pack": "writer",
        "handler": "_handle_rules",
    },
    {
        "id": "languages",
        "prompt": "What human languages do you work in? (e.g. 'English', 'English and French')",
        "pack": "writer",
        "facts": lambda answer: [
            Fact(
                key="languages",
                value=answer,
                type=FactType.SKILL,
                confidence=Confidence.HIGH,
                source="onboard",
            ),
        ],
    },
]


# ---------------------------------------------------------------------------
# Tone presets
# ---------------------------------------------------------------------------
TONE_PRESETS = {
    "1": {
        "tone": "Direct, no fluff, sharp analytical edge. Challenge me when my reasoning has gaps.",
        "rules": [
            Rule(
                instruction="Avoid corporate jargon, buzzwords, and empty filler phrases",
                priority=9,
            ),
            Rule(
                instruction="Lead with the conclusion, then explain the reasoning",
                priority=8,
            ),
            Rule(
                instruction="Challenge me directly when my reasoning has gaps — no sugarcoating",
                priority=9,
            ),
        ],
    },
    "2": {
        "tone": "Friendly, supportive, encouraging. Explain things clearly with patience.",
        "rules": [
            Rule(instruction="Be encouraging and supportive in tone", priority=7),
            Rule(instruction="Explain complex concepts step by step", priority=8),
            Rule(instruction="Offer alternatives when suggesting changes", priority=6),
        ],
    },
    "3": {
        "tone": "Technical, precise, detailed. Assume I know what I'm doing.",
        "rules": [
            Rule(
                instruction="Be technically precise — use correct terminology",
                priority=9,
            ),
            Rule(instruction="Skip beginner explanations unless asked", priority=8),
            Rule(
                instruction="Include edge cases and caveats in technical answers",
                priority=7,
            ),
        ],
    },
}


# ---------------------------------------------------------------------------
# Onboarding engine
# ---------------------------------------------------------------------------
class Onboarder:
    """Runs the interactive onboarding flow."""

    def __init__(self):
        self.writer_facts: list[Fact] = []
        self.writer_rules: list[Rule] = []
        self.work_facts: list[Fact] = []
        self.work_rules: list[Rule] = []

    def run(self, ask_fn=None) -> dict[str, ContextPack]:
        """
        Run the onboarding flow.

        Args:
            ask_fn: Function that takes a prompt string and returns user input.
                    Defaults to input() for CLI usage.

        Returns:
            Dict of pack_name -> ContextPack
        """
        if ask_fn is None:
            ask_fn = input

        for question in QUESTIONS:
            answer = ask_fn(f"\n  {question['prompt']}\n  → ").strip()

            if not answer or answer.lower() == "skip":
                continue

            if "handler" in question:
                handler = getattr(self, question["handler"])
                handler(answer)
            elif "facts" in question:
                facts = question["facts"](answer)
                if question["pack"] == "writer":
                    self.writer_facts.extend(facts)
                elif question["pack"] == "work":
                    self.work_facts.extend(facts)

        # Build packs
        packs = {}

        if self.writer_facts or self.writer_rules:
            packs["writer"] = ContextPack(
                name="writer",
                scope="writing",
                facts=self.writer_facts,
                rules=self.writer_rules,
                meta=PackMeta(
                    description="Writing style and communication preferences",
                    tags=["onboard", "personal"],
                ),
            )

        if self.work_facts or self.work_rules:
            packs["work"] = ContextPack(
                name="work",
                scope="work",
                facts=self.work_facts,
                rules=self.work_rules,
                meta=PackMeta(
                    description="Professional context and current priorities",
                    tags=["onboard", "personal"],
                ),
            )

        return packs

    def _handle_tone(self, answer: str):
        """Handle the tone question with presets or custom input."""
        answer = answer.strip()

        if answer in TONE_PRESETS:
            preset = TONE_PRESETS[answer]
            self.writer_facts.append(
                Fact(
                    key="tone",
                    value=preset["tone"],
                    type=FactType.STYLE,
                    confidence=Confidence.HIGH,
                    source="onboard",
                )
            )
            self.writer_rules.extend(preset["rules"])
        else:
            # Custom tone
            self.writer_facts.append(
                Fact(
                    key="tone",
                    value=answer,
                    type=FactType.STYLE,
                    confidence=Confidence.HIGH,
                    source="onboard",
                )
            )

    def _handle_rules(self, answer: str):
        """Handle the rules question — split by commas."""
        if answer.lower() == "skip":
            return

        rules = [r.strip() for r in answer.split(",") if r.strip()]
        for rule_text in rules:
            self.writer_rules.append(
                Rule(
                    instruction=rule_text,
                    priority=7,
                )
            )
