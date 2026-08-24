# -*- coding: utf-8 -*-
"""
星枢 观测规划引擎 — "今晚拍什么"
纯本地天文计算(无依赖): 目标高度角/最佳时段/月相/评分排序
"""
import json, math
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
TARGETS = json.loads((ROOT / "data" / "targets.json").read_text(encoding="utf-8"))["目标"]


# ═══════════ 天文计算(简化算法, 精度~1°, 够选目标用) ═══════════
def _julian(dt: datetime) -> float:
    y, m = dt.year, dt.month
    if m <= 2:
        y, m = y - 1, m + 12
    d = dt.day + (dt.hour + dt.minute / 60 + dt.second / 3600) / 24
    a = y // 100
    b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5


def _sun_position(dt):
    """太阳赤经赤纬(度)"""
    jd = _julian(dt) - 2451545.0
    L = (280.460 + 0.9856474 * jd) % 360
    g = math.radians((357.528 + 0.9856003 * jd) % 360)
    lam = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439 - 0.0000004 * jd)
    ra = math.degrees(math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))) % 360
    dec = math.degrees(math.asin(math.sin(eps) * math.sin(lam)))
    return ra, dec


def _moon_position(dt):
    """月亮赤经赤纬(度) — 简化"""
    jd = _julian(dt) - 2451545.0
    L = math.radians((218.316 + 13.176396 * jd) % 360)
    M = math.radians((134.963 + 13.064993 * jd) % 360)
    F = math.radians((93.272 + 13.229350 * jd) % 360)
    lam = L + math.radians(6.289 * math.sin(M))
    beta = math.radians(5.128 * math.sin(F))
    eps = math.radians(23.439)
    ra = math.degrees(math.atan2(math.sin(lam) * math.cos(eps) - math.tan(beta) * math.sin(eps),
                                  math.cos(lam))) % 360
    dec = math.degrees(math.asin(math.sin(beta) * math.cos(eps) +
                                  math.cos(beta) * math.sin(eps) * math.sin(lam)))
    return ra, dec


def moon_phase(dt):
    """月相: 返回(相位0-1, 文本) 0=新月 0.5=满月"""
    sun_ra, _ = _sun_position(dt)
    moon_ra, _ = _moon_position(dt)
    elong = (moon_ra - sun_ra) % 360
    phase = elong / 360
    if phase < 0.05 or phase > 0.95:
        txt = "新月(全黑, 深空黄金期)"
    elif abs(phase - 0.5) < 0.1:
        txt = "满月(亮, 只适合窄带/行星)"
    elif phase < 0.5:
        txt = f"娥眉月(月龄{phase*29.5:.0f}天, 傍晚西天)"
    else:
        txt = f"盈凸/亏凸月(月龄{phase*29.5:.0f}天)"
    return phase, txt


def _lst(dt, lon):
    """本地恒星时(度)"""
    jd = _julian(dt)
    t = (jd - 2451545.0) / 36525
    gmst = 280.46061837 + 360.98564736629 * (jd - 2451545.0) + 0.000387933 * t * t
    return (gmst + lon) % 360


def altaz(ra, dec, dt, lat, lon):
    """目标高度角(度)"""
    ha = math.radians((_lst(dt, lon) - ra) % 360)
    dec_r = math.radians(dec)
    lat_r = math.radians(lat)
    alt = math.degrees(math.asin(
        math.sin(lat_r) * math.sin(dec_r) + math.cos(lat_r) * math.cos(dec_r) * math.cos(ha)))
    return alt


def angular_sep(ra1, dec1, ra2, dec2):
    """两天体角距(度)"""
    ra1, dec1, ra2, dec2 = map(math.radians, (ra1, dec1, ra2, dec2))
    cosd = (math.sin(dec1) * math.sin(dec2) +
            math.cos(dec1) * math.cos(dec2) * math.cos(ra1 - ra2))
    return math.degrees(math.acos(max(-1, min(1, cosd))))


def meridian_passage(ra_deg, dec_deg, lat, lon, now=None):
    """目标过中天时刻+峰值高度(18:00-次日06:00逐10分扫)"""
    now = now or datetime.now()
    best_t, best_alt = None, -99
    t = now.replace(hour=18, minute=0, second=0, microsecond=0)
    for _ in range(73):
        alt = altaz(ra_deg, dec_deg, t, lat, lon)
        if alt > best_alt:
            best_alt, best_t = alt, t
        t += timedelta(minutes=10)
    return best_t, best_alt


def sun_alt(dt, lat, lon):
    ra, dec = _sun_position(dt)
    return altaz(ra, dec, dt, lat, lon)


# ═══════════ 评分与推荐 ═══════════
def tonight(lat: float = 40.0, lon: float = 116.0, top_n: int = 8,
            focal: str = "") -> dict:
    """核心入口: 返回今晚推荐清单"""
    now = datetime.now()
    tonight_20 = now.replace(hour=20, minute=0, second=0, microsecond=0)
    tonight_23 = now.replace(hour=23, minute=0, second=0, microsecond=0)
    month = now.month

    # 月相+月亮位置(角距避让用)
    phase, phase_txt = moon_phase(now)
    moon_up = abs(phase - 0.5) < 0.25   # 接近满月的窗口
    mra, mdec = _moon_position(now.replace(hour=21))   # 21点月亮位置

    # 太阳落山估算(高度角=-12民用暮光)
    sunset = None
    t = now.replace(hour=16, minute=0)
    for _ in range(600):
        if sun_alt(t, lat, lon) < -12:
            sunset = t
            break
        t += timedelta(minutes=3)

    results = []
    for tg in TARGETS:
        ra = tg["赤经"]   # v2.0起星表统一为度值
        # 高度角: 20点和23点采样
        alt20 = altaz(ra, tg["赤纬"], tonight_20, lat, lon)
        alt23 = altaz(ra, tg["赤纬"], tonight_23, lat, lon)
        best_alt = max(alt20, alt23)
        # 中天窗口+月角距
        mer_t, mer_alt = meridian_passage(ra, tg["赤纬"], lat, lon, now)
        moon_sep = angular_sep(ra, tg["赤纬"], mra, mdec)

        if best_alt < 25:   # 太低不推
            continue

        # 正季判定(季跨年如[11,3])
        s, e = tg["最佳季"]
        in_season = (s <= month <= e) if s <= e else (month >= s or month <= e)

        # 评分
        score = 0
        score += min(best_alt, 70) * 0.8            # 高度权重
        score += 15 if in_season else 0              # 正季加权
        score += tg["易拍度"] * 2.5                  # 好拍加权
        if moon_up and "窄带" in tg["滤镜"]:
            score += 8                                # 月亮天窄带目标加分
        if moon_up and tg["滤镜"] == "LRGB":
            score -= 12                               # 满月毁宽带
        if moon_sep < 15:
            score -= 15                               # 月亮就在旁边, 重罚
        elif moon_sep < 30:
            score -= 6                                # 月光近距干扰

        results.append({
            "名": tg["名"], "类型": tg["类型"],
            "高度角20点": round(alt20), "高度角23点": round(alt23),
            "最佳时段": (f"{mer_t:%H:%M}过中天(峰值{mer_alt:.0f}°)" if mer_t else "-"),
            "月距": f"{moon_sep:.0f}°" + (" ⚠️月旁" if moon_sep < 20 else ""),
            "正季": "✅" if in_season else "—",
            "易拍": "★" * tg["易拍度"],
            "焦段": tg["焦段"], "滤镜": tg["滤镜"],
            "备注": tg["备注"], "得分": round(score, 1),
        })

    results.sort(key=lambda x: -x["得分"])
    return {
        "日期": f"{now:%Y-%m-%d}",
        "月相": phase_txt,
        "月相相位": round(phase, 2),
        "天黑约": f"{sunset:%H:%M}" if sunset else "计算中",
        "推荐数": min(top_n, len(results)),
        "清单": results[:top_n],
        "总可见": len(results),
        "提示": "高度角>25°才入选; 得分=高度+正季+易拍度+月相适配",
    }


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    r = tonight()
    print(f"🌌 {r['日期']} 今晚拍什么 · 月相: {r['月相']} · 天黑约{r['天黑约']}")
    print(f"   可见目标{r['总可见']}个, TOP{r['推荐数']}推荐:\n")
    for i, t in enumerate(r["清单"], 1):
        print(f"{i}. {t['名']} [{t['类型']}] {t['正季']} {t['易拍']}")
        print(f"   高度: 20点{t['高度角20点']}° / 23点{t['高度角23点']}° | {t['焦段']}mm | {t['滤镜']}")
        print(f"   {t['备注']} | 得分{t['得分']}")
