from dataclasses import dataclass
from typing import Optional

from .utils import coerce_float_optional, coerce_int


@dataclass
class NnsEvent:
    section: str
    bar: int
    beat: float
    number: str
    quality: str
    rhythm: str
    repeat: str
    time_signature: str
    audio_start: Optional[float]
    audio_end: Optional[float]

    def to_dict(self) -> dict:
        return {
            "section": self.section,
            "bar": self.bar,
            "beat": self.beat,
            "number": self.number,
            "quality": self.quality,
            "rhythm": self.rhythm,
            "repeat": self.repeat,
            "time_signature": self.time_signature,
            "audio_start": self.audio_start,
            "audio_end": self.audio_end,
        }

    @classmethod
    def from_dict(cls, row: dict) -> "NnsEvent":
        start = row.get("audio_start", row.get("start"))
        end = row.get("audio_end", row.get("end"))
        return cls(
            section=str(row.get("section", "VERSE") or "VERSE"),
            bar=coerce_int(row.get("bar"), 1),
            beat=float(row.get("beat", 1) or 1),
            number=str(row.get("number", "1") or "1"),
            quality=str(row.get("quality", "") or ""),
            rhythm=str(row.get("rhythm", "") or ""),
            repeat=str(row.get("repeat", "") or ""),
            time_signature=str(row.get("time_signature", "4/4") or "4/4"),
            audio_start=coerce_float_optional(start),
            audio_end=coerce_float_optional(end),
        )
