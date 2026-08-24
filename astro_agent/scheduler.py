# -*- coding: utf-8 -*-
"""
星枢 观测日程 + 进度播报 后台引擎
- schedules.json 定义提醒(时间+动作)
- 每30s检查: 到点→查天气→生成提示→WS广播
- 序列运行时每N张播报进度
"""
import asyncio, json, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
SCHED_FILE = ROOT / "data" / "schedules.json"

_default = {
    "提醒": [
        {"名": "入夜检查", "时间": "19:30", "动作": "查天气+设备状态, 提示是否可以开始",
         "启用": True},
        {"名": "收工提醒", "时间": "04:00", "动作": "提醒停泊收工, 生成观测报告", "启用": False}
    ],
    "进度播报": {"每N张": 10, "每小时": True, "启用": True}
}
if not SCHED_FILE.exists():
    SCHED_FILE.parent.mkdir(exist_ok=True)
    SCHED_FILE.write_text(json.dumps(_default, ensure_ascii=False, indent=1), encoding="utf-8")

SCHED = json.loads(SCHED_FILE.read_text(encoding="utf-8"))


def save_sched():
    SCHED_FILE.write_text(json.dumps(SCHED, ensure_ascii=False, indent=1), encoding="utf-8")


async def _nina(path):
    import httpx
    from utils.config import CFG
    base = f'http://{CFG.get("NINA_API_HOST", "127.0.0.1")}:{CFG.get("NINA_API_PORT", "1888")}/v2/api'
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(base + path)
            return r.json().get("Response", {}) if r.status_code == 200 else {}
    except Exception:
        return {}


class Assistant:
    """被 main.py 注入: broadcast(type, payload) 推送到WS"""

    def __init__(self):
        self.broadcast = None      # async fn(type, data)
        self._fired = {}           # (名,日期) → True 防重复
        self._last_frame_count = None
        self._last_hour_report = None

    async def run_forever(self):
        while True:
            try:
                await self._tick()
            except Exception:
                pass
            await asyncio.sleep(25)

    async def _tick(self):
        # 历史库自动沉淀(序列在跑就入库)
        try:
            from astro_agent.history import auto_capture_from_nina
            await asyncio.to_thread(auto_capture_from_nina)
        except Exception:
            pass
        now = datetime.now()
        hm = f"{now:%H:%M}"
        today = f"{now:%Y-%m-%d}"

        # ═══ 定时提醒 ═══
        for a in SCHED.get("提醒", []):
            if not a.get("启用"):
                continue
            key = (a["名"], today)
            if self._fired.get(key):
                continue
            if a["时间"] <= hm:                     # 到点(过点也补一次)
                self._fired[key] = True
                await self._fire_reminder(a)

        # ═══ 进度播报 ═══
        pb = SCHED.get("进度播报", {})
        if pb.get("启用"):
            seq = await _nina("/sequence/state")
            if isinstance(seq, dict) and seq.get("Status") not in (None, "IDLE", "", "NoSequence"):
                await self._progress(seq, pb, now)

    async def _fire_reminder(self, a):
        # 天气+设备快照
        wx = await _nina("/equipment/weather/info")
        equip = await _nina("/equipment/info")
        cloud = wx.get("CloudCover")
        msg = {"类型": "提醒", "名": a["名"], "动作": a["动作"], "时间": f"{datetime.now():%H:%M}"}
        if isinstance(cloud, (int, float)) and cloud == cloud:
            safe = "✅ 适合" if cloud < 70 else "⚠️ 云量偏高"
            msg["天气"] = f"云量{cloud:.0f}% {safe} · 湿度{wx.get('Humidity', '-')}%"
        cams = equip.get("Camera", {}) if isinstance(equip, dict) else {}
        if isinstance(cams, dict):
            msg["设备"] = "相机已连" if cams.get("Connected") else "相机未连"
        if self.broadcast:
            await self.broadcast("提醒", msg)

    async def _progress(self, seq, pb, now):
        cnt = seq.get("ImageCount") or seq.get("CapturedImageCount") or 0
        every = pb.get("每N张", 10)
        if (isinstance(cnt, int) and cnt > 0 and every > 0
                and cnt // every != (self._last_frame_count or 0) // every):
            self._last_frame_count = cnt
            tgt = seq.get("TargetName", "当前目标")
            stats = seq.get("Average") or {}
            hfr = seq.get("HFR") or (stats.get("HFR") if isinstance(stats, dict) else None)
            msg = {"类型": "进度", "目标": tgt, "已拍": f"{cnt}张",
                   "HFR": f"{hfr:.2f}" if isinstance(hfr, (int, float)) else "-",
                   "状态": seq.get("Status", "")}
            if self.broadcast:
                await self.broadcast("进度", msg)
            return
        # 每小时整点播报
        if pb.get("每小时") and now.minute < 25 and self._last_hour_report != now.hour:
            self._last_hour_report = now.hour
            if self.broadcast:
                await self.broadcast("进度", {"类型": "整点报时", "时间": f"{now:%H:%M}",
                                              "目标": seq.get("TargetName", ""),
                                              "已拍": f"{seq.get('ImageCount', '?')}张"})


assistant = Assistant()
