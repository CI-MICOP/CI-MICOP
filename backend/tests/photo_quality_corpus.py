"""Step 5.8.15: controlled validation corpus for the evidence photo quality
check (services/evidence_quality.py).

Images are generated with Pillow from fixed seeds: the same gradient-and-
shapes scenes as the duplication corpus, plus fine random texture so a
"sharp" image has the kind of small-scale detail real photos have. None of
it is a real accident photo. Results describe how the check behaves on
these generated images only - not an accuracy estimate for real photos.

Each case records:
  ideal_flags    - the flags a careful person would expect
  observed_flags - what flags_for(measure_image(...)) actually returned
                   when this corpus was first run (2026-10-03). Recorded
                   from a real run, not predicted;
                   test_evidence_quality.py asserts it still holds.
"""

from __future__ import annotations

import io
import random
from dataclasses import dataclass
from typing import Callable

from PIL import Image, ImageEnhance, ImageFilter

from tests.evidence_duplication_corpus import scene


def textured_scene(seed: int) -> Image.Image:
    image = scene(seed)
    rnd = random.Random(seed)
    pixels = image.load()
    for _ in range(20000):
        x, y = rnd.randrange(image.width), rnd.randrange(image.height)
        shift = rnd.randint(-40, 40)
        pixels[x, y] = tuple(max(0, min(255, c + shift)) for c in pixels[x, y])
    return image


def _jpeg(image: Image.Image, quality: int) -> Image.Image:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=quality)
    return Image.open(io.BytesIO(buffer.getvalue()))


def _blur(radius: float) -> Callable[[Image.Image], Image.Image]:
    return lambda i: i.filter(ImageFilter.GaussianBlur(radius))


def _brightness(factor: float) -> Callable[[Image.Image], Image.Image]:
    return lambda i: ImageEnhance.Brightness(i).enhance(factor)


@dataclass(frozen=True)
class QualityCase:
    case_id: str
    description: str
    seed: int
    edit: Callable[[Image.Image], Image.Image]
    ideal_flags: tuple[str, ...]
    observed_flags: tuple[str, ...]
    textured: bool = True

    def image(self) -> Image.Image:
        base = textured_scene(self.seed) if self.textured else scene(self.seed)
        return self.edit(base)


CORPUS: list[QualityCase] = [
    QualityCase("Q01", "clear photo", 301, lambda i: i, (), ()),
    QualityCase("Q02", "heavily compressed JPEG (quality 20)", 302, lambda i: _jpeg(i, 20), (), ()),
    QualityCase("Q03", "very slight blur (radius 1)", 303, _blur(1), (), ()),
    QualityCase("Q04", "blurred (radius 2)", 304, _blur(2), ("BLURRY",), ("BLURRY",)),
    QualityCase("Q05", "blurred (radius 4)", 305, _blur(4), ("BLURRY",), ("BLURRY",)),
    QualityCase("Q06", "very blurred (radius 8)", 306, _blur(8), ("BLURRY",), ("BLURRY",)),
    QualityCase("Q07", "dark (30% brightness)", 307, _brightness(0.3), ("TOO_DARK",), ("TOO_DARK", "LOW_CONTRAST")),
    QualityCase("Q08", "very dark (15% brightness)", 308, _brightness(0.15), ("TOO_DARK", "LOW_CONTRAST"), ("TOO_DARK", "LOW_CONTRAST")),
    QualityCase("Q09", "over-exposed (250% brightness)", 309, _brightness(2.5), ("TOO_BRIGHT",), ("TOO_BRIGHT",)),
    QualityCase("Q10", "washed out (20% contrast)", 310, lambda i: ImageEnhance.Contrast(i).enhance(0.2), ("LOW_CONTRAST",), ("LOW_CONTRAST",)),
    QualityCase("Q11", "small (320 x 240)", 311, lambda i: i.resize((320, 240)), ("LOW_RESOLUTION",), ("LOW_RESOLUTION",)),
    QualityCase("Q12", "tiny (160 x 120)", 312, lambda i: i.resize((160, 120)), ("LOW_RESOLUTION",), ("LOW_RESOLUTION",)),
    QualityCase("Q13", "dark and blurred", 313, lambda i: _brightness(0.3)(_blur(4)(i)), ("TOO_DARK", "BLURRY"), ("TOO_DARK", "LOW_CONTRAST", "BLURRY")),
    QualityCase("Q14", "clear but smooth, little fine detail", 314, lambda i: i, (), ("BLURRY",), textured=False),
    QualityCase("Q15", "large clear photo (1920 x 1440)", 315, lambda i: i.resize((1920, 1440), Image.LANCZOS), (), ()),
]
