# -*- coding: utf-8 -*-
"""
星枢 观测报告生成器 (PRD 3.7)
序列结束/手动触发 → 汇总设备数据 → 中文Markdown报告(含AI优化建议) → reports/
"""
import asyncio, json, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)


async def _get(path: str):
    import httpx
    from utils.config import CFG
    base = f'http://{CFG.get("NINA_API_HOST","127.0.0.1")}:{CFG.get("NINA_API_PORT","1888")}/v2/api'
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(base + path)
            return r.json().get("Response", {}) if r.status_code == 200 else {}
    except Exception:
        return {}


def _fmt(v, unit=""):
    if v is None or (isinstance(v, float) and v != v):  # None或NaN
        return "-"
    if isinstance(v, float):
        return f"{v:.2f}{unit}"
    return f"{v}{unit}"


def _num(v):
    """数值或NaN→None"""
    if isinstance(v, float) and v != v:
        return None
    if isinstance(v, (int, float)):
        return v
    return None


def _risk_badge(ok):
    return "✅" if ok else "⚠️"


async def build_report(ai_summary: bool = True) -> dict:
    """生成完整观测报告"""
    now = datetime.now()
    t0 = time.time()

    # 并行拉全量数据
    cam, mount, guider, wx, seq, equip = await asyncio.gather(
        _get("/equipment/camera/info"),
        _get("/equipment/mount/info"),
        _get("/equipment/guider/info"),
        _get("/equipment/weather/info"),
        _get("/sequence/state"),
        _get("/equipment/info"),
    )

    lines = []
    lines.append(f"# 🌌 星枢观测报告 · {now:%Y-%m-%d %H:%M}")
    lines.append("")
    lines.append(f"> 生成时间: {now:%Y年%m月%d日 %H:%M} · 数据来源: N.I.N.A 实时读取")
    lines.append("")

    # ═══ 设备状态总览 ═══
    lines.append("## 一、设备运行状态")
    lines.append("")
    lines.append("| 设备 | 状态 |")
    lines.append("|---|---|")
    dev_states = []
    for dev, key in [("相机", "Camera"), ("赤道仪", "Mount"), ("调焦座", "Focuser"),
                     ("滤镜轮", "FilterWheel"), ("导星", "Guider"), ("旋转器", "Rotator")]:
        d = (equip.get(key) or {})
        name = d.get("Name") or "未配置"
        connected = d.get("Connected")
        if connected is None:
            state = "未配置" if name in ("未配置", "", "No Device") else "在线"
        else:
            state = f"{_risk_badge(connected)} 已连接" if connected else "⚪ 未连接"
        lines.append(f"| {dev} | {state} ({name}) |")
        dev_states.append((dev, connected, name))
    online = sum(1 for _, c, _ in dev_states if c)
    lines.append("")
    lines.append(f"**在线设备: {online}/{len(dev_states)}**")
    lines.append("")

    # ═══ 拍摄统计 ═══
    lines.append("## 二、拍摄任务统计")
    lines.append("")
    if seq and isinstance(seq, dict):
        lines.append(f"- **序列状态**: {seq.get('Status', '-')}")
        lines.append(f"- **当前目标**: {seq.get('TargetName', '-')}")
        # 常见统计字段自适应
        for k, zh in [("ImageCount", "已拍张数"), ("ExposureCount", "曝光次数"),
                      ("TotalExposureTime", "累计曝光(秒)"), ("Progress", "进度"),
                      ("CurrentItem", "当前步骤"), ("EstimatedTime", "预计剩余")]:
            if seq.get(k) is not None:
                lines.append(f"- **{zh}**: {seq[k]}")
    else:
        lines.append("- 序列数据不可用(可能未启动或无活动序列)")
    lines.append("")

    # ═══ 星点质量 ═══
    lines.append("## 三、星点质量 (HFR/导星)")
    lines.append("")
    seqd = seq if isinstance(seq, dict) else {}
    hfr = cam.get("HFR") or seqd.get("HFR")
    if hfr:
        quality = "优秀" if hfr < 2.5 else ("良好" if hfr < 3.5 else "偏大,建议重新对焦")
        lines.append(f"- **HFR**: {hfr:.2f} ({quality})")
    rms_ra = guider.get("RAError") or guider.get("RMSRA")
    rms_de = guider.get("DEError") or guider.get("RMSDE")
    if rms_ra or rms_de:
        total_rms = ((rms_ra or 0)**2 + (rms_de or 0)**2) ** 0.5
        gq = "优秀" if total_rms < 0.8 else ("良好" if total_rms < 1.5 else "偏大,注意风载/导星参数")
        lines.append(f"- **导星 RMS**: RA {rms_ra or 0:.2f}\" / DE {rms_de or 0:.2f}\" → 总 {total_rms:.2f}\" ({gq})")
    if not hfr and not (rms_ra or rms_de):
        lines.append("- 本轮无对焦/导星数据(设备未连接或未开始拍摄)")
    lines.append("")

    # ═══ 温度 ═══
    lines.append("## 四、温度管理")
    lines.append("")
    temp = cam.get("Temperature")
    target = cam.get("TargetTemp")
    at_target = cam.get("AtTargetTemp")
    power = cam.get("CoolerPower")
    if _num(temp) is not None:
        lines.append(f"- **CCD温度**: {temp:.1f}℃ (目标 {target if target is not None else '-'}℃"
                     f"{' · ✅已达目标' if at_target else ' · ⏳降温中'})")
        if _num(power) is not None:
            warn = " ⚠️功率接近上限,检查散热" if power > 90 else ""
            lines.append(f"- **制冷功率**: {power:.0f}%{warn}")
    else:
        lines.append("- 相机温度不可读(未连接)")
    lines.append("")

    # ═══ 天气记录 ═══
    lines.append("## 五、天气快照")
    lines.append("")
    if wx:
        cloud = wx.get("CloudCover")
        safe = wx.get("SafeToOperate")
        lines.append(f"- 温度 {_fmt(_num(wx.get('Temperature')))}℃ · 湿度 {_fmt(_num(wx.get('Humidity')))}%"
                     f" · 云量 {_fmt(_num(cloud))}%"
                     f" · 风 {_fmt(_num(wx.get('WindSpeed')))}km/h(阵风{_fmt(_num(wx.get('WindGust')))})")
        lines.append(f"- 降雨率 {_fmt(_num(wx.get('RainRate')))} · 气压 {_fmt(_num(wx.get('Pressure')))}hPa"
                     f" · 露点 {_fmt(_num(wx.get('DewPoint')))}℃")
        if safe is not None:
            lines.append(f"- **安全判定**: {'✅ 安全' if safe else '⚠️ 不安全'}")
        if _num(cloud) is not None and cloud > 80:
            lines.append("- 💡 云量偏高,平场/校准帧优先,科学目标可等窗口")
    else:
        lines.append("- 天气数据不可用")
    lines.append("")

    # ═══ 赤道仪 ═══
    if mount:
        lines.append("## 六、赤道仪位置")
        lines.append("")
        lines.append(f"- 赤经 {mount.get('RightAscension','-')} · 赤纬 {mount.get('Declination','-')}")
        lines.append(f"- 地平高度 {mount.get('Altitude','-')}° · 方位角 {mount.get('Azimuth','-')}°")
        flip = mount.get("TimeToMeridianFlip")
        if isinstance(flip, (int, float)) and flip > 0:
            lines.append(f"- ⏱️ 距过中天翻转: {flip:.0f} 分钟")
        lines.append("")

    # ═══ AI 智能建议 ═══
    advice = []
    if isinstance(hfr, (int, float)) and hfr > 3.5:
        advice.append(f"HFR={hfr:.1f}偏大: 建议运行全自动对焦, 并检查镜筒受冷变形(碳筒需补偿)")
    if rms_ra and rms_de and (rms_ra**2 + rms_de**2)**0.5 > 1.5:
        advice.append("导星RMS偏大: 检查导星焦距/曝光(建议1-2s)/风载护罩, 必要时降低导星频率")
    if isinstance(power, (int, float)) and power > 90:
        advice.append("制冷功率>90%: 检查散热环境, 防止CCD结露(环境湿度高时回温要慢)")
    if _num(cloud) is not None and cloud > 85:
        advice.append("云量>85%: 建议拍校准帧或窄带, 或暂停等待窗口")
    if isinstance(wx.get("Humidity"), (int, float)) and wx["Humidity"] > 85:
        advice.append("湿度>85%: 开除露带, 收工时CCD回温防结露")
    if online == 0:
        advice.append("全部设备离线: 若在调试请先连接设备; 若收工请忽略")
    if not advice:
        advice.append("各项指标正常, 保持当前节奏即可 ✅")

    lines.append("## 七、AI 优化建议")
    lines.append("")
    for a in advice:
        lines.append(f"- 💡 {a}")
    lines.append("")
    lines.append("---")
    lines.append(f"*星枢 StarPivot · 报告生成耗时 {time.time()-t0:.1f}s · "
                 f"数据实时读取自 N.I.N.A Advanced-API*")

    content = "\n".join(lines)
    fname = REPORTS / f"观测报告_{now:%Y%m%d_%H%M}.md"
    fname.write_text(content, encoding="utf-8")
    return {"file": str(fname), "content": content}


# 手动触发: python report_builder.py
if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    r = asyncio.run(build_report())
    print(f"✅ 报告已生成: {r['file']}")
    print(r["content"][:800])
