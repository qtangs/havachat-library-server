from __future__ import annotations

import json
from typing import Literal, Optional

import anthropic
import openai
from pydantic import BaseModel, Field

from models.meditation_script import (
    DURATION_REGISTRY,
    STYLE_REGISTRY,
    MeditationDuration,
    MeditationScript,
    MeditationStyle,
    ScriptGenerationError,
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class MeditationScriptGeneratorConfig(BaseModel):
    llm_backend: Literal["claude", "gpt4o"] = Field(default="claude", description="LLM backend to use")
    claude_api_key: Optional[str] = Field(None, description="Anthropic API key")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    max_retries: int = Field(default=3, description="Maximum generation retries on validation failure")


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(style: MeditationStyle, duration: MeditationDuration) -> str:
    word_count_min = int(duration.word_count * 0.9)
    word_count_max = int(duration.word_count * 1.1)

    # Style-specific instructions
    style_specific = ""
    if style.key == "plum_village":
        style_specific = (
            "- Begin with a bell invitation (e.g., 'I invite the bell...') to open the session.\n"
            "- Weave in breath awareness throughout, gently returning attention to the in-breath and out-breath.\n"
            "- Use interbeing language — the interconnection of all things, touching the earth, the sky, our ancestors.\n"
        )
    elif style.key == "yoga_nidra":
        style_specific = (
            "- Include a full body-part rotation of consciousness section: systematically move awareness through "
            "each part of the body (right thumb, index finger, middle finger, ring finger, little finger, palm, "
            "back of hand, wrist, forearm, elbow, upper arm, shoulder, armpit, right side of chest, right side of "
            "waist, right hip, right thigh, kneecap, calf, ankle, heel, sole, right big toe, second toe, third toe, "
            "fourth toe, fifth toe — then mirror on the left side, then the back, then the face and head).\n"
            "- Keep the rotation instructions calm, slow, and precise.\n"
        )
    elif style.key == "loving_kindness":
        style_specific = (
            "- Include traditional metta phrases, adapted naturally into the script, for example:\n"
            "  'May you be happy. May you be healthy. May you be safe. May you live with ease.'\n"
            "- Radiate loving-kindness first to yourself, then to a loved one, then to a neutral person, "
            "then to a difficult person, then to all beings everywhere.\n"
        )
    elif style.key == "body_scan":
        style_specific = (
            "- Begin either at the feet (moving upward) or at the crown of the head (moving downward) — "
            "choose one direction and move systematically through every region of the body.\n"
            "- Spend proportional time at each body region; do not skip areas.\n"
        )
    else:
        style_specific = (
            f"- Follow the style description closely: {style.description}\n"
        )

    prompt = f"""You are an expert meditation guide specialising in the {style.label} tradition.

Your task is to write a complete, spoken meditation script with the following specifications:

**Style:** {style.label}
{style.description}

**Duration:** {duration.label} ({duration.target_minutes} minutes)
**Target word count:** {duration.word_count} words (acceptable range: {word_count_min}–{word_count_max} words)
  - Word count applies to spoken words only; do NOT count [pause X seconds] markers in the word count.

---

## Silence marker format

Insert silence markers in this exact format throughout the script:
  [pause X seconds]
where X is a positive integer between 2 and 30 (inclusive).

Requirements:
- Include **at least 3** pause markers.
- Place pauses at natural breathing or transition points.
- Vary pause lengths to suit the moment (short pauses 2–5 s for breath, longer 10–30 s for deep silence).

---

## Style-specific instructions

{style_specific}

---

## Output format

You MUST call the `submit_script` tool with a JSON object matching this schema exactly:

```json
{{
  "title": "string — a poetic title for this session",
  "style_key": "{style.key}",
  "duration_key": "{duration.key}",
  "word_count": <integer — approximate spoken word count, NOT counting pause markers>,
  "body": "string — the full meditation script text with [pause X seconds] markers embedded inline"
}}
```

Do not include any commentary outside the tool call. Write the full script now.
"""
    return prompt


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class MeditationScriptGenerator:
    def __init__(self, config: MeditationScriptGeneratorConfig) -> None:
        self.config = config

    def _call_claude(self, prompt: str) -> dict:
        """Call Anthropic API using tool-use JSON enforcement."""
        client = anthropic.Anthropic(api_key=self.config.claude_api_key)
        tools = [{
            "name": "submit_script",
            "description": "Submit the generated meditation script",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "style_key": {"type": "string"},
                    "duration_key": {"type": "string"},
                    "word_count": {"type": "integer"},
                    "body": {"type": "string"},
                },
                "required": ["title", "style_key", "duration_key", "word_count", "body"],
            }
        }]
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            tools=tools,
            tool_choice={"type": "any"},
            messages=[{"role": "user", "content": prompt}],
        )
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_script":
                return block.input
        raise ScriptGenerationError("Claude did not call the submit_script tool")

    def _call_gpt4o(self, prompt: str) -> dict:
        """Call OpenAI API using response_format json_object."""
        client = openai.OpenAI(api_key=self.config.openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You output only valid JSON matching the provided schema."},
                {"role": "user", "content": prompt},
            ],
        )
        return json.loads(response.choices[0].message.content)

    def _parse_and_validate(self, raw: dict, style_key: str, duration_key: str) -> MeditationScript:
        """Construct and validate MeditationScript from raw LLM dict."""
        # Override the keys to ensure they match what was requested
        raw["style_key"] = style_key
        raw["duration_key"] = duration_key
        return MeditationScript(**raw)

    async def generate(self, style_key: str, duration_key: str) -> MeditationScript:
        """Generate a meditation script with retry logic."""
        if style_key not in STYLE_REGISTRY:
            raise ValueError(f"Unknown style_key: {style_key!r}. Available: {list(STYLE_REGISTRY)}")
        if duration_key not in DURATION_REGISTRY:
            raise ValueError(f"Unknown duration_key: {duration_key!r}. Available: {list(DURATION_REGISTRY)}")

        style = STYLE_REGISTRY[style_key]
        duration = DURATION_REGISTRY[duration_key]
        prompt = _build_prompt(style, duration)

        last_exc: Exception = ScriptGenerationError("No attempts made")
        for attempt in range(1, self.config.max_retries + 1):
            try:
                if self.config.llm_backend == "claude":
                    raw = self._call_claude(prompt)
                else:
                    raw = self._call_gpt4o(prompt)
                return self._parse_and_validate(raw, style_key, duration_key)
            except Exception as exc:
                last_exc = exc
        raise ScriptGenerationError(
            f"Script generation failed after {self.config.max_retries} attempts: {last_exc}"
        ) from last_exc
