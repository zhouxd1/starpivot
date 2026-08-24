# -*- coding: utf-8 -*-
"""
星枢 MCP 执行引擎 — 中文工具路由/参数修复/风险拦截/全日志
"""
import asyncio, json, re, time, logging
from pathlib import Path

ROOT = Path(__file__).parent.parent
from nina_sdk.advanced_api import NinaSDK
from utils.config import CFG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [星枢] %(levelname)s %(message)s",
    handlers=[logging.FileHandler(ROOT / "starpivot.log", encoding="utf-8"),
              logging.StreamHandler()])
log = logging.getLogger("starpivot")

sdk = NinaSDK()

# 中文工具 → SDK方法映射 + 参数签名(含默认值/类型矫正)
TOOL_MAP = {
    "制冷控制": {"fn": sdk.相机_制冷, "签名": {"目标温度": float, "是否开启": lambda x: str(x).lower() in ("true","1","是","开")}},
    "单次曝光": {"fn": sdk.相机_曝光, "签名": {"曝光时长": float, "增益": int, "偏置": int,
                                          "是否保存": lambda x: str(x).lower() in ("true","1","是")}},
    "读取相机参数": {"fn": sdk.相机_读参数, "签名": {}},
    "GOTO转向": {"fn": sdk.赤道仪_GOTO, "签名": {"目标": str}},
    "跟踪开关": {"fn": sdk.赤道仪_跟踪, "签名": {"是否开启": lambda x: str(x).lower() in ("true","1","是","开"),
                                            "模式": str}},
    "停泊": {"fn": sdk.赤道仪_停泊, "签名": {}},
    "坐标同步": {"fn": sdk.赤道仪_坐标同步, "签名": {"赤经": str, "赤纬": str}},
    "调焦移动": {"fn": sdk.调焦_移动, "签名": {"步数": int, "方向": str}},
    "全自动对焦": {"fn": sdk.调焦_全自动对焦, "签名": {"曝光时长": float, "滤镜": str}},
    "切换滤镜": {"fn": sdk.滤镜轮_切换, "签名": {"滤镜": str}},
    "读取滤镜位置": {"fn": sdk.滤镜轮_位置, "签名": {}},
    "导星启停": {"fn": sdk.导星_启停, "签名": {"是否开启": lambda x: str(x).lower() in ("true","1","是","开")}},
    "Dither抖动": {"fn": sdk.导星_Dither, "签名": {"像素": int}},
    "星点解析": {"fn": sdk.星点解析, "签名": {"曝光时长": float}},
    "序列控制": {"fn": sdk.序列_控制, "签名": {"操作": str}},
    "状态总览": {"fn": sdk.状态总览, "签名": {"明细": str}},
    "天气安全检查": {"fn": sdk.天气_安全检查, "签名": {}},
}

# 参数别名纠错(口语→标准)
ALIAS = {
    "目标温度": ["温度", "制冷温度", "设定温度"],
    "曝光时长": ["时长", "曝光时间", "秒数"],
    "是否开启": ["开启", "打开", "启用", "开关"],
    "步数": ["移动步数", "步"],
    "增益": ["gain"],
    "目标": ["目标名", "天体", "对象"],
}


def fix_args(tool: str, args: dict) -> dict:
    """参数修复层: 别名归一/类型矫正/默认值"""
    spec = TOOL_MAP.get(tool, {}).get("签名", {})
    fixed = {}
    for k, v in (args or {}).items():
        # 别名归一
        std = k
        for sk, aliases in ALIAS.items():
            if k in aliases or k == sk:
                std = sk
                break
        # 类型矫正
        caster = spec.get(std)
        if caster and v is not None:
            try:
                v = caster(v)
            except Exception:
                pass   # 矫正失败保留原值(让LLM看报错自纠)
        fixed[std] = v
    return fixed


async def execute(tool: str, args: dict = None, auto_mode: bool = False) -> dict:
    """执行中文工具: 校验→修复→执行→日志。统一返回中文结构"""
    t0 = time.time()
    args = fix_args(tool, args or {})

    if tool not in TOOL_MAP:
        return {"状态": "该工具暂未实现, 已记录需求, 将在后续版本支持", "工具": tool}

    spec = TOOL_MAP[tool]
    # 必填校验
    missing = []
    for p in spec.get("签名", {}):
        if p not in args:
            missing.append(p)
    if missing and tool not in ("读取相机参数", "停泊", "读取滤镜位置", "状态总览"):
        return {"状态": "参数缺失", "缺少": missing, "提示": f"请补充: {','.join(missing)}"}

    try:
        result = await asyncio.wait_for(spec["fn"](**args), timeout=60)
        ms = int((time.time() - t0) * 1000)
        log.info(f"✅ {tool}({args}) → {str(result)[:80]} [{ms}ms]")
        return {"状态": "成功", "结果": result, "耗时ms": ms}
    except asyncio.TimeoutError:
        log.error(f"⏰ {tool} 超时")
        return {"状态": "超时", "提示": "设备响应超时, 请检查连接"}
    except Exception as e:
        log.error(f"❌ {tool} 异常: {e}")
        return {"状态": "失败", "原因": str(e)[:200]}


# 英文工具名(LLM协议要求) ↔ 中文执行名
EN_MAP = {"camera_cool": "制冷控制", "camera_capture": "单次曝光",
          "camera_info": "读取相机参数", "mount_goto": "GOTO转向",
          "mount_tracking": "跟踪开关", "mount_park": "停泊",
          "mount_sync": "坐标同步", "focuser_move": "调焦移动",
          "autofocus": "全自动对焦", "filter_set": "切换滤镜",
          "filter_info": "读取滤镜位置", "guider_toggle": "导星启停",
          "guider_dither": "Dither抖动", "platesolve": "星点解析",
          "sequence_ctl": "序列控制", "status_overview": "状态总览",
          "weather_status": "天气安全检查"}
ZH_MAP = {v: k for k, v in EN_MAP.items()}


def execute_en(en_name: str, args: dict = None, **kw) -> dict:
    """LLM给的英文工具名 → 中文执行"""
    return execute(EN_MAP.get(en_name, en_name), args, **kw)


def tools_schema_for_llm() -> list:
    """生成给LLM的OpenAI function-calling schema(英文工具名+中文参数描述)"""
    schema_path = ROOT / "mcp_engine" / "cn_mcp_tools.json"
    raw = json.loads(schema_path.read_text(encoding="utf-8"))
    tools = []
    FLAT = {"制冷控制": ("相机", "制冷控制"), "单次曝光": ("相机", "单次曝光"),
            "读取相机参数": ("相机", "读取参数"), "GOTO转向": ("赤道仪", "GOTO转向"),
            "跟踪开关": ("赤道仪", "跟踪开关"), "停泊": ("赤道仪", "停泊"),
            "坐标同步": ("赤道仪", "坐标同步"), "调焦移动": ("调焦座", "移动"),
            "全自动对焦": ("调焦座", "全自动对焦"), "切换滤镜": ("滤镜轮", "切换"),
            "读取滤镜位置": ("滤镜轮", "读取位置"), "导星启停": ("导星", "启停"),
            "Dither抖动": ("导星", "Dither抖动"), "星点解析": ("星点解析", "拍摄并解析"),
            "序列控制": ("序列", "启停控制"), "状态总览": ("全局状态", "读取总览")}
    for name, (cat, cname) in FLAT.items():
        spec = raw["工具集"].get(cat, {}).get(cname, {})
        props = {}
        required = []
        for pname, pdef in (spec.get("参数") or {}).items():
            tmap = {"数字": "number", "整数": "integer", "布尔": "boolean", "文本": "string"}
            props[pname] = {"type": tmap.get(pdef.get("类型", "文本"), "string"),
                            "description": f'{pdef.get("说明","")}{pdef.get("单位","")}'.strip()}
            if pdef.get("枚举"):
                props[pname]["enum"] = pdef["枚举"]
            if pdef.get("默认") is not None:
                props[pname]["default"] = pdef["默认"]
            if pdef.get("必填"):
                required.append(pname)
        tools.append({"type": "function", "function": {
            "name": ZH_MAP.get(name, name),
            "description": f'[{cat}] {spec.get("返回","")}'[:120],
            "parameters": {"type": "object", "properties": props, "required": required}}})
    tools.append({"type": "function", "function": {
        "name": "weather_status",
        "description": "[天气] 读取实时天气并判断观测是否安全(云量/雨/风/湿度)。用户问天气/是否安全/能不能拍时用这个,不要用status_overview",
        "parameters": {"type": "object", "properties": {}}}})
    return tools
