"""Compare AE's (A) and py_aep's (C) renders of every render-matrix label.

Usage:
    uv run python scripts/render_matrix/compare.py DIR [label ...]

Pixels differing by at most 1 are AE's 8-bit dither noise (two AE imports of
the same frames differ that much); audio must be sample-identical.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from imaging import aiff_samples, tiff_pixels  # noqa: E402


def _log(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    status: dict[str, str] = {}
    attrs: dict[str, str] = {}
    if not path.exists():
        return status, attrs
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^(START|OK|SKIPCRASH|NOITEM|ERR) (\S+)(.*)", line)
        if m:
            status[m.group(2)] = m.group(1) + m.group(3)
        m = re.match(r"^ATTR (\S+) \| (.*)", line)
        if m:
            attrs[m.group(1)] = m.group(2)
    return status, attrs


def _pixel_verdict(a_frames: list[Path], c_frames: list[Path]) -> str:
    if len(a_frames) != len(c_frames):
        return f"FRAMES {len(a_frames)} vs {len(c_frames)}"
    worst_n, worst_max, total = 0, 0, 0
    for fa, fc in zip(a_frames, c_frames):
        wa, ha, pa = tiff_pixels(fa)
        wc, hc, pc = tiff_pixels(fc)
        if (wa, ha) != (wc, hc):
            return f"SIZE {wa}x{ha} vs {wc}x{hc}"
        diffs = [abs(x - y) for x, y in zip(pa, pc) if x != y]
        mx = max(diffs, default=0)
        if (mx, len(diffs)) > (worst_max, worst_n):
            worst_n, worst_max, total = len(diffs), mx, len(pa)
    if worst_max == 0:
        return "pixels identical"
    if worst_max == 1:
        return "pixels match (dither)"
    alpha = ""
    pa, pc = tiff_pixels(a_frames[0])[2], tiff_pixels(c_frames[0])[2]
    ma, mc = sum(pa[3::4]) / (len(pa) // 4), sum(pc[3::4]) / (len(pc) // 4)
    if abs(ma - mc) > 1:
        alpha = f", mean alpha {ma:.1f} vs {mc:.1f}"
    return f"PIXELS DIFF {worst_n}/{total} max {worst_max}{alpha}"


def main(out: Path, only: list[str]) -> None:
    render = out / "render"
    sa, aa = _log(out / "render_A.jsx_log.txt")
    sc, ac = _log(out / "render_C.jsx_log.txt")
    for label in dict.fromkeys(list(sa) + list(sc)):
        if only and label not in only:
            continue
        cells = []
        for tag, status in (("A", sa), ("C", sc)):
            state = status.get(label, "-")
            if not state.startswith("OK"):
                cells.append(f"{tag} {state}")
        a_frames = sorted(render.glob(f"A_{label}_[0-9]*.tif"))
        c_frames = sorted(render.glob(f"C_{label}_[0-9]*.tif"))
        if a_frames or c_frames:
            cells.append(_pixel_verdict(a_frames, c_frames))
        a_aud, c_aud = render / f"A_{label}_audio.aif", render / f"C_{label}_audio.aif"
        if a_aud.exists() and c_aud.exists():
            same = aiff_samples(a_aud) == aiff_samples(c_aud)
            cells.append("audio identical" if same else "AUDIO DIFF")
        elif a_aud.exists() or c_aud.exists():
            cells.append(f"audio only in {'A' if a_aud.exists() else 'C'}")
        if aa.get(label) != ac.get(label):
            cells.append(f"ATTR\n      A: {aa.get(label)}\n      C: {ac.get(label)}")
        print(f"{label:20s} " + " | ".join(cells))


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2:])
