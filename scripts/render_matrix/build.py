"""Build the per-format render matrix: py_aep's project plus AE scripts.

Every format py_aep imports is imported twice - by After Effects itself
(copy A, `ae_import.jsx`) and by py_aep (copy C, `fmt_C.aep`) - then AE
renders both (`render_A.jsx`, `render_C.jsx`) and `compare.py` diffs the
pixels and audio. See `.claude/plans/format-render-fixes.md`.

Usage:
    uv run python scripts/render_matrix/build.py [--out DIR] [--only a,b]
    pwsh scripts/render_matrix/run.ps1 -Dir DIR -Script ae_import.jsx
    pwsh scripts/render_matrix/run.ps1 -Dir DIR -Script render_A.jsx
    pwsh scripts/render_matrix/run.ps1 -Dir DIR -Script render_C.jsx
    uv run python scripts/render_matrix/compare.py DIR
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import traceback
from pathlib import Path

import py_aep
from py_aep import ImportAsType, ImportOptions

REPO = Path(__file__).resolve().parents[2]
ASSETS = REPO / "samples" / "assets"
BASE = REPO / "samples" / "models" / "folder" / "folder.aep"
F, COMP, CROP = "FOOTAGE", "COMP", "COMP_CROPPED_LAYERS"

# (label, asset, sequence, import_as)
SPEC: list[tuple[str, str, bool, str]] = [
    ("png_still", "image_with_alpha.png", False, F),
    ("exr_still", "new_exr.0002.exr", False, F),
    ("tif_8bits", "8bits.tif", False, F),
    ("tif_alpha", "8bits_transparency.tif", False, F),
    ("dpx_8rgb", "dpx_8bit_rgb.dpx", False, F),
    ("dpx_8rgba", "dpx_8bit_rgba.dpx", False, F),
    ("dpx_10be", "dpx_10bit_be.dpx", False, F),
    ("dpx_12be", "dpx_12bit_be.dpx", False, F),
    ("dpx_16rgba", "dpx_16bit_rgba_be.dpx", False, F),
    ("cin", "cin.cin", False, F),
    ("heic", "heic.heic", False, F),
    ("heic_alpha", "heic_alpha.heic", False, F),
    ("jpg", "11_progressive.jpg", False, F),
    ("tga_16", "tga_16.tga", False, F),
    ("tga_24", "tga_24.tga", False, F),
    ("tga_32", "tga_32.tga", False, F),
    ("bmp", "bmp.bmp", False, F),
    ("gif_still", "gif.gif", False, F),
    ("psd_8bits", "8bits.psd", False, F),
    ("psd_flat", "flattened.psd", False, F),
    ("psd_flat_rgb", "flattened_rgb.psd", False, F),
    ("psb", "8bits.psb", False, F),
    ("hdr", "hdr.hdr", False, F),
    ("crw", "crw.crw", False, F),
    ("ai_footage", "ai.ai", False, F),
    ("eps_footage", "eps.eps", False, F),
    ("pdf_footage", "pdf.pdf", False, F),
    ("mov_23976", "mov_23_976.mov", False, F),
    ("mov_23976_noaudio", "mov_23_976_no_audio.mov", False, F),
    ("mov_480", "mov_480.mov", False, F),
    ("mov_alpha", "mov_alpha_small.mov", False, F),
    ("mp4_360p", "mp4_5s-360p.mp4", False, F),
    ("mp4_640", "mp4_640x360.mp4", False, F),
    ("mp4_av1_audio", "mp4_av1_with_audio.mp4", False, F),
    ("m4v", "m4v.m4v", False, F),
    ("mpeg", "mpeg.mpeg", False, F),
    ("wmv", "wmv.wmv", False, F),
    ("swf", "swf.swf", False, F),
    ("aif", "aif.aif", False, F),
    ("aiff", "click.aiff", False, F),
    ("wav", "wav.wav", False, F),
    ("mp3", "mp3.mp3", False, F),
    ("aac", "aac.aac", False, F),
    ("m4a", "m4a.m4a", False, F),
    ("fbx", "crystal.fbx", False, F),
    ("psd_comp", "layer_bounds.psd", False, COMP),
    ("psd_cropped", "layer_bounds.psd", False, CROP),
    ("psd_groups_comp", "grouped_layers.psd", False, COMP),
    ("psd_styles_cropped", "psd_layer_styles.psd", False, CROP),
    ("psd_vmask_comp", "psd_vector_mask.psd", False, COMP),
    ("psb_comp", "8bits.psb", False, COMP),
    ("ai_comp", "ai.ai", False, COMP),
    ("eps_comp", "eps.eps", False, COMP),
    ("svg", "svg.svg", False, CROP),
    ("svg_butterfly", "butterfly.svg", False, CROP),
    ("svg_mixed", "svg_mixed.svg", False, CROP),
    ("seq_png", "image_with_alpha.png", True, F),
    ("seq_dpx", "dpx_seq.0001.dpx", True, F),
    ("seq_exr", "new_exr.0002.exr", True, F),
    ("seq_tif", "8bits_transparency.tif", True, F),
    ("seq_jpg", "11_progressive.jpg", True, F),
    ("seq_tga", "tga_32.tga", True, F),
    ("seq_bmp", "bmp.bmp", True, F),
    ("seq_gif", "gif.gif", True, F),
    ("seq_cin", "cin.cin", True, F),
    ("seq_hdr", "hdr.hdr", True, F),
    ("seq_crw", "crw.crw", True, F),
]
# Already numbered sets on disk; any other sequence is 3 copies of the asset.
_NUMBERED = {"dpx_seq.0001.dpx", "new_exr.0002.exr"}
# AE's importFile returns null for SVG but still builds the comp, named after
# the file. (Left out of SPEC: a PSD sequence and an EXR cropped-comp import,
# whose scripted AE import opens a modal dialog that hangs -noui.)
_SVG_NAMES = {
    "svg": "svg.svg",
    "svg_butterfly": "butterfly.svg",
    "svg_mixed": "svg_mixed.svg",
}

_RESUME_JS = """
    var logFile = new File(outDir + LOGNAME);
    function log(m) { logFile.open("a"); logFile.writeln(m); logFile.close(); }
    // Resume after a crash or hang: skip finished labels and the one a
    // previous run died on.
    var prev = {};
    if (logFile.exists) {
        logFile.open("r");
        while (!logFile.eof) {
            var m = logFile.readln().match(/^(START|OK|SKIPCRASH|NOITEM|ERR|CANNOT) (\\S+)/);
            if (m) { prev[m[2]] = m[1]; }
        }
        logFile.close();
    }
    log("RUN " + new Date().toString());
"""


def _source_path(out: Path, label: str, asset: str, sequence: bool) -> Path:
    if not sequence or asset in _NUMBERED:
        return ASSETS / asset
    folder = out / label
    folder.mkdir(exist_ok=True)
    ext = Path(asset).suffix
    for n in (1, 2, 3):
        target = folder / f"{label}_{n:04d}{ext}"
        if not target.exists():
            shutil.copy2(ASSETS / asset, target)
    return folder / f"{label}_0001{ext}"


def _import_jsx(out: Path, rows: list[tuple[str, Path, bool, str]]) -> str:
    spec = ",\n".join(
        f"        [{json.dumps(lb)}, {json.dumps(p.as_posix())}, "
        f"{'true' if seq else 'false'}, {json.dumps(how)}]"
        for lb, p, seq, how in rows
    )
    return f"""(function () {{
    var outDir = {json.dumps(out.as_posix() + "/")};
    var LOGNAME = "ae_import.jsx_log.txt";
    var spec = [
{spec}
    ];
{_RESUME_JS}
    app.open(new File({json.dumps(BASE.as_posix())}));
    for (var i = 0; i < spec.length; i++) {{
        var s = spec[i];
        if (prev[s[0]] === "START") {{ log("SKIPCRASH " + s[0]); continue; }}
        log("START " + s[0]);
        try {{
            var io = new ImportOptions(new File(s[1]));
            if (s[2]) {{ io.sequence = true; }}
            var how = ImportAsType[s[3]];
            if (!io.canImportAs(how)) {{ log("CANNOT " + s[0]); continue; }}
            io.importAs = how;
            var it = app.project.importFile(io);
            if (it) {{ it.name = s[0]; }}
            log("OK " + s[0]);
        }} catch (e) {{ log("ERR " + s[0] + " - " + e.toString()); }}
    }}
    app.project.save(new File(outDir + "fmt_A.aep"));
    log("DONE");
}})();
"""


def _render_jsx(out: Path, tag: str, labels: list[str]) -> str:
    alias = json.dumps(_SVG_NAMES if tag == "A" else {})
    return f"""(function () {{
    var outDir = {json.dumps(out.as_posix() + "/")};
    var LOGNAME = "render_{tag}.jsx_log.txt";
    var TAG = "{tag}";
    var labels = {json.dumps(labels)};
    var alias = {alias};
{_RESUME_JS}
    new Folder(outDir + "render").create();
    app.open(new File(outDir + "fmt_" + TAG + ".aep"));
    // Software rendering: GPU paths fail on remote sessions (HEIC).
    app.project.gpuAccelType = GpuAccelType.SOFTWARE;
    function find(name) {{
        for (var i = 1; i <= app.project.numItems; i++) {{
            if (app.project.item(i).name === name) {{ return app.project.item(i); }}
        }}
        return null;
    }}
    var rq = app.project.renderQueue;
    for (var k = 0; k < labels.length; k++) {{
        var label = labels[k];
        if (prev[label] === "START") {{ log("SKIPCRASH " + label); continue; }}
        if (prev[label]) {{ continue; }}
        try {{
            var it = find(label) || (alias[label] ? find(alias[label]) : null);
            if (!it) {{ log("NOITEM " + label); continue; }}
            var isComp = it instanceof CompItem;
            var ms = isComp ? null : it.mainSource;
            log("ATTR " + label + " | " + (isComp ? "comp layers=" + it.numLayers :
                "missing=" + it.footageMissing + " still=" + ms.isStill + " hasAlpha=" + ms.hasAlpha +
                " alphaMode=" + ms.alphaMode + " conform=" + ms.conformFrameRate) +
                " " + it.width + "x" + it.height + " par=" + it.pixelAspect + " dur=" + it.duration +
                " fps=" + it.frameRate + " video=" + it.hasVideo + " audio=" + it.hasAudio);
            log("START " + label);
            var fps = it.frameRate > 0 ? it.frameRate : 24;
            var n = Math.round(it.duration * fps);
            var video = isComp || it.hasVideo;
            var comp = app.project.items.addComp("R_" + label, it.width >= 4 ? it.width : 100,
                it.height >= 4 ? it.height : 100, 1, video ? 3 / fps : 1, fps);
            var layer = comp.layers.add(it);
            // Sample mid-clip so wrong timing shows up.
            if (n > 6) {{ layer.startTime = -Math.floor(n / 2) / fps; }}
            var added = [];
            if (video) {{
                var rv = rq.items.add(comp); added.push(rv);
                rv.outputModule(1).applyTemplate("TIFF Sequence with Alpha");
                rv.outputModule(1).file = new File(outDir + "render/" + TAG + "_" + label + "_[#]");
            }}
            if (it.hasAudio) {{
                var ra = rq.items.add(comp); added.push(ra);
                ra.outputModule(1).applyTemplate("AIFF 48kHz");
                ra.outputModule(1).file = new File(outDir + "render/" + TAG + "_" + label + "_audio");
            }}
            rq.render();
            // An item AE leaves QUEUED would silently block every later
            // render() call, so each one is removed after its turn.
            var st = [];
            for (var r = 0; r < added.length; r++) {{ st.push(added[r].status); added[r].remove(); }}
            log("OK " + label + " status=" + st.join(","));
        }} catch (e) {{ log("ERR " + label + " - " + e.toString()); }}
    }}
    log("DONE");
}})();
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--out", type=Path, default=Path(tempfile.gettempdir()) / "py_aep_render_matrix"
    )
    parser.add_argument("--only", default="", help="comma-separated labels")
    args = parser.parse_args()
    out: Path = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    only = set(filter(None, args.only.split(",")))
    spec = [s for s in SPEC if not only or s[0] in only]

    rows = [(lb, _source_path(out, lb, a, seq), seq, how) for lb, a, seq, how in spec]
    (out / "ae_import.jsx").write_text(_import_jsx(out, rows), encoding="utf-8")
    labels = [r[0] for r in rows]
    for tag in ("A", "C"):
        (out / f"render_{tag}.jsx").write_text(
            _render_jsx(out, tag, labels), encoding="utf-8"
        )

    project = py_aep.parse(BASE).project
    for label, path, seq, how in rows:
        try:
            options = ImportOptions(path)
            options.sequence = seq
            options.import_as = ImportAsType[how]
            project.import_file(options).name = label
        except (ValueError, NotImplementedError) as e:
            print(f"py refuses {label}: {e}")
        except Exception:  # noqa: BLE001 - keep building the rest of the matrix
            print(f"py FAILED {label}:")
            traceback.print_exc()
    target = out / "fmt_C.aep"
    if target.exists():
        target.unlink()
    project.save(target)
    print(f"{len(rows)} labels -> {out}")


if __name__ == "__main__":
    main()
