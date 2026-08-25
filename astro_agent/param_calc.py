# -*- coding: utf-8 -*-
"""
星枢 拍摄参数计算器 — 目标×器材×环境 → 中文参数建议
纯本地计算, 供 calc_params 工具调用
"""
import json, math
from pathlib import Path

ROOT = Path(__file__).parent.parent
TARGETS = {t["名"]: t for t in json.loads(
    (ROOT / "data" / "targets.json").read_text(encoding="utf-8"))["目标"]}

# 常见相机传感器 (宽mm, 高mm, 像元μm) — 覆盖主流天文相机
SENSORS = {
    "IMX571(2600MM/585MC)": (23.5, 15.7, 3.76),
    "IMX571裁切4/3": (17.7, 13.4, 3.76),
    "IMX294": (19.1, 13.0, 4.63),
    "IMX533(533MM/MC)": (17.9, 15.5, 3.76),
    "IMX585": (11.2, 6.3, 2.9),
    "IMX462": (5.6, 3.2, 2.9),
    "IMX224": (4.6, 3.6, 3.75),
    "IMX178": (7.4, 4.96, 2.4),
    "IMX294小微": (19.1, 13.0, 4.63),
    "ASI120": (5.8, 3.9, 3.75),
    "QHY5III462": (5.6, 3.2, 2.9),
    "未知/手动输入": (15.9, 12.0, 3.8),   # APS-C默认
}


def find_target(name: str):
    """模糊匹配目标名"""
    name = name.upper().replace(" ", "")
    for k, v in TARGETS.items():
        # 匹配编号部分(M31/NGC7380/IC405...)
        code = k.split()[0].upper()
        if code == name or name in k.upper().replace(" ", ""):
            return k, v
    return None, None


def calc(target_name: str, focal_mm: float = 750,
         sensor: str = "未知/手动输入", gain_hint: str = "",
         seeing: str = "一般", light_pollution: str = "郊区"):
    """主计算"""
    k, tg = find_target(target_name)
    if not tg:
        return {"错误": f"星表中未找到'{target_name}'", "提示": "试试 M31/NGC7380/IC405 等编号"}

    w, h, pix = SENSORS.get(sensor, SENSORS["未知/手动输入"])

    # ═══ 视场 ═══
    fov_w = math.degrees(math.atan(w / focal_mm)) * 60   # 角分
    fov_h = math.degrees(math.atan(h / focal_mm)) * 60
    fov_diag = math.hypot(fov_w, fov_h)
    size = tg["尺寸角分"]

    if size > fov_diag * 1.3:
        fit = "❌ 目标比视场大, 框不全 — 换更短焦或拼接"
    elif size < fov_diag * 0.15:
        fit = "❌ 目标在视场里太小 — 换更长焦或加增距"
    elif size < fov_diag * 0.35:
        fit = "⚠️ 目标偏小, 构图偏空(可接受, 焦点更集中)"
    elif size > fov_diag * 0.95:
        fit = "⚠️ 目标撑满视场, 边缘可能裁切"
    else:
        fit = "✅ 焦段匹配, 构图舒适"

    # ═══ 采样率(像素比例尺) ═══
    scale = 206265 * pix / (focal_mm * 1000)  # 角秒/像素
    seeing_map = {"优异": 1.2, "良好": 1.8, "一般": 2.5, "差": 4.0}
    seeing_as = seeing_map.get(seeing, 2.5)
    if scale < seeing_as / 3:
        samp = f"欠采样({scale:.2f}\"/px, 导星有余)— 可bin2提信噪比"
    elif scale > seeing_as * 2.5:
        samp = f"过采样({scale:.2f}\"/px)— 浪费视场, 建议短焦或bin"
    else:
        samp = f"采样合适({scale:.2f}\"/px vs 视宁度~{seeing_as}\")"

    # ═══ 曝光建议 ═══
    lp_map = {"波特尔1-2(荒野)": ("宽带", 300, 1), "波特尔3-4(郊野)": ("宽带", 180, 1.3),
              "郊区": ("宽带", 120, 1.6), "城市边缘": ("窄带", 300, 2),
              "城市": ("窄带", 300, 2.5)}
    mode, base_exp, lp_factor = lp_map.get(light_pollution, ("宽带", 120, 1.6))

    is_nb = "窄带" in tg["滤镜"] or "Ha" in tg["滤镜"]
    if is_nb:
        mode = "窄带(Ha/OIII)"
        exp = 300
        gain_txt = "增益100-120(高增益档, 读噪低)"
    else:
        exp = int(base_exp * lp_factor)
        gain_txt = "增益90-110 或 ISO400-800"

    if "星团" in tg["类型"]:
        exp = min(exp, 120)
    if "星系" in tg["类型"] and mode.startswith("宽带"):
        exp = max(exp, 180)

    # ═══ 总曝光时长(按类型经验值) ═══
    hours_map = {"星系": (8, 15), "星云": (6, 12), "行星状星云": (4, 8),
                 "疏散星团": (2, 4), "球状星团": (2, 5), "超新星遗迹": (10, 20),
                 "暗星云": (8, 15)}
    h_lo, h_hi = hours_map.get(tg["类型"], (5, 10))

    n_frames_lo = int(h_lo * 3600 / exp)
    n_frames_hi = int(h_hi * 3600 / exp)
    per_night = int(4 * 3600 / exp)   # 一晚约4h有效曝光

    return {
        "目标": k, "类型": tg["类型"], "角尺寸": f'{size}′',
        "器材": f"{focal_mm}mm + {sensor}",
        "视场": f"{fov_w:.1f}′ × {fov_h:.1f}′",
        "焦段匹配": fit,
        "采样": samp,
        "拍摄模式": mode,
        "单帧曝光": f"{exp}秒",
        "增益": gain_txt,
        "滤镜": tg["滤镜"],
        "总时长": f"{h_lo}-{h_hi}小时({'单晚可成' if h_lo <= 4 else '建议多晚累积'})",
        "帧数": f"{n_frames_lo}-{n_frames_hi}张(每张{exp}s)",
        "单晚参考": f"一晚约{per_night}张 — {'✅ 一晚拍够' if per_night >= n_frames_lo else '需' + str(math.ceil(n_frames_lo / per_night)) + '晚'}",
        "进阶提示": "Dither每3-5帧一次; 导星RMS控制在1.5″内; 每晚补拍暗场/平场",
    }


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    r = calc("M31", 750, "IMX571(2600MM/585MC)")
    for k, v in r.items():
        print(f"  {k}: {v}")

def match_camera(focal_mm: float, seeing_as: float = 2.0) -> dict:
    """相机×焦段匹配推荐: 给定焦距,排出各相机的采样率/视场/适配结论"""
    import math
    rows = []
    for name, (w, h, px) in SENSORS.items():
        scale = 206.3 * px / focal_mm
        fov_w = w / focal_mm * 57.3 * 60
        fov_h = h / focal_mm * 57.3 * 60
        ratio = scale / seeing_as
        if ratio < 0.5:
            verdict = "欠采样 — 建议bin2(等效采样翻倍,信噪比提升)"
        elif ratio > 2.5:
            verdict = "过采样 — 视场浪费,适合短焦目标或像元合并"
        else:
            verdict = "✅ 采样合适(经典区间1-2x视宁度)"
        rows.append({"相机": name, "像元μm": px, "采样角秒": round(scale, 2),
                     "视场": f"{fov_w:.1f}×{fov_h:.1f}'", "结论": verdict})
    rows.sort(key=lambda r: abs(r["采样角秒"] / seeing_as - 1.2))
    best = rows[0]
    return {"焦距": focal_mm, "视宁度假设": f"~{seeing_as}\"",
            "最佳匹配": str(best["相机"]) + " (采样 " + str(best["采样角秒"]) + '"/px)',
            "全表": rows[:10],
            "提示": "排序按与最佳采样的接近度; 实际以当地视宁度为准(郊区2-3\",山顶1-1.5\")"}
