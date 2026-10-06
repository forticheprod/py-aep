"""Compare `platform_probe.jsx` outputs side by side.

Usage:
    uv run python scripts/platform_probe_report.py <probe.aep> [<probe.aep> ...]

Each argument is a `probe.aep` written by `scripts/jsx/platform_probe.jsx` (or
any project, e.g. one saved after a manual File > Import); the label is its
folder name (`<mac|win>_<AE version>_<ui|noui>` for the probe). Every file
footage item is listed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import py_aep
from py_aep import FileSource, FootageItem
from py_aep.binary.utils import find_by_list_type, parse_alas_data

_AGENT = re.compile(rb"softwareAgent(?:>|=\")Adobe After Effects ([^<\"]*)")


def _style(path: str) -> str:
    if path.startswith("\\\\"):
        return "unc"
    if re.match(r"^[A-Za-z]:", path):
        return "drive"
    return "posix" if path.startswith("/") else "other"


def _footage(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    app = py_aep.parse(path)
    project = app.project
    nnhd = project._nnhd
    agents = [a.decode() for a in _AGENT.findall(path.read_bytes())]
    header = {
        "build": app.version,
        "head_os": str(project._head.ae_version_os),
        "nnhd_b2": str(nnhd._reserved_00[2]),
        "codepage": nnhd._unknown_1a[:2].hex(),
        "gpu": str(project.gpu_accel_type),
        "last_save": agents[-1] if agents else "",
    }
    items: dict[str, str] = {}
    for item in project.items.values():
        if not isinstance(item, FootageItem):
            continue
        src = item.main_source
        if not isinstance(src, FileSource):
            continue
        s = src._sspc
        alas = parse_alas_data(src._pin.chunks)
        cells = [
            s.source_format_type,
            f"full={int(s.full_frame)} c8={s._reserved_c8.hex()} "
            f"0x71={s._flags_70:02x} 0x73={s._reserved_71[1]:02x} "
            f"from_file={int(s.from_file)}",
            f"bpp={s.depth} alpha={s.alpha_mode_raw}/{s._alpha_flags}",
            f"dur={s.duration_dividend}/{s.duration_divisor} "
            f"fps={s.native_frame_rate:g} size={s.data_size}",
            f"path={alas.get('platform')}/{_style(alas.get('fullpath', ''))} "
            f"asc={alas.get('ascendcount_base')}/{alas.get('ascendcount_target')} "
            f"server={alas.get('server_name')!r}",
        ]
        try:
            stvc = find_by_list_type(chunks=src._pin.chunks, list_type="StVc")
            names = [c.value for c in stvc.chunks if c.chunk_type == "Utf8"]
            cells.append("order=" + ",".join(ascii(n)[1:-1] for n in names))
        except Exception:  # noqa: BLE001 - numbered sequences have no StVc
            pass
        items[item.name] = " | ".join(cells)
    return header, items


def main(paths: list[str]) -> None:
    results = {}
    for p in map(Path, paths):
        label = p.parent.name if p.stem == "probe" else f"{p.parent.name}/{p.stem}"
        results[label] = _footage(p)
    print("== header")
    for label, (header, _) in results.items():
        print(f"  {label}: " + " ".join(f"{k}={v}" for k, v in header.items()))
    names = sorted({n for _, items in results.values() for n in items})
    for name in names:
        print(f"== {name}")
        for label, (_, items) in results.items():
            print(f"  {label}: {items.get(name, '-')}")


if __name__ == "__main__":
    main(sys.argv[1:])
