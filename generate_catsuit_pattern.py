"""
乳胶紧身连体衣 打版 DXF 生成器
=================================
基于 ezdxf 库，根据人体尺寸自动生成基础裁片 DXF 文件。

用法:
    python generate_catsuit_pattern.py
    或在顶部修改 CUSTOM_MEASUREMENTS 字典

输出:
    catsuit_pattern_{日期}.dxf — 包含前片、后片、裆片、拉链贴条
"""

import math
import datetime
import sys
from typing import List, Tuple

# Windows 控制台 UTF-8 支持（否则 emoji 报 GBK 错误）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── 尝试导入 ezdxf，给出友好提示 ──────────────────────────────────
try:
    import ezdxf
    from ezdxf.math import Vec2
    from ezdxf.enums import TextEntityAlignment
except ImportError:
    print("❌ 需要 ezdxf 库。安装命令：pip install ezdxf")
    raise SystemExit(1)

# ====================================================================
# 客户尺寸 (cm)
# 在这里改数字就能适配不同客户
# ====================================================================
CUSTOM_MEASUREMENTS = {
    "bust":     88.0,   # 胸围
    "waist":    68.0,   # 腰围
    "hip":      92.0,   # 臀围
    "height":   165.0,  # 身高
    "neck":     36.0,   # 颈围
    "shoulder": 38.7,   # 肩宽
    "arm_len":  58.0,   # 臂长
    "arm_circ": 28.0,   # 上臂围
    "back_len": 39.6,   # 背长（第7颈椎→腰线）
    "waist_to_hip": 20.0,  # 腰→臀高
    "waist_to_crotch": 28.0,  # 腰→裆深（含裆）
    "inseam":   78.0,    # 内缝长（裆→脚踝）
    "wrist":    15.0,    # 腕围
    "ankle":    20.0,    # 脚踝围
}

# ── 从尺寸算出 1/4 围度（单侧裁片用）────────────────────────────
# 全部转成 mm（DXF 标准单位）
M = {k: v * 10 for k, v in CUSTOM_MEASUREMENTS.items()}
Q = {k: M[k] / 4.0 for k in ("bust", "waist", "hip", "neck")}
Q["arm_circ_half"] = M["arm_circ"] / 2.0

# 缝份 (mm) — 乳胶不锁边所以缝份需要多一些，或做对接缝
SEAM = 10.0

# ── DXF 单位 (4=mm, 5=cm) — 我们所有坐标用 mm
DXF_UNITS = 4

# ── 是否只画半边（镜像可以得到完整裁片）──────────────────────────
HALF_PATTERN = True

# ====================================================================
# 三阶 Bezier 曲线辅助 — 用于画光滑的袖窿、领口、裆弧
# ====================================================================
def bezier3(t: float, p0: Vec2, p1: Vec2, p2: Vec2, p3: Vec2) -> Vec2:
    """三次 Bezier 曲线上 t∈[0,1] 的点"""
    u = 1.0 - t
    return (u**3) * p0 + 3 * u * u * t * p1 + 3 * u * (t**2) * p2 + (t**3) * p3


def bezier_chain(
    pts: List[Vec2], steps: int = 20
) -> List[Vec2]:
    """把一组 [p0, c1, c2, p3, c4, c5, p6, ...] 控制点转成平滑折线。
    每 4 个点一组 (起点, 控制1, 控制2, 终点)。
    相邻段共享端点，不会重复添加。
    """
    out: List[Vec2] = []
    i = 0
    first_segment = True
    while i + 3 < len(pts):
        p0, p1, p2, p3 = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
        start_s = 0 if first_segment else 1  # 跳过重复端点
        for s in range(start_s, steps):
            t = s / steps
            out.append(bezier3(t, p0, p1, p2, p3))
        first_segment = False
        i += 3
    # 最后一个点
    if pts:
        out.append(pts[-1])
    return out


def add_polyline(
    msp,
    points: List[Vec2],
    layer: str = "裁片",
    color: int = 1,
    close: bool = False,
):
    """画一条多段线"""
    pl = msp.add_lwpolyline(
        points=[(p.x, p.y) for p in points],
        close=close,
        dxfattribs={"layer": layer, "color": color},
    )
    return pl


def add_dimension_line(
    msp,
    start: Vec2,
    end: Vec2,
    offset: float = 15.0,
    label: str = "",
    layer: str = "标注",
    color: int = 3,
):
    """画尺寸线 + 文字"""
    dx, dy = end.x - start.x, end.y - start.y
    length = math.hypot(dx, dy)
    # 垂直偏移方向
    nx, ny = -dy / length, dx / length if length > 0 else (0, 1)
    off = Vec2(nx * offset, ny * offset)
    a = start + off
    b = end + off
    msp.add_line(a, b, dxfattribs={"layer": layer, "color": color})
    # 引线
    msp.add_line(start, a, dxfattribs={"layer": layer, "color": color})
    msp.add_line(end, b, dxfattribs={"layer": layer, "color": color})
    # 尺寸文本
    mid = (a + b) * 0.5
    msp.add_text(
        label if label else f"{length:.0f}",
        height=3.0,
        dxfattribs={"layer": layer, "color": color},
    ).set_placement(mid, align=TextEntityAlignment.MIDDLE_CENTER)


def add_grid_reference(msp, origin: Vec2, label: str, color: int = 4):
    """在裁片原点画十字参考 + 标签"""
    r = 5.0
    msp.add_line(
        origin + Vec2(-r, 0),
        origin + Vec2(r, 0),
        dxfattribs={"layer": "参考", "color": color},
    )
    msp.add_line(
        origin + Vec2(0, -r),
        origin + Vec2(0, r),
        dxfattribs={"layer": "参考", "color": color},
    )
    msp.add_text(
        label,
        height=3.5,
        dxfattribs={"layer": "参考", "color": color},
    ).set_placement(
        origin + Vec2(0, -r - 5), align=TextEntityAlignment.MIDDLE_CENTER
    )


def mirror_points(pts: List[Vec2]) -> List[Vec2]:
    """对 Y 轴镜像 (x → -x)，返回新列表"""
    return [Vec2(-p.x, p.y) for p in pts]


# ====================================================================
# 前片 (Front Panel) — 右半，原点在腰线/前中线交点
# ====================================================================
def build_front_panel(m) -> Tuple[List[Vec2], dict]:
    """
    返回 (轮廓点列, 关键点字典) — 腰线以上用背长比例推算
    """
    q_bust = m["bust"] / 4
    q_waist = m["waist"] / 4
    q_hip = m["hip"] / 4
    q_neck = m["neck"] / 6

    bl = m["back_len"]          # 背长→肩颈点
    wh = m["waist_to_hip"]      # 腰到臀
    wc = m["waist_to_crotch"]   # 腰到裆
    ins = m["inseam"]           # 裆到脚踝

    shoulder_slope = 30.0       # 肩斜(mm)
    armhole_depth = 60.0        # 袖窿深(mm)
    neck_front_depth = 80.0     # 前领深(mm)
    crotch_extension = 40.0     # 裆底延伸(mm)

    # ── 关键点 (x=前中线, y=0 腰线)
    k = {}

    # 下摆 (脚踝高度)
    k["hem"] = Vec2(0, -(wc + ins))

    # 裆底
    k["crotch"] = Vec2(crotch_extension, -wc)

    # 臀围线
    k["hip"] = Vec2(q_hip, -wh)

    # 腰线 (原点)
    k["waist"] = Vec2(q_waist, 0)

    # 胸围线 (约在腰上 1/3 背长处)
    k["bust"] = Vec2(q_bust, bl * 0.35)

    # 前领底
    k["neck_front"] = Vec2(q_neck * 0.8, bl)

    # 前领深
    k["neck_depth"] = Vec2(0, bl - neck_front_depth)

    # 肩点
    shoulder_w = q_neck * 0.8 + m["shoulder"] / 2
    k["shoulder"] = Vec2(shoulder_w, bl - shoulder_slope)

    # 腋下 (袖窿底)
    k["armpit"] = Vec2(q_bust - 1, bl * 0.35 - armhole_depth)

    # ── 串联轮廓 (顺时针：领→肩→袖窿→侧缝→下摆→裆→前中→领)
    # 每条 Bezier 链共享端点，不会重复
    chain: List[Vec2] = []
    # 1) 前中线（领口到底边） — 直线，x=0
    chain.append(k["neck_depth"])
    # 2) 领口弧 (neck_depth → shoulder)
    neck_curve = bezier_chain([
        k["neck_depth"],
        Vec2(q_neck * 0.3, k["neck_depth"].y + (k["neck_front"].y - k["neck_depth"].y) * 0.3),
        Vec2(k["neck_front"].x + 10, k["neck_front"].y + 5),
        k["neck_front"],
        Vec2(k["shoulder"].x - 10, k["shoulder"].y),
        k["shoulder"],
    ])
    chain.extend(neck_curve)
    # 3) 袖窿弧 (shoulder → armpit)
    armhole = bezier_chain([
        k["shoulder"],
        Vec2(k["shoulder"].x - 20, k["shoulder"].y - armhole_depth * 0.5),
        Vec2(k["armpit"].x + 10, k["armpit"].y + 20),
        k["armpit"],
    ])
    chain.extend(armhole)
    # 4) 侧缝 (armpit → waist → hip → hem)
    # hem 是下摆中点 (x=0, y=-(wc+ins))
    side_seam = bezier_chain([
        k["armpit"],
        Vec2(k["bust"].x, k["armpit"].y - 30),
        Vec2(k["waist"].x + 5, k["waist"].y + 20),
        k["waist"],
        Vec2(k["hip"].x + 5, k["hip"].y - 10),
        Vec2(k["hem"].x + 15, k["hem"].y + 100),
        k["hem"],
    ])
    chain.extend(side_seam)
    # 5) 内缝 (hem → crotch) — 控制点始终在 crotch.y 以下
    inseam_span = abs(k["hem"].y - k["crotch"].y)  # 裆到踝的垂直距离
    inseam = bezier_chain([
        k["hem"],
        Vec2(k["hem"].x + 5, k["hem"].y + inseam_span * 0.35),
        Vec2(k["crotch"].x - 5, k["crotch"].y - inseam_span * 0.05),
        k["crotch"],
    ])
    chain.extend(inseam)
    # 6) 裆底回前中 — 沿水平走，不越过 crotch.y
    chain.append(Vec2(0, k["crotch"].y + crotch_extension * 0.3))
    # 7) 前中回到领口
    center_front = bezier_chain([
        Vec2(0, k["crotch"].y + crotch_extension * 0.3),
        Vec2(0, k["crotch"].y + crotch_extension * 0.15),
        Vec2(0, k["neck_depth"].y + 10),
        k["neck_depth"],
    ])
    chain.extend(center_front)

    # 去重 & 去 None
    pts = [p for p in chain if p is not None]

    return pts, k


# ====================================================================
# 后片 (Back Panel) — 后中缝比前片稍长, 领口更高
# ====================================================================
def build_back_panel(m, front_k) -> Tuple[List[Vec2], dict]:
    """基于前片调整出后片（不同的领口、肩宽，其余复用前片几何）"""
    bl = m["back_len"]
    neck_back_depth = 30.0  # 后领深(mm)

    k = dict(front_k)
    k["neck_depth"] = Vec2(0, bl - neck_back_depth)
    # 后肩稍宽
    if "shoulder" in k:
        k["shoulder"] = Vec2(k["shoulder"].x + 5, k["shoulder"].y)

    chain: List[Vec2] = []
    # 1) 后中线（领口到底边）
    chain.append(k["neck_depth"])
    # 2) 后领弧 (neck_depth → shoulder)
    neck_curve = bezier_chain([
        k["neck_depth"],
        Vec2(20, k["neck_depth"].y - 10),
        Vec2(k["neck_front"].x + 10, k["neck_front"].y + 5),
        k["neck_front"],
        Vec2(k["shoulder"].x - 10, k["shoulder"].y),
        k["shoulder"],
    ])
    chain.extend(neck_curve)
    # 3) 袖窿弧
    armhole = bezier_chain([
        k["shoulder"],
        Vec2(k["shoulder"].x - 20, k["shoulder"].y - 50),
        Vec2(k["armpit"].x + 10, k["armpit"].y + 20),
        k["armpit"],
    ])
    chain.extend(armhole)
    # 4) 侧缝
    side_seam = bezier_chain([
        k["armpit"],
        Vec2(k["bust"].x, k["armpit"].y - 30),
        Vec2(k["waist"].x + 5, k["waist"].y + 20),
        k["waist"],
        Vec2(k["hip"].x + 5, k["hip"].y - 10),
        Vec2(k["hem"].x + 15, k["hem"].y + 100),
        k["hem"],
    ])
    chain.extend(side_seam)
    # 5) 内缝
    inseam_span = abs(k["hem"].y - k["crotch"].y)
    inseam = bezier_chain([
        k["hem"],
        Vec2(k["hem"].x + 5, k["hem"].y + inseam_span * 0.35),
        Vec2(k["crotch"].x - 5, k["crotch"].y - inseam_span * 0.05),
        k["crotch"],
    ])
    chain.extend(inseam)
    # 6) 裆底回后中
    chain.append(Vec2(0, k["crotch"].y + 12))
    # 7) 后中回到领口
    center_back = bezier_chain([
        Vec2(0, k["crotch"].y + 12),
        Vec2(0, k["crotch"].y + 6),
        Vec2(0, k["neck_depth"].y + 10),
        k["neck_depth"],
    ])
    chain.extend(center_back)

    return [p for p in chain if p is not None], k


# ====================================================================
# 裆片 (Gusset / Crotch Panel) — 菱形, 前后连接
# ====================================================================
def build_gusset(m) -> List[Vec2]:
    """
    菱形裆片：宽 = 臀围/8, 长 = 裆深 × 0.6
    """
    w = m["hip"] / 8.0
    h = m["waist_to_crotch"] * 0.6
    return [
        Vec2(0, h),
        Vec2(w, 0),
        Vec2(0, -h),
        Vec2(-w, 0),
    ]


# ====================================================================
# 拉链贴条 (Zipper Placket)
# ====================================================================
def build_zipper_placket(m) -> List[Vec2]:
    """简单矩形贴条, 长=背长×1.1, 宽=40mm"""
    length = m["back_len"] * 1.1
    half_w = 20.0
    return [
        Vec2(-half_w, 0),
        Vec2(half_w, 0),
        Vec2(half_w, -length),
        Vec2(-half_w, -length),
    ]


# ====================================================================
# 主函数：生成 DXF
# ====================================================================
def main():
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = DXF_UNITS  # mm
    doc.layers.new("裁片", dxfattribs={"color": 1, "lineweight": 35})
    doc.layers.new("标注", dxfattribs={"color": 3, "lineweight": 15})
    doc.layers.new("参考", dxfattribs={"color": 4, "lineweight": 10})
    doc.layers.new("缝份", dxfattribs={"color": 2, "lineweight": 20, "linetype": "DASHED2"})
    msp = doc.modelspace()

    # ── 1. 前片 ────────────────────────────────────────────────
    front_pts, front_k = build_front_panel(M)
    origin_front = Vec2(100, 250)
    p_front = [origin_front + p for p in front_pts]
    add_polyline(msp, p_front, layer="裁片", color=1, close=True)
    add_grid_reference(msp, origin_front, "前片 Front")

    # 缝份线 (内偏 1cm 示意)
    seam_pts = [origin_front + Vec2(p.x - SEAM if p.x > 0 else p.x, p.y - 1.0) for p in front_pts]
    add_polyline(msp, seam_pts, layer="缝份", color=2, close=True)

    # 关键尺寸标注
    if "waist" in front_k and "hip" in front_k:
        add_dimension_line(
            msp, origin_front + front_k["waist"], origin_front + front_k["hip"],
            offset=25, label=f'腰→臀 {M["waist_to_hip"]/10:.0f}cm'
        )
    if "hem" in front_k and "crotch" in front_k:
        add_dimension_line(
            msp, origin_front + front_k["crotch"], origin_front + front_k["hem"],
            offset=-18, label=f'裆→踝 {M["inseam"]/10:.0f}cm'
        )

    # ── 2. 后片 ────────────────────────────────────────────────
    back_pts, back_k = build_back_panel(M, front_k)
    origin_back = Vec2(100 + 60, 250)  # 前片右侧 60mm
    p_back = [origin_back + p for p in back_pts]
    add_polyline(msp, p_back, layer="裁片", color=5, close=True)
    add_grid_reference(msp, origin_back, "后片 Back")

    # ── 3. 裆片 ────────────────────────────────────────────────
    gusset_pts = build_gusset(M)
    origin_gusset = Vec2(100 + 120, 250)
    p_gusset = [origin_gusset + p for p in gusset_pts]
    add_polyline(msp, p_gusset, layer="裁片", color=6, close=True)
    add_grid_reference(msp, origin_gusset, "裆片 Gusset")

    # ── 4. 拉链贴条 ────────────────────────────────────────────
    zipper_pts = build_zipper_placket(M)
    origin_zip = Vec2(100 + 140, 250)
    p_zip = [origin_zip + p for p in zipper_pts]
    add_polyline(msp, p_zip, layer="裁片", color=7, close=True)
    add_grid_reference(msp, origin_zip, "拉链贴条 Zipper")

    # ── 信息块 ──────────────────────────────────────────────────
    info_lines = [
        f"乳胶紧身连体衣 打版 DXF",
        f"生成日期: {datetime.date.today()}",
        f"尺寸: 胸{CUSTOM_MEASUREMENTS['bust']} 腰{CUSTOM_MEASUREMENTS['waist']} 臀{CUSTOM_MEASUREMENTS['hip']} 身高{CUSTOM_MEASUREMENTS['height']}",
        f"缝份: {SEAM}mm (虚线标注)",
        f"注意: 纸样为单侧轮廓，实际裁布需镜像+缝份",
        "单位: 毫米 (mm) — DXF INSUNITS=4",
    ]
    for i, line in enumerate(info_lines):
        msp.add_text(
            line,
            height=3.0,
            dxfattribs={"layer": "参考", "color": 4},
        ).set_placement(
            Vec2(10, 300 - i * 5), align=TextEntityAlignment.LEFT
        )

    # ── 保存 ────────────────────────────────────────────────────
    filename = f"catsuit_pattern_{datetime.date.today().strftime('%Y%m%d')}.dxf"
    doc.saveas(filename)
    print(f"✅ 已生成: {filename}")
    print(f"   尺寸: {CUSTOM_MEASUREMENTS['bust']}/{CUSTOM_MEASUREMENTS['waist']}/{CUSTOM_MEASUREMENTS['hip']} (胸/腰/臀)")
    print(f"   用 LibreCAD 或 Inkscape 打开后按 A4 分页打印。")


if __name__ == "__main__":
    main()
