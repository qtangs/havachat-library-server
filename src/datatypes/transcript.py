from typing import List
from typing import Optional

from pydantic.v1 import BaseModel
from pydantic.v1 import Field


class TranscriptWord(BaseModel):
    """A word in a transcript with start and end time"""

    start: Optional[float] = Field(description="Start time of the word")
    end: Optional[float] = Field(description="End time of the word")
    word: str = Field(description="The word itself")
    score: Optional[float] = Field(
        description="Confidence score of the word. None if not applicable."
    )

    def to_dict(self):
        return {
            "start": self.start,
            "end": self.end,
            "word": self.word,
            "score": self.score,
        }


class TranscriptSegment(BaseModel):
    """A segment can be complete/partial sentence(s) in a transcript."""

    start: float = Field(description="Start time of the segment.")
    end: float = Field(description="End time of the segment.")
    text: str = Field(description="Text of the segment.")
    words: Optional[List[TranscriptWord]] = Field(
        description="Optional list of words in the segment. "
        "None or empty list if not applicable."
    )
    speaker: Optional[str] = Field(
        description="Optional speaker of the segment. None if not applicable."
    )

    def to_dict(self):
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "words": [word.to_dict() for word in self.words] if self.words else [],
        }


class Transcript(BaseModel):
    segments: List[TranscriptSegment]
    doc_id: Optional[str]
    index: int = 0
    is_last_transcript: bool = True
    url: Optional[str]
    title: Optional[str]
    transcriber: Optional[str]
    detected_language: Optional[str]

    def to_dict(self):
        return {"segments": [segment.to_dict() for segment in self.segments]}
