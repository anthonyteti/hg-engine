"""Deterministic Stage 6A direction-board generator.

The boards are presentation planning evidence. They use only project-owned
geometry, labels, and colors; no retail artwork or external image service is
required.  The canonical design input is presentation/stage6/directions.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "presentation/stage6/directions.json"
DEFAULT_OUTPUT = ROOT / "docs/stage6/boards"
FONT_REGULAR = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    if not path.exists():
        raise FileNotFoundError(f"deterministic board font missing: {path}")
    return ImageFont.truetype(str(path), size=size)


def _color(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"expected RGB hex color, got {value!r}")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def _mix(left: tuple[int, int, int], right: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(round(a * (1.0 - amount) + b * amount) for a, b in zip(left, right))


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, *, size: int, fill: tuple[int, int, int], bold: bool = False) -> None:
    draw.text(xy, value, font=_font(size, bold), fill=fill)


def _rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill: tuple[int, int, int], outline: tuple[int, int, int] | None = None, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _screen_frame(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], ink: tuple[int, int, int], paper: tuple[int, int, int]) -> None:
    _rounded(draw, box, 12, ink)
    x0, y0, x1, y1 = box
    draw.rectangle((x0 + 8, y0 + 8, x1 - 8, y1 - 8), fill=paper)


def _battle_mock(draw: ImageDraw.ImageDraw, origin: tuple[int, int], scale: int, colors: dict[str, tuple[int, int, int]]) -> None:
    x, y = origin
    w, h = 256 * scale, 192 * scale
    _screen_frame(draw, (x, y, x + w, y + h), colors["ink"], colors["paper"])
    left, top = x + 8 * scale, y + 8 * scale
    right, bottom = x + w - 8 * scale, y + h - 8 * scale
    draw.rectangle((left, top, right, top + 99 * scale), fill=_mix(colors["sea"], colors["paper"], 0.72))
    draw.polygon(
        [(left, top + 86 * scale), (left + 55 * scale, top + 63 * scale), (left + 118 * scale, top + 82 * scale), (right, top + 54 * scale), (right, top + 100 * scale), (left, top + 100 * scale)],
        fill=_mix(colors["pine"], colors["paper"], 0.5),
    )
    # Abstract monster silhouettes preserve copyright hygiene while exposing clear zones.
    draw.ellipse((left + 24 * scale, top + 51 * scale, left + 80 * scale, top + 105 * scale), fill=colors["pine"], outline=colors["ink"], width=scale)
    draw.polygon([(left + 38 * scale, top + 55 * scale), (left + 50 * scale, top + 34 * scale), (left + 59 * scale, top + 57 * scale)], fill=colors["pine"])
    draw.ellipse((right - 75 * scale, top + 16 * scale, right - 34 * scale, top + 58 * scale), fill=colors["terracotta"], outline=colors["ink"], width=scale)
    # HUD cards.
    _rounded(draw, (left + 9 * scale, top + 8 * scale, left + 105 * scale, top + 38 * scale), 5 * scale, colors["paper"], colors["ink"], scale)
    _rounded(draw, (right - 111 * scale, top + 68 * scale, right - 8 * scale, top + 99 * scale), 5 * scale, colors["paper"], colors["ink"], scale)
    draw.rectangle((left + 22 * scale, top + 28 * scale, left + 94 * scale, top + 33 * scale), fill=colors["sea"])
    draw.rectangle((right - 98 * scale, top + 89 * scale, right - 19 * scale, top + 94 * scale), fill=colors["pine"])
    # Command rail and touch buttons.
    draw.rectangle((left, top + 105 * scale, right, bottom), fill=colors["ink"])
    _rounded(draw, (left + 8 * scale, top + 113 * scale, left + 126 * scale, bottom - 8 * scale), 6 * scale, colors["paper"])
    _rounded(draw, (left + 132 * scale, top + 113 * scale, right - 8 * scale, bottom - 8 * scale), 6 * scale, colors["terracotta"], colors["sun"], 2 * scale)
    _text(draw, (left + 18 * scale, top + 120 * scale), "BATTLE", size=7 * scale, fill=colors["shadow"], bold=True)
    _text(draw, (left + 143 * scale, top + 126 * scale), "FIGHT", size=12 * scale, fill=colors["paper"], bold=True)


def _party_mock(draw: ImageDraw.ImageDraw, origin: tuple[int, int], scale: int, colors: dict[str, tuple[int, int, int]]) -> None:
    x, y = origin
    w, h = 256 * scale, 192 * scale
    _screen_frame(draw, (x, y, x + w, y + h), colors["ink"], colors["paper"])
    left, top = x + 8 * scale, y + 8 * scale
    right = x + w - 8 * scale
    draw.rectangle((left, top, right, top + 23 * scale), fill=colors["ink"])
    _text(draw, (left + 9 * scale, top + 5 * scale), "FIELD TEAM", size=9 * scale, fill=colors["paper"], bold=True)
    for index in range(6):
        col, row = index % 2, index // 2
        sx = left + (8 + col * 116) * scale
        sy = top + (32 + row * 47) * scale
        selected = index == 0
        fill = colors["terracotta"] if selected else _mix(colors["limestone"], colors["paper"], 0.45)
        outline = colors["sun"] if selected else colors["shadow"]
        _rounded(draw, (sx, sy, sx + 108 * scale, sy + 39 * scale), 5 * scale, fill, outline, 2 * scale if selected else scale)
        draw.ellipse((sx + 6 * scale, sy + 6 * scale, sx + 32 * scale, sy + 32 * scale), fill=colors["sea"] if index % 2 else colors["pine"], outline=colors["ink"], width=scale)
        draw.rectangle((sx + 39 * scale, sy + 25 * scale, sx + 98 * scale, sy + 30 * scale), fill=colors["paper"])
        draw.rectangle((sx + 39 * scale, sy + 25 * scale, sx + (84 - index * 4) * scale, sy + 30 * scale), fill=colors["pine"])
    _text(draw, (left + 10 * scale, top + 174 * scale), "A  SUMMARY", size=7 * scale, fill=colors["ink"], bold=True)


def _dex_mock(draw: ImageDraw.ImageDraw, origin: tuple[int, int], scale: int, colors: dict[str, tuple[int, int, int]]) -> None:
    x, y = origin
    w, h = 256 * scale, 192 * scale
    _screen_frame(draw, (x, y, x + w, y + h), colors["ink"], colors["paper"])
    left, top = x + 8 * scale, y + 8 * scale
    right = x + w - 8 * scale
    draw.rectangle((left, top, left + 67 * scale, y + h - 8 * scale), fill=colors["ink"])
    _text(draw, (left + 8 * scale, top + 8 * scale), "DEX", size=12 * scale, fill=colors["paper"], bold=True)
    for index in range(5):
        yy = top + (35 + index * 25) * scale
        fill = colors["terracotta"] if index == 2 else _mix(colors["shadow"], colors["ink"], 0.2)
        _rounded(draw, (left + 5 * scale, yy, left + 61 * scale, yy + 19 * scale), 3 * scale, fill)
        _text(draw, (left + 11 * scale, yy + 4 * scale), f"{100 + index:04d}", size=7 * scale, fill=colors["paper"], bold=index == 2)
    draw.ellipse((left + 89 * scale, top + 27 * scale, left + 162 * scale, top + 101 * scale), fill=colors["sea"], outline=colors["ink"], width=2 * scale)
    _text(draw, (left + 88 * scale, top + 112 * scale), "COASTAL POKEMON", size=7 * scale, fill=colors["terracotta"], bold=True)
    for row in range(3):
        draw.rectangle((left + 87 * scale, top + (132 + row * 11) * scale, right - 10 * scale, top + (137 + row * 11) * scale), fill=colors["limestone"])


def _world_mock(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], colors: dict[str, tuple[int, int, int]]) -> None:
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=_mix(colors["sea"], colors["paper"], 0.65))
    horizon = y0 + (y1 - y0) * 43 // 100
    draw.polygon([(x0, horizon), (x0 + 120, horizon - 80), (x0 + 250, horizon - 20), (x0 + 390, horizon - 125), (x0 + 535, horizon - 10), (x1, horizon - 70), (x1, y1), (x0, y1)], fill=_mix(colors["limestone"], colors["shadow"], 0.18))
    draw.polygon([(x0, horizon + 52), (x0 + 210, horizon + 19), (x0 + 430, horizon + 64), (x1, horizon + 14), (x1, y1), (x0, y1)], fill=colors["sea"])
    draw.polygon([(x0, horizon + 100), (x0 + 280, horizon + 42), (x0 + 565, horizon + 91), (x1, horizon + 50), (x1, y1), (x0, y1)], fill=colors["pine"])
    # Modular limestone/roof building vocabulary.
    for bx, by, bw, bh in ((x0 + 95, horizon - 5, 120, 88), (x0 + 238, horizon + 13, 92, 69), (x0 + 555, horizon - 10, 143, 98)):
        draw.rectangle((bx, by, bx + bw, by + bh), fill=colors["paper"], outline=colors["ink"], width=2)
        draw.polygon([(bx - 8, by), (bx + bw // 2, by - 39), (bx + bw + 8, by), (bx + bw, by + 10), (bx, by + 10)], fill=colors["terracotta"], outline=colors["ink"])
        draw.rectangle((bx + bw // 2 - 10, by + bh - 35, bx + bw // 2 + 10, by + bh), fill=colors["shadow"])
        draw.rectangle((bx + 14, by + 22, bx + 34, by + 40), fill=colors["sea"])
    # Vegetation silhouettes and a path establish regional density/negative space.
    for tx, ty, height in ((x0 + 35, horizon + 66, 75), (x0 + 370, horizon + 65, 97), (x0 + 475, horizon + 77, 64), (x0 + 745, horizon + 67, 89)):
        draw.rectangle((tx - 3, ty, tx + 3, ty + 31), fill=colors["shadow"])
        draw.polygon([(tx, ty - height), (tx - 18, ty + 8), (tx + 18, ty + 8)], fill=colors["pine"], outline=colors["ink"])
    draw.polygon([(x0 + 300, y1), (x0 + 385, horizon + 65), (x0 + 440, horizon + 65), (x0 + 535, y1)], fill=colors["limestone"])
    draw.line((x0 + 300, y1, x0 + 385, horizon + 65), fill=colors["paper"], width=3)
    draw.rectangle(box, outline=colors["ink"], width=4)


def _wrap(draw: ImageDraw.ImageDraw, text: str, width: int, font: ImageFont.FreeTypeFont) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def weighted_score(source: dict[str, Any], candidate: dict[str, Any]) -> float:
    criteria = source["criteria"]
    scores = candidate["scores"]
    if len(criteria) != len(scores):
        raise ValueError(f"{candidate['id']} has {len(scores)} scores for {len(criteria)} criteria")
    if any(not isinstance(score, int) or not 1 <= score <= 10 for score in scores):
        raise ValueError(f"{candidate['id']} scores must be integers from 1 through 10")
    total_weight = sum(row["weight"] for row in criteria)
    return round(sum(row["weight"] * score for row, score in zip(criteria, scores)) / total_weight, 3)


def validate(source: dict[str, Any]) -> None:
    if source.get("schema_version") != 1:
        raise ValueError("unsupported direction schema")
    if source.get("native_screen") != [256, 192]:
        raise ValueError("Stage 6 target must remain native DS 256x192")
    candidates = source.get("candidates", [])
    if len(candidates) < 3:
        raise ValueError("Stage 6A requires at least three direction candidates")
    ids = [candidate["id"] for candidate in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate IDs must be unique")
    selected = source["selected"]
    if selected["id"] not in ids or selected["primary_parent"] not in ids:
        raise ValueError("selected direction and primary parent must reference candidates")
    for candidate in candidates:
        weighted_score(source, candidate)
        required_colors = {"ink", "paper", "limestone", "terracotta", "sea", "pine", "sun", "shadow"}
        if set(candidate["palette"]) != required_colors:
            raise ValueError(f"{candidate['id']} palette must define {sorted(required_colors)}")
        for value in candidate["palette"].values():
            _color(value)
    winner = max(candidates, key=lambda candidate: weighted_score(source, candidate))["id"]
    if winner != selected["id"]:
        raise ValueError(f"selected direction {selected['id']} is not matrix leader {winner}")


def render_board(source: dict[str, Any], candidate: dict[str, Any], output: Path) -> None:
    colors = {key: _color(value) for key, value in candidate["palette"].items()}
    canvas = Image.new("RGB", (1600, 1120), colors["paper"])
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 1600, 156), fill=colors["ink"])
    draw.rectangle((0, 146, 1600, 156), fill=colors["terracotta"])
    _text(draw, (62, 36), candidate["name"].upper(), size=45, fill=colors["paper"], bold=True)
    _text(draw, (65, 99), candidate["tagline"], size=22, fill=colors["limestone"])
    score = weighted_score(source, candidate)
    _rounded(draw, (1355, 42, 1537, 119), 18, colors["terracotta"], colors["sun"], 3)
    _text(draw, (1386, 57), f"{score:.2f}", size=34, fill=colors["paper"], bold=True)
    _text(draw, (1386, 95), "WEIGHTED", size=11, fill=colors["paper"], bold=True)

    # Three native-resolution UI views, displayed at 2x.
    _text(draw, (62, 184), "NATIVE DS UI STUDIES  •  256 × 192", size=19, fill=colors["ink"], bold=True)
    _battle_mock(draw, (62, 224), 2, colors)
    _party_mock(draw, (544, 224), 2, colors)
    _dex_mock(draw, (1026, 224), 2, colors)

    _text(draw, (62, 640), "REGIONAL WORLD LANGUAGE", size=19, fill=colors["ink"], bold=True)
    _world_mock(draw, (62, 679, 1000, 1039), colors)
    _text(draw, (1036, 641), "SYSTEM NOTES", size=19, fill=colors["ink"], bold=True)
    note_font = _font(17)
    label_font = _font(13, True)
    note_y = 685
    for label, value in (("UI", candidate["ui_language"]), ("WORLD", candidate["world_language"]), ("TYPE", candidate["typography"])):
        draw.text((1038, note_y), label, font=label_font, fill=colors["terracotta"])
        note_y += 23
        for line in _wrap(draw, value, 480, note_font):
            draw.text((1038, note_y), line, font=note_font, fill=colors["ink"])
            note_y += 24
        note_y += 16
    _text(draw, (1038, 984), "PALETTE", size=13, fill=colors["terracotta"], bold=True)
    for index, (name, color) in enumerate(colors.items()):
        px = 1038 + (index % 4) * 120
        py = 1005 + (index // 4) * 55
        draw.rectangle((px, py, px + 102, py + 28), fill=color, outline=colors["ink"], width=1)
        _text(draw, (px, py + 31), name.upper(), size=9, fill=colors["ink"], bold=True)

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=False, compress_level=9)


def render_matrix(source: dict[str, Any]) -> str:
    candidates = source["candidates"]
    lines = [
        "# Stage 6A Weighted Direction Matrix",
        "",
        "Weights intentionally favor Pokemon authenticity, native-resolution readability, DS feasibility, UI/environment scalability, and long-term suitability.",
        "",
        "| Criterion | Weight | " + " | ".join(candidate["name"] for candidate in candidates) + " |",
        "|---|---:|" + "---:|" * len(candidates),
    ]
    for index, criterion in enumerate(source["criteria"]):
        lines.append(
            f"| {criterion['label']} | {criterion['weight']} | "
            + " | ".join(str(candidate["scores"][index]) for candidate in candidates)
            + " |"
        )
    lines.extend(
        [
            "| **Weighted mean** | — | "
            + " | ".join(f"**{weighted_score(source, candidate):.3f}**" for candidate in candidates)
            + " |",
            "",
            f"Selected: **{next(candidate['name'] for candidate in candidates if candidate['id'] == source['selected']['id'])}**.",
            "",
            "The scores are comparative design judgments, not runtime measurements. Technical constraints and actual implementation evidence may refine details without silently changing the dominant direction.",
            "",
        ]
    )
    return "\n".join(lines)


def build(source_path: Path = DEFAULT_SOURCE, output_dir: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    validate(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    boards = []
    for candidate in source["candidates"]:
        output = output_dir / f"{candidate['id']}.png"
        render_board(source, candidate, output)
        try:
            manifest_path = output.relative_to(ROOT).as_posix()
        except ValueError:
            manifest_path = output.name
        boards.append(
            {
                "candidate": candidate["id"],
                "weighted_score": weighted_score(source, candidate),
                "path": manifest_path,
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            }
        )
    result = {
        "schema_version": 1,
        "source": source_path.relative_to(ROOT).as_posix(),
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "selected": source["selected"]["id"],
        "boards": boards,
    }
    (output_dir / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (output_dir / "decision_matrix.md").write_text(render_matrix(source), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build(args.source.resolve(), args.output.resolve()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
