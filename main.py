# -*- coding: utf-8 -*-
import sys, io
from pathlib import Path as _P

# windowed打包时stdout/stderr=None → uvicorn日志崩, 替换为null流(可随时丢弃)
class _Null:
    def write(self, *a): return 0
    def flush(self): pass
    def isatty(self): return False
    def close(self): pass

if sys.stdout is None: sys.stdout = _Null()
if sys.stderr is None: sys.stderr = _Null()
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
# -*- coding: utf-8 -*-
"""
星枢天文AI助手 — 主服务
FastAPI: /api/chat 中文对话 | /api/weather | /ws/astro_events | 内置Web控制台
"""
import asyncio, json, time, uuid
from pathlib import Path
import json
from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import sys as _sys
if getattr(_sys, "frozen", False):
    ROOT = Path(_sys.executable).parent          # exe目录: .env/reports
    RES = Path(getattr(_sys, "_MEIPASS", "")) or ROOT / "_internal"   # 资源: 星表/提示词/static
else:
    ROOT = Path(__file__).parent
    RES = ROOT
import sys
sys.path.insert(0, str(ROOT))

from utils.config import CFG
from astro_agent.ollama_client import ModelRouter
from mcp_engine.executor_v2 import execute_tool as execute_en, llm_tools as tools_schema_for_llm, client as nina_client, BASE as NINA_BASE
import logging
log = logging.getLogger("starpivot")

app = FastAPI(title="星枢天文AI助手")
router_llm = ModelRouter()

def get_router():
    """版本号变了自动重建(设置保存后下一条消息即用新Key)"""
    global router_llm
    import utils.config as _uc
    ver = getattr(_uc, "ROUTER_VER", 0)
    global _router_ver_seen
    if _router_ver_seen != ver:
        router_llm = ModelRouter()
        _router_ver_seen = ver
    return router_llm

_router_ver_seen = 0
SYSTEM_PROMPT = (RES / "astro_agent" / "system_prompt.txt").read_text(encoding="utf-8")
REPORTS_DIR = ROOT / "reports"

# ---------- 会话管理 ----------
SESSIONS = {}
SESSION_COUNTER = 0
SESSIONS_FILE = ROOT / "data" / "sessions_cache.json"

def _load_sessions():
    global SESSIONS, SESSION_COUNTER
    if SESSIONS_FILE.exists():
        try:
            import json as _j
            d = _j.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
            SESSIONS = d.get("sessions", {})
            SESSION_COUNTER = d.get("counter", 0)
        except Exception:
            pass

def _save_sessions():
    try:
        SESSIONS_FILE.parent.mkdir(exist_ok=True)
        SESSIONS_FILE.write_text(json.dumps(
            {"sessions": {k: {"messages": v["messages"][-20:]} for k, v in SESSIONS.items()},
             "counter": SESSION_COUNTER}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

_load_sessions()   # sid → {messages: [...], created, last}

class ChatReq(BaseModel):
    message: str
    session_id: str = ""

def get_session(sid: str):
    if sid not in SESSIONS:
        sid = sid or f"astro-{uuid.uuid4().hex[:8]}"
        SESSIONS[sid] = {"messages": [{"role": "system", "content": SYSTEM_PROMPT}],
                          "created": time.time(), "last": time.time()}
    SESSIONS[sid]["last"] = time.time()
    return sid

# ---------- 中文AI对话(核心: LLM↔MCP多轮循环) ----------
@app.post("/api/chat")
async def chat(req: ChatReq):
    sid = get_session(req.session_id)
    sess = SESSIONS[sid]
    sess["messages"].append({"role": "user", "content": req.message})

    tools = tools_schema_for_llm()
    final = ""
    t0 = time.time()
    # 最多3轮工具调用
    for round_i in range(3):
        reply = await get_router().chat(sess["messages"], tools=tools)
        if not reply.get("tool_calls"):
            final = reply.get("content", "")
            break
        # 执行工具(可能多个)
        tool_results = []
        for tc in reply["tool_calls"]:
            r = await execute_en(tc["name"], tc["args"])
            rtxt = json.dumps(r, ensure_ascii=False)
            if len(rtxt) > 1200:
                rtxt = rtxt[:1200] + " ...(已精简)"
            tool_results.append(f"[{tc['name']}] {rtxt}")
        # 工具结果以user消息回传(避免非法tool_calls结构)
        # assistant侧记录为内部动作标记(非对话输出, 防LLM复读给用户)
        called = ",".join(tc["name"] for tc in reply["tool_calls"])
        sess["messages"].append({"role": "assistant",
                                  "content": ""})
        sess["messages"].append({"role": "user",
                                  "content": "工具执行结果(中文JSON, 请据此用中文回答用户):\n" +
                                             "\n".join(tool_results)})
    else:
        # 3轮后强制总结
        reply = await get_router().chat(sess["messages"] + [
            {"role": "user", "content": "请根据以上工具结果, 用中文简洁总结当前状态"}])
        final = reply.get("content", "")

    if not final or "所有模型通道不可用" in final:
        from utils.config import CFG as _CFG
        has_key = any(_CFG.get(k) for k in ("DEEPSEEK_API_KEY", "ZHIPU_API_KEY",
                         "MOONSHOT_API_KEY", "QWEN_API_KEY", "DOUBAO_API_KEY",
                         "MINIMAX_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY",
                         "OPENROUTER_API_KEY", "CUSTOM_API_KEY"))
        if not has_key:
            final = ("⚠️ 还没有配置模型Key — 点右上角 ⚙️设置 填写DeepSeek API Key"
                     "(也支持智谱/任意OpenAI兼容模型), 保存后立即可对话。")
        else:
            err = final if final else "模型无响应"
            final = (f"⚠️ 模型通道连接失败 — 已配置Key但调用不成功。{err[:80]} "
                     "常见原因: ①Key无效(点⚙️设置→测试模型连通验证) "
                     "②网络不通(该机器无法访问模型API) "
                     "③自定义端点地址错误。")
    sess["messages"].append({"role": "assistant", "content": final})
    # 上下文裁剪(保system+最近20条)
    if len(sess["messages"]) > 22:
        sess["messages"] = [sess["messages"][0]] + sess["messages"][-20:]
    _save_sessions()
    return {"session_id": sid, "reply": final,
            "耗时秒": round(time.time() - t0, 1), "通道": reply.get("channel", "")}


@app.get("/api/session/list")
async def session_list():
    return [{"id": s, "created": time.strftime("%m-%d %H:%M", time.localtime(v["created"])),
             "last": time.strftime("%m-%d %H:%M", time.localtime(v["last"]))}
            for s, v in sorted(SESSIONS.items(), key=lambda x: -x[1]["last"])]


@app.delete("/api/session/{sid}")
async def session_del(sid: str):
    SESSIONS.pop(sid, None)
    return {"ok": True}


# ---------- 天气 ----------
@app.get("/api/weather/status")
async def weather():
    try:
        r = await sdk._get("/equipment/weather/info")
        d = r.get("Response", r) if isinstance(r, dict) else {}
        return {"温度": d.get("Temperature"), "湿度": d.get("Humidity"),
                "云量": d.get("CloudCover"), "安全": d.get("SafeToOperate", None),
                "来源": "NINA天气插件", "原始": d}
    except Exception as e:
        return {"状态": "天气数据不可用", "原因": str(e)[:100]}


# ---------- WebSocket 中文事件流 ----------
EVENT_ZH = {"ExposureStarted": "曝光开始", "ExposureFinished": "曝光结束",
            "AutoFocusFinished": "自动对焦完成", "MeridianFlip": "过中天翻转",
            "DeviceDisconnected": "设备离线", "SequenceStarted": "序列启动",
            "SequenceFinished": "序列结束", "GuidingStarted": "导星开始"}

class EventHub:
    def __init__(self):
        self.clients = set()

    async def broadcast(self, msg: dict):
        dead = set()
        for ws in self.clients:
            try:
                await ws.send_text(json.dumps(msg, ensure_ascii=False))
            except Exception:
                dead.add(ws)
        self.clients -= dead

hub = EventHub()


@app.websocket("/ws/astro_events")
async def astro_events(ws: WebSocket):
    await ws.accept()
    WS_CLIENTS.append(ws)
    hub.clients.add(ws)
    await ws.send_text(json.dumps({"类型": "系统", "内容": "星枢事件流已连接"}, ensure_ascii=False))
    try:
        while True:
            # 心跳: 每10s推一次设备状态
            try:
                st = await asyncio.wait_for(execute_en("equipment_info"), timeout=8)
                await ws.send_text(json.dumps({"类型": "状态", "内容": st}, ensure_ascii=False,
                                              default=str))
            except Exception:
                pass
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        pass
    finally:
        hub.clients.discard(ws)


# ---------- 工具清单(分类) ----------
@app.get("/api/tools")
async def api_tools(v: str = None):
    from mcp_engine.full_tools import TOOLS
    cats = {}
    CAT_ZH = {'camera': '📷 相机', 'mount': '🔭 赤道仪', 'focuser': '🎯 调焦座',
              'filter': '🎨 滤镜轮', 'filterwheel': '🎨 滤镜轮', 'guider': '⭐ 导星', 'sequence': '📋 序列',
              'dome': '🏠 圆顶', 'flat': '🔆 平场', 'flatpanel': '🔆 平场', 'flats': '🔆 平场', 'rotator': '🔄 旋转器',
              'switch': '🔌 电子开关', 'safety': '🛡 安全监控', 'safetymonitor': '🛡 安全监控', 'weather': '🌤 天气',
              'framing': '🖼 取景', 'equipment': '⚡ 全局设备', 'nina': '⚙ 系统'}
    for name, desc, ep, params, risk in TOOLS:
        cat = name.split('_')[0]
        if cat == 'filter': cat = 'filterwheel'
        if cat in ('flats', 'flatpanel', 'flat'): cat = 'flatpanel'
        cat = CAT_ZH.get(cat, '⚙ 系统' if cat == 'nina' else cat)
        cats.setdefault(cat, []).append(
            {'name': name, 'desc': desc, 'risk': risk,
             'params': {k: {'type': v[0], 'desc': v[1], 'required': v[2]}
                         for k, v in params.items()}})
    return {'total': len(TOOLS), 'categories': cats}


# ---------- 日程/进度引擎 ----------
import asyncio as _aio
from astro_agent.scheduler import assistant as _sched

WS_CLIENTS = []

async def _ws_broadcast(类型, 数据):
    import json as _json
    dead = []
    for ws in WS_CLIENTS:
        try:
            await ws.send_text(_json.dumps({"类型": 类型, **数据}, ensure_ascii=False))
        except Exception:
            dead.append(ws)
    for w in dead:
        WS_CLIENTS.remove(w)

_sched.broadcast = _ws_broadcast
_aio.get_event_loop().create_task(_sched.run_forever())


# ---------- 系统设置 ----------
from settings_api import register_settings_api
register_settings_api(app, ROOT)


# ---------- 今晚推荐 ----------
@app.get("/api/tonight")
async def api_tonight(v: str = None):
    from astro_agent.planner import tonight
    r = tonight()
    return r


# ---------- 监控舱(右侧聚合数据) ----------
def _n(v):
    """NaN清洗"""
    if isinstance(v, float) and v != v:
        return None
    if isinstance(v, str) and v.strip().lower() == 'nan':
        return None
    return v


@app.get("/api/monitor")
async def api_monitor(v: str = None):
    import httpx as _hx
    async def g(path):
        try:
            r = await nina_client.get(f"{NINA_BASE}{path}", timeout=6)
            return r.json().get("Response", {}) if r.status_code == 200 else {}
        except Exception:
            return {}
    seq, cam, mount, guider, wx, fw, foc, rot, sw = await asyncio.gather(
        g("/sequence/state"), g("/equipment/camera/info"),
        g("/equipment/mount/info"), g("/equipment/guider/info"),
        g("/equipment/weather/info"), g("/equipment/filterwheel/info"),
        g("/equipment/focuser/info"), g("/equipment/rotator/info"),
        g("/equipment/switch/info"))
    seqd = seq if isinstance(seq, dict) else {}
    return {
        "序列": {"状态": str(seqd.get("Status", "空闲"))[:16],
                 "目标": seqd.get("TargetName", "-"),
                 "已拍": seqd.get("ImageCount", 0),
                 "曝光中": seqd.get("ExposureInProgress", False),
                 "当前曝光": seqd.get("ExposureTime", None)},
        "相机": {"温度": cam.get("Temperature"), "目标温度": cam.get("TargetTemp"),
                  "制冷": "开" if cam.get("CoolerOn") else "关",
                  "功率": cam.get("CoolerPower"), "增益": cam.get("Gain"),
                  "状态": str(cam.get("CameraState", "-"))[:12]},
        "赤道仪": {"赤经": mount.get("RightAscension"), "赤纬": mount.get("Declination"),
                    "跟踪": "开" if mount.get("Tracking") else "关",
                    "停泊": "是" if mount.get("AtPark") else "否",
                    "高度": mount.get("Altitude") if isinstance(mount.get("Altitude"), (int, float)) else None},
        "导星": {"状态": str(guider.get("State", "-"))[:12],
                  "RA误差": guider.get("RAError"), "DE误差": guider.get("DEError")},
        "天气": {"云量": wx.get("CloudCover"), "湿度": wx.get("Humidity"),
                  "风速": wx.get("WindSpeed"), "温度": wx.get("Temperature")},
        "滤轮": {"在线": bool(fw.get("Connected")), "移动中": bool(fw.get("IsMoving")),
                  "滤镜列表": [str(x) for x in (fw.get("AvailableFilters") or [])],
                  "数量": len(fw.get("AvailableFilters") or []),
                  "当前": (fw.get("AvailableFilters") or ["-"])[0] if fw.get("Connected") else "-"},
        "电调": {"在线": bool(foc.get("Connected")), "位置": _n(foc.get("Position")),
                  "温度": _n(foc.get("Temperature")), "移动中": bool(foc.get("IsMoving")),
                  "温补": bool(foc.get("TempComp")) if foc.get("TempComp") is not None else None},
        "旋转器": {"在线": bool(rot.get("Connected")), "角度": rot.get("Position"),
                    "机械位": rot.get("MechanicalPosition"), "移动中": bool(rot.get("IsMoving"))},
        "开关": {"在线": bool(sw.get("Connected"))},
    }


@app.get("/api/last_image")
async def api_last_image():
    """最新一帧缩略图(jpeg二进制)"""
    try:
        h = await nina_client.get(f"{NINA_BASE}/image-history", timeout=6)
        # history倒序取最新index
        txt = h.text
        import re as _re
        idxs = _re.findall(r'"Index":\s*(\d+)', txt)
        if not idxs:
            idxs = _re.findall(r'IMAGE_(\d+)', txt)
        if not idxs:
            return Response(status_code=404)
        idx = idxs[0]
        r = await nina_client.get(f"{NINA_BASE}/image/thumbnail/{idx}?width=320",
                                  timeout=15)
        if r.status_code == 200 and r.content[:2] == bytes([255, 216]):
            return Response(content=r.content, media_type="image/jpeg")
        return Response(status_code=404)
    except Exception:
        return Response(status_code=404)


# ---------- 工具直调(工具箱双击, 不经LLM) ----------
@app.post("/api/tool_run")
async def api_tool_run(body: dict):
    from mcp_engine.executor_v2 import execute_tool
    name = body.get("name", "")
    HIGH_RISK = {"mount_park", "mount_unpark", "mount_flip", "sequence_start",
                 "sequence_stop", "equipment_disconnect_all", "dome_open_shutter",
                 "dome_close_shutter", "start_imaging"}
    if name in HIGH_RISK and not body.get("confirm"):
        return {"need_confirm": True, "msg": f"{name} 是高风险操作, 再点一次确认执行"}
    try:
        r = await asyncio.wait_for(execute_tool(name, body.get("args") or {}), timeout=60)
        return {"ok": True, "result": r}
    except Exception as e:
        return {"ok": False, "msg": str(e)[:150]}


# ---------- 趋势图数据 ----------
@app.get("/api/trends")
async def api_trends():
    """HFR曲线(当前序列) + 天气趋势(近N次采样)"""
    import httpx
    out = {"hfr": [], "weather": []}
    # HFR: 从NINA拿序列统计历史(尽力) — 拿不到就空
    try:
        r = await nina_client.get(f"{NINA_BASE}/sequence/state", timeout=6)
        seq = r.json().get("Response", {})
        if isinstance(seq, dict):
            for k in ("HFRHistory", "HfrHistory", "Statistics"):
                v = seq.get(k)
                if isinstance(v, list) and v:
                    out["hfr"] = [x.get("HFR") if isinstance(x, dict) else x for x in v[-60:]]
                    break
    except Exception:
        pass
    # 天气: 内存环形缓冲(WS线程在攒)
    out["weather"] = WX_SAMPLES[-60:]
    return out


WX_SAMPLES = []


async def _wx_sampler():
    """每2分钟采一次天气, 攒60点(2小时)"""
    while True:
        try:
            r = await nina_client.get(f"{NINA_BASE}/equipment/weather/info", timeout=6)
            d = r.json().get("Response", {})
            cloud, hum = d.get("CloudCover"), d.get("Humidity")
            if isinstance(cloud, (int, float)) and cloud == cloud:
                WX_SAMPLES.append({"t": f"{datetime.now():%H:%M}", "cloud": cloud,
                                   "hum": hum if isinstance(hum, (int, float)) else None,
                                   "wind": d.get("WindSpeed") if isinstance(d.get("WindSpeed"), (int, float)) else None})
                if len(WX_SAMPLES) > 60:
                    WX_SAMPLES.pop(0)
        except Exception:
            pass
        await asyncio.sleep(120)


import asyncio as _aio2
from datetime import datetime as _dt
_aio2.get_event_loop().create_task(_wx_sampler())


# ---------- 观测报告 ----------
@app.post("/api/report")
async def api_report():
    from report_builder import build_report
    try:
        r = await asyncio.wait_for(build_report(), timeout=30)
        return {"ok": True, "file": r["file"], "content": r["content"][:4000]}
    except Exception as e:
        return {"ok": False, "msg": str(e)[:150]}


@app.get("/api/report/list")
async def api_report_list(v: str = None):
    files = sorted(REPORTS_DIR.glob("观测报告_*.md"), reverse=True) if REPORTS_DIR.exists() else []
    return [{"file": f.name, "time": time.strftime("%m-%d %H:%M", time.localtime(f.stat().st_mtime)),
              "path": str(f)} for f in files[:20]]


# ---------- Web控制台 ----------
@app.get("/")
async def console():
    return FileResponse(RES / "static" / "index.html")


if __name__ == "__main__":
    import uvicorn
    port = int(CFG.get("STARPIVOT_PORT", "8899"))
    print(f"🌌 星枢天文AI助手 → http://127.0.0.1:{port}")
    print(f"   模型: {CFG.get('MODEL_ROUTE')} | NINA: 真机(v2/api)"  )
    uvicorn.run(app, host="127.0.0.1", port=port)
