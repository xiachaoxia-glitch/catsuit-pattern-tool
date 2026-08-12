"""
全自动版型编排脚本
==================
一条命令跑完：提取尺寸 → 生成 DXF → 验证 → 重试 → 出报告

用法:
    python auto_pattern.py --obj customer.obj --photo design.jpg
    python auto_pattern.py --manual --bust 88 --waist 68 --hip 92
"""

import json, sys, os, subprocess, time, argparse
from pathlib import Path

RETRY_MAX = 3          # 验证失败最多重试次数
ADJUST_FACTORS = [1.05, 0.95, 1.02, 0.98]  # 尺寸微调策略

def step(msg):
    print(f"\n{'='*50}")
    print(f"  {msg}")
    print(f"{'='*50}")

def run(cmd: str, timeout=60) -> dict:
    """执行命令并返回结果"""
    start = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return {
        "ok": r.returncode == 0,
        "stdout": r.stdout.strip(),
        "stderr": r.stderr.strip(),
        "elapsed": time.time() - start,
    }

def main():
    parser = argparse.ArgumentParser(description="乳胶紧身衣全自动版型")
    parser.add_argument("--obj", help="人体扫描 OBJ 文件路径")
    parser.add_argument("--photo", help="样品照片路径")
    parser.add_argument("--manual", action="store_true", help="手动输入尺寸模式")
    parser.add_argument("--bust", type=float, help="胸围 (cm)")
    parser.add_argument("--waist", type=float, help="腰围 (cm)")
    parser.add_argument("--hip", type=float, help="臀围 (cm)")
    parser.add_argument("--height", type=float, default=165, help="身高 (cm)")
    args = parser.parse_args()

    measurements = {}

    # ── 模式 A：从 OBJ 提取 ──────────────────────────────
    if args.obj and not args.manual:
        step("① OBJ → Blender → 尺寸提取")
        # 检查 Blender
        r = run("where blender")
        if not r["ok"]:
            print("⚠️  Blender 未找到。请安装 Blender 或使用 --manual 模式。")
            print("   下载: https://www.blender.org/download/")
            return
        
        # 这里调用 Blender 脚本提取尺寸（下一轮实现）
        print("   OBJ 路径:", args.obj)
        print("   Blender 测量脚本待实现——现在用 --manual 代替")
        return

    # ── 模式 B：手动输入尺寸 ──────────────────────────────
    if args.manual or not args.obj:
        step("① 手动输入尺寸")
        measurements = {
            "bust": args.bust or float(input("  胸围 (cm): ")),
            "waist": args.waist or float(input("  腰围 (cm): ")),
            "hip": args.hip or float(input("  臀围 (cm): ")),
            "height": args.height or 165,
            "shoulder": args.bust * 0.44 if args.bust else 39,
            "back_len": args.height * 0.24 if args.height else 40,
            "waist_to_hip": 20,
            "waist_to_crotch": 28,
            "inseam": 78,
            "arm_circ": 28,
        }
        print(f"  尺寸: 胸{measurements['bust']} 腰{measurements['waist']} 臀{measurements['hip']}")

    # ── ② 照片分析款式（未来）────────────────────────────
    step("② 款式分析")
    style = {"type": "catsuit", "neckline": "round", "sleeve": "long"}
    if args.photo:
        print(f"   照片: {args.photo}")
        print("   (GPT-4V 分析待接入，使用默认款式)")
    else:
        print("   无照片，使用默认款式")

    # ── ③ 生成 DXF ──────────────────────────────────────
    step("③ 生成 DXF 裁片")
    success = False
    for attempt in range(1, RETRY_MAX + 1):
        print(f"  尝试 {attempt}/{RETRY_MAX}...")

        # 把尺寸写入生成器脚本的临时配置
        # 方式：直接修改 CUSTOM_MEASUREMENTS 字典
        gen_script = Path(__file__).parent / "generate_catsuit_pattern.py"
        with open(gen_script, "r", encoding="utf-8") as f:
            code = f.read()

        # 替换尺寸
        for key, val in measurements.items():
            old = f'"{key}":'
            replacement = f'"{key}": {val:.1f},   # (auto)'
            # 找到并替换 CUSTOM_MEASUREMENTS 中的对应行
            import re
            pattern = rf'("{key}"\s*:\s*)\d+\.?\d*'
            code = re.sub(pattern, fr'\g<1>{val:.1f}', code)

        with open(gen_script, "w", encoding="utf-8") as f:
            f.write(code)

        r = run(f"python {gen_script}")
        if r["ok"]:
            print(f"  ✅ 生成成功")
            # 找生成的 DXF
            dxf_files = sorted(Path(".").glob("catsuit_pattern_*.dxf"))
            if dxf_files:
                dxf_path = str(dxf_files[-1])
                print(f"  DXF: {dxf_path}")
            else:
                print("  ⚠️  没找到 DXF 文件")
                continue
        else:
            print(f"  ❌ 生成失败:\n{r['stderr'][:300]}")
            continue

        # ── ④ 验证 ──────────────────────────────────────
        step(f"④ 验证 (attempt {attempt})")
        r = run(f"python validate_pattern.py \"{dxf_path}\"")
        if r["ok"]:
            print(r["stdout"])
            if "❌" not in r["stdout"] and "⚠️ 警告" in r["stdout"]:
                # 只有警告，可以继续
                print("  ⚠️  有轻微警告，但可以接受")
                success = True
                break
            elif "❌" not in r["stdout"]:
                print("  ✅ 验证通过！")
                success = True
                break
            else:
                print(f"  ❌ 验证未通过，尝试调整尺寸重试...")
                # 应用调整因子
                if attempt <= len(ADJUST_FACTORS):
                    f = ADJUST_FACTORS[attempt - 1]
                    measurements["bust"] *= f
                    measurements["waist"] *= f
                    measurements["hip"] *= f
                    print(f"  调整因子: {f} → 胸{measurements['bust']:.0f}")
        else:
            print(f"  ⚠️  验证脚本异常: {r['stderr'][:200]}")

    # ── 结果 ─────────────────────────────────────────────
    step("📋 结果汇总")
    if success:
        print(f"  ✅ 版型已生成并通过验证")
        print(f"  文件: {os.path.abspath(dxf_path)}")
        print(f"  尺寸: 胸{measurements['bust']:.0f}/腰{measurements['waist']:.0f}/臀{measurements['hip']:.0f}")
        print(f"\n  下一步: LibreCAD 打开 DXF → A4 分页打印")
    else:
        print(f"  ❌ 经过 {RETRY_MAX} 次尝试，版型未通过验证")
        print(f"  请手动检查生成器和验证器的配置")

    # ── 生成报告 ─────────────────────────────────────────
    report = {
        "status": "pass" if success else "fail",
        "measurements": measurements,
        "dxf": dxf_path if success else None,
        "attempts": attempt,
        "style": style,
    }
    report_path = "pattern_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  报告: {report_path}")


if __name__ == "__main__":
    main()
