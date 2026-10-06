# AEP File Format Specification

This page describes the binary After Effects project format (`.aep`): how the
file is laid out, what every chunk holds, and the rules a program must follow
to write a file After Effects opens. It is the reference behind py_aep's
[binary layer](https://github.com/forticheprod/py-aep/tree/main/src/py_aep/binary),
but it is written for anyone who needs to read or write `.aep` files. The
[CLI tools](cli.md) `aep-inspect` and `aep-compare` print a file's chunk tree
and diff two files chunk by chunk, which is the quickest way to follow along.

The format is undocumented by Adobe. Everything here was reverse-engineered
from files After Effects writes - the py-aep sample corpus of about 1,350
projects saved by After Effects CC 2018 to AE 2026 on Windows and macOS - and
from After Effects' behaviour when it opens, resaves and renders files crafted
to differ in one field. Unless a section says otherwise, the description
matches AE 2026 (file version 97). Fields nobody has decoded are listed as
*Unknown*, with the values the samples show; meanings that rest on inference
rather than a test are marked *(inferred)*.

The XML variant of the format (`.aepx`) and the other RIFX files After
Effects writes (keyframe clipboards, favourites, templates) are out of scope.

## Conventions

### Byte order and types

The file is **big-endian**. A handful of chunks, and a few fields inside
big-endian chunks, are written little-endian; their type carries an ` LE`
suffix (see [Little-endian data](#little-endian-data)).

| Type | Size | Meaning |
|---|---|---|
| `u1` `u2` `u4` `u8` | 1, 2, 4, 8 | Unsigned integer. |
| `s1` `s2` `s4` `s8` | 1, 2, 4, 8 | Two's-complement signed integer. |
| `f4` `f8` | 4, 8 | IEEE 754 single / double precision float. |
| `fixed 16.16` | 4 | `u2` integer part followed by a `u2` fraction in 1/65536 units. |
| `fourcc` | 4 | Four ASCII characters (chunk tags, list types, codec and importer codes). Codes may end in spaces (`Pin `, `seq `). |
| `char[N]` | N | Fixed-size text, NUL-padded; each table says whether it is ASCII or UTF-8. |
| `bytes[N]` | N | Raw bytes. |

Offsets are hexadecimal from the start of the chunk body, lengths are decimal
byte counts. Bits are numbered from the least significant (bit 0 = mask
`0x01`).

### Times and rates

After Effects stores most times as a **rational pair** - a dividend and a
divisor, seconds = dividend / divisor - and most frame rates as
`fixed 16.16`. Keyframe times are integers in the *time base* of the layer
that owns the property (its `tdb4` time base, see
[`tdb4`](#tdb4)). Durations of 600ths of a second also appear (markers).

### Version notation

"AE 2022", "AE 23" ... name After Effects releases. "File version 93.43"
names the `major.minor` pair stored at the start of [`head`](#head) (see
[File versions](#file-versions)).

## File structure

An `.aep` file is a single **RIFX** chunk followed by an **XMP packet**:

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | fourcc | `RIFX` |
| 0x04 | 4 | u4 | Length of the RIFX body (everything up to the XMP packet, minus these 8 bytes). |
| 0x08 | 4 | fourcc | Form type `Egg!`. |
| 0x0C | ... | chunks | The project chunks, in the [root order](#root-chunk-order). |
| ... | ... | UTF-8 | [XMP packet](#xmp-packet) to the end of the file. |

### Chunks

Every chunk has an 8-byte header and a body:

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | fourcc | Chunk tag (`cdta`, `Utf8`, `LIST`, ...). |
| 0x04 | 4 | u4 | Body length in bytes, excluding the header and the pad byte. |
| 0x08 | n | | Body. |
| 0x08 + n | 0 or 1 | | One pad byte (0) when the body length is odd, so the next chunk starts at an even offset. |

Most chunks hold data, laid out per tag as documented on this page; the
others are containers whose body is a sequence of chunks.

### `LIST`

A `LIST` chunk groups chunks. Its body starts with a four-character **list
type** that says what the list is, followed by the child chunks:

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | fourcc | List type (`Fold`, `Item`, `Layr`, `tdgp`, ...). |
| 0x04 | ... | chunks | Children, up to the end of the body. |

This page names lists by their type: `LIST:Item` is a `LIST` chunk whose list
type is `Item`. The root `RIFX` chunk has the same layout with list type
`Egg!`.

One list breaks the rule: [`LIST:btdk`](#listbtdk) (a text document) holds
raw bytes after its list type instead of chunks.

### Wrapper chunks

Five tags are containers without a list type: their body is a chunk
sequence - in practice a single [`Utf8`](#utf8) - and the tag says what the
string is.

#### `tdsn`

A property's display name, in [`LIST:tdgp`](#listtdgp) and
[`LIST:tdbs`](#listtdbs). AE writes `-_0_/-` for a property that has not been
renamed; its name then comes from the match name. **py_aep:** `TdsnChunk`

#### `pdnm`

An effect parameter's name, or a popup's items separated by `|`, in
[`LIST:parT`](#listpart). **py_aep:** `ContainerChunk`

#### `fnam`

The match name of an effect instance, in [`LIST:sspc`](#listsspc).
**py_aep:** `ContainerChunk`

#### `vfdn`

A variable font axis name (e.g. `Font Axis Weight`), after the stream of an
`ADBE Text VF Axis` property in a text animator (AE 26 on). **py_aep:**
`VfdnChunk`

The fifth, [`RCom`](#rcom), holds a render-queue item's comment.

### `Utf8`

A UTF-8 string: the whole body, with no length prefix, no terminator and no
BOM. An empty body is an empty string.

**Parent:** many lists · **Size:** variable · **py_aep:** `Utf8Chunk`

Most strings are `Utf8` chunks placed right after the chunk they belong to:
an item's name after its [`idta`](#idta), a layer's name after its
[`ldta`](#ldta), a property stream's expression in its
[`LIST:tdbs`](#listtdbs), and the JSON payloads that follow the colour
management flags ([`pcms`](#pcms), [`PwCs`](#pwcs), [`pdvc`](#pdvc),
[`mcsp`](#mcsp), [`Mcsp`](#mcsp_1), [`ocsp`](#ocsp), [`hdrm`](#hdrm)). Two
strings are not `Utf8` chunks: [`wsnm`](#wsnm) is UTF-16LE and
[`cmta`](#cmta) is a NUL-terminated UTF-8 chunk.

### Little-endian data

These chunks are little-endian as a whole: [`CsCt`](#csct), [`EfDC`](#efdc),
[`dwga`](#dwga), [`idpc`](#idpc), [`idpi`](#idpi), [`iide`](#iide),
[`linl`](#linl), [`mrid`](#mrid), [`sfid`](#sfid), [`StVS`](#stvs),
[`strt`](#strt), [`btov`](#btov), [`mtov`](#mtov), [`mdlv`](#mdlv) and
[`mdld`](#mdld). Little-endian fields also sit inside big-endian chunks
([`shph`](#shph) at 0x14, [`tdb4`](#tdb4) at 0x3C, [`NmHd`](#nmhd) at 0x10),
in orientation values ([`LIST:otst`](#listotst)), and in some plug-in
payloads (the OpenEXR [`opti`](#opti) and [`Ropt`](#ropt)). Each table marks
them.

### How After Effects reads a file

These rules come from opening files with one chunk removed, moved or added
(AE 2026). They are what makes chunk order matter:

- AE reads the children of a list **by tag, scanning forward** from the last
  chunk it read. A chunk it does not know is **skipped**: an unknown tag inside
  a `LIST:Item` opens fine.
- Most chunks are **required**. When one is missing AE refuses the file with
  "missing data in file". This also happens when a required chunk is present
  but **out of order**: placing [`cdrp`](#cdrp) before [`cdta`](#cdta) hides
  it from the forward scan, so AE reports it missing.
- Some chunks are **optional** and AE falls back to a default (a viewer's
  missing [`ppSn`](#ppsn) reads as 0.0).
- Some optional chunks end the scan when they are missing: without
  [`otln`](#otln), AE also loses the `seq`, `LIST:LSIf` and `ppSn` chunks
  that follow it in the same list.
- A few chunks are verified: without [`linl`](#linl) in a footage colour
  list, AE stops with an "internal verification failure".

A writer should therefore emit chunks in exactly the order After Effects
does, never drop a chunk it does not understand, and may add chunks of its
own (they are skipped). AE also regenerates some purely visual state: the
root [`LIST:LSIf`](#listlsif) and [`LIST:PTRE`](#listptre) panel records can
be left out of a new file.

## File versions

The first four bytes of [`head`](#head) hold the **file version**, a `u2`
major and a `u2` minor. After Effects refuses a file whose major is higher
than its own - AE CC 2018 opening a file stamped for AE 2022 reports: "The
file you are attempting to open was created with After Effects version 22.0
(Windows 64) and cannot be opened with this version".

| Release | File version major | Versions seen in the corpus |
|---|---|---|
| CC 2018 (15.x) | 92 | 92.14 |
| CC 2019 (16.x) to AE 2022 (22.x) | 93 | 93.40, 93.43 |
| AE 23 | 94 | 94.9 |
| AE 24 | 95 | 95.6 |
| AE 25 | 96 | 96.5, 96.9 |
| AE 26 | 97 | 97.2, 97.7 |

From AE 2022 on, the major is the release number plus 71. The minor differs
between builds of one release (AE 26.0 writes 97.2, later 26.x builds 97.7).
After Effects decides which chunks to read - and what size some of them have -
from the full version, so a writer must stamp the version of the release
whose layout it writes. Version-dependent layouts are noted where they occur,
for example [`ldta`](#ldta): 160 bytes before AE 23, 164 from AE 23. Every
After Effects release refuses a composition whose layer records are 164 bytes
in a file stamped 93.x ("chunk in file too big").

### `svap`

**Parent:** root · **Size:** 4 bytes · **py_aep:** `SvapChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | The build word of the After Effects that saved the file - the same value as `head` 0x04 in every sample (`0F100643` = AE 26.0 build 67). |

AE does not use it to decide whether it can open the file.

### `head`

The file header: file version, the saving application, the next item id.

**Parent:** root · **Size:** 20 bytes · **py_aep:** `HeadChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | File version major (`0x61` = 97 for AE 26). |
| 0x02 | 2 | u2 | File version minor. |
| 0x04 | 4 | u4 | Build word of the saving application (below). |
| 0x08 | 4 | u4 | `0x80000000` in every sample. |
| 0x0C | 4 | u4 | Next item id: always greater than every item id in the project ([`idta`](#idta) 0x10). |
| 0x10 | 4 | u4 | Revision counter: grows as the project is edited and saved (exceeds 65,535 in production files). |

The build word packs the version of the After Effects that saved the file:

| Bits | Meaning |
|---|---|
| 31 | 0. |
| 30-26 | Major version / 8 (the high part). |
| 25-22 | Operating system: 12 = Windows, 14 = macOS. |
| 21-19 | Major version % 8 (major = high part x 8 + this). |
| 18-15 | Minor version (the `1` of `15.1.2`). |
| 14-11 | Bug-fix version (the `2` of `15.1.2`) *(inferred: set only in the CC 2018 15.1.2 samples)*. |
| 10 | 1 in every sample. |
| 9 | 1 = release build, 0 = beta. |
| 8 | 0 in every sample. |
| 7-0 | Build number (the `67` of `26.0x67`). |

For AE 26.0x67 on Windows the word is `0x0F100643`. The OS bits only record
where the file was saved: AE rewrites them on every save and opens files
stamped for the other platform.

### `nhed`

A compact copy of some project settings; it mirrors [`nnhd`](#nnhd).

**Parent:** root · **Size:** 32 bytes · **py_aep:** `NhedChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | 0 in every sample. |
| 0x02 | 2 | u2 | Unknown: `0x0800` or 0 (0x08 in the first byte on macOS, as in `nnhd`). |
| 0x04 | 4 | u4 | Unknown: 0, 1 or 5. |
| 0x08 | 1 | u1 | Time display: bit 7 = feet + frames film type (1 = 16 mm, 0 = 35 mm), bits 6-0 = time display type (0 = timecode, 1 = frames). |
| 0x09 | 1 | u1 | Footage start time (0 = start at 0, 1 = use the media's timecode). |
| 0x0A | 1 | u1 | Unknown (1 in new projects). |
| 0x0B | 1 | u1 | Bit 0 = show frames as feet + frames. |
| 0x0C | 1 | u1 | Timecode default base (frames per second of the timecode display, 30 by default). |
| 0x0D | 1 | u1 | Unknown: 16 or 40, the low byte of `nnhd` 0x10. |
| 0x0E | 1 | u1 | Frame count: 0 = start at 0, 1 = start at 1, 2 = timecode conversion. |
| 0x0F | 1 | u1 | Project colour depth: 0 = 8 bpc, 1 = 16 bpc, 2 = 32 bpc. |
| 0x10 | 1 | u1 | 1 = thumbnails use the transparency grid. |
| 0x11 | 1 | u1 | Unknown. |
| 0x12 | 2 | u2 | System text encoding of the saving machine (Windows code page `0x04E4` = 1252 up to AE 25, `0xFDE9` = 65001 from AE 26; `0x0100` on macOS). |
| 0x14 | 12 | bytes[12] | Values that vary from save to save and carry no project setting; AE ignores them on open. |

AE keeps the shared fields of `nhed` and `nnhd` equal; a writer should
update both.

### `nnhd`

Project settings: time display, frame counting, colour depth.

**Parent:** root · **Size:** 40 bytes · **py_aep:** `NnhdChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | 0 in every sample. |
| 0x02 | 2 | u2 | Unknown: `0x0800` on macOS, 0 on Windows (rewritten by every save). |
| 0x04 | 4 | u4 | Unknown: 0, 1 or 5. |
| 0x08 | 1 | u1 | Time display, as `nhed` 0x08. |
| 0x09 | 1 | u1 | Footage start time, as `nhed` 0x09. |
| 0x0A | 1 | u1 | Unknown (1 in new projects). |
| 0x0B | 1 | u1 | Bit 0 = show frames as feet + frames. |
| 0x0C | 2 | u2 | 0 in every sample. |
| 0x0E | 2 | u2 | Timecode default base (1-999). |
| 0x10 | 4 | u4 | Unknown: 16 or 40. |
| 0x14 | 1 | u1 | Frame count, as `nhed` 0x0E. |
| 0x15 | 3 | bytes[3] | 0. |
| 0x18 | 1 | u1 | Project colour depth, as `nhed` 0x0F. |
| 0x19 | 1 | u1 | 1 = thumbnails use the transparency grid. |
| 0x1A | 2 | u2 | System text encoding, as `nhed` 0x12. |
| 0x1C | 12 | bytes[12] | Values that vary from save to save; AE ignores them on open. |

## Root chunk order

The children of the root, in the order After Effects writes them (bracketed
chunks are optional). This order holds across every AE 2022-2026 sample:

| Chunk | Description |
|---|---|
| [`svap`](#svap) | Saving application's build word. |
| [`head`](#head) | File version, build word, next item id. |
| [`nhed`](#nhed), [`nnhd`](#nnhd) | Project display settings. |
| [`adfr`](#adfr) | Project audio sample rate. |
| [`LIST:Pefl`](#listpefl) | Effects used by the project. |
| [`LIST:EfdG`](#listefdg) | Effect parameter definitions, one per effect type used (AE rebuilds them). |
| [`qtlg`](#qtlg) | Legacy QuickTime gamma setting *(inferred)*. |
| [`LIST:gpuG`](#listgpug) | GPU renderer id. |
| [`LIST:sfnm`](#listsfnm) | Solids folder name and id. |
| [`mrid`](#mrid) | Media Replacement Comps folder id (AE 2020 on). |
| [`acer`](#acer) | Compensate for scene-referred profiles. |
| [`LIST:CPPl`](#listcppl) | ICC profiles the project refers to. |
| [`cpid`](#cpid) | Working colour space profile id. |
| [`lnrb`](#lnrb) | Present when linear blending is on. |
| [`lnrp`](#lnrp) | Present when the working space is linearized. |
| [`dwga`](#dwga) | Working gamma. |
| [`pcms`](#pcms) + [`Utf8`](#utf8) | Colour management settings (AE 2022 on). |
| [`PwCs`](#pwcs) + [`Utf8`](#utf8) | Working colour space (AE 2022 on). |
| [`pdvc`](#pdvc) + [`Utf8`](#utf8) | Display colour space (AE 23 on). |
| [`LIST:ExEn`](#listexen) | Expression engine (CC 2019 on). |
| [`LIST:Fold`](#listfold) | The project's items. |
| [`wsns`](#wsns), [`wsnm`](#wsnm), [`Utf8`](#utf8) | Workspace name. |
| [`fcid`](#fcid) | The active item. |
| [`oacc`](#oacc) | Essential Graphics panel state: count of `ocid`. |
| [`acid`](#acid), [`ocid`](#ocid) | Essential Graphics panel state (rare). |
| [`LIST:LSIf`](#listlsif) | Project panel state. |
| [`LIST:LRdr`](#listlrdr) | The render queue. |
| [`LIST:PTRE`](#listptre) | Project panel tree state. |

## XMP packet

After the RIFX chunk, the file ends with an XMP packet in UTF-8
(`<?xpacket begin="..." id="W5M0MpCehiHzreSzNTczkc9d"?>` ...
`<?xpacket end="w"?>`) carrying the project's metadata, including an
editing history that AE extends on every save. Its length is not recorded
anywhere: it runs to the end of the file. The packet is optional - AE opens a
file that ends with the RIFX chunk.

## Project settings and colour management

Between the file header chunks and the item tree, and again after it, the
root of every `.aep` holds a run of small project-level chunks: the
Project Settings (audio sample rate, GPU renderer, expression engine,
colour management), a few bookkeeping ids (the Solids and Media
Replacement folders, the active item, Essential Graphics panel state), an
ICC profile pool, and Project panel state that AE regenerates. Most are
fixed-size chunks. Colour settings follow a common pattern: a 1-byte marker
chunk immediately followed by a root-level [`Utf8`](#utf8) chunk holding
JSON, described in [Root-level settings strings](#root-level-settings-strings)
and [Colour-profile envelope](#colour-profile-envelope).

Multi-byte integers are big-endian except in [`sfid`](#sfid),
[`mrid`](#mrid) and [`dwga`](#dwga), which AE writes little-endian.
"Required" below means AE refuses to open a project that lacks the chunk
("missing data in file"); because AE finds root chunks by scanning forward
(see the reading rules in the overview), these chunks must also keep the
order AE writes them in:

| Order | Chunk | Occurs | Written by | Holds |
|---|---|---|---|---|
| 1 | [`adfr`](#adfr) | 1, required | every version | Audio sample rate. |
| 2 | [`LIST:Pefl`](#listpefl) | 1 | every version | Match names of the effects in use. |
| - | [`LIST:EfdG`](#listefdg) | 0-1 | | Effect definitions (effects section). |
| 3 | [`qtlg`](#qtlg) | 1, required | every version | Legacy QuickTime gamma flag. |
| 4 | [`LIST:gpuG`](#listgpug) | 1 | every version | GPU renderer. |
| 5 | [`LIST:sfnm`](#listsfnm) | 1 | every version | Solids folder name and id. |
| 6 | [`mrid`](#mrid) | 1, required | file version above 93.18 (AE 2020+) | Media Replacement folder id. |
| 7 | [`acer`](#acer) | 1, required | every version | Compensate for scene-referred profiles. |
| 8 | [`LIST:CPPl`](#listcppl) | 1, required | every version | ICC profile pool. |
| 9 | [`cpid`](#cpid) | 1 | every version | Working-space profile ID. |
| 10 | [`lnrb`](#lnrb) | 0-1 | every version | Linear blending on. |
| 11 | [`lnrp`](#lnrp) | 0-1 | every version | Linearize working space on. |
| 12 | [`dwga`](#dwga) | 1 | every version | Working gamma. |
| 13 | [`pcms`](#pcms) + `Utf8` | 0-1 | AE 2022+ | Colour-management settings JSON. |
| 14 | [`PwCs`](#pwcs) + `Utf8` | 0-1 | AE 2022+ | Working colour space envelope. |
| 15 | [`pdvc`](#pdvc) + `Utf8` | 0-1 | AE 2023+ | Display colour space envelope. |
| - | [`LIST:dats`](#listdats) | 0-1 | | Data-driven sources (items section). |
| 16 | [`LIST:ExEn`](#listexen) | 0-1 | AE 2019+ (inferred) | Expression engine. |
| - | [`LIST:Fold`](#listfold) | 1 | | The item tree. |
| 17 | [`wsns`](#wsns), [`wsnm`](#wsnm), `Utf8` | 1 each, required | every version | Workspace name. |
| 18 | [`fcid`](#fcid) | 1, required | every version | Active item id. |
| 19 | [`oacc`](#oacc), [`acid`](#acid), [`ocid`](#ocid) | `oacc` 1, required; the others only when `oacc` > 0 | every version | Essential Graphics panel state. |
| - | [`LIST:LSIf`](#listlsif), [`LIST:LRdr`](#listlrdr) | | | Panel state, render queue. |
| 20 | [`LIST:PTRE`](#listptre) | 0-1 | every version | Project panel state. |

"Written by" is the oldest AE whose samples contain the chunk (the corpus
holds CC 2018 = 92.14 files and AE 2022-2026 files) or, where known, the
file-version gate. A writer targeting an older file version should leave
out the chunks newer than it.

A new project saved by AE 2026 (File > New, then Save) contains:
`adfr` = 48000, empty `LIST:Pefl`, `qtlg` = 0, `LIST:gpuG` = CUDA on
Windows, `LIST:sfnm` = "Solids" with `sfid` 0, `mrid` 0, `acer` 1, empty
`LIST:CPPl`, `cpid` = FF x 16, no `lnrb`/`lnrp`, `dwga` 1, settings JSON
`{"lutInterpolationMethod":1}`, `{}` after `PwCs` and `pdvc`, expression
engine `javascript-1.0`, workspace "Default", `fcid` 0, `oacc` 0, and a
zero-filled `ftwd`.

### `adfr`

Project audio sample rate (File > Project Settings > Audio).

**Parent:** root · **Size:** 8 bytes · **py_aep:** `F8Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 8 | f8 | Sample rate in Hz. The dialog offers 22050, 32000, 44100, 48000 and 96000; samples hold 22050, 48000 and 96000. Not exposed to ExtendScript. |

### `LIST:Pefl`

The effects used in the project, one match name per child.

**Parent:** root

| Child | Occurs | Description |
|---|---|---|
| [`pjef`](#pjef) | 0-n | One effect match name. |

In AE-written files the entries are unique and sorted by byte value, and
they match the effects applied on layers (exactly, in all but 25 of about
1,360 samples; the exceptions leave out pseudo-effects such as the
Dropdown Menu Control, or list an effect that has no ordinary layer
instance, e.g. `ADBE FreePin3`). Files whose list does not match the
effects in use open normally, so a writer can leave it empty. Up to 98
entries in the samples.

### `pjef`

One effect match name, e.g. `ADBE Gaussian Blur 2` or `S_BlurDirectional`.

**Parent:** [`LIST:Pefl`](#listpefl) · **Size:** variable (5-31 bytes in samples) · **py_aep:** `Utf8Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | n | char[n] | ASCII match name, no terminator (the chunk is padded to an even length like every chunk). |

### `qtlg`

Legacy QuickTime gamma flag.

**Parent:** root · **Size:** 1 byte · **py_aep:** `U1Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 0 in every sample. Presumably the "Match legacy After Effects QuickTime gamma adjustments" project setting (inferred from the tag name). Write 0. |

### `LIST:gpuG`

The project's GPU renderer (File > Project Settings > Video Rendering and
Effects; `Project.gpuAccelType`).

**Parent:** root

| Child | Occurs | Description |
|---|---|---|
| [`Utf8`](#utf8) | 1 | The renderer's GUID as lowercase hyphenated text. |

| GUID | Renderer | `Project.gpuAccelType` |
|---|---|---|
| `7ee0ab59-822d-44cc-ac10-16279d041016` | Mercury GPU Acceleration (CUDA) | 1813 (`CUDA`) |
| `f33089e2-1ede-47c1-8a9e-b232bb1cc1a4` | Mercury Software Only | 1816 (`SOFTWARE`) |
| `be93941a-7488-4117-8a46-7e3596950307` | Mercury GPU Acceleration (OpenCL) | 1812 (`OPENCL`) |
| `6ed1497e-17ad-4a5b-846f-52bb81e20104` | Mercury GPU Acceleration (Metal) | 1814 (`METAL`) |
| `c4471277-d5d1-4ea7-a36c-b93ac76dfd41` | Mercury GPU Acceleration (Vulkan) | 1815 (`VULKAN`) |
| `cd99cfc1-bf65-4cb7-ab70-a8f5ea50e8f4` | Mercury GPU Acceleration (DirectX) | 1817 (`DIRECTX`) |
| `31df47f6-8f38-473b-a94a-f6acfeefe2ee` | Unknown: saved by AE 26.3 on Windows; AE 26.0 reads it as 0, no `GpuAccelType` value | - |

The `gpuAccelType` column is what AE 2026 reports for a project holding the
GUID, whether or not the machine can use that renderer. Setting
`gpuAccelType` to a renderer the machine lacks silently stores the default
one instead (AE 2026 with only CUDA and Software available saved the CUDA
GUID for OpenCL, Metal, Vulkan and DirectX).

The value is not rewritten when the project is saved on another
platform: a Metal project saved by Windows AE keeps the Metal GUID.

### `LIST:sfnm`

The Solids folder: its name and its item id.

**Parent:** root

| Child | Occurs | Description |
|---|---|---|
| [`Utf8`](#utf8) | 1 | Name of the folder AE files new solids into, stamped from AE's preferences when the project is created and kept from then on; localised (`Solids`, `Solides`, `Farbflächen` in samples). |
| [`sfid`](#sfid) | 1, required, after the `Utf8` | Item id of that folder. |

### `sfid`

Item id of the Solids folder.

**Parent:** [`LIST:sfnm`](#listsfnm) · **Size:** 4 bytes · **py_aep:** `U4LeChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 LE | Item id of the Solids folder ([`idta`](#idta) id), 0 when none is recorded. |

Measured on AE 2026: a new solid goes into the folder with this id even
after that folder was renamed or moved. When the id is 0 or names no
folder, AE uses a root-level folder whose name equals the `LIST:sfnm`
name, and otherwise creates one and records its id here.

### `mrid`

Item id of the "Media Replacement Comps" folder, the folder AE files the
compositions it creates for Essential Graphics media replacement into.

**Parent:** root · **Size:** 4 bytes · **py_aep:** `U4LeChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 LE | Folder item id, 0 when there is none (e.g. `1d 00 00 00` = item 29, named "Media Replacement Comps", in a media-replacement sample). |

Written and read for file versions above 93.18 (AE 2020, which added media
replacement, saves 93.22); the CC 2018 samples do not have it.

### `acer`

"Compensate for Scene-referred Profiles" (File > Project Settings > Color;
`Project.compensateForSceneReferredProfiles`).

**Parent:** root · **Size:** 1 byte · **py_aep:** `U1Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 1 = on, 0 = off. A new AE 2026 project has 1. |

### `LIST:CPPl`

The project's ICC profile pool: each ICC profile that a 16-byte
[profile ID](#profile-ids) elsewhere in the project refers to, stored once.

**Parent:** root

| Child | Occurs | Description |
|---|---|---|
| [`pprf`](#pprf) | 0-n | One complete ICC profile. |

The list is present, often empty, in every sample. Entries are unique and
sorted by ascending profile ID (all 14 samples with more than one entry).
Ids that refer into the pool:

- [`cpid`](#cpid): in CC 2018 files, the working space lives only here.
  From AE 2022 on, the working-space ICC is embedded in the
  [`PwCs`](#pwcs) envelope instead (the one AE 2024 sample has it in both
  places; AE 2025 and 2026 samples only in the envelope).
- The footage profile ids in [`LIST:CLRS`](#listclrs): every embedded
  (`epid`) and assigned (`apid`) profile in CC 2018 files; in AE 2022+
  files the embedded profiles (`epid`, all but one sample), while the
  assigned profiles travel as envelopes.

AE keeps entries nothing refers to any more (old projects carry dozens of
monitor profiles such as "iMac" or "Display"; up to 144 entries).

### `pprf`

One ICC profile of the pool.

**Parent:** [`LIST:CPPl`](#listcppl) · **Size:** variable (508-60,988 bytes in samples) · **py_aep:** untyped (raw `Chunk`)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | n | bytes[n] | A complete ICC profile (ISO 15076-1): bytes 0-3 hold the profile size (= the chunk size), bytes 36-39 `acsp`. Its key is the profile ID computed from these bytes; the profile's own ID field (bytes 84-99) is either zero or that same ID. |

### `cpid`

Profile ID of the project working space.

**Parent:** root · **Size:** 16 bytes · **py_aep:** `CpidChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 16 | bytes[16] | ICC [profile ID](#profile-ids) of the working space, or `FF` x 16 when the working space is not an ICC profile (None, or any OCIO colour space). |

In every AE 2022+ sample with an ICC working space (699 files) it equals
the profile ID of the ICC embedded in the [`PwCs`](#pwcs) envelope; with
`{}` or an OCIO envelope it is `FF` x 16. In CC 2018 files it names a
[`pprf`](#pprf) entry of [`LIST:CPPl`](#listcppl): AE 2026 reports the
working space "sRGB IEC61966-2.1" for the CC 2018 sample whose `cpid` names
the sRGB entry, and "None" for the CC 2018 File > New sample (`FF` x 16).
AE 2026 rewrites `cpid` when a script sets `workingSpace` (to
`33bc7f1c156fa0d72f8f717ae5886bd4` for "Adobe RGB (1998)", to `FF` x 16
for "None"), without adding a `pprf`; keep it consistent with `PwCs`.
Present in every sample; write it in every file (inferred: when it is
missing, AE also misses the root chunks that follow it).

Working spaces seen in samples:

| `cpid` | Working space (`colorProfileName`) | ICC size |
|---|---|---|
| `1d3fda2edb4a89ab60a23c5f7c7d81dd` | `sRGB IEC61966-2.1` | 3,144 |
| `506f062e12412703215710a53aef4744` | `Rec.2100 PQ` | 30,772 |
| `ae27d1e66d65c5a0a50fe0ec149a24fa` | `ACEScct` | 50,152 |
| `601e997329e4901f2acc5b497ba315f3` | `Rec.709 Gamma 2.4` | 624 |
| `c772b2d26a8f2450ce0da7ac2c511f4c` | `image P3` | 620 |
| `c24ec791616e49618507e9f6063b258a` | `ProPhoto RGB` | 940 |

### `lnrb`

"Blend Colors Using 1.0 Gamma" (`Project.linearBlending`). Present only
when the setting is on.

**Parent:** root · **Size:** 1 byte · **py_aep:** `U1Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | Always 1. |

The setting is the chunk's presence, not its value. Its slot is right after
[`cpid`](#cpid) and before [`lnrp`](#lnrp)/[`dwga`](#dwga); placed anywhere
later (for example at the end of the root) AE's forward search finds it
there and then reports missing data for the chunks it skipped.

### `lnrp`

"Linearize Working Space" (`Project.linearizeWorkingSpace`). Present only
when the setting is on.

**Parent:** root · **Size:** 1 byte · **py_aep:** `U1Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | Always 1. |

Same rules as [`lnrb`](#lnrb); it comes after `lnrb` when both are present.

### `dwga`

Working gamma (File > Project Settings > Color; `Project.workingGamma`).

**Parent:** root · **Size:** 4 bytes · **py_aep:** `DwgaChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 LE | 0 = gamma 2.2, 1 = gamma 2.4 (`01 00 00 00`). A new AE 2026 project has 1. |

### `pcms`

Marker for the colour-management settings: the next root chunk is a
[`Utf8`](#utf8) holding the settings JSON.

**Parent:** root · **Size:** 1 byte · **py_aep:** `U1Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | Always 1. |

Written by AE 2022 and later, together with [`PwCs`](#pwcs).

#### Colour-management settings JSON

One compact JSON object (no whitespace), keys in alphabetical order. A
key whose value is the default is omitted (0 or empty string in every
sample pair that differs in one setting), so the object is `{}` when every
setting is at its default and two files can show disjoint key sets, e.g.
`{"colorManagementSystem":1,"ocioConfigurationFile":"ACES 1.2"}` and
`{"graphicsWhiteLuminance":203,"lutInterpolationMethod":1}`. Readers must
apply the defaults for absent keys.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `colorManagementSystem` | integer | 0 | 0 = Adobe (ICC), 1 = OCIO (`Project.colorManagementSystem`). |
| `graphicsWhiteLuminance` | number | not known | Only 203 is seen (AE 2025 and 2026 files). Presumably the graphics-white luminance in cd/m2 used for HDR, 203 being the BT.2408 reference white (inferred). |
| `lutInterpolationMethod` | integer | 0 | 0 = trilinear, 1 = tetrahedral (`Project.lutInterpolationMethod`). A new AE 2026 project stores 1. |
| `ocioConfigurationFile` | string | `""` | The OCIO configuration: the name of a configuration shipped with AE (`ACES 1.2`, `ACES 1.3 CG v1.0` in samples) or the path of a `.ocio` file, JSON-escaped (`\\` for each backslash). Kept while the project is in Adobe mode (`Project.ocioConfigurationFile`). |

The AE 2022 sample stores only `lutInterpolationMethod`;
`ocioConfigurationFile` first appears in the AE 2023 sample and
`graphicsWhiteLuminance` in AE 2025 files.

#### Unsampled colour flags

AE can also write two more 1-byte chunks in this run, `pcsa` (after the
settings `Utf8`) and `psac` (after the working-space `Utf8`). No sample
contains either and their meaning is not known; a reader should skip
them, a writer should not write them.

### `PwCs`

Marker for the project working colour space (`Project.workingSpace`): the
next root chunk is a [`Utf8`](#utf8) holding a
[colour-profile envelope](#colour-profile-envelope).

**Parent:** root · **Size:** 1 byte · **py_aep:** `U1Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | Always 1. |

The following `Utf8` holds:

- `{}`: no working space ("None"), in either mode.
- an ICC envelope (`baseProfileType` 2) in Adobe mode: the full working
  space profile is embedded, and `colorProfileName` (its `desc` text) is
  what `Project.workingSpace` reports. [`cpid`](#cpid) holds its profile
  ID.
- an OCIO envelope (`baseProfileType` 3) in OCIO mode, of any
  [selection kind](#ocio-selections); `Project.workingSpace` reports its
  `colorProfileName`, e.g. `ACES/ACEScg yo` for a direct pick.

Written by AE 2022 and later; AE reads it only from file versions above
93.34. Projects from earlier versions keep their working space in
[`LIST:CPPl`](#listcppl) via [`cpid`](#cpid).

### `pdvc`

Marker for the project display colour space (File > Project Settings >
Color, OCIO mode; not exposed to ExtendScript): the next root chunk is a
[`Utf8`](#utf8) holding a [colour-profile envelope](#colour-profile-envelope).

**Parent:** root · **Size:** 1 byte · **py_aep:** `U1Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | Always 1. |

The following `Utf8` is `{}` in Adobe mode (the display uses the
operating system's monitor profile, which is not stored) and when the OCIO
display is None; otherwise an OCIO display + view envelope, e.g.
`colorProfileName` `ACES/sRGB` with data
`{"colorSpace1":"ACES","colorSpace2":"sRGB","ocioColorSpaceType":1}`. No
other envelope type occurs here. Written by AE 2023 and later (absent from
the AE 2022 sample).

### `LIST:ExEn`

The expression engine (File > Project Settings > Expressions;
`Project.expressionEngine`).

**Parent:** root

| Child | Occurs | Description |
|---|---|---|
| [`Utf8`](#utf8) | 1 | `extendscript` (the legacy engine) or `javascript-1.0`. |

Absent from the CC 2018 samples: the JavaScript engine arrived in AE 16.0
(CC 2019). A project without it uses the ExtendScript engine (inferred).

### `wsns`

Byte length of the workspace name in [`wsnm`](#wsnm).

**Parent:** root · **Size:** 2 bytes · **py_aep:** `WsnsChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | s2 | Size of `wsnm` in bytes (2 per UTF-16 code unit); 0 for an empty name. Must equal the `wsnm` chunk size. |

### `wsnm`

Name of the UI workspace that was active when the project was saved.

**Parent:** root · **Size:** variable (0-24 bytes in samples) · **py_aep:** `WsnmChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | n | bytes[n] | UTF-16LE text, no BOM, no terminator; n = [`wsns`](#wsns). |

A root [`Utf8`](#utf8) with the same name in UTF-8 follows it (identical in
every sample). Samples hold `Default`, `Standard`, `Small Screen` and the
French `Par défaut`; 121 samples have an empty name (`wsns` 0, empty
`wsnm`, empty `Utf8`).

### `fcid`

The project's active item (`Project.activeItem`).

**Parent:** root · **Size:** 4 bytes · **py_aep:** `U4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Item id ([`idta`](#idta)) of the active item, 0 for none. |

AE writes 0 once the active item is deleted. An id that names no item is
tolerated: AE opens the project with nothing active.

### `oacc`

Count of [`ocid`](#ocid) chunks that follow. Essential Graphics panel
state (inferred: the compositions open in the panel).

**Parent:** root · **Size:** 2 bytes · **py_aep:** `U2Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | Number of entries. 0 in all but two samples (both Essential Graphics projects, value 1). |

When the count is not 0, one [`acid`](#acid) follows, then `oacc`
[`ocid`](#ocid) chunks; with 0 neither is written.

### `acid`

A composition id for the Essential Graphics panel (inferred: the
composition the panel shows).

**Parent:** root · **Size:** 4 bytes · **py_aep:** untyped (raw `Chunk`)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Item id of a composition (`Comp 1` = 1 and `image_with_alpha` = 2 in the two samples). |

Present only when [`oacc`](#oacc) > 0, directly after it. It is not the
active item: in both samples [`fcid`](#fcid) names a different
composition.

### `ocid`

One composition id of the Essential Graphics panel list (inferred: a
composition open in the panel).

**Parent:** root · **Size:** 4 bytes · **py_aep:** untyped (raw `Chunk`)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Item id of a composition (equal to `acid` in both samples). |

Repeated [`oacc`](#oacc) times after [`acid`](#acid).

### `LIST:PTRE`

Project panel view state (inferred from the tag name).

**Parent:** root (last chunk before the XMP trailer)

| Child | Occurs | Description |
|---|---|---|
| [`ftwd`](#ftwd) | 1, required | The panel state record. |

Present in every sample, but optional: AE 2026 opens a project without it
and writes a fresh one on the next save.

### `LIST:CTRE`

A second panel-state list with the same content as
[`LIST:PTRE`](#listptre), seen once, inside a [`LIST:FEE`](#listfee) of a
CC 2018 production project.

**Parent:** [`LIST:FEE`](#listfee)

| Child | Occurs | Description |
|---|---|---|
| [`ftwd`](#ftwd) | 1 | The panel state record. |

### `ftwd`

Panel view state record. All zeros in 1,359 of the 1,362 records in the
samples; write 56 zero bytes.

**Parent:** [`LIST:PTRE`](#listptre), [`LIST:CTRE`](#listctre) · **Size:** 56 bytes · **py_aep:** untyped (raw `Chunk`)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | Unknown; 0 in every sample. |
| 0x02 | 2 | u2 | Unknown; 0 in every sample. |
| 0x04 | 2 | u2 | Unknown; 0 in every sample. |
| 0x06 | 2 | u2 | Unknown; 0 in every sample. |
| 0x08 | 2 | u2 | Unknown; varies in the three non-zero records (`00 24`, `23 08`, `FC 9E`). |
| 0x0A | 2 | u2 | Unknown; varies in the three non-zero records (`FF FC`, `03 A7`, `FC 8E`). |
| 0x0C | 2 | u2 | Unknown; 1 in the non-zero records. |
| 0x0E | 6 | bytes[6] | Unknown; 0 in every sample. |
| 0x14 | 4 | u4 | Unknown; 0 in every sample. |
| 0x18 | 4 | u4 | Unknown; 0 in every sample. |
| 0x1C | 2 | u2 | Unknown; 0 in every sample. |
| 0x1E | 10 | bytes[10] | Unknown; 0 in every sample. |
| 0x28 | 2 | u2 | Unknown; 1 in the non-zero records. |
| 0x2A | 2 | u2 | Unknown; 25 in the non-zero records. |
| 0x2C | 4 | u4 | Unknown; 55 in the non-zero records. |
| 0x30 | 2 | u2 | Unknown; 0 in every sample. |
| 0x32 | 2 | u2 | Unknown; 0 in every sample. |
| 0x34 | 4 | bytes[4] | Unknown; `01 00 00 00` in the non-zero records. |

### Root-level settings strings

Four [`Utf8`](#utf8) chunks sit directly under the root, each identified by
the chunk just before it (no other root-level `Utf8` occurs in the
samples):

| Preceding chunk | `Utf8` content |
|---|---|
| [`pcms`](#pcms) | [Colour-management settings JSON](#colour-management-settings-json). |
| [`PwCs`](#pwcs) | Working colour space: a [colour-profile envelope](#colour-profile-envelope) or `{}`. |
| [`pdvc`](#pdvc) | Display colour space: a colour-profile envelope or `{}`. |
| [`wsnm`](#wsnm) | The workspace name again, in UTF-8. |

The other project-setting strings are inside lists:
[`LIST:gpuG`](#listgpug) (GPU renderer), [`LIST:sfnm`](#listsfnm) (Solids
folder name) and [`LIST:ExEn`](#listexen) (expression engine). Find each
JSON by its marker, never by position or content: an unset slot holds a
literal `{}`, so "the first envelope in the file" is the display space
whenever the working space is unset.

### Colour-profile envelope

AE stores a colour space as text in one JSON shape, the colour-profile
envelope, always in a [`Utf8`](#utf8) chunk that follows a marker chunk:
the project working space ([`PwCs`](#pwcs)), the project display colour
space ([`pdvc`](#pdvc)), and the footage colour slots of
[`LIST:CLRS`](#listclrs) (`mcsp`/`Mcsp`: the colour space the media itself
carries; `ocsp`: the colour space assigned to the footage). Output modules
([`LIST:LOm`](#listlom)) store no envelope, only a 16-byte id (see
[Profile IDs](#profile-ids)).

```
{"baseColorProfile":{"colorProfileData":"<base64>","colorProfileName":"<name>"},"baseProfileType":<n>}
```

- Compact JSON (no whitespace), keys in exactly this order (alphabetical).
- `colorProfileData` is standard base64 with `=` padding.
- `{}` means the slot is unset.
- No sample has a non-ASCII name, so how AE escapes one is not verified.

#### Profile types

| `baseProfileType` | `colorProfileData` decodes to | `colorProfileName` | Seen in |
|---|---|---|---|
| 1 | 8 bytes `01 00 00 00 FF FF FF FF` (meaning unknown) | A built-in video colour description: `BT.709,10-bit,Display-Referred`, `BT.709,32f,Display-Referred`. One sample has `BT.709 RGB Full` with no `colorProfileData` key at all. | Footage slots only. |
| 2 | A complete ICC profile (bytes 36-39 `acsp`) | The profile's `desc` text, verbatim (every sample), e.g. `sRGB IEC61966-2.1`. | `PwCs` (Adobe mode), footage. |
| 3 | A small UTF-8 JSON naming OCIO colour spaces | Depends on the [selection kind](#ocio-selections). | `PwCs`, `pdvc` and footage in OCIO mode. |

An embedded ICC profile is stored as-is: its own profile-ID field (bytes
84-99) is zero in most samples and equals the computed ID in the rest.
Working-space profiles can be large (50,152 bytes for `ACEScct`).

#### OCIO selections

The `baseProfileType` 3 data is a compact JSON object with, in this order,
`colorSpace1` (string), `colorSpace2` (string, display + view only) and
`ocioColorSpaceType` (1 = display + view, 2 = role or alias, absent for a
direct pick). Which bytes AE writes depends only on what kind of name was
picked from the OCIO configuration:

| Selection | `colorProfileName` | `colorProfileData` |
|---|---|---|
| A colour space, including display colour spaces | `<family>/<name>` (presumably just `<name>` when the colour space has no family) | `{"colorSpace1":"<name>"}` |
| A role | The role's target colour space name | `{"colorSpace1":"<target>","ocioColorSpaceType":2}` |
| An alias | The alias | `{"colorSpace1":"<alias>","ocioColorSpaceType":2}` |
| A display + view | `<display>/<view>` | `{"colorSpace1":"<display>","colorSpace2":"<view>","ocioColorSpaceType":1}` |

Examples from samples: `ACES/ACEScg yo` + `{"colorSpace1":"ACEScg yo"}`
(colour space `ACEScg yo` of family `ACES`); role `mari_int16` stored as
`sRGB (mari_int16)` + `{"colorSpace1":"sRGB (mari_int16)","ocioColorSpaceType":2}`;
`sRGB yo/Un-tone-mapped yo` (display + view).

- The rule holds for every slot (working space, display, footage, output
  module ids) and is independent of the AE version: AE 25.6 and AE 26.3
  write byte-identical envelopes for the same pick, and one AE build
  writes both shapes for different picks.
- A role is stored as its target, so the role itself cannot be recovered
  (several roles often share one target).
- A family can share a display's name (in the built-in `ACES 1.2`
  configuration, `ACES` is both the only display and the family of
  `ACES - ACEScg`). Classify `A/B` as display + view only when `B` is a
  view of display `A`.
- Footage imported into an OCIO project (measured on AE 2026 with three
  configurations): AE assigns the colour space chosen by the
  configuration's file rules, taking the first rule that matches
  (`Default` matches every file; a `regex` rule by regular-expression
  search on the path; a `pattern` + `extension` rule by glob on the stem
  and the extension, case-insensitively). It stores the rule's colour
  space as a direct pick even when the rule names a role:
  `colorProfileName` = `<family of the colour space it resolves to>/<rule value>`,
  data `{"colorSpace1":"<rule value>"}` (e.g. `Utility/scene_linear`). A
  configuration without file rules gives its `default` role, in the role
  shape.

#### Profile IDs

Several chunks refer to a colour space by a 16-byte id instead of an
envelope: [`cpid`](#cpid), the key of each [`pprf`](#pprf), the footage
ids `epid` (embedded profile) and `apid` (assigned profile) in
[`LIST:CLRS`](#listclrs), and the output colour space in the output module
settings ([`LIST:LOm`](#listlom)).

**ICC colour spaces (Adobe mode)** use the ICC profile ID of ISO 15076-1
(ICC.1:2010, 7.2.18): the MD5 digest of the complete profile with bytes
44-47 (profile flags), 64-67 (rendering intent) and 84-99 (profile ID)
set to zero. This holds for every id in the samples that has its profile
in the file (all 699 `cpid`/`PwCs` pairs, and the pool entries that
`cpid`, `epid` and `apid` values refer to). Two profiles that differ only
in the rendering-intent field get the same id. Test vector: AE's
3,144-byte `sRGB IEC61966-2.1` profile gives
`1d3fda2edb4a89ab60a23c5f7c7d81dd`; more are in the [`cpid`](#cpid) table.
An output module names an Adobe output colour space by this id alone,
without the profile bytes.

**`FF` x 16** means "no profile / not an ICC colour space": `cpid` when
the working space is None or OCIO, `apid` for unassigned footage and for
all OCIO footage (whose colour space is the `ocsp` envelope), `epid` when
the media has no embedded profile, and the output module value for
"Working Color Space" (together with the module's working-space flag).

#### OCIO output colour-space id

An output module whose colour space is an OCIO selection stores neither an
envelope nor a name, only a 16-byte id derived from the selection's
envelope (the kinds above). The id depends only on the selection, not on
the configuration file's path or date. py_aep computes it
(`OutputModule.output_color_space`) and reads it back by matching the ids
of the selections the project's OCIO configuration offers.

## Items, folders and compositions

The project's items (folders, compositions and footage) live in one tree rooted
at [`LIST:Fold`](#listfold), the root folder. Every item is a
[`LIST:Item`](#listitem) whose first fixed-size chunk, [`idta`](#idta), gives its
type, id and label. Folder contents are purely physical: an item belongs to
the folder whose container holds it (the root [`LIST:Fold`](#listfold) or a
folder's [`LIST:Sfdr`](#listsfdr)). There is no parent-folder id anywhere, and
moving an item to another folder means moving its whole block of chunks
(observed on AE 2026: `item.parentFolder = folder` relocates the block and
appends it at the end of the destination container).

Item ids and layer ids come from one project-wide counter: the next free id is
stored in [`head`](#head), and the same counter numbers items, real layers and
the composition view layers described below. AE trusts that counter on open
and does not rescan the ids (a stale counter made AE hand out duplicate layer
ids), so a writer that adds items or layers must keep it above every id in the
file.

Besides the data the user edits, the item tree carries a lot of panel state:
every composition and footage item is followed by an *item UI record*
([`fvdv`](#fvdv) ... [`fifl`](#fifl)) describing its viewer and Timeline
tabs, every composition by a [`LIST:FEE`](#listfee) Timeline panel record,
and every layer inside a composition by an Effect Controls record
([`LIST:Ewst`](#listewst)) and two more item UI records. Most of these bytes
are opaque, but AE requires several of them to be present.

A composition also carries eleven *view layers*: hidden layers that hold the
cameras of the 3D views (Default, Front, Left, Top, Back, Right, Bottom,
Custom View 1-3) and the composition markers. AE cannot open a composition
without them (it crashes), so a writer creating a composition has to emit the
whole skeleton, see [Minimal composition item](#minimal-composition-item).

### `LIST:Fold`

The root folder of the project. It is not itself an item: it has no
[`idta`](#idta) or name, and its children are the root-level items.

**Parent:** [root](#root-chunk-order) · **py_aep:** `ListChunk`

| Child | Occurs | Description |
|---|---|---|
| [`fdta`](#fdta) | 1, first | Root folder record. |
| item block | 0+ | One per root-level item, see below. |

An *item block* is the item's [`LIST:Item`](#listitem) followed by the panel
state AE stores for it in the parent container:

| Item type | Block |
|---|---|
| Folder | [`LIST:Item`](#listitem) only. |
| Composition | [`LIST:Item`](#listitem), [`LIST:FEE`](#listfee), one [item UI record](#fvdv). |
| Footage | [`LIST:Item`](#listitem), one [item UI record](#fvdv). |

The same blocks fill a folder's [`LIST:Sfdr`](#listsfdr). AE requires the
trailing records: removing a composition's [`LIST:FEE`](#listfee) and item UI
record makes AE refuse the file ("missing data in file", probed).
Unknown chunks placed between blocks are skipped by AE.

### `fdta`

Root folder record.

**Parent:** [`LIST:Fold`](#listfold) · **Size:** 14 bytes · **py_aep:** `FdtaChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 10 | bytes[10] | 0 in every sample. |
| 0x0A | 4 | bytes[4] | Unknown. Varies between files and saves (the last byte is 0 in almost every sample). Files written with an arbitrary constant here open normally. |

### `LIST:Item`

One project item: a folder, a composition or a footage item. The children
depend on the item type; the tables below give the order AE writes. AE reads
the children in order and skips chunks it does not know, so the order is
load-bearing: AE refuses a composition whose [`cdrp`](#cdrp) is missing or
placed before [`cdta`](#cdta) ("missing data in file", probed on AE 2026),
while an unknown extra chunk is ignored.

**Parent:** [`LIST:Fold`](#listfold), [`LIST:Sfdr`](#listsfdr) · **py_aep:** `ListChunk`

#### Folder item

| Child | Occurs | Description |
|---|---|---|
| [`iide`](#iide) | 1 (AE 17 and later) | Item id, little-endian copy. |
| [`idpc`](#idpc) | 1 (AE 17 and later) | Dependency count, 0 for folders. |
| [`idta`](#idta) | 1, required | Type 1, id, label. |
| [`Utf8`](#utf8) | 1 | Folder name (may be empty). |
| [`cmta`](#cmta) | 0-1 | Comment. |
| [`sfdt`](#sfdt) | 1 | Folder flag word. |
| [`LIST:Sfdr`](#listsfdr) | 1 | The folder's contents. |

#### Composition item

Order written by AE 2022 to AE 2026 (file versions 93.40 to 97.x):

| Child | Occurs | Description |
|---|---|---|
| [`iide`](#iide) | 1 (AE 17 and later) | Item id, little-endian copy. |
| [`idpc`](#idpc) | 1 (AE 17 and later) | Number of [`idpi`](#idpi) that follow. |
| [`idpi`](#idpi) | 0+ | Ids of the compositions nested in this one. |
| [`idta`](#idta) | 1, required | Type 4, id, label. |
| [`Utf8`](#utf8) | 1 | Composition name. |
| [`cmta`](#cmta) | 0-1 | Comment. |
| [`LIST:dats`](#listdats) | 1 | Data-driven source descriptions (empty in every sample). |
| [`cdta`](#cdta) | 1, required | Composition settings. |
| [`cdrp`](#cdrp) | 1, required, after `cdta` | Drop-frame timecode flag. |
| [`comr`](#comr) | 1 (AE 17 and later) | Media-replacement wrapper flag. |
| [`LIST:PRin`](#listprin) | 1 | 3D renderer. |
| layer block | 0+ | One per layer, top layer first: [`LIST:Layr`](#listlayr), [`LIST:Ewst`](#listewst), two [item UI records](#fvdv). |
| view layer blocks | 11 | Same shape, with [`LIST:DLay`](#listdlay) x1, [`LIST:SLay`](#listslay) x6, [`LIST:CLay`](#listclay) x3, [`LIST:SecL`](#listsecl) x1, in that order. |
| [`LIST:CIFO`](#listcifo) | 1 | Essential Graphics, oldest copy. |
| [`LIST:CIF2`](#listcif2) | 1 | Essential Graphics, second copy. |
| [`LIST:CIF3`](#listcif3) | 1 | Essential Graphics, current copy. |
| [`LIST:Gide`](#listgide) | 1 | Composition guides. |
| [`LIST:Pin`](#listpin) | 0-1 | Proxy source, when the composition has a proxy. |

AE 15 (file version 92.14) samples differ: no `iide`, `idpc`, `comr`,
`LIST:DLay` or `LIST:CIF3` (so ten view layers), and an extra
[`LIST:OvdG`](#listovdg) in every layer list, view layers included.

#### Footage item

| Child | Occurs | Description |
|---|---|---|
| [`iide`](#iide) | 1 (AE 17 and later) | Item id, little-endian copy. |
| [`idpc`](#idpc) | 1 (AE 17 and later) | 0 for footage. |
| [`idta`](#idta) | 1, required | Type 7, id, label, footage-kind flags. |
| [`Utf8`](#utf8) | 1 | Item name, usually empty (see below). |
| [`LIST:Pin`](#listpin) | 1 | Main source (file, solid or placeholder). |
| [`ftgi`](#ftgi) | 1 | Footage interpretation record. |
| [`mdls`](#mdls) | 0-1 | 3D model footage only. |
| [`mdld`](#mdld) | 0-1 | 3D model footage only. |
| [`Utf8`](#utf8) | 1 | Unknown; empty in every sample. |
| [`LIST:Gide`](#listgide) | 1 | Footage viewer guides. |
| [`LIST:Pin`](#listpin) | 0-1 | Proxy source, when the item has a proxy. |

#### Item name

The first [`Utf8`](#utf8) after [`idta`](#idta) is the item name, and when AE
writes a non-empty value it is displayed verbatim (a `/` or AE's own
` 2` disambiguation suffix included).

- Folders and compositions: always the name (an empty folder name is allowed).
- Solids and placeholders: always empty. The name lives in the source's
  [`opti`](#opti) (255 UTF-8 bytes at most); renaming the item in AE rewrites
  the `opti`, not this chunk.
- File footage: empty means "derive the name from the source" (the sequence
  pattern, else `layer name/file name` for a layer of a layered file, else the
  file name). AE writes a value only when the user renames the item.
  Replacing the footage never touches this chunk, so a user-given name
  survives a replace and an empty one follows the new file.

#### Minimal composition item

AE hard-crashes on a composition item that lacks the view-state skeleton, so a
writer must emit the full child list above. What AE 2026 writes for a new,
empty composition (`items.addComp()`), and what a writer can copy:

| Chunk | Value |
|---|---|
| [`iide`](#iide), [`idpc`](#idpc) | The new item id; count 0. |
| [`idta`](#idta) | Type 4, the id, kind flags 0x20, label from the "Comp" label preference (15 on a factory install). |
| [`Utf8`](#utf8) | The name. |
| [`LIST:dats`](#listdats) | One [`numS`](#nums) = 0. |
| [`cdta`](#cdta) | See [Composition timing](#composition-timing): time 0/600, work area start 0/600 and end `0xFFFFFFFF`/600, duration in timebase units, display start 0/1. |
| [`cdrp`](#cdrp), [`comr`](#comr) | 0, 0. |
| [`LIST:PRin`](#listprin) | `ADBE Escher` / `Classic 3D`, 12-byte Classic 3D [`prda`](#prda). |
| view layers | The eleven lists of [Composition view layers](#composition-view-layers), each followed by an empty [`LIST:Ewst`](#listewst) and two default [item UI records](#fvdv). |
| [`LIST:CIFO`](#listcifo), [`LIST:CIF2`](#listcif2), [`LIST:CIF3`](#listcif3) | Each: [`LIST:CpS2`](#listcps2) (`Untitled`, `en_US`), [`LIST:CapS`](#listcaps) (`Untitled`), [`CPTm`](#cptm) 0/1, [`CROI`](#croi) 0, [`CcCt`](#ccct) 0. |
| [`LIST:Gide`](#listgide) | [`gdta`](#gdta) and a guide list with no items. |

In the parent container the item is followed by a [`LIST:FEE`](#listfee)
holding only [`ppSn`](#ppsn) and one default item UI record (`fvdv` 3, then
zeros). Every view layer takes a fresh id from the shared counter, and its
[`ldta`](#ldta) must use the record size of the file's version: 160 bytes up
to AE 2022 (file version 93.x), 164 bytes from AE 23 (94.9) on. A 164-byte
record in a file of version 93.x or older makes the composition unopenable in
every AE version ("chunk in file too big").

### `idta`

Item header: type, id, label, proxy state and footage-kind flags.

**Parent:** [`LIST:Item`](#listitem) · **Size:** 84 bytes · **py_aep:** `IdtaChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | Item type: 1 = folder, 4 = composition, 7 = footage. The only values in the samples. |
| 0x02 | 14 | bytes[14] | 0 in every sample. |
| 0x10 | 4 | u4 | Item id (`Item.id`), unique across items and layers. |
| 0x14 | 2 | bytes[2] | 0 in every sample. |
| 0x16 | 1 | u1 | Bit 0: use proxy (`AVItem.useProxy`). One sample composition has 0x02 (unknown). |
| 0x17 | 1 | u1 | Kind flags, see below. |
| 0x18 | 32 | bytes[32] | 0 in every sample. |
| 0x38 | 1 | u1 | 1 when a proxy source is assigned, whether or not it is in use; else 0. |
| 0x39 | 1 | u1 | 1 when the item has a comment ([`cmta`](#cmta)); 0 otherwise (all AE-saved samples). |
| 0x3A | 1 | u1 | Label colour index, 0 (none) to 16 (`Item.label`). |
| 0x3B | 1 | u1 | 0 in every sample. |
| 0x3C | 8 | f8 | 0.0 in every sample. |
| 0x44 | 8 | f8 | 0.0 in every sample. |
| 0x4C | 4 | u4 | 0 in every sample. |
| 0x50 | 4 | u4 | A timestamp in seconds since 1904-01-01 00:00 UTC (inferred: the values decode to dates shortly before each sample was saved, and items created at different times differ). |

Flags at 0x17:

| Bit | Mask | Meaning |
|---|---|---|
| 0 | 0x01 | Folders only. Unknown; set on about 60% of the sample folders. |
| 2 | 0x04 | Footage has audio. |
| 4 | 0x10 | Footage is a still (single image, solid, or data file). |
| 5 | 0x20 | Footage has video (pixel dimensions). Always set on compositions. |

Values observed on footage: 0x30 for still images and solids, 0x20 for movies
without audio and image sequences, 0x24 for movies with audio, 0x04 for audio
files, 0x10 for data files (CSV, TSV, JSON, MGJSON, TXT). A writer sets them
from the source's actual content.

Default labels of new items come from AE's label preferences; on a factory
install: compositions 15, folders 2, solids 1, video files, sequences and
placeholders 3, stills 5, audio-only files 7.

A writer creating an item can leave the timestamp at 0x50 at 0: such files
open normally.

### `cmta`

Item comment (`Item.comment`). AE also writes `cmta` inside a layer list for a
layer comment ([`LIST:Layr`](#listlayr)).

**Parent:** [`LIST:Item`](#listitem), [`LIST:Layr`](#listlayr) · **Size:** variable · **py_aep:** `CmtaChunk`

UTF-8 text followed by two NUL bytes in every AE-saved sample (files older
than version 92.0 use a legacy multibyte string). In an item it follows the
name [`Utf8`](#utf8); [`idta`](#idta) byte 0x39 is set when it is present.

### `iide`

Item id, little-endian copy.

**Parent:** [`LIST:Item`](#listitem) · **Size:** 4 bytes · **py_aep:** `U4LeChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 LE | Item id; equal to the [`idta`](#idta) id in every AE-saved sample. |

Written for file versions above 93.7 (AE 17 / 2020 and later): AE 15 files
have none and AE 2022-2026 write one on every new item (AE 16-18 not
measured). AE opens files in which `iide` and the `idta` id disagree (probed
both ways).

### `idpc`

Number of [`idpi`](#idpi) chunks that follow.

**Parent:** [`LIST:Item`](#listitem) · **Size:** 8 bytes · **py_aep:** `IdpcChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 LE | Count of `idpi` chunks (0 to 3 in the samples; 0 for folders and footage). |
| 0x04 | 4 | bytes[4] | 0 in every sample. |

Written for file versions above 93.7 (AE 17 and later): absent from AE 15
files, written on every new item by AE 2022-2026 (AE 16-18 not measured).
New compositions written with a count of 0 open normally.

### `idpi`

One composition this composition depends on.

**Parent:** [`LIST:Item`](#listitem) (compositions) · **Size:** 4 bytes · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 LE | Item id of a composition used as a layer source in this composition (inferred: in every sample the ids are those of the nested compositions). |

Placed between [`idpc`](#idpc) and [`idta`](#idta); file versions above 93.7.

### `sfdt`

Folder flag word.

**Parent:** [`LIST:Item`](#listitem) (folders) · **Size:** 4 bytes · **py_aep:** `SfdtChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Unknown. 1 in most samples and on every empty folder; 0 on some non-empty folders. New folders: 1. |

### `LIST:Sfdr`

A folder's contents: item blocks exactly as in [`LIST:Fold`](#listfold)
(each [`LIST:Item`](#listitem), then [`LIST:FEE`](#listfee) for
compositions, then an [item UI record](#fvdv) for compositions and footage).
Empty for an empty folder.

**Parent:** [`LIST:Item`](#listitem) (folders, last child) · **py_aep:** `ListChunk`

### `fvdv`

First chunk of an *item UI record*: the panel state of one item, or of one
layer inside a composition. The record is a flat run of sibling chunks (not a
list). AE writes one after every composition and footage item in its parent
container, and two after every layer list inside a composition (the first for
the layer's Effect Controls tab, the second for its Layer panel).

**Parent:** [`LIST:Fold`](#listfold), [`LIST:Sfdr`](#listsfdr), [`LIST:Item`](#listitem) · **Size:** 4 bytes · **py_aep:** `U4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | 3 in every sample. |

#### Item UI record

| Chunk | Occurs | Description |
|---|---|---|
| [`fvdv`](#fvdv) | 1 | Start (3). |
| [`fiop`](#fiop) | 1 | A panel of the item is open. |
| [`ftts`](#ftts) | 1 | Focus stamp. |
| [`foac`](#foac) | 1 | 1 when the first tab context follows. |
| [`fots`](#fots), [`fott`](#fott), [`fovc`](#fovc), [`fovi`](#fovi) x`fovc` | if `foac` = 1 | First tab context: Timeline (`AE Timeline`) for items, Effect Controls (`AE Effect Controls`) for layers. |
| [`fiac`](#fiac) | 1 | 1 when the viewer tab context follows. |
| [`fits`](#fits), [`fitt`](#fitt), [`fivc`](#fivc), [`fivi`](#fivi) x`fivc` | if `fiac` = 1 | Viewer tab context: `AE Composition`, `AE Footage` or `AE Layer`. |
| [`fipc`](#fipc) | 1 | Number of viewer records. |
| viewer record | x`fipc` | [`fidi`](#fidi), [`fipl`](#fipl), [`fmpl`](#fmpl) (AE 23 and later), [`fimr`](#fimr), then [`fips`](#fips) x4 for a Composition viewer or x1 for a Footage or Layer viewer. |
| [`fifl`](#fifl) | 1 | End (0). |

A closed, never-viewed item is `fvdv` 3, `fiop` 0, `ftts` 0, `foac` 0,
`fiac` 0, `fipc` 0, `fifl` 0. AE 15 production samples also contain viewer
records without [`fips`](#fips) and records whose viewer records follow
[`fifl`](#fifl). Older versions wrote further record chunks (`fiin`, `fitl`,
`fivd`, `fivs`, `fivv`, `fotl`) that current AE still accepts but no longer
writes; none appears in the samples.

### `fiop`

**Parent:** item UI record · **Size:** 1 byte · **py_aep:** `U1Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 1 when one of the item's panels is open, else 0 (inferred). |

### `ftts`

**Parent:** item UI record · **Size:** 4 bytes · **py_aep:** `U4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Focus stamp (inferred: 0 for items never shown; among open items the one whose panel was focused last has the highest value). |

### `foac`

**Parent:** item UI record · **Size:** 1 byte · **py_aep:** `U1Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 1 when [`fots`](#fots) ... [`fovi`](#fovi) follow, else 0. |

### `fots`

**Parent:** item UI record · **Size:** 2 bytes · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | Byte length of the following [`fott`](#fott) (11 or 18). |

### `fott`

Tab type name of the first tab context, ASCII, no terminator: `AE Timeline`
(items) or `AE Effect Controls` (layers).

**Parent:** item UI record · **Size:** variable · **py_aep:** raw `Chunk`

### `fovc`

**Parent:** item UI record · **Size:** 2 bytes · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | Number of [`fovi`](#fovi) that follow (1 in every sample). |

### `fovi`

**Parent:** item UI record · **Size:** 4 bytes · **py_aep:** `U4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Tab identifier (0 to 21 in the samples). |

### `fiac`

**Parent:** item UI record · **Size:** 1 byte · **py_aep:** `U1Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 1 when [`fits`](#fits) ... [`fivi`](#fivi) follow (the item has a viewer tab), else 0. |

### `fits`

**Parent:** item UI record · **Size:** 2 bytes · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | Byte length of the following [`fitt`](#fitt) (14, 10 or 8). |

### `fitt`

Viewer type name, ASCII, no terminator: `AE Composition`, `AE Footage` or
`AE Layer` (`Viewer.type`).

**Parent:** item UI record · **Size:** variable · **py_aep:** `AsciiChunk`

### `fivc`

**Parent:** item UI record · **Size:** 2 bytes · **py_aep:** `S2Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | Number of [`fivi`](#fivi) that follow (1 to 3 in the samples). |

### `fivi`

**Parent:** item UI record · **Size:** 4 bytes · **py_aep:** `U4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Viewer tab identifier; the values match the [`fidi`](#fidi) ids of the viewer records (inferred: a file with two Composition viewers of one composition has `fivi` 0 and 1 and viewer records 0 and 1). |

### `fipc`

**Parent:** item UI record · **Size:** 2 bytes · **py_aep:** `S2Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | Number of viewer records that follow (0 to 6 in the samples). |

### `fidi`

First chunk of a viewer record.

**Parent:** item UI record · **Size:** 4 bytes · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Viewer id (0 to 5 in the samples). |

### `fipl`

**Parent:** item UI record · **Size:** 2 bytes · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | Unknown. 0 in every sample except one AE 15 production file (3). |

### `fmpl`

**Parent:** item UI record · **Size:** 2 bytes · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | 3D view layout of the viewer: 0 = 1 View, 1 = 2 Views, 3 = 4 Views (from samples saved with each layout). |

Written by AE 23 and later only; AE 2022 and older files have no `fmpl`.

### `fimr`

**Parent:** item UI record · **Size:** 2 bytes · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | Unknown, 0 in most samples (inferred: the active view of a multi-view layout; 1 in a sample saved with the left view of a 2-view layout active, 0 with the right one). |

### `fips`

Options of one view of a viewer (`View.options`). A Composition viewer
record stores four (inferred: one per view of a 4-view layout); Footage and
Layer viewer records store one.

**Parent:** item UI record · **Size:** 96 bytes · **py_aep:** `FipsChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | bytes[4] | 0 in every sample. |
| 0x04 | 4 | u4 | Channels (`ViewOptions.channels`): 0 = RGB, 1 = Red, 2 = Green, 3 = Blue, 4 = Alpha, 8 = RGB Straight. |
| 0x08 | 4 | u4 | Flags: bit 0 = title/action safe, bit 1 = proportional grid. |
| 0x0C | 4 | u4 | Display flags, see below. |
| 0x10 | 4 | u4 | 0 in every sample. |
| 0x14 | 4 | u4 | Guide flags: bit 0 = guides visible, bit 1 = guides locked, bit 2 = snap to guides, bit 3 = grid. |
| 0x18 | 4 | s4 | Unknown. -32767 (`FF FF 80 01`) in most samples, small positive values otherwise. |
| 0x1C | 4 | s4 | Unknown, same pattern as 0x18. |
| 0x20 | 8 | bytes[8] | `80 FF 00 00 FF FF 00 FF` in every sample. |
| 0x28 | 2 | u2 | Region of interest top. |
| 0x2A | 2 | u2 | Region of interest left. |
| 0x2C | 2 | u2 | Region of interest bottom. |
| 0x2E | 2 | u2 | Region of interest right. |
| 0x30 | 4 | u4 | Unknown: 0, 1, 2 or 4. |
| 0x34 | 4 | u4 | Unknown: low byte 0, 2, 4 or 6; byte 0x36 rarely 0x47. |
| 0x38 | 2 | u2 | Unknown: 5 in most samples, 7 to 15 otherwise. |
| 0x3A | 2 | bytes[2] | `01 00` in every sample. |
| 0x3C | 4 | s4 | -1 in every sample but one. |
| 0x40 | 1 | u1 | Unknown: 0 or 1. |
| 0x41 | 3 | bytes[3] | 0 in every sample. |
| 0x44 | 1 | u1 | Unknown: 0 or 1. |
| 0x45 | 1 | u1 | Zoom mode: 0 = custom, 1 = Fit, 2 = Fit up to 100%. |
| 0x46 | 2 | s2 | Unknown: 0, -1, -2 or -3. |
| 0x48 | 8 | f8 | Zoom factor, 1.0 = 100% (`ViewOptions.zoom`). |
| 0x50 | 4 | f4 | Exposure in stops, -40.0 to 40.0 (`ViewOptions.exposure`). |
| 0x54 | 1 | u1 | 0 in every sample. |
| 0x55 | 1 | u1 | Bit 0: use display colour management (1 in all but one sample). |
| 0x56 | 1 | u1 | Bit 0: auto resolution (inferred). |
| 0x57 | 2 | bytes[2] | 0 in every sample. |
| 0x59 | 1 | u1 | Unknown: 0x24 or 0. |
| 0x5A | 6 | bytes[6] | 0 in every sample. |

Display flags at 0x0C (bits of the big-endian u4):

| Bit | Mask | Meaning |
|---|---|---|
| 4 | 0x00000010 | Mask and shape path visible. |
| 7 | 0x00000080 | Transparency grid (`ViewOptions.checkerboards`). |
| 12 | 0x00001000 | Fast Previews: Wireframe. |
| 14 | 0x00004000 | Rulers (`ViewOptions.rulers`). |
| 15 | 0x00008000 | Region of interest enabled. |
| 16 | 0x00010000 | Fast Previews: Adaptive Resolution. |
| 18 | 0x00040000 | Fast Previews: Fast Draft. |
| 20 | 0x00100000 | Fast Previews: Draft. |
| 26 | 0x04000000 | Draft 3D (`ViewOptions.draft3d`). |

Bits 0-3, 5, 6, 8, 10, 13, 21-23 and 27 are set in many samples; their
meaning is unknown. The fast-preview mode (`ViewOptions.fastPreview`) is off
when none of bits 12, 16, 18 and 20 is set.

### `fifl`

Last chunk of an item UI record.

**Parent:** item UI record · **Size:** 4 bytes · **py_aep:** `U4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | 0 in every sample. |

### `LIST:FEE`

Timeline panel state of a composition. The list type is `FEE ` (with a
trailing space). It follows the composition's [`LIST:Item`](#listitem) in the
parent container and is required there (see [`LIST:Fold`](#listfold)).

**Parent:** [`LIST:Fold`](#listfold), [`LIST:Sfdr`](#listsfdr) · **py_aep:** `ListChunk`

| Child | Occurs | Description |
|---|---|---|
| [`otln`](#otln) | 0-1 | Outline (twirl) state of the Timeline rows. |
| [`seq`](#seq) | 0-1 | Timeline view settings. |
| [`LIST:LSIf`](#listlsif) | 0-1 | Holds [`ACsi`](#acsi). |
| [`LIST:CTRE`](#listctre) | 0-1 | Seen once, after `LIST:LSIf`. |
| [`ppSn`](#ppsn) | 0-1 | AE 2022 and later. |

Many sample compositions have only `ppSn` (or nothing in older files),
presumably those never opened in a Timeline panel. The children depend on
each other: when `otln` is missing, AE also ignores the `seq`, `LIST:LSIf`
and `ppSn` that follow (probed: AE's resave of such a file kept only `ppSn` =
0.0).

### `otln`

Timeline outline state: one word per Timeline row.

**Parent:** [`LIST:FEE`](#listfee) · **Size:** 4 + 4 x count bytes · **py_aep:** `OtlnChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Number of entries. |
| 0x04 | 4 x count | u4[count] | One entry per row. Byte 0 holds state flags (inferred: twirl and selection state; values 0x80, 0xA0, 0xA8, 0x88 dominate), bytes 1-3 a row kind (0x11 on most rows, 0x44 on the row that starts a layer, other small values rarely). |

### `seq`

Timeline view settings. The tag is `seq ` (with a trailing space).

**Parent:** [`LIST:FEE`](#listfee) · **Size:** 74 bytes · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 8 | bytes[8] | 0 in every sample. |
| 0x08 | 4 | bytes[4] | `00 00 01 00` or zeros. |
| 0x0C | 2 | u2 | Unknown, varies (263 to 583 typical). |
| 0x0E | 4 | u4 | 0 in every sample. |
| 0x12 | 4 | u4 | Visible time range start, dividend (inferred, see below). |
| 0x16 | 4 | u4 | Visible time range start, divisor. |
| 0x1A | 4 | u4 | Visible time range end, dividend. |
| 0x1E | 4 | u4 | Visible time range end, divisor. |
| 0x22 | 4 | u4 | Unknown: 0 or 0x80000000 (rarely 0x04000000). |
| 0x26 | 4 | u4 | Unknown, varies (0 in half the samples). |
| 0x2A | 4 | u4 | Unknown, small integer (0 to 7 typical). |
| 0x2E | 4 | u4 | 0 in every sample. |
| 0x32 | 4 | u4 | Unknown flags: 0x83 in most samples; bits 8 and 9 vary. |
| 0x36 | 4 | s4 | Unknown: 0 or 1 (-1 once). |
| 0x3A | 4 | u4 | 3 in every sample. |
| 0x3E | 4 | u4 | 1 (0 in a few samples). |
| 0x42 | 8 | bytes[8] | 0 in every sample. |

The two times at 0x12 and 0x1A are the Timeline's zoomed time span (inferred:
in 767 of 788 sample compositions the span is 0 to the composition duration,
and the others show a shorter span).

### `ppSn`

**Parent:** [`LIST:FEE`](#listfee) · **Size:** 8 bytes · **py_aep:** `F8Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 8 | f8 | Unknown. 150.0 or 0.0 in the samples. |

Written for file versions above 93.29 (AE 2022 and later): AE 15 writes an
empty `LIST:FEE` after a new composition, AE 2022-2026 one holding `ppSn`
(AE 16-18 not measured). When it is missing, AE behaves as if it were 0.0
(probed: AE's resave writes 0.0).

### `LIST:LSIf`

Wrapper for one opaque 1,872-byte panel-state record. It appears in three
places, each with its own record tag.

**Parent:** [`LIST:FEE`](#listfee), [root](#root-chunk-order), [`LIST:LRdr`](#listlrdr) · **py_aep:** `ListChunk`

| Child | Occurs | Description |
|---|---|---|
| [`ACsi`](#acsi) | 1 (in `LIST:FEE`) | Timeline panel record of a composition. |
| [`AFsi`](#afsi) | 1 (at the root) | Project panel record (inferred from its position). |
| [`ARsi`](#arsi) | 1 (in `LIST:LRdr`) | Render Queue panel record. |

The root `LIST:LSIf` can be left out entirely: AE rebuilds it (a new-project
file written without it opens and saves normally in AE 2022-2026).

### `ACsi`

**Parent:** [`LIST:LSIf`](#listlsif) in [`LIST:FEE`](#listfee) · **Size:** 1872 bytes · **py_aep:** raw `Chunk`

Opaque panel state; copy it unchanged. All three records share one shape,
seen only through the samples: an 8-byte header, then 21 records of 88 bytes
(offsets 0x08 to 0x73F), then 16 bytes. Inside the 88-byte records only the
bytes at +0x10 to +0x13 (two u2 that look like an id and a size) and +0x57
(0 or 1) are ever non-zero (inferred: one record per panel column). The rest
is 0 in every sample.

### `AFsi`

**Parent:** root [`LIST:LSIf`](#listlsif) · **Size:** 1872 bytes · **py_aep:** raw `Chunk`

Same shape as [`ACsi`](#acsi). Byte 0x01 is 0x04 and byte 0x03 is 0, 1 or 4 in
the samples.

### `ARsi`

**Parent:** [`LIST:LSIf`](#listlsif) in [`LIST:LRdr`](#listlrdr) · **Size:** 1872 bytes · **py_aep:** `ArsiChunk`

Same shape as [`ACsi`](#acsi). Two bytes change when the render queue goes
from empty to one item: byte 0x03 becomes 1 (0 while the queue is empty), and
byte 0x17B (a byte of the fifth 88-byte record) is rewritten (0x73 in the
observed case). The rest can be copied unchanged.

### `LIST:Ewst`

Effect Controls panel state of one layer. AE writes one directly after every
layer list ([`LIST:Layr`](#listlayr) and the view layers) inside a
composition, followed by the layer's two [item UI records](#fvdv). It is empty
unless the layer was shown in an Effect Controls panel.

**Parent:** [`LIST:Item`](#listitem) (compositions) · **py_aep:** `ListChunk`

| Child | Occurs | Description |
|---|---|---|
| [`ewin`](#ewin) | 0-1 | Panel geometry. |
| [`ewot`](#ewot) | 0-1, after `ewin` | Outline state of the effect rows. |

### `ewin`

**Parent:** [`LIST:Ewst`](#listewst) · **Size:** 28 bytes · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | 0 in every sample. |
| 0x02 | 2 | u2 | 0 in every sample. |
| 0x04 | 2 | u2 | Unknown, varies (1121, 615, 625 ...). |
| 0x06 | 2 | u2 | Unknown, varies (358, 318 ...). |
| 0x08 | 4 | u4 | Unknown: 0 or 1. |
| 0x0C | 4 | u4 | Unknown, varies (0 in half the samples). |
| 0x10 | 4 | u4 | Unknown, varies (small values such as 13 to 29). |
| 0x14 | 8 | bytes[8] | 0 in every sample. |

The four u2 at 0x00 look like a panel rectangle (top, left, bottom, right)
(inferred).

### `ewot`

Effect Controls outline state: one word per row.

**Parent:** [`LIST:Ewst`](#listewst) · **Size:** 4 + 4 x count bytes · **py_aep:** `EwotChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Number of entries. |
| 0x04 | 4 x count | u4[count] | One entry per row: byte 0 state flags (inferred: twirl and selection), bytes 1-3 a row kind (0x11, 0x1B, 0x2A ... in the samples). |

### `cdta`

Composition settings: timing, size, background colour, motion blur and flags.

**Parent:** [`LIST:Item`](#listitem) (compositions) · **Size:** 204 bytes · **py_aep:** `CdtaChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | Horizontal resolution factor (`CompItem.resolutionFactor[0]`; 1 = Full, 2 = Half, 3 = Third, 4 = Quarter, custom 1-99). |
| 0x02 | 2 | u2 | Vertical resolution factor (`resolutionFactor[1]`). |
| 0x04 | 4 | u4 | Time scale x 256 (24.8 fixed point; 1024 = 4.0). See [Composition timing](#composition-timing). |
| 0x08 | 4 | u4 | Timebase: time units per second. |
| 0x0C | 4 | u4 | Unknown. 0 in every sample but one (650). |
| 0x10 | 4 | u4 | 600 in every sample. |
| 0x14 | 4 | s4 | Current time (`CompItem.time`), dividend. Negative values occur in AE 15 production files. |
| 0x18 | 4 | u4 | Current time, divisor (600 or the timebase). |
| 0x1C | 4 | s4 | Work area start (`workAreaStart`), dividend. Signed: AE 2026 stores -1 frame for a zero-length composition. |
| 0x20 | 4 | u4 | Work area start, divisor. |
| 0x24 | 4 | u4 | Work area end, dividend; `0xFFFFFFFF` = the work area ends at the end of the composition. |
| 0x28 | 4 | u4 | Work area end, divisor. |
| 0x2C | 4 | u4 | Duration (`CompItem.duration`), dividend. |
| 0x30 | 4 | u4 | Duration, divisor (the timebase in every AE-saved sample). |
| 0x34 | 1 | u1 | Background colour red, 0-255 (`CompItem.bgColor`). |
| 0x35 | 1 | u1 | Background colour green. |
| 0x36 | 1 | u1 | Background colour blue. |
| 0x37 | 1 | u1 | 0 in every sample. |
| 0x38 | 80 | bytes[80] | 0 in every sample. |
| 0x88 | 4 | u4 | Composition flags, see below. |
| 0x8C | 2 | u2 | Width in pixels (`CompItem.width`, 1-30000). |
| 0x8E | 2 | u2 | Height in pixels (`CompItem.height`, 1-30000). |
| 0x90 | 4 | u4 | Pixel aspect ratio, dividend (`pixelAspect`). |
| 0x94 | 4 | u4 | Pixel aspect ratio, divisor. |
| 0x98 | 4 | u4 | 0 in every sample. |
| 0x9C | 4 | u4 | Frame rate, 16.16 fixed point (`CompItem.frameRate`; 29.97 is stored as 0x001DF852). |
| 0xA0 | 4 | u4 | 0 in every sample. |
| 0xA4 | 4 | s4 | Display start time (`displayStartTime`), dividend. Negative = the time ruler starts before 0. |
| 0xA8 | 4 | u4 | Display start time, divisor. |
| 0xAC | 4 | u4 | Shutter angle in degrees, 0-720 (`shutterAngle`; 180 by default). |
| 0xB0 | 4 | u4 | 360 in every sample. |
| 0xB4 | 4 | s4 | Shutter phase in degrees, -360 to 360 (`shutterPhase`). |
| 0xB8 | 4 | u4 | 360 in every sample. |
| 0xBC | 4 | u4 | Unknown: 0, 1 or 2. |
| 0xC0 | 4 | u4 | Unknown: 0 in all but three samples. |
| 0xC4 | 4 | s4 | Motion blur adaptive sample limit (`motionBlurAdaptiveSampleLimit`, 128 by default, at most 256, at least the samples per frame). |
| 0xC8 | 4 | s4 | Motion blur samples per frame (`motionBlurSamplesPerFrame`, 2-64, 16 by default). |

Flags at 0x88 (bits of the big-endian u4):

| Bit | Mask | Meaning |
|---|---|---|
| 0 | 0x00000001 | Hide shy layers (`CompItem.hideShyLayers`). |
| 3 | 0x00000008 | Motion blur enabled (`CompItem.motionBlur`). |
| 4 | 0x00000010 | Frame blending enabled (`CompItem.frameBlending`). |
| 5 | 0x00000020 | Preserve frame rate when nested or in render queue (`preserveNestedFrameRate`). |
| 7 | 0x00000080 | Preserve resolution when nested (`preserveNestedResolution`). |
| 8 | 0x00000100 | Unknown; set on a few compositions of one production file. |
| 9 | 0x00000200 | Unknown; set on one composition. |
| 15 | 0x00008000 | Draft 3D (`CompItem.draft3d`) (inferred; no AE-saved sample sets it). |

#### Composition timing

Every time in a composition is a dividend/divisor pair; the value in seconds
is dividend / divisor. AE uses the composition's *timebase* (0x08) as the
divisor for most of them, and 600 for some initial values (a new composition
stores its current time and work area start as 0/600 and a pinned work-area
end as `0xFFFFFFFF`/600; editing them later switches to the timebase).

The timebase and the time scale (0x04) are tied to the frame rate: one frame
is 256 x time scale timebase units, so timebase = frame rate x time scale x
256. AE takes the rate to the thousandth (half up) as a reduced fraction
p/q, and gives a frame q x 2^k units with the largest k (at least 0) that
keeps the timebase under 40000. This reproduces every AE-saved sample (1 to
999 fps) and 90 rates set in AE 2026:

- NTSC rates share timebase 23976: 23.976 fps (2997/125) gets 1000 units a
  frame (time scale 3.90625), 29.97 gets 800 (3.125), 47.952 500, 59.94 400,
  119.88 200.
- Whole and binary-fraction rates get powers of two: 24 fps -> 1024 units
  (24576), 25 -> 1024 (25600), 60 -> 512 (30720), 19.5 -> 2048 (39936),
  37 -> 1024 (37888), 78.125 -> 256 (20000, not 40000), 999 -> 32 (31968).
- Other decimal rates: 7.3 -> 5120 (37376), 23.98 -> 1600 (38368),
  29.98 -> 800 (23984), 44.1 -> 640 (28224), 99.99 -> 400 (39996); a rate
  whose thousandths have no small denominator keeps k = 0, even past 40000
  (99.123 -> 1000 units, timebase 99123).
- Past 115200 even at k = 0, AE halves the units per frame until the
  timebase fits, rounds the timebase down and stores the whole units per
  frame, so the frame grid runs a hair off the rate: 120.001 fps -> 500
  units (60000, a 120 fps grid), 333.333 -> 250 (83333), 750.001 -> 125
  (93750), 998.999 -> 62 (62437, computed from 62.5 units).

The stored 16.16 frame rate (0x9C) only approximates timebase / units per
frame (29.970001220703125 for 23976 / 800); AE counts frames on the timebase
grid. A time's frame number (`displayStartFrame`, `frameTime`) is the time in
timebase units over the units per frame, rounded away from zero: a display
start stored as float32 0.0416666679 s is frame 2 at 24 fps. On the NTSC
timebase AE keeps a float32-stored start within about 1/10000 of a frame on
that frame (52/29.97 s is frame 52).

Keyframe times inside the composition are counted in the same timebase units
(see [`ldat`](#ldat)), so changing the frame rate rescales them.

AE stores whole frames: a duration, work area or current time set through the
UI or scripting is snapped to the nearest frame, half a frame rounding up,
and stored as frames x units per frame over the timebase (a 10 s composition
at 24 fps is 245760/24576). A frame-rate change re-snaps the duration, work
area start and end (unless pinned) and the current time to the new frame grid,
each independently; the display start is left alone. The work area times are
relative to the start of the composition (frame 0), not to the display start.
The display start time, when set as a time, is stored as the exact ratio of
the 32-bit float value AE holds (1/24 s is stored as 11184811/268435456);
when set as a frame it is frames x units per frame over the timebase.

### `cdrp`

Drop-frame timecode display (`CompItem.dropFrame`).

**Parent:** [`LIST:Item`](#listitem) (compositions) · **Size:** 1 byte · **py_aep:** `U1Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 1 = drop-frame timecode, 0 = non-drop. Only meaningful at 29.97 and 59.94 fps. |

Required, and it must come after [`cdta`](#cdta): AE refuses a composition
without it, or with it placed before `cdta` ("missing data in file", probed on
AE 2026).

### `comr`

**Parent:** [`LIST:Item`](#listitem) (compositions) · **Size:** 1 byte · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 1 on the composition AE created in the "Media Replacement Comps" folder to wrap the media of a Media Replacement controller; 0 elsewhere (inferred from a single sample). |

Written for file versions above 93.18 (AE 17 and later), right after
[`cdrp`](#cdrp): absent from AE 15 compositions, present in every AE
2022-2026 one (AE 16-18 not measured).

### `LIST:PRin`

The composition's 3D renderer (`CompItem.renderer`) and its options.

**Parent:** [`LIST:Item`](#listitem) (compositions) · **py_aep:** `ListChunk`

| Child | Occurs | Description |
|---|---|---|
| [`prin`](#prin) | 1 | Renderer names. |
| [`prda`](#prda) | 1, after `prin` | Renderer options; layout depends on the renderer. |

### `prin`

**Parent:** [`LIST:PRin`](#listprin) · **Size:** 104 bytes · **py_aep:** `PrinChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | bytes[4] | 0 in every sample. |
| 0x04 | 48 | char[48] | Renderer match name, ASCII, NUL-padded. |
| 0x34 | 48 | char[48] | Renderer display name, ASCII, NUL-padded. |
| 0x64 | 4 | u4 | 1 in every sample. |

| Match name | Display name | [`prda`](#prda) size |
|---|---|---|
| `ADBE Escher` | `Classic 3D` | 12 |
| `ADBE Calder` | `Advanced 3D` | 52 |
| `ADBE Ernst` | `Cinema 4D` | 20 |
| `ADBE Picasso` | `Ray-traced 3D` | 16 (renderer removed in AE 17; found only in older files) |

### `prda`

Options of the renderer named by [`prin`](#prin). The first two u4 are shared;
the rest depends on the renderer. Unknown renderers or sizes should be
copied verbatim.

**Parent:** [`LIST:PRin`](#listprin) · **Size:** 12, 16, 20 or 52 bytes · **py_aep:** `PrdaChunk` (`ClassicPrdaChunk`, `RayTracedPrdaChunk`, `Cinema4DPrdaChunk`, `AdvancedPrdaChunk`)

#### Classic 3D (12 bytes)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | 1 in every sample (inferred: format version). |
| 0x04 | 4 | u4 | 0 (inferred: renderer id). |
| 0x08 | 4 | u4 | Shadow Map Resolution menu index: 0 = Comp Size, 1 = 250, 2 = 500, 3 = 750, 4 = 1000, 5 = 1500, 6 = 2000, 7 = 3000, 8 = 4000. |

#### Ray-traced 3D (16 bytes)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | 1. |
| 0x04 | 4 | u4 | 0. |
| 0x08 | 4 | u4 | Unknown; 3 in every sample. |
| 0x0C | 4 | u4 | Unknown; 1 in every sample. |

#### Cinema 4D (20 bytes)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | 1. |
| 0x04 | 4 | u4 | 1 (inferred: renderer id). |
| 0x08 | 4 | u4 | Quality, 1-99 (25 by default). |
| 0x0C | 4 | u4 | 1 in every sample. |
| 0x10 | 4 | u4 | 0 in every sample. |

#### Advanced 3D (52 bytes)

This variant is mixed-endian: the first 20 bytes are big-endian, the rest
little-endian, in every sample.

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | 1. |
| 0x04 | 4 | u4 | 3 (inferred: renderer id). |
| 0x08 | 4 | u4 | Quality, 1-125 (8 by default). |
| 0x0C | 4 | u4 | 1 in every sample. |
| 0x10 | 4 | u4 | 0 in every sample. |
| 0x14 | 4 | u4 LE | Environment light shadow resolution: 0 = Half (2MB), 1 = Full (16MB), 2 = Double (128MB). |
| 0x18 | 4 | u4 LE | Environment light shadow smoothness, 1-20 (3 by default). |
| 0x1C | 4 | f4 LE | Casting box size X, as a fraction of the composition width in pixels (pixel aspect not applied). |
| 0x20 | 4 | f4 LE | Casting box size Y, same unit (the dialog keeps X, Y and Z equal). |
| 0x24 | 4 | f4 LE | Casting box size Z, same unit. |
| 0x28 | 4 | f4 LE | Casting box centre X, offset from the composition centre, fraction of the width. |
| 0x2C | 4 | f4 LE | Casting box centre Y, fraction of the height. |
| 0x30 | 4 | f4 LE | Casting box centre Z, fraction of the width. |

### `LIST:Layr`

One layer of a composition. Layers are stored in Timeline order, layer 1
first. The contents ([`ldta`](#ldta), the layer name [`Utf8`](#utf8),
[`LIST:tdgp`](#listtdgp), [`LIST:Gide`](#listgide) and optional trailing
chunks such as [`cmta`](#cmta) or [`mdla`](#mdla)) are described with the
layers. Inside the composition each `LIST:Layr` is directly followed by a
[`LIST:Ewst`](#listewst) and two [item UI records](#fvdv).

**Parent:** [`LIST:Item`](#listitem) (compositions) · **py_aep:** `ListChunk`

### `LIST:DLay`

The Default 3D view of a composition: a hidden camera layer named `Default`.
Same contents as [`LIST:Layr`](#listlayr). One per composition in every
sample from AE 2022 on; absent from AE 15 (92.14) samples. See
[Composition view layers](#composition-view-layers).

**Parent:** [`LIST:Item`](#listitem) (compositions) · **py_aep:** `ListChunk`

### `LIST:SLay`

The six orthographic 3D views of a composition, as hidden camera layers named
`Front`, `Left`, `Top`, `Back`, `Right` and `Bottom` (one list each, in that
order). Same contents as [`LIST:Layr`](#listlayr).

**Parent:** [`LIST:Item`](#listitem) (compositions) · **py_aep:** `ListChunk`

### `LIST:CLay`

The three custom 3D views, hidden camera layers named `Custom View 1` to
`Custom View 3`. Same contents as [`LIST:Layr`](#listlayr).

**Parent:** [`LIST:Item`](#listitem) (compositions) · **py_aep:** `ListChunk`

### `LIST:SecL`

A hidden layer named `Markers` that carries the composition markers
(`CompItem.markerProperty`): the markers are stored in its marker stream, with
times in composition time. One per composition. Same container shape as
[`LIST:Layr`](#listlayr).

**Parent:** [`LIST:Item`](#listitem) (compositions) · **py_aep:** `ListChunk`

#### Composition view layers

What AE 2026 writes for the eleven view layers of a new composition (W, H =
composition size, PAR = pixel aspect, Z = W x PAR / 0.72, which is the
50 mm camera distance; every layer's out point is the composition duration):

| List | Name | Position |
|---|---|---|
| `DLay` | `Default` | none (no Position stream) |
| `SLay` | `Front` | (W/2, H/2, -5000) |
| `SLay` | `Left` | (W/2 - 5000, H/2, 0) |
| `SLay` | `Top` | (W/2, H/2 - 5000, 0) |
| `SLay` | `Back` | (W/2, H/2, 5000) |
| `SLay` | `Right` | (W/2 + 5000, H/2, 0) |
| `SLay` | `Bottom` | (W/2, H/2 + 5000, 0) |
| `CLay` | `Custom View 1` | (W/2 - Z, H/2 - Z, -Z) |
| `CLay` | `Custom View 2` | (W/2, H/2 - Z, -Z) |
| `CLay` | `Custom View 3` | (W/2 + Z, H/2 - Z, -Z) |
| `SecL` | `Markers` | none |

The ten camera views share one property layout (a transform group with
Anchor Point, the Position above, the separated X/Y/Z positions, Scale on
`Default` and the custom views only, Z rotation, Opacity and Envir Appear,
then an empty camera options group). The `Markers` layer has its own layout
(transform group with Orientation and X/Y rotations, layer styles, extrusion
and material options). Its material options vary by release: AE 15 to AE
2023 leave out Casts Shadows, Light Transmission, Accepts Shadows, Accepts
Lights, Shadow Color and the Ambient, Diffuse, Specular, Shininess and Metal
coefficients, which AE 2024 and later write (Shadow Color alpha 0 in AE
2024, 255 from AE 2025); AE 15 also has no `ADBE Layer Sets` group there.
Measured on new compositions in AE 2022-2026 and on the AE 15 sample. The
layer records themselves are covered under
[`ldta`](#ldta): view layers need their own layer ids and the record size of
the file's version.

### `LIST:Gide`

Ruler guides. Every composition item has one (the composition's guides,
`Item.guides`); every footage item and every layer list has one too
(inferred: the Footage and Layer panel guides; empty in every sample).

**Parent:** [`LIST:Item`](#listitem) (compositions, footage), [`LIST:Layr`](#listlayr), [`LIST:DLay`](#listdlay), [`LIST:SLay`](#listslay), [`LIST:CLay`](#listclay), [`LIST:SecL`](#listsecl) · **py_aep:** `ListChunk`

| Child | Occurs | Description |
|---|---|---|
| [`gdta`](#gdta) | 1 | Header. |
| [`LIST:list`](#listlist) | 1 | Generic list: [`lhd3`](#lhd3) with item size 16, then one [`ldat`](#ldat) holding the guide items (no `ldat` when there are no guides). |

#### Guide item

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Orientation: 2 = horizontal, 1 = vertical (ExtendScript `orientationType` 0 and 1). |
| 0x04 | 4 | u4 | Position type: 0 = pixels (the only value). |
| 0x08 | 8 | f8 | Position in pixels from the top (horizontal) or left (vertical) edge; negative and fractional values are valid (AE 2026 accepts both). |

### `gdta`

**Parent:** [`LIST:Gide`](#listgide) · **Size:** 8 bytes · **py_aep:** `GdtaChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 8 | bytes[8] | 0 in every sample. |

### `LIST:dats`

Descriptions of data-driven sources used by the composition. Every sample
composition has one, holding only [`numS`](#nums) = 0.

**Parent:** [`LIST:Item`](#listitem) (compositions) · **py_aep:** `ListChunk`

| Child | Occurs | Description |
|---|---|---|
| [`numS`](#nums) | 1 | Count. |

AE can also write, after `numS`, a `LIST:dtSg` holding `LIST:dtSd` lists made
of `sTyp` (4 bytes), `dNam` and `eNam` (strings), `minV` and `maxV` (8 bytes
each) and `prec` (4 bytes, file versions above 92.2). No sample contains them,
so their layout is unverified.

### `numS`

**Parent:** [`LIST:dats`](#listdats) · **Size:** 4 bytes · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Count of data-driven source descriptions (inferred); 0 in every sample. |

### `mdls`

Settings of a 3D model footage item (an FBX file in the samples), written
after [`ftgi`](#ftgi).

**Parent:** [`LIST:Item`](#listitem) (footage) · **Size:** 64 bytes · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 8 | f8 | Unknown; 1.0 in every sample. |
| 0x08 | 2 | u2 | Unknown; 2 in every sample. |
| 0x0A | 4 | u4 | Unknown flags: 0x0A or 0x0B. |
| 0x0E | 50 | bytes[50] | Unknown. The values change from file to file with no visible pattern. |

### `mdld`

Geometry of a 3D model footage item. All values are little-endian doubles
inside the big-endian file.

**Parent:** [`LIST:Item`](#listitem) (footage), after [`mdls`](#mdls) · **Size:** 176 bytes · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 128 | f8 LE[16] | 4 x 4 transform matrix, row by row (the identity in every sample). |
| 0x80 | 24 | f8 LE[3] | Bounding box minimum X, Y, Z (inferred). |
| 0x98 | 24 | f8 LE[3] | Bounding box maximum X, Y, Z (inferred). |

### `LIST:CIFO`

Essential Graphics definition of a composition (Motion Graphics template),
oldest of three copies. [`LIST:CIF2`](#listcif2) and [`LIST:CIF3`](#listcif3)
have the same structure; AE 2022 and later write all three in a row, AE 15
wrote `CIFO` and `CIF2` only. `CIF3` is the current copy: some samples hold
fewer controllers in `CIFO` and `CIF2` than in `CIF3`. A writer adding or
removing a controller should do it in all three.

**Parent:** [`LIST:Item`](#listitem) (compositions) · **py_aep:** `ListChunk`

| Child | Occurs | Description |
|---|---|---|
| [`LIST:CpS2`](#listcps2) | 1 | Template name (`CompItem.motionGraphicsTemplateName`), per locale. |
| [`LIST:CapS`](#listcaps) | 1 | Template caption. |
| [`CPTm`](#cptm) | 1 | Time. |
| [`CROI`](#croi) | 1 | Rectangle. |
| [`CcCt`](#ccct) | 1 | Number of controllers. |
| [`LIST:CCtl`](#listcctl) | x`CcCt` | One per controller, in panel order. |

### `LIST:CIF2`

Second copy of the Essential Graphics definition; same structure as
[`LIST:CIFO`](#listcifo).

**Parent:** [`LIST:Item`](#listitem) (compositions) · **py_aep:** `ListChunk`

### `LIST:CIF3`

Current copy of the Essential Graphics definition (AE 2022 and later); same
structure as [`LIST:CIFO`](#listcifo). Readers should prefer it when present.

**Parent:** [`LIST:Item`](#listitem) (compositions) · **py_aep:** `ListChunk`

### `LIST:CpS2`

A localized string: one text per locale.

**Parent:** [`LIST:CIFO`](#listcifo) / [`LIST:CIF2`](#listcif2) / [`LIST:CIF3`](#listcif3), [`LIST:CCtl`](#listcctl) · **py_aep:** `ListChunk`

| Child | Occurs | Description |
|---|---|---|
| [`CsCt`](#csct) | 1 | Number of pairs. |
| [`Utf8`](#utf8), [`Utf8`](#utf8) | x`CsCt` | Text, then its locale (`en_US`, `de_DE` ...). |

A new composition's template name is `Untitled` / `en_US`; one sample carries
two pairs, `Unbenannt` / `de_DE` then `Unbenannt` / `en_US`. In a
[`LIST:CCtl`](#listcctl) it holds the controller name.

### `CsCt`

**Parent:** [`LIST:CpS2`](#listcps2), [`LIST:CapS`](#listcaps) · **Size:** 4 bytes · **py_aep:** `CsctChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 LE | Number of entries in the list (1 or 2 in the samples). Little-endian inside the big-endian file. |

### `LIST:CapS`

Caption strings, one per entry.

**Parent:** [`LIST:CIFO`](#listcifo) / [`LIST:CIF2`](#listcif2) / [`LIST:CIF3`](#listcif3), [`LIST:CCtl`](#listcctl) · **py_aep:** `ListChunk`

| Child | Occurs | Description |
|---|---|---|
| [`CsCt`](#csct) | 1 | Number of pairs. |
| [`CapL`](#capl), [`Utf8`](#utf8) | x`CsCt` | Pair: an id, then the text (same text as the `LIST:CpS2`). |

### `CapL`

**Parent:** [`LIST:CapS`](#listcaps) · **Size:** 4 bytes · **py_aep:** `U4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | 0 in every sample. |

### `CPTm`

**Parent:** [`LIST:CIFO`](#listcifo) / [`LIST:CIF2`](#listcif2) / [`LIST:CIF3`](#listcif3) · **Size:** 8 bytes · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | 0 in every sample. |
| 0x04 | 4 | u4 | 1 in every sample. |

Inferred: a time as dividend/divisor (0 s), probably the template's poster
time.

### `CROI`

**Parent:** [`LIST:CIFO`](#listcifo) / [`LIST:CIF2`](#listcif2) / [`LIST:CIF3`](#listcif3) · **Size:** 8 bytes · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | 0 in every sample. |
| 0x02 | 2 | u2 | 0 in every sample. |
| 0x04 | 2 | u2 | 0 in every sample. |
| 0x06 | 2 | u2 | 0 in every sample. |

Inferred: a rectangle (top, left, bottom, right).

### `CcCt`

**Parent:** [`LIST:CIFO`](#listcifo) / [`LIST:CIF2`](#listcif2) / [`LIST:CIF3`](#listcif3) · **Size:** 4 bytes · **py_aep:** `S4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | s4 | Number of [`LIST:CCtl`](#listcctl) that follow (verified on every sample). |

### `LIST:CCtl`

One Essential Graphics controller.

**Parent:** [`LIST:CIFO`](#listcifo) / [`LIST:CIF2`](#listcif2) / [`LIST:CIF3`](#listcif3) · **py_aep:** `ListChunk`

| Child | Occurs | Description |
|---|---|---|
| [`LIST:CpS2`](#listcps2) | 1 | Controller name per locale. |
| [`LIST:CapS`](#listcaps) | 1 | Controller caption. |
| [`Utf8`](#utf8) | 1 | Controller id: a lowercase UUID (36 characters). Override groups reference it (see [`LIST:OvG2`](#listovg2)). |
| [`CTyp`](#ctyp) | 1 | Controller type. |
| type-specific chunks | | See below. |
| [`CprC`](#cprc) | 1 | Number of [`LIST:CPrp`](#listcprp) that follow (big-endian here). |
| [`LIST:CPrp`](#listcprp) | x`CprC` (0 or 1) | Source property reference. |

Type-specific chunks, in order:

| `CTyp` | Controller | Chunks |
|---|---|---|
| 1 | Checkbox | [`CVal`](#cval), [`CDef`](#cdef) (1 byte each). |
| 2 | Slider | [`CVal`](#cval), [`CDef`](#cdef) (8 bytes each), [`Smin`](#smin), [`Smax`](#smax). |
| 4 | Color | [`CVal`](#cval), [`CDef`](#cdef) (16 bytes each). |
| 5 | Point | [`CVal`](#cval), [`CDef`](#cdef) (16 bytes each). |
| 6 | Source Text | [`Utf8`](#utf8) text, [`Utf8`](#utf8) text (the same in every sample), [`CFEd`](#cfed), [`CSEd`](#csed), [`CFEd`](#cfed), [`Utf8`](#utf8) font options JSON, [`Utf8`](#utf8) alternate-source JSON, [`CTov`](#ctov). |
| 10 | Group | [`LIST:StVc`](#liststvc) (the ids of the controllers in the group), [`CSGe`](#csge). |
| 13 | Dropdown | [`CVal`](#cval), [`CDef`](#cdef) (4 bytes each), [`LIST:StVc`](#liststvc) (the menu item names). |
| 14 | Media Replacement | [`Utf8`](#utf8), [`Utf8`](#utf8) (both the zero UUID `00000000-0000-0000-0000-000000000000` in the sample; inferred: no alternate source assigned yet), [`CSMw`](#csmw), [`CSMh`](#csmh), [`CSMs`](#csms), [`CSMe`](#csme), [`CSMt`](#csmt), [`CSMp`](#csmp), [`CCEx`](#ccex), [`Utf8`](#utf8) (a UUID plus the media's file extension; inferred: a thumbnail cache file name), [`CSMd`](#csmd). |

The Source Text font options JSON holds `capPropFontEdit`,
`capPropFontFauxStyleEdit`, `capPropFontSizeEdit` (booleans), `fontEditValue`
(PostScript font name), `fontFSAllCapsValue`, `fontFSBoldValue`,
`fontFSItalicValue`, `fontFSSmallCapsValue` (booleans) and `fontSizeEditValue`
(number). The alternate-source JSON is `{"compId":-1,"isEnabled":false,"layerId":-1}`
on every sample.

AE can also write `CDim` (4 bytes) and `CSLk` (1 byte) inside a `LIST:CCtl`;
no sample contains them. AE 2026 shows a Group "drop zone" in the panel that
is not stored in the file.

### `CTyp`

**Parent:** [`LIST:CCtl`](#listcctl) · **Size:** 4 bytes · **py_aep:** `U4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Controller type: 1 = Checkbox, 2 = Slider, 4 = Color, 5 = Point, 6 = Source Text, 10 = Group, 13 = Dropdown, 14 = Media Replacement (all seen in the samples). |

### `CVal`

Current value of the controller. Layout by [`CTyp`](#ctyp):

**Parent:** [`LIST:CCtl`](#listcctl) · **Size:** 1, 4, 8 or 16 bytes · **py_aep:** raw `Chunk`

| `CTyp` | Size | Layout |
|---|---|---|
| 1 | 1 | u1: 0 or 1. |
| 2 | 8 | f8: the value. |
| 4 | 16 | f4[4]: red, green, blue, alpha in 0-1 (inferred order: a red source colour reads 1, 0, 0, 1). |
| 5 | 16 | f8[2]: x, y. |
| 13 | 4 | u4: selected menu item (1 in every sample; inferred 1-based). |

AE can also write a 32-byte value (no sample). `CVal` and [`CDef`](#cdef) are
equal in every sample, and both are a copy of the source property's value at
the time the controller was added. When AE duplicates a composition, it writes
zeros in both for the copy's controllers.

### `CDef`

Default value of the controller; same layout as [`CVal`](#cval).

**Parent:** [`LIST:CCtl`](#listcctl) · **Size:** 1, 4, 8 or 16 bytes · **py_aep:** raw `Chunk`

### `Smin`

**Parent:** [`LIST:CCtl`](#listcctl) (sliders) · **Size:** 8 bytes · **py_aep:** `F8Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 8 | f8 | Slider minimum (for example -150 for Brightness, 0 for Opacity). AE can also write a 4-byte form (no sample). |

### `Smax`

**Parent:** [`LIST:CCtl`](#listcctl) (sliders) · **Size:** 8 bytes · **py_aep:** `F8Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 8 | f8 | Slider maximum (150 for Brightness, 100 for Opacity). |

### `CFEd`

**Parent:** [`LIST:CCtl`](#listcctl) (Source Text) · **Size:** 1 byte · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 0 in every sample. Appears twice per Source Text controller; together with [`CSEd`](#csed) it mirrors the three `capProp...Edit` flags of the font options JSON (inferred). |

Written for file versions above 92.16 (AE 16 and later).

### `CSEd`

**Parent:** [`LIST:CCtl`](#listcctl) (Source Text) · **Size:** 1 byte · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 0 in every sample (see [`CFEd`](#cfed)). |

Written for file versions above 92.16 (AE 16 and later).

### `CTov`

**Parent:** [`LIST:CCtl`](#listcctl) (Source Text) · **Size:** 4 bytes · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | bytes[4] | Unknown; `07 00 00 00` in every sample. |

Written for file versions above 95.1 (AE 24 and later).

### `CSGe`

**Parent:** [`LIST:CCtl`](#listcctl) (Group) · **Size:** 1 byte · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | Unknown; 1 in every sample. |

Written for file versions above 92.19 (AE 16 and later).

### `CSMw`

**Parent:** [`LIST:CCtl`](#listcctl) (Media Replacement) · **Size:** 4 bytes · **py_aep:** `U4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Width in pixels of the media slot (640 in the sample, the size of the source layer's item). |

The Media Replacement chunks `CSMw` to `CCEx` are written for file versions
above 93.12 (AE 17 and later).

### `CSMh`

**Parent:** [`LIST:CCtl`](#listcctl) (Media Replacement) · **Size:** 4 bytes · **py_aep:** `U4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Height in pixels of the media slot. |

### `CSMs`

**Parent:** [`LIST:CCtl`](#listcctl) (Media Replacement) · **Size:** 4 bytes · **py_aep:** `U4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Start of the source layer (in point) in [`CSMt`](#csmt) units. |

### `CSMe`

**Parent:** [`LIST:CCtl`](#listcctl) (Media Replacement) · **Size:** 4 bytes · **py_aep:** `U4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | End of the source layer (out point) in [`CSMt`](#csmt) units (720000 = 30.03 s at 23976). |

### `CSMt`

**Parent:** [`LIST:CCtl`](#listcctl) (Media Replacement) · **Size:** 4 bytes · **py_aep:** `U4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Divisor of `CSMs` and `CSMe`: the composition timebase (23976 in the sample). |

### `CSMp`

**Parent:** [`LIST:CCtl`](#listcctl) (Media Replacement) · **Size:** 8 bytes · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | 0 in the sample. |
| 0x04 | 4 | u4 | 1 in the sample (same bytes as [`CPTm`](#cptm)). |

### `CCEx`

**Parent:** [`LIST:CCtl`](#listcctl) (Media Replacement) · **Size:** 1 byte · **py_aep:** raw `Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | Unknown; 1 in the sample. |

### `CSMd`

**Parent:** [`LIST:CCtl`](#listcctl) (Media Replacement) · **Size:** 4 bytes · **py_aep:** `U4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Unknown; 2 in the sample. |

Written for file versions above 93.23 (AE 18 and later).

### `CprC`

Count of [`LIST:CPrp`](#listcprp) children. Its byte order depends on the
parent.

**Parent:** [`LIST:CCtl`](#listcctl), [`LIST:OvG2`](#listovg2), [`LIST:OvdG`](#listovdg) · **Size:** 4 bytes · **py_aep:** `S4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 (BE in `LIST:CCtl`, LE in `LIST:OvG2`) | Number of `LIST:CPrp` that follow: 0 or 1 in a controller, 0 to 3 in an override group (`03 00 00 00` with three `LIST:CPrp` children), 0 in `LIST:OvdG`. Verified on every sample. |

### `LIST:CPrp`

A property reference. Inside a controller it names the source property the
controller exposes; inside an override group it names a controller.

**Parent:** [`LIST:CCtl`](#listcctl), [`LIST:OvG2`](#listovg2) · **py_aep:** `ListChunk`

In a [`LIST:CCtl`](#listcctl):

| Child | Occurs | Description |
|---|---|---|
| [`CCId`](#ccid) | 1 | Item id of the composition that owns the source property. |
| [`CLId`](#clid) | 1 | Layer id of the source layer. |
| [`Utf8`](#utf8) | 1 | Path from the layer to the property, as JSON. |

The path JSON maps the positions `"0"`, `"1"`, ... (root to leaf) to
`{"index": n, "matchName": "..."}`. `index` 4294967295 (`0xFFFFFFFF`) means
"find by match name"; other values are the property's 0-based position among
all children of its parent group, counting hidden ones (so it differs from the
ExtendScript index). Example: `{"0":{"index":4294967295,"matchName":"ADBE Effect Parade"},"1":{"index":0,"matchName":"ADBE Fill"},"2":{"index":3,"matchName":"ADBE Fill-0002"}}`.

In a [`LIST:OvG2`](#listovg2): one [`Utf8`](#utf8) holding a controller id
(the UUID of a [`LIST:CCtl`](#listcctl)).

### `CCId`

**Parent:** [`LIST:CPrp`](#listcprp) · **Size:** 4 bytes · **py_aep:** `U4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Item id of the composition that owns the source property. |

### `CLId`

**Parent:** [`LIST:CPrp`](#listcprp) · **Size:** 4 bytes · **py_aep:** `U4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Layer id (the id in the layer's [`ldta`](#ldta)) of the source layer. |

When AE duplicates a composition, the copy's controllers get fresh UUIDs (the
same new UUID in all three containers), [`CCId`](#ccid) becomes the copy's
item id and [`CLId`](#clid) the matching copied layer's id.

### `LIST:OvG2`

Override group of a layer's Essential Properties: the controllers of the
layer's source composition whose overrides this layer holds. It sits inside
the layer's [`LIST:tdgp`](#listtdgp), right after the
[`tdmn`](#tdmn) `ADBE Layer Overrides`.

**Parent:** [`LIST:tdgp`](#listtdgp) · **py_aep:** `ListChunk`

| Child | Occurs | Description |
|---|---|---|
| [`CprC`](#cprc) | 1 | Count, little-endian. 0 for a layer without overrides. |
| [`LIST:CPrp`](#listcprp) | x`CprC` | One controller id each (inferred: in the order of the override properties). |

### `LIST:OvdG`

An older override container found only in AE 15 (92.14) samples, which
also have [`LIST:OvG2`](#listovg2): a child of the layer list itself
([`LIST:Layr`](#listlayr), [`LIST:SLay`](#listslay),
[`LIST:CLay`](#listclay), [`LIST:SecL`](#listsecl)), after its
[`LIST:Gide`](#listgide), holding a single [`CprC`](#cprc) = 0. Not written
by AE 2022 or later.

**Parent:** [`LIST:Layr`](#listlayr), [`LIST:SLay`](#listslay), [`LIST:CLay`](#listclay), [`LIST:SecL`](#listsecl) · **py_aep:** `ListChunk`

## Footage

A footage item is a [`LIST:Item`](#listitem) whose [`idta`](#idta) says
"footage". Its source - a file, an image sequence, a solid or a placeholder -
is a [`LIST:Pin`](#listpin): the cached media properties
([`sspc`](#sspc)), the importer's own record ([`opti`](#opti)), the file path
([`LIST:Als2`](#listals2)), the colour-management settings
([`LIST:CLRS`](#listclrs)) and the media timecode ([`LIST:mnfo`](#listmnfo)).
A proxy is a second `LIST:Pin` of the same shape. The item itself adds
[`ftgi`](#ftgi) after its main source.

After Effects caches what it knows about the media in the project and does not
re-read the file on open while the file's modification time matches the one
stored in [`sspc`](#sspc) (0x76): a PNG whose stored size was patched to 7x7
opens as 7x7, footage found and all (AE 2026). A writer therefore has to put
correct dimensions, duration, frame rate, alpha, pixel depth and audio
information into `sspc`. AE does check the structure against its own importer,
in both directions: an `sspc` that claims a video track the importer cannot
decode opens as missing footage, one that claims audio only for a file whose
video AE can decode opens with a "problem accessing the audio or video data"
warning and renders nothing (AE 2026, MP4 files).

Layouts below were reverse-engineered from the files AE writes; the samples
are the 5,359 `LIST:Pin` of the py-aep sample corpus (file versions 92.14 -
the AE CC 2018 era samples - up to 97.7).

### `LIST:Pin`

One footage source (list type `Pin ` with a trailing space).

**Parent:** [`LIST:Item`](#listitem) (footage items and, for a proxy,
compositions)

| Child | Occurs | Description |
|---|---|---|
| [`sspc`](#sspc) | 1, first | Cached source settings. |
| [`Utf8`](#utf8) | 1 | Name of the referenced layer when the source is one layer of a layered PSD/PSB/AI/PDF file (`inner`, `Calque 2`); empty otherwise. |
| [`LIST:Als2`](#listals2) | 0-1 | Path of the file, or of the folder of an image sequence. Absent for solids and placeholders. |
| [`Utf8`](#utf8), [`Utf8`](#utf8) | 0 or 2 | Numbered image sequence only: the file-name text before the frame number, then the extension with its dot (`sequence_`, `.gif`). |
| [`LIST:StVc`](#liststvc) | 0-1 | Alphabetical image sequence only, in place of the two `Utf8`: the frame file names. |
| [`opti`](#opti) | 1 | Importer record; layout depends on the importer. |
| [`pgui`](#pgui) | 1 | A 16-byte GUID; differs between otherwise identical imports. |
| [`LIST:CLRS`](#listclrs) | 1 | Colour-management settings. |
| [`LIST:mnfo`](#listmnfo) | 1 | Media start timecode. |
| [`Utf8`](#utf8) | 1, last | Empty in every sample. |

Child orders in the samples: `sspc Utf8 LIST:Als2 opti pgui LIST:CLRS
LIST:mnfo Utf8` (file footage, 2,379), `sspc Utf8 opti pgui LIST:CLRS
LIST:mnfo Utf8` (solids and placeholders, 2,051), `sspc Utf8 LIST:Als2 Utf8
Utf8 opti ...` (numbered sequences, 621) and `sspc Utf8 LIST:Als2 LIST:StVc
opti ...` (alphabetical sequences, 126). Write them in this order.

**Main source and proxy.** In a footage item the first `LIST:Pin` sits right
after the item's name [`Utf8`](#utf8) and before [`ftgi`](#ftgi): it is the
main source. A proxy is a second `LIST:Pin` placed as the very last child of
the `LIST:Item`, after [`LIST:Gide`](#listgide). A composition has no main
source; when it has a proxy, that proxy is its only `LIST:Pin`, again the last
child. Whether the proxy is in use is a flag of [`idta`](#idta)
(`AVItem.useProxy`). Sample: `models/item/proxy.aep` (a QuickTime movie with
a PNG proxy, and two compositions with PNG proxies).

#### Source kinds

How each kind of footage is represented:

- **File footage.** [`sspc`](#sspc) holds the importer's source format code
  (0x16), `01 01` at 0x40, 1 at 0x4F and the file's modification time at
  0x76. [`LIST:Als2`](#listals2) holds the absolute path. The item's display
  name is the item-level [`Utf8`](#utf8), written only when the user renames
  the item; empty means "derived from the file" (sequence pattern, else
  `layer/file` for a layer, else the file name).
- **Solid.** `sspc` code `Soli`, the solid's size, a zero duration, alpha byte
  3 (no alpha), `00 00` at 0x40, 0 at 0x4F, `0x00010000` at 0x68 and 0x6C, 1
  at 0x86; 0x76 holds a time stamp in the same encoding as a file's (dates in
  the samples suggest the creation or last edit of the solid). No
  `LIST:Als2`. The colour and the item's name live in the
  [solid record](#solid-record-soli) of `opti`; the item-level `Utf8` stays
  empty. [`LIST:CLRS`](#listclrs) has `ipws` 1, `dcui` and `prgb`.
- **Placeholder.** `sspc` code is four NUL bytes; size, duration in seconds
  and the placeholder's frame rate in the native-rate slot (0x3A, conform 0);
  bit 0 of byte 0x73 (missing) set; no time stamp; layer index (0xC0)
  0xFFFFFFFE for a placeholder created with Import > Placeholder, 0xFFFFFFFF
  on others seen in AE 2026 files. No `LIST:Als2`. The name lives in the
  [placeholder record](#placeholder-record) of `opti`. ExtendScript reports
  it as missing footage.
- **Numbered image sequence.** `sspc` 0xA8 = 2, first and last frame numbers,
  digit count and zero-padding flag (0xAC-0xB8), `01 01` at 0xBA; AE 2026
  opens a sequence written without 0xA8 and these flags as missing. The path
  is the folder (`target_is_folder` true), followed by the two `Utf8`
  (prefix, extension). The time stamp is the folder's modification time. The
  sequence's rate is the native rate (0x3A) with conform 0; the stored
  duration is frame count over that rate, unreduced (3 frames at 30 fps =
  3/30). A new sequence's rate comes from AE's "Sequence Footage" import
  preference (factory 30), not from the project.
- **Alphabetical image sequence** (imported with "Force alphabetical
  order"): `sspc` 0xA8 = 1, first and last frame 0xFFFFFFFF, digit count 0,
  0xB8 and 0xBA 0, byte 0x74 = 1. The frames are listed by name in
  [`LIST:StVc`](#liststvc): every file of the same extension in the folder
  (extension compared case-insensitively), sorted by lower-cased name (`n_10`
  before `n_2`). The item is named after the folder. Sample:
  `models/footage/sequence_alphabetical.aep`.
- **One layer of a layered file** (Composition import, or a layer chosen in
  the import dialog). `sspc` 0xBC (Photoshop layer id), 0xC0 (layer index),
  0xC7 (full frame or cropped) and 0xC9 (layer-style handling); the layer's
  name in the `Utf8` after `sspc`; the layer is described again in `opti`
  ([Photoshop](#photoshop-and-tiff-record-8bps-tif) /
  [Illustrator](#illustrator-eps-and-pdf-record-text)). Every layer is its own
  footage item pointing at the same file.
- **Missing footage.** Stays file footage with all its cached values; only
  bit 0 of `sspc` byte 0x73 is set when the file was missing when the project
  was saved (`models/footage/footage_missing.aep` and
  `footage_not_missing.aep` differ in that bit only).
  `FileSource.missingFootagePath` is the stored path.

### `sspc`

Cached properties of the footage source (Interpret Footage settings included).
Not to be confused with the effect list [`LIST:sspc`](#listsspc).

**Parent:** [`LIST:Pin`](#listpin) · **Size:** 222 bytes · **py_aep:** `SspcChunk`

Every sample is 222 bytes. AE also reads a 286-byte form used by older
project versions; no sample contains it.

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 22 | bytes | 0 in every sample. |
| 0x16 | 4 | fourcc | Source format code of the importer (see [Source format codes](#source-format-codes)); `Soli` for a solid, four NUL bytes for a placeholder and for text/CSV data files. |
| 0x1A | 4 | bytes | 0 in every sample. |
| 0x1E | 4 | u4 | Width in pixels (`AVItem.width`); 0 for audio-only and data footage. |
| 0x22 | 4 | u4 | Height in pixels. |
| 0x26 | 4 | u4 | Duration dividend. |
| 0x2A | 4 | u4 | Duration divisor; duration in seconds = dividend / divisor. A still stores 0 over any divisor (usually the time base, 600). A movie uses its own time scale (2631/24). An image sequence stores frame count x rate denominator over rate numerator, unreduced (12/24, 1200/2997). |
| 0x2E | 4 | bytes | 0 in every sample. |
| 0x32 | 4 | u4 | Time base: a movie's own time scale (24, 25, 30, 2997, 23829; 14989 for a WMV, 749 for a SWF, 10 for an animated GIF); 600 for everything else (stills, sequences, audio, data, solids, placeholders). |
| 0x36 | 4 | bytes | 0 in every sample. |
| 0x3A | 4 | fixed 16.16 | Native frame rate (`FootageSource.nativeFrameRate`); 0 for stills, audio and solids. For a sequence or a placeholder, the rate it is played at (see 0x94). |
| 0x3E | 2 | s2 | Pixel depth as an `AEIO_InputDepth` value (see [Pixel depth](#pixel-depth)). |
| 0x40 | 2 | bytes | `01 01` on every file source, `00 00` on solids and placeholders. |
| 0x42 | 3 | bytes | 0 in every sample. |
| 0x45 | 1 | u1 | Alpha flags: bit 0 premultiplied (see [Alpha](#alpha)), bit 1 invert alpha (`FootageSource.invertAlpha`). Other bits 0. |
| 0x46 | 3 | u1[3] | Premultiplied matte colour, red, green, blue, 0-255 (`FootageSource.premulColor`). |
| 0x49 | 1 | u1 | Alpha interpretation: 0 Straight, 1 Premultiplied, 2 Ignore, 3 the source has no alpha channel (`FootageSource.hasAlpha` false). |
| 0x4A | 4 | fourcc | `FIEL` for media that declares its field order (QuickTime `fiel`), else 0. |
| 0x4E | 1 | u1 | 0 in every sample. |
| 0x4F | 1 | u1 | 1 when the source is read from a file, 0 on solids and placeholders (every sample from AE 2022 on; some file sources in 92.14 projects have 0). |
| 0x50 | 3 | bytes | 0 in every sample. |
| 0x53 | 1 | u1 | Separate Fields: 0 off, 1 on (`FootageSource.fieldSeparationType` is OFF when 0). |
| 0x54 | 3 | bytes | 0 in every sample. |
| 0x57 | 1 | u1 | Field order when 0x53 is 1: 0 upper field first, 1 lower field first. |
| 0x58 | 8 | bytes | 0 in every sample. |
| 0x60 | 2 | u2 | 3 when the source has audio, else 0 (inferred: sample format of AE's decoded audio, 32-bit float; a 16-bit mono AIFF also stores 3). |
| 0x62 | 2 | u2 | 4 when the source has audio, else 0 (inferred: bytes per decoded sample). |
| 0x64 | 2 | u2 | Audio channel count (1 for the mono AIFF samples, 2 for stereo), 0 without audio. |
| 0x66 | 2 | bytes | 0 in every sample. |
| 0x68 | 4 | u4 | `0x00010000` on solids and placeholders, 0 on file sources (every sample). Unknown. |
| 0x6C | 4 | u4 | Same values as 0x68. Unknown. |
| 0x70 | 4 | u4 | Source flags (table below). |
| 0x74 | 1 | u1 | 1 on an alphabetical image sequence, else 0. |
| 0x75 | 1 | u1 | 0 in every sample. |
| 0x76 | 4 | u4 | Source modification time, seconds since 1904-01-01 (Unix time + 2082844800): the file's for a single file, the folder's for an image sequence; 0 for a placeholder and for media AE has never found. See [Modification time](#modification-time). |
| 0x7A | 3 | bytes | 0 in every sample. |
| 0x7D | 1 | u1 | 0x0C in every sample. |
| 0x7E | 4 | u4 | Loop count (`FootageSource.loop`), 1 = play once. |
| 0x82 | 4 | bytes | 0 in every sample. |
| 0x86 | 1 | u1 | 1 on solids and placeholders, 0 on file sources (every sample). Unknown. |
| 0x87 | 1 | u1 | 0 in every sample. |
| 0x88 | 4 | u4 | Pixel aspect ratio dividend. |
| 0x8C | 4 | u4 | Pixel aspect ratio divisor (`AVItem.pixelAspect` = dividend / divisor; samples: 1/1, 4/3, 10/11, 768/702, 2/1, 8950645/8388608). |
| 0x90 | 4 | u4 | Remove Pulldown (`FootageSource.removePulldown`): 0 off; 1-5 the 3:2 phases WSSWW, SSWWW, SWWWS, WWWSS, WWSSW; 6-10 the 24Pa phases WWWSW, WWSWW, WSWWW, SWWWW, WWWWS. AE refuses a file with a phase 1-5 and Separate Fields off ("field order must be set before 3:2 pulldown can be removed"); phases 6-10 need no field order. |
| 0x94 | 4 | fixed 16.16 | Conform frame rate ("Assume this frame rate", `FootageSource.conformFrameRate`); 0 = use the native rate. Sequences and placeholders keep an assumed rate in 0x3A instead and leave this 0. |
| 0x98 | 4 | fixed 16.16 | Display frame rate (`FootageSource.displayFrameRate`) = (conform rate, or native rate when it is 0) x 0.8 when 0x90 is not 0. Every sample satisfies this. |
| 0x9C | 4 | u4 | Interpretation flags (table below). |
| 0xA0 | 8 | f8 | Audio sample rate in Hz (48000.0, 44100.0); 0.0 = no audio. |
| 0xA8 | 4 | u4 | Sequence kind: 0 single file, 1 alphabetical image sequence, 2 numbered image sequence. |
| 0xAC | 4 | u4 | First frame number; 0xFFFFFFFF for an alphabetical sequence; 0 for a single file. |
| 0xB0 | 4 | u4 | Last frame number; 0xFFFFFFFF for an alphabetical sequence. |
| 0xB4 | 4 | u4 | Frame-number digit count, taken from the first frame (`s1.png` ... `s12.png` gives 1, `frame_0001.png` 4); 0 for single files and alphabetical sequences. |
| 0xB8 | 1 | u1 | 1 when the frame numbers are zero-padded (the first frame's number has fewer digits than 0xB4: `z_0410.png`), 0 otherwise (`p410.png`). |
| 0xB9 | 1 | u1 | 1 when the sequence was imported with a user-set frame range (AE 2026 probe); 0 in every sample. |
| 0xBA | 1 | u1 | 1 on numbered sequences (618 of the 622 samples), else 0. Unknown. |
| 0xBB | 1 | u1 | 1 on every numbered sequence, else 0. Unknown. |
| 0xBC | 4 | u4 | Photoshop layer id (`lyid`) of the referenced layer; 0xFFFFFFFF when the source is not one Photoshop layer (whole files, merged Photoshop footage, Illustrator/PDF layers, which have no id). |
| 0xC0 | 4 | u4 | Index of the referenced layer: for Photoshop the 0-based position among the document's layer records, counting the group start and end records (bottom first); for Illustrator/PDF the position in the document's optional-content group list. 0xFFFFFFFF for a whole file; placeholders store 0xFFFFFFFE (see [Source kinds](#source-kinds)). |
| 0xC4 | 3 | bytes | 0 in every sample. |
| 0xC7 | 1 | u1 | Full frame: 1 when the source spans its file's whole frame (every ordinary import, and a chosen layer imported at Document Size), 0 for a layer cropped to its content box (Composition - Retain Layer Sizes, or a chosen layer at Layer Size). Solids and placeholders 0. See the note on scripted imports below. |
| 0xC8 | 1 | u1 | 0 in every sample. |
| 0xC9 | 1 | u1 | Layer handling. Photoshop composition layers: 0 Ignore Layer Styles, 1 Merge Layer Styles into Footage, 2 Editable Layer Styles (also every style-less file); Photoshop footage imported with "Merged Layers" chosen in the import dialog 3 (a scripted import of the whole file stores 2); a chosen Photoshop layer 1 (0 when its styles are ignored, inferred). Illustrator/PDF composition layers 0; a chosen Illustrator layer 2. Ordinary raster, vector, movie and audio footage (whole-document AI/EPS/PDF included) 2. Solids and placeholders 0. |
| 0xCA | 2 | bytes | 0 in every sample. |
| 0xCC | 8 | u8 | Cached data size in bytes (samples up to 14,729,427,240): a single file's size on disk; for a numbered sequence the first frame's size times the frame count; for merged Photoshop footage and TIFF stills the decoded image instead, width x height x channels x bytes per channel (the channel count of the [`opti`](#opti) record: colour channels, plus one for alpha except a flattened Photoshop file's alpha channel); for one Photoshop layer its content box's pixels the same way. AE recomputes it when it re-reads the media, so 0 is accepted. |
| 0xD4 | 1 | u1 | 1 in most samples, 0 on many movies; equal to [`drop`](#drop) in all but one sample. Unknown. |
| 0xD5 | 1 | u1 | 0 except on one movie. Unknown. |
| 0xD6 | 4 | u4 | Time dividend: 0 in most samples; on some movies in 92.14 projects the media's start timecode as a time (86400/24 = 01:00:00:00, 10800000/2997, 14532/25), matching [`strt`](#strt). |
| 0xDA | 4 | u4 | Time divisor: 0, or the media's time scale (24, 25, 30, 2997). |

Source flags at 0x70 (a big-endian u4; byte 0x73 holds bits 0-7):

| Bit | Mask | Meaning |
|---|---|---|
| 0 | 0x00000001 | Footage missing when the project was saved (`AVItem.footageMissing`); set on every placeholder. |
| 11 | 0x00000800 | Byte 0x72 bit 3. AE 2026 sets it on image sequences imported by script and on footage replaced by script (together with 0xC7 = 0 and 0xC9 = 0, see below); an import through the Import dialog leaves it clear. Also common on sequences in 92.14 projects. Rendering is the same either way (AE 2026). Meaning unknown. |
| 19 | 0x00080000 | Byte 0x71 bit 3. Seen on Photoshop footage in 9 sample files. Unknown. |
| 21 | 0x00200000 | Byte 0x71 bit 5. Seen only in 92.14 files, on movie, audio and JPEG footage. Unknown. |
| 27 | 0x08000000 | Byte 0x70 bit 3. Media format: set by AE 2025 and later imports on JPEG, BMP/GIF, HEIC, movie, audio and data footage, single files and sequences alike. |

All other bits are 0 in every sample.

Interpretation flags at 0x9C (a big-endian u4; byte 0x9F holds bits 0-7):

| Bit | Mask | Meaning |
|---|---|---|
| 0 | 0x00000001 | Preserve Edges (`FootageSource.highQualityFieldSeparation`). |
| 3 | 0x00000008 | Media file: as bit 27 of 0x70, for single files only (clear on sequences). AE restores it from the media when it saves (an AE 2026 file with it cleared opens normally and resaves with it set). |

All other bits are 0 in every sample.

**Scripted imports.** AE 2026's scripted `importFile` of an image sequence
and every scripted `replace`/`replaceWithSequence` write 0xC7 = 0, 0xC9 = 0
and bit 11 of 0x70, and keep 0x4F from the old source; the Import dialog
writes 1 / 2 / clear for the same files. Stills and movies get 1 / 2 / clear
either way. Rendering does not change (AE 2026 render comparison); a writer
should use the dialog values.

#### Alpha

The alpha byte (0x49) and bit 0 of the alpha flags (0x45) must agree:
Premultiplied (1) goes with the bit set, Straight (0) and Ignore (2) with it
clear. When the byte says Premultiplied and the bit is clear, AE 2026 resets
the footage to Straight alpha on open. The exception is an FBX scene (`LDOM`):
AE sets the bit while the byte stays Straight. Six items in an older
production sample carry byte 1 with the bit clear.

AE's own import picks Straight for most formats with alpha and Premultiplied
for OpenEXR; a source without alpha stores 3.

#### Pixel depth

0x3E is the source's pixel depth as an AE SDK `AEIO_InputDepth` value: 24,
48 and 96 for RGB at 8, 16 and 32 bits per channel, 32, 64 and 128 with
alpha; 40, -16 and -32 for 8, 16 and 32-bit grayscale; 34 and 36 for 2 and
4-bit grayscale; 1 for 1-bit; 8 for indexed colour; 0 for media without
video. What AE 2026 writes:

| Format | Depth |
|---|---|
| PNG | grayscale stays grayscale (1, 34, 36, 40, -16); palette files 32; a `tRNS` chunk adds alpha (0x49) without changing the depth; otherwise 24/48 or 32/64. |
| TIFF | alpha only from extra samples (or Photoshop layer data); bilevel 0; palette 8; CMYK 24; else by bits and alpha. |
| Photoshop (whole file) | opaque (24/48/96) when the file is flattened without an alpha channel or its bottom layer is a Background layer, else 32/64/128; a Background layer's own footage is opaque too. Without alpha a grayscale file stays grayscale (40, -16), bitmap 0, indexed 8; Lab and CMYK 24. |
| Targa | colour-mapped 8, grayscale 40, 16 and 24-bit files 24, 32-bit 32. |
| BMP, GIF, SWF, FBX, AI/EPS/PDF | 32 |
| JPEG, MPEG, WMV | 24 |
| OpenEXR | 96, or 128 with alpha |
| Radiance HDR | 96 |
| Camera Raw | 48 |
| DPX, Cineon, HEIC | 16 bits per channel when the file has more than 8 |
| QuickTime/MP4 | ProRes, and H.264 with more than 8 bits per sample, 48 (64 with alpha); other codecs 24/32; a file whose only video track AE cannot decode 0 |
| Audio, data | 0 |

The depth is load-bearing for rendering: with 0 AE 2026 renders TIFF,
merged PSD/PSB and AI/EPS/PDF footage (and compositions made from them) with
their alpha ignored, and an FBX scene with stray content, while ExtendScript
still reports `hasAlpha` true. Formats whose `opti` is the
[generic media record](#generic-media-record) re-read the file and are not
affected.

#### Modification time

0x74-0x7C: byte 0x74 is the alphabetical-sequence marker, 0x76 a big-endian
u4 of seconds since 1904-01-01, the other bytes 0. AE compares 0x76 with the
file (a sequence: its folder) on open. When they match, AE trusts the values
cached in `sspc`. When they differ, or 0x76 is 0, AE re-reads the media and
takes the dimensions from the format's own reader, which is not always what
its importer recorded: an OpenEXR frame whose data window (2354x1000) is
smaller than its display window (2356x1002) is imported at the display window
but opens at the data window from an unstamped file (AE 2026). A writer should
stamp every source whose file it can see. A stamp also means AE no longer
corrects a wrong cached value on open.

#### Source format codes

0x16 names the importer AE used. It must match an importer that can read the
file; AE does not use it to find the file.

| Code | Format |
|---|---|
| `png!` | PNG |
| `ZPEG` | JPEG |
| `TIF ` | TIFF (`TIF_` in 92.14 files) |
| `8BPS` | Photoshop PSD and PSB (whole file or one layer) |
| `oEXR` | OpenEXR |
| `sDPX` | DPX and Cineon |
| `TPIC` | Targa |
| `STIL`, `IMIO` | BMP and GIF: AE on Windows writes `STIL`, AE on macOS `IMIO`, for stills and sequences. A still opens on either platform with either code; an `IMIO` sequence does not open on Windows and a `STIL` sequence does not open on macOS (AE 2026). |
| `AIDE` | HEIC/HEIF |
| `RHDR` | Radiance HDR |
| `Craw` | Camera Raw files (CRW, NEF) |
| `IFF ` | IFF (92.14 sample) |
| `TEXT` | Illustrator, EPS and PDF |
| `MOoV` | QuickTime `.mov`, `.m4v`, `.m4a` (older AE versions also used it for `.mp4`) |
| `XCEX` | MP4 (AE 2026) |
| `MPEG` | AAC audio (`.aac`); `.mp4` in older files |
| `MPEO` | MPEG-1/2 (`.mpg`, `.mpeg`) |
| `WMED` | Windows Media (`.wmv`) |
| `SWF ` | Flash |
| `WAVE` | WAV |
| `AIFC` | AIFF |
| `MP3A` | MP3 |
| `LDOM` | FBX 3D scene |
| `C4DC` | Cinema 4D scene (no sample) |
| `nosj` | JSON data |
| `sjgm` | MGJSON data |
| four NUL bytes | text and CSV data; placeholders |
| `Soli` | solid |

### `opti`

The importer's own record for the source. The layout depends on the importer;
the first four bytes identify it.

**Parent:** [`LIST:Pin`](#listpin) · **Size:** variable (0, 30, 46, 48, 58, 66, 266, 282, 322, 596, 600, 602, 8466, 9750 in the samples) · **py_aep:** `OptiChunk` (`SoliOptiChunk`, `PsdOptiChunk`, `TextOptiChunk`, `PlaceholderOptiChunk`)

Every non-empty record starts with the same 10-byte header:

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | fourcc | Record kind (usually the [source format code](#source-format-codes)); four NUL bytes for a placeholder. |
| 0x04 | 2 | u2 | Record version. |
| 0x06 | 4 | u4 | Total length of the record, header included (= the chunk size). |

| Kind | Version | Size | Record |
|---|---|---|---|
| `MOoV` `WAVE` `ZPEG` `STIL` `IMIO` `AIDE` `AIFC` `XCEX` `MPEG` `MPEO` `MP3A` `WMED` `SWF ` `nosj` `sjgm`, data files | 5 | 58 (66) | [Generic media record](#generic-media-record) |
| `png!` | 1 | 322 | [PNG record](#png-record-png) |
| `oEXR` | 1 | 9750 | [OpenEXR record](#openexr-record-oexr) |
| `8BPS`, `TIF ` | 0x0108 / 0x0109 | 600 / 602 | [Photoshop and TIFF record](#photoshop-and-tiff-record-8bps-tif) |
| `TIF_` | 1 | 46 | [Older TIFF record](#older-tiff-record-tif_) |
| `TEXT` | 8 | 596 | [Illustrator, EPS and PDF record](#illustrator-eps-and-pdf-record-text) |
| `sDPX` | 3 | 48 | [DPX and Cineon record](#dpx-and-cineon-record-sdpx) |
| `TPIC` `IFF ` `RHDR` `Craw` | 0x002E | 30 + block | [Photoshop-plug-in record](#photoshop-plug-in-record) |
| `Soli` | 9 | 282 | [Solid record](#solid-record-soli) |
| four NUL bytes | 2 | 266 | [Placeholder record](#placeholder-record) |
| none | - | 0 | [Empty record](#empty-and-other-records) |

**What a writer must write.** AE accepts a record that differs from its own
in many bytes, but not every kind can be left out. Measured on AE 2026: an
empty `opti` is accepted for an FBX scene and an OpenEXR still; a PNG still
with an empty `opti` opens but crashes AE as soon as it is rendered, while
the 58-byte generic record (code `png!`) renders like AE's own import; JPEG,
BMP/GIF, Targa, movies and audio need at least the generic record; TIFF
needs the 602-byte record (empty or generic crashes AE, still or sequence);
DPX/Cineon need their 48-byte record; Radiance HDR refuses an empty or
generic record; Camera Raw crashes AE with an empty record but accepts the
generic one (AE rewrites it on save); AI/EPS/PDF need the 596-byte record; an
OpenEXR whose data window differs from its display window needs the 9750-byte
record (see below). AE's own 322-byte PNG record copied onto an `sspc` that AE did
not write rendered with alpha ignored, so do not transplant a format-specific
record on its own.

#### Generic media record

Used by AE's media importers: QuickTime and MP4, audio, JPEG, BMP/GIF, HEIC,
MPEG, WMV, SWF and data files. The kind is the source format code, except for
data files whose `sspc` code is four NUL bytes (`\0vsc` for a `.csv`, `\0vst`
for a `.txt`).

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 10 | | Header: kind, version 5, length 58. |
| 0x0A | 20 | bytes | 0 in every sample. |
| 0x1E | 4 | fourcc | A container or file-type code stored byte-reversed: `VooM` (QuickTime), `EVAW`, `GEPJ`, `fFIG`, ` PMB`, ` 4PM`, `CIEH`, `FFIA`, `GEPM`, `DEMW`, ` FWS`, `bvh` + NUL (data files). 0 on BMP/GIF image sequences. |
| 0x22 | 4 | bytes | FF FF FF FF (0 when 0x1E is 0). |
| 0x26 | 4 | fourcc | Codec: `avc1`, `AVC1`, `apch`, `apcn`, `ap4h`, `jpeg`, `png `, `MPG4`, `MPG1`, `RAW `, `SWF `, `UNKN`; 0 for audio and data. |
| 0x2A | 4 | u4 LE | 1 when the source has video, 0 otherwise (and on BMP/GIF image sequences). |
| 0x2E | 4 | u4 LE | 1 in every sample. |
| 0x32 | 8 | bytes | 0 in every sample. |

An older 66-byte form (version 5, `MPEG` sources in 92.14 projects) appends
a u4 LE 1 and FF FF FF FF. AE re-derives the bytes from 0x1E to 0x31 from
the media: a record with the reversed source format code at 0x1E, FF FF FF FF,
no codec and the two 1 words opens and renders like AE's own (AE 2026,
MP4/MP3/MPEG/WMV included); the kind at 0x00 is what has to be right.

#### PNG record (`png!`)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 10 | | Header: `png!`, version 1, length 322. |
| 0x0A | 4 | bytes | `01 00 00 00` in every sample. |
| 0x0E | 4 | u4 | 1 in every sample. |
| 0x12 | 4 | u4 | Width. |
| 0x16 | 4 | u4 | Height. |
| 0x1A | 4 | u4 | Bits per channel (8 or 16). |
| 0x1E | 4 | u4 | Interlace method (0 none, 1 Adam7). |
| 0x22 | 4 | u4 | Colour type as decoded: 6 when the image has alpha (RGBA, gray + alpha, or a `tRNS` chunk), 2 otherwise (RGB, gray and palette images included). |
| 0x26 | 8 | bytes | 0 in every sample. |
| 0x2E | 4 | u4 | 4 in every sample. |
| 0x32 | 4 | u4 | Row size in bytes: width x 4 x bytes per channel. |
| 0x36 | 4 | bytes | 0 in every sample. |
| 0x3A | 264 | char | File name (UTF-8, NUL-padded); for a sequence, the name of one frame. |

#### OpenEXR record (`oEXR`)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 10 | | Header: `oEXR`, version 1 (big-endian like every header), length 9750. |
| 0x0A | 2 | u2 LE | 1 in every sample. |
| 0x0C | 2 | u2 LE | 0 in every sample. |
| 0x0E | 2 | u2 LE | Compression of the (first) part, OpenEXR numbering: 0 none, 1 RLE, 2 ZIPS, 3 ZIP, 4 PIZ, 5 PXR24, 6 B44, 7 B44A, 8 DWAA, 9 DWAB. |
| 0x10 | 2 | u2 LE | 1 in every sample. |
| 0x12 | 2 | u2 LE | Number of channels over all parts (0 in 92.14 files). |
| 0x14 | 26 | bytes | 0 in every sample. |
| 0x2E | 2 | u2 LE | Number of channels plus one per named layer (a part name, or the prefix of a `layer.channel` name); 0 in 92.14 files. |
| 0x30 | 9702 | bytes | Varies from save to save with no observable meaning (all zero in some samples); zeros render identically (AE 2026, compared with AE's own imports). |

Without this record AE places an image whose data window differs from its
display window wrongly, and crashed rendering one whose data window is larger
than the display window; the first 0x30 bytes with zeros after them are
enough (AE 2026).

#### Photoshop and TIFF record (`8BPS`, `TIF `)

Used for whole Photoshop files (PSD and PSB), for each layer of a Photoshop
file imported as layers, and for TIFF stills and sequences. The file-info
fields from 0x12 copy the Photoshop file header, little-endian.

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 10 | | Header: `8BPS` or `TIF `, version 0x0109 (602 bytes) or 0x0108 (600 bytes, 92.14 files). AE 2026 rewrites a 0x0108 record as 0x0109 by changing the version, the length and byte 0x148, and appending two zero bytes; no field moves. |
| 0x0A | 1 | u1 | 1 when the layer has a vector mask (enabled or not), and for the merged image of a flattened file imported as a one-layer composition; else 0. |
| 0x0B | 1 | u1 | 0 in every sample. |
| 0x0C | 2 | bytes | `01 01` in every sample. |
| 0x0E | 4 | u4 | Layer index (as `sspc` 0xC0), big-endian; 0xFFFFFFFF for a whole file. |
| 0x12 | 4 | fourcc | File signature stored byte-reversed: `SPB8` (PSD and PSB), ` FIT`. |
| 0x16 | 2 | u2 LE | 1 in every sample, PSB files included. |
| 0x18 | 6 | bytes | 0 in every sample. |
| 0x1E | 2 | u2 LE | Channels of the decoded image: the colour channels (1 for grayscale, indexed and bitmap, 3 for RGB and Lab, 4 for CMYK) plus 1 when it has alpha (TIFF extra samples marked as alpha or Photoshop layer data, Photoshop layer transparency). A Photoshop file with transparent layers counts its alpha (4 for RGB); a flattened or Background-only RGB file stores 3, a flattened one with an alpha channel too. Every record of one document stores the document's value, a layer's included. |
| 0x20 | 4 | u4 LE | Document height. |
| 0x24 | 4 | u4 LE | Document width. |
| 0x28 | 2 | u2 LE | Bits per channel (1, 8, 16, 32). |
| 0x2A | 2 | u2 LE | Colour mode, Photoshop numbering: 0 bitmap, 1 grayscale, 2 indexed, 3 RGB, 4 CMYK, 9 Lab. A TIFF stores the mode it reads as: 0 for 1-bit grayscale, 9 for CIELab. |
| 0x2C | 4 | bytes | 0 in every sample. |
| 0x30 | 1 | u1 | Number of layers: a Photoshop document's layer count (up to 194 in the samples; 0 for a flattened file); for a TIFF, the layer count when it carries Photoshop layers, else 1 when it has alpha and 0 when it has none. |
| 0x31 | 29 | bytes | 0 in every sample. |
| 0x4E | 4 | s4 LE | Layer content box top (0 for a whole file). |
| 0x52 | 4 | s4 LE | Left. |
| 0x56 | 4 | s4 LE | Bottom. |
| 0x5A | 4 | s4 LE | Right. The box is the layer's content box, not the canvas, for a full-frame and a cropped import alike. |
| 0x5E | 1 | u1 | Channels of the referenced layer: the document's colour channels plus 1 for the layer's transparency - 4 for an RGB pixel layer (even one with an empty content box), 3 for an RGB Background layer, 2 for a grayscale one; 0 for an adjustment layer and for a whole file. |
| 0x5F | 245 | bytes | 0 in every sample, except byte 0x148 = 3 in version 0x0108 records. |
| 0x154 | 4 | u4 LE | Photoshop layer id (`lyid`, as `sspc` 0xBC); 0 for a whole file. |
| 0x158 | 258 | char | Layer name, UTF-8, NUL-padded (256 bytes in a version 0x0108 record); empty for a whole file. A Background layer is named `Background` whatever its name in the file (AE 2026, English UI). |

AE does not re-derive the channel count, bit depth, colour mode or layer
count from the file: it keeps the stored values when it saves, and footage
whose record carries other values (all four wrong for grayscale, CMYK,
palette and bilevel files) renders the same as AE's own import (AE 2026
render comparison).

#### Older TIFF record (`TIF_`)

Seen only in 92.14 projects (48 items).

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 10 | | Header: `TIF_`, version 1, length 46. |
| 0x0A | 4 | bytes | `01 00 00 00`. |
| 0x0E | 2 | u2 | 4. |
| 0x10 | 2 | u2 | 0. |
| 0x12 | 2 | u2 | 0x0100. |
| 0x14 | 2 | u2 | TIFF compression code (1, 5, 7 seen) (inferred). |
| 0x16 | 4 | u4 | Width. |
| 0x1A | 4 | u4 | Height. |
| 0x1E | 2 | u2 | Bits per sample. |
| 0x20 | 4 | bytes | 0. |
| 0x24 | 2 | u2 | Samples per pixel (3 or 4). |
| 0x26 | 8 | f8 | 1.0 or 0.0. Unknown. |

#### Illustrator, EPS and PDF record (`TEXT`)

Used for whole AI/EPS/PDF documents and for each layer of an Illustrator or
PDF file imported as layers (a layer is a PDF optional-content group).

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 10 | | Header: `TEXT`, version 8, length 596. |
| 0x0A | 6 | bytes | 0 in every sample. |
| 0x10 | 16 | fixed 16.16 x4 | Artwork box x0, y0, x1, y1 in points (signed). A whole page stores (0, 0, page width, page height). A layer imported at Layer Size stores the layer's artwork box, fractional and offset from the page origin; AE sizes the footage by rounding the box size up, with a 1-pixel minimum; an empty layer stores (0, 0, 1/65536, 1/65536). |
| 0x20 | 8 | bytes | 0 in every sample. |
| 0x28 | 4 | u4 | 0xFFFFFFFF in every sample. |
| 0x2C | 4 | u4 | 0 in every sample. |
| 0x30 | 4 | u4 | Number of layers in the document (0 for EPS and for files without layers). |
| 0x34 | 8 | bytes | 0 in every sample. |
| 0x3C | 1 | u1 | 1 (0 for EPS). |
| 0x3D | 1 | u1 | Visibility of the referenced layer in the document: 0 for a layer the file's default configuration hides (AE also imports it with its video switch off). AE 2026 writes 0 for whole-document footage. Not a "references a layer" flag: the layer name is. |
| 0x3E | 6 | bytes | 0 in every sample. |
| 0x44 | 512 | char | Name of the referenced layer, UTF-8, NUL-padded; empty for whole-document footage. |
| 0x244 | 16 | fixed 16.16 x4 | Page box as 0, page height, page width, 0 (points); all zero for EPS and in 92.14 files. |

AE caches the footage size in `sspc`; the page box at 0x244 and the bytes
0x30 and 0x3C are not needed for a whole-document source to open. AE keeps
them as stored when it saves, and a whole-document record with them zero
renders the same as AE's own (AE 2026, `ai.ai`, `complex.ai`, `pdf.pdf`).

#### DPX and Cineon record (`sDPX`)

The same 48 bytes as the Cineon/DPX output options of an output module (see
[`Ropt`](#ropt)); every sample is identical:

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 10 | | Header: `sDPX`, version 3, length 48. |
| 0x0A | 4 | bytes | 0. |
| 0x0E | 2 | u2 | 10-bit black point: 0. |
| 0x10 | 2 | u2 | 10-bit white point: 1023. |
| 0x12 | 8 | f8 | Converted black point: 0.0. |
| 0x1A | 8 | f8 | Converted white point: 1.0. |
| 0x22 | 8 | f8 | Gamma: 1.0. |
| 0x2A | 2 | u2 | Highlight expansion: 0. |
| 0x2C | 1 | u1 | Logarithmic conversion: 0. |
| 0x2D | 1 | u1 | File format: 1 (DPX). |
| 0x2E | 1 | u1 | Bit depth: 10. |
| 0x2F | 1 | u1 | 0. |

#### Photoshop-plug-in record

Formats read through Photoshop-style file-format plug-ins (Targa `TPIC`,
`IFF `, Radiance `RHDR`, Camera Raw `Craw`) share an envelope, also used by
some output-format options ([`Ropt`](#ropt)):

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 10 | | Header: kind, version 0x002E, length 30 + block length. |
| 0x0A | 4 | bytes | `04 00 00 00` (Targa), `02 00 00 00` (Radiance), `05 00 00 00` (Camera Raw with settings), 0 (IFF, older Targa). AE rewrites it on every save; patched values open normally. |
| 0x0E | 4 | bytes | 0. |
| 0x12 | 4 | u4 | Block length. |
| 0x16 | 8 | bytes | Varies between items and between saves with no observable meaning; zeros are accepted (AE 2026). |
| 0x1E | n | bytes | Plug-in block: empty for Targa, IFF and Radiance; for Camera Raw `B64_` followed by base64-encoded XMP develop settings. |

Radiance HDR and Camera Raw keep their dimensions in `sspc` only. A Camera Raw
source with no develop settings is the 30-byte envelope with 0 at 0x0A: AE
2026 rewrites a generic record into that form on save, and an import that
carries its default settings renders the same image.

#### Solid record (`Soli`)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 10 | | Header: `Soli`, version 9, length 282. |
| 0x0A | 4 | f4 | 1.0 in every sample (inferred: the colour's alpha). |
| 0x0E | 4 | f4 | Red, 0.0-1.0 (`SolidSource.color`). |
| 0x12 | 4 | f4 | Green. |
| 0x16 | 4 | f4 | Blue. |
| 0x1A | 256 | char | The solid's item name, UTF-8, NUL-padded. At most 255 bytes: AE cuts a longer name to the longest prefix that fits in 255 bytes without splitting a character. |

#### Placeholder record

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 10 | | Header: four NUL bytes, version 2, length 266. |
| 0x0A | 256 | char | The placeholder's item name, UTF-8, NUL-padded, at most 255 bytes (truncated like a solid's). |

#### Empty and other records

An FBX scene (`LDOM`) has an empty `opti` (AE re-reads the scene). A Cinema 4D
scene gets a large importer record (about 357 KB) that AE rebuilds on save;
AE 2026 accepts the generic record in its place. Readers should keep any
unknown record as raw bytes.

### `LIST:Als2`

The path of a file or folder.

**Parent:** [`LIST:Pin`](#listpin) (file footage), [`LIST:LOm`](#listlom) (render output path)

| Child | Occurs | Description |
|---|---|---|
| [`alas`](#alas) | 1 | The path record. |

AE also knows an older `LIST:Alas` container for very old project versions;
no sample contains one.

### `alas`

A path record: UTF-8 JSON text, like a [`Utf8`](#utf8) body.

**Parent:** [`LIST:Als2`](#listals2) · **Size:** variable (179-418 bytes in the samples) · **py_aep:** `Utf8Chunk`

The JSON is compact (no spaces) with its keys in alphabetical order, as AE
writes it:

```
{"ascendcount_base":3,"ascendcount_target":2,"fullpath":"C:\\Users\\me\\proj\\assets\\image.png","platform":1,"server_name":"HP-C-10","server_volume_name":"","target_is_folder":false}
```

| Key | Type | Description |
|---|---|---|
| `fullpath` | string | Absolute path of the file; for an image sequence (and a render output folder) the folder. AE finds footage by this absolute path first; a relative path opens as missing. |
| `target_is_folder` | bool | `true` when `fullpath` is a folder (image sequence). |
| `platform` | int | Path style: 1 for a drive-letter or UNC path, 2 for a POSIX path. It follows the path, not the machine that saved the file, and Windows AE opens either. |
| `server_name` | string | For a UNC path the server (`serge` for `\\serge\as_serie\...`); for a drive-letter path the name of the machine that saved it; empty for a POSIX path. |
| `server_volume_name` | string | For a UNC path the share (`as_serie`); empty otherwise. |
| `ascendcount_base` | int | Relative-path count on the project side: path components of the project file below the deepest folder it shares with the target. |
| `ascendcount_target` | int | Path components of the target below that shared folder; a folder target counts one more, as for a file inside it. Both counts are 0 when the paths are on different drives or shares, or in different styles. |

The relative-path counts are load-bearing: when the absolute path does not
resolve, AE retries the target relative to the project file. A project
folder moved elsewhere finds its footage with AE's counts and loses it with
0/0 (AE 2026). Example: project `C:\U\me\git\proj\samples\models\item\proxy.aep`
and target `C:\U\me\git\proj\samples\assets\image_with_alpha.png` share
`C:\U\me\git\proj\samples`, giving 3 and 2. On save AE rewrites the record of
footage it found through a native path (`platform` 1, its own machine or UNC
server name, recomputed counts) and leaves the records of POSIX paths and of
missing footage as they were. Windows AE maps a POSIX path onto drive C:
(`/Users/x` opens as `C:\Users\x`).

### `LIST:StVc`

A list of strings: here the frame files of an alphabetical image sequence.

**Parent:** [`LIST:Pin`](#listpin), [`LIST:CCtl`](#listcctl) (Essential Graphics menu items)

| Child | Occurs | Description |
|---|---|---|
| [`StVS`](#stvs) | 1, first | Number of strings. |
| [`Utf8`](#utf8) | as counted | One file name per frame, in play order (sample: `new_exr.0002.exr`, `new_exr.0003.exr`, `old_exr.00004.exr`). |

### `StVS`

The string count of a [`LIST:StVc`](#liststvc).

**Parent:** [`LIST:StVc`](#liststvc) · **Size:** 4 bytes · **py_aep:** `U4LeChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 LE | Number of [`Utf8`](#utf8) children that follow. |

### `LIST:CLRS`

The footage's Interpret Footage > Color Management settings. The colour
spaces are stored as [colour-profile envelopes](#colour-profile-envelope)
(JSON in the `Utf8` that follows a one-byte marker chunk).

**Parent:** [`LIST:Pin`](#listpin)

| Child | Occurs | Description |
|---|---|---|
| [`epid`](#epid) | 1, required | ID of the embedded profile. |
| [`apid`](#apid) | 1, required | ID of the assigned profile. |
| [`empd`](#empd) + [`Utf8`](#utf8) | 0-1 pair | Name of a colour space the media declares. |
| [`linl`](#linl) | 1, required | Interpret As Linear Light. |
| [`embp`](#embp) | 1 | Always 1. |
| [`ipws`](#ipws) | 1 | Interpret in the working space. |
| [`dcui`](#dcui) | 0-1 | Solids; some movies in 92.14 files; Illustrator footage in 93.40-95.6 files. |
| [`prgb`](#prgb) | 0-1 | Preserve RGB is on. |
| [`mcsp`](#mcsp) + [`Utf8`](#utf8) | 0-1 pair | Embedded colour space (file version 93.40 and later). |
| [`Mcsp`](#mcsp_1) + [`Utf8`](#utf8) | 1 pair | Media colour space (file version 93.40 and later). |
| [`ocsp`](#ocsp) + [`Utf8`](#utf8) | 1 pair | Assigned colour space (file version 93.40 and later). |
| [`hdrm`](#hdrm) + [`Utf8`](#utf8) | 1 pair | Always `{}` (file version 96.9 and later). |

Version gates seen in the samples: 92.14 files stop after `ipws` (`dcui`
`prgb` for solids); 93.40-95.6 (AE 2022-2024) add the `Mcsp` and `ocsp`
pairs, and the `mcsp` pair for media that embeds a profile; 96.9 (AE 2025)
and later add the `hdrm` pair. AE 2022-2024 open a file whose records end
with `hdrm` and drop the pair when they save it; they also write `dcui` for
Illustrator footage, which AE 2025 does not (imports of the same files into
an empty project of each version, `models/import/clrs_ae20XX.aep`). A project
with a footage `LIST:CLRS` lacking `linl` is refused ("internal verification
failure", AE 2026); a missing `epid` or `apid` is treated the same way
(inferred). AE can also write the one-byte tags `gmtm`, `pocs` and `scsp`
here in conditions no sample covers; their meaning is not established.

What AE 2026 writes for a fresh import (Adobe colour management, measured over
every format it imports plus untagged JPEG/TIFF/PSB and an sRGB-chunk PNG):

| Media | `epid` | `apid` | `empd` name | `ipws` | `mcsp` / `Mcsp` envelope | `ocsp` envelope |
|---|---|---|---|---|---|---|
| Embeds an ICC profile (PNG `iCCP`, JPEG, TIFF, PSD/PSB) | profile ID | FF | - | 0 | the profile (`baseProfileType` 2), in both | empty |
| Embeds none: stills, sequences, audio, data | FF | sRGB ID | - | 0 | - / empty | sRGB IEC61966-2.1 |
| Embeds none: video AE decodes itself (animated GIF, MPEG, SWF, WMV) | FF | ID | - | 0 | - / empty | Rec.709 Gamma 2.4 |
| JPEG without a profile | FF | FF | - | 0 | - / empty | empty |
| QuickTime/MP4 video | FF | FF | `Rec. 709` | 0 | display-referred tag (type 1), in both | empty |
| Grayscale, CMYK, Lab or indexed TIFF/PSD without a profile | FF | FF | `Dot Gain 20%` (32-bit float grayscale: `Linear Grayscale Profile`), `U.S. Web Coated (SWOP) v2`, `Lab D50`, `sRGB IEC61966-2.1`; none for a bitmap file | 0 | - / empty | empty |
| AI/EPS/PDF | FF | FF | document profile (`Coated FOGRA39 (ISO 12647-2:2004)`) when it has one | 1 in the samples | - / empty | empty |
| Solid | FF | FF | - | 1 | - / empty (`dcui`, `prgb` present) | empty |
| Placeholder | FF | FF | - | 1 | - / empty | empty |

FF = sixteen FF bytes. "- / empty" = no `mcsp` pair, an empty `Utf8` after
`Mcsp`. Notes:

- PNG files are read for `iCCP` only; an `sRGB` chunk counts as no profile.
- TIFF and Photoshop footage store AE's catalogued copy of a profile rather
  than the file's bytes (the two differ only in the rendering-intent field, so
  the ID is the same), and treat an untagged file as carrying sRGB.
- QuickTime/MP4 name their space with `empd` + `Rec. 709` and an `mcsp`/`Mcsp`
  envelope of `baseProfileType` 1 named `BT.709,<decode format>,Display-Referred`
  (`32f` for untagged samples, `10-bit` for a tagged 10-bit ProRes) whose data
  is `AQAAAP////8=` (bytes `01 00 00 00 FF FF FF FF`). The decode format is not
  derivable from the container; AE fills it in when it opens a file whose
  record is missing. AE 2022-2024 samples assign Rec.709 Gamma 2.4 to the same
  QuickTime footage instead (`apid` + `ocsp`, no `empd`).
- User choices in Interpret Footage: "Working Color Space" sets `ipws` 1,
  `apid` FF and empties the `ocsp` `Utf8`; assigning a profile sets `apid` to
  its ID and `ocsp` to its envelope; choosing the embedded profile sets `apid`
  FF and copies the embedded envelope into `ocsp`.
- On a Replace Footage AE keeps `ipws`, `prgb`, `linl` and an assigned profile
  (`apid` + `ocsp`), and re-measures `epid`, `mcsp`, `Mcsp` and `empd` from
  the new file.

**OCIO projects.** When the project uses OCIO colour management (section A),
AE writes an OCIO envelope (`baseProfileType` 3) into the `ocsp` `Utf8` of
every file it imports, keeps an embedded ICC profile in `mcsp`/`Mcsp`, and
leaves `apid` FF and `ipws` 0; the colour space is identified by name, not by
ID. The space comes from the configuration's `file_rules`, tried in order
(`Default` matches everything; a `regex` rule is a regular-expression search
of the path; a `pattern` + `extension` rule globs the file name and the
lower-cased extension). The matched rule's colour space is stored as a direct
pick: name `<family>/<colour space>`, data `{"colorSpace1":"<colour space>"}`,
the family found by resolving a role to its target. A configuration without
`file_rules` gives the `default` role in the role shape: name = the role's
target, data `{"colorSpace1":"<target>","ocioColorSpaceType":2}`. Samples:
`models/import/ocio_input_{aces12,aces13cg,sergb}.aep`.

### `epid`

ICC profile ID of the profile the media embeds.

**Parent:** [`LIST:CLRS`](#listclrs) · **Size:** 16 bytes · **py_aep:** `EpidChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 16 | bytes | The profile's ICC Profile ID (MD5 of the profile with the header's flags, rendering intent and ID fields zeroed, as ICC.1 defines it); sixteen FF bytes when the media embeds no profile. |

### `apid`

ICC profile ID of the profile assigned to the footage.

**Parent:** [`LIST:CLRS`](#listclrs) · **Size:** 16 bytes · **py_aep:** `ApidChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 16 | bytes | ICC Profile ID of the assigned profile, whose bytes are in the `ocsp` envelope (`1d3fda2e...` for sRGB IEC61966-2.1); sixteen FF bytes when none is assigned and in OCIO projects. |

### `linl`

Interpret As Linear Light.

**Parent:** [`LIST:CLRS`](#listclrs) · **Size:** 4 bytes · **py_aep:** `LinlChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 LE | 0 Off, 1 On, 2 On for 32 bpc (the default). |

AE writes 0 for the formats it decodes through its media importers (JPEG,
BMP/GIF, SWF, MPEG, WMV and QuickTime/MP4 with video) and 2 for everything
else, audio-only movies and image sequences included.

### `embp`

**Parent:** [`LIST:CLRS`](#listclrs) · **Size:** 1 byte · **py_aep:** `EmbpChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 1 in every sample. Unknown. |

### `empd`

Marks that a [`Utf8`](#utf8) with the name of the media's declared colour
space follows.

**Parent:** [`LIST:CLRS`](#listclrs) · **Size:** 1 byte · **py_aep:** `EmpdChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 1. |

The `Utf8` after it is plain text, not an envelope: `Rec. 709`, `HDTV (Rec.
709) Y'CbCr`, `SDTV PAL Y'CbCr`, `SDTV NTSC Y'CbCr` (video), `Dot Gain 20%`,
`U.S. Web Coated (SWOP) v2`, `Linear Grayscale Profile` (TIFF and Photoshop),
`Coated FOGRA39 (ISO 12647-2:2004)` (the document profile of an AI/PDF file,
read from its ICC `desc` tag). Absent when there is no such name. The pair
comes right after [`apid`](#apid).

### `ipws`

**Parent:** [`LIST:CLRS`](#listclrs) · **Size:** 1 byte · **py_aep:** `IpwsChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 1 when the footage is interpreted in the project's working space ("Working Color Space"), 0 when it uses its own or an assigned space. |

### `dcui`

**Parent:** [`LIST:CLRS`](#listclrs) · **Size:** 1 byte · **py_aep:** `DcuiChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 1. Present on every solid, on some movies in 92.14 files and on Illustrator footage in 93.40-95.6 files (AE 2022-2024 write it back on save when it is missing). Unknown. |

### `prgb`

**Parent:** [`LIST:CLRS`](#listclrs) · **Size:** 1 byte · **py_aep:** `PrgbChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 1. The chunk's presence means Preserve RGB is on; it is absent when off. Every solid has it. |

### `mcsp`

Marks that the envelope of the embedded colour space follows (file version
93.40 and later).

**Parent:** [`LIST:CLRS`](#listclrs) · **Size:** 1 byte

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 1. |

The following `Utf8` holds the embedded ICC profile (type 2) or the video
display-referred tag (type 1). Present only when the media has one.

### `Mcsp`

Marks that the envelope of the media colour space follows (file version
93.40 and later).

**Parent:** [`LIST:CLRS`](#listclrs) · **Size:** 1 byte · **py_aep:** `McspChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 1. |

The following `Utf8` is the same envelope as after [`mcsp`](#mcsp) when there
is one, and empty otherwise.

### `ocsp`

Marks that the envelope of the assigned colour space follows (file version
93.40 and later).

**Parent:** [`LIST:CLRS`](#listclrs) · **Size:** 1 byte · **py_aep:** `OcspChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 1. |

The following `Utf8` is the colour space the footage is interpreted in when
it is not the embedded one: an ICC envelope matching [`apid`](#apid), a copy
of the embedded envelope (the user picked it explicitly), an OCIO envelope
(OCIO projects), or empty.

### `hdrm`

**Parent:** [`LIST:CLRS`](#listclrs), [`LIST:LOm`](#listlom) · **Size:** 1 byte · **py_aep:** `HdrmChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 1. |

The following `Utf8` is `{}` in every sample (file version 96.9 and later).

### `LIST:mnfo`

Media timecode information.

**Parent:** [`LIST:Pin`](#listpin)

| Child | Occurs | Description |
|---|---|---|
| [`strt`](#strt) | 1 | Start timecode. |
| [`drop`](#drop) | 1 | A flag. |

### `strt`

The media's start timecode, as a time.

**Parent:** [`LIST:mnfo`](#listmnfo) · **Size:** 8 bytes · **py_aep:** `StrtChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 LE | Time dividend. |
| 0x04 | 4 | u4 LE | Time divisor; start time in seconds = dividend / divisor. |

Stills, sequences, audio and solids store 0/30, placeholders 0/1. A movie
stores 0 over its own time scale, or its embedded start timecode (86592/24 =
01:00:08:00, 2767565/768 = 3603.6 s).

### `drop`

**Parent:** [`LIST:mnfo`](#listmnfo) · **Size:** 1 byte · **py_aep:** `DropChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 1 on stills, sequences, audio, solids, placeholders and most movies in newer files; 0 on many movies. Equal to `sspc` byte 0xD4 in all but one sample. The name suggests a drop-frame timecode flag; the samples do not confirm it (a 23.976 fps movie stores 0 in some files, 30 fps stills store 1). |

### `ftgi`

Footage item times.

**Parent:** [`LIST:Item`](#listitem) (footage items, right after the main [`LIST:Pin`](#listpin)) · **Size:** 16 bytes · **py_aep:** `FtgiChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Time dividend; 0 by default. |
| 0x04 | 4 | u4 | Time divisor; 1 by default. |
| 0x08 | 4 | u4 | Time dividend; 0xFFFFFFFF (undefined) by default. |
| 0x0C | 4 | u4 | Time divisor; 600 by default. |

Every footage item has one (solids and placeholders included); compositions
have none. All but 10 samples hold the defaults `0/1` and `0xFFFFFFFF/600`.
The exceptions are movies in 92.14 production projects, with times inside
the movie in its own time scale (`879/24` and `1029/24`, or `1592/24` with
the second time undefined). Meaning not established (possibly the Footage
panel's time state).

### `elab`

Despite this section, not a footage chunk: one byte found inside effect
instances.

**Parent:** [`LIST:sspc`](#listsspc) (layer effects, and the project's effect definitions in [`LIST:EfdG`](#listefdg)) · **Size:** 1 byte

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | 0xFF in every sample. Unknown. |

It follows the effect's [`pgui`](#pgui) and occurs only in samples of file
version 97.7 (71 chunks in 7 files), written by an AE 26 build later than
26.0; files written by AE 26.0 (97.2) do not contain it.

## Layers, properties and keyframes

Every layer of a composition is one layer list ([`LIST:Layr`](#listlayr) for
the layers a user sees, `LIST:SLay`, `LIST:CLay`, `LIST:DLay` and `LIST:SecL`
for the viewer pseudo-layers AE keeps per composition). Its body always starts
with the same three chunks: the fixed [`ldta`](#ldta) record, the layer name
as a [`Utf8`](#utf8), and the root property group [`LIST:tdgp`](#listtdgp).
Everything a layer animates - transform, masks, effects, text, shape contents,
markers - hangs off that group as a tree: groups are [`LIST:tdgp`](#listtdgp)
lists that hold `(match name, body)` pairs, and the leaves are property
streams, [`LIST:tdbs`](#listtdbs) lists that hold either one static value
([`cdat`](#cdat)) or a keyframe list ([`LIST:list`](#listlist) =
[`lhd3`](#lhd3) + [`ldat`](#ldat)). This section covers the layer record, the
group and stream chunks and the keyframe items; the special value containers
that sit next to some streams (masks, shapes, markers, gradients, text,
effects) are in their own sections and are linked where they appear.

Children of a layer list, in the order AE writes them (all AE 2018-2026
samples):

| Child | Occurs | Description |
|---|---|---|
| [`ldta`](#ldta) | 1, required | Layer record: id, timing, switches, type, parent. |
| [`Utf8`](#utf8) | 1, required | Layer name (empty = the name of the source item). |
| [`LIST:tdgp`](#listtdgp) | 1, required | Root property group. |
| [`LIST:Gide`](#listgide) | 1 | Layer guides (usually empty). |
| [`cmta`](#cmta) | 0-1 | Layer comment. |
| [`LIST:OvdG`](#listovdg) | 0-1 | Essential Graphics overrides. |
| [`mdla`](#mdla), [`mdlv`](#mdlv) | 0-1 each | 3D model layers only, after `LIST:Gide`. |

### `ldta`

The layer record: identity, timing, switches, blending, track matte, layer
type and parent.

**Parent:** [`LIST:Layr`](#listlayr), `LIST:SLay`, `LIST:CLay`, `LIST:DLay`, `LIST:SecL` · **Size:** 160 bytes (file versions before 94.x), 164 bytes (AE 23, file version 94.x, and later) · **py_aep:** `LdtaChunk`

All times are dividend / divisor pairs (seconds = dividend / divisor). The
in and out points are in layer time: they are measured from the layer's
start time and are not stretched, so the composition in point is
`start_time + in_point * stretch / 100` (same for the out point).

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Layer id (ExtendScript `Layer.id`). Unique and persistent; referenced by [`ldta`](#ldta) parent and matte ids and by [`tdpi`](#tdpi). |
| 0x04 | 2 | u2 | Quality: 0 = Wireframe, 1 = Draft, 2 = Best (`AVLayer.quality`). Cameras, lights and the viewer cameras store 0. |
| 0x06 | 2 | bytes | 0 in every sample. |
| 0x08 | 4 | s4 | Stretch dividend. Stretch in percent = 100 x dividend / divisor (divisor at 0x6C); negative = time-reversed layer. A stretch set by script is the float32 of the percentage / 100 as an exact ratio (133.33 % is 11184531 / 8388608); anything under 1 % (0 included) becomes 655 / 65536. The samples also hold other exact ratios, such as 33 / 50 and 10 / 7. A time-reversed layer's time 0 sits `abs(stretch) / 100 / 3000` s before its start time, for its in and out points as for its keyframes. |
| 0x0C | 4 | s4 | Start time dividend (`Layer.startTime`, composition time). |
| 0x10 | 4 | u4 | Start time divisor. Usually 600 or the composition timebase in the samples. A start time set by script is stored in ticks of the layer's timebase (the [`tdb4`](#tdb4) time base for the stretch at that moment), rounded half up: 1.3 s on a 150 % layer at 24 fps is 47923 / 36864. A later stretch change keeps the stored ratio. |
| 0x14 | 4 | s4 | In point dividend (layer time, see above). |
| 0x18 | 4 | u4 | In point divisor (usually the composition timebase in the samples). |
| 0x1C | 4 | s4 | Out point dividend (layer time). |
| 0x20 | 4 | u4 | Out point divisor. |
| 0x24 | 1 | u1 | 0 in every sample. |
| 0x25 | 1 | u1 | Layer flags A (bits below). |
| 0x26 | 1 | u1 | Layer flags B (bits below). |
| 0x27 | 1 | u1 | Layer flags C (bits below). Usually 0x07 on AV layers (nulls included), 0x87 on text and shape layers, 0x01 on cameras and lights. |
| 0x28 | 4 | u4 | Source item id (the [`idta`](#idta) id of the footage, solid or composition). 0 for text, shape and camera layers; lights store 0 up to AE 2022 and 0xFFFFFFFF from AE 2023 (new lights in AE 15 and 2022-2026), except an environment light that uses a footage item as its light source, which stores that item's id. |
| 0x2C | 15 | bytes | 0 in every sample. |
| 0x3B | 1 | u1 | Unknown. 1 on every AV layer (footage, solid, null, text, shape, 3D model, mesh), 0 on cameras, lights and the viewer cameras. |
| 0x3C | 1 | u1 | Unknown. 0, except 1 on 7 sample layers (3D nulls among them). |
| 0x3D | 1 | u1 | Label colour, 0 (none) - 16 (`Layer.label`). |
| 0x3E | 2 | bytes | 0 in every sample. |
| 0x40 | 32 | char[32] UTF-8 | The first 31 bytes of the layer name, NUL-terminated. The [`Utf8`](#utf8) that follows holds the full name and is authoritative; older files may hold this copy in a legacy 8-bit encoding. Empty when the name comes from the source item. |
| 0x60 | 3 | bytes | 0 in every sample. |
| 0x63 | 1 | u1 | Blending mode (table below). |
| 0x64 | 3 | bytes | 0 in every sample. |
| 0x67 | 1 | u1 | Transfer flags (bits below). |
| 0x68 | 3 | bytes | 0 in every sample. |
| 0x6B | 1 | u1 | Track matte type: 0 none, 1 Alpha, 2 Alpha Inverted, 3 Luma, 4 Luma Inverted (`AVLayer.trackMatteType`). |
| 0x6C | 4 | u4 | Stretch divisor (see 0x08). |
| 0x70 | 8 | f8 | 0.0 in every sample. |
| 0x78 | 8 | f8 | 0.0 in every sample. |
| 0x80 | 3 | bytes | 0 in every sample. |
| 0x83 | 1 | u1 | Layer type: 0 AV (footage, solid, composition, null, adjustment), 1 light, 2 camera, 3 text, 4 shape, 5 3D model, 7 parametric mesh. |
| 0x84 | 4 | u4 | Parent layer id, 0 = no parent (`Layer.parent`). |
| 0x88 | 3 | bytes | 0 in every sample. |
| 0x8B | 1 | u1 | Light type for a light layer (0 Parallel, 1 Spot, 2 Point, 3 Ambient, 4 Environment, the AE SDK `AEGP_LightType` order); mesh type for a parametric mesh layer (0 Cube, 1 Sphere, 2 Plane, 3 Torus, 4 Cone, 5 Cylinder); 0 otherwise. |
| 0x8C | 4 | u4 | 1 on the six secondary viewer cameras (`LIST:SLay`), 0 elsewhere. |
| 0x90 | 1 | u1 | 1 on every viewer pseudo-layer (`SLay`, `CLay`, `DLay`, `SecL`), 0 on composition layers. |
| 0x91 | 3 | bytes | 0 in every sample. |
| 0x94 | 4 | u4 | 1 when 0x98 is non-zero, else 0. |
| 0x98 | 8 | f8 | 0.0, 36.0 or 102.0472440944882 on camera layers and viewer cameras, 0.0 elsewhere (inferred: a 36 mm film size; 102.047... = 36 x 72 / 25.4). The viewer cameras of a new composition get 102.047... (and 1 at 0x94) from AE 26 only; AE 15 and AE 2022-2025 write 0. |
| 0xA0 | 4 | u4 | Track matte layer id, 0 = none. Present only in the 164-byte form (AE 23 and later), where any layer can be the matte; older files use the layer directly above. |

Layer flags A at 0x25:

| Bit | Mask | Meaning |
|---|---|---|
| 0 | 0x01 | The name was set explicitly on a layer that has a source item (it differs from the source's name). Always 0 on sourceless layers (camera, light, text, shape) even when named, except parametric meshes, which set it once renamed. |
| 1 | 0x02 | Guide layer (`Layer.guideLayer`). |
| 2 | 0x04 | Frame blending mode: 1 = Pixel Motion, 0 = Frame Mix (only meaningful with flags C bit 4). |
| 3 | 0x08 | Per-character 3D (`threeDPerChar`). |
| 4 | 0x10 | Auto-orient: characters toward camera (`AutoOrientType.CHARACTERS_TOWARD_CAMERA`, needs bit 3). |
| 5 | 0x20 | Environment layer (`environmentLayer`). |
| 6 | 0x40 | Sampling quality: 1 = Bicubic, 0 = Bilinear (`samplingQuality`). |
| 7 | 0x80 | 0 in every sample. |

Layer flags B at 0x26:

| Bit | Mask | Meaning |
|---|---|---|
| 0 | 0x01 | Auto-orient along path. |
| 1 | 0x02 | Adjustment layer. |
| 2 | 0x04 | 3D layer (`threeDLayer`). |
| 3 | 0x08 | Solo. |
| 4 | 0x10 | Layer markers locked (inferred). |
| 5 | 0x20 | Auto-orient towards camera, on an AV layer (`CAMERA_OR_POINT_OF_INTEREST`, needs bit 2). |
| 6 | 0x40 | Auto-orient towards point of interest, on a camera or light (two-node rig). AE 2026 writes 0x44 for a default two-node camera and 0x04 for one with auto-orient off. |
| 7 | 0x80 | Null layer (`nullLayer`). |

Layer flags C at 0x27:

| Bit | Mask | Meaning |
|---|---|---|
| 0 | 0x01 | Video enabled (`Layer.enabled`). |
| 1 | 0x02 | Audio enabled. |
| 2 | 0x04 | Effects active. |
| 3 | 0x08 | Motion blur. |
| 4 | 0x10 | Frame blending on (type in flags A bit 2). |
| 5 | 0x20 | Locked. |
| 6 | 0x40 | Shy. |
| 7 | 0x80 | Collapse transformations / continuously rasterize. |

Transfer flags at 0x67:

| Bit | Mask | Meaning |
|---|---|---|
| 0 | 0x01 | Preserve underlying transparency. |
| 1 | 0x02 | Dancing Dissolve: with blending mode 3 (Dissolve) this bit selects Dancing Dissolve; there is no separate mode value for it. |

Blending mode values at 0x63. They are the AE SDK `PF_Xfer` transfer-mode
values; Normal is 2, and cameras, lights and the viewer cameras store 0:

| Value | Mode | Value | Mode | Value | Mode |
|---|---|---|---|---|---|
| 0 | Normal (cameras, lights) | 13 | Hue | 26 | Difference |
| 2 | Normal | 14 | Saturation | 27 | Color Dodge |
| 3 | Dissolve (Dancing Dissolve with transfer bit 1) | 15 | Color | 28 | Color Burn |
| 4 | Add | 16 | Luminosity | 29 | Linear Dodge |
| 5 | Multiply | 17 | Stencil Alpha | 30 | Linear Burn |
| 6 | Screen | 18 | Stencil Luma | 31 | Linear Light |
| 7 | Overlay | 19 | Silhouette Alpha | 32 | Vivid Light |
| 8 | Soft Light | 20 | Silhouette Luma | 33 | Pin Light |
| 9 | Hard Light | 21 | Luminescent Premultiply | 34 | Hard Mix |
| 10 | Darken | 22 | Alpha Add | 35 | Lighter Color |
| 11 | Lighten | 23 | Classic Color Dodge | 36 | Darker Color |
| 12 | Classic Difference | 24 | Classic Color Burn | 37 | Subtract |
| | | 25 | Exclusion | 38 | Divide |

Notes for writers:

- The record is 164 bytes only in files of version 94.x (AE 23) and later.
  A 164-byte `ldta` in an older-version file makes every AE version refuse
  the composition ("chunk in file too big"); write 160 bytes there.
- AE writes the name in both places: the truncated copy at 0x40 and the full
  [`Utf8`](#utf8). Layers named after their source (footage, solid,
  composition and null layers that were never renamed) store an empty
  string in both.
- The auto-orient setting is spread over three bits: along path = flags B
  bit 0; towards camera = flags B bit 5 (AV layers) or bit 6 (cameras and
  lights); characters toward camera = flags A bit 4 (with bit 3).
- The trailing fields from 0x8C on describe the viewer pseudo-layers; a
  normal layer stores zeros there (cameras also use 0x94 / 0x98).

#### Layer name

The [`Utf8`](#utf8) right after `ldta` is the layer name in UTF-8, with no
length limit. An empty string means the layer shows its source item's name.

### `mdla`

A 256-byte block written on 3D model layers (layer type 5), after
[`LIST:Gide`](#listgide).

**Parent:** [`LIST:Layr`](#listlayr) · **Size:** 256 bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 256 | bytes | Unknown. All zero in the three samples that contain it. |

### `mdlv`

An 8-byte value written right after [`mdla`](#mdla) on 3D model layers.

**Parent:** [`LIST:Layr`](#listlayr) · **Size:** 8 bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 8 | u8 LE | Unknown. 1 (`01 00 00 00 00 00 00 00`) in the three samples that contain it. Little-endian. |

### `LIST:tdgp`

A property group: the layer's root group, and every named group below it
(Transform, Masks, Effects, a mask, an effect's parameters, a shape group,
a layer style, ...).

**Parent:** [`LIST:Layr`](#listlayr) and the viewer layer lists (root
group), [`LIST:tdgp`](#listtdgp), [`LIST:sspc`](#listsspc) (an effect's
parameters), and the bodies listed below.

| Child | Occurs | Description |
|---|---|---|
| [`tdsb`](#tdsb) | 1, required, first | Group flags (enabled, hidden, ...). |
| [`tdsn`](#tdsn) | 1, required, second | Group display name (one [`Utf8`](#utf8)): see below. |
| [`tdmn`](#tdmn) + body | 0-n | One child property: its match name, followed by the chunks that make up the child. |
| [`tdmn`](#tdmn) `ADBE Group End` | 1, required, last | Terminator. Has no body. |

A child's body is every chunk between its `tdmn` and the next `tdmn`. Most
bodies are one list, some are several chunks:

| Body | Child kind |
|---|---|
| [`LIST:tdbs`](#listtdbs) | A property stream (number, point, colour, ...). |
| [`LIST:tdgp`](#listtdgp) | A sub-group. |
| [`LIST:otst`](#listotst) | `ADBE Orientation`. |
| [`LIST:om-s`](#listom-s) | A mask path or shape path (`ADBE Mask Shape`, `ADBE Vector Shape`). |
| [`mkif`](#mkif) + [`LIST:tdgp`](#listtdgp) | A mask (`ADBE Mask Atom`): mask settings, then the mask's properties. |
| [`LIST:mrst`](#listmrst) | Layer markers (`ADBE Marker`). |
| [`LIST:btds`](#listbtds) | A text document (`ADBE Text Document`). |
| [`LIST:GCst`](#listgcst) | Gradient colours (shape gradients, layer-style gradients). |
| [`LIST:sspc`](#listsspc) | One effect instance inside `ADBE Effect Parade`. |
| [`LIST:OvG2`](#listovg2) + [`LIST:tdgp`](#listtdgp) | `ADBE Layer Overrides`. |
| [`blsv`](#blsv) + [`blsi`](#blsi) + [`LIST:tdbs`](#listtdbs) | `ADBE Layer Source Alternate`. |
| [`LIST:tdbs`](#listtdbs) + [`vfdn`](#vfdn) | A variable-font axis of a text animator (AE 26). |
| [`mtov`](#mtov) + [`Utf8`](#utf8) + [`LIST:tdgp`](#listtdgp) | A 3D model material (`ADBE3D Para Mat Parade` children). |

The group's [`tdsn`](#tdsn) holds:

- the six characters `-_0_/-` when the group has no name of its own: AE then
  shows the match name's default (localised) display name. AE writes this
  sentinel for every built-in group (Transform, Layer Styles, ...) and for
  the first instance of an effect.
- the user-visible name for groups that carry one: masks (`Mask 1`), shape
  groups and shape operators (`Group 1`, `Rectangle Path 1`, `Fill 1`), a
  renamed effect, `Compositing Options`.
- an empty string on a layer's root group.

A writer that creates a property group or stream must write the sentinel,
not the default display name.

#### Child order and omitted properties

AE reads a group's children by match name in a fixed order, scanning
forward. A child that appears earlier than AE expects is skipped as if
absent, and AE then refuses the file ("missing data in file") or drops the
layer. When a property is written for the first time it must therefore be
inserted at its canonical position, not appended before `ADBE Group End`.
The order AE 2025 and 2026 write, from the samples:

- Root group of a layer: `ADBE Marker`, then `ADBE Time Remapping` (AV
  layers), `ADBE Text Properties` (text layers) or `ADBE Root Vectors Group`
  (shape layers), `ADBE Mask Parade`, `ADBE Effect Parade`,
  `ADBE Transform Group`, `ADBE Light Options Group` / `ADBE Camera Options
  Group`, `ADBE Layer Styles`, `ADBE Plane Options Group`,
  `ADBE Extrsn Options Group`, `ADBE Material Options Group`,
  `ADBE Audio Group`, `ADBE Data Group`, `ADBE Layer Overrides`,
  `ADBE Layer Sets`, `ADBE Source Options Group`, `ADBE Group End`.
  AE 15 layers have neither `ADBE Layer Sets` nor `ADBE Source Options
  Group`.
- `ADBE Transform Group`: `ADBE Anchor Point`, `ADBE Position`,
  `ADBE Position_0`, `ADBE Position_1`, `ADBE Position_2`, `ADBE Scale`,
  `ADBE Orientation`, `ADBE Rotate X`, `ADBE Rotate Y`, `ADBE Rotate Z`,
  `ADBE Opacity`, `ADBE Envir Appear in Reflect`, `ADBE Group End`.

AE does not write every property of a group. Empty Masks, Effects, Motion
Trackers and Text Animators groups are left out, and so are many streams:
in the AE-generated samples, 573 of about 810 AV layers have no
`ADBE Anchor Point`, `ADBE Position` or `ADBE Scale` in their Transform
group at all. A reader
must supply the default value of a missing property; a writer that gives
one a value must insert its `tdmn` + body at the canonical position.

Every group, including a newly built one, must end with the
`ADBE Group End` match name; a group without it makes AE refuse the file
("missing data in file").

### `tdmn`

The match name of the child that follows (or `ADBE Group End`).

**Parent:** [`LIST:tdgp`](#listtdgp), [`LIST:parT`](#listpart), [`LIST:EfDf`](#listefdf) · **Size:** 40 bytes · **py_aep:** `TdmnChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 40 | char[40] ASCII | Match name, NUL-padded (`ADBE Position`, `ADBE Effect Parade`, ...). The longest in the samples is 36 characters; the padding is always zeros. Effect parameters are named `<effect match name>-NNNN` with a four-digit parameter index (`ADBE Gaussian Blur 2-0001`); `-0000` is a hidden first parameter every effect carries. |

### `tdsb`

Flags of a property group or stream, one big-endian 32-bit word.

**Parent:** [`LIST:tdgp`](#listtdgp) (first child), [`LIST:tdbs`](#listtdbs) (first child) · **Size:** 4 bytes · **py_aep:** `TdsbChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Flags (bits below). |

| Bit | Mask | Meaning |
|---|---|---|
| 0 | 0x00000001 | Enabled. Functional: a cleared bit disables the group or stream (a layer style that is switched off stores 0x2). |
| 1 | 0x00000002 | Hidden in the Timeline: the property does not apply to the layer as it is (a 3D-only property on a 2D layer, another light type's option, the unused half of a separable Position, an effect parameter its plugin hides). AE recomputes it when it opens a project, so it never changes rendering; AE refuses an expression on a hidden stream. |
| 4 | 0x00000010 | Unknown. Set on a few groups and streams (`ADBE Plane Options Group`, `ADBE Text Render Order`, `ADBE Text Character Blend Mode`). |
| 9 | 0x00000200 | Unknown. Set on some transform streams (Position, Opacity, Rotation, Scale) in production projects only (161 chunks). |
| 10 | 0x00000400 | Set on `ADBE Root Vectors Group`, `ADBE Vectors Group` and `ADBE Data Group` (inferred: listed in the Timeline even when empty). |
| 11 | 0x00000800 | Dimensions separated, on the separation leader (`ADBE Position`): ExtendScript `dimensionsSeparated`. Agrees with every AE-exported value in the samples (288 of 288). |
| 13 | 0x00002000 | X/Y link off: the constrain-proportions switch of `ADBE Scale` (or `ADBE Mask Feather`) is unlinked. Polarity inferred from `scale_unlinked.aep`. |
| 24 | 0x01000000 | RotoBezier, on a mask or shape path stream (`ADBE Mask Shape`). |

All other bits (2, 3, 5-8, 12, 14-23, 25-31) are 0 in all 1.1 million
`tdsb` chunks of the sample corpus; in particular there is no saved
"locked ratio" bit 12.

Values in AE's own files: a visible stream stores 0x1, a hidden one 0x3. A
separable Position that is not separated stores 0x1 on `ADBE Position` and
0x3 on `ADBE Position_0`/`_1`/`_2`; once separated, 0x803 on the leader and
0x1 on the followers (which then carry the values and keyframes - the
leader's stored value is a default AE does not use). Groups store 0x1, 0x2
(disabled layer style), 0x3, 0x401 / 0x403 (bit 10) or 0x11.

### `LIST:tdbs`

A property stream: one animatable value with its flags, metadata and either
a static value or keyframes.

**Parent:** [`LIST:tdgp`](#listtdgp), [`LIST:otst`](#listotst), [`LIST:om-s`](#listom-s), [`LIST:mrst`](#listmrst), [`LIST:btds`](#listbtds), [`LIST:GCst`](#listgcst)

| Child | Occurs | Description |
|---|---|---|
| [`tdsb`](#tdsb) | 1, required | Stream flags. |
| [`tdsn`](#tdsn) | 1, required | Display name (one [`Utf8`](#utf8)): `-_0_/-` for the default name; empty on an effect's hidden `-0000` parameter; some effect parameters store their parameter name. |
| [`tdb4`](#tdb4) | 1, required | Stream metadata. |
| [`cdat`](#cdat) or [`LIST:list`](#listlist) | 1, required | The static value, or the keyframes (header [`lhd3`](#lhd3) + items [`ldat`](#ldat)). |
| [`Utf8`](#utf8) | 0-1 | The expression, when the stream has one. |
| [`tdli`](#tdli) | 0-1 | Mask reference of a path parameter (effects only). |
| [`tdum`](#tdum) + [`tduM`](#tdum) | 0-1 pair | Minimum and maximum; only on the stream kinds listed under [`tdum`](#tdum). |
| [`tdpi`](#tdpi) + [`tdps`](#tdps) | 0-1 pair | Layer reference (effect layer parameters, `ADBE Paint Clone Layer`). |

The child orders in the samples are exactly `tdsb tdsn tdb4 (cdat |
LIST:list) [Utf8] [tdum tduM | tdpi tdps | tdli]`. AE reads these chunks in
that order; keep it.

#### Stream kinds

The value layout depends on [`tdb4`](#tdb4): its dimension count (0x02), its
stream flags (0x04, bit 1 "single-ease layout") and its valueless flag
(0x38 bit 0). The kinds AE writes:

| Kind | Examples | Dims | Flags (static / animated) | Valueless | Static `cdat` | Keyframe item | Value container |
|---|---|---|---|---|---|---|---|
| 1-D number | Opacity, Rotation, sliders, menus | 1 | 0x01 / 0x00 | 0 | 40 bytes | 48 bytes | - |
| 2-D number | shape Size, Mask Feather | 2 | 0x01 / 0x00 | 0 | 80 bytes | 88 bytes | - |
| 3-D number | Scale | 3 | 0x01 / 0x00 | 0 | 120 bytes | 128 bytes | - |
| 2-D spatial | effect points, shape Position | 2 | 0x0F / 0x0E | 0 | 48 bytes | 104 bytes | - |
| 3-D spatial | Position, Anchor Point | 3 | 0x0F / 0x0E | 0 | 72 bytes | 128 bytes | - |
| Colour | Shadow Color, Color Control | 4 | 0x07 / 0x06 | 0 | 96 bytes | 152 bytes | - |
| Orientation | `ADBE Orientation` | 1 | 0x07 / 0x06 | 1 | 24 bytes | 80 bytes | [`LIST:otky`](#listotky) |
| Path, gradient | mask and shape paths, gradient colours | 1 | 0x07 / 0x06 | 1 | 4 bytes | 64 bytes | [`LIST:omks`](#listomks), [`LIST:GCky`](#listgcky) |
| Text, markers | `ADBE Text Document`, `ADBE Marker` | 1 | 0x01 / 0x00 | 1 | 4 bytes | 16 bytes | [`LIST:btdk`](#listbtdk), [`LIST:mrky`](#listmrky) |
| Layer Source Alternate | (after `blsv`/`blsi`) | 1 | 0x01 | 1 | 4 bytes | - | - |

3-D numbers and 3-D spatial streams both use 128-byte keyframe items; the
stream flags decide which layout they follow. Valueless streams keep their
real value in the sibling container listed; their [`cdat`](#cdat) and the
value part of their keyframe items are placeholders.

#### Expressions

An expression is stored as a [`Utf8`](#utf8) child right after the value
(`cdat` or `LIST:list`) and before any `tdum`/`tduM`. The text is UTF-8,
line breaks as typed (CRLF in the samples). [`tdb4`](#tdb4) records it
twice: 0x78 holds 0x01000000 exactly when the `Utf8` is present (in all 47
expression streams of the samples, and nowhere else), and bit 0 of 0x77 is
set when the expression is disabled (`expressionEnabled = false`). AE
refuses a file whose `tdb4` claims an expression that has no `Utf8`
("missing data in file").

#### Static and animated streams

A stream is static (one value in [`cdat`](#cdat)) or animated (a
[`LIST:list`](#listlist) of keyframes in the same slot). When the first
keyframe is added, AE replaces the `cdat` with the list and changes only
these [`tdb4`](#tdb4) bytes - verified by comparing every match name that
appears both static and animated in the samples (19 kinds):

- clears bit 0 of the stream flags (0x05);
- sets 0x44 to 1;
- clears bit 0 of 0x4F (set on static streams whose flags have bit 1);
- zeroes the keyframe record at 0x48-0x73 (all zero on every animated
  stream).

Dimensions, masks, type and category bytes, time base and multipliers stay
as they were. Valueless kinds keep their value container unchanged: a
static mask path, Orientation, gradient or text document already holds
exactly one value in its container, and adding the first keyframe does not
touch it (a static marker stream has an empty marker list).

Removing the last keyframe does the reverse: the list becomes a `cdat`
again (the empty 4-byte placeholder for valueless kinds, the three
little-endian angles for Orientation, otherwise the value padded with
zeros to 3 doubles per dimension when the stream flags have bit 1, 5
otherwise), bit 0 and 0x4F bit 0 come back, 0x44 is cleared, and the
record takes the removed keyframe's in/out interpolation at 0x4C/0x4D (1/1
for linear keys: mask path, Orientation, Position, Scale, Opacity, colours;
3/3 for hold keys: text, marker) and its spatial flags at 0x50 (1 on a
Position whose key was spatially continuous). Everything else in `tdb4`
keeps its animated value (measured on AE 2026 for those streams and a
shape group's Position and Fill Color).

A stream that was never set or animated (as AE writes many defaults) also
differs from an animated one in the value-hint and interpolation bytes
(0x06-0x0B), the time base and the category, which are zero (0x0B: 2): a
shape group's Position goes from `0009 0000 0000 0002`, time base 0 and
category 0 to `000E 0003 FFFF FFFF`, 0x6000 and 9 when AE adds its first
keyframe, and keeps those bytes when the keyframes are removed again. A
static stream written with the never-set bytes but a non-default value is
not read back: AE 2026 shows a layer or shape group Position at its
default and fails to evaluate a shape Fill Color ("time stream with no key
values") written that way.

Mask path, Orientation and text containers keep the last value; the marker
list is emptied; AE deletes a shape gradient's whole `tdmn` +
[`LIST:GCst`](#listgcst) pair (measured on AE 2026).

Bounds chunks ([`tdum`](#tdum)/[`tduM`](#tdum)) stay where they are in both
states, after the value and the expression. A stream that AE writes with
bounds must keep them: AE refuses a file where `ADBE Scale` has lost its
`tdum`/`tduM` ("missing data in file").

### `tdb4`

Stream metadata: dimensions, stream flags, interpolation masks, time base,
motion-path measuring parameters, value type, animated flag, a stored
keyframe record and the expression flags.

**Parent:** [`LIST:tdbs`](#listtdbs) (third child) · **Size:** 124 bytes · **py_aep:** `Tdb4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | Magic 0xDB99 in every sample. |
| 0x02 | 2 | u2 | Dimensions: 1-3, 4 for a colour. Orientation stores 1 (its three angles are one value). |
| 0x04 | 2 | u2 | Stream flags (bits below). |
| 0x06 | 2 | u2 | Spatial interpolation setting (inferred). 3 on spatial streams (Position, Anchor Point, effect and shape points), 1 on mask and shape paths and layer-style colours, 0 elsewhere. |
| 0x08 | 2 | u2 | Spatial interpolation mask (inferred). 0xFFFF on spatial streams and many others, 0x0001 on most non-spatial numbers, 0x0002 on colours, paths and some angles, 0x0006 on Orientation. |
| 0x0A | 2 | u2 | Interpolation mask: which keyframe interpolation types the stream allows (inferred: bit 0 Linear, bit 1 Bezier, bit 2 Hold). 0xFFFF on most streams, 0x0007 on Orientation and paths, 0x0004 on hold-only streams (menus, checkboxes, text documents, markers), 0x0000 on streams that cannot be animated. For 132 of the 137 layer-property match names in the samples, bit 1 equals ExtendScript's `canVaryOverTime` (valueless streams always report true); the exceptions are hold-only menus and checkboxes such as `ADBE Camera Depth of Field`, `ADBE Iris Shape` and `ADBE Light Falloff Type`, which report true. Effect parameters follow their [`pard`](#pard) flags. |
| 0x0C | 4 | u4 | Time base: keyframe time units per second of the owning layer's time. The composition timebase up to 100 % stretch; past it, `floor(composition timebase x s)` with `s` the stretch / 100 rounded to 16.16 fixed point, capped at 115200 (500 % at 24 fps stores 115200, not 122880; 116 % at 99.123 fps stores 114983). Equals the composition timebase ([`cdta`](#cdta)) for an unstretched layer (24576 at 24 fps, 25600 at 25, 30720 at 30, 23976 at 23.976); a 300 % stretch at 24 fps stores 73728, so the full 32 bits are used. Present on static streams too. |
| 0x10 | 8 | f8 | Arc accuracy: the tolerance (a squared distance) AE fits a spatial segment's length to. 0.0001 for values stored in pixels; 6.25e-12 for points stored as a fraction of the layer (effect points) and on some Anchor Point streams. |
| 0x18 | 8 | f8 | X multiplier applied before measuring a motion path: the composition's pixel aspect ratio on a layer's Position and Anchor Point, the layer's width / height on a point stored as a fraction of the layer (and on mask paths, inferred); 1.0 elsewhere. |
| 0x20 | 8 | f8 | Y multiplier. 1.0 in every sample. |
| 0x28 | 8 | f8 | Z multiplier. 1.0 in every sample. |
| 0x30 | 8 | f8 | Fourth multiplier. 1.0 in every sample. |
| 0x38 | 2 | u2 | Value flags. Bit 0: valueless stream (text document, mask and shape paths, markers, gradients, Orientation, Layer Source Alternate, an effect's arbitrary-data parameter). Other bits 0. |
| 0x3A | 2 | u2 | Type flags (table below). |
| 0x3C | 4 | u4 LE | Category (table below). The only little-endian field of the chunk; the values fit in its first byte. |
| 0x40 | 4 | bytes | 0 in every sample. |
| 0x44 | 1 | u1 | Animated: 1 when the stream holds a keyframe list, 0 when it holds a `cdat`. |
| 0x45 | 3 | bytes | 0 in every sample. |
| 0x48 | 4 | s4 | Keyframe record, time: 0 on layer properties; on static effect parameters 0x80000000 ("no time"), 0 or another time value (each about a third of the corpus). |
| 0x4C | 1 | u1 | Keyframe record, in interpolation (values as in a keyframe item: 1 Linear, 2 Bezier, 3 Hold). 3 on most static Position and Anchor Point streams, 1 or 3 after keyframes were removed (see [`LIST:tdbs`](#listtdbs)), otherwise 0. |
| 0x4D | 1 | u1 | Keyframe record, out interpolation. Equal to 0x4C in nearly every sample. |
| 0x4E | 2 | u2 | Keyframe record, key flags. Bit 0 is set exactly on static streams whose stream flags have bit 1 (all 678,000 streams of the sample corpus follow this); 7 or 8 also seen on static streams. 0 on animated streams. |
| 0x50 | 4 | u4 | Keyframe record, spatial flags: 0-3 or 7 in the samples (inferred: same bits as a keyframe item's spatial flags). |
| 0x54 | 8 | f8 | Keyframe record, in speed. |
| 0x5C | 8 | f8 | Keyframe record, in influence (0.16666666667, 0.33333333, 0.75 seen). |
| 0x64 | 8 | f8 | Keyframe record, out speed. |
| 0x6C | 8 | f8 | Keyframe record, out influence. |
| 0x74 | 4 | u4 | Expression flags. Bit 0 (byte 0x77): expression disabled. Also set on many Position and Anchor Point streams that have no expression. |
| 0x78 | 4 | u4 | 0x01000000 when an expression [`Utf8`](#utf8) follows the value, else 0. |

Stream flags at 0x04:

| Bit | Mask | Meaning |
|---|---|---|
| 0 | 0x0001 | Static: the stream has no keyframes. Cleared when animated. |
| 1 | 0x0002 | Single-ease layout: keyframes carry one temporal ease for the whole value plus per-dimension tangents, and the static `cdat` holds 3 doubles per dimension instead of 5. Set on spatial streams, colours, Orientation, paths and gradients. |
| 2 | 0x0004 | Set together with bit 1 in every sample; meaning not decoded. |
| 3 | 0x0008 | Spatial: the values form a motion path (Position, Anchor Point, effect and shape points); keyframes can rove. |

Observed values: 0x01, 0x07, 0x0F on static streams; 0x00, 0x06, 0x0E on
animated ones.

Type flags (0x3B) and category (0x3C), as AE writes them:

| 0x3B | 0x3C | Streams |
|---|---|---|
| 0x08 | 9 | Most numeric streams: Position, Anchor Point, Scale, Rotation, Opacity, Time Remapping, material coefficients, shape sizes, many effect sliders. |
| 0x04 | 4 | Menus and checkboxes (`ADBE Casts Shadows`, `ADBE Bevel Direction`, layer-style modes and switches) and an effect's `-0000` parameter. |
| 0x04 | 6 | Layer-style angles, `ADBE Mask Feather`, `ADBE Mask Opacity`, some effect parameters (points, Drop Shadow distance and softness). |
| 0x04 | 8 | Camera iris options, shape stroke width and miter limit, star radii and roundness. |
| 0x01 | 1 | Colours (4 dimensions). |
| 0x08 | 0 | Valueless streams (0x38 bit 0 set). |
| 0x18 | 0 | `ADBE Orientation` (valueless). |

Bit 0 of 0x3B marks a colour and bit 4 appears only on Orientation; the
meaning of bits 2 and 3 and of the category values is not decoded beyond
this table. Neither byte changes when a stream is animated.

The keyframe record at 0x48-0x73 has the same field order as the start of a
keyframe item (time, in and out interpolation, key flags, spatial flags,
then in speed, in influence, out speed and out influence, without the
segment length). It is all zero on every animated stream; on static streams
it keeps values such as the interpolation and ease of keyframes that were
removed (inferred). Files that store zeros there (except bit 0 of 0x4E)
open normally.

Notes for writers:

- The time base must be the owning layer's. A stream whose time base is 0
  makes AE refuse the file ("zero denominator converting ratio
  denominators"), static or not. When a composition's frame rate or a
  layer's stretch changes, every stream of the affected layers needs the new
  value (and the keyframe times rescaled, see [`ldat`](#ldat)).
- 0x18 must hold the composition's pixel aspect ratio on a layer's Position
  and Anchor Point; Orientation keeps 1.0 even though it is a spatial-looking
  stream.
- Animate / de-animate by changing only the bytes listed under
  [Static and animated streams](#static-and-animated-streams).

### `cdat`

The static value of a stream.

**Parent:** [`LIST:tdbs`](#listtdbs) (fourth child, in place of [`LIST:list`](#listlist)) · **Size:** see below · **py_aep:** `CdatChunk`

The value block has the layout of a keyframe item's value part, with
everything but the value set to zero:

- Streams without stream-flag bit 1 (numbers, menus): `dims x 5` big-endian
  f8. The first `dims` doubles are the value; the rest (the places of the
  in speed, in influence, out speed and out influence) are 0 in every
  sample. 40, 80 or 120 bytes.
- Streams with stream-flag bit 1 (spatial, colour): `dims x 3` big-endian
  f8: the value, then the in and out tangents, which are 0 in every sample.
  48 or 72 bytes for 2-D / 3-D points, 96 bytes for a colour.
- Orientation (inside [`LIST:otst`](#listotst)): three **little-endian** f8,
  the X, Y and Z angles in degrees (24 bytes). The same angles are in the
  sibling [`otda`](#otda), big-endian.
- Other valueless streams (paths, gradients, text, markers, Layer Source
  Alternate): 4 zero bytes. A few samples have 8 bytes that vary between
  saves instead; write the 4 zero bytes. A zero-padded double block here
  makes AE refuse the file ("chunk in file too big").

Values are in AE's stored units, which are not always the units ExtendScript
reports:

| Stream | Stored as |
|---|---|
| `ADBE Opacity`, `ADBE Scale` | A fraction: 1.0 = 100 %. |
| Colours | Four doubles A, R, G, B in 0-255 (opaque red = 255, 255, 0, 0). |
| Effect point parameters | A fraction of the layer's width and height (0.5 = centre). |
| Position, Anchor Point, rotations, Light Intensity, most others | The value ExtendScript reports (pixels, degrees, percent, seconds). |

### `tdum`

Minimum (`tdum`) and maximum (`tduM`) of a stream; two chunks with the same
layout, `tdum` first.

**Parent:** [`LIST:tdbs`](#listtdbs) (after the value and any expression) · **Size:** 8 bytes each · **py_aep:** `TdumChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 8 | f8 | The bound. Every `tdum` / `tduM` in the samples is 8 bytes. |

On layer properties the pair appears on numeric streams that are not
angles, menus, checkboxes, colours or spatial streams. Effect parameters
keep their real bounds in [`pard`](#pard); about one in six effect
parameters of the production samples also carries a pair (none in the small
AE-generated samples), holding the slider range rather than the valid range
(inferred: `ADBE Slider Control` 0 / 100, `ADBE Gaussian Blur 2` 0 / 50,
`ADBE Fractal Noise` 20 / 600). Layer-property examples:

| Stream | `tdum` / `tduM` |
|---|---|
| `ADBE Opacity`, material coefficients, iris options, layer-style opacities | 0.0 / 100.0 (in ExtendScript units: Opacity stores its value as 0-1 but its bounds as 0-100) |
| `ADBE Index of Refraction` | 1.0 / 2.0 |
| `ADBE Plane Subdivision` | 2.0 / 256.0 |
| `ADBE Camera Split Blur Level`, `ADBE Vector Rect Size` | -32000.0 / 32000.0 |
| `ADBE Position_0`/`_1`/`_2`, `ADBE Scale`, `ADBE Time Remapping`, camera focus distance | 0.0 / 0.0 - a placeholder: ExtendScript reports no bounds for these. |

AE expects the pair on exactly the streams it writes it for; dropping it
from `ADBE Scale` makes AE refuse the file. When a writer creates such a
stream it must write the pair (0.0 / 0.0 where AE has no bounds).

### `tdli`

Mask reference of an effect path parameter (a `PF_Param_PATH` parameter
such as Stroke's Path, Audio Spectrum's Path or Smear's masks).

**Parent:** [`LIST:tdbs`](#listtdbs) (after the value) · **Size:** 4 bytes · **py_aep:** `S4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | s4 | 0 in most samples, 1 in a few (inferred: 0 = no mask, n = the n-th mask of the layer). |

### `tdpi`

Layer reference of an effect layer parameter.

**Parent:** [`LIST:tdbs`](#listtdbs) (after the value, before [`tdps`](#tdps)) · **Size:** 4 bytes · **py_aep:** `S4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | s4 | A layer id ([`ldta`](#ldta) 0x00). On every effect's hidden `-0000` parameter it is the id of the layer the effect is applied to; on a layer parameter (Layer Control, Set Matte's "Take Matte From Layer", `ADBE Paint Clone Layer`) it is the referenced layer, 0 = none. |

The referenced layer must exist in the same composition: AE refuses a file
whose layer parameter names a layer the composition does not contain
("Can't find layer ID=N in composition X"). AE rewrites the `-0000` value
when a layer is duplicated.

### `tdps`

Companion of [`tdpi`](#tdpi).

**Parent:** [`LIST:tdbs`](#listtdbs) (after [`tdpi`](#tdpi)) · **Size:** 4 bytes · **py_aep:** `S4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | s4 | Unknown. 0 in nearly every sample, -1 in a few. |

### `LIST:list`

A generic typed list: a header and, when the list is not empty, the items
back to back. Under a [`LIST:tdbs`](#listtdbs) it is the stream's keyframe
list.

**Parent:** [`LIST:tdbs`](#listtdbs) (keyframes), [`LIST:Gide`](#listgide) (guides), [`LIST:shap`](#listshap) (mask and shape vertices), [`LIST:LRdr`](#listlrdr) and [`LIST:LItm`](#listlitm) (render queue records)

| Child | Occurs | Description |
|---|---|---|
| [`lhd3`](#lhd3) | 1, required | Header: item count, item size, item type. |
| [`ldat`](#ldat) | 0-1 | The items. Absent when the count is 0 (empty guide lists); a keyframe list always has at least one item. |

### `lhd3`

Header of a [`LIST:list`](#listlist).

**Parent:** [`LIST:list`](#listlist) (first child) · **Size:** 52 bytes · **py_aep:** `Lhd3Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Magic 0x00D00BEE in every sample. |
| 0x04 | 4 | u4 | 0 in every sample. |
| 0x08 | 4 | u4 | Item count. The [`ldat`](#ldat) body is exactly count x item size bytes. |
| 0x0C | 4 | u4 | Allocated blocks: `ceil(count / block size)`, minimum 1. |
| 0x10 | 4 | u4 | Item size in bytes (keyframes: 16-152, see [`ldat`](#ldat); guides 16; vertices 8; render queue 2246 and 128). |
| 0x14 | 4 | u4 | Item type: 4 = keyframes and path vertices, 2 = guides, 1 = render queue and output module records. |
| 0x18 | 4 | u4 | The number of blocks when the block size is 1, else 1. |
| 0x1C | 4 | u4 | Capacity in items: blocks x block size. |
| 0x20 | 20 | bytes | 0 in every sample. |

Block sizes: 4 for keyframes and path vertices, 2 for guides, 1 for render
queue and output module records (all AE-written samples). An empty guide
list stores count 0 with counters 1, 1, 2. AE validates the counters
against the count when it loads a list and refuses the file when they
disagree ("Invalid read length"). AE's own path vertex lists sometimes
reserve more blocks than needed (12 vertices in 4 blocks, capacity 16);
writers should use the minimum.

### `ldat`

The items of a [`LIST:list`](#listlist): `count` records of `item size`
bytes, no padding between them. The record layout depends on the parent
list: guides are documented with [`LIST:Gide`](#listgide), path vertices
with [`LIST:shap`](#listshap), render queue records with
[`LIST:LRdr`](#listlrdr) and [`LIST:LItm`](#listlitm). This section
documents keyframe items, the items of a list inside a
[`LIST:tdbs`](#listtdbs).

**Parent:** [`LIST:list`](#listlist) · **Size:** count x item size · **py_aep:** `LdatChunk`

#### Keyframe items

Keyframes are sorted by time. Every item starts with the same 8-byte
header:

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | s4 | Time, in the stream's time units ([`tdb4`](#tdb4) 0x0C) of layer time: `seconds = time / time base`, counted from the layer's start time. Negative times occur. 0x80000000 means "no time". |
| 0x04 | 1 | u1 | In interpolation: 1 Linear, 2 Bezier, 3 Hold (the AE SDK `AEGP_KeyInterp` values; ExtendScript 6612-6614). |
| 0x05 | 1 | u1 | Out interpolation, same values. |
| 0x06 | 2 | u2 | Key flags (bits below). |

Key flags at 0x06:

| Bit | Mask | Meaning |
|---|---|---|
| 0-2 | 0x0007 | 0x7 on every spatial keyframe, 0x1 on colour, Orientation, path and gradient keyframes, 0 on the others; meaning not decoded. |
| 3 | 0x0008 | Temporal continuous (`temporalContinuous`). |
| 4 | 0x0010 | Temporal auto-Bezier (`temporalAutoBezier`). ExtendScript also reports the key as continuous. |
| 5 | 0x0020 | Roving (`roving`), spatial streams only. |
| 6-10 | 0x07C0 | Label colour, 0-16 (`(flags >> 6) & 0x1F`; label 1 = 0x0040, 5 = 0x0140, 16 = 0x0400). |
| 11-15 | 0xF800 | 0 in every sample. |

The rest of the item depends on the stream ([`tdb4`](#tdb4) stream flags
bit 1, dimensions and valueless flag).

**Without stream-flag bit 1** (numbers; text documents and markers), the
value block starts at 0x08:

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x08 | 8 x dims | f8[dims] | Value. |
| ... | 8 x dims | f8[dims] | In speed, per dimension. |
| ... | 8 x dims | f8[dims] | In influence, per dimension (a fraction: 0.33 = 33 %). |
| ... | 8 x dims | f8[dims] | Out speed, per dimension. |
| ... | 8 x dims | f8[dims] | Out influence, per dimension. |

So a 1-D item is 48 bytes (value, in speed, in influence, out speed, out
influence), a 2-D item 88 and a 3-D item 128. Text document and marker
items (16 bytes) have 8 bytes at 0x08 instead: they vary between saves and
carry nothing (the value is in [`LIST:btdk`](#listbtdk) or
[`LIST:mrky`](#listmrky)); write zeros. Their interpolation bytes are 3/3
(hold).

**With stream-flag bit 1** (spatial, colour, Orientation, paths,
gradients), one ease for the whole value:

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x08 | 4 | u4 | Spatial flags: bit 0 spatial continuous (`spatialContinuous`), bit 1 spatial auto-Bezier (`spatialAutoBezier`). 1 or 3 on spatial keys, 0 elsewhere. |
| 0x0C | 4 | u4 | 0 in every sample. |
| 0x10 | 8 | f8 | Length of the segment to the next keyframe, 0 on the last keyframe: the motion path's arc length for spatial streams (in the measuring units of [`tdb4`](#tdb4) 0x18), the colour distance in 0-255 units for colours (360.62 = 255 x sqrt(2) from red to blue), the segment duration in seconds for Orientation, paths and gradients. Some samples store 0 here; files that store 0 open normally. |
| 0x18 | 8 | f8 | In speed (one value: units per second along the path for spatial streams). |
| 0x20 | 8 | f8 | In influence (fraction). |
| 0x28 | 8 | f8 | Out speed. |
| 0x30 | 8 | f8 | Out influence (fraction). |
| 0x38 | ... | | Value block (below). |

Value block at 0x38:

- Spatial streams: `f8[dims]` value, `f8[dims]` in tangent, `f8[dims]` out
  tangent. Tangents are offsets from the value (`inSpatialTangent`,
  `outSpatialTangent`). 2-D items are 104 bytes, 3-D items 128.
- Colours: `f8[4]` A, R, G, B (0-255), then 8 doubles in the places of the
  tangents, 0 in every sample. 152 bytes.
- Orientation: the X, Y and Z angles in degrees as three **little-endian**
  f8, a copy of the keyframe's [`otda`](#otda). 80 bytes.
- Paths and gradients: 8 bytes that vary between saves and carry nothing
  (the value is in [`LIST:omks`](#listomks) or [`LIST:GCky`](#listgcky));
  write zeros. 64 bytes.

The item sizes, stream by stream, are in the
[stream kinds table](#stream-kinds). Speeds are in the stream's stored units
per second (an `ADBE Opacity` out speed of 0.2 reads as 20 %/s in
ExtendScript). Influences are fractions from 0 to 1; AE's default influence
is the decimal 0.16666666667 (not exactly 1/6), which appears 37,000 times in
the sample corpus.

#### Interpreting keyframes

Rules measured on AE 2026 (and checked against AE 2018 files where noted);
a writer needs them to produce keyframes AE will display the way the stored
values say.

- **Time.** A key's composition time is `start_time + (time / time base) x
  stretch / 100`. With a negative stretch AE also shifts by
  `-(abs(stretch) / 100) / 3000` seconds. Times need not fall on frames
  (`setValueAtTime(1.5)` in a 25 fps composition stores 38400 = frame
  37.5). When a layer's stretch changes, AE keeps keys at the same layer
  time and rescales the stored counts with the new time base (a key at
  layer second 1 holds 24576 at 100 % and 49152 at 200 %). When a
  composition's frame rate changes, AE keeps keys at the same time in
  seconds and rescales the counts by `new time base / old time base`.
- **Segment type.** The segment between keys A and B uses A's out type and
  B's in type. Hold on A's out side keeps A's value until B. Linear on both
  sides is a straight line (in distance along the path, for a spatial
  stream).
- **Temporal Bezier (non-spatial streams).** Per dimension, with
  `dt = tB - tA`, out ease (speed `so`, influence `io`) of A and in ease
  (`si`, `ii`) of B, the curve has the control points `(tA, vA)`,
  `(tA + dt x io, vA + dt x io x so)`, `(tB - dt x ii, vB - dt x ii x si)`,
  `(tB, vB)`. The handles are absolute, so a segment between two equal
  values still bows when its speeds are not 0. A Linear side in a mixed
  segment acts as the segment's average slope with influence
  0.16666666667 (the ease AE reports for it; inferred for evaluation).
- **Spatial streams.** The path from A to B is the cubic `vA`,
  `vA + outTangentA`, `vB + inTangentB`, `vB` (the path always follows the
  tangents, whatever the interpolation types). The ease maps time to
  distance along that path: a curve in (seconds, distance) from `(0, 0)` to
  `(dt, D)`, D the arc length, with handles `(dt x io, dt x io x so)` and
  `(dt - dt x ii, D - dt x ii x si)`; a Linear side's handle is at
  0.16666666667 of the way along the chord, and Linear on both sides is
  constant speed. AE measures the length with each dimension multiplied by
  the [`tdb4`](#tdb4) multipliers (0x18-0x37). A spatial speed is never
  negative. Hold on either side keeps the start value.
- **The stored ease is kept.** Switching a key between Linear, Hold and
  Bezier never rewrites its stored speeds and influences: AE only reports
  derived values while the type is Linear or Hold (segment slope or 0, with
  influence 16.666666667 %) and returns the stored ones when the key is
  Bezier again. AE's own Linear and Hold keys store 0.
- **Auto-Bezier.** When key flag bit 4 is set, AE ignores the stored ease
  and uses, per dimension, the slope between the two neighbouring keys
  (`(v_next - v_prev) / (t_next - t_prev)`) on both sides, influence
  0.16666666667; an end key uses its single segment's slope on the inner
  side and 0 on the outer side. AE stores zeros there. When spatial flag
  bit 1 is set, AE ignores the stored tangents and uses
  `out = (P_next - P_prev) / 6`, `in = -out` (an end key uses its single
  neighbour), independent of the key times. Both rules hold in AE 2018 and
  AE 2026 files.
- **Continuous.** With key flag bit 3 set, AE keeps the out speed equal to
  the in speed (setting the flag in AE copies the in speed to the out
  speed and makes both sides Bezier).
- **Roving.** A roving key's stored time is derived: AE places it where the
  span between the enclosing non-roving keys has travelled its share of the
  path's arc length (eased once over the whole span), rounds to a time unit,
  and recomputes it whenever the path changes. Roving is only valid between
  two non-roving keys of a spatial stream; writers should store the derived
  time.

### `LIST:otst`

The body of `ADBE Orientation`: the orientation stream and its per-keyframe
angles.

**Parent:** [`LIST:tdgp`](#listtdgp)

| Child | Occurs | Description |
|---|---|---|
| [`LIST:tdbs`](#listtdbs) | 1, required, first | The stream: [`tdb4`](#tdb4) with dims 1, valueless flag set, type flags 0x18; [`cdat`](#cdat) with the three angles as little-endian f8 when static, or a [`LIST:list`](#listlist) of 80-byte keyframe items when animated. |
| [`LIST:otky`](#listotky) | 1, required, second | The angles, one [`otda`](#otda) per keyframe (one for a static stream). |

The two copies of the angles (the little-endian `cdat` or keyframe item
value block, and the big-endian `otda`) hold the same numbers in every
sample; write both. A camera's Orientation that was never modified can
also appear as a bare [`LIST:tdbs`](#listtdbs) with dims 3 and no
`LIST:otst` around it; giving it a keyframe wraps it in `LIST:otst`
(measured on AE 2026).

### `LIST:otky`

The orientation values, in keyframe order.

**Parent:** [`LIST:otst`](#listotst)

| Child | Occurs | Description |
|---|---|---|
| [`otda`](#otda) | 1 per keyframe (1 when static), required | The X, Y, Z angles of that keyframe. |

### `otda`

One orientation value.

**Parent:** [`LIST:otky`](#listotky) · **Size:** 24 bytes · **py_aep:** `OtdaChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 8 | f8 | X angle in degrees. |
| 0x08 | 8 | f8 | Y angle in degrees. |
| 0x10 | 8 | f8 | Z angle in degrees. |

Big-endian, unlike the copies in the stream's [`cdat`](#cdat) and keyframe
items, which are little-endian.

## Masks, shapes, paint, markers and effects

This section covers the property values that do not fit the generic stream of
[`LIST:tdbs`](#listtdbs): mask settings and paths, bezier paths in general
(mask paths, shape-layer paths, paint strokes), markers, gradients, effect
instances with their parameter definitions and plug-in data, and the
feature-specific chunks that sit directly inside a [`LIST:tdgp`](#listtdgp) next
to a property's [`tdmn`](#tdmn).

Paths, markers and gradients share one layout: a wrapper LIST holds the
property's [`LIST:tdbs`](#listtdbs) (stream flags, name, [`tdb4`](#tdb4) and
the keyframe timing) followed by a value container that holds one value per
keyframe, in keyframe order, or a single value when the property is static.

| Wrapper | Value container | One value |
|---|---|---|
| [`LIST:om-s`](#listom-s) (path) | [`LIST:omks`](#listomks) | [`LIST:shap`](#listshap) |
| [`LIST:mrst`](#listmrst) (markers) | [`LIST:mrky`](#listmrky) | [`LIST:Nmrd`](#listnmrd) |
| [`LIST:GCst`](#listgcst) (gradient) | [`LIST:GCky`](#listgcky) | [`Utf8`](#utf8) |

When such a property is static its `LIST:tdbs` holds an empty 4-byte
[`cdat`](#cdat) (four zero bytes) and the container holds one value; when it
is animated the `LIST:tdbs` holds a [`LIST:list`](#listlist) of keyframes
(timing and easing only) instead of the `cdat`, and the container holds one
value per keyframe. Adding the first keyframe does not change the stored
value, and removing the last keyframe of a path in AE puts the `cdat` back
and keeps one value (measured on AE 2026); markers and gradients behave
differently, see [`LIST:mrst`](#listmrst) and [`LIST:GCst`](#listgcst).
Orientation (`LIST:otst`) and text (`LIST:btds`) use the same pattern and are
described with layers and text.

Unless noted, multi-byte values are big-endian. "In every sample" refers to the
sample corpus of this project (about 1,350 projects written by AE 2018 to AE 2026).

### `mkif`

Mask settings: inverted, locked, motion blur, feather falloff, mode, id and
outline colour. One per mask.

**Parent:** [`LIST:tdgp`](#listtdgp) of the `ADBE Mask Parade` group · **Size:** 48 bytes · **py_aep:** `MkifChunk`

The masks of a layer live in the `ADBE Mask Parade` group of the layer's
property tree. Each mask is a triplet: a [`tdmn`](#tdmn) `ADBE Mask Atom`,
this `mkif`, then the mask's [`LIST:tdgp`](#listtdgp) (the `mkif` sits between
the match name and the group it describes):

```
tdmn "ADBE Mask Parade"
LIST:tdgp
  tdsb, tdsn
  tdmn "ADBE Mask Atom"     -- one triplet per mask, in mask order
  mkif
  LIST:tdgp                 -- tdsb, tdsn (mask name, e.g. "Mask 1"), children, tdmn "ADBE Group End"
  ...
  tdmn "ADBE Group End"
```

Inside the mask group the children appear in this order, each one omitted
while it holds its default value: `ADBE Mask Shape` ([`LIST:om-s`](#listom-s)),
`ADBE Mask Feather`, `ADBE Mask Opacity`, `ADBE Mask Offset` (Mask Expansion),
the last three as plain [`LIST:tdbs`](#listtdbs) streams. A mask added by a
script has none of them; AE reads a mask without `ADBE Mask Shape` as a closed
rectangle covering the whole mask space (see [Mask space](#mask-space)). A
layer without masks has either no `ADBE Mask Parade` group or an empty one
(`tdsb`, `tdsn`, `ADBE Group End`). `mkif` is required in a mask triplet.

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | Inverted (`MaskPropertyGroup.inverted`): 1 = inverted, 0 = normal. |
| 0x01 | 1 | u1 | Locked (`MaskPropertyGroup.locked`): 1 = locked. |
| 0x02 | 1 | u1 | Mask motion blur (`AEGP_MaskMBlur`): 0 = Same as Layer, 1 = Off, 2 = On. |
| 0x03 | 1 | u1 | Mask feather falloff (`AEGP_MaskFeatherFalloff`): 0 = Smooth, 1 = Linear. |
| 0x04 | 4 | u4 | Mask mode (`PF_MaskMode`): 0 = None, 1 = Add, 2 = Subtract, 3 = Intersect, 4 = Lighten, 5 = Darken, 6 = Difference. Bytes 0x04-0x06 are 0 in every sample. |
| 0x08 | 4 | u4 | Mask id: 1-based, unique within the layer, assigned in creation order. AE gives a duplicated mask the highest id on the layer plus one and names it after that id: duplicating "Mask 1" on a layer whose masks have ids 1 and 3 gives id 4, "Mask 4". |
| 0x0C | 32 | bytes | Unknown. Changes on every save of the same project and often holds unrelated leftover bytes (fragments of match names); AE accepts zeros. |
| 0x2C | 1 | u1 | 0xFF in every sample (inferred: the alpha of the outline colour). |
| 0x2D | 1 | u1 | Outline colour, red (0-255) (`MaskPropertyGroup.color`). |
| 0x2E | 1 | u1 | Outline colour, green. |
| 0x2F | 1 | u1 | Outline colour, blue. |

AE assigns new masks a colour from a cycling palette whose position belongs
to the application, not to the project, so the same operation gives different
colours in different sessions; any colour is valid.

### `LIST:om-s`

A bezier path property. Three match names use it in the samples:
`ADBE Mask Shape` (Mask Path), `ADBE Vector Shape` (the Path of a shape-layer
path group) and `ADBE Paint Shape` (a paint stroke).

**Parent:** [`LIST:tdgp`](#listtdgp), right after the property's [`tdmn`](#tdmn)

| Child | Occurs | Description |
|---|---|---|
| [`LIST:tdbs`](#listtdbs) | 1, required | The path stream: flags, name, [`tdb4`](#tdb4). Static: an empty 4-byte [`cdat`](#cdat). Animated: a [`LIST:list`](#listlist) of keyframes carrying timing and easing but no path. |
| [`LIST:omks`](#listomks) | 1 | The path values. |

### `LIST:omks`

The path values of a [`LIST:om-s`](#listom-s).

**Parent:** [`LIST:om-s`](#listom-s)

| Child | Occurs | Description |
|---|---|---|
| [`LIST:shap`](#listshap) | 1 (static) or one per keyframe | One path per keyframe, in keyframe order (true of every animated path in the samples). |

### `LIST:shap`

One bezier path value.

**Parent:** [`LIST:omks`](#listomks)

| Child | Occurs | Description |
|---|---|---|
| [`shph`](#shph) | 1, required | Path header: open/closed flag and the box the points are normalized to. |
| [`LIST:list`](#listlist) | 1, required | The points: an [`lhd3`](#lhd3) followed by an [`ldat`](#ldat) of 8-byte items (below). |
| [`LIST:pnts`](#listpnts) | 0-1 | Paint stroke dynamics (`ADBE Paint Shape` only). |
| [`omtn`](#omtn) | 1, required | RotoBezier tensions, often empty but always present. |
| [`fth5`](#fth5) | 0-1 | Variable-width feather points (closed mask paths only). |

Children appear in the order listed (`shph, LIST:list, [LIST:pnts], omtn,
[fth5]` in every sample).

#### Vertex items

The [`lhd3`](#lhd3) of a path list has item size 8 and an item count of 3 x
the vertex count; the [`ldat`](#ldat) holds the items. Each item is one point:

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | f4 | x, normalized to the [`shph`](#shph) box (0 = left edge, 1 = right edge). |
| 0x04 | 4 | f4 | y, normalized to the box (0 = top edge, 1 = bottom edge). |

Points come in groups of three per vertex, in this order: vertex *i*, the
outgoing control point of vertex *i*, the incoming control point of vertex
*i*+1. The last item of the list is therefore the incoming control point of
vertex 0. Control points are absolute positions: after denormalizing (and
scaling to the mask space), ExtendScript's `Shape.outTangents[i]` is (point
3*i*+1) - (point 3*i*) and `Shape.inTangents[i]` is (point 3*i*-1, wrapping
to the last item) - (point 3*i*). Open paths use the
same 3n layout; the control points of the missing closing segment are stored
but unused. An empty path (no vertices) has the `lhd3` only, with no `ldat`.

Denormalizing a point: x = left + nx * (right - left), y = top + ny * (bottom -
top), with the box from [`shph`](#shph).

#### Mask space

The box and points of a path are expressed in the space of the property that
owns it (measured on AE 2026):

- `ADBE Mask Shape` on a layer that has a source (footage, solid,
  composition): fractions of the source size. Pixel coordinates are the
  denormalized point multiplied by the source width and height (a mask on a
  56 x 56 source in a 64 x 64 composition uses 56, not 64).
- `ADBE Mask Shape` on a text or shape layer (no source): the mask space is
  1 x 1, so the box and points are already in layer pixels.
- A mask with no `ADBE Mask Shape` stored is the closed rectangle
  `[[0, 0], [0, h], [w, h], [w, 0]]` of its mask space (the unit square on
  text and shape layers).
- `ADBE Vector Shape`: pixels in the coordinate space of the enclosing shape
  group.
- `ADBE Paint Shape`: small fractions of the layer size, relative to the
  stroke's `ADBE Paint Position` (inferred from the samples).

Two more values belong to a mask path but live in the Mask Shape's stream:

- The RotoBezier switch (`MaskPropertyGroup.rotoBezier`) is byte 0 of the
  [`tdsb`](#tdsb) inside the `ADBE Mask Shape` [`LIST:tdbs`](#listtdbs)
  (1 = on).
- The f8 at 0x18 of that stream's [`tdb4`](#tdb4) is the mask space's display
  aspect: source width x source pixel aspect / source height (1.0 on text and
  shape layers). RotoBezier tangents are computed in that aspect (see
  [`omtn`](#omtn)). 2,313 of 2,427 stored mask paths in the samples carry
  it; the rest hold a stale 1.0, which AE opens without complaint.

### `shph`

Path header: flags and the bounding box the points are normalized to.

**Parent:** [`LIST:shap`](#listshap) · **Size:** 24 bytes · **py_aep:** `ShphChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | 0xB3DE in every sample. |
| 0x02 | 1 | u1 | 2 in every sample (inferred: a path kind). |
| 0x03 | 1 | u1 | Flags (below). |
| 0x04 | 4 | f4 | Box left (x minimum). |
| 0x08 | 4 | f4 | Box top (y minimum). |
| 0x0C | 4 | f4 | Box right (x maximum). |
| 0x10 | 4 | f4 | Box bottom (y maximum). |
| 0x14 | 4 | u4 LE | 1 in every sample. |

Flags at 0x03:

| Bit | Mask | Meaning |
|---|---|---|
| 0 | 0x01 | Points are normalized to the box. Set in every sample; when it is clear AE reads the points as absolute coordinates, so writers must set it. |
| 3 | 0x08 | Open path (`Shape.closed` is false). |

The samples hold 0x01 (closed) or 0x09 (open); paint strokes are always open.
In about two thirds of the sample paths (3,584 of 5,172) the box is exactly
the bounds of all points, vertices and control points; in the others the
points do not reach every edge. The box of a mask path may extend past 0-1
when the mask reaches outside the layer.

### `omtn`

Per-vertex RotoBezier tensions of a path.

**Parent:** [`LIST:shap`](#listshap) · **Size:** 4 x vertex count, or 0 · **py_aep:** `OmtnChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 4 x *i* | 4 | f4 | Tension of vertex *i*: 0 = smoothest, 1 = corner (zero-length handles). |

The chunk is required but usually empty (5,134 of 5,172 sample paths): an
empty `omtn` means a tension of 1/3 for every vertex. When the mask's
RotoBezier switch is on, AE ignores the stored control points and recomputes
the handles from the vertices and these tensions. Setting
`MaskPropertyGroup.rotoBezier = true` from a script stores 1.0 on a path
whose vertices have no handles and 1/3 on a path with handles (AE 2026).

#### RotoBezier tangents

Measured on AE 2026 (matches its read-backs to float32 precision). Work with
the mask-space points with x multiplied by the aspect stored in the Mask
Shape's [`tdb4`](#tdb4) (0x18). For vertex *v* with tension *t*, let
*k* = (1 - *t*) / 2.

- Every vertex of a closed path, and every interior vertex of an open path:
  *u* = unit(next - previous) (zero when that distance is below 1e-12);
  in-tangent = -*u* * |*v* - previous| * *k*, out-tangent = *u* * |next - *v*| * *k*.
- Open path ends: first the last vertex, in-tangent = (*v*[n-2] + out[n-2] -
  *v*[n-1]) * *k*[n-1]; then the first vertex, out-tangent = (*v*[1] + in[1] -
  *v*[0]) * *k*[0]. On a two-vertex open path the first formula therefore uses
  an out-tangent of zero.
- A closed path with one or two vertices has zero tangents.
- Between keyframes the tensions are interpolated along with the path. A
  keyframe whose `omtn` is empty contributes, per vertex, 1.0 when both of its
  stored handles are zero and 1/3 otherwise; at a keyframe (or on a static
  path) an empty `omtn` is 1/3 regardless of the handles.

### `fth5`

Variable-width mask feather points (Mask Feather tool), listed in creation
order.

**Parent:** [`LIST:shap`](#listshap) (closed mask paths, after [`omtn`](#omtn)) · **Size:** 32 x point count · **py_aep:** `Fth5Chunk`

Each keyframe's [`LIST:shap`](#listshap) carries its own `fth5`. Absent when
the mask has no feather points.

#### Feather point record

The two integers are little-endian, the floats big-endian.

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 LE | Segment index, 0-based (`Shape.featherSegLocs`). |
| 0x04 | 4 | u4 LE | Radius interpolation: 0 = normal, 2 = hold (ExtendScript `featherInterps` 0 / 1). |
| 0x08 | 8 | f8 | Position along the segment, 0.0-1.0 (`featherRelSegLocs`). |
| 0x10 | 8 | f8 | Feather radius (`featherRadii`); negative = inner feather point (`featherTypes` 1). |
| 0x18 | 4 | f4 | Relative corner angle, percent (`featherRelCornerAngles`). |
| 0x1C | 4 | f4 | Tension, 0.0-1.0 (`featherTensions`). |

### `LIST:pnts`

Brush dynamics of one paint stroke (Paint, Clone Stamp and Eraser tools).

**Parent:** [`LIST:shap`](#listshap) of an `ADBE Paint Shape`

Paint strokes belong to the `ADBE Paint` effect. Its `ADBE Paint Group`
("Strokes") holds one triplet per stroke: a [`tdmn`](#tdmn) `ADBE Paint Atom`,
a [`pnta`](#pnta), then the stroke's [`LIST:tdgp`](#listtdgp) ("Brush 1",
"Eraser 2", ...) with `ADBE Paint Duration`, `ADBE Paint Shape` (a
[`LIST:om-s`](#listom-s) whose path is the stroke), the `ADBE Paint
Properties` group (colour, diameter, hardness, clone source, ...) and the
`ADBE Paint Transform` group.

| Child | Occurs | Description |
|---|---|---|
| [`tmds`](#tmds) | 1 | Time of each path vertex. |
| [`tpsp`](#tpsp) | 1 | Unknown two-record channel. |
| [`dmtr`](#dmtr) | 1 | Diameter channel. |
| [`opct`](#opct) | 1 | Opacity channel. |
| [`flow`](#flow) | 1 | Flow channel. |
| [`angl`](#angl) | 1 | Angle channel. |
| [`rndn`](#rndn) | 1 | Roundness channel. |

The order above is the same in all 1,765 strokes of the two production
samples that contain paint. No sample has ExtendScript ground truth for these
values; the meanings below are inferred from the tags and the values.

### `tmds`

When each vertex of the stroke was drawn.

**Parent:** [`LIST:pnts`](#listpnts) · **Size:** 16 x vertex count

| Offset | Length | Type | Description |
|---|---|---|---|
| 16 x *i* | 8 | f8 | Time of vertex *i* in seconds from the start of the stroke (inferred; 0.0 for the first vertex, increasing). |
| 16 x *i* + 8 | 8 | f8 | Vertex index *i* (0.0, 1.0, 2.0, ...). |

The last time is the stroke length that the other channels use as their end
position.

### `tpsp`

**Parent:** [`LIST:pnts`](#listpnts) · **Size:** 9 x record count

| Offset | Length | Type | Description |
|---|---|---|---|
| 9 x *i* | 8 | f8 | Position on the stroke's time axis (same axis as [`tmds`](#tmds)). |
| 9 x *i* + 8 | 1 | u1 | Unknown. |

Every sample has exactly two records: (0.0, 0) and (end of stroke, 1).

### `dmtr`

Diameter channel of the stroke's brush dynamics.

**Parent:** [`LIST:pnts`](#listpnts) · **Size:** 12 x record count

| Offset | Length | Type | Description |
|---|---|---|---|
| 12 x *i* | 8 | f8 | Position on the stroke's time axis (same axis as [`tmds`](#tmds)). |
| 12 x *i* + 8 | 4 | f4 | Value at that position (inferred: a multiplier of the brush setting, 1.0 = unchanged). |

The samples hold two records, at 0.0 and at the end of the stroke, both 1.0.
[`opct`](#opct), [`flow`](#flow), [`angl`](#angl) and [`rndn`](#rndn) use the
same record layout.

### `opct`

Opacity channel of the stroke's brush dynamics; records as in [`dmtr`](#dmtr).
Two records of 1.0 in every sample.

**Parent:** [`LIST:pnts`](#listpnts) · **Size:** 12 x record count

### `flow`

Flow channel of the stroke's brush dynamics; records as in [`dmtr`](#dmtr).
Two records of 1.0 in every sample.

**Parent:** [`LIST:pnts`](#listpnts) · **Size:** 12 x record count

### `angl`

Angle channel of the stroke's brush dynamics; records as in [`dmtr`](#dmtr).
Two to four records in the samples, values 0.0 or 1.0.

**Parent:** [`LIST:pnts`](#listpnts) · **Size:** 12 x record count

### `rndn`

Roundness channel of the stroke's brush dynamics; records as in
[`dmtr`](#dmtr). Two records of 1.0 in every sample.

**Parent:** [`LIST:pnts`](#listpnts) · **Size:** 12 x record count

### `pnta`

Paint stroke type.

**Parent:** [`LIST:tdgp`](#listtdgp) of the `ADBE Paint Group`, between the [`tdmn`](#tdmn) `ADBE Paint Atom` and the stroke's [`LIST:tdgp`](#listtdgp) · **Size:** 4 bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Stroke type: 0 = Brush, 1 = Eraser, 2 = Clone (the stroke names in the samples are "Brush N", "Eraser N" and "Clone N" respectively). |

Required in a paint stroke triplet.

### `LIST:mrst`

The `ADBE Marker` property: the markers of a layer, or of a composition.

**Parent:** [`LIST:tdgp`](#listtdgp) of a layer, right after the [`tdmn`](#tdmn) `ADBE Marker`

Composition markers are stored on the composition's hidden
[`LIST:SecL`](#listsecl) layer, in that layer's `ADBE Marker` property; their
times are composition times (not relative to that layer's start).

| Child | Occurs | Description |
|---|---|---|
| [`LIST:tdbs`](#listtdbs) | 1, required | The marker stream. Each marker is one keyframe of its [`LIST:list`](#listlist) (16-byte items); the keyframe time is the marker time. |
| [`LIST:mrky`](#listmrky) | 1, required | One [`LIST:Nmrd`](#listnmrd) per marker. |

A layer whose last marker was removed keeps its `LIST:mrst`, with a
[`cdat`](#cdat) in place of the keyframe list and an empty `LIST:mrky`. A
layer that never had a marker has no `ADBE Marker` property at all; adding
one means inserting the `tdmn` and `LIST:mrst` at the property's place in
the layer's group (see [`LIST:tdgp`](#listtdgp)).

### `LIST:mrky`

Marker values.

**Parent:** [`LIST:mrst`](#listmrst)

| Child | Occurs | Description |
|---|---|---|
| [`LIST:Nmrd`](#listnmrd) | one per marker | In the same order as the keyframes of the marker stream (1,871 of 1,871 samples match). |

### `LIST:Nmrd`

One marker (`MarkerValue`).

**Parent:** [`LIST:mrky`](#listmrky)

| Child | Occurs | Description |
|---|---|---|
| [`NmHd`](#nmhd) | 1, required, first | Flags, duration, label, parameter count. |
| [`Utf8`](#utf8) | 1 | Comment (`MarkerValue.comment`). |
| [`Utf8`](#utf8) | 1 | Chapter (`chapter`). |
| [`Utf8`](#utf8) | 1 | URL (`url`). |
| [`Utf8`](#utf8) | 1 | Frame target (`frameTarget`). |
| [`Utf8`](#utf8) | 1 | Cue-point name (`cuePointName`). |
| [`Utf8`](#utf8) | 2 x N | Cue-point parameters (the marker's parameter list in ExtendScript): key, value, key, value, ... N = [`NmHd`](#nmhd) 0x04. |

The five text fields are always present, empty when unused.

### `NmHd`

Marker header.

**Parent:** [`LIST:Nmrd`](#listnmrd) · **Size:** 20 bytes · **py_aep:** `NmhdChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Flags (below). Bits 3-31 are 0 in every sample. |
| 0x04 | 4 | u4 | Number of cue-point parameters N (key/value pairs). Must equal the number of `Utf8` pairs after the cue-point name, or AE ignores the parameters. |
| 0x08 | 4 | u4 | Duration dividend. Duration in seconds (`MarkerValue.duration`) = dividend / divisor. |
| 0x0C | 4 | u4 | Duration divisor. 600 on most markers (a 5 s marker stores 3000 / 600); 24, 25 and 24576 also occur. AE 2026 opens 36 / 24 as 1.5 s and 1500 / 0 as 2.5 s (0 reads as 600). When a script creates a marker or sets its duration, AE 2026 writes `round(seconds x 600)` / 600 whatever the composition frame rate (24, 25 and 29.97 fps measured); other edits keep the stored pair. |
| 0x10 | 4 | u4 LE | Label colour index (`MarkerValue.label`): 0 = None, 1-16. |

Flags at 0x00 (u4):

| Bit | Mask | Meaning |
|---|---|---|
| 0 | 0x01 | Navigation marker, `eventCuePoint` false (the AE SDK's `AEGP_MarkerFlag_NAVIGATION`; never set in the samples, all of whose markers report `eventCuePoint` true). |
| 1 | 0x02 | Protected region (`MarkerValue.protectedRegion`; the SDK's `AEGP_MarkerFlag_PROTECT_REGION`). |
| 2 | 0x04 | Unknown, not an SDK flag. Set on every marker AE 2022-2026 saves, clear on every CC 2018 marker. AE 2026 keeps a stored 0 or 1 when it resaves, and ExtendScript reports the same marker attributes either way. |

### `LIST:EfdG`

Project-level effect definitions: one entry per effect type used in the
project.

**Parent:** RIFX root (after `LIST:Pefl`, see the root order in the overview)

| Child | Occurs | Description |
|---|---|---|
| [`EfDC`](#efdc) | 1, required, first | Number of definitions. |
| [`LIST:EfDf`](#listefdf) | `EfDC` | One effect definition. |

Written by AE 2022 and later; AE 2018 projects have none. In every sample
from AE 2022 on that uses effects (139 files), the definitions are exactly the
effect match names used on layers, no more and no fewer.

#### Writing effects

- AE does not need the table to open a project. Measured on AE 2026:
  projects whose effect instances have no matching definition (and AE 2018
  projects with no `LIST:EfdG` at all) open normally, and AE writes the
  missing definitions on its next save. A writer may therefore leave the
  table unchanged when it adds an effect.
- The [`LIST:sspc`](#listsspc) of a definition is a byte-for-byte copy of the
  first instance of that effect in the project, values included: a project
  with two Gaussian Blur instances at Blurriness 20 and 30 has a definition
  holding 20, not the effect's default.
- A definition (or any existing instance) is thus a complete template for
  adding another instance of an installed effect whose parameters a writer
  cannot describe from scratch. Clone its `LIST:sspc`, then: set the
  [`tdpi`](#tdpi) of the `-0000` parameter to the id of the new owning
  layer; rewrite every non-zero time base in the clone's [`tdb4`](#tdb4)
  chunks to the target composition's; set the instance name in the value
  group's [`tdsn`](#tdsn) (the default-name placeholder for the first
  instance on a layer, "Name 2", "Name 3", ... for later ones); remove
  keyframes and expressions (an expression needs both its text and the
  stream's has-expression flag removed, see [`tdb4`](#tdb4)); and set each
  value back to its [`pard`](#pard) default. AE 2026 opens and re-saves
  instances built this way.

### `EfDC`

Number of effect definitions.

**Parent:** [`LIST:EfdG`](#listefdg) · **Size:** 4 bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 LE | Number of [`LIST:EfDf`](#listefdf) children (139 of 139 samples match). Little-endian. |

### `LIST:EfDf`

One effect definition.

**Parent:** [`LIST:EfdG`](#listefdg)

| Child | Occurs | Description |
|---|---|---|
| [`tdmn`](#tdmn) | 1, required | Effect match name (`ADBE Gaussian Blur 2`). |
| [`engv`](#engv) | 0-1 | Puppet effect only. |
| [`Utf8`](#utf8) | 0-1 | Unknown. One sample (`ADBE Samurai`) holds a comma-separated list of numbers here. |
| [`LIST:sspc`](#listsspc) | 1, required | The definition: a copy of the first instance (see [Writing effects](#writing-effects)). |

### `LIST:sspc`

One effect instance (list type `sspc`; not the footage [`sspc`](#sspc)
chunk). The same list is the body of an effect definition.

**Parent:** [`LIST:tdgp`](#listtdgp) of the layer's `ADBE Effect Parade` group, right after the effect's [`tdmn`](#tdmn) (and [`engv`](#engv) when present); [`LIST:EfDf`](#listefdf)

| Child | Occurs | Description |
|---|---|---|
| [`fnam`](#fnam) | 1 | Effect display name (a [`Utf8`](#utf8) inside), e.g. "Gaussian Blur". |
| [`LIST:parT`](#listpart) | 1 | Parameter definitions; empty except on the first instance of each effect type in the file. |
| [`LIST:tdgp`](#listtdgp) | 1 | Parameter values (below). |
| [`sdat`](#sdat) | 0-1 | The effect's sequence data. |
| [`pgui`](#pgui) | 1 | GUID. |
| [`elab`](#elab) | 0-1 | One byte, 0xFF. Only in samples saved with file version 97.7 (a later AE 26 build); meaning unknown. |

Children appear in the order listed. Write the `LIST:parT` even when it is
empty.

#### Parameter values

The instance's [`LIST:tdgp`](#listtdgp) holds: [`tdsb`](#tdsb); [`tdsn`](#tdsn)
(the instance name: the default-name placeholder on the first instance of an
effect on a layer, the real name, e.g. "Gaussian Blur 2", on later ones); then
a [`tdmn`](#tdmn) + body pair for each parameter AE stores, in parameter
order; `ADBE Effect Built In Params` with its group ("Compositing Options");
and `ADBE Group End`.

- Parameter match names are those of the [`LIST:parT`](#listpart):
  `<effect match name>-NNNN` (`ADBE Gaussian Blur 2-0001`) or a name of its
  own (`ADBE Force CPU GPU`).
- A parameter's body is a [`LIST:tdbs`](#listtdbs); a group-start parameter
  has a [`LIST:tdgp`](#listtdgp); an arbitrary-data parameter has its
  `LIST:tdbs` followed by a [`LIST:aRbs`](#listarbs).
- The `-0000` parameter (the effect's input layer) is always written; its
  [`tdpi`](#tdpi) is the id of the layer that owns the effect, and AE rewrites
  it when it duplicates the layer. A Layer-type parameter's `tdpi` is the id
  of the layer it references and is kept on duplicate.
- Parameters at their default value are usually omitted. Of 324 built-in
  effects freshly applied in AE, 218 store only `-0000` and the Compositing
  Options group; the others also store a few parameters at their defaults.
  AE 2026 also drops a parameter a script sets back to its default.
- An omitted parameter holds its [`pard`](#pard) default, not the cached
  value at 0x38: ExtendScript reports the popup default (0x3E) for 9,465 of
  9,468 omitted popups in the samples, among them 1,725 whose cached value
  differs (S_BlurDirectional's Edge Mode caches 1 and reports 3); the
  three others are OCIO transform popups whose ids the plug-in computes. An
  omitted point is its default percentage of the layer size (Path Text's
  80 % caches the 16.16 fraction 0.7999878 and reports exactly 80 on a
  100-pixel layer). `isModified` of a stored parameter compares against
  the same default.
- Effect point values are fractions of the layer size: x / width, y /
  height, and a 3D point's z / height (measured on AE 2026: [100, 50, 7] on a
  200 x 100 layer stores [0.5, 0.5, 0.07]).

Static flag byte for effect parameters: when a parameter value is written as
a static value (including one AE had omitted, or one whose keyframes were
removed), byte 0x05 of its [`tdb4`](#tdb4) must be the effect-parameter value
for its control type: 0x01 for one-dimensional controls, 0x07 for a colour,
0x0F for a 2D or 3D point. Bit 1 (0x02) marks the stream as holding an
instance value; without it AE ignores a static colour or point and shows the
default. Animated parameters use 0x06 (colour) and 0x0E (points); removing
the last keyframe of a colour in AE 2026 stores 0x07. These values differ
from the ones layer properties use (see [`tdb4`](#tdb4)).

### `LIST:parT`

Parameter definitions of an effect.

**Parent:** [`LIST:sspc`](#listsspc)

| Child | Occurs | Description |
|---|---|---|
| [`parn`](#parn) | 1, first (absent when the list is empty) | Number of parameters. |
| [`tdmn`](#tdmn) | 1 per parameter | Parameter match name. |
| [`pard`](#pard) | 1 per parameter, after its `tdmn` | Parameter definition. |
| [`pdnm`](#pdnm) | after the `pard` of a popup, checkbox or button | Popup: the choices, separated by `\|` ("Horizontal and Vertical\|Horizontal\|Vertical"). Checkbox: the label shown beside the box (may be empty). Button: the button label. |
| [`aRbp`](#arbp) | after the `pard` of most arbitrary-data parameters | The parameter's default value. |

- In all 2,325 non-empty sample lists, the first parameter is the effect's
  input layer `<effect>-0000` (control type 0, Layer) and the last is
  `ADBE Effect Built In Params` (control type 9, no data), which stands for
  the Compositing Options group. The numbers in `-NNNN` names follow the
  plug-in's parameter ids, not the order in the list.
- Only the first instance of each effect type in the file carries the
  definitions (1,283 of 1,283 sample effect types); later instances, on any
  layer, have an empty `LIST:parT`. The copy in [`LIST:EfDf`](#listefdf) is
  full.
- The list is a cache of what the installed plug-in declares: AE 2022
  re-saving an AE 2018 project dropped a parameter that the old list still
  had. Writing a full list on every instance is accepted.
- The Dropdown Menu Control is a pseudo effect whose match name is
  `Pseudo/@@` followed by 22 base64 characters (a random 16-byte id per
  instance); its item list exists only in this list's `pdnm`.

### `parn`

Number of parameters in a [`LIST:parT`](#listpart).

**Parent:** [`LIST:parT`](#listpart) · **Size:** 4 bytes · **py_aep:** `S4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Number of [`tdmn`](#tdmn) + [`pard`](#pard) pairs (2,325 of 2,325 samples match). |

### `pard`

One effect parameter definition: the SDK `PF_ParamDef` record, big-endian.

**Parent:** [`LIST:parT`](#listpart), after the parameter's [`tdmn`](#tdmn) · **Size:** 148 bytes · **py_aep:** `PardChunk`

A 56-byte header common to all parameters, then a 92-byte body whose layout
depends on the control type (the SDK `PF_ParamDefUnion`).

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | 0 in every sample (the SDK's `id` / change flags). |
| 0x04 | 4 | u4 | UI flags (`PF_ParamUIFlags`, below). |
| 0x08 | 2 | u2 | Custom UI width (`ui_width`); 0 unless the plug-in draws its own control. |
| 0x0A | 2 | u2 | Custom UI height (`ui_height`). |
| 0x0C | 4 | u4 | Control type (`PF_ParamType`, below); bytes 0x0C-0x0E are 0 in every sample. |
| 0x10 | 32 | char[32] | Parameter name, NUL-terminated. Usually UTF-8; a few built-in effects store a Windows code-page apostrophe (0x92). Bytes after the terminator are not always zero. |
| 0x30 | 4 | u4 | Parameter flags (`PF_ParamFlags`, below). |
| 0x34 | 4 | u4 | 0 in every sample (the SDK's `unused`). |
| 0x38 | 92 | bytes | Control-type body (below). |

UI flags at 0x04 (bits seen in the samples):

| Bit | Mask | Meaning |
|---|---|---|
| 0 | 0x001 | `PF_PUI_TOPIC`: custom UI on the parameter's title. |
| 1 | 0x002 | `PF_PUI_CONTROL`: custom UI control (uses `ui_width` / `ui_height`). |
| 2 | 0x004 | `PF_PUI_STD_CONTROL_ONLY`: UI only, no data. |
| 3 | 0x008 | `PF_PUI_NO_ECW_UI`: not shown in the Effect Controls panel. |
| 4 | 0x010 | `PF_PUI_ECW_SEPARATOR`. |
| 5 | 0x020 | `PF_PUI_DISABLED`: greyed out. |
| 7 | 0x080 | `PF_PUI_DONT_ERASE_CONTROL`. |
| 9 | 0x200 | `PF_PUI_INVISIBLE`: hidden from the Effect Controls panel and the Timeline. ExtendScript `canSetExpression` is false for every such parameter in the samples (419 of 419). |

Parameter flags at 0x30 (bits seen in the samples):

| Bit | Mask | Meaning |
|---|---|---|
| 1 | 0x002 | `PF_ParamFlag_CANNOT_TIME_VARY`: ExtendScript `canVaryOverTime` is false (21,569 of 21,570 sample parameters agree; the exception is `ADBE FreePin3 Puppet Engine`). |
| 2 | 0x004 | `PF_ParamFlag_CANNOT_INTERP`: hold keyframes only. |
| 5 | 0x020 | `PF_ParamFlag_COLLAPSE_TWIRLY` (`START_COLLAPSED`). |
| 6 | 0x040 | `PF_ParamFlag_SUPERVISE`: the plug-in is told when the value changes. |
| 7 | 0x080 | `PF_ParamFlag_USE_VALUE_FOR_OLD_PROJECTS`. |
| 8 | 0x100 | `PF_ParamFlag_EXCLUDE_FROM_HAVE_INPUTS_CHANGED`. |
| 9 | 0x200 | `PF_ParamFlag_SKIP_REVEAL_WHEN_UNHIDDEN`. |

Control types at 0x0C (`PF_ParamType`) and their counts in the samples:

| Value | SDK name | Body | Samples |
|---|---|---|---|
| 0 | `PF_Param_LAYER` | [Layer](#layer-type-0) | 3,716 |
| 1 | `PF_Param_SLIDER` (integer, obsolete) | [Integer slider](#integer-slider-type-1) | 585 |
| 2 | `PF_Param_FIX_SLIDER` | [Fixed slider](#fixed-slider-type-2) | 25,674 |
| 3 | `PF_Param_ANGLE` | [Angle](#angle-type-3) | 1,234 |
| 4 | `PF_Param_CHECKBOX` | [Checkbox](#checkbox-type-4) | 6,083 |
| 5 | `PF_Param_COLOR` | [Colour](#colour-type-5) | 2,145 |
| 6 | `PF_Param_POINT` | [Point](#point-type-6) | 1,550 |
| 7 | `PF_Param_POPUP` | [Popup](#popup-type-7) | 7,023 |
| 9 | `PF_Param_NO_DATA` | none | 2,420 |
| 10 | `PF_Param_FLOAT_SLIDER` | [Float slider](#float-slider-type-10) | 6,914 |
| 11 | `PF_Param_ARBITRARY_DATA` | [Arbitrary data](#arbitrary-data-type-11) | 1,104 |
| 12 | `PF_Param_PATH` | [Path](#path-type-12) | 1,220 |
| 13 | `PF_Param_GROUP_START` | none | 4,192 |
| 14 | `PF_Param_GROUP_END` | none | 4,192 |
| 15 | `PF_Param_BUTTON` | [Button](#button-type-15) | 2,841 |
| 18 | `PF_Param_POINT_3D` | [3D point](#3d-point-type-18) | 312 |

Types 9, 13 and 14 have no body (all zeros in the samples). In every type,
the body bytes after the fields listed below are not part of the definition:
depending on the type, from a few percent to half of the sample records hold
leftover data there (repeating 8-byte patterns, fragments of other
parameters' match names), the others zeros. The same goes for the text
fields of the slider bodies, which hold no text in any sample.

The "value" fields are the parameter value when the definition was cached,
not the instance value, which lives in the instance's
[parameter values](#parameter-values). The bounds are what ExtendScript
reports as `minValue` / `maxValue` (21,567 of 21,569 sample parameters
agree).

#### Layer (type 0)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x80 | 4 | s4 | Default layer (`PF_LayerDefault`): -1 = the layer the effect is on, 0 = none. The `-0000` input parameter is -1. |

#### Integer slider (type 1)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x38 | 4 | s4 | Value. |
| 0x3C | 32 | char[32] | Value text (`value_str`); no text in the samples (zeros or leftovers). |
| 0x5C | 32 | char[32] | Value description (`value_desc`); no text in the samples. |
| 0x7C | 4 | s4 | Valid minimum. |
| 0x80 | 4 | s4 | Valid maximum. |
| 0x84 | 4 | s4 | Slider minimum (UI range). |
| 0x88 | 4 | s4 | Slider maximum. |
| 0x8C | 4 | s4 | Default. |

#### Fixed slider (type 2)

All values are `fixed 16.16` (value / 65536).

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x38 | 4 | fixed 16.16 | Value. |
| 0x3C | 32 | char[32] | Value text; no text in the samples. |
| 0x5C | 32 | char[32] | Value description; no text in the samples. |
| 0x7C | 4 | fixed 16.16 | Valid minimum. |
| 0x80 | 4 | fixed 16.16 | Valid maximum. |
| 0x84 | 4 | fixed 16.16 | Slider minimum. |
| 0x88 | 4 | fixed 16.16 | Slider maximum. |
| 0x8C | 4 | fixed 16.16 | Default. |
| 0x90 | 2 | s2 | Decimal places shown (`precision`). |
| 0x92 | 2 | u2 | Display flags (`PF_ValueDisplayFlags`). 0 on most sample parameters even where the UI shows percent or pixels; AE takes these flags from the plug-in when it loads the project. |

#### Angle (type 3)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x38 | 4 | fixed 16.16 | Value, degrees (not limited to 0-360). |
| 0x3C | 4 | fixed 16.16 | Default, degrees. |
| 0x40 | 4 | fixed 16.16 | Valid minimum (the SDK says effects do not support it; 0 in nearly every sample). |
| 0x44 | 4 | fixed 16.16 | Valid maximum. |

#### Checkbox (type 4)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x38 | 4 | s4 | Value: 0 or 1. |
| 0x3C | 1 | u1 | Default: 0 or 1. |
| 0x3D | 3 | bytes | Reserved, 0. |

The label shown beside the box is the [`pdnm`](#pdnm) that follows.

#### Colour (type 5)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x38 | 4 | u1[4] | Value: alpha, red, green, blue (0-255). |
| 0x3C | 4 | u1[4] | Default: alpha, red, green, blue. |

#### Point (type 6)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x38 | 4 | fixed 16.16 | X value. |
| 0x3C | 4 | fixed 16.16 | Y value. |
| 0x40 | 3 | bytes | Reserved, 0. |
| 0x43 | 1 | u1 | Restrict to the layer bounds (`restrict_bounds`). |
| 0x44 | 4 | fixed 16.16 | X default, percent of the layer width (50.0 = centre). |
| 0x48 | 4 | fixed 16.16 | Y default, percent of the layer height. |

The value comes in two forms in AE-written files: equal to the default (in
percent, as the plug-in declared it), or as a fraction of the layer size (0.5
= centre).

#### Popup (type 7)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x38 | 4 | s4 | Value, 1-based choice. |
| 0x3C | 2 | s2 | Number of choices. |
| 0x3E | 2 | s2 | Default, 1-based choice. |

The choices are the [`pdnm`](#pdnm) that follows, separated by `|`.

#### Float slider (type 10)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x38 | 8 | f8 | Value. |
| 0x40 | 8 | f8 | Phase (audio effects only). |
| 0x48 | 32 | char[32] | Value description; no text in the samples. |
| 0x68 | 4 | f4 | Valid minimum; a non-finite value means no lower bound. |
| 0x6C | 4 | f4 | Valid maximum; non-finite means no upper bound. |
| 0x70 | 4 | f4 | Slider minimum (UI range). |
| 0x74 | 4 | f4 | Slider maximum. |
| 0x78 | 4 | f4 | Default. |
| 0x7C | 2 | s2 | Decimal places shown (`precision`). |
| 0x7E | 2 | u2 | Display flags (`PF_ValueDisplayFlags`): bit 0 (`PERCENT`) is set on every float slider ExtendScript reports in percent (207 of 207) and on no other. |
| 0x80 | 4 | u4 | Float slider flags (`PF_FSliderFlags`). |
| 0x84 | 4 | f4 | Curve tolerance (0.05, 0.1 or 0 in the samples). |
| 0x88 | 1 | u1 | Use exponent display (`useExponent`). |
| 0x89 | 3 | bytes | Padding. |
| 0x8C | 4 | f4 | Exponent. |

#### Arbitrary data (type 11)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x38 | 4 | bytes | Plug-in defined (the SDK's arbitrary-data `id` and padding). |

The default value is the [`aRbp`](#arbp) that follows in the
[`LIST:parT`](#listpart) (1,092 of 1,104 sample parameters have one).

#### Path (type 12)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x38 | 4 | u4 | Path id (0 or 1 in the samples). |
| 0x3C | 4 | u4 | Reserved, 0. |
| 0x40 | 4 | s4 | Default mask: 0 = none, otherwise the 1-based mask index. |

#### Button (type 15)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x38 | 4 | bytes | Unknown (the SDK says the value is unused); varies between buttons. |

The button label is the [`pdnm`](#pdnm) that follows.

#### 3D point (type 18)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x38 | 8 | f8 | X value. |
| 0x40 | 8 | f8 | Y value. |
| 0x48 | 8 | f8 | Z value. |
| 0x50 | 8 | f8 | X default, percent of the layer width. |
| 0x58 | 8 | f8 | Y default, percent of the layer height. |
| 0x60 | 8 | f8 | Z default, percent of the layer height. |
| 0x68 | 16 | bytes | Reserved, 0. |

As with the 2D point, the value is either equal to the default (percent) or a
fraction of the layer size.

### `sdat`

An effect's sequence data: state the plug-in keeps for an effect instance,
flattened by the plug-in when the project is saved.

**Parent:** [`LIST:sspc`](#listsspc), after the value [`LIST:tdgp`](#listtdgp) · **Size:** variable (4 to 9,248 bytes in the samples)

The payload belongs to the plug-in, which writes it when the project is saved and reads it back when the project is opened. Many
plug-ins write it in their own machine byte order (little-endian on current
platforms). Two first-party layouts seen in the samples:

| Effect | Size | Content |
|---|---|---|
| Curves (`ADBE CurvesCustom`) | 20 | Little-endian: the four bytes `VRUC` (`CURV` stored reversed), u4 1, u4 selected channel (inferred), 8 zero bytes. |
| Levels (`ADBE Easy Levels2`) | 8,208 | Little-endian: `KLIW` (`WILK` stored reversed), a histogram cache of 2,048 u4 values and a display preference. A cache, not settings. |

### `LIST:aRbs`

Values of an arbitrary-data effect parameter.

**Parent:** the instance's [`LIST:tdgp`](#listtdgp), right after the parameter's [`LIST:tdbs`](#listtdbs)

| Child | Occurs | Description |
|---|---|---|
| [`aRbp`](#arbp) | 1 (static) or one per keyframe | The value(s), in keyframe order (5,058 of 5,070 samples). |

Empty in 12 samples (3D Camera Tracker, Warp Stabilizer and Mocha instances).

### `aRbp`

One arbitrary-data value (curves, colour ranges, histograms, plug-in state).

**Parent:** [`LIST:aRbs`](#listarbs) (instance value); [`LIST:parT`](#listpart) (default value, after the parameter's [`pard`](#pard)) · **Size:** variable (1 byte to 7 MB in the samples; at most 2,580 bytes for first-party effects, Mesh Warp)

The payload belongs to the plug-in that declared the parameter; third-party
payloads are opaque (some are text, some native little-endian structures).
The first-party layouts decoded from the samples are below.

#### Hue/Saturation

`ADBE HUE SATURATION-0003` (Channel Range): 180 bytes, 45 big-endian s4.

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | s4 | Master hue, degrees. |
| 0x04 | 4 | s4 | Master saturation. |
| 0x08 | 4 | s4 | Master lightness. |
| 0x0C | 168 | s4[42] | Six ranges (Reds, Yellows, Greens, Cyans, Blues, Magentas), 28 bytes each: four hue-window points in degrees (Reds 315, 345, 15, 45 in the samples, each later range 60 degrees further), then hue, saturation, lightness. |

#### Levels

`ADBE Easy Levels2-0002` (Histogram): 108 bytes.

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | 0x000F10A7 in every sample (inferred: a version). |
| 0x04 | 4 | u4 | 1 in every sample. |
| 0x08 | 100 | f4[25] | Five channels (RGB, Red, Green, Blue, Alpha), 20 bytes each: input black, input white, gamma, output black, output white, normalized to 0-1. |

#### Curves

`ADBE CurvesCustom-0001` (Curves): 1,644 bytes.

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x000 | 2 | u2 | 1 in every sample (inferred: a version). |
| 0x002 | 2 | u2 | 1 in every sample. |
| 0x004 | 1280 | `u1[5][256]` | Lookup tables for RGB, Red, Green, Blue, Alpha (256 bytes each; identity = 0, 1, 2, ..., 255). |
| 0x504 | 360 | records | Five curve records, 72 bytes each, same channel order (below). |

Curve record:

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 64 | `u2[16][2]` | Up to 16 control points as (input, output) pairs, 0-255; unused points are zero. |
| 0x40 | 4 | u4 | Number of control points used. |
| 0x44 | 4 | u4 | Unknown: 1 or 0xFFFFFFFF in the samples. |

### `pgui`

A 16-byte GUID.

**Parent:** [`LIST:sspc`](#listsspc) (effects); [`LIST:Pin`](#listpin) (footage sources); [`LIST:btgu`](#listbtgu) (text) · **Size:** 16 bytes · **py_aep:** `PguiChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 16 | bytes | GUID, raw bytes. |

On effect instances and definitions the GUID is all zeros in 11,009 of 11,030
samples; the remaining ones carry a random (version 4) GUID, on a few effect
types (`ADBE Path Text`, `ADBE Numbers2`, `ADBE Basic Text2`,
`ADBE Apply Color LUT2`, the OCIO transforms, Particular). The Dropdown Menu
Control writes zeros. Footage sources carry a random version-4 GUID in every
sample; text uses both forms. Meaning beyond identity unknown.

### `engv`

**Parent:** [`LIST:tdgp`](#listtdgp) of a layer's `ADBE Effect Parade`, between the effect's [`tdmn`](#tdmn) and its [`LIST:sspc`](#listsspc); [`LIST:EfDf`](#listefdf), at the same place · **Size:** 4 bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Unknown: 2 in 8 of 9 samples, 1 in one. |

Seen only before Puppet effect (`ADBE FreePin3`) instances and their
definitions. Optional.

### `LIST:GCst`

A gradient property: `ADBE Vector Grad Colors` (shape-layer gradient fill and
stroke) and the layer-style gradients (`gradientFill/gradient`,
`innerGlow/gradient`, `outerGlow/gradient`).

**Parent:** [`LIST:tdgp`](#listtdgp), right after the property's [`tdmn`](#tdmn)

| Child | Occurs | Description |
|---|---|---|
| [`LIST:tdbs`](#listtdbs) | 1, required | The gradient stream. Static: an empty 4-byte [`cdat`](#cdat), which AE requires ("missing data in file" without it). Animated: a [`LIST:list`](#listlist) of keyframes. |
| [`LIST:GCky`](#listgcky) | 1 | The gradient values. |

A gradient never edited has no `tdmn` and no `LIST:GCst` (AE shows its
default gradient). When the last keyframe of a gradient is removed, AE 2026
deletes the `tdmn` and `LIST:GCst` and the gradient reverts to its default;
a static edited gradient (as found in the samples) keeps its value.

### `LIST:GCky`

Gradient values.

**Parent:** [`LIST:GCst`](#listgcst)

| Child | Occurs | Description |
|---|---|---|
| [`Utf8`](#utf8) | 1 (static) or one per keyframe | One gradient as XML text (below), in keyframe order. |

#### Gradient XML

An XML property map, `\n` line endings, ending with a newline:

```xml
<?xml version='1.0'?>
<prop.map version='4'>
<prop.list>
<prop.pair>
<key>Gradient Color Data</key>
<prop.list>
<prop.pair>
<key>Alpha Stops</key>
<prop.list>
<prop.pair>
<key>Stops List</key>
<prop.list>
<prop.pair>
<key>Stop-0</key>
<prop.list>
<prop.pair>
<key>Stops Alpha</key>
<array>
<array.type><float/></array.type>
<float>0</float>      <!-- location, 0-1 -->
<float>0.5</float>    <!-- midpoint to the next stop, 0-1 -->
<float>1</float>      <!-- alpha -->
</array>
</prop.pair>
</prop.list>
</prop.pair>
<!-- Stop-1, Stop-2, ... -->
</prop.list>
</prop.pair>
<prop.pair>
<key>Stops Size</key>
<int type='unsigned' size='32'>2</int>
</prop.pair>
</prop.list>
</prop.pair>
<prop.pair>
<key>Color Stops</key>
<!-- same structure; each "Stops Color" array holds
     location, midpoint, red, green, blue (0-1), then 1 -->
</prop.pair>
</prop.list>
</prop.pair>
<prop.pair>
<key>Gradient Colors</key>
<string>1.0</string>
</prop.pair>
</prop.list>
</prop.map>
```

(The comments are explanatory; AE writes none.) Stops are keyed
`Stop-0` ... `Stop-N`, listed in lexicographic order of the key (`Stop-0,
Stop-1, Stop-10, Stop-11, ..., Stop-2, ...`), which only matters past ten
stops. Values are single-precision floats printed with up to eight significant digits (`0`, `0.5`, `0.81176472`; 0.83 prints as `0.82999998`).

### `blsv`

**Parent:** [`LIST:tdgp`](#listtdgp) of the layer's `ADBE Source Options Group`, after the [`tdmn`](#tdmn) `ADBE Layer Source Alternate` · **Size:** 4 bytes · **py_aep:** `U4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | 1 in every sample (inferred: a version). |

The `ADBE Layer Source Alternate` property is stored as its `tdmn`, then
`blsv`, [`blsi`](#blsi) and the property's [`LIST:tdbs`](#listtdbs). Both
chunks are required there. AE writes this property on every new AV layer:
AE 2023 and later with its `LIST:tdbs`, AE 2022 without it (the `tdmn`,
`blsv` and `blsi` only). AE 15 layers have no Source Options group.

### `blsi`

The layer's alternate source (Media Replacement).

**Parent:** [`LIST:tdgp`](#listtdgp) of the layer's `ADBE Source Options Group`, after [`blsv`](#blsv) · **Size:** 4 bytes · **py_aep:** `U4Chunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Item id of the alternate source (`Property.alternateSource`), 0 = none. One sample holds 30, the id ExtendScript reports for its alternate source. |

### `btov`

**Parent:** [`LIST:tdgp`](#listtdgp) holding an `ADBE EP Text Document` (an Essential Graphics text override), after its [`LIST:btds`](#listbtds) and [`LIST:btgu`](#listbtgu) · **Size:** 4 bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 LE | Unknown; 7 in both samples. Little-endian. |

Written only for file versions after 95.2 (AE 24 and later). Required where
it occurs.

### `fpov`

The Puppet effect (`ADBE FreePin3`) keeps its mesh and outline data in chunks
inside its parameter groups. The outlines are stored as a [`tdmn`](#tdmn)
`ADBE FreePin3 Outlines` followed by `fpov`, [`init`](#init),
[`olsz`](#olsz), [`fpol`](#fpol) and the property's
[`LIST:tdbs`](#listtdbs), inside the `ADBE FreePin3 ARAP Group` group. All
four chunks are required there.

**Parent:** [`LIST:tdgp`](#listtdgp) of the `ADBE FreePin3 ARAP Group` · **Size:** 4 bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | 3 in every sample (inferred: a version). |

### `init`

**Parent:** [`LIST:tdgp`](#listtdgp) of the `ADBE FreePin3 ARAP Group`, after [`fpov`](#fpov) · **Size:** 1 byte

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 1 | u1 | Unknown; 0 in every sample. |

### `olsz`

**Parent:** [`LIST:tdgp`](#listtdgp) of the `ADBE FreePin3 ARAP Group`, after [`init`](#init) · **Size:** 4 bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Size in bytes of the following [`fpol`](#fpol) (4 in every sample). |

### `fpol`

Puppet outline data.

**Parent:** [`LIST:tdgp`](#listtdgp) of the `ADBE FreePin3 ARAP Group`, after [`olsz`](#olsz) · **Size:** [`olsz`](#olsz) bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | `olsz` | bytes | Outline data, opaque. Four zero bytes in every sample. |

### `fpmv`

Each Puppet mesh is stored as a [`tdmn`](#tdmn) `ADBE FreePin3 Mesh` followed
by `fpmv`, [`fpsz`](#fpsz), [`fpms`](#fpms) and the property's
[`LIST:tdbs`](#listtdbs), inside an `ADBE FreePin3 Mesh Atom` group. All
three chunks are required there.

**Parent:** [`LIST:tdgp`](#listtdgp) of an `ADBE FreePin3 Mesh Atom` · **Size:** 4 bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | 6 in every sample (inferred: a version). |

### `fpsz`

**Parent:** [`LIST:tdgp`](#listtdgp) of an `ADBE FreePin3 Mesh Atom`, after [`fpmv`](#fpmv) · **Size:** 4 bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Size in bytes of the following [`fpms`](#fpms) (40 and 6,896 in the samples). |

### `fpms`

Puppet mesh data.

**Parent:** [`LIST:tdgp`](#listtdgp) of an `ADBE FreePin3 Mesh Atom`, after [`fpsz`](#fpsz) · **Size:** [`fpsz`](#fpsz) bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | `fpsz` | bytes | Mesh data, opaque (mixed integers and floats). |

### `menv`

The `ADBE FreePin3 Mesh Group` ends with `menv`, [`PEvr`](#pevr),
[`PEsz`](#pesz) and [`PEdt`](#pedt), after its last mesh chunk and before
`ADBE Group End`.

**Parent:** [`LIST:tdgp`](#listtdgp) of the `ADBE FreePin3 Mesh Group` · **Size:** 4 bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Unknown; 1 in every sample. Optional. |

### `PEvr`

**Parent:** [`LIST:tdgp`](#listtdgp) of the `ADBE FreePin3 Mesh Group`, after [`menv`](#menv) · **Size:** 4 bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | 1 or 2 in the samples (inferred: a version of [`PEdt`](#pedt)). Required. |

### `PEsz`

**Parent:** [`LIST:tdgp`](#listtdgp) of the `ADBE FreePin3 Mesh Group`, after [`PEvr`](#pevr) · **Size:** 4 bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Size in bytes of the following [`PEdt`](#pedt) (30 and 24,173 in the samples). Required. |

### `PEdt`

Opaque Puppet data.

**Parent:** [`LIST:tdgp`](#listtdgp) of the `ADBE FreePin3 Mesh Group`, after [`PEsz`](#pesz) · **Size:** [`PEsz`](#pesz) bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | 0x0AD0BEEF in every sample. |
| 0x04 | `PEsz` - 4 | bytes | Opaque; begins with a u4 matching [`PEvr`](#pevr) in the samples. |

Required.

### `tver`

Motion trackers (Tracker panel) live in the layer's `ADBE MTrackers` group.
Each tracker is a [`tdmn`](#tdmn) `ADBE MTracker` followed by `tver`,
[`mtif`](#mtif), [`mtpr`](#mtpr), [`tpds`](#tpds), [`mtpd`](#mtpd) and the
tracker's [`LIST:tdgp`](#listtdgp) (its track points). One sample (a
production project with one tracker) contains them; all five chunks are
required there.

**Parent:** [`LIST:tdgp`](#listtdgp) of the `ADBE MTrackers` group · **Size:** 4 bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | 3 in the sample (inferred: a version). |
| 0x02 | 2 | u2 | 0 in the sample. |

### `mtif`

Tracker information.

**Parent:** [`LIST:tdgp`](#listtdgp) of the `ADBE MTrackers` group, after [`tver`](#tver) · **Size:** 40 bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | 3 in the sample. |
| 0x04 | 4 | u4 | 0xFFFFFFFF in the sample. |
| 0x08 | 32 | char[32] | Match name of the tracking plug-in, NUL-terminated ASCII (`ADBE Motion Tracker`); the bytes after the terminator are leftovers. |

### `mtpr`

**Parent:** [`LIST:tdgp`](#listtdgp) of the `ADBE MTrackers` group, after [`mtif`](#mtif) · **Size:** 20 bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Unknown; 0x31F in the sample. |
| 0x04 | 4 | u4 | Unknown; 0. |
| 0x08 | 4 | u4 | Unknown; 0x80000000. |
| 0x0C | 4 | u4 | Unknown; 0xFFFFFFFF. |
| 0x10 | 1 | u1 | Unknown; 0. |
| 0x11 | 1 | u1 | Unknown; 0. |
| 0x12 | 2 | bytes | 0. |

### `tpds`

**Parent:** [`LIST:tdgp`](#listtdgp) of the `ADBE MTrackers` group, after [`mtpr`](#mtpr) · **Size:** 4 bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Size in bytes of the following [`mtpd`](#mtpd) (20 in the sample). |

### `mtpd`

Options of the tracking plug-in (inferred).

**Parent:** [`LIST:tdgp`](#listtdgp) of the `ADBE MTrackers` group, after [`tpds`](#tpds) · **Size:** [`tpds`](#tpds) bytes

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | `tpds` | bytes | Plug-in defined, opaque. |

### `mtov`

**Parent:** [`LIST:tdgp`](#listtdgp) of the `ADBE3D Para Mat Parade` group (parametric mesh layers), after a [`tdmn`](#tdmn) `ADBE3D Param Mat Atom` · **Size:** 8 bytes

Each parametric-mesh material is stored as the `tdmn`, `mtov`, a
[`Utf8`](#utf8) with the material name ("Material") and the material's
[`LIST:tdgp`](#listtdgp). One sample (6 materials) contains it. Required
there.

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 LE | Unknown; 0xFFFFFFFF in every sample. |
| 0x04 | 4 | u4 LE | Unknown; 0 in every sample. |

## Text

A text layer keeps its Source Text property (`ADBE Text Document`) as an
ordinary property stream wrapped in a [`LIST:btds`](#listbtds): the stream
carries the timing (one keyframe per text document), and every text
document - characters, styles, fonts, the text box and a cache of the laid
out lines - lives in one [`LIST:btdk`](#listbtdk) beside it, written in the
object syntax of PDF (COS). A [`LIST:btgu`](#listbtgu) follows the
`LIST:btds`. Inside the layer's `ADBE Text Properties` group
([`LIST:tdgp`](#listtdgp)) the order is:

    tdmn "ADBE Text Document", LIST:btds, LIST:btgu,
    tdmn "ADBE Text Path Options", LIST:tdgp,
    tdmn "ADBE Text More Options", LIST:tdgp,
    [tdmn "ADBE Text Animators", LIST:tdgp,]
    tdmn "ADBE Group End"

An Essential Graphics text property (`ADBE EP Text Document`) uses the same
`LIST:btds` + `LIST:btgu` pair, followed by a [`btov`](#btov).

The COS body is fragile: After Effects rejects a text layer whose `btdk`
is not formatted exactly as it writes it ("Error reading the text layer.
Skipping the text layer.", AE 2026), even when the content is equivalent.
A writer must reproduce the formatting rules below byte for byte; reading
and re-serializing all 353 `btdk` bodies of the sample corpus with these
rules gives identical bytes.

### `LIST:btds`

The Source Text property: a property stream plus the text documents it
animates.

**Parent:** [`LIST:tdgp`](#listtdgp)

| Child | Occurs | Description |
|---|---|---|
| [`LIST:tdbs`](#listtdbs) | 1, required | The stream: [`tdsb`](#tdsb), [`tdsn`](#tdsn) (`-_0_/-`), [`tdb4`](#tdb4), then either [`cdat`](#cdat) (a static value) or a [`LIST:list`](#listlist) (keyframes), and an optional [`Utf8`](#utf8) expression. |
| [`LIST:btdk`](#listbtdk) | 1, required | The text documents. |

The order is `LIST:tdbs`, `LIST:btdk` in every sample.

**Static text.** The `cdat` is 4 bytes, 0 in every sample (341 static
streams); the value is document 0 of the `btdk` and the document array
holds exactly one document.

**Animated text.** The keyframe list has one 16-byte item per keyframe
([`lhd3`](#lhd3) item size 16, item type byte 4). Keyframe *i* takes its
value from document *i* of the `btdk` document array (`/1/1`), so the
keyframe count and the document count are always equal (2 and 2, 1 and 1
in the samples). Adding or removing a keyframe means inserting or removing
a document at the same index.

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | s4 | Keyframe time in the layer's time base (see [`ldat`](#ldat)). |
| 0x04 | 1 | u1 | In interpolation: 3 (hold) in every sample. |
| 0x05 | 1 | u1 | Out interpolation: 3 (hold) in every sample. |
| 0x06 | 2 | u2 | Key flags, as in other keyframe items (0 in the samples). |
| 0x08 | 8 | bytes | Varies from save to save; zeros are accepted (AE 2026 opens and re-saves a file written with zeros here). |

### `LIST:btdk`

The text documents of one Source Text property, as a single COS body.

**Parent:** [`LIST:btds`](#listbtds) · **Size:** variable (6-21 KB in the samples) · **py_aep:** `ListChunk` (raw `data`)

Unlike every other `LIST`, the body after the list type `btdk` is not a
chunk sequence but raw COS text, padded like any chunk when its length is
odd (about half the samples are).

#### COS syntax

The body is a sequence of PDF-style tokens. AE writes it with these rules
(all 353 sample bodies follow them):

| Element | As written by AE |
|---|---|
| Body | Starts with one space (0x20). The top level is a dictionary *without* `<<` `>>` delimiters: ` /98 << ... >> /0 << ... >> /1 << ... >>`. The body ends with the `>>` of the last value. |
| Separators | Exactly one space between any two tokens, including after `<<` and `[` and before `>>` and `]`. No tabs, line breaks or comments outside strings. |
| Dictionary | `<< /key value /key value >>`; empty: `<< >>`. Keys are names made of decimal digits (`/0`, `/1`, ... `/99`). Keys are in AE's own order, which is not sorted (`/1` lists `/4 /0 /5 /1 /2 /3`); a writer must keep the order it read and insert new keys where AE puts them. |
| Array | `[ value value ]`; empty: `[ ]`. |
| Name | `/Name`, used as a value for object types (`/CoolTypeFont`, `/SimplePaint`, `/PC` ...) and for an empty value (`/nil`). Key `/99` of a dictionary holds its type name. |
| Integer | Decimal, optional `-`: `0`, `-2`, `2398`. |
| Real | Always has a decimal point; whole values keep `.0` (`0.0`, `9.0`, `-2.0`); the leading zero is dropped below 1 (`.5`, `-.03571`) but `0.0` keeps it; no exponent. At most five digits after the point in the samples. A real must stay a real: writing `9` for `9.0` changes the bytes. |
| Boolean | `true`, `false`. |
| String | `( ... )`. Text is UTF-16 big-endian with a byte-order mark (`FE FF`); a few strings (bit-flag strings such as `(00110)`) are plain ASCII with no mark. Only `(`, `)` and `\` are escaped, with a backslash; every other byte - including 0x0A and 0x0D, which occur as halves of UTF-16 code units - is written raw. The encoding of an existing string cannot be inferred from its content, so a writer must keep track of it per string. |

Hex strings, indirect objects, streams and `null` do not occur.

#### Top-level keys

| Key | Value | Description |
|---|---|---|
| `/98` | `<< /0 n >>` | Format version of the text data (inferred): 7 in file version 92.14, 9 in 93.40 and 94.9, 11 in 95.6, 13 in 96.9 and later. |
| `/0` | dictionary | Resources shared by the documents: `/1` font table, `/4` line-breaking rule sets, `/5` character style sheets, `/6` paragraph style sheets, `/8` text frames. |
| `/1` | dictionary | The documents: `/4` composer, `/0` typography settings, `/5` used fonts, `/1` document array, `/2` default character style, `/3` default paragraph style (written in this order). `/4` appears from file version 95.6 (AE 24), `/5` from 96.9 (AE 25). |

Paths below are written from the top: `/1/1/0` is entry 0 of the array at
key `/1` of key `/1`.

#### Font table (`/0/1/0`)

An array of fonts; character styles refer to a font by its index here.

    << /0 << /99 /CoolTypeFont /0 << /0 (MyriadPro-Regular) /2 0 /5 (Version 2.115;PS 2.000;...) >> >> >>

| Key (in `/0/0`) | Description |
|---|---|
| `/0` | PostScript name (`FontObject.postScriptName`). |
| `/2` | Integer, 0 or 1. Unknown. |
| `/4` | Variable fonts only: the design vector, one `fixed 16.16` integer per axis. |
| `/5` | Optional: the font's version string (the font's name-table version, `FontObject.version`). |

Three to six fonts in the samples, always including `AdobeInvisFont`.
The same PostScript name may appear twice; AE writes such tables.

A font index is stored in five places, which must all be renumbered when an
entry is inserted: the `/0` key of every character style in the character
runs of every document, the default character style `/1/2`, the typography
settings `/1/0/0/0`, the character style of each style sheet in `/0/5`,
and the used-font records `/1/5/*/4`. AE inserts new fonts (scripted
`font` changes put the new font first; `replaceFont` inserts it right
after the replaced one and keeps the old entry) and renumbers all five.

#### Documents (`/1/1`)

One document per keyframe, or one for a static Source Text. Each document
is a dictionary with two keys:

| Path | Description |
|---|---|
| `/0/0` | The text, UTF-16. Paragraphs end with CR (U+000D) - line breaks are stored as CR, never LF - and the text always ends with one CR that ExtendScript does not show (`"Hello"` is stored as `Hello` followed by CR). AE fails to read a text without the final CR. |
| `/0/5` | Paragraph runs: `<< /0 [ run ... ] >>`. |
| `/0/6` | Character runs: `<< /0 [ run ... ] >>`. |
| `/0/8` | Optional: manual kerning runs (payload `<< /0 value >>`, or `<< >>` for no kerning). |
| `/0/7` | Optional: the kerning before the first character, written with `/0/8`. |
| `/0/9` | Seen once: a run array whose payload names OpenType features (`(tnumonum)`) (inferred). |
| `/1/4` | Optional (95.6 and later): the same composer record as the top-level `/1/4`. |
| `/1/5` | Optional (96.9 and later): integer, 0 in the samples. |
| `/1/0` | `[ << /0 0 >> ]` in the samples (inferred: the text frame of `/0/8` the document flows into). |
| `/1/1` | Lines per paragraph: a run array over the text whose payload `<< /1 n >>` gives the number of composed lines of that paragraph. Absent when the document is a single line (one paragraph laid out on one line); present otherwise, also for a box text that shows no line at all. |
| `/1/2` | The composed-line cache, see below. |

A run is `<< /0 payload /1 count >>`. Counts are UTF-16 code units of the
stored text, the final CR included, and the counts of an array add up to
the text length. Paragraph runs correspond one to one to the paragraphs;
AE merges adjacent character runs with equal styles. The payloads are:

    paragraph run:  << /0 << /0 () /5 <<paragraph style>> /6 0 >> >>
    character run:  << /0 << /0 () /5 0 /6 <<character style>> >> >>

Each run carries a complete style: all 42 paragraph keys or all 92
character keys, never a sparse set. The decoded keys:

| Character key | Description |
|---|---|
| `/0` | Font index into `/0/1/0`. |
| `/1` | Font size (real). |
| `/2`, `/3` | Faux bold, faux italic. |
| `/4` | Auto leading. |
| `/5` | Leading; AE stores `0.01` while auto leading is on. |
| `/6`, `/7` | Horizontal and vertical scale (1.0 = 100%). |
| `/8` | Tracking. |
| `/9` | Baseline shift. |
| `/11` | Auto kern type. |
| `/12` | Font caps option. |
| `/13` | Font baseline option (superscript, subscript). |
| `/18` | Ligatures. |
| `/35` | Baseline direction. |
| `/36` | Tsume (0.0-1.0). |
| `/52` | No break. |
| `/53` | Fill colour: `<< /99 /SimplePaint /0 << /0 1 /1 [ a r g b ] >> >>`, components 0.0-1.0, alpha 1.0. |
| `/54` | Stroke colour, same form. |
| `/56`, `/57` | Apply fill, apply stroke. |
| `/58` | Stroke over fill. |
| `/62` | Line join. |
| `/63` | Stroke width. |
| `/70` | Digit set. |

| Paragraph key | Description |
|---|---|
| `/0` | Justification. |
| `/1`, `/2`, `/3` | First-line indent, start indent, end indent. |
| `/4`, `/5` | Space before, space after. |
| `/8` | Leading type. |
| `/9` | Auto hyphenate. |
| `/21` | Roman hanging punctuation. |
| `/29` | Every-line composer (else single-line). |
| `/33` | Paragraph direction. |

Enumerated values are stored as their zero-based position in the matching
ExtendScript enumeration (baseline direction is one-based). The
ExtendScript `TextDocument` properties that read one value for the whole
document return the style of the first character.

#### Defaults, style sheets and settings

| Path | Description |
|---|---|
| `/1/2` | Default character style (92 keys). |
| `/1/3` | Default paragraph style (42 keys). |
| `/0/5` | Character style sheets: `<< /0 [ << /0 << /0 (Normal RGB) /6 <<character style>> >> >> ] >>`. |
| `/0/6` | Paragraph style sheets: `/0` the sheets (`(Normal RGB)` with a `/5` paragraph style), `/1` `[ << /0 0 >> ]`. |
| `/0/4` | Japanese line-breaking rule sets (inferred from the content): `/0` holds the sets `(Hard)` and `(Soft)`, each `/5 << /0 /1 /2 /3 (character lists) /4 integer >>`; `/1` `[ << /0 0 >> << /0 1 >> ]`. |
| `/1/0` | Typography settings: `/0 << /0 font index /1 [...] >>` (always `AdobeInvisFont` in the samples), `/3`-`/7` the reals 0.583, 0.333, 0.583, 0.333, 0.7 (inferred: superscript size and position, subscript size and position, small-caps size), `/9` 22 quotation-mark sets by language, `/8`, `/16`, `/17` unknown. |
| `/1/4` | Composer: `<< /0 7 /1 10 /2 0 /3 (DVA) >>`; `/3` is `(DVA)` for the Latin/CJK composer, `(Universal)` for the universal one (`TextDocument.composerEngine`). |
| `/1/5` | Used fonts: an array of records `<< /0 integer /1 <<composer>> /2 (bit string) /3 (bit string) /4 [ << /0 font index /1 (version string) /2 (identifier) >> ... ] >>`; one record in the samples. |

#### Text frames (`/0/8`)

`/0/8/0` is an array with one frame, shared by all the documents of the
layer: `<< /0 << /1 << /0 [ 32 reals ] >> /2 <<frame settings>> >> >>`.
The `/1` outline is present for box (paragraph) text only and is how box
text is recognised. It lists 16 points as x, y pairs in layer coordinates:
the top-left corner twice, the top-right, bottom-right and bottom-left
corners four times each, then the top-left corner twice again (a 220 x 140
box at -110, -70 starts `[ -110.0 -70.0 -110.0 -70.0 110.0 -70.0 ...`).

| Frame settings key | Description |
|---|---|
| `/0` | 1 for box text. |
| `/1` | Line orientation. |
| `/6` | `[ -2.0 -2.0 ]` for box text. |
| `/9` | Box inset spacing. |
| `/10` | First-baseline alignment: `<< /0 alignment /1 minimum >>`. |
| `/11` | Dictionary; box text has `/4 -2` and `/18 -2.0` in it. |
| `/13` | Box vertical alignment. |
| `/14` | Box auto-fit policy. |

The frame keys appear in ascending numeric order. Keyframe edits add or
remove documents, never frames: removing frame 0 breaks the layer in
AE 2026.

#### Composed-line cache (`/PC`)

`/1/2` of each document holds the text as AE last laid it out:

    [ << /99 /PC /5 0 /6 [ frame ... ] >> ]

It nests typed dictionaries: `/PC` > `/F` (frame) > `/R` > `/R` > `/L`
(line) > `/S` (segment) > `/G` (glyph run), children in `/6`. Known
fields:

| Path | Description |
|---|---|
| `/L` `/0/0` | Line origin `[ x y ]`; 0, 0 when absent. |
| `/L` `/10` | Baseline y. |
| `/S` `/15/0` | Characters in the segment; a line's character count is the sum over its segments. |
| `/S` `/15/7/7` | Character advances, cumulative from the start of the line. |

AE puts a whole line in one segment even across font changes. For point
text the lines are the paragraphs.

The cache is required: AE 26.3 crashes while opening a document whose
`/PC` was removed. It is not checked against the text: a file whose cache
is stale after a text edit opens normally (py_aep writes such files) and AE
lays the text out again. Within an AE session, ExtendScript's composed-line
properties can serve a stale cache too: after a script shortens the text,
`composedLineCount` keeps its old value and line ranges are clamped to the
new text (AE 26.3). Writers should leave the cache in place, stale, rather
than remove or rebuild its structure.

### `LIST:btgu`

Identifiers of the text documents of the preceding [`LIST:btds`](#listbtds).

**Parent:** [`LIST:tdgp`](#listtdgp), right after the `LIST:btds`

| Child | Occurs | Description |
|---|---|---|
| [`pgui`](#pgui) | documents + 1 | A 16-byte GUID per document, then one all-zero GUID. |

Every sample has one more `pgui` than its `btdk` has documents (two for a
static text, three for two keyframes) and the last one is all zeros; the
others look random and differ between layers.

## Render queue

The render queue is the root [`LIST:LRdr`](#listlrdr). Each render-queue
item is spread over three places: a fixed record in the `LIST:list` of
`LIST:LRdr` (its render settings), a group of rows in [`Rout`](#rout), and
a group of chunks in [`LIST:LItm`](#listlitm) (its comment and output
modules). The *n*-th item of each is the *n*-th render-queue item. Render
settings and output module templates are not stored in the project; they
live in After Effects' preferences.

A file written by AE always has a `LIST:LRdr`, even with an empty queue.
When adding the first item to an empty queue AE also rewrites two bytes of
the panel record [`ARsi`](#arsi).

### `LIST:LRdr`

The render queue.

**Parent:** root (see [Root chunk order](#root-chunk-order))

| Child | Occurs | Description |
|---|---|---|
| [`Rhed`](#rhed) | 1 | Render queue header. |
| [`Rout`](#rout) | 1 | Render Queue panel rows. |
| [`LIST:list`](#listlist) | 1 | [`lhd3`](#lhd3) + [`ldat`](#ldat): one [render-queue item record](#render-queue-item-record) per item. |
| [`LIST:LItm`](#listlitm) | 1 | Comments and output modules of the items. |
| [`LIST:LSIf`](#listlsif) | 1 | Render Queue panel state ([`ARsi`](#arsi)). |

This order holds in all 1,362 samples. The `lhd3` of the list has item
size 2246 (0x8C6), item type byte 1, and its count is the number of items;
its three capacity counters (0x0C, 0x18, 0x1C) equal the count, with a
floor of 1 for an empty queue, and AE rejects the file ("Invalid read
length") when they disagree with the count. An empty queue has the `lhd3`
and no `ldat`.

#### Render-queue item record

One record per item, 2246 bytes, in the `ldat` of the `LIST:list` above.
Big-endian like the rest of the file. Several settings are 4-byte fields
whose upper half is always 0.

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x000 | 2 | u2 | 1 in every sample. |
| 0x002 | 2 | u2 | 0. |
| 0x004 | 4 | u4 | Flags, see below. |
| 0x008 | 4 | u4 | Item id of the composition to render ([`idta`](#idta) 0x10). |
| 0x00C | 4 | s4 | Status: -1 will continue, 0 needs output, 1 unqueued, 2 queued, 3 rendering, 4 user stopped, 5 error stopped, 6 done (`RenderQueueItem.status` minus 3013). |
| 0x010 | 2 | u2 | 3 in every sample. |
| 0x012 | 2 | u2 | 0. |
| 0x014 | 4 | s4 | Time span start, dividend. Signed: a negative start is stored in two's complement. |
| 0x018 | 4 | u4 | Time span start, divisor. |
| 0x01C | 4 | s4 | Time span duration, dividend. |
| 0x020 | 4 | u4 | Time span duration, divisor. |
| 0x024 | 8 | | A third dividend/divisor pair; 0 in every sample. |
| 0x02C | 4 | fixed 16.16 | Frame rate of "Use this frame rate". While "Use comp's frame rate" is selected AE stores a rate it does not use: the comp's rate in most samples, 30 for items added by scripting. |
| 0x030 | 4 | u4 | Field render: 0 off, 1 upper field first, 2 lower field first. |
| 0x034 | 4 | u4 | 3:2 pulldown: 0 off, 1 WSSWW, 2 SSWWW, 3 SWWWS, 4 WWWSS, 5 WWSSW. |
| 0x038 | 2 | u2 | Quality: 0 wireframe, 1 draft, 2 best, 0xFFFF current settings. |
| 0x03A | 2 | u2 | Resolution, horizontal divisor (1 full, 2 half, 3 third, 4 quarter, any 1-99 for custom). 0 here and at 0x03C means current settings. |
| 0x03C | 2 | u2 | Resolution, vertical divisor. |
| 0x03E | 4 | u4 | Effects: 0 all off, 1 all on, 2 current settings. |
| 0x042 | 4 | u4 | Proxy use: 0 use no proxies, 1 use all proxies, 2 current settings, 3 use comp proxies only. |
| 0x046 | 4 | u4 | Motion blur: 0 off for all layers, 1 on for checked layers, 2 current settings. |
| 0x04A | 4 | u4 | Frame blending: same values as motion blur. |
| 0x04E | 4 | u4 | Log: 0 errors only, 1 errors and settings, 2 errors and per-frame info. |
| 0x052 | 4 | u4 | Skip existing files: 0 or 1. |
| 0x056 | 4 | u4 | 0. |
| 0x05A | 1024 | char[1024] | Render settings template name, UTF-8, NUL-padded ("Best Settings"; a French AE writes "Paramètres optimaux"). |
| 0x45A | 1024 | char[1024] | Path of the render log written for this item, UTF-8, NUL-padded; empty until AE has rendered the item with a log. |
| 0x85A | 4 | u4 | 0 or 1: 1 once the render settings were edited after the template was applied. AE 2026 sets it on every scripted `setSettings`, even of an unchanged value; `skipFrames` and the time-span attributes leave it. |
| 0x85E | 4 | u4 | Frame rate: 0 use comp's frame rate, 1 use this frame rate (0x02C). |
| 0x862 | 4 | u4 | Time span: 0 length of comp, 1 work area only, 2 custom. |
| 0x866 | 4 | s4 | -1 in every sample. |
| 0x86A | 4 | u4 | 0x00B40000 in every sample. |
| 0x86E | 4 | u4 | 0. |
| 0x872 | 4 | u4 | Solo switches: 0 all off, 2 current settings. |
| 0x876 | 4 | u4 | Disk cache: 0 read only, 2 current settings. |
| 0x87A | 4 | u4 | Guide layers: 0 all off, 2 current settings. |
| 0x87E | 4 | u4 | 2 in every sample. |
| 0x882 | 4 | s4 | Colour depth: -1 current settings, 0 8 bpc, 1 16 bpc, 2 32 bpc. |
| 0x886 | 16 | | 0. |
| 0x896 | 4 | u4 | Render start time, seconds since 1904-01-01 00:00; 0 when the item has not been rendered (`RenderQueueItem.startTime`). |
| 0x89A | 4 | u4 | Elapsed rendering time in seconds (`elapsedSeconds`). |
| 0x89E | 16 | | 0. |
| 0x8AE | 4 | u4 | Item id, unique in the queue. AE 2026 gives a new item (added or duplicated) the highest id of the queue + 1, and 2 in an empty queue. |
| 0x8B2 | 2 | u2 | 0. |
| 0x8B4 | 2 | u2 | 15 in most samples (1 and 14 seen). Unknown. |
| 0x8B6 | 16 | | 0. |

Flags at 0x007 (the low byte of 0x004):

| Bit | Mask | Meaning |
|---|---|---|
| 0 | 0x01 | Set on queued, rendered and stopped items, clear on unqueued and needs-output items (inferred: the Render check box). |
| 1 | 0x02 | Seen once. Unknown. |
| 2 | 0x04 | Notify when done (`RenderQueueItem.queueItemNotify`). |

The fields match the ExtendScript render settings one for one; AE's
scripting enforces bounds that a writer should keep: skip frames 0-99,
resolution divisors 0-99, a time span of at least one frame. AE accepts a
negative start or an end before the start and silently renders garbage. A
resolution pair with exactly one 0 is never produced by AE, and setting one
through scripting crashes AE 2026.

AE writes a shorter, 514-byte (0x202) record for file versions below 92.0;
no sample has one.

### `Rhed`

Render queue header.

**Parent:** [`LIST:LRdr`](#listlrdr) · **Size:** 20 bytes · **py_aep:** `RhedChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | 1 in every sample. |
| 0x02 | 2 | u2 | 2 in every sample. |
| 0x04 | 4 | u4 | 0. |
| 0x08 | 2 | u2 | Rectangle top: 0 in every sample. |
| 0x0A | 2 | u2 | Rectangle left: 0 in every sample. |
| 0x0C | 2 | u2 | Rectangle bottom: varies (183-1359 in the samples, median 274). |
| 0x0E | 2 | u2 | Rectangle right: varies (315-2556, median 1660). |
| 0x10 | 2 | u2 | 0. |
| 0x12 | 2 | u2 | 1 in every sample. |

The rectangle is inferred from its values (a panel-sized area in pixels,
top-left at 0, 0); it varies between saves and machines.

### `Rout`

One entry per row of the Render Queue panel (inferred from the counts).

**Parent:** [`LIST:LRdr`](#listlrdr) · **Size:** 4 + 4 x entries · **py_aep:** `RoutChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | u4 | Number of entries. |
| 0x04 | 4 x n | u4 | Entries, in render-queue order. |

Each item has five entries, plus two for each output module beyond the
first: the counts match the panel's rows (the item row, Render Settings,
Log, Output Module, Output To, then Output Module and Output To for each
further module). An empty queue has a count of 0. Typical entries:

| Row (inferred) | Value |
|---|---|
| Item | 0x00000011, or 0x40000011 (bit 30 set on about a third of the items, whatever their status) |
| Render Settings | 0x80000011 |
| Log | 0xA000007B |
| Output Module | 0x80000011 (0x00000011 for 8 items) |
| Output To | 0xA0000088 |
| Further Output Module | 0xC0000011 |
| Further Output To | 0xA0000088 |

Some files have low bytes one smaller (0x10, 0x7A, 0x87). The meaning of
the flag bits and the low byte is unknown. AE opens files with the default
five entries per item shown above (py_aep writes them for new items, and
its new items are byte-identical to AE's own).

### `LIST:LItm`

The comments and output modules of the render-queue items.

**Parent:** [`LIST:LRdr`](#listlrdr)

| Child | Occurs | Description |
|---|---|---|
| [`RCom`](#rcom) | 0-1 per item | The item's comment, before its `LIST:list`; only when the comment is not empty. |
| [`LIST:list`](#listlist) | 1 per item | [`lhd3`](#lhd3) + [`ldat`](#ldat): one [output-module settings record](#output-module-settings-record) per output module of the item (item size 128, item type byte 1, count = number of modules; counters as for `LIST:LRdr`). |
| [`LIST:LOm`](#listlom) | 1 per item | The item's output modules. |

The groups follow the render-queue order. An empty queue has an empty
`LIST:LItm`.

#### Output-module settings record

One per output module, 128 bytes, in the item's `LIST:list`; the *n*-th
record goes with the *n*-th module of the item's `LIST:LOm`. The decoded
fields were checked against ExtendScript `OutputModule.getSettings()` and
against sample pairs that differ in one setting.

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 2 | u2 | 5 in every sample. |
| 0x02 | 2 | u2 | 0. |
| 0x04 | 4 | u4 | Flags, see below. |
| 0x08 | 4 | u4 | Post-render action target (`postRenderTargetComp`): item id of the composition; 0 when none was chosen, which means the rendered composition. |
| 0x0C | 4 | u4 | 1 in most samples (0 in 36). Unknown. |
| 0x10 | 4 | u4 | Channels: 0 RGB, 1 RGB + Alpha, 2 Alpha. |
| 0x14 | 4 | u4 | Resize quality: 0 low, 1 high. |
| 0x18 | 2 | u2 | 1 in most samples; 5 and 22 in samples resized to the "HD 1920x1080 29.97" and "DVCPRO HD 960x720" presets (inferred: the Resize-to preset). |
| 0x1A | 2 | u2 | Resize: 0 or 1. The target size is in [`Roou`](#roou) 0x22/0x26. |
| 0x1C | 2 | u2 | Lock aspect ratio: 0 or 1. |
| 0x1E | 2 | u2 | Crop: 0 or 1. |
| 0x20 | 2 | s2 | Crop top. |
| 0x22 | 2 | s2 | Crop left. |
| 0x24 | 2 | s2 | Crop bottom. |
| 0x26 | 2 | s2 | Crop right. |
| 0x28 | 1 | u1 | 0. |
| 0x29 | 1 | u1 | Output Audio on: 1 for On and for Auto. |
| 0x2A | 1 | u1 | Output Audio auto: 1 for Auto. |
| 0x2B | 4 | | 0. |
| 0x2F | 1 | u1 | Bit 0: Include Project Link. Bit 1 set in two samples, unknown. |
| 0x30 | 4 | u4 | Post-render action: 0 none, 1 import, 2 import & replace usage, 3 set proxy (`postRenderAction` minus 3612). |
| 0x34 | 4 | u4 | 0, or 1 in three samples. Unknown. |
| 0x38 | 16 | bytes | All 0xFF in most records; all 0 in 48, among them the OCIO samples, always together with 0x5F = 1. Unknown. |
| 0x48 | 16 | bytes | Output colour profile id. All 0xFF when the output uses the working colour space. For an Adobe ICC profile, the profile's ICC Profile ID (the MD5 of the profile with header bytes 44-47, 64-67 and 84-99 zeroed); in an OCIO project, an id computed from the OCIO colour space. |
| 0x58 | 3 | | 0. |
| 0x5B | 1 | u1 | Convert to linear light: 0 off, 1 on, 2 on for 32 bpc. |
| 0x5C | 1 | u1 | 0 or 1. Unknown. |
| 0x5D | 1 | u1 | 1 when the output colour space is the working space. |
| 0x5E | 1 | u1 | Preserve RGB: 0 or 1 (the only byte that differs between the "preserve RGB" off and on samples). Not an ExtendScript setting: AE 2026 `getSettings` has no such key. |
| 0x5F | 1 | u1 | 1 exactly when 0x38 is all 0, else 0. Unknown. |
| 0x60 | 32 | | 0. |

Flags at 0x07 (the low byte of 0x04):

| Bit | Mask | Meaning |
|---|---|---|
| 1 | 0x02 | Set in 37 of 681 records. Unknown. |
| 3 | 0x08 | Use comp frame number. |
| 4 | 0x10 | Use region of interest (crop to the comp's region of interest). |
| 5 | 0x20 | The module has an output file: set exactly on the modules with a `LIST:Als2` path record. AE 2026 ignores a path record without it (the output file reads as `C:\`). |
| 6 | 0x40 | Include source XMP metadata. |

**Output Audio.** The ExtendScript "Output Audio" setting is stored only
in 0x29/0x2A: On = 1/0, Auto = 1/1, Off clears 0x29 and keeps 0x2A as it
was. Changing it never touches the audio fields of [`Roou`](#roou), and
AE ignores those fields when deciding whether audio is on (AE 2026).

### `RCom`

Comment of a render-queue item (`RenderQueueItem.comment`).

**Parent:** [`LIST:LItm`](#listlitm) · **Size:** variable

A [wrapper chunk](#wrapper-chunks) whose body is one [`Utf8`](#utf8) with
the comment. It sits just before the `LIST:list` of its item and is
omitted when the comment is empty (one sample has one).

### `LIST:LOm`

The output modules of one render-queue item. The list type is `LOm `
(with a trailing space).

**Parent:** [`LIST:LItm`](#listlitm)

Each output module is the following run of chunks; a second module repeats
the run, and a new module starts at each [`Roou`](#roou):

| Child | Occurs | Description |
|---|---|---|
| [`Roou`](#roou) | 1, first | Output format, size, frame rate, depth, audio. |
| [`Ropt`](#ropt) | 1 | Options of the output format. |
| [`hdrm`](#hdrm) | 0-1 | 1 byte, 1. Written with the next `Utf8` from file version 96.9 (AE 25); absent in older files. |
| [`Utf8`](#utf8) | with `hdrm` | HDR10 metadata JSON: `{}`, or for PNG output with HDR10 metadata the compact keys `colorMetadataPresent`, `displayPrimaries` (0 Rec. 709, 1 P3 D65, 2 Rec. 2020), `minLuminance`, `maxLuminance`, `maxContentLightLevel`, `maxFrameAverageLightLevel`. |
| [`LIST:Als2`](#listals2) | 0-1 | Output folder (the [`alas`](#alas) `fullpath`); written once an output file has been set, absent for a fresh module. |
| [`Utf8`](#utf8) | 1 | Output module name, as shown in the panel: the template name ("Lossless", "H.264 - Match Render Settings - 15 Mbps"). |
| [`Utf8`](#utf8) | 1 | File name template (`[compName].[fileextension]`, a sequence pattern, or a literal name); empty for a fresh module. |

The output file (`OutputModule.file`) is the `alas` folder joined with the
file name template. The last two `Utf8` chunks of a module are always the
name and the file name, which is how to find them whether or not `hdrm` and
`LIST:Als2` are present.

### `Roou`

Output format and video/audio settings of an output module.

**Parent:** [`LIST:LOm`](#listlom) · **Size:** 154 bytes · **py_aep:** `RouuChunk`

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | fourcc | `FXTC` in every sample. |
| 0x04 | 4 | fourcc | Handler tag: `CTXF` with AVI, H.264, MP3, WAV and AIFF, `DOVT` with QuickTime, `MIB8` with image sequences, `FXTC` in a few samples. It is not the codec (the codec is in the [`Ropt`](#ropt) options) and does not always match the format (an OpenEXR module with `CTXF` exists), so it is not a reliable format indicator. |
| 0x08 | 4 | u4 | AE version word, encoded as in [`head`](#head) 0x04; equal to the file's own in 651 of 681 samples (the others carry an older version). |
| 0x0C | 4 | u4 | 0x80000000 in every sample (as `head` 0x08). |
| 0x10 | 4 | u4 | Starting # (first frame number of an image sequence). |
| 0x14 | 4 | s4 | -1 in every sample. |
| 0x18 | 2 | bytes | `01 00` in every sample. |
| 0x1A | 4 | fourcc | Output format: `.AVI`, `AIFF`, `H264`, `IFF `, `JPEG`, `Mp3 `, `MooV` (QuickTime), `oEXR`, `png!`, `8BPS` (Photoshop), `RHDR` (Radiance), `SGI `, `TIF `, `TPIC` (Targa), `wao_` (WAV), `sDPX` (DPX/Cineon). It selects the [`Ropt`](#ropt) layout. ExtendScript cannot change the format of a module ("Format" is read-only). |
| 0x1E | 4 | | 0. |
| 0x22 | 4 | u4 | Output width (the resize target when Resize is on); 0 when video output is off, as for the audio formats. |
| 0x26 | 4 | u4 | Output height, likewise. |
| 0x2A | 14 | | 0. |
| 0x38 | 2 | u2 | 1 in the samples (600 in five H.264 samples). Output module templates kept in AE's preferences have 0 here (inferred: set when a template is applied to a render-queue item). |
| 0x3A | 8 | u8 | 0. |
| 0x42 | 4 | fixed 16.16 | Output frame rate: the render frame rate divided by (skip frames + 1), e.g. 24.0 = `00 18 00 00`, 29.97 = `00 1D F8 52`, 30 fps skipping 3 = 7.5 = `00 07 80 00`. See below. |
| 0x46 | 2 | s2 | Depth in bits per pixel: 24 Millions of Colors, 32 Millions of Colors+, 48 Trillions of Colors, 64 Trillions of Colors+, 96 Floating Point, 128 Floating Point+ (the values in the samples); ExtendScript also lists 8 = 256 Colors, 40 = 256 Grays and -32 = Floating Point Gray, stored `FF E0` (AE 2026 reads it as Floating Point Gray and keeps it on save). |
| 0x48 | 2 | bytes | `01 01` in every sample. |
| 0x4A | 4 | u4 | Colour: 1 premultiplied (matted), 0 straight (unmatted). |
| 0x4E | 4 | u4 | Same value as 0x4A in every sample. |
| 0x52 | 4 | fourcc | `FIEL`. |
| 0x56 | 2 | u2 | 1 in every sample. |
| 0x58 | 4 | u4 | 0 or 1. Unknown. |
| 0x5C | 4 | u4 | 0 or 1. Unknown. |
| 0x60 | 4 | u4 | 0. |
| 0x64 | 8 | f8 | Audio sample rate in Hz (8000-96000, also 12000); -1.0 while unset. |
| 0x6C | 2 | u2 | Audio sample encoding: 1 unsigned PCM, 2 signed PCM, 3 float; 0xFFFF while unset. |
| 0x6E | 2 | u2 | Audio bytes per sample: 1 (8 bit), 2 (16 bit), 4 (32 bit); 0xFFFF while unset. |
| 0x70 | 2 | u2 | Audio channels: 1 mono, 2 stereo; 0 while unset. |
| 0x72 | 10 | | 0. |
| 0x7C | 4 | u4 | 1 in most samples (4 and 10 seen). Unknown. |
| 0x80 | 4 | u4 | 1 in most samples (3 and 9 seen). Unknown. |
| 0x84 | 4 | u4 | 0 in most samples (1-5 in H.264 samples). Unknown. |
| 0x88 | 18 | | 0. |

Every sample (file versions 92.14 to 97.7) has 154 bytes.

The frame rate's fraction sits at 0x44-0x45, right before the depth: a
reader that takes 0x44-0x47 as one depth value sees `F852xxxx` for 29.97
fps output and must use the low two bytes.

**Output frame rate and skip frames.** The output frame rate is the only
trace of `RenderQueueItem.skipFrames` in the file (sample items that differ
only in skip frames differ only here). Measured on AE 2026:

- AE rewrites the rate when it prepares the item for output (seen after a
  script set the output file and time span of a queued item): a 60 fps or
  12.5 fps comp then stores 60 or 12.5. Before that, an item added by a
  script stores 30 whatever the comp rate, and setting `skipFrames`, the
  render frame rate or the comp frame rate, or applying an output-module
  template, from a script does not change it.
- When it opens a project, AE reports `skipFrames` 0 for every item, also
  for one saved with 7.5 fps for 30 fps rendering, and keeps the stored
  rate until it prepares the item again. The stored rate is not read when
  AE renders: items storing 12 and 6 fps for a 24 fps comp render all 24
  frames of a 1 s comp, while `skipFrames` 1 and 3 set in the same session
  render 12 and 6.
- Changing the composition's frame rate leaves the stored rate as it is:
  an item rendering a 24 fps comp at its own rate with skip 1 stores 12,
  and still stores 12 after a script sets the comp to 48 fps.

**Audio fields.** Write the three audio fields as whole `u2` values: AE
reads a half-written field (`FF 01`) as its fallback, 32 bit. The audio
format counts as set when the channel count is not 0. Measured on AE 2026:

- When AE loads a set format, or a script sets the channels, it completes
  the others: a rate of -1 becomes 48000 (other unsupported rates snap to
  a supported one, 0 to 8000, 12345 to 11025), an invalid sample size
  becomes 2, and the encoding becomes 3 for 4-byte samples, else 2.
- An unset format loads as stored; ExtendScript then reports 32 Bit,
  Stereo and an empty rate.
- Setting the bit depth on an unset format writes the encoding from the
  size (1 for 1 byte, 2 for 2, 3 for 4) and leaves the channels at 0.
- 3 bytes per sample ("24 Bit") is not a usable value: setting it through
  scripting crashes AE, and a stored 3 in a set format loads as 16 bit.

### `Ropt`

Options of the output format, laid out by the format's own convention.

**Parent:** [`LIST:LOm`](#listlom) · **Size:** variable (30 bytes to 41 KB) · **py_aep:** `RoptChunk` (variants `PngRoptChunk`, `OpenExrRoptChunk`, `TargaRoptChunk`, `JpegRoptChunk`, `CineonRoptChunk`, `TiffRoptChunk`)

Every variant starts with the same 10 bytes:

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | fourcc | Format code; the same as [`Roou`](#roou) 0x1A. |
| 0x04 | 2 | u2 | Version of the options: 1 (PNG, OpenEXR), 3 (DPX/Cineon), 0x002E (Targa, JPEG, SGI, IFF, Radiance), 0x0109 (TIFF, Photoshop), 0x0410 (the XML formats). |
| 0x06 | 4 | u4 | Total size of the options, equal to the chunk body length. |

| Format | Code | Size in the samples | Layout |
|---|---|---|---|
| PNG | `png!` | 322 | [PNG options](#png-options-png) |
| OpenEXR | `oEXR` | 78 | [OpenEXR options](#openexr-options-oexr) |
| Targa, JPEG, SGI, IFF, Radiance | `TPIC` `JPEG` `SGI ` `IFF ` `RHDR` | 84, 58, 70, 78, 30 | [Photoshop-plug-in options](#photoshop-plug-in-options) |
| DPX/Cineon | `sDPX` | 48 | [DPX/Cineon options](#dpxcineon-options-sdpx) |
| TIFF, Photoshop | `TIF ` `8BPS` | 602 | [TIFF and Photoshop options](#tiff-and-photoshop-options) |
| H.264, AVI, QuickTime, MP3, WAV, AIFF | `H264` `.AVI` `MooV` `Mp3 ` `wao_` `AIFF` | 4 KB-41 KB | [XML options](#xml-options) |

#### PNG options (`png!`)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 10 | | Header: `png!`, version 1, size 322. |
| 0x0A | 4 | bytes | `01 00 00 00`. |
| 0x0E | 2 | u2 | 0. |
| 0x10 | 2 | u2 | 1. |
| 0x12 | 4 | u4 | Width. |
| 0x16 | 4 | u4 | Height. |
| 0x1A | 4 | u4 | Bits per channel: 8 or 16. |
| 0x1E | 4 | u4 | Compression: 0 none, 1 interlaced (bit 0). |
| 0x22 | 4 | u4 | Flags: bit 1 always set, bit 2 = alpha (2 for RGB, 6 for RGB + Alpha). |
| 0x26 | 8 | | 0. |
| 0x2E | 4 | u4 | Channel count: 3 (RGB) or 4 (RGB + Alpha). |
| 0x32 | 272 | | 0. |

In every sample the bit depth, alpha flag and channel count agree with the
module's Depth and Channels; AE 2026 renders the module's Depth and
Channels even when they disagree. The HDR10 metadata of PNG output is the
JSON `Utf8` of the [`LIST:LOm`](#listlom).

#### OpenEXR options (`oEXR`)

After the header the options are little-endian.

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 10 | | Header: `oEXR`, version 1, size 78. |
| 0x0A | 4 | bytes | `01 00 00 00`. |
| 0x0E | 1 | u1 | Compression: 0 none, 1 RLE, 2 ZIP, 3 ZIP16, 4 PIZ, 5 PXR24, 6 B44, 7 B44A, 8 DWAA, 9 DWAB, 10 HTJ2K 256, 11 HTJ2K 32 (10 and 11 from AE 2026). |
| 0x0F | 1 | u1 | 32-bit float channels (else 16-bit half). |
| 0x10 | 1 | u1 | Luminance/chroma. |
| 0x11 | 1 | | 0. |
| 0x12 | 4 | f4 LE | DWA compression level, stored whatever the compression: 45.0 by default (every file version 96.9 sample that does not set it); 0.0 in the 92.14 files (inferred: written before AE had the DWA option). |
| 0x16 | 56 | | 0. |

#### Photoshop-plug-in options

Targa, JPEG, SGI, IFF and Radiance output are written by Photoshop-style
format plug-ins. Their options use the envelope of the
[Photoshop-plug-in `opti`](#opti) record:

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 10 | | Header: format code, version 0x002E, size 30 + block length. |
| 0x0A | 4 | bytes | First byte 1 (JPEG), 3 (SGI), 4 or 5 (Targa), 2 (Radiance), 0 (IFF); the rest 0. AE rewrites it on save; it is not load-bearing. |
| 0x0E | 4 | | 0. |
| 0x12 | 4 | u4 | Block length. |
| 0x16 | 8 | bytes | 0 in every `Ropt`. |
| 0x1E | n | | The plug-in's block, below. |

**Targa** (`TPIC`, 54-byte block):

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x1E | 46 | | 0. |
| 0x4C | 1 | u1 | 1 in every sample. |
| 0x4D | 1 | u1 | Bits per pixel: 24 or 32. |
| 0x4E | 4 | fourcc | `TimS`. |
| 0x52 | 1 | u1 | RLE compression. |
| 0x53 | 1 | | 0. |

The bits-per-pixel byte, not the module's Depth, decides the written file
(AE 2026 renders): 32 writes a 32-bit TGA with alpha even when the Depth is
Millions of Colors; 24 and 16 write a 24-bit TGA. AE only updates this byte
when its Targa Options dialog is used, so samples hold both 32 with an RGB
Depth and 24 with an RGBA Depth.

**JPEG** (`JPEG`, 28-byte block):

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x1E | 4 | fourcc | `JP64`. |
| 0x22 | 16 | | 0. |
| 0x32 | 2 | u2 | 0 in every sample. |
| 0x34 | 2 | u2 | Quality, 0-10 (5 by default). |
| 0x36 | 2 | u2 | Format: 0 baseline standard, 1 baseline optimized, 2 progressive. |
| 0x38 | 2 | u2 | Progressive scans as an index: 1, 2, 3 = 3, 4, 5 scans; 1 by default, also for baseline formats. |

A scans value of 0 or above 3 makes AE 2026 hang when rendering.

**SGI** (`SGI `, 40-byte block): `SG64` at 0x1E, 0 up to 0x43, RLE
compression as a `u2` at 0x44 (1 in both samples).

**IFF** (`IFF `, 48-byte block): no signature; little-endian `u2` values
1, 1, 24, 24, 0, 1, 0, -1, 0, -1 at 0x26-0x39 in both samples, the rest 0.
Meanings unknown.

**Radiance** (`RHDR`): block length 0, the 30-byte envelope only.

#### DPX/Cineon options (`sDPX`)

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 10 | | Header: `sDPX`, version 3, size 48. |
| 0x0A | 4 | | 0. |
| 0x0E | 2 | u2 | 10-bit black point (0-1023; AE's default is 0). |
| 0x10 | 2 | u2 | 10-bit white point (1023 by default). |
| 0x12 | 8 | f8 | Converted black point (0.0 by default). |
| 0x1A | 8 | f8 | Converted white point (1.0 by default). |
| 0x22 | 8 | f8 | Current gamma (1.0 by default). |
| 0x2A | 2 | u2 | Highlight expansion. |
| 0x2C | 1 | u1 | Logarithmic conversion. |
| 0x2D | 1 | u1 | File format: 1 DPX, 0 FIDO/Cineon 4.5. |
| 0x2E | 1 | u1 | Bit depth: 8, 10, 12 or 16. Not used with FIDO/Cineon (always 10 bit), where it keeps a stale value. |
| 0x2F | 1 | u1 | 0, or 0x98 in two 16-bit samples. Unknown. |

#### TIFF and Photoshop options

The 602-byte (version 0x0109) record of the
[Photoshop and TIFF `opti`](#opti), with the image fields left at 0:

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x000 | 10 | | Header: `TIF ` or `8BPS`, version 0x0109, size 602. |
| 0x00A | 2 | | 0. |
| 0x00C | 2 | bytes | `01 01`. |
| 0x00E | 586 | | 0 in every sample. |
| 0x258 | 1 | u1 | TIFF: IBM PC byte order. |
| 0x259 | 1 | u1 | TIFF: LZW compression. |

These bytes are what AE writes for its "TIFF Sequence with Alpha" template.

#### XML options

H.264 (`H264`), AVI (`.AVI`), QuickTime (`MooV`), MP3 (`Mp3 `), WAV
(`wao_`) and AIFF (`AIFF`) keep their options as an XML document after a
34-byte envelope:

| Offset | Length | Type | Description |
|---|---|---|---|
| 0x00 | 4 | fourcc | Format code. |
| 0x04 | 2 | u2 | 0x0410 in every sample. |
| 0x06 | 4 | u4 | Total size of the options (the chunk body length). |
| 0x0A | 8 | bytes | 0. |
| 0x12 | 4 | fourcc | File type: `H264`, `AVIV`, `MooV`, `MP3 `, `WAVE`, `AIFF`. |
| 0x16 | 4 | fourcc | Creator: `NICK` for H.264, `????` for the others. |
| 0x1A | 4 | fourcc | Codec: `avc1` (H.264); for AVI ` BID` (uncompressed), `dsvp`, `dsv2`, `dsvn`, `VUYI`, `YVYU`; for QuickTime `AVdn` (DNxHD/DNxHR), `CFHD`, `rle `, `avc1`, `apcn`, `apch`; 0 for the audio formats. |
| 0x1E | 4 | u4 | Length of the XML text: the total size minus 36. |
| 0x22 | n | UTF-8 | The XML text, ending with `>` and a line feed. |
| 0x22 + n | 2 | | Two NUL bytes. |

**Both lengths are load-bearing.** AE reads exactly the number of bytes
the header announces: with stale lengths after an edit of the XML, AE 26.3
silently truncates the XML on open (losing `</PremiereData>`) and saves the
damaged options back. Update 0x06 and 0x1E with every change.

The XML is a parameter graph. Elements reference each other by number:
`ObjectID` defines an object, `ObjectRef` points to one.

    <?xml version="1.0" encoding="UTF-8"?>
    <PremiereData Version="3">
    	<AfterEffects_MediaCore_OutputOptions ObjectRef="1"/>
    	<ExporterParamContainer ObjectID="1" ClassID="5c20a4a5-5e7c-4032-85b8-26ad4531fe7b" Version="1">
    		<ParamContainerItems Version="1">
    			<ParamContainerItem Index="0" ObjectRef="2"/>
    		</ParamContainerItems>
    		<ContainedParamsVersion>1</ContainedParamsVersion>
    	</ExporterParamContainer>
    	<ExporterParam ObjectID="2" ClassID="9f049ab7-d48f-43e9-a8ca-4d7f21233625" Version="1">
    		<ParamType>10</ParamType>
    		<ParamOrdinalValue>0</ParamOrdinalValue>
    		<ParamIdentifier>0</ParamIdentifier>
    		<ParamName></ParamName>
    		<ExporterChildParams ObjectRef="3"/>
    	</ExporterParam>
    	...
    </PremiereData>

- An `ExporterParamContainer` lists its parameters through
  `ParamContainerItem` references; a group parameter points to the
  container of its children with `ExporterChildParams`.
- An `ExporterParam` has a `ParamIdentifier` (`ADBEVideoCodec`,
  `ADBEAudioRatePerSecond`, `BitRate` ...), a `ParamType`, a
  `ParamOrdinalValue` (its position in the container) and, when it has a
  value, a `ParamValue` as its first child. Other children:
  `ParamName`, `ParamMinValue`, `ParamMaxValue`, `ParamIsHidden`,
  `ParamIsDisabled`, `ParamIsSlider`, `ParamAuxValue`, `ParamFlags`,
  `IsOptionalParam`, `ParamArbData`.
- `ParamType` values seen: 1 boolean, 2 integer, 3 real, 4 frame rate,
  6 string, 7 button, 8 group, 9 channel configuration, 10 root,
  11 ratio. The `ClassID` attribute follows the type.
- Values are text: integers in decimal (four-character codes as their
  integer, e.g. `ADBEAudioCodec` 1094796064 = `AAC `), whole reals with a
  trailing point (`15.`), booleans `true`/`false`, ratios `n,d`
  (`ADBEVideoAspect` `1,1`), frame rates as ticks per frame at
  254,016,000,000 ticks per second (`ADBEVideoFPS` 8467200000 = 30 fps).
- `ParamArbData` holds base64 data with a decimal `Checksum` attribute
  whose algorithm is unknown: keep it verbatim.
- An **unset** parameter keeps its `ExporterParam` element and loses only
  its `ParamValue` (the H.264 Baseline profile is stored this way). Deleting
  the whole element reads back the same but breaks the object graph.

Formatting, for byte identity with AE: a double-quoted XML declaration,
tab indentation and LF line ends, empty elements with attributes
self-closed without a space (`<Foo ObjectRef="1"/>`), empty elements
without attributes written as a pair (`<ParamName></ParamName>`).

Some decoded parameter values, from AE-authored samples that differ in one
dialog setting:

| Parameter | Values |
|---|---|
| `ADBEVideoMPEGProfile` (H.264) | unset = Baseline, 1 Main (also what "Auto" saves), 3 High, 4 High 10. |
| `ADBEVideoMPEGProfileLevel` (H.264) | Level x 10 (41 = level 4.1); 100 = unrestricted. |
| `ADBEMPEGAudioFormat` (H.264 audio format) | `AAC `, `MPEG`, `PCM ` as integers. |
| `ADBEVideoResolution` (DNxHD/DNxHR in QuickTime) | 1001-1019, one per entry of the resolution menu. Kept, and stale, when the codec changes. |
| `ADBEDNxHDAlphaType` | 1 compressed alpha; absent = none. |
| `ADBEMPEGVideoEncodingPerformanceParam` | absent = hardware, 1 = software encoding. |
| `BitRate` (MP3) | The bit rate. |

When a module follows the render settings' frame rate, AE recomputes
`ADBEVideoFPS` from the comp on open, whatever the file says.

## Chunk index

Every chunk documented on this page, alphabetically.

| Chunk | Section |
|---|---|
| [`acer`](#acer) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`acid`](#acid) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`ACsi`](#acsi) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`adfr`](#adfr) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`AFsi`](#afsi) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`alas`](#alas) | [Footage](#footage) |
| [`angl`](#angl) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`apid`](#apid) | [Footage](#footage) |
| [`aRbp`](#arbp) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`ARsi`](#arsi) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`blsi`](#blsi) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`blsv`](#blsv) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`btov`](#btov) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`CapL`](#capl) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CcCt`](#ccct) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CCEx`](#ccex) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CCId`](#ccid) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`cdat`](#cdat) | [Layers, properties and keyframes](#layers-properties-and-keyframes) |
| [`CDef`](#cdef) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`cdrp`](#cdrp) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`cdta`](#cdta) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CFEd`](#cfed) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CLId`](#clid) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`cmta`](#cmta) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`comr`](#comr) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`cpid`](#cpid) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`CprC`](#cprc) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CPTm`](#cptm) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CROI`](#croi) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CsCt`](#csct) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CSEd`](#csed) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CSGe`](#csge) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CSMd`](#csmd) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CSMe`](#csme) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CSMh`](#csmh) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CSMp`](#csmp) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CSMs`](#csms) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CSMt`](#csmt) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CSMw`](#csmw) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CTov`](#ctov) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CTyp`](#ctyp) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`CVal`](#cval) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`dcui`](#dcui) | [Footage](#footage) |
| [`dmtr`](#dmtr) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`drop`](#drop) | [Footage](#footage) |
| [`dwga`](#dwga) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`EfDC`](#efdc) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`elab`](#elab) | [Footage](#footage) |
| [`embp`](#embp) | [Footage](#footage) |
| [`empd`](#empd) | [Footage](#footage) |
| [`engv`](#engv) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`epid`](#epid) | [Footage](#footage) |
| [`ewin`](#ewin) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`ewot`](#ewot) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`fcid`](#fcid) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`fdta`](#fdta) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`fiac`](#fiac) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`fidi`](#fidi) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`fifl`](#fifl) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`fimr`](#fimr) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`fiop`](#fiop) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`fipc`](#fipc) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`fipl`](#fipl) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`fips`](#fips) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`fits`](#fits) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`fitt`](#fitt) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`fivc`](#fivc) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`fivi`](#fivi) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`flow`](#flow) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`fmpl`](#fmpl) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`fnam`](#fnam) | [File structure](#file-structure) |
| [`foac`](#foac) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`fots`](#fots) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`fott`](#fott) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`fovc`](#fovc) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`fovi`](#fovi) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`fpms`](#fpms) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`fpmv`](#fpmv) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`fpol`](#fpol) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`fpov`](#fpov) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`fpsz`](#fpsz) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`ftgi`](#ftgi) | [Footage](#footage) |
| [`fth5`](#fth5) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`ftts`](#ftts) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`ftwd`](#ftwd) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`fvdv`](#fvdv) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`gdta`](#gdta) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`hdrm`](#hdrm) | [Footage](#footage) |
| [`head`](#head) | [File versions](#file-versions) |
| [`idpc`](#idpc) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`idpi`](#idpi) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`idta`](#idta) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`iide`](#iide) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`init`](#init) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`ipws`](#ipws) | [Footage](#footage) |
| [`ldat`](#ldat) | [Layers, properties and keyframes](#layers-properties-and-keyframes) |
| [`ldta`](#ldta) | [Layers, properties and keyframes](#layers-properties-and-keyframes) |
| [`lhd3`](#lhd3) | [Layers, properties and keyframes](#layers-properties-and-keyframes) |
| [`linl`](#linl) | [Footage](#footage) |
| [`LIST`](#list) | [File structure](#file-structure) |
| [`LIST:Als2`](#listals2) | [Footage](#footage) |
| [`LIST:aRbs`](#listarbs) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`LIST:btdk`](#listbtdk) | [Text](#text) |
| [`LIST:btds`](#listbtds) | [Text](#text) |
| [`LIST:btgu`](#listbtgu) | [Text](#text) |
| [`LIST:CapS`](#listcaps) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:CCtl`](#listcctl) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:CIF2`](#listcif2) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:CIF3`](#listcif3) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:CIFO`](#listcifo) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:CLay`](#listclay) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:CLRS`](#listclrs) | [Footage](#footage) |
| [`LIST:CPPl`](#listcppl) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`LIST:CPrp`](#listcprp) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:CpS2`](#listcps2) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:CTRE`](#listctre) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`LIST:dats`](#listdats) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:DLay`](#listdlay) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:EfDf`](#listefdf) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`LIST:EfdG`](#listefdg) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`LIST:Ewst`](#listewst) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:ExEn`](#listexen) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`LIST:FEE`](#listfee) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:Fold`](#listfold) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:GCky`](#listgcky) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`LIST:GCst`](#listgcst) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`LIST:Gide`](#listgide) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:gpuG`](#listgpug) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`LIST:Item`](#listitem) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:Layr`](#listlayr) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:list`](#listlist) | [Layers, properties and keyframes](#layers-properties-and-keyframes) |
| [`LIST:LItm`](#listlitm) | [Render queue](#render-queue) |
| [`LIST:LOm`](#listlom) | [Render queue](#render-queue) |
| [`LIST:LRdr`](#listlrdr) | [Render queue](#render-queue) |
| [`LIST:LSIf`](#listlsif) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:mnfo`](#listmnfo) | [Footage](#footage) |
| [`LIST:mrky`](#listmrky) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`LIST:mrst`](#listmrst) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`LIST:Nmrd`](#listnmrd) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`LIST:om-s`](#listom-s) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`LIST:omks`](#listomks) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`LIST:otky`](#listotky) | [Layers, properties and keyframes](#layers-properties-and-keyframes) |
| [`LIST:otst`](#listotst) | [Layers, properties and keyframes](#layers-properties-and-keyframes) |
| [`LIST:OvdG`](#listovdg) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:OvG2`](#listovg2) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:parT`](#listpart) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`LIST:Pefl`](#listpefl) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`LIST:Pin`](#listpin) | [Footage](#footage) |
| [`LIST:pnts`](#listpnts) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`LIST:PRin`](#listprin) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:PTRE`](#listptre) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`LIST:SecL`](#listsecl) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:Sfdr`](#listsfdr) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:sfnm`](#listsfnm) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`LIST:shap`](#listshap) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`LIST:SLay`](#listslay) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`LIST:sspc`](#listsspc) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`LIST:StVc`](#liststvc) | [Footage](#footage) |
| [`LIST:tdbs`](#listtdbs) | [Layers, properties and keyframes](#layers-properties-and-keyframes) |
| [`LIST:tdgp`](#listtdgp) | [Layers, properties and keyframes](#layers-properties-and-keyframes) |
| [`lnrb`](#lnrb) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`lnrp`](#lnrp) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`Mcsp`](#mcsp_1) | [Footage](#footage) |
| [`mcsp`](#mcsp) | [Footage](#footage) |
| [`mdla`](#mdla) | [Layers, properties and keyframes](#layers-properties-and-keyframes) |
| [`mdld`](#mdld) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`mdls`](#mdls) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`mdlv`](#mdlv) | [Layers, properties and keyframes](#layers-properties-and-keyframes) |
| [`menv`](#menv) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`mkif`](#mkif) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`mrid`](#mrid) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`mtif`](#mtif) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`mtov`](#mtov) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`mtpd`](#mtpd) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`mtpr`](#mtpr) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`nhed`](#nhed) | [File versions](#file-versions) |
| [`NmHd`](#nmhd) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`nnhd`](#nnhd) | [File versions](#file-versions) |
| [`numS`](#nums) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`oacc`](#oacc) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`ocid`](#ocid) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`ocsp`](#ocsp) | [Footage](#footage) |
| [`olsz`](#olsz) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`omtn`](#omtn) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`opct`](#opct) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`opti`](#opti) | [Footage](#footage) |
| [`otda`](#otda) | [Layers, properties and keyframes](#layers-properties-and-keyframes) |
| [`otln`](#otln) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`pard`](#pard) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`parn`](#parn) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`pcms`](#pcms) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`pdnm`](#pdnm) | [File structure](#file-structure) |
| [`pdvc`](#pdvc) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`PEdt`](#pedt) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`PEsz`](#pesz) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`PEvr`](#pevr) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`pgui`](#pgui) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`pjef`](#pjef) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`pnta`](#pnta) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`pprf`](#pprf) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`ppSn`](#ppsn) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`prda`](#prda) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`prgb`](#prgb) | [Footage](#footage) |
| [`prin`](#prin) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`PwCs`](#pwcs) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`qtlg`](#qtlg) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`RCom`](#rcom) | [Render queue](#render-queue) |
| [`Rhed`](#rhed) | [Render queue](#render-queue) |
| [`rndn`](#rndn) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`Roou`](#roou) | [Render queue](#render-queue) |
| [`Ropt`](#ropt) | [Render queue](#render-queue) |
| [`Rout`](#rout) | [Render queue](#render-queue) |
| [`sdat`](#sdat) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`seq`](#seq) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`sfdt`](#sfdt) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`sfid`](#sfid) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`shph`](#shph) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`Smax`](#smax) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`Smin`](#smin) | [Items, folders and compositions](#items-folders-and-compositions) |
| [`sspc`](#sspc) | [Footage](#footage) |
| [`strt`](#strt) | [Footage](#footage) |
| [`StVS`](#stvs) | [Footage](#footage) |
| [`svap`](#svap) | [File versions](#file-versions) |
| [`tdb4`](#tdb4) | [Layers, properties and keyframes](#layers-properties-and-keyframes) |
| [`tdli`](#tdli) | [Layers, properties and keyframes](#layers-properties-and-keyframes) |
| [`tdmn`](#tdmn) | [Layers, properties and keyframes](#layers-properties-and-keyframes) |
| [`tdpi`](#tdpi) | [Layers, properties and keyframes](#layers-properties-and-keyframes) |
| [`tdps`](#tdps) | [Layers, properties and keyframes](#layers-properties-and-keyframes) |
| [`tdsb`](#tdsb) | [Layers, properties and keyframes](#layers-properties-and-keyframes) |
| [`tdsn`](#tdsn) | [File structure](#file-structure) |
| [`tdum`](#tdum) | [Layers, properties and keyframes](#layers-properties-and-keyframes) |
| [`tmds`](#tmds) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`tpds`](#tpds) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`tpsp`](#tpsp) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`tver`](#tver) | [Masks, shapes, paint, markers and effects](#masks-shapes-paint-markers-and-effects) |
| [`Utf8`](#utf8) | [File structure](#file-structure) |
| [`vfdn`](#vfdn) | [File structure](#file-structure) |
| [`wsnm`](#wsnm) | [Project settings and colour management](#project-settings-and-colour-management) |
| [`wsns`](#wsns) | [Project settings and colour management](#project-settings-and-colour-management) |
