"""几何基础函数测试"""
import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from validate_pattern import (
    distance,
    polyline_length,
    orientation,
    on_segment,
    segments_intersect,
    check_self_intersection,
    find_matching_edges,
)


class TestGeometry:
    def test_distance(self):
        assert distance((0, 0), (3, 4)) == 5.0
        assert distance((0, 0), (0, 0)) == 0.0

    def test_polyline_length(self):
        # 3-4-5 直角三角形的两条直角边
        pts = [(0, 0), (3, 0), (3, 4)]
        assert polyline_length(pts) == 7.0

    def test_orientation(self):
        # 逆时针
        assert orientation((0, 0), (1, 0), (1, 1)) == 1
        # 顺时针
        assert orientation((0, 0), (1, 1), (1, 0)) == 2
        # 共线
        assert orientation((0, 0), (1, 1), (2, 2)) == 0

    def test_on_segment(self):
        # q=(1,1) 在 p=(0,0) 和 r=(2,2) 的包围盒内
        assert on_segment((0, 0), (1, 1), (2, 2)) is True
        # q=(3,3) 在 p=(0,0) 和 r=(2,2) 的包围盒外
        assert on_segment((0, 0), (3, 3), (2, 2)) is False

    def test_segments_intersect_cross(self):
        # 十字交叉
        assert segments_intersect((0, 0), (2, 2), (0, 2), (2, 0)) is True

    def test_segments_intersect_parallel(self):
        # 平行不交
        assert segments_intersect((0, 0), (2, 0), (0, 1), (2, 1)) is False

    def test_segments_intersect_share_endpoint(self):
        # 共享端点
        assert segments_intersect((0, 0), (2, 2), (2, 2), (4, 0)) is True


class TestSelfIntersection:
    def test_square_not_self_intersecting(self):
        # 正方形不自交
        pts = [(0, 0), (10, 0), (10, 10), (0, 10)]
        assert check_self_intersection(pts) is False

    def test_bowtie_self_intersecting(self):
        # 蝴蝶结形状自交
        pts = [(0, 0), (10, 10), (10, 0), (0, 10)]
        assert check_self_intersection(pts) is True

    def test_triangle_not_self_intersecting(self):
        pts = [(0, 0), (10, 0), (5, 10)]
        assert check_self_intersection(pts) is False

    def test_few_points_no_intersection(self):
        assert check_self_intersection([(0, 0), (1, 1)]) is False


class TestFindMatchingEdges:
    def test_matching_edges_no_issue(self):
        # 两条等长边，不应报告 seam_mismatch
        panels = {
            "A": [(0, 0), (0, 50), (50, 50), (50, 0)],
            "B": [(0, 0), (0, 52), (52, 52), (52, 0)],
        }
        issues = find_matching_edges(panels, tolerance=5.0)
        seam_issues = [i for i in issues if i["type"] == "seam_mismatch"]
        assert len(seam_issues) == 0

    def test_mismatched_edges_reported(self):
        # 两条接近但差超过容差的边（50 vs 62，差12 > 容差5 且 < 30%），应报告
        panels = {
            "A": [(0, 0), (0, 50), (50, 50), (50, 0)],
            "B": [(0, 0), (0, 62), (62, 62), (62, 0)],
        }
        issues = find_matching_edges(panels, tolerance=5.0)
        seam_issues = [i for i in issues if i["type"] == "seam_mismatch"]
        assert len(seam_issues) >= 1
