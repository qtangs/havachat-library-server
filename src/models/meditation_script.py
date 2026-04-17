from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Duration
# ---------------------------------------------------------------------------

@dataclass
class MeditationDuration:
    key: str
    label: str
    target_minutes: float
    word_count: int


DURATION_REGISTRY: dict[str, MeditationDuration] = {
    "shorts": MeditationDuration(key="shorts", label="Shorts (<1 min)", target_minutes=0.5, word_count=50),
    "5min":   MeditationDuration(key="5min",   label="5 Minutes",       target_minutes=5.0,  word_count=600),
    "10min":  MeditationDuration(key="10min",  label="10 Minutes",      target_minutes=10.0, word_count=1200),
    "20min":  MeditationDuration(key="20min",  label="20 Minutes",      target_minutes=20.0, word_count=2400),
    "30min":  MeditationDuration(key="30min",  label="30 Minutes",      target_minutes=30.0, word_count=3600),
    "40min":  MeditationDuration(key="40min",  label="40 Minutes",      target_minutes=40.0, word_count=4800),
    "50min":  MeditationDuration(key="50min",  label="50 Minutes",      target_minutes=50.0, word_count=6000),
    "60min":  MeditationDuration(key="60min",  label="60 Minutes",      target_minutes=60.0, word_count=7200),
}


# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------

@dataclass
class MeditationStyle:
    key: str
    label: str
    description: str
    image_prompt_template: str


STYLE_REGISTRY: dict[str, MeditationStyle] = {
    "plum_village": MeditationStyle(
        key="plum_village",
        label="Plum Village",
        description="Mindfulness in the Thich Nhat Hanh tradition, interbeing and breath awareness",
        image_prompt_template=(
            "Misty bamboo forest at dawn, soft golden light filtering through leaves, "
            "still pond reflecting the sky, serene and peaceful, watercolor style"
        ),
    ),
    "plum_village_total_relaxation": MeditationStyle(
        key="plum_village_total_relaxation",
        label="Plum Village Total Relaxation",
        description="Deep body and mind rest",
        image_prompt_template=(
            "Hammock between blossoming cherry trees, dappled sunlight, gentle breeze, "
            "wildflower meadow in background, soft pastel tones"
        ),
    ),
    "body_scan": MeditationStyle(
        key="body_scan",
        label="Body Scan",
        description="Progressive awareness moving through each body part",
        image_prompt_template=(
            "Silhouette of a human figure lying in peaceful repose, soft warm light emanating from within, "
            "gentle gradient from golden to deep blue sky"
        ),
    ),
    "vipassana": MeditationStyle(
        key="vipassana",
        label="Vipassana",
        description="Insight meditation observing impermanence and sensation",
        image_prompt_template=(
            "Ancient stone meditation hall at sunrise, incense smoke curling upward, "
            "warm amber light, simple and austere, deeply still"
        ),
    ),
    "loving_kindness": MeditationStyle(
        key="loving_kindness",
        label="Loving-Kindness (Metta)",
        description="Radiating compassion and goodwill to all beings",
        image_prompt_template=(
            "Lotus flowers floating on a calm lake at sunset, warm rose and amber hues, "
            "concentric ripples spreading outward, soft and luminous"
        ),
    ),
    "yoga_nidra": MeditationStyle(
        key="yoga_nidra",
        label="Yoga Nidra",
        description="Yogic sleep and rotation of consciousness",
        image_prompt_template=(
            "Starlit night sky over a still ocean, Milky Way reflection in dark water, "
            "cosmic and tranquil, deep indigo and silver tones"
        ),
    ),
    "guided_imagery": MeditationStyle(
        key="guided_imagery",
        label="Guided Imagery",
        description="Vivid visualisation journeys through peaceful landscapes",
        image_prompt_template=(
            "Lush verdant valley with a winding river, snow-capped peaks in distance, "
            "wildflowers in foreground, bright and expansive, idyllic natural paradise"
        ),
    ),
    "mantra_based": MeditationStyle(
        key="mantra_based",
        label="Mantra-Based",
        description="Repetition of sacred sound or phrase for concentration",
        image_prompt_template=(
            "Tibetan singing bowls arranged on a wooden surface, warm candlelight, "
            "sacred geometry patterns, rich gold and burgundy, intimate and focused"
        ),
    ),
}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class MeditationScript(BaseModel):
    title: str = Field(..., description="Title of the meditation session")
    style_key: str = Field(..., description="Key referencing an entry in STYLE_REGISTRY")
    duration_key: str = Field(..., description="Key referencing an entry in DURATION_REGISTRY")
    word_count: int = Field(..., description="Approximate word count of the script body")
    body: str = Field(..., description="Full meditation script text, including [pause X seconds] markers")


class ScriptSegment(BaseModel):
    text: str = Field(..., description="Spoken text segment")
    pause_after_seconds: Optional[int] = Field(
        None, description="Duration of silence to insert after this segment, in seconds"
    )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ScriptGenerationError(Exception):
    """Raised when LLM script generation fails after all retries."""
    pass


class ScriptParseError(Exception):
    """Raised when a generated script body cannot be parsed."""
    pass


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_PAUSE_PATTERN = re.compile(r'\[pause (\d+) seconds?\]')


class MeditationScriptParser:
    @classmethod
    def parse(cls, body: str) -> list[ScriptSegment]:
        """Parse a meditation script body into a list of ScriptSegments.

        Splits on ``[pause N seconds]`` markers. Each text chunk before a
        marker becomes a segment whose ``pause_after_seconds`` is set to N.
        The final chunk (after the last marker, or the whole body if there are
        no markers) gets ``pause_after_seconds=None``.

        Raises:
            ScriptParseError: If any pause value is not a positive integer.
        """
        parts = _PAUSE_PATTERN.split(body)
        # _PAUSE_PATTERN has one capture group, so split returns:
        #   [text0, pause1, text1, pause2, text2, ...]
        # i.e. odd indices are pause values, even indices are text chunks.

        segments: list[ScriptSegment] = []
        num_parts = len(parts)

        i = 0
        while i < num_parts:
            raw_text = parts[i]
            text = raw_text.strip()

            is_last_chunk = (i + 1 >= num_parts)

            if is_last_chunk:
                # Only emit the final chunk if it has content (avoids empty segment
                # when the script body ends with a pause marker)
                if text:
                    segments.append(ScriptSegment(text=text, pause_after_seconds=None))
                break

            # There is a following pause value at parts[i + 1]
            pause_str = parts[i + 1]
            pause_value = int(pause_str)

            if pause_value <= 0:
                raise ScriptParseError(
                    f"Pause value must be a positive integer, got {pause_value}"
                )

            if text:  # skip empty intermediate segments
                segments.append(ScriptSegment(text=text, pause_after_seconds=pause_value))
            # If text is empty we still consumed the pause; move on.

            i += 2  # advance past (text_chunk, pause_value) pair

        return segments
