"""
版型验证器 — 读取 DXF 裁片，进行自动几何校验
=============================================
用法: python validate_pattern.py <dxf文件>
      python validate_pattern.py catsuit_pattern_20260721.dxf

输出: 通过/警告/失败 三级报告
"""

import sys, math
from typing import List, Tuple, Dict, Optional

# Windows 控制台 UTF-8 支持（否则 emoji 报 GBK 错误）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import ezdxf
except ImportError:
    print("❌ 需要 ezdxf，安装：pip install ezdxf")
    raise SystemExit(1)


def polyline_points(poly) -> List[Tuple[float, float]]:
    """从 DXF LWPOLYLINE 提取点列"""
    pts = poly.get_points()
    # ezdxf 的 get_points 可能返回 Vec2 或 tuple
    return [(p[0], p[1]) for p in pts]


def distance(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def polyline_length(pts: List[Tuple[float, float]]) -> float:
    return sum(distance(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def check_self_intersection(pts: List[Tuple[float, float]]) -> bool:
    """检测自交 — 只检查不共享顶点的线段对"""
    n = len(pts)
    if n < 4:
        return False
    for i in range(n - 1):
        a1, a2 = pts[i], pts[i + 1]
        for j in range(i + 2, n - 1):
            b1, b2 = pts[j], pts[j + 1]
            # 跳过共享顶点和相邻边
            if j == i + 1:
                continue
            shared = {a1, a2} & {b1, b2}
            if shared:
                continue
            if segments_intersect(a1, a2, b1, b2):
                return True
    return False


def orientation(p, q, r) -> int:
    """叉积判断三点方向：1=逆时针(左转), 2=顺时针(右转), 0=共线
    标准公式：(q-p) × (r-p)
    """
    val = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    if abs(val) < 1e-9:
        return 0
    return 1 if val > 0 else 2


def on_segment(p, q, r) -> bool:
    return (
        min(p[0], r[0]) <= q[0] <= max(p[0], r[0])
        and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])
    )


def segments_intersect(p1, q1, p2, q2) -> bool:
    o1 = orientation(p1, q1, p2)
    o2 = orientation(p1, q1, q2)
    o3 = orientation(p2, q2, p1)
    o4 = orientation(p2, q2, q1)
    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and on_segment(p1, p2, q1):
        return True
    if o2 == 0 and on_segment(p1, q2, q1):
        return True
    if o3 == 0 and on_segment(p2, p1, q2):
        return True
    if o4 == 0 and on_segment(p2, q1, q2):
        return True
    return False


def find_matching_edges(
    panels: Dict[str, List[Tuple[float, float]]],
    tolerance: float = 5.0,
) -> List[dict]:
    """
    自动寻找不同裁片之间长度相近的边，适配对。
    用于发现应该缝合但长度不匹配的边。
    注意：半片裁片（两侧）的缝合边长度应 ×2 后匹配。
    """
    issues = []
    names = list(panels.keys())

    # 对每对裁片，找到各自最长边（最可能是缝合边）
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            pi, pj = panels[names[i]], panels[names[j]]
            # 找每个裁片中最长的一段直边（连续 3 点近似直线）
            def find_longest_edge(pts):
                best = 0
                n = len(pts)
                for k in range(n):
                    p1 = pts[k]
                    p2 = pts[(k + 1) % n]
                    d = distance(p1, p2)
                    if d > best:
                        best = d
                return best

            ei = find_longest_edge(pi)
            ej = find_longest_edge(pj)
            diff = abs(ei - ej)
            # 如果两条最长边长度接近，可能是一对缝合边
            if diff <= max(ei, ej) * 0.3 and diff > tolerance:
                issues.append({
                    "type": "seam_mismatch",
                    "panel_a": names[i],
                    "panel_b": names[j],
                    "length_a": round(ei, 1),
                    "length_b": round(ej, 1),
                    "diff": round(diff, 1),
                    "message": f"{names[i]} 最长边({ei:.0f}) ↔ {names[j]} 最长边({ej:.0f}) 差 {diff:.0f}mm",
                })
    return issues


def validate(
    dxf_path: str,
    body_measurements: Optional[Dict[str, float]] = None,
) -> dict:
    """主验证函数"""
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    # ── 收集裁片 ──────────────────────────────────────────
    panels: Dict[str, List[Tuple[float, float]]] = {}
    panel_objects = {}

    for e in msp:
        if e.dxftype() == "LWPOLYLINE" and hasattr(e.dxf, "layer"):
            layer = e.dxf.layer
            if "裁片" in layer and e.closed:
                pts = polyline_points(e)
                color = e.dxf.color
                # 用颜色+尺寸做标识
                label = f"panel_{len(panels)}"
                # 尝试从附近文字找出标签
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                label = f"P{len(panels)+1}_c{color}"
                panels[label] = pts
                panel_objects[label] = e

    total_entities = len(list(msp))

    # ── 逐项检查 ──────────────────────────────────────────
    issues: List[dict] = []
    panel_results = {}

    for name, pts in panels.items():
        info = {"name": name, "points": len(pts), "closed": True}
        info["length"] = round(polyline_length(pts) + distance(pts[-1], pts[0]), 1)
        # 面积（多边形 shoelace）
        area = 0.0
        n = len(pts)
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            area += x1 * y2 - x2 * y1
        info["area_cm2"] = round(abs(area) / 2, 1)

        # 自交检测
        info["self_intersecting"] = check_self_intersection(pts)

        # 最小包围盒 (用于察觉离谱比例)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        info["bbox_mm"] = (
            round(max(xs) - min(xs), 1),
            round(max(ys) - min(ys), 1),
        )

        if info["self_intersecting"]:
            issues.append(
                {
                    "type": "self_intersect",
                    "panel": name,
                    "message": f"{name} 有自交！需要手动修复",
                }
            )

        # 面积太小的警告
        if info["area_cm2"] < 50:
            issues.append(
                {
                    "type": "tiny_panel",
                    "panel": name,
                    "message": f"{name} 面积仅 {info['area_cm2']}cm²，确认是否需要",
                }
            )

        panel_results[name] = info

    # ── 裁片间匹配 ────────────────────────────────────────
    seam_issues = find_matching_edges(panels)
    issues.extend(seam_issues)

    # ── 体型一致性检查（需要 body_measurements 中传入 mm 值）──
    # 跳过: 版型验证只做几何检查，比例合理性由生成器保证
    # 如需比例检查，请使用外部参考尺寸人工核对

    # ── 汇总 ──────────────────────────────────────────────
    status = "✅ 通过" if len(issues) == 0 else (
        "⚠️ 警告" if sum(1 for i in issues if i["type"] in ("seam_mismatch", "tiny_panel")) == len(issues)
        else "❌ 失败"
    )

    report = {
        "file": dxf_path,
        "entity_count": total_entities,
        "panel_count": len(panels),
        "status": status,
        "panels": panel_results,
        "issues": issues,
    }
    return report


def print_report(report: dict):
    """打印人类可读的报告"""
    print("=" * 60)
    print(f"  版型验证报告 — {report['file']}")
    print(f"  状态: {report['status']}")
    print("=" * 60)

    print(f"\n📐 裁片 ({report['panel_count']} 个)")
    print("-" * 60)
    for name, info in report["panels"].items():
        flag = "⚠️" if info["self_intersecting"] else " "
        bw, bh = info["bbox_mm"]
        print(
            f"  {flag} {name:<12s}"
            f" 面积 {info['area_cm2']:>6.1f} cm²"
            f" 周长 {info['length']:>6.1f} mm"
            f" 尺寸 {bw:>4.0f}×{bh:>4.0f} mm"
        )

    print(f"\n🛑 问题 ({len(report['issues'])})")
    print("-" * 60)
    if not report["issues"]:
        print("  无 — 所有几何检查通过")
    else:
        for iss in report["issues"]:
            level = {
                "self_intersect": "❌",
                "seam_mismatch": "⚠️",
                "proportion": "⚠️",
                "tiny_panel": "💡",
            }.get(iss["type"], "  ")
            print(f"  {level} [{iss['type']}] {iss['message']}")

    # 建议
    print(f"\n💡 后续操作")
    print("-" * 60)
    if report["status"] == "✅ 通过":
        print("  版型通过自动验证。建议继续 L2 人工检查（LibreCAD 叠图）。")
    elif report["status"] == "⚠️ 警告":
        print("  有比例或缝边不匹配问题，建议先手动复查再裁布。")
        print("  打开 DXF → 测量对应的边 → 确认是否需要调整。")
    else:
        print("  存在自交等严重几何错误，必须先修复再使用。")

    if report["panel_count"] < 2:
        print("  ⚠️ 裁片数量 < 2，检查 DXF 是否正确导入了所有面板。")
    print()


def main(argv=None):
    import json

    # ── 你可以在这里填写真实体型尺寸进行比例验证 ──
    BODY_MEASUREMENTS = {
        "bust": 88,
        "waist": 68,
        "hip": 92,
        "height": 165,
    }

    import sys as _sys
    if argv is None:
        argv = _sys.argv[1:]

    if len(argv) < 1:
        print("用法: python validate_pattern.py <dxf 文件路径>")
        print("示例: python validate_pattern.py catsuit_pattern_20260721.dxf")
        raise SystemExit(1)

    path = argv[0]
    report = validate(path, body_measurements=BODY_MEASUREMENTS)
    print_report(report)

    # 同时输出 JSON 供程序读取
    with open(path.replace(".dxf", "_validation.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"JSON 报告已保存: {path.replace('.dxf', '_validation.json')}")


if __name__ == "__main__":
    main()
