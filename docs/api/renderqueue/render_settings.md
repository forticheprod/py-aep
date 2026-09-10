# Render Settings

Render settings are accessed via `RenderQueueItem.settings`, a [SettingsView][py_aep.models.renderqueue.settings.SettingsView] dict with ExtendScript-compatible keys matching the format from `RenderQueueItem.get_settings(GetSettingsFormat.NUMBER)`.

## Available Keys

| Key | Type | Description |
|-----|------|-------------|
| `"3:2 Pulldown"` | [PulldownSetting][py_aep.enums.PulldownSetting] | Pulldown phase setting |
| `"Color Depth"` | [ColorDepthSetting][py_aep.enums.ColorDepthSetting] | Color depth setting |
| `"Disk Cache"` | [DiskCacheSetting][py_aep.enums.DiskCacheSetting] | Disk cache setting |
| `"Effects"` | [EffectsSetting][py_aep.enums.EffectsSetting] | Effects setting |
| `"Field Render"` | [FieldRender][py_aep.enums.FieldRender] | Field render setting |
| `"Frame Blending"` | [FrameBlendingSetting][py_aep.enums.FrameBlendingSetting] | Frame blending setting |
| `"Frame Rate"` | [FrameRateSetting][py_aep.enums.FrameRateSetting] | Frame rate source |
| `"Guide Layers"` | [GuideLayers][py_aep.enums.GuideLayers] | Guide layers setting |
| `"Motion Blur"` | [MotionBlurSetting][py_aep.enums.MotionBlurSetting] | Motion blur setting |
| `"Proxy Use"` | [ProxyUseSetting][py_aep.enums.ProxyUseSetting] | Proxy use setting |
| `"Quality"` | [RenderQuality][py_aep.enums.RenderQuality] | Quality setting |
| `"Resolution"` | `list[int]` | Resolution factor `[x, y]` (e.g. `[1, 1]` = Full, `[2, 2]` = Half, `[3, 3]` = Third, `[4, 4]` = Quarter) |
| `"Skip Existing Files"` | `bool` | Whether to skip rendering if output file exists |
| `"Solo Switches"` | [SoloSwitchesSetting][py_aep.enums.SoloSwitchesSetting] | Solo switches setting |
| `"Time Span Duration"` | `float` | Duration in seconds |
| `"Time Span End"` | `float` | End time in seconds |
| `"Time Span Start"` | `float` | Start time in seconds |
| `"Time Span"` | [TimeSpanSource][py_aep.enums.TimeSpanSource] | Time span source |
| `"Use comp's frame rate"` | `float` | The composition's frame rate |
| `"Use this frame rate"` | `float` | Custom frame rate value (when `"Frame Rate"` is `USE_THIS_FRAME_RATE`) |

## Enum Values

### PulldownSetting

| Member | Value | Label |
|--------|-------|-------|
| `OFF` | 0 | `"Off"` |
| `WSSWW` | 1 | `"WSSWW"` |
| `SSWWW` | 2 | `"SSWWW"` |
| `SWWWS` | 3 | `"SWWWS"` |
| `WWWSS` | 4 | `"WWWSS"` |
| `WWSSW` | 5 | `"WWSSW"` |

### ColorDepthSetting

| Member | Value | Label |
|--------|-------|-------|
| `CURRENT_SETTINGS` | -1 | `"Current Settings"` |
| `EIGHT_BITS_PER_CHANNEL` | 0 | `"8 bits per channel"` |
| `SIXTEEN_BITS_PER_CHANNEL` | 1 | `"16 bits per channel"` |
| `THIRTY_TWO_BITS_PER_CHANNEL` | 2 | `"32 bits per channel"` |

### FieldRender

| Member | Value | Label |
|--------|-------|-------|
| `OFF` | 0 | `"Off"` |
| `UPPER_FIELD_FIRST` | 1 | `"Upper Field First"` |
| `LOWER_FIELD_FIRST` | 2 | `"Lower Field First"` |

### FrameRateSetting

| Member | Value | Label |
|--------|-------|-------|
| `USE_COMP_FRAME_RATE` | 0 | `"Use comp's frame rate"` |
| `USE_THIS_FRAME_RATE` | 1 | `"Use this frame rate"` |

### RenderQuality

| Member | Value | Label |
|--------|-------|-------|
| `CURRENT_SETTINGS` | -1 | `"Current Settings"` |
| `WIREFRAME` | 0 | `"Wireframe"` |
| `DRAFT` | 1 | `"Draft"` |
| `BEST` | 2 | `"Best"` |

### MotionBlurSetting

| Member | Value | Label |
|--------|-------|-------|
| `OFF_FOR_ALL_LAYERS` | 0 | `"Off for All Layers"` |
| `ON_FOR_CHECKED_LAYERS` | 1 | `"On for Checked Layers"` |
| `CURRENT_SETTINGS` | 2 | `"Current Settings"` |

### FrameBlendingSetting

| Member | Value | Label |
|--------|-------|-------|
| `OFF_FOR_ALL_LAYERS` | 0 | `"Off for All Layers"` |
| `ON_FOR_CHECKED_LAYERS` | 1 | `"On for Checked Layers"` |
| `CURRENT_SETTINGS` | 2 | `"Current Settings"` |

### EffectsSetting

| Member | Value | Label |
|--------|-------|-------|
| `ALL_OFF` | 0 | `"All Off"` |
| `ALL_ON` | 1 | `"All On"` |
| `CURRENT_SETTINGS` | 2 | `"Current Settings"` |

### ProxyUseSetting

| Member | Value | Label |
|--------|-------|-------|
| `USE_NO_PROXIES` | 0 | `"Use No Proxies"` |
| `USE_ALL_PROXIES` | 1 | `"Use All Proxies"` |
| `CURRENT_SETTINGS` | 2 | `"Current Settings"` |
| `USE_COMP_PROXIES_ONLY` | 3 | `"Use Comp Proxies Only"` |

### SoloSwitchesSetting

| Member | Value | Label |
|--------|-------|-------|
| `ALL_OFF` | 0 | `"All Off"` |
| `CURRENT_SETTINGS` | 2 | `"Current Settings"` |

### GuideLayers

| Member | Value | Label |
|--------|-------|-------|
| `ALL_OFF` | 0 | `"All Off"` |
| `CURRENT_SETTINGS` | 2 | `"Current Settings"` |

### DiskCacheSetting

| Member | Value | Label |
|--------|-------|-------|
| `READ_ONLY` | 0 | `"Read Only"` |
| `CURRENT_SETTINGS` | 2 | `"Current Settings"` |

### TimeSpanSource

| Member | Value | Label |
|--------|-------|-------|
| `LENGTH_OF_COMP` | 0 | `"Length of Comp"` |
| `WORK_AREA_ONLY` | 1 | `"Work Area Only"` |
| `CUSTOM` | 2 | `"Custom"` |

## The settings view

::: py_aep.models.renderqueue.settings.SettingsView
    options:
      heading_level: 3
