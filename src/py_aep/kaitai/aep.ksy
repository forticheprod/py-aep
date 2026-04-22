meta:
  id: aep
  endian: be
  file-extension: aep

seq:
  - id: root
    type: chunk
  - id: xmp_packet
    type: str
    encoding: UTF-8
    size-eos: true

types:
  chunks:
    seq:
      - id: chunks
        type: chunk
        repeat: eos
  chunk:
    seq:
      - id: chunk_type
        size: 4
        type: str
        encoding: ASCII
      - id: len_body
        type: u4
      - id: body
        size: len_body
        type:
          switch-on: 'chunk_type == "opti" and len_body == 0 ? "" : chunk_type'  # 3D Model Layers opti body is empty
          cases:
            '"acer"': acer_body # Compensate for Scene-Referred Profiles setting
            '"adfr"': adfr_body # Audio sample rate settings
            '"alas"': utf8_body # File footage data in json format as a string, contains file path
            '"CapL"': u4_body   # Essential Graphics preferred locale ID
            '"CcCt"': u4_body   # Essential Graphics controller count
            '"CCId"': u4_body   # Essential Graphics composition ID reference
            '"cdat"': cdat_body(_parent.as<list_body>._parent.as<chunk>._parent.as<list_body>.list_type == "otst") # Property value(s)
            '"cdrp"': cdrp_body # Composition drop frame
            '"cdta"': cdta_body # Composition data
            '"CLId"': u4_body   # Essential Graphics layer ID reference
            '"cmta"': utf8_body # Comment data
            '"CprC"': u4_body   # Essential Graphics controller property count
            '"CsCt"': u4_body   # Essential Graphics localized string count
            '"CTyp"': u4_body   # Essential Graphics controller type
            '"dwga"': dwga_body # Working gamma setting
            '"EfDC"': efdc_body # Effect definition count
            '"ewot"': ewot_body # Effect workspace outline entries
            '"fcid"': fcid_body # Active composition item ID
            '"fdta"': fdta_body # Folder data
            '"fiac"': fiac_body # Viewer inner tab active flag
            '"fiop"': fiop_body # Viewer panel open flag
            '"fips"': fips_body # Folder item panel settings (per-view options)
            '"fitt"': fitt_body # Viewer inner tab type label
            '"fovi"': fovi_body # Viewer item index (maps viewer to item)
            '"fivc"': fivc_body # Viewer locked view count
            '"fivi"': fivi_body # Per-view sequential identity
            '"fnam"': chunks # Effect name. Contains a single utf-8 chunk but no list_type
            '"foac"': foac_body # Viewer outer tab active flag
            '"fott"': fitt_body # Viewer secondary panel type (always 'AE Timeline')
            '"head"': head_body # Contains AE version and file revision
            '"apid"': apid_body # Footage media color space ICC Profile ID
            '"idta"': idta_body # Item data
            '"ipws"': ipws_body # Footage interpret as project working space flag
            '"ldat"': ldat_body(_parent.as<list_body>.chunks[0].body.as<lhd3_body>.item_type, _parent.as<list_body>.chunks[0].body.as<lhd3_body>.item_size, _parent.as<list_body>.chunks[0].body.as<lhd3_body>.count) # Data of a keyframe
            '"ldta"': ldta_body # Layer data
            '"lhd3"': lhd3_body # Number of keyframes and keyframe size for a property
            '"linl"': linl_body # Footage interpret as linear light setting
            '"lnrb"': lnrb_body # Linear blending flag
            '"lnrp"': lnrp_body # Linearize working space flag
            '"LIST"': list_body # List of chunks
            '"RIFX"': list_body # RIFF big-endian container (root)
            '"mkif"': mkif_body # Mask info
            '"NmHd"': nmhd_body # Marker data
            '"nnhd"': nnhd_body # Project data
            '"opti"': opti_body # Footage data
            '"otda"': cdat_body(false) # Orientation keyframe value(s) (3 doubles)
            '"otln"': otln_body # Comp panel outline entries (selection + collapsed state)
            '"pard"': pard_body # Property default values and ranges
            '"parn"': parn_body # Parameter count in a parT list
            '"prgb"': prgb_body # Footage preserve RGB flag
            '"pdnm"': chunks # Parameter control strings. Contains a single utf-8 chunk but no list_type
            '"pjef"': utf8_body # Effect names
            '"prin"': prin_body # Composition renderer info (inside LIST:PRin)
            '"RCom"': chunks # Render queue item comment. Contains a single utf-8 chunk
            '"Roou"': roou_body # Output module settings
            '"Ropt"': ropt_body # Format-specific render options
            '"Rout"': rout_body # Render queue item flags
            '"fth5"': fth5_body # Variable-width mask feather points
            '"shph"': shph_body # Shape path header (bounding box + closed flag)
            '"Smax"': f8_body   # Essential Graphics controller maximum value
            '"Smin"': f8_body   # Essential Graphics controller minimum value
            '"sspc"': sspc_body # Footage data
            '"StVS"': u4_body   # Essential Graphics dropdown option count
            '"tdb4"': tdb4_body # Property metadata
            '"tdli"': s4_body   # Mask index for MASK control property (1-based)
            '"tdmn"': utf8_body # Property or parameter name
            '"tdum"': tdum_body(_parent.as<list_body>.chunks[2].body.as<tdb4_body>.color, _parent.as<list_body>.chunks[2].body.as<tdb4_body>.integer) # Property minimum value
            '"tduM"': tdum_body(_parent.as<list_body>.chunks[2].body.as<tdb4_body>.color, _parent.as<list_body>.chunks[2].body.as<tdb4_body>.integer) # Property maximum value
            '"tdpi"': s4_body   # Layer ID for LAYER control property (references ldta.layer_id)
            '"tdps"': s4_body   # Secondary layer selector (always 0 in known samples)
            '"tdsb"': tdsb_body # Transform property group flags
            '"tdsn"': chunks # User-defined name of a property. Contains a single utf-8 chunk but no list_type
            '"Utf8"': utf8_body # Contains text
            _: ascii_body
      - id: pad_byte
        size: 1
        if: (len_body % 2) != 0
  ewot_body:
    doc: |
      Effect workspace outline entries inside LIST Ewst.
      Each entry is 4 bytes. The first byte contains flags:
        - bit 7 (0x80): child property of an effect (not an effect group)
        - bit 6 (0x40): selected
      Entries without bit 7 are effect-group-level nodes.
    seq:
      - id: num_entries
        type: u4
        doc: Number of entries
      - id: entries
        type: ewot_entry
        repeat: expr
        repeat-expr: num_entries
        doc: Array of outline entries
  ewot_entry:
    doc: Single effect workspace outline entry.
    seq:
      - id: is_child_property
        type: b1
        doc: When true, this is a child property, not an effect group (bit 7 of flags byte)
      - id: selected
        type: b1
        doc: When true, this entry is selected (bit 6 of flags byte)
      - id: reserved_flags
        type: b6
        doc: Remaining flag bits
      - id: data
        size: 3
        doc: Remaining entry bytes
  otln_body:
    doc: |
      Comp panel outline entries inside LIST FEE (composition timeline).
      Each entry is 4 bytes. The first byte contains flags:
        - bit 7 (0x80): collapsed in the timeline
        - bit 6 (0x40): selected
      Entries correspond 1:1 to layers and their property-tree nodes
      in DFS order across all visible layers of the active composition.
    seq:
      - id: num_entries
        type: u4
        doc: Number of entries
      - id: entries
        type: otln_entry
        repeat: expr
        repeat-expr: num_entries
        doc: Array of outline entries
  otln_entry:
    doc: Single comp panel outline entry.
    seq:
      - id: collapsed
        type: b1
        doc: When true, this node is collapsed in the comp timeline (bit 7 of flags byte)
      - id: selected
        type: b1
        doc: When true, this entry is selected (bit 6 of flags byte)
      - id: is_property
        type: b1
        doc: When true, this entry represents a property (bit 5 of flags byte)
      - type: b1
      - id: is_sub_entry
        type: b1
        doc: When true, this entry is a sub-entry / leaf (bit 3 of flags byte)
      - type: b3
      - size: 2
      - id: entry_type
        type: u1
        doc: |
          Entry type byte. The value 0x44 marks a per-layer boundary
          marker - exactly one appears per layer in the otln block.
          Normal entries have 0x11.
    instances:
      is_layer_marker:
        value: 'entry_type == 0x44'
        doc: When true, this entry is a per-layer boundary marker.
  efdc_body:
    doc: |
      Effect definition count. The first byte contains the number of
      LIST EfDf definitions inside LIST EfdG.
    seq:
      - id: count
        type: u1
        doc: Number of effect definitions
  parn_body:
    doc: |
      Parameter count inside a LIST parT. Contains the number of tdmn/pard
      parameter entries that follow.
    seq:
      - id: count
        type: u4
        doc: Number of parameters
  acer_body:
    doc: |
      Compensate for Scene-Referred Profiles setting in Project Settings.
      This setting affects how scene-referred color profiles are handled.
    seq:
      - id: compensate_for_scene_referred_profiles
        type: u1
        doc: Whether to compensate for scene-referred profiles (0=false, 1=true)
  adfr_body:
    seq:
      - id: audio_sample_rate
        type: f8
        doc: Project audio sample rate in Hz (e.g. 22050.0, 44100.0, 48000.0, 96000.0)
  dwga_body:
    doc: |
      Working gamma setting. Indicates the gamma value used for color management.
    seq:
      - id: working_gamma_selector
        type: u1
        doc: Working gamma selector (0=2.2, 1=2.4)
      - size: 3
        doc: Unknown bytes 1-3
    instances:
      working_gamma:
        value: 'working_gamma_selector != 0 ? 2.4 : 2.2'
        doc: Working gamma value (2.2 or 2.4)
  apid_body:
    doc: |
      Media color space ICC Profile ID.
      Inside LIST:CLRS in a footage item's LIST:Pin.
      A 16-byte ICC Profile ID identifying the color space to assign
      to the footage. All 0xFF bytes means "Embedded" (use the
      media's native profile).
    seq:
      - id: profile_id
        size: 16
        doc: 16-byte ICC Profile ID (all 0xFF = embedded)
  ascii_body:
    seq:
      - id: contents
        size-eos: true
  cdat_body:
    doc: |
      Property value chunk storing one or more doubles.
      When is_le is true (OTST orientation), values are little-endian.
    params:
      - id: is_le
        type: bool
    seq:
      - id: value_be
        type: f8
        repeat: expr
        repeat-expr: '_parent.len_body / 8'
        if: 'not is_le'
      - id: value_le
        type: f8le
        repeat: expr
        repeat-expr: '_parent.len_body / 8'
        if: is_le
    instances:
      value:
        value: 'is_le ? value_le : value_be'
  cdrp_body:
    doc: |
      Composition drop frame setting.
      When true, the composition uses drop-frame timecode.
    seq:
      - id: drop_frame
        type: u1
        doc: Whether the composition uses drop-frame timecode (0=false, 1=true)
  fips_body:
    doc: |
      Folder item panel settings. Stores viewer panel state including
      Draft 3D mode, view options (channels, exposure, zoom, etc.), and
      toggle flags (guides, rulers, grid, etc.). There are typically 4
      fips chunks per viewer group, one for each AE composition viewer
      panel. Total size is 96 bytes.
    seq:
      - size: 7
        doc: Unknown bytes 0-6
      - id: channels
        type: u1
        doc: |
          Channel display mode. 0=RGB, 1=Red, 2=Green, 3=Blue,
          4=Alpha, 8=RGB Straight.
      - size: 3
        doc: Unknown bytes 8-10
      - type: b6  # skip bits 7-2
      - id: proportional_grid
        type: b1  # bit 1 (value 0x02)
        doc: Whether the proportional grid overlay is displayed
      - id: title_action_safe
        type: b1  # bit 0 (value 0x01)
        doc: Whether title/action safe guides are displayed
      - type: b5  # skip bits 7-3
      - id: draft3d
        type: b1  # bit 2 (value 0x04)
        doc: Whether Draft 3D mode is enabled for this viewer panel
      - type: b2  # skip bits 1-0
      - type: b3  # skip bits 7-5
      - id: fast_preview_draft
        type: b1  # bit 4 (value 0x10)
        doc: Whether draft fast preview mode is enabled (ray-traced 3D only)
      - type: b1  # skip bit 3
      - id: fast_preview_fast_draft
        type: b1  # bit 2 (value 0x04)
        doc: Whether fast draft fast preview mode is enabled (ray-traced 3D only)
      - type: b1  # skip bit 1
      - id: fast_preview_adaptive
        type: b1  # bit 0 (value 0x01)
        doc: Whether adaptive resolution fast preview is enabled
      - id: region_of_interest
        type: b1  # bit 7 (value 0x80)
        doc: Whether the region of interest selection is active
      - id: rulers
        type: b1  # bit 6 (value 0x40)
        doc: Whether rulers are displayed
      - type: b1  # skip bit 5
      - id: fast_preview_wireframe
        type: b1  # bit 4 (value 0x10)
        doc: Whether wireframe fast preview mode is enabled
      - type: b4  # skip bits 3-0
      - id: checkerboards
        type: b1  # bit 7 (value 0x80)
        doc: Whether the transparency checkerboard is displayed
      - type: b2  # skip bits 6-5
      - id: mask_and_shape_path
        type: b1  # bit 4 (value 0x10)
        doc: Whether mask and shape paths are visible
      - type: b4  # skip bits 3-0
      - size: 7
        doc: Unknown bytes 16-22
      - type: b4  # skip bits 7-4
      - id: grid
        type: b1  # bit 3 (value 0x08)
        doc: Whether the grid overlay is displayed
      - id: guides_snap
        type: b1  # bit 2 (value 0x04)
        doc: Whether layers snap to guides when dragged in the view
      - id: guides_locked
        type: b1  # bit 1 (value 0x02)
        doc: Whether guides are locked in the view
      - id: guides_visibility
        type: b1  # bit 0 (value 0x01)
        doc: Whether guides are visible
      - size: 16
        doc: Unknown bytes 24-39
      - id: roi_top
        type: u2
        doc: Region of interest top coordinate (pixels from top)
      - id: roi_left
        type: u2
        doc: Region of interest left coordinate (pixels from left)
      - id: roi_bottom
        type: u2
        doc: Region of interest bottom coordinate (pixels from top)
      - id: roi_right
        type: u2
        doc: Region of interest right coordinate (pixels from left)
      - size: 21
        doc: Unknown bytes 48-68
      - id: zoom_type
        type: u1
        doc: |
          Zoom mode. 0=custom manual zoom, 1=fit, 2=fit up to 100%.
      - size: 2
        doc: Unknown bytes 70-71
      - id: zoom
        type: f8
        doc: |
          Zoom factor where 1.0 = 100%. E.g. 0.25 = 25%,
          16.0 = 1600%.
      - id: exposure
        type: f4
        doc: |
          Exposure value in stops. 0.0 = no adjustment.
          Range is -40.0 to 40.0.
      # Byte 84: unknown
      - size: 1
        doc: Unknown byte 84
      # Byte 85: use_display_color_management flag
      - type: b7  # skip bits 7-1
      - id: use_display_color_management
        type: b1  # bit 0 (value 0x01)
        doc: Whether display color management is enabled
      # Byte 86: auto_resolution flag
      - type: b7  # skip bits 7-1
      - id: auto_resolution
        type: b1  # bit 0 (value 0x01)
        doc: Whether auto resolution is enabled for the viewer
      - size-eos: true
    instances:
      fast_preview_type:
        value: 'fast_preview_wireframe ? 4 : (fast_preview_fast_draft ? 3 : (fast_preview_draft ? 2 : (fast_preview_adaptive ? 1 : 0)))'
        enum: fast_preview_type
        doc: |
          Computed fast preview type from individual binary flags.
          0=off, 1=adaptive_resolution, 2=draft, 3=fast_draft, 4=wireframe.
  foac_body:
    doc: |
      Viewer outer tab active flag. Not a focus indicator - does not
      change when clicking different panels.
    seq:
      - id: active
        type: u1
        doc: Whether the outer tab is active (0=false, 1=true)
  fiac_body:
    doc: |
      Viewer inner tab active flag. Not a focus indicator - does not
      change when clicking different panels.
    seq:
      - id: active
        type: u1
        doc: Whether the inner tab is active (0=false, 1=true)
  fiop_body:
    doc: |
      Viewer panel open flag. When 1, the panel is open and visible.
      Blocks without fitt are ghost/closed entries.
    seq:
      - id: open
        type: u1
        doc: Whether the panel is open (0=closed, 1=open)
  fitt_body:
    doc: |
      Viewer inner tab type label. An ASCII string identifying the
      viewer type (e.g. "AE Composition", "AE Layer", "AE Footage").
    seq:
      - id: label
        type: str
        encoding: ASCII
        size-eos: true
        doc: The inner tab type label
  fovi_body:
    doc: |
      Viewer item index. A zero-based positional index into the LIST:Item
      children at the same folder level, mapping this viewer to its
      associated composition or footage item.
    seq:
      - id: item_index
        type: u4
        doc: Zero-based index of the item in the parent folder
  fivi_body:
    doc: |
      Per-view sequential identity. One fivi chunk per locked view
      (as counted by fivc). Not an active view indicator.
    seq:
      - id: identity
        type: u4
        doc: Sequential view identity counter
  fivc_body:
    doc: |
      Locked view count. Counts views created via "View > Split with
      New Locked View" (1=single, 2=split). Does NOT count 3D
      viewports - the 3D viewport layout is stored inside fips.
    seq:
      - id: view_count
        type: u2
        doc: Number of locked views
  s4_body:
    doc: Single signed 32-bit integer value.
    seq:
      - id: value
        type: s4
  u4_body:
    doc: Single unsigned 32-bit integer value.
    seq:
      - id: value
        type: u4
  f8_body:
    doc: Single 64-bit floating-point value.
    seq:
      - id: value
        type: f8
  fcid_body:
    doc: |
      Active composition item ID. Stores the item ID of the currently
      active (most recently focused) composition in the project.
    seq:
      - id: active_item_id
        type: u4
        doc: The item ID of the active composition
  cdta_body:
    seq:
      - id: resolution_factor
        type: u2
        repeat: expr
        repeat-expr: 2
      - size: 1
        doc: Reserved, always 0.
      - id: time_scale_integer
        type: u2
        doc: |
          Integer part of the time scale. For non-integer frame rates
          (e.g. 29.97fps), the actual time scale is a fractional number
          encoded as time_scale_integer + time_scale_fractional / 256.
      - id: time_scale_fractional
        type: u1
        doc: |
          Fractional part of the time scale (1/256th units). Zero for
          integer frame rates, non-zero for NTSC-style frame rates like
          29.97fps. The effective time scale is
          time_scale_integer + time_scale_fractional / 256.
      - id: internal_timebase
        type: u4
        doc: |
          Internal timebase derived from frame rate and time scale
          (frame_rate * 256 * time_scale). E.g. 24576 for 24fps/ts=4,
          30720 for 30fps/ts=4 or 60fps/ts=2, 23976 for 29.97fps.
      - size: 4
        doc: Reserved. Usually 0, rarely 650 in some production files.
      - id: standard_timebase
        type: u4
        doc: Standard After Effects timebase. Always 600.
      - id: time_dividend
        type: s4
      - id: time_divisor
        type: u4
      - id: work_area_start_dividend
        type: u4
      - id: work_area_start_divisor
        type: u4
      - id: work_area_end_dividend
        type: u4
      - id: work_area_end_divisor
        type: u4
      - id: duration_dividend
        type: u4
      - id: duration_divisor
        type: u4
      - id: bg_color
        type: u1
        repeat: expr
        repeat-expr: 3
      - size: 83
        doc: Reserved, always zeros.
      - id: draft3d
        type: b1  # bit 7
        doc: Whether Draft 3D is enabled for this composition. Deprecated.
      - type: b7  # skip bits 6-0
      - id: preserve_nested_resolution
        type: b1  # bit 7
      - type: b1  # skip bit 6
      - id: preserve_nested_frame_rate
        type: b1  # bit 5
      - id: frame_blending
        type: b1  # bit 4
      - id: motion_blur
        type: b1  # bit 3
      - type: b2  # skip bits 2-1
      - id: hide_shy_layers
        type: b1  # bit 0
      - id: width
        type: u2
      - id: height
        type: u2
      - id: pixel_ratio_dividend
        type: u4
      - id: pixel_ratio_divisor
        type: u4
      - size: 4
        doc: Reserved, always 0.
      - id: frame_rate_integer
        type: u2
      - id: frame_rate_fractional
        type: u2
      - size: 4
        doc: Reserved, always 0.
      - id: display_start_time_dividend
        type: s4
        doc: |
          Signed 32-bit dividend for display start time. Negative values
          represent compositions whose timeline starts before frame 0.
      - id: display_start_time_divisor
        type: u4
      - size: 2
        doc: Reserved, always 0.
      - id: shutter_angle
        type: u2
      - size: 4
        doc: Reserved, always 360.
      - id: shutter_phase
        type: s4
      - size: 4
        doc: Reserved, always 360.
      - size: 8
        doc: Reserved, always 0.
      - id: motion_blur_adaptive_sample_limit
        type: s4
      - id: motion_blur_samples_per_frame
        type: s4
    instances:
      time_scale:
        value: 'time_scale_integer + time_scale_fractional * 1.0 / 256'
        doc: |
          Effective time scale combining integer and fractional parts.
          Used as divisor for keyframe time_raw to compute frame numbers.
      display_start_time:
        value: 'display_start_time_dividend * 1.0 / display_start_time_divisor'
      frame_rate:
        value: 'frame_rate_integer + (frame_rate_fractional * 1.0 / 65536)'
      display_start_frame:
        value: 'display_start_time * frame_rate'
      duration:
        value: 'duration_dividend * 1.0 / duration_divisor'
      frame_duration:
        value: 'duration * frame_rate'
      pixel_aspect:
        value: 'pixel_ratio_dividend * 1.0 / pixel_ratio_divisor'
      time:
        value: 'time_dividend * 1.0 / time_divisor'
      frame_time:
        value: 'time * frame_rate'
      work_area_start_absolute:
        value: 'display_start_time + work_area_start_dividend * 1.0 / work_area_start_divisor'
        doc: Absolute work area start in composition time (seconds). Internal.
      frame_work_area_start_absolute:
        value: '(display_start_time + work_area_start_dividend * 1.0 / work_area_start_divisor) * frame_rate'
        doc: Absolute work area start in composition time (frames). Internal.
      work_area_end_absolute:
        value: '(work_area_end_dividend == 0xffffffff ? display_start_time + duration : display_start_time + work_area_end_dividend * 1.0 / work_area_end_divisor)'
        doc: Absolute work area end in composition time (seconds). Internal.
      frame_work_area_end_absolute:
        value: '(work_area_end_dividend == 0xffffffff ? display_start_frame + frame_duration : (display_start_time + work_area_end_dividend * 1.0 / work_area_end_divisor) * frame_rate)'
        doc: Absolute work area end in composition time (frames). Internal.
      work_area_start_relative:
        value: 'work_area_start_absolute - display_start_time'
        doc: Work area start relative to composition start (seconds)
      frame_work_area_start_relative:
        value: 'frame_work_area_start_absolute - display_start_frame'
        doc: Work area start relative to composition start (frames)
      work_area_duration:
        value: 'work_area_end_absolute - work_area_start_absolute'
        doc: Work area duration (seconds)
      frame_work_area_duration:
        value: 'frame_work_area_end_absolute - frame_work_area_start_absolute'
        doc: Work area duration (frames)

  fdta_body:
    seq:
      - size: 1
      - size-eos: true
  head_body:
    doc: |
      After Effects file header. Contains version info encoded as a 32-bit value.
      Major version = MAJOR-A * 8 + MAJOR-B
      See: https://github.com/tinogithub/aftereffects-version-check
    seq:
      - size: 4
        doc: Reserved/unknown bytes before version
      # Version bits (32 bits total, MSB first)
      - type: b1
        doc: Bit 31 - reserved
      - id: ae_version_major_a
        type: b5
        doc: Bits 30-26 - high bits of major version
      - id: ae_version_os
        type: b4
        doc: Bits 25-22 - OS code (12=Windows, 13=Mac, 14=Mac ARM64)
      - id: ae_version_major_b
        type: b3
        doc: Bits 21-19 - low bits of major version
      - id: ae_version_minor
        type: b4
        doc: Bits 18-15 - minor version number
      - id: ae_version_patch
        type: b4
        doc: Bits 14-11 - patch version number
      - type: b1
        doc: Bit 10 - reserved
      - id: ae_version_beta_flag
        type: b1
        doc: Bit 9 - beta flag (false=beta, true=release)
      - type: b1
        doc: Bit 8 - reserved
      - id: ae_build_number
        type: b8
        doc: Bits 7-0 - build number
      - size: 10
        doc: Padding before file_revision
      - id: file_revision
        type: u2
    instances:
      ae_version_major:
        value: ae_version_major_a * 8 + ae_version_major_b
        doc: Full major version number (e.g., 25)
      ae_version_beta:
        value: not ae_version_beta_flag
        doc: True if beta version
      version:
        value: f"{ae_version_major}.{ae_version_minor}x{ae_build_number}"
  idta_body:
    seq:
      - id: item_type
        type: u2
        enum: item_type
      - size: 14
        doc: Reserved, always zeros.
      - id: item_id
        type: u4
      - size: 4
        doc: |
          Item flags that vary by item_type. Known values: type 1
          (folder) = 0 or 1, type 4 (comp) = 32 or 544, type 7
          (footage) = 0, 4, 32, 36, or 48.
      - size: 34
        doc: Reserved, mostly zeros (rarely non-zero in some files).
      - id: label
        type: u1
        enum: label
      - size-eos: true
  ldat_body:
    doc: |
      Keyframe / shape / settings data items. Typed via params from sibling lhd3.
      Automatically promotes three_d to three_d_spatial when the parent tdbs
      context indicates the property is spatial (tdb4.is_spatial).
    params:
      - id: item_type
        type: u1
        enum: ldat_item_type
      - id: item_size
        type: u2
      - id: count
        type: u2
    instances:
      is_spatial:
        value: >-
          _parent.as<chunk>._parent.as<list_body>._parent.as<chunk>._parent.as<list_body>.list_type == "tdbs"
          and _parent.as<chunk>._parent.as<list_body>._parent.as<chunk>._parent.as<list_body>.chunks[2].body.as<tdb4_body>.is_spatial
        doc: Whether the parent property is spatial (from tdb4 in the grandparent LIST:tdbs).
      effective_item_type:
        value: >-
          item_type == ldat_item_type::three_d and is_spatial
          ? ldat_item_type::three_d_spatial
          : item_type
        doc: |
          Promotes three_d to three_d_spatial for spatial properties.
          Both have item_size=128 but different binary layouts (kf_multi_dimensional vs kf_position).
    seq:
      - id: items
        type:
          switch-on: effective_item_type
          cases:
            'ldat_item_type::lrdr': render_settings_ldat_body
            'ldat_item_type::litm': output_module_settings_ldat_body
            'ldat_item_type::shape': shape_point
            'ldat_item_type::gide': guide_item
            _: ldat_item(effective_item_type)
        size: item_size
        repeat: expr
        repeat-expr: count
  roou_body:
    doc: Output module settings (154 bytes)
    seq:
      - id: magic
        size: 4
        doc: Magic bytes, typically "FXTC"
      - id: video_codec
        type: str
        size: 4
        encoding: ASCII
        doc: Video codec 4-char code
      - size: 8
        doc: Unknown bytes 8-15
      - id: starting_number
        type: u4
        doc: Starting frame number for image sequence output (bytes 16-19)
      - size: 6
        doc: Unknown bytes 20-25
      - id: format_id
        type: str
        size: 4
        encoding: ASCII
        doc: |
          Output format 4-char identifier (e.g. ".AVI", "H264", "TIF ", "8BPS",
          "png!", "JPEG", "MooV", "oEXR", "AIFF", "wao_", "Mp3 ", "sDPX",
          "SGI ", "IFF ", "TPIC", "RHDR")
      - size: 2
        doc: Unknown bytes 30-31
      - size: 4
        doc: Unknown bytes 32-35
      - id: width
        type: u2
        doc: Output width in pixels (0 when video disabled)
      - size: 2
        doc: Unknown bytes 38-39
      - id: height
        type: u2
        doc: Output height in pixels (0 when video disabled)
      - size: 25
        doc: Unknown bytes 42-66
      - id: frame_rate
        type: u1
        doc: Frame rate in fps
      - size: 3
        doc: Unknown bytes 68-70
      - id: depth
        type: u1
        doc: Color depth in bits per pixel (24=Millions/8bpc, 48=Trillions/16bpc, 96=Floating/32bpc)
      - size: 5
        doc: Unknown bytes 72-76
      - id: color_premultiplied
        type: u1
        doc: Color premultiplied flag (0=no, 1=yes)
      - size: 3
        doc: Unknown bytes 78-80
      - id: color_matted
        type: u1
        doc: Color matted flag (0=no, 1=yes)
      - size: 18
        doc: Unknown bytes 82-99
      - id: audio_sample_rate
        type: f8
        doc: Audio sample rate in Hz (e.g. 8000, 22050, 44100, 48000, 96000)
      - id: audio_disabled_hi
        type: u1
        doc: High byte of audio disabled flag (0xFF when disabled)
      - id: audio_format
        type: u1
        doc: Audio format/depth indicator (2=16-bit, 3=24-bit, 4=32-bit)
      - size: 1
        doc: Unknown byte 110
      - id: audio_bit_depth
        type: u1
        doc: Audio bit depth indicator (1=8-bit, 2=16-bit, 4=32-bit)
      - size: 1
        doc: Unknown byte 112
      - id: audio_channels
        type: u1
        doc: Audio channels (1=mono, 2=stereo)
      - size-eos: true
  ropt_body:
    doc: |
      Format-specific render options for the output module.
      The first 4 bytes identify the format, followed by format-specific data.
      These settings complement the main output module settings in roou_body.
    seq:
      - id: format_code
        type: str
        size: 4
        encoding: ASCII
        doc: |
          Output format 4-char identifier matching roou_body.format_id
          (e.g. ".AVI", "sDPX", "png!", "JPEG")
      - id: body
        type:
          switch-on: format_code
          cases:
            '"sDPX"': cineon_ropt_data
            '"JPEG"': jpeg_ropt_data
            '"oEXR"': openexr_ropt_data
            '"TPIC"': targa_ropt_data
            '"TIF "': tiff_ropt_data
            '"png!"': png_ropt_data
            _: ropt_generic_data
  cineon_ropt_data:
    doc: |
      Cineon/DPX format-specific render options (44 bytes after format code).
      These correspond to the Cineon Settings dialog in After Effects.
    seq:
      - size: 6
        doc: Unknown bytes (offsets 4-9)
      - size: 4
        doc: Unknown bytes (offsets 10-13)
      - id: ten_bit_black_point
        type: u2
        doc: 10-bit black point value (0-1023)
      - id: ten_bit_white_point
        type: u2
        doc: 10-bit white point value (0-1023)
      - id: converted_black_point
        type: f8
        doc: Converted black point value, normalized to 0.0-1.0 range
      - id: converted_white_point
        type: f8
        doc: Converted white point value, normalized to 0.0-1.0 range
      - id: current_gamma
        type: f8
        doc: Current gamma value
      - id: highlight_expansion
        type: u2
        doc: Highlight expansion value
      - id: logarithmic_conversion
        type: u1
        doc: Logarithmic conversion flag (0=off, 1=on)
      - id: file_format
        type: u1
        doc: File format (0=FIDO/Cineon 4.5, 1=DPX)
      - id: bit_depth
        type: u1
        doc: Bit depth (8, 10, 12, or 16)
      - size-eos: true
  targa_ropt_data:
    doc: |
      Targa (TGA) format-specific render options.
      These correspond to the Targa Options dialog in After Effects.
    seq:
      - size: 73
        doc: Unknown header bytes (offsets 0-72)
      - id: bits_per_pixel
        type: u1
        doc: |
          Color depth in bits per pixel.
          24 = 24 bits/pixel (no alpha), 32 = 32 bits/pixel (with alpha).
      - size: 4
        doc: "'TimS' marker string (offsets 74-77)"
      - id: rle_compression
        type: u1
        doc: RLE compression flag (0=off, 1=on)
      - size-eos: true
  tiff_ropt_data:
    doc: |
      TIFF format-specific render options.
      These correspond to the TIFF Options dialog in After Effects.
    seq:
      - size: 596
        doc: Unknown header bytes (offsets 0-595)
      - id: ibm_pc_byte_order
        type: u1
        doc: IBM PC byte order flag (0=Macintosh/big-endian, 1=IBM PC/little-endian)
      - id: lzw_compression
        type: u1
        doc: LZW compression flag (0=off, 1=on)
  openexr_ropt_data:
    doc: |
      OpenEXR format-specific render options.
      These correspond to the OpenEXR Options dialog in After Effects.
    seq:
      - size: 8
        doc: Unknown header bytes (offsets 0-7)
      - size: 2
        doc: Unknown bytes (offsets 8-9, always 0)
      - id: compression
        type: u1
        doc: |
          Compression method: 0=None, 1=RLE, 2=Zip, 3=Zip16, 4=Piz,
          5=PXR24, 6=B44, 7=B44A, 8=DWAA, 9=DWAB.
      - id: thirty_two_bit_float
        type: u1
        doc: 32-bit float output flag (0=off, 1=on)
      - id: luminance_chroma
        type: u1
        doc: Luminance/Chroma encoding flag (0=off, 1=on)
      - size: 1
        doc: Padding byte (always 0)
      - id: dwa_compression_level
        type: f4le
        doc: |
          DWA compression level (little-endian float32, default 45.0).
          Only meaningful when compression is DWAA or DWAB.
          Stored as little-endian despite the RIFX big-endian container,
          matching OpenEXR's native byte order.
      - size-eos: true
  png_ropt_data:
    doc: |
      PNG format-specific render options.
      Contains width, height, and bit depth at known offsets.
    seq:
      - size: 14
        doc: Unknown header bytes (offsets 0-13)
      - id: width
        type: u4
        doc: Output width in pixels
      - id: height
        type: u4
        doc: Output height in pixels
      - size: 2
        doc: Unknown bytes (offsets 22-23)
      - id: bit_depth
        type: u2
        doc: Bit depth per channel (8 or 16)
      - id: compression
        type: u4
        doc: |
          Compression / interlace mode: 0 = None, 1 = Interlaced (Adam7).
          Corresponds to the Compression dropdown in the PNG Options dialog.
      - size-eos: true
  jpeg_ropt_data:
    doc: |
      JPEG format-specific render options (54 bytes after format code).
      The first 48 bytes are a static header/magic block. The last 6 bytes
      hold quality, format type, and scans as u16 values.
    seq:
      - size: 48
        doc: Static header block (includes 'JP64' magic at offset 26)
      - id: quality
        type: u2
        doc: JPEG quality level (0-10)
      - id: format_type
        type: u2
        doc: |
          JPEG format option type:
          0 = Baseline (Standard), 1 = Baseline Optimized, 2 = Progressive.
      - id: scans
        type: u2
        doc: |
          Scans index for Progressive format (1=3 scans, 2=4 scans, 3=5 scans).
          Always 1 for non-Progressive formats.
  ropt_generic_data:
    doc: Generic render options data for formats without specific parsing.
    seq:
      - id: raw
        size-eos: true
  rout_body:
    doc: Render queue item flags (4-byte header + 4 bytes per item)
    seq:
      - size: 4
        doc: Header bytes
      - id: items
        type: rout_item
        repeat: eos
  rout_item:
    doc: Per-item render queue flags (4 bytes)
    seq:
      - type: b1  # skip bit 7
      - id: render
        type: b1  # bit 6
        doc: True when item is set to render when queue is started
      - type: b6  # skip bits 5-0
      - size: 3
        doc: Remaining bytes
  output_module_settings_ldat_body:
    doc: |
      Per-output-module settings chunk (128 bytes).
      Used under LIST:list within LIST:LItm for each render queue item.
      Note: The actual comp_id is stored in render_settings_ldat_body, not here.
    seq:
      - size: 7
        doc: Unknown bytes 0-6
      - id: preserve_rgb
        type: b1
        doc: Preserve RGB channels when exporting (bit 7)
      - id: include_source_xmp
        type: b1
        doc: Include source XMP metadata in output (bit 6)
      - type: b1
        doc: Unknown bit 5
      - id: use_region_of_interest
        type: b1
        doc: Use Region of Interest checkbox (bit 4)
      - id: use_comp_frame_number
        type: b1
        doc: Use Comp Frame Number checkbox (bit 3)
      - type: b3
        doc: Unknown bits 2-0
      - id: post_render_target_comp_id
        type: u4
        doc: |
          Composition ID for post-render action target.
          Only used when post_render_use_comp is 1 (use custom comp).
          When 0, uses the render queue item's comp.
      - size: 4
        doc: Unknown bytes 12-15
      - size: 3
        doc: Unknown bytes 16-18
      - id: channels
        type: u1
        doc: Output channels (0=RGB, 1=RGBA, 2=Alpha)
      - size: 3
        doc: Unknown bytes 20-22
      - id: resize_quality
        type: u1
        doc: Resize quality (byte 23, 0=low, 1=high)
      - size: 3
        doc: Unknown bytes 24-26
      - id: resize
        type: u1
        doc: Resize checkbox (byte 27, 0=off, 1=on)
      - size: 1
        doc: Unknown byte 28
      - id: lock_aspect_ratio
        type: u1
        doc: Lock Aspect Ratio checkbox (byte 29, 0=off, 1=on)
      - size: 1
        doc: Unknown byte 30
      - type: b7
        doc: Unknown bits 7-1 of byte 31
      - id: crop
        type: b1
        doc: Crop checkbox enabled (bit 0 of byte 31)
      - id: crop_top
        type: u2
        doc: Crop top value in pixels (bytes 32-33)
      - id: crop_left
        type: u2
        doc: Crop left value in pixels (bytes 34-35)
      - id: crop_bottom
        type: u2
        doc: Crop bottom value in pixels (bytes 36-37)
      - id: crop_right
        type: u2
        doc: Crop right value in pixels (bytes 38-39)
      - size: 2
        doc: Unknown bytes 40-41
      - id: output_audio
        type: u1
        doc: Output audio mode (byte 42, 0=on, 1=auto)
      - size: 4
        doc: Unknown bytes 43-46
      - id: include_project_link
        type: u1
        doc: Include project link in output (byte 47, 0=off, 1=on)
      - id: post_render_action
        type: u4
        doc: Post-render action (0=NONE, 1=IMPORT, 2=IMPORT_AND_REPLACE, 3=SET_PROXY)
      - id: post_render_use_comp
        type: u4
        doc: Post-render action target comp (0=use render queue item comp, 1=use custom comp)
      - size: 16
        doc: Unknown bytes 56-71
      - id: output_profile_id
        size: 16
        doc: Output profile ID (16-byte binary identifier)
      - size: 3
        doc: Unknown bytes 88-90
      - id: convert_to_linear_light
        type: u1
        doc: Convert to Linear Light setting (byte 91, 0=off, 1=on, 2=on for 32 bpc)
      - size: 1
        doc: Unknown byte 92
      - id: output_color_space_working
        type: u1
        doc: 1 if "Output Color Space" is set to "Working Color Space"
      - size: 34
        doc: Remaining unknown bytes (94-127)
  render_settings_ldat_body:
    doc: Render settings ldat chunk (2246 bytes)
    seq:
      - size: 7
        doc: Unknown bytes 0-6
      - type: b5
        doc: Unknown bits 7-3
      - id: queue_item_notify
        type: b1
        doc: Queue item notify flag (bit 2)
      - type: b2
        doc: Unknown bits 1-0
      - id: comp_id
        type: u4
        doc: Composition ID being rendered
      - id: status
        type: u4
        doc: Render queue item status (0=NEEDS_OUTPUT, 1=UNQUEUED, 2=QUEUED, 3=RENDERING, 4=USER_STOPPED, 5=ERR_STOPPED, 6=DONE)
      - size: 4
        doc: Unknown bytes 16-19
      - id: time_span_start_dividend
        type: u4
        doc: Time span start dividend
      - id: time_span_start_divisor
        type: u4
        doc: Time span start divisor
      - id: time_span_duration_dividend
        type: u4
        doc: Time span duration dividend
      - id: time_span_duration_divisor
        type: u4
        doc: Time span duration divisor
      - size: 8
        doc: Unknown bytes 36-43
      - id: frame_rate_integer
        type: u2
        doc: Frame rate integer part in fps
      - id: frame_rate_fractional
        type: u2
        doc: Frame rate fractional part (divide by 65536)
      - size: 2
        doc: Unknown bytes 48-49
      - id: field_render
        type: u2
        doc: Field render setting (0=off, 1=upper first, 2=lower first)
      - size: 2
        doc: Unknown bytes 52-53
      - id: pulldown
        type: u2
        doc: 3:2 Pulldown setting (0=off, 1=WSSWW, 2=SSWWW, 3=SWWWS, 4=WWWSS, 5=WWSSW)
      - id: quality
        type: u2
        doc: Render quality (0=wireframe, 1=draft, 2=best)
      - id: resolution_x
        type: u2
        doc: Resolution factor X
      - id: resolution_y
        type: u2
        doc: Resolution factor Y
      - size: 2
        doc: Unknown bytes 62-63
      - id: effects
        type: u2
        doc: Effects setting (0=all on, 1=all off, 2=current settings)
      - size: 2
        doc: Unknown bytes 66-67
      - id: proxy_use
        type: u2
        doc: Proxy use setting (0=use all proxies, 1=use comp proxies only, 3=use no proxies)
      - size: 2
        doc: Unknown bytes 70-71
      - id: motion_blur
        type: u2
        doc: Motion blur setting (0=current settings, 1=off for all layers, 2=on for checked layers)
      - size: 2
        doc: Unknown bytes 74-75
      - id: frame_blending
        type: u2
        doc: Frame blending setting (0=current settings, 1=off for all layers, 2=on for checked layers)
      - size: 2
        doc: Unknown bytes 78-79
      - id: log_type
        type: u2
        doc: Log type (0=errors only, 1=errors+settings, 2=errors+per frame info)
      - size: 2
        doc: Unknown bytes 82-83
      - id: skip_existing_files
        type: u2
        doc: Skip existing files (0=off, 1=on)
      - size: 4
        doc: Unknown bytes 86-89
      - id: template_name
        size: 64
        type: strz
        encoding: ASCII
        doc: Render settings template name
      - size: 1990
        doc: Unknown bytes 154-2143
      - id: use_this_frame_rate
        type: u2
        doc: Use this frame rate flag (1=use custom frame rate)
      - size: 2
        doc: Unknown bytes 2146-2147
      - id: time_span_source
        type: u2
        doc: Time span source (0=length of comp, 1=work area only, 2=custom)
      - size: 14
        doc: Unknown bytes 2150-2163
      - id: solo_switches
        type: u2
        doc: Solo switches setting (0=current settings, 2=all off)
      - size: 2
        doc: Unknown bytes 2166-2167
      - id: disk_cache
        type: u2
        doc: Disk cache setting (0=read only, 2=current settings)
      - size: 2
        doc: Unknown bytes 2170-2171
      - id: guide_layers
        type: u2
        doc: Guide layers setting (0=current settings, 2=all off)
      - size: 6
        doc: Unknown bytes 2174-2179
      - id: color_depth
        type: u2
        doc: Color depth setting (0xFFFF=current, 0=8bpc, 1=16bpc, 2=32bpc)
      - size: 16
        doc: Unknown bytes 2182-2197
      - id: start_time
        type: u4
        doc: Render start timestamp (seconds since Mac HFS+ epoch Jan 1, 1904)
      - id: elapsed_seconds
        type: u4
        doc: Elapsed render time in seconds
      - size-eos: true
    instances:
      time_span_start:
        value: 'time_span_start_divisor != 0 ? time_span_start_dividend * 1.0 / time_span_start_divisor : 0'
        doc: Time span start in seconds
      time_span_duration:
        value: 'time_span_duration_divisor != 0 ? time_span_duration_dividend * 1.0 / time_span_duration_divisor : 0'
        doc: Time span duration in seconds
      frame_rate:
        value: 'frame_rate_integer + (frame_rate_fractional * 1.0 / 65536)'
        doc: Frame rate in fps (integer + fractional)
  ldat_item:
    params:
      - id: item_type
        type: u1
        enum: ldat_item_type
    seq:
      - size: 1
      - id: time_raw
        type: s2
        doc: |
          Keyframe time in time-scale units. Signed 16-bit; negative values
          occur for keyframes positioned before the layer's start (e.g.
          composition markers).
      - size: 1
      - id: in_interpolation_type
        type: u1
        doc: |
          Incoming interpolation type (binary value).
          Add 6611 to get the ExtendScript enum value:
          1 > LINEAR (6612), 2 > BEZIER (6613), 3 > HOLD (6614).
      - id: out_interpolation_type
        type: u1
        doc: |
          Outgoing interpolation type (binary value).
          Add 6611 to get the ExtendScript enum value:
          1 > LINEAR (6612), 2 > BEZIER (6613), 3 > HOLD (6614).
      - id: label
        type: u1
        enum: label
      - type: b2  # skip first 2 bits
      - id: roving
        type: b1  # bit 5
      - id: temporal_auto_bezier
        type: b1  # bit 4
      - id: temporal_continuous
        type: b1  # bit 3
      - type: b3  # skip remaining 3 bits
      - id: kf_data
        type:
          switch-on: item_type
          cases:
            'ldat_item_type::unknown': kf_unknown_data
            'ldat_item_type::color': kf_color
            'ldat_item_type::three_d_spatial': kf_position(3)
            'ldat_item_type::three_d': kf_multi_dimensional(3)
            'ldat_item_type::two_d_spatial': kf_position(2)
            'ldat_item_type::two_d': kf_multi_dimensional(2)
            'ldat_item_type::orientation': kf_multi_dimensional(1)
            'ldat_item_type::no_value': kf_no_value
            'ldat_item_type::one_d': kf_multi_dimensional(1)
            'ldat_item_type::marker': kf_unknown_data
      - size-eos: true
  kf_unknown_data:
    seq:
      - id: contents
        size-eos: true
  guide_item:
    doc: |
      A single guide item (16 bytes) inside LIST:Gide/LIST:list/ldat.
      Guides are ruler lines used for alignment in compositions.
    seq:
      - id: orientation_type
        type: u4
        doc: |
          Guide orientation in binary form. 1 = vertical, 2 = horizontal.
      - id: position_type
        type: u4
        doc: Guide position type. Always 0 (pixels).
      - id: position
        type: f8
        doc: Guide position in pixels from the top (horizontal) or left (vertical) edge.
  kf_no_value:
    seq:
      - type: u8
      - type: f8
      - id: in_speed
        type: f8
      - id: in_influence
        type: f8
      - id: out_speed
        type: f8
      - id: out_influence
        type: f8
  kf_color:
    seq:
      - type: u8
      - type: f8
      - id: in_speed
        type: f8
      - id: in_influence
        type: f8
      - id: out_speed
        type: f8
      - id: out_influence
        type: f8
      - id: value
        type: f8
        repeat: expr
        repeat-expr: 4
      - type: f8
        repeat: expr
        repeat-expr: 8
  kf_position:
    params:
      - id: num_value
        type: u1
    seq:
      - size: 3
        doc: Unknown bytes (always 0x000000).
      - type: b6
      - id: spatial_auto_bezier
        type: b1
        doc: Spatial auto-Bezier flag.
      - id: spatial_continuous
        type: b1
        doc: Spatial continuity flag.
      - size: 4
        doc: Unknown bytes (always 0x00000000).
      - type: f8
      - id: in_speed
        type: f8
      - id: in_influence
        type: f8
      - id: out_speed
        type: f8
      - id: out_influence
        type: f8
      - id: value
        type: f8
        repeat: expr
        repeat-expr: num_value
      - id: in_spatial_tangents
        type: f8
        repeat: expr
        repeat-expr: num_value
      - id: out_spatial_tangents
        type: f8
        repeat: expr
        repeat-expr: num_value
  kf_multi_dimensional:
    params:
      - id: num_value
        type: u1
    seq:
      - id: value
        type: f8
        repeat: expr
        repeat-expr: num_value
      - id: in_speed
        type: f8
        repeat: expr
        repeat-expr: num_value
      - id: in_influence
        type: f8
        repeat: expr
        repeat-expr: num_value
      - id: out_speed
        type: f8
        repeat: expr
        repeat-expr: num_value
      - id: out_influence
        type: f8
        repeat: expr
        repeat-expr: num_value
  ldta_body:
    seq:
      - id: layer_id
        type: u4
      - id: quality
        type: u2
      - size: 2
        doc: Reserved, always zeros.
      - id: stretch_dividend
        type: s4
      - id: start_time_dividend
        type: s4
        doc: Signed to allow negative start times
      - id: start_time_divisor
        type: u4
      - id: in_point_dividend
        type: s4
        doc: Signed, stored relative to start_time. Add start_time to get absolute in_point.
      - id: in_point_divisor
        type: u4
      - id: out_point_dividend
        type: s4
        doc: Signed, stored relative to start_time. Add start_time to get absolute out_point.
      - id: out_point_divisor
        type: u4
      - size: 1
        doc: Reserved, always 0.
      - type: b1  # skip bit 7
      - id: sampling_quality
        type: b1  # bit 6
      - id: environment_layer
        type: b1  # bit 5
      - id: characters_toward_camera
        type: b1  # bit 4
        doc: When true together with three_d_per_char, layer has CHARACTERS_TOWARD_CAMERA auto-orient mode
      - id: three_d_per_char
        type: b1  # bit 3
        doc: When true, per-character 3D is enabled on this text layer
      - id: frame_blending_mode
        type: b1  # bit 2
      - id: guide_layer
        type: b1  # bit 1
      - type: b1  # skip bit 0
      - id: null_layer
        type: b1  # bit 7
      - type: b1  # skip bit 6
      - id: camera_or_poi_auto_orient
        type: b1  # bit 5
        doc: When true and three_d_layer is true, layer has CAMERA_OR_POINT_OF_INTEREST auto-orient mode
      - id: markers_locked
        type: b1  # bit 4
      - id: solo
        type: b1  # bit 3
      - id: three_d_layer
        type: b1  # bit 2
      - id: adjustment_layer
        type: b1  # bit 1
      - id: auto_orient_along_path
        type: b1  # bit 0
        doc: When true, layer has ALONG_PATH auto-orient mode
      - id: collapse_transformation
        type: b1  # bit 7
      - id: shy
        type: b1  # bit 6
      - id: locked
        type: b1  # bit 5
      - id: frame_blending
        type: b1  # bit 4
      - id: motion_blur
        type: b1  # bit 3
      - id: effects_active
        type: b1  # bit 2
      - id: audio_enabled
        type: b1  # bit 1
      - id: enabled
        type: b1  # bit 0
      - id: source_id
        type: u4
      - size: 17
        doc: |
          Reserved, mostly zeros. Last 2 bytes may contain flags
          (values 0x0001 or 0x0101 in rare cases).
      - id: label
        type: u1
        enum: label
      - size: 2
        doc: Reserved, always zeros.
      - id: layer_name
        size: 32
        type: str
        encoding: windows-1252
      - size: 3
        doc: Reserved, always zeros.
      - id: blending_mode
        type: u1
      - size: 3
        doc: Reserved, always zeros.
      - id: preserve_transparency
        type: u1
      - size: 3
        doc: Reserved, always zeros.
      - id: track_matte_type
        type: u1
      - id: stretch_divisor
        type: u4
      - size: 19
        doc: Reserved, always zeros.
      - id: layer_type
        type: u1
        enum: layer_type
      - id: parent_id
        type: u4
      - size: 3
        doc: Reserved, always zeros.
      - id: light_type
        type: u1
        doc: Type of light for light layers (0=parallel, 1=spot, 2=point, 3=ambient)
      - size: 20
        doc: Reserved, mostly zeros.
      - id: matte_layer_id
        type: u4
        if: _io.size - _io.pos >= 4
        doc: |
          ID of the layer used as a track matte for this layer.
          0 when no track matte is applied. Only present in
          AE >= 23 (ldta chunks longer than 160 bytes).
    instances:
      start_time:
        value: 'start_time_dividend * 1.0 / start_time_divisor'
      in_point:
        value: 'in_point_dividend * 1.0 / in_point_divisor'
        doc: In point relative to start_time (seconds, before stretch)
      out_point:
        value: 'out_point_dividend * 1.0 / out_point_divisor'
        doc: Out point relative to start_time (seconds, before stretch)
      stretch:
        value: 'stretch_divisor != 0 ? stretch_dividend * 100.0 / stretch_divisor : 0'
        doc: Layer time stretch as percentage (100 = normal speed)
      auto_orient_type:
        value: >-
          auto_orient_along_path ? 1 :
          (camera_or_poi_auto_orient and three_d_layer ? 2 :
          (characters_toward_camera and three_d_per_char ? 3 : 0))
        enum: auto_orient_type
        doc: |
          Computed auto-orient mode from individual binary flags.
          0=no_auto_orient, 1=along_path, 2=camera_or_point_of_interest,
          3=characters_toward_camera.
      frame_blending_type:
        value: 'frame_blending ? (frame_blending_mode ? 2 : 1) : 0'
        enum: frame_blending_type
        doc: |
          Computed frame blending mode from frame_blending (enabled) and
          frame_blending_mode (0=frame_mix, 1=pixel_motion) bits.
          0=no_frame_blend, 1=frame_mix, 2=pixel_motion.
  lhd3_body:
    doc: |
      Header for item/keyframe lists. AE reuses this structure for:
      - Property keyframes (count = keyframe count, item_size = keyframe data size)
      - Render queue items (count = item count, item_size = 2246 for settings)
      - Output module items (count = item count, item_size = 128 for settings)
    seq:
      - size: 10
      - id: count
        type: u2
        doc: Number of items/keyframes in the associated ldat chunk
      - size: 6
      - id: item_size
        type: u2
        doc: Size in bytes of each item/keyframe in the associated ldat chunk
      - size: 3
      - id: item_type_raw
        type: u1
      - size-eos: true
    instances:
      item_type:
        value: >-
          item_type_raw == 1 and item_size == 2246 ? ldat_item_type::lrdr :
          item_type_raw == 1 and item_size == 128 ? ldat_item_type::litm :
          item_type_raw == 2 and item_size == 16 ? ldat_item_type::gide :
          item_type_raw == 4 and item_size == 152 ? ldat_item_type::color :
          item_type_raw == 4 and item_size == 128 ? ldat_item_type::three_d :
          item_type_raw == 4 and item_size == 104 ? ldat_item_type::two_d_spatial :
          item_type_raw == 4 and item_size == 88 ? ldat_item_type::two_d :
          item_type_raw == 4 and item_size == 80 ? ldat_item_type::orientation :
          item_type_raw == 4 and item_size == 64 ? ldat_item_type::no_value :
          item_type_raw == 4 and item_size == 48 ? ldat_item_type::one_d :
          item_type_raw == 4 and item_size == 16 ? ldat_item_type::marker :
          item_type_raw == 4 and item_size == 8 ? ldat_item_type::shape :
          ldat_item_type::unknown
  ipws_body:
    doc: |
      Interpret footage as project working space flag.
      Inside LIST:CLRS in a footage item's LIST:Pin.
      When enabled (1), the footage media color space is overridden
      to use the project's working color space.
    seq:
      - id: enabled
        type: u1
        doc: Whether to interpret as project working space (0=no, 1=yes)
  linl_body:
    doc: |
      Interpret As Linear Light setting for footage color management.
      Inside LIST:CLRS in a footage item's LIST:Pin.
      Controls whether footage is treated as having linear gamma.
    seq:
      - id: value
        type: u1
        doc: Linear light mode (0=off, 1=on, 2=on for 32 bits per channel only)
      - size: 3
        doc: Padding bytes (always 0)
  lnrb_body:
    doc: |
      Linear blending flag. Presence of this chunk in the root chunk list
      means linear blending is enabled for the project.
    seq:
      - contents: [0x01]
  lnrp_body:
    doc: |
      Linearize working space flag. Presence of this chunk in the root
      chunk list means the working color space is linearized.
    seq:
      - contents: [0x01]
  prgb_body:
    doc: |
      Preserve RGB flag for footage color management.
      Inside LIST:CLRS in a footage item's LIST:Pin.
      When this chunk is present, Preserve RGB is enabled.
      Prevents color shifts during alpha compositing in linear color.
    seq:
      - contents: [0x01]
  prin_body:
    doc: |
      Composition renderer info.
      Contains the internal match name and the display name of the
      active 3D renderer plug-in (e.g. "Classic 3D", "Cinema 4D").
      Found inside LIST:PRin of a composition's LIST:Item.
    seq:
      - size: 4
      - id: match_name
        type: strz
        size: 48
        encoding: ASCII
      - id: display_name
        type: strz
        size: 48
        encoding: ASCII
      - size: 3
      - contents: [0x01]
  list_body:
    seq:
      - id: list_type
        type: str
        encoding: windows-1252
        size: 4
      - id: chunks
        type: chunk
        repeat: eos
        if: list_type != "btdk"
      - id: binary_data
        size-eos: true
        if: list_type == "btdk"
    instances:
      # LIST:list - keyframe / shape data (always lhd3 first, ldat second when present)
      lhd3:
        value: chunks[0]
        if: 'list_type == "list"'
        doc: Header chunk (count + item size). Always the first child.
      ldat:
        value: chunks[1]
        if: 'list_type == "list" and chunks.size >= 2'
        doc: Data chunk (keyframe / shape binary items). Absent when property has no keyframes.
      # LIST:tdbs - leaf property container (always tdsb, tdsn, tdb4 in that order)
      tdsb:
        value: chunks[0]
        if: 'list_type == "tdbs"'
        doc: Property flags chunk. Always the first child.
      tdsn:
        value: chunks[1]
        if: 'list_type == "tdbs"'
        doc: Property name chunk (tdsn wraps a Utf8 child). Always the second child.
      tdb4:
        value: chunks[2]
        if: 'list_type == "tdbs"'
        doc: Property metadata chunk. Always the third child.
  mkif_body:
    doc: |
      Mask info. Contains inverted flag, locked flag, mask mode,
      motion blur, feather falloff and color.
    seq:
      - id: inverted
        type: u1
        doc: Whether the mask is inverted (1 = inverted, 0 = normal)
      - id: locked
        type: u1
        doc: Whether the mask path is locked (1 = locked, 0 = unlocked)
      - id: mask_motion_blur
        type: u1
        doc: Mask motion blur (0=Same as Layer, 1=Off, 2=On)
      - id: mask_feather_falloff
        type: u1
        doc: Mask feather falloff (0=Smooth, 1=Linear)
      - size: 2
      - id: mode
        type: u2
        doc: Mask blending mode (0=None, 1=Add, 2=Subtract, 3=Intersect, 4=Darken, 5=Lighten, 6=Difference)
      - size: 37
        doc: Unknown data (timestamps, hashes)
      - id: color
        type: u1
        repeat: expr
        repeat-expr: 3
        doc: Mask color RGB (0-255)
  fth5_body:
    doc: |
      Variable-width mask feather points.  Each feather point is 32 bytes.
      Feather points can be placed anywhere along a closed mask path to vary
      the feather radius at different positions.  The number of points is
      determined by the chunk size divided by 32.

      Integer fields use little-endian byte order despite the big-endian
      RIFX container (similar to OTST cdat).  Float fields remain big-endian.
    seq:
      - id: points
        type: feather_point
        repeat: eos
  feather_point:
    doc: |
      A single variable-width mask feather point (32 bytes).
      The feather type (inner/outer) is derived from the sign of the radius:
      negative radius = inner feather (type 1), positive = outer (type 0).
    seq:
      - id: seg_loc
        type: u4le
        doc: |
          Mask path segment number where this feather point is located
          (0-based, segments are portions of the path between vertices).
      - id: interp_raw
        type: u4le
        doc: |
          Feather radius interpolation type.
          0 = non-Hold, 2 = Hold.  Mapped to 0/1 in ExtendScript.
      - id: rel_seg_loc
        type: f8
        doc: |
          Relative position on the segment, from 0.0 (at the starting
          vertex) to 1.0 (at the next vertex).
      - id: radius
        type: f8
        doc: |
          Feather radius (amount).  Negative values indicate inner
          feather points; positive values indicate outer feather.
      - id: corner_angle
        type: f4
        doc: |
          Relative angle percentage between the two normals at a
          corner (0 to 100).  0 for non-corner feather points.
      - id: tension
        type: f4
        doc: Feather tension amount, from 0.0 (0%) to 1.0 (100%).
  shph_body:
    doc: |
      Shape path header. Contains a closed/open flag and the bounding box
      for the shape vertices.  Vertex coordinates in the associated ldat
      are normalized to [0, 1] relative to this bounding box.
    seq:
      - size: 3
      - type: b4  # skip bits 7-4
      - id: open
        type: b1  # bit 3 - true when path is open
      - type: b3  # skip bits 2-0
      - id: top_left_x
        type: f4
        doc: Bounding-box left edge (x minimum)
      - id: top_left_y
        type: f4
        doc: Bounding-box top edge (y minimum)
      - id: bottom_right_x
        type: f4
        doc: Bounding-box right edge (x maximum)
      - id: bottom_right_y
        type: f4
        doc: Bounding-box bottom edge (y maximum)
      - size: 4
  shape_point:
    doc: |
      A single normalized bezier point in a shape path.
      Coordinates are f4 values in the [0, 1] range,
      relative to the bounding box defined in shph_body.
    seq:
      - id: x
        type: f4
        doc: Normalized X coordinate
      - id: y
        type: f4
        doc: Normalized Y coordinate
  nmhd_body:
    seq:
      - size: 3
      - type: b5  # skip first 5 bits
      - id: unknown
        type: b1  # bit 2
      - id: protected_region
        type: b1  # bit 1
      - id: navigation
        type: b1  # bit 0
      - size: 4
      - id: frame_duration
        type: u4
      - size: 4
      - id: label
        type: u1
        enum: label
    instances:
      duration:
        value: 'frame_duration * 1.0 / 600'
        doc: Marker duration in seconds (frame_duration is in 600ths of a second)
  nnhd_body:
    seq:
      - size: 8
        doc: |
          Reserved. First 7 bytes always 0. Last byte can be
          0, 1, or 5 (3 unique values across all samples).
      - id: feet_frames_film_type
        type: b1
        doc: Feet+Frames film type (0=MM35, 1=MM16)
      - id: time_display_type
        type: b7
        doc: Time display type (0=TIMECODE, 1=FRAMES)
      - id: footage_timecode_display_start_type
        type: u1
      - size: 1
        doc: Reserved.
      - type: b7
      - id: frames_use_feet_frames
        type: b1
        doc: Whether to use feet+frames for timecode display (0=false, 1=true)
      - size: 2
        doc: Reserved.
      - id: timecode_default_base
        type: u2
        doc: |
          The Default Base value shown in the Time Display Style
          section of the Project Settings dialog, under Timecode.
      - size: 4
        doc: |
          Unknown u4 field. Only two values observed: 16 (0x10)
          and 40 (0x28) across all samples.
      - id: frames_count_type
        type: u1
      - size: 3
        doc: Reserved.
      - id: bits_per_channel
        type: u1
      - id: transparency_grid_thumbnails
        type: u1
        doc: Whether transparency grid is shown in thumbnails (0=false, 1=true)
      - size: 5
        doc: Unknown bytes 26-30
      - type: b2
        doc: Unknown bits 7-6
      - id: linearize_working_space
        type: b1
        doc: Whether to linearize working space for blending (0=false, 1=true). Note - the lnrp chunk at root level is the source of truth for this setting.
      - type: b5
        doc: Unknown bits 4-0
      - size: 8
        doc: Unknown bytes 32-39
    instances:
      display_start_frame:
        value: frames_count_type % 2
        doc: "Alternate way of reading the Frame Count setting as 0 or 1."
  opti_body:
    seq:
      - id: asset_type
        size: 4
        type: strz
        encoding: ASCII
        # enum: asset_type
      - id: asset_type_int
        type: u2
      - size: 8
        if: asset_type == "Soli"
      - id: color
        type: f4
        repeat: expr
        repeat-expr: 3
        if: asset_type == "Soli"
      - id: solid_name
        size: 256
        type: strz
        encoding: windows-1252
        if: asset_type == "Soli"
      - size: 4
        if: asset_type_int == 2
      - id: placeholder_name
        type: str
        encoding: windows-1252
        size-eos: true
        if: asset_type_int == 2
      # PSD-specific fields (Photoshop document layers)
      # Note: PSD sub-structure seems to use little-endian byte order...
      - size: 10
        if: asset_type == "8BPS"
        doc: Unknown PSD bytes 6-15
      - id: psd_layer_index
        type: u2
        if: asset_type == "8BPS"
        doc: |
          Zero-based index of this layer within the source PSD file.
          0 is typically the Background layer. 0xFFFF means
          merged/flattened (no specific layer).
      - size: 4
        if: asset_type == "8BPS"
        doc: Unknown PSD bytes 18-21 (contains reversed magic "SPB8")
      - size: 4
        if: asset_type == "8BPS"
        doc: Unknown PSD bytes 22-25
      - size: 4
        if: asset_type == "8BPS"
        doc: Unknown PSD bytes 26-29
      - id: psd_channels
        type: u1
        if: asset_type == "8BPS"
        doc: Number of color channels (3=RGB, 4=RGBA or CMYK)
      - size: 1
        if: asset_type == "8BPS"
        doc: Unknown PSD byte 31
      - id: psd_canvas_height
        type: u2le
        if: asset_type == "8BPS"
        doc: Full PSD canvas height in pixels
      - size: 2
        if: asset_type == "8BPS"
        doc: Unknown PSD bytes 34-35
      - id: psd_canvas_width
        type: u2le
        if: asset_type == "8BPS"
        doc: Full PSD canvas width in pixels
      - size: 2
        if: asset_type == "8BPS"
        doc: Unknown PSD bytes 38-39
      - id: psd_bit_depth
        type: u1
        if: asset_type == "8BPS"
        doc: Bit depth per channel (8=8bpc, 16=16bpc)
      - size: 7
        if: asset_type == "8BPS"
        doc: Unknown PSD bytes 41-47
      - id: psd_layer_count
        type: u1
        if: asset_type == "8BPS"
        doc: Total number of layers in the source PSD file
      - size: 29
        if: asset_type == "8BPS"
        doc: Unknown PSD bytes 49-77
      - id: psd_layer_top
        type: s4le
        if: asset_type == "8BPS"
        doc: Layer bounding box top coordinate in pixels (can be negative)
      - id: psd_layer_left
        type: s4le
        if: asset_type == "8BPS"
        doc: Layer bounding box left coordinate in pixels (can be negative)
      - id: psd_layer_bottom
        type: s4le
        if: asset_type == "8BPS"
        doc: Layer bounding box bottom coordinate in pixels
      - id: psd_layer_right
        type: s4le
        if: asset_type == "8BPS"
        doc: Layer bounding box right coordinate in pixels
      - size: 250
        if: asset_type == "8BPS"
        doc: Unknown PSD bytes 94-343
      - id: psd_group_name
        type: str
        encoding: UTF-8
        size-eos: true
        if: asset_type == "8BPS"
        doc: PSD group/folder name that this layer belongs to (e.g. "PAINT 02")
      - size-eos: true
  pard_body:
    seq:
      - size: 15
      - id: property_control_type
        type: u1
        enum: property_control_type
      - id: name
        size: 32
        type: str
        encoding: windows-1252
      - size: 8
      - id: last_color
        type: u1
        repeat: expr
        repeat-expr: 4
        if: property_control_type == property_control_type::color
      - id: default_color
        type: u1
        repeat: expr
        repeat-expr: 4
        if: property_control_type == property_control_type::color
      - id: last_value
        type:
          switch-on: property_control_type
          cases:
            'property_control_type::scalar': s4
            'property_control_type::angle': s4
            'property_control_type::boolean': u4
            'property_control_type::enum': u4
            'property_control_type::slider': f8
        if: >-
          property_control_type == property_control_type::scalar
          or property_control_type == property_control_type::angle
          or property_control_type == property_control_type::boolean
          or property_control_type == property_control_type::enum
          or property_control_type == property_control_type::slider
      - id: last_value_x_raw
        type:
          switch-on: property_control_type
          cases:
            'property_control_type::two_d': s4
            'property_control_type::three_d': f8
        if: >-
          property_control_type == property_control_type::two_d
          or property_control_type == property_control_type::three_d
      - id: last_value_y_raw
        type:
          switch-on: property_control_type
          cases:
            'property_control_type::two_d': s4
            'property_control_type::three_d': f8
        if: >-
          property_control_type == property_control_type::two_d
          or property_control_type == property_control_type::three_d
      - id: last_value_z_raw
        type: f8
        if: property_control_type == property_control_type::three_d
      - id: nb_options
        type: s4
        if: property_control_type == property_control_type::enum
      - id: default
        type:
          switch-on: property_control_type
          cases:
            'property_control_type::boolean': u1
            'property_control_type::enum': s4
        if: >-
          property_control_type == property_control_type::boolean
          or property_control_type == property_control_type::enum
      - size: '(property_control_type == property_control_type::scalar ? 72 : property_control_type == property_control_type::color ? 64 : 52)'
        if: >-
          property_control_type == property_control_type::scalar
          or property_control_type == property_control_type::color
          or property_control_type == property_control_type::slider
      - id: min_value
        type: s2
        if: property_control_type == property_control_type::scalar
      - size: 2
        if: property_control_type == property_control_type::scalar
      - id: max_color
        type: u1
        repeat: expr
        repeat-expr: 4
        if: property_control_type == property_control_type::color
      - id: max_value
        type:
          switch-on: property_control_type
          cases:
            'property_control_type::scalar': s2
            'property_control_type::slider': f4
        if: >-
          property_control_type == property_control_type::scalar
          or property_control_type == property_control_type::slider
      - size-eos: true
    instances:
      last_value_x:
        value: 'last_value_x_raw * (property_control_type == property_control_type::two_d ? 1.0/128 : 512)'
        if: >-
          property_control_type == property_control_type::two_d
          or property_control_type == property_control_type::three_d
      last_value_y:
        value: 'last_value_y_raw * (property_control_type == property_control_type::two_d ? 1.0/128 : 512)'
        if: >-
          property_control_type == property_control_type::two_d
          or property_control_type == property_control_type::three_d
      last_value_z:
        value: 'last_value_z_raw * 512'
        if: property_control_type == property_control_type::three_d
  sspc_body:
    doc: |
      Source footage settings chunk. Contains dimension, timing, and alpha/field settings.
    seq:
      - size: 22
        doc: Reserved, always zeros.
      - id: source_format_type
        type: str
        size: 4
        encoding: ASCII
        doc: |
          Source format 4-character code identifying the file type.
          Common values: 'png!', '8BPS' (PSD), 'MOoV' (QuickTime),
          'WAVE', 'oEXR' (OpenEXR), 'MPEG', 'TIF_', 'Soli' (Solid),
          'TEXT', 'STIL', 'ZPEG' (JPEG). Null bytes for unknown/missing.
      - size: 6
        doc: Reserved, always zeros.
      - id: width
        type: u2
      - size: 2
        doc: Reserved.
      - id: height
        type: u2
      - id: duration_dividend
        type: u4
      - id: duration_divisor
        type: u4
      - size: 10
        doc: |
          10 bytes: bytes 0-3 always 0, bytes 4-7 contain a frame rate
          dividend (values: 24, 25, 30, 600, 2997), bytes 8-9 always 0.
      - id: native_frame_rate_integer
        type: u4
      - id: native_frame_rate_fractional
        type: u2
      - size: 7
        doc: |
          7 bytes: byte 0 always 0, byte 1 contains source depth flags
          (0x18=24bpc, 0x20=32bpc, 0x40=64bpc, etc.), bytes 2-3 are
          a pair (both 0 or both 1), bytes 4-6 always zeros.
      # Byte 69: alpha flags
      - type: b6  # skip bits 7-2
      - id: invert_alpha
        type: b1  # bit 1
        doc: True if the alpha channel should be inverted
      - id: premultiplied
        type: b1  # bit 0
        doc: True if alpha is premultiplied (matches alpha_mode=PREMULTIPLIED)
      # Bytes 70-72: premul color (RGB, 0-255)
      - id: premul_color
        type: u1
        repeat: expr
        repeat-expr: 3
        doc: Premultiply color RGB (0-255)
      - id: alpha_mode_raw
        type: u1
        doc: |
          Alpha interpretation mode. When no_alpha (3), the footage has no alpha channel.
      - size: 9
        doc: Reserved.
      - id: field_separation_type_raw
        type: u1
        doc: |
          0 = OFF, 1 = enabled (check field_order for UPPER vs LOWER)
      - size: 3
        doc: Reserved.
      - id: field_order
        type: u1
        doc: |
          Field order when field separation is enabled
      - size: 27
        doc: Reserved.
      - id: footage_missing_at_save
        type: u1
        doc: |
          Whether the footage was missing when the project was last saved.
          0 = source file found, 1 = source file missing or placeholder.
      - size: 13
        doc: |
          13 bytes: byte 0 is a flag (0 or 1), byte 1 always 0,
          bytes 2-5 contain an HFS+ timestamp (seconds since
          1904-01-01), bytes 6-9 always 12, bytes 10-12 always zeros.
      - id: loop
        type: u1
        doc: Number of times to loop the footage (1 = no loop, 2+ = loop count)
      - size: 6
        doc: Reserved.
      - id: pixel_ratio_dividend
        type: u4
      - id: pixel_ratio_divisor
        type: u4
      - size: 3
        doc: Reserved.
      - id: remove_pulldown
        type: u1
        doc: Pulldown phase (0=OFF, 1-10=various pulldown phases)
      - id: conform_frame_rate_integer
        type: u2
        doc: Integer part of conform frame rate. 0 = no conforming.
      - id: conform_frame_rate_fractional
        type: u2
        doc: Fractional part of conform frame rate (/ 65536).
      - size: 7
        doc: Reserved.
      - id: high_quality_field_separation
        type: u1
        doc: |
          When true (1), After Effects uses special algorithms for high-quality field separation.
      - id: audio_sample_rate
        type: f8
        doc: |
          Audio sample rate in Hz (e.g. 44100.0 or 48000.0).
          0.0 when the footage has no audio component.
      - size: 4
        doc: Reserved.
      - id: start_frame
        type: u4
      - id: end_frame
        type: u4
      - id: frame_padding
        type: u4
        doc: |
          Number of zero-padded digits used for frame numbers in image
          sequences. For example, 4 means frames are numbered as 0001,
          0002 etc. 0 for non-sequence footage.
      - size-eos: true
    instances:
      native_frame_rate:
        value: 'native_frame_rate_integer + (native_frame_rate_fractional / 65536.0)'
        doc: The native frame rate of the footage.
      pixel_aspect:
        value: 'pixel_ratio_dividend * 1.0 / pixel_ratio_divisor'
      has_alpha:
        value: alpha_mode_raw != 3
        doc: True if footage has an alpha channel (3 means no_alpha)
      has_audio:
        value: audio_sample_rate > 0
        doc: True if footage has an audio component.
      field_separation_type:
        value: 'field_separation_type_raw == 0 ? 0 : field_order + 1'
        doc: |
          Combined field separation mode.
          0 = OFF, 1 = UPPER_FIELD_FIRST, 2 = LOWER_FIELD_FIRST
      conform_frame_rate:
        value: 'conform_frame_rate_integer + (conform_frame_rate_fractional / 65536.0)'
        doc: |
          A frame rate to use instead of native_frame_rate.
          0 means no conforming (use native_frame_rate).
      display_frame_rate:
        value: '(conform_frame_rate != 0 ? conform_frame_rate : native_frame_rate) * (remove_pulldown != 0 ? 0.8 : 1.0)'
        doc: |
          The effective frame rate as displayed and rendered.
          If removePulldown is active, multiplied by 0.8.
      source_duration:
        value: 'duration_dividend * 1.0 / duration_divisor'
        doc: Raw duration of the source footage in seconds (before conform/loop).
      duration:
        value: 'source_duration * (conform_frame_rate != 0 ? native_frame_rate / conform_frame_rate : 1) * loop'
        doc: |
          Total duration of the footage item in seconds.
          Accounts for conform frame rate and loop count.
          Pulldown does not affect duration (frame rate reduction and
          frame removal cancel out).
      frame_duration:
        value: 'duration * display_frame_rate'
        doc: Total number of frames in the footage item.
  tdum_body:
    doc: |
      Property min/max value inside a tdbs LIST.
      Used for both tdum (min) and tduM (max) chunks.
      Encoding depends on tdb4 sibling flags: color (4x f4),
      integer (u4), or scalar/position/vector (repeated f8).
    params:
      - id: is_color
        type: bool
      - id: is_integer
        type: bool
    seq:
      - id: value_doubles
        type: f8
        repeat: expr
        repeat-expr: '_parent.len_body / 8'
        if: 'not is_color and not is_integer'
      - id: value_color
        type: f4
        repeat: expr
        repeat-expr: 4
        if: is_color
      - id: value_integer
        type: u4
        if: is_integer
  tdb4_body:
    seq:
      - id: magic
        contents: [0xdb, 0x99]
      - id: dimensions
        type: u2
        doc: Number of values in a multi-dimensional
      - size: 1
      - type: b4  # skip bits 7-4
      - id: is_spatial
        type: b1  # bit 3
      - type: b2  # skip bits 2-1
      - id: static
        type: b1  # bit 0
      - size: 5
        doc: Unknown bytes including flags
      - type: b6  # skip bits 7-2
      - id: can_vary_over_time
        type: b1  # bit 1
        doc: |
          When true, the property can vary over time (can accept keyframes
          or expressions). Matches ExtendScript canVaryOverTime for most
          property types. A small subset of effect dropdown / menu
          parameters report canVaryOverTime=true in ExtendScript despite
          this bit being 0.
      - type: b1  # skip bit 0
      - size: 4
        doc: Unknown bytes
      - id: unknown_floats
        type: f8
        repeat: expr
        repeat-expr: 5
        doc: |
          First float is a threshold (0.0001 for most properties, 0.0 for
          some plugin spatial points). Second float encodes a comp aspect
          ratio for spatial properties (e.g. 1.777778 = 16:9, 1.333333 =
          4:3); 1.0 for non-spatial. Last three are always 1.0.
      # property_control_type - 4 bytes
      - size: 1
      - type: b7  # skip bits 7-1
      - id: no_value
        type: b1  # bit 0
      - size: 1
      - type: b4  # skip bits 7-4
      - id: vector
        type: b1  # bit 3
      - id: integer
        type: b1  # bit 2
      - type: b1  # skip bit 1
      - id: color
        type: b1  # bit 0
      - size: 8
        doc: Unknown bytes including type correlated byte
      - id: animated
        type: u1
      - size: 15
        doc: Unknown bytes and flags
      - size: 32
        doc: Reserved - always zero across all known property types.
      - size: 3
      - type: b7  # skip first 7 bits
      - id: expression_disabled
        type: b1  # bit 0
      - size: 4
        doc: Unknown flags
  tdsb_body:
    seq:
      - id: roto_bezier
        type: u1
        doc: |
          RotoBezier flag for mask shape properties (byte 0).
          1 = RotoBezier enabled. Always 0 for non-mask-shape properties.
      - size: 1   # skip byte 1
      - type: b3  # skip first 3 bits
      - id: locked_ratio
        type: b1  # bit 4
      - type: b4  # skip remaining 4 bits
      - type: b6  # skip first 6 bits
      - id: dimensions_separated  
        type: b1  # bit 1
      - id: enabled
        type: b1  # bit 0
  utf8_body:
    seq:
      - id: contents
        type: str
        encoding: UTF-8
        size-eos: true

enums:
  item_type: # type of item. See: https://ae-scripting.docsforadobe.dev/item/item/#itemtypename
    1: folder
    4: composition
    7: footage
  asset_type:
    2: placeholder
    9: solid
  layer_type:
    0: avlayer
    1: light
    2: camera
    3: text
    4: shape
    5: three_d_model
  label:
    0: none
    1: red
    2: yellow
    3: aqua
    4: pink
    5: lavender
    6: peach
    7: sea_foam
    8: blue
    9: green
    10: purple
    11: orange
    12: brown
    13: fuchsia
    14: cyan
    15: sandstone
    16: dark_green
  auto_orient_type:
    0: no_auto_orient
    1: along_path
    2: camera_or_point_of_interest
    3: characters_toward_camera
  frame_blending_type:
    0: no_frame_blend
    1: frame_mix
    2: pixel_motion
  fast_preview_type:
    0: off
    1: adaptive_resolution
    2: draft
    3: fast_draft
    4: wireframe
  property_control_type:
    0: layer
    # 1: integer ?
    2: scalar
    3: angle
    4: boolean
    5: color
    6: two_d
    7: enum
    9: paint_group
    10: slider
    11: curve
    # 12: mask ?
    13: group
    # 14: ??
    15: unknown
    18: three_d
  ldat_item_type:
    0:
      id: unknown
      doc: unknown
    1:
      id: no_value
      doc: Stores no data
    2:
      id: three_d_spatial
      doc: |
        Array of three floating-point positional values.
        For example, an Anchor Point value might be [10.0, 20.2, 0.0]
    3:
      id: three_d
      doc: |
        Array of three floating-point quantitative values.
        For example, a Scale value might be [100.0, 20.2, 0.0]
    4:
      id: two_d_spatial
      doc: |
        Array of 2 floating-point positional values.
        For example, an Anchor Point value might be [5.1, 10.0]
    5:
      id: two_d
      doc: |
        Array of 2 floating-point quantitative values.
        For example, a Scale value might be [5.1, 100.0]
    6:
      id: one_d
      doc: A floating-point value.
    7:
      id: color
      doc: |
        Array of 4 floating-point values in the range [0.0..1.0].
        For example, [0.8, 0.3, 0.1, 1.0]
    8:
      id: custom_value
      doc: Custom property value, such as the Histogram property for the Levels effect.
    9:
      id: marker
      doc: MarkerValue object
    10:
      id: layer_index
      doc: Integer; a value of 0 means no layer.
    11:
      id: mask_index
      doc: Integer; a value of 0 means no mask.
    12:
      id: shape
      doc: Shape object
    13:
      id: text_document
      doc: TextDocument object
    14:
      id: lrdr
      doc: Render Queue Item settings
    15:
      id: litm
      doc: Output Module settings
    16:
      id: gide
      doc: Guide item (orientation + position)
    17:
      id: orientation
      doc: ??
