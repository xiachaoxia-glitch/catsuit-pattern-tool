# Catsuit Pattern Tool 🧵

**自动生成乳胶紧身连体衣打版 DXF 文件 + 几何验证工具链**
**Automated latex catsuit pattern drafting (DXF) + geometric validation pipeline**

Generate sewing patterns as DXF files from body measurements, then automatically validate the geometry (self-intersections, seam matching, panel proportions).

## Features

| Tool | Description |
|------|-------------|
| `generate_catsuit_pattern.py` | Generate a full catsuit pattern DXF from body measurements — front panel, back panel, gusset, zipper placket. Bezier curves for smooth armholes, necklines and crotch seams. |
| `validate_pattern.py` | Geometric validation of DXF patterns — self-intersection detection, seam edge matching between panels, panel area/bbox/length reporting. Outputs human-readable report + JSON. |
| `auto_pattern.py` | One-command pipeline: measurements → generate DXF → validate → auto-retry with size adjustment → report. |

## Quick Start

```bash
pip install ezdxf

# 1. Generate a pattern (edit CUSTOM_MEASUREMENTS at the top of the script for your size)
python generate_catsuit_pattern.py
# → catsuit_pattern_YYYYMMDD.dxf

# 2. Validate it
python validate_pattern.py catsuit_pattern_20260721.dxf
# → 通过/警告/失败 report + catsuit_pattern_20260721_validation.json

# 3. Or run the full auto pipeline (manual measurements mode)
python auto_pattern.py --manual --bust 88 --waist 68 --hip 92 --height 165
```

## Install from PyPI

```bash
pip install catsuit-pattern

# CLI entry points (after install)
catsuit-generate              # generate a DXF pattern
catsuit-validate <file.dxf>   # validate a pattern
catsuit-auto --manual --bust 88 --waist 68 --hip 92   # full pipeline
```

## Development

```bash
pip install -e .[dev]
pytest -v        # run the test suite
```

CI runs the test suite + smoke test (generate → validate) on Python 3.9/3.11/3.12 for every push and PR.

## Example Output

Run `validate_pattern.py examples/catsuit_pattern_20260721.dxf` to see a sample report:

```
📐 裁片 (4 个)
    P1_c1        面积 189585.8 cm² 周长 3159.6 mm 尺寸  242×1456 mm
    P2_c5        面积 191602.7 cm² 周长 3182.3 mm 尺寸  246×1456 mm
    P3_c6        面积 38640.0 cm² 周长  814.4 mm 尺寸  230× 336 mm
    P4_c7        面积 17424.0 cm² 周长  951.2 mm 尺寸   40× 436 mm
```

## DXF Output

- Units: **millimeters** (INSUNITS=4)
- Layers: 裁片 (panels), 标注 (dimensions), 参考 (reference), 缝份 (seam allowance)
- Open with LibreCAD / Inkscape / AutoCAD, print at A4 tile layout
- Patterns are half-side (single panel); mirror + seam allowance needed when cutting fabric

## Workflow

```
body measurements → generate_catsuit_pattern.py → .dxf → validate_pattern.py → ✅ pass / ⚠️ warn / ❌ fail
                                                                                          ↓ retry with adjustment factors (auto_pattern.py)
```

## Notes

- Seam allowance (缝份) is drawn as a dashed inner line (10mm default)
- Validation is geometric only — fabric stretch properties of latex are outside the scope of this tool
- 说明：本工具只做几何打版与校验，乳胶面料的弹性拉伸特性不在处理范围内

## License

MIT
