# -*- coding: utf-8 -*-
"""
星枢 V2 执行器 — 全量工具版(AI-Assistant 115工具对齐)
所有工具直接HTTP调Advanced-API, 英文进出, 中文包装
"""
import asyncio, json, time, logging
import httpx

from utils.config import CFG
from mcp_engine.full_tools import to_llm_schema, find_tool

log = logging.getLogger("starpivot")

async def _detect_location():
    """位置检测链: NINA观测点 → IP定位 → 默认北京"""
    # 1. NINA
    try:
        r = await client.get(f"{BASE or 'http://127.0.0.1:1888/v2/api'}/equipment/mount/info", timeout=5)
        d = r.json().get("Response", {})
        lat, lon = d.get("SiteLatitude"), d.get("SiteLongitude")
        if lat and lon and (abs(lat) > 0.1 or abs(lon) > 0.1):
            return float(lat), float(lon), "NINA观测点"
    except Exception:
        pass
    # 2. IP定位(ipapi免key)
    try:
        r = await client.get("https://ipapi.co/json/", timeout=6)
        d = r.json()
        return float(d["latitude"]), float(d["longitude"]), "IP定位"
    except Exception:
        pass
    # 3. .env手动
    if CFG.get("OBS_LAT"):
        return float(CFG["OBS_LAT"]), float(CFG.get("OBS_LON", 116.4)), "手动配置"
    return 40.0, 116.4, "默认北京(请配置)"


BASE = (f'http://{CFG.get("NINA_API_HOST", "127.0.0.1")}:'
        f'{CFG.get("NINA_API_PORT", "1888")}/v2/api')
MOCK = CFG.get("NINA_MOCK", "false").lower() == "true"

client = httpx.AsyncClient(timeout=30)

# 英文响应字段 → 中文(全量映射)
ZH = {"Response": "数据", "Error": "错误", "Success": "成功", "Type": "类型",
      "TargetTemp": "目标温度", "AtTargetTemp": "已达目标", "Temperature": "温度",
      "CoolerPower": "制冷功率", "CoolerOn": "制冷开启", "Gain": "增益", "Offset": "偏置",
      "CameraState": "相机状态", "RightAscension": "赤经", "Declination": "赤纬",
      "AtPark": "已停泊", "Tracking": "跟踪中", "Altitude": "地平高度", "Azimuth": "方位角",
      "SideOfPier": "镜筒侧", "TimeToMeridianFlip": "距中天翻转(分)",
      "Name": "名称", "Connected": "已连接", "Position": "位置", "Moving": "移动中",
      "TempComp": "温度补偿", "TempCompAvailable": "支持温度补偿",
      "IsMoving": "移动中", "HFR": "HFR", "Stars": "星点数", "Average": "平均值",
      "Median": "中位数", "StdDev": "标准差", "ExposureTime": "曝光时长",
      "CloudCover": "云量", "Humidity": "湿度", "WindSpeed": "风速", "WindGust": "阵风",
      "RainRate": "降雨率", "Pressure": "气压", "DewPoint": "露点", "SafeToOperate": "安全可运行",
      "SafeToCapture": "安全可拍摄", "AvailableFilters": "可用滤镜", "Filter": "滤镜",
      "StepSize": "步进尺寸", "MaxIncrement": "最大步数", "MaxStep": "最大行程",
      "RAError": "赤经误差", "DEError": "赤纬误差", "RMS": "RMS", "PA": "方位角PA",
      "State": "状态", "Status": "状态", "Message": "消息", "Data": "数据",
      "TargetName": "目标名", "StartDate": "开始时间", "EndDate": "结束时间",
      "ImageCount": "已拍张数", "EstimatedDownload": "预计下载(秒)"}


def zhify(d):
    if isinstance(d, dict):
        return {ZH.get(k, k): zhify(v) for k, v in d.items()}
    if isinstance(d, list):
        return [zhify(x) for x in d]
    return d


SLOW_OPS = {"mount_slew", "mount_slew_altaz", "mount_park", "mount_unpark",
            "mount_flip", "mount_find_home", "focuser_autofocus",
            "dome_park", "dome_slew", "flats_skyflat"}
slow_client = httpx.AsyncClient(timeout=45)


async def execute_tool(name: str, args: dict = None) -> dict:
    """统一执行入口: 校验→HTTP→中文化→日志"""
    t0 = time.time()
    args = args or {}

    # 一键开拍工作流
    if name == "start_imaging":
        from astro_agent.planner import TARGETS as _TG
        from astro_agent.param_calc import find_target
        k, tg = find_target(args.get("target", ""))
        steps = []
        if not tg:
            return {"状态": "目标未找到", "提示": f"星表中没有'{args.get('target')}', 请检查名称"}
        # ① GOTO
        r = await execute_tool("mount_slew", {"ra": f'{tg["赤经"]:.4f}', "dec": f'{tg["赤纬"]:.4f}'})
        steps.append({"步": "GOTO转向", "结果": r.get("状态", str(r)[:60])})
        if r.get("状态") != "成功":
            return {"工作流": "中止", "原因": "GOTO失败(设备未连接?)", "步骤": steps,
                    "建议": "先连接赤道仪(equipment_connect_all), 再重新开拍"}
        # ② 等待到达(查位置变化, 最多60s)
        import asyncio as _a
        ok_arrive = False
        for _ in range(6):
            await _a.sleep(10)
            info = await execute_tool("mount_info", {})
            res = info.get("结果", {}) if isinstance(info, dict) else {}
            if str(res.get("赤经", "")).replace(".","").replace(":",  "")[:3] == f'{tg["赤经"]:.1f}'.replace(".","")[:3]:
                ok_arrive = True; break
        steps.append({"步": "到达确认", "结果": "✅已到位" if ok_arrive else "⚠️60秒未确认(可能仍在转向)"})
        # ③ 导星
        if args.get("start_guide", True):
            g = await execute_tool("guider_start", {})
            steps.append({"步": "启动导星", "结果": g.get("状态", str(g)[:60])})
        # ④ 序列
        s = await execute_tool("sequence_start", {})
        steps.append({"步": "启动序列", "结果": s.get("状态", str(s)[:60])})
        return {"工作流": "✅开拍流程完成" if s.get("状态") == "成功" else "⚠️部分完成",
                "目标": k, "步骤": steps,
                "提示": "进度会自动播报; 说'停止拍摄'可随时叫停"}

    # 观测历史
    if name == "history_query":
        from astro_agent.history import query
        return query(args.get("mode", "汇总"), args.get("target"))

    # 拍摄参数计算器
    if name == "calc_params":
        from astro_agent.param_calc import calc, SENSORS
        focal = float(args.get("focal") or 0) or None
        if not focal:
            focal = float(CFG.get("TELESCOPE_FOCAL") or 750)
        sensor = args.get("sensor") or ""
        if sensor and sensor not in SENSORS:
            for k in SENSORS:
                if sensor.upper() in k.upper():
                    sensor = k; break
        lp = args.get("light_pollution", "郊区")
        lp_n = {"荒野": "波特尔1-2(荒野)", "郊野": "波特尔3-4(郊野)", "郊区": "郊区",
                "城市边缘": "城市边缘", "城市": "城市"}.get(lp, lp)
        return calc(args["target"], focal, sensor or "未知/手动输入", light_pollution=lp_n)

    # 观测规划: 今晚拍什么(位置自动检测: NINA→IP→.env→北京默认)
    if name == "tonight_targets":
        from astro_agent.planner import tonight
        lat, lon, src_note = await _detect_location()
        if args.get("lat"):
            lat, lon = float(args["lat"]), float(args.get("lon", 116.4))
            src_note = "用户指定"
        r = tonight(lat=lat, lon=lon)
        r["位置"] = f"{lat:.2f}°N, {lon:.2f}°E ({src_note})"
        return r

    # 天气走本地智能判定
    if name == "weather_status":
        r = await client.get(f"{BASE}/equipment/weather/info")
        d = r.json().get("Response", {}) if r.status_code == 200 else {}
        safe = d.get("SafeToOperate")
        if safe is None:
            reasons, safe = [], True
            for k, op, lim, txt in [("CloudCover", ">", 90, "云量过高"),
                                      ("RainRate", ">", 0, "正在降雨"),
                                      ("WindGust", ">", 40, "阵风过强"),
                                      ("Humidity", ">", 95, "湿度过高结露风险")]:
                v = d.get(k)
                if isinstance(v, (int, float)) and ((op == ">" and v > lim)):
                    safe = False
                    reasons.append(f"{txt}({v})")
            basis = "星枢规则判定"
        else:
            basis = "NINA安全监控"
        return {"天气安全": "✅ 安全可拍摄" if safe else "⚠️ 不安全,建议停泊",
                "判定依据": basis,
                "风险明细": reasons if safe is not None and not safe else ["各项正常"],
                "数据": zhify({k: v for k, v in d.items()
                                if k in ("Temperature", "Humidity", "CloudCover",
                                         "WindSpeed", "RainRate", "Pressure")})}

    # 批量连接/断开: ninaAPI无all端点("Invalid equipment"), 循环单设备实现
    if name in ("equipment_connect_all", "equipment_disconnect_all"):
        action = "connect" if name.startswith("equipment_connect") else "disconnect"
        devs = ["camera", "mount", "focuser", "filterwheel", "guider",
                "rotator", "dome", "flatdevice", "switch", "safetymonitor"]
        results, ok_cnt = {}, 0
        for dev in devs:
            try:
                r = await client.get(f"{BASE}/equipment/{dev}/{action}", timeout=15)
                ok = r.status_code == 200
                results[dev] = "✓" if ok else f"✗{r.status_code}"
                ok_cnt += ok
            except Exception as e:
                results[dev] = f"✗超时"
        return {"状态": f"批量{'连接' if action == 'connect' else '断开'}完成",
                f"成功": f"{ok_cnt}/{len(devs)}",
                "明细": results,
                "提示": "未配置的设备报错属正常, 已连接设备均已被处理"}

    # 设备总览精简: equipment_info返回压缩版(每设备一行, 防超长截断丢设备)
    if name == "equipment_info":
        r = await client.get(f"{BASE}/equipment/info")
        d = r.json().get("Response", {}) if r.status_code == 200 else {}
        out = {}
        for dev, info in (d or {}).items():
            if not isinstance(info, dict):
                continue
            out[dev] = {"已连接": info.get("Connected"),
                        "名称": info.get("Name", ""),
                        "关键状态": {k: v for k, v in info.items()
                                     if k in ("CameraState", "Temperature", "TargetTemp",
                                              "RightAscension", "Declination", "Tracking",
                                              "AtPark", "Position", "IsMoving", "State",
                                              "CoolerOn", "Gain") and v not in (None, "", "NaN")}}
        return {"状态": "成功", "全部设备": out}

    t = find_tool(name)
    if not t:
        return {"状态": "未知工具", "提示": f"工具{name}不存在"}
    # 版本兼容: 当前ninaAPI未提供的端点优雅降级
    VERSION_404 = {"camera_set_readout_mode", "mount_sync_to_target", "mount_stop",
                    "dome_open_shutter", "dome_close_shutter", "dome_stop",
                    "dome_sync_telescope", "rotator_halt", "nina_time"}
    if name in VERSION_404:
        return {"状态": "当前NINA API版本不支持",
                "提示": "此功能需要更新ninaAPI插件版本, 或在NINA界面手动操作"}
    _, desc, ep, params, risk = t

    # 参数校验(必填+类型)
    missing = [p for p, pd in params.items()
               if (pd[2] if isinstance(pd, tuple) else pd.get("required")) and p not in args]
    if missing:
        return {"状态": "参数缺失", "缺少": missing, "提示": f"请补充{missing}"}

    method, path = ep.split(" ", 1)
    url = BASE + path
    # 路径参数替换 + query参数
    for k in list(args.keys()):
        path_t = "{" + k + "}"
        if path_t in url:
            url = url.replace(path_t, str(args.pop(k)))

    try:
        _c = slow_client if name in SLOW_OPS else client
        if method == "GET":
            r = await _c.get(url, params={k: str(v).lower() if isinstance(v, bool) else v
                                           for k, v in args.items()})
        else:
            r = await _c.post(url, json=args)
        ms = int((time.time() - t0) * 1000)
        if r.status_code == 200:
            try:
                body = r.json()
            except Exception:
                body = r.text[:300]
            data = zhify(body.get("Response", body) if isinstance(body, dict) else body)
            ok = not (isinstance(body, dict) and body.get("Error"))
            log.info(f"{'✅' if ok else '⚠️'} {name}({args}) [{ms}ms]")
            return {"状态": "成功" if ok else "设备报错",
                    "结果": data,
                    "原始错误": zhify(body.get("Error")) if isinstance(body, dict) and body.get("Error") else None}
        else:
            err = ""
            try:
                err = r.json().get("Error", {}).get("Message", "")[:150]
            except Exception:
                err = r.text[:150]
            log.warning(f"⏰ {name} HTTP{r.status_code}: {err}")
            return {"状态": "设备拒绝", "码": r.status_code, "原因": err,
                    "建议": "检查设备是否已连接" if r.status_code == 409 else "稍后重试"}
    except asyncio.TimeoutError:
        if name in SLOW_OPS:
            return {"状态": "指令已发出但设备未在45秒内完成",
                    "提示": "可能是设备未连接/机械动作慢(转向/对焦需要时间)。指令已送达NINA, 若设备在线它会继续执行; 建议先检查设备连接"}
        return {"状态": "超时", "提示": "设备无响应(30秒), 大概率未连接, 请先连接设备"}
    except Exception as e:
        log.error(f"❌ {name}: {e}")
        return {"状态": "失败", "原因": str(e)[:150]}


def llm_tools():
    return to_llm_schema()
