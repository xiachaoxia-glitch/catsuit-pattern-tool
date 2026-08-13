"""版型生成器测试"""
import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import generate_catsuit_pattern as gen
from generate_catsuit_pattern import (
    bezier3,
    bezier_chain,
    build_front_panel,
    build_back_panel,
    build_gusset,
    build_zipper_placket,
)
from ezdxf.math import Vec2


class TestBezier:
    def test_bezier3_endpoints(self):
        p0, p3 = Vec2(0, 0), Vec2(10, 10)
        c1, c2 = Vec2(3, 1), Vec2(7, 9)
        assert bezier3(0.0, p0, c1, c2, p3) == p0
        assert bezier3(1.0, p0, c1, c2, p3) == p3

    def test_bezier_chain_returns_points(self):
        pts = [Vec2(0, 0), Vec2(1, 1), Vec2(2, 1), Vec2(3, 0)]
        out = bezier_chain(pts, steps=10)
        assert len(out) == 11  # steps + 1
        assert out[0] == pts[0]
        assert out[-1] == pts[-1]


class TestPanels:
    def test_front_panel_returns_points(self):
        pts, k = build_front_panel(gen.M)
        assert len(pts) > 10
        assert "shoulder" in k
        assert "hem" in k
        assert "crotch" in k

    def test_back_panel_returns_points(self):
        front_pts, front_k = build_front_panel(gen.M)
        pts, k = build_back_panel(gen.M, front_k)
        assert len(pts) > 10

    def test_gusset_is_diamond(self):
        pts = build_gusset(gen.M)
        assert len(pts) == 4
        # 对称性：左右关于 Y 轴对称
        assert abs(pts[0].x) == abs(pts[2].x)
        assert pts[0].y > 0 and pts[2].y < 0

    def test_zipper_placket_is_rectangle(self):
        pts = build_zipper_placket(gen.M)
        assert len(pts) == 4
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        assert min(xs) == -20.0 and max(xs) == 20.0
        assert max(ys) == 0.0  # 从 0 向下延伸


class TestDXFGeneration:
    def test_generate_dxf_file(self, tmp_path):
        """实际生成 DXF 并检查文件存在、可读取"""
        import os
        import ezdxf

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            gen.main()
            files = list(tmp_path.glob("catsuit_pattern_*.dxf"))
            assert len(files) == 1
            doc = ezdxf.readfile(str(files[0]))
            msp = doc.modelspace()
            # 应该有裁片图层
            assert "裁片" in doc.layers
            # 应该至少有 4 个闭合多段线裁片
            polylines = [e for e in msp if e.dxftype() == "LWPOLYLINE"]
            assert len(polylines) >= 4
        finally:
            os.chdir(old_cwd)
