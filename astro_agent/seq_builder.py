# -*- coding: utf-8 -*-
"""NINA序列构造器: 从验证过的模板克隆DSO容器 → POST进NINA
用法: setup_sequence('狮子星云', exposure=300, count=20, filter='Ha')
坐标自动从星表targets.json查(度→时分秒转换)"""
import json, copy, time
from pathlib import Path

ROOT = Path(__file__).parent.parent
B = "http://127.0.0.1:1888/v2/api"

def _load_template():
    return json.load(open(ROOT / "data" / "seq_template.json", encoding="utf-8-sig"))

def _reid(o, start=1000):
    """重编$id/$ref防冲突"""
    idmap = {}
    counter = [start]
    def scan(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "$id":
                    idmap[v] = "n" + str(counter[0]); counter[0] += 1
                scan(v)
        elif isinstance(x, list):
            for i in x: scan(i)
    scan(o)
    def fix(x):
        if isinstance(x, dict):
            r = {}
            for k, v in x.items():
                if k == "$id": r["$id"] = idmap[v]
                elif k == "$ref": r["$ref"] = idmap.get(v, v)
                else: r[k] = fix(v)
            return r
        if isinstance(x, list): return [fix(i) for i in x]
        return x
    return fix(o)

def _find_type(o, tkey):
    if isinstance(o, dict):
        if tkey in str(o.get("$type", "")): return o
        if "$values" in o and isinstance(o.get("$values"), list):
            for x in o["$values"]:
                r = _find_type(x, tkey)
                if r: return r
        for v in o.values():
            r = _find_type(v, tkey)
            if r: return r
    elif isinstance(o, list):
        for x in o:
            r = _find_type(x, tkey)
            if r: return r
    return None

def _strip_plugins(o):
    if isinstance(o, dict):
        if "Items" in o and isinstance(o.get("Items"), dict) and "$values" in o["Items"]:
            o["Items"]["$values"] = [i for i in o["Items"]["$values"]
                if "DiscordAlert" not in str(i.get("$type", "")) and "RemoteCopy" not in str(i.get("$type", ""))]
        for v in o.values(): _strip_plugins(v)
    elif isinstance(o, list):
        for x in o: _strip_plugins(x)

def _find_target(name):
    data = json.load(open(ROOT / "data" / "targets.json", encoding="utf-8"))["目标"]
    for t in data:
        if name in t["名"] or t["名"].startswith(name):
            return t
    return None

def setup_sequence(target_name: str, exposure: int = 300, count: int = 20,
                   filter_name: str = None, gain: int = None):
    """配置NINA拍摄序列(注入DSO+SmartExposure), 成功后NINA里可见"""
    import httpx
    tg = _find_target(target_name)
    if not tg:
        return {"状态": "失败", "原因": f"星表中没有'{target_name}'",
                "提示": "试试: 巫师星云/心脏星云/象鼻/M31 等星表内目标名"}
    # 度→时分秒
    ra_h_total = tg["赤经"] / 15.0
    ra_h = int(ra_h_total); ra_m = int(round((ra_h_total - ra_h) * 60))
    dec = tg["赤纬"]; dec_d = abs(int(dec)); dec_m = int(round((abs(dec) - dec_d) * 60))
    # 参数建议
    if filter_name is None:
        filter_name = "Ha" if "Ha" in tg.get("滤镜", "") else None
    if gain is None:
        gain = 100 if filter_name else 120
    tpl = _load_template()
    items = tpl["Items"]
    vals = items[2]["$values"] if isinstance(items, list) else items["$values"]
    targets_area = next((v for v in vals if v.get("Name") == "Targets"), None)
    if not targets_area:
        return {"状态": "失败", "原因": "模板结构异常(Targets区缺失)"}
    dso_sample = targets_area["Items"]["$values"][0]
    d = _reid(copy.deepcopy(dso_sample))
    full_name = tg["名"]
    d["Name"] = full_name
    d["Target"]["TargetName"] = full_name
    ic = d["Target"]["InputCoordinates"]
    ic["RAHours"] = ra_h; ic["RAMinutes"] = ra_m; ic["RASeconds"] = 0.0
    ic["DecDegrees"] = dec_d if dec >= 0 else dec_d
    ic["DecMinutes"] = dec_m; ic["DecSeconds"] = 0.0
    ic["NegativeDec"] = dec < 0
    # 曝光参数
    te = _find_type(d, "TakeExposure")
    if te:
        te["ExposureTime"] = exposure
        if filter_name and "Filter" in te: te["Filter"] = filter_name
        if gain is not None and "Gain" in te: te["Gain"] = gain
    lc = _find_type(d, "LoopCondition")
    if lc: lc["Iterations"] = max(1, count // 5) if count > 5 else 1  # LoopCondition循环,每次5张
    se = _find_type(d, "SmartExposure")
    if se and "TotalExposureCount" in se: se["TotalExposureCount"] = min(count, 5)
    _strip_plugins(d)
    targets_area["Items"]["$values"] = [d]
    try:
        r = httpx.post(f"{B}/sequence/load", json=tpl, timeout=15)
        body = r.json()
        if body.get("Success"):
            total_h = exposure * count / 3600
            return {"状态": "成功",
                    "序列": f"{full_name}: {filter_name or '宽带'} {exposure}s × {count}张 (约{total_h:.1f}小时)",
                    "坐标": f"RA {ra_h}h{ra_m}m Dec {'+' if dec>=0 else '-'}{dec_d}°{dec_m}'",
                    "下一步": "序列已注入NINA! 在NINA序列界面确认后点开始,或对我说'开始序列'"}
        return {"状态": "失败", "原因": str(body.get("Error"))[:80],
                "提示": "请确认NINA已打开Advanced Sequence界面"}
    except Exception as e:
        return {"状态": "失败", "原因": f"NINA连接失败: {str(e)[:50]}",
                "提示": "确认NINA开着且Advanced-API插件启用"}

if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print(setup_sequence(sys.argv[1] if len(sys.argv) > 1 else "狮子星云"))
