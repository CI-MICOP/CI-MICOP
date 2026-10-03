"""Step 5.8.14: controlled validation corpus for the evidence duplication
check (services/evidence_duplication.py).

Every image here is generated with Pillow from a fixed random seed (a
gradient background with blurred coloured shapes). None of it is a real
accident photo, and none comes from the synthetic research dataset (which
holds only evidence metadata, no image files). Results describe how the
check behaves on these generated images only - not an accuracy estimate
for real claim photos.

Each case records:
  should_match - True if a careful person would call the second image a
                 copy (original or edited) of the first
  observed     - what compare_fingerprints() actually returned when this
                 corpus was first run (2026-10-03): "EXACT", "NEAR" or
                 None. Recorded from a real run, not predicted;
                 test_evidence_duplication.py asserts it still holds.
"""

from __future__ import annotations

import io
import random
from dataclasses import dataclass
from typing import Callable

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


def scene(seed: int, width: int = 640, height: int = 480) -> Image.Image:
    rnd = random.Random(seed)
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    top = [rnd.randint(0, 255) for _ in range(3)]
    bottom = [rnd.randint(0, 255) for _ in range(3)]
    for y in range(height):
        t = y / height
        draw.line([(0, y), (width, y)], fill=tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)))
    for _ in range(rnd.randint(6, 12)):
        x0, y0 = rnd.randint(0, width - 50), rnd.randint(0, height - 50)
        x1, y1 = x0 + rnd.randint(40, 260), y0 + rnd.randint(40, 200)
        colour = tuple(rnd.randint(0, 255) for _ in range(3))
        (draw.ellipse if rnd.random() < 0.5 else draw.rectangle)([x0, y0, x1, y1], fill=colour)
    return image.filter(ImageFilter.GaussianBlur(1))


def jpeg_bytes(image: Image.Image, quality: int = 90) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=quality)
    return buffer.getvalue()


def _crop(image: Image.Image, fraction: float) -> Image.Image:
    w, h = image.size
    dx, dy = int(w * fraction), int(h * fraction)
    return image.crop((dx, dy, w - dx, h - dy))


def _reencode(quality: int) -> Callable[[Image.Image], bytes]:
    return lambda image: jpeg_bytes(image, quality)


def _edit(fn: Callable[[Image.Image], Image.Image]) -> Callable[[Image.Image], bytes]:
    return lambda image: jpeg_bytes(fn(image))


@dataclass(frozen=True)
class DuplicationCase:
    case_id: str
    description: str
    seed_a: int
    seed_b: int | None  # None -> derive image B from image A via `make_b`
    make_b: Callable[[Image.Image], bytes] | None
    should_match: bool
    observed: str | None

    def image_bytes(self) -> tuple[bytes, bytes]:
        original = scene(self.seed_a)
        a = jpeg_bytes(original)
        if self.seed_b is not None:
            return a, jpeg_bytes(scene(self.seed_b))
        if self.make_b is None:  # identical file
            return a, a
        return a, self.make_b(original)


CORPUS: list[DuplicationCase] = [
    DuplicationCase("D01", "identical file", 101, None, None, should_match=True, observed="EXACT"),
    DuplicationCase("D02", "resized to 50%", 102, None, _edit(lambda i: i.resize((i.width // 2, i.height // 2))), True, "NEAR"),
    DuplicationCase("D03", "re-saved as JPEG quality 60", 103, None, _reencode(60), True, "NEAR"),
    DuplicationCase("D04", "re-saved as JPEG quality 30", 104, None, _reencode(30), True, "NEAR"),
    DuplicationCase("D05", "brightened 15%", 105, None, _edit(lambda i: ImageEnhance.Brightness(i).enhance(1.15)), True, "NEAR"),
    DuplicationCase("D06", "darkened 25%", 106, None, _edit(lambda i: ImageEnhance.Brightness(i).enhance(0.75)), True, "NEAR"),
    DuplicationCase("D07", "converted to greyscale", 107, None, _edit(lambda i: i.convert("L").convert("RGB")), True, "NEAR"),
    DuplicationCase("D08", "edges cropped 3%", 108, None, _edit(lambda i: _crop(i, 0.03)), True, None),
    DuplicationCase("D09", "edges cropped 10%", 109, None, _edit(lambda i: _crop(i, 0.10)), True, None),
    DuplicationCase("D10", "edges cropped 20%", 110, None, _edit(lambda i: _crop(i, 0.20)), True, None),
    DuplicationCase("D11", "mirrored left-right", 111, None, _edit(lambda i: i.transpose(Image.FLIP_LEFT_RIGHT)), True, None),
    DuplicationCase("D12", "rotated 90 degrees", 112, None, _edit(lambda i: i.rotate(90, expand=True)), True, None),
    DuplicationCase("D13", "rotated 5 degrees", 113, None, _edit(lambda i: i.rotate(5, fillcolor=(0, 0, 0))), True, None),
    DuplicationCase("D14", "different image", 114, 214, None, False, None),
    DuplicationCase("D15", "different image", 115, 215, None, False, None),
    DuplicationCase("D16", "different image", 116, 216, None, False, None),
    DuplicationCase("D17", "different image", 117, 217, None, False, None),
    DuplicationCase("D18", "different image", 118, 218, None, False, None),
]
