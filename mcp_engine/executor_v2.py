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
    # ═══ 本地工具路由(星枢自研工作流) ═══
    if name == "sequence_setup":
        from astro_agent.seq_builder import setup_sequence
        return setup_sequence(
            args.get("目标", ""),
            int(args.get("单张曝光秒", 300)),
            int(args.get("张数", 20)),
            args.get("滤镜"),
            int(args["增益"]) if args.get("增益") else None)

    if name == "multi_schedule":
        from astro_agent.planner import multi_schedule as _ms
        lat, lon, _loc = await _detect_location()
        wants = args.get("目标", args.get("names", []))
        if isinstance(wants, str):
            wants = [w.strip() for w in wants.split(",") if w.strip()]
        return _ms(wants, lat=lat, lon=lon)

    if name == "obs_report":
        from astro_agent.report_gen import build_report
        return build_report(args.get("目标", ""))

    if name == "history_export":
        from astro_agent.history import export_history
        return export_history(args.get("路径"))

    if name == "history_import":
        from astro_agent.history import import_history
        return import_history(args.get("路径", ""))

    if name == "camera_match":
        from astro_agent.param_calc import match_camera
        return match_camera(float(args.get("焦距", 750)), float(args.get("视宁度", 2.0)))

    if name == "weather_cross":
        return await _weather_cross(str(args.get("机场", "ZBAA")))

    if name == "guide_rescue":
        return await _guide_rescue()

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
    # 圆顶/平顶前置检查: 没配设备时说人话,不让AI瞎猜
    if name.startswith("dome_") and name not in ("dome_info", "dome_list"):
        r = await client.get(f"{BASE}/equipment/dome/info", timeout=8)
        d = r.json().get("Response", {}) if r.status_code == 200 else {}
        if not d.get("Connected") and str(d.get("ShutterStatus", "")).endswith("None") is False and not d.get("Connected"):
            pass  # 已连,放行
        if not d.get("Connected"):
            # 查dome设备是否配置
            r2 = await client.get(f"{BASE}/equipment/dome/list-devices", timeout=8)
            devs = r2.json().get("Response", []) if r2.status_code == 200 else []
            chosen = next((x for x in devs if x.get("Id") not in (None, "No_Device")), None)
            if not chosen:
                return {"状态": "无法执行",
                        "原因": "NINA中未配置圆顶/平顶设备(当前=没有圆顶)",
                        "怎么办": "1)若你有圆顶或平顶: 在NINA设备区选择对应驱动(如ASCOM Dome)并连接后重试; 2)若是手动开合的平顶: 本功能不适用,出摊前手动开合即可; 3)注意:平顶通常可作为ASCOM Dome驱动接入(带开关盖能力的),装ASCOM平台+厂商驱动后NINA里可选",
                        "设备能力": {"CanSetShutter": d.get("CanSetShutter", False), "ShutterStatus": d.get("ShutterStatus")}}
        elif name in ("dome_open_shutter", "dome_close_shutter") and not d.get("CanSetShutter"):
            return {"状态": "无法执行",
                    "原因": f"当前圆顶驱动不支持舱盖控制(CanSetShutter=false, ShutterStatus={d.get('ShutterStatus')})",
                    "怎么办": "检查NINA里选择的圆顶驱动类型是否正确;平顶应选择支持开关盖的ASCOM Dome驱动",
                    "设备能力": {"CanSetShutter": d.get("CanSetShutter"), "ShutterStatus": d.get("ShutterStatus")}}

    if name in ("equipment_connect_all", "equipment_disconnect_all"):
        action = "connect" if name.startswith("equipment_connect") else "disconnect"
        devs = ["camera", "mount", "focuser", "filterwheel", "guider",
                "rotator", "dome", "flatdevice", "switch", "safetymonitor"]
        results, ok_cnt = {}, 0

        async def _one(dev):
            try:
                r = await client.get(f"{BASE}/equipment/{dev}/{action}", timeout=25)
                body = r.json() if r.status_code == 200 else {}
                ok = r.status_code == 200 and body.get("Success") is True
                return dev, ("✓" if ok else "✗" + str(body.get('Error') or body.get('StatusCode') or r.status_code)), ok
            except Exception:
                return dev, "✗超时", False

        import asyncio as _a2
        for _dev, _mark, _ok in await _a2.gather(*[_one(d) for d in devs]):
            results[_dev] = _mark
            ok_cnt += _ok
        # 连接后实测各设备真实状态(防假成功)
        real_online = []
        if action == "connect":
            for dev in devs[:6]:
                try:
                    r2 = await client.get(f"{BASE}/equipment/{dev}/info", timeout=8)
                    d2 = r2.json().get("Response", {}) if r2.status_code == 200 else {}
                    if d2.get("Connected"):
                        real_online.append(dev)
                except Exception:
                    pass
        verdict = (f"实际在线: {', '.join(real_online) if real_online else '无 — 请检查NINA里是否已选好设备并手动连接一次'}"
                   if action == "connect" else "")
        return {"状态": f"批量{'连接' if action == 'connect' else '断开'}请求已发出",
                f"API成功": f"{ok_cnt}/{len(devs)}",
                "实际验证": verdict,
                "明细": results,
                "提示": "未配置/未选择的设备连接失败属正常;关键看'实际验证'里哪些设备真的在线"}

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

async def _weather_cross(station: str = "ZBAA"):
    """天气多源交叉: METAR机场实况(观测) vs OpenMeteo/NINA(预报)"""
    import re as _re
    out = {"机场": station}
    try:
        r = await client.get(f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{station}.TXT", timeout=10)
        txt = r.text
        tl = txt.strip().split(chr(10))
        metar = tl[-1] if tl else ""
        out["原始METAR"] = metar
        out["观测时间"] = tl[0] if tl else ""
        m = _re.search(r"(\d{4,8})MPS|(\d{3})(\d{2,3})KT", metar)
        if m:
            out["风"] = m.group(1) + "m/s" if m.group(1) else m.group(2) + "°" + m.group(3) + "kt"
        vis = _re.search(r"\s(\d{4})\s", metar)
        if vis:
            v = int(vis.group(1))
            out["能见度"] = str(v) + "m " + ("⚠️差" if v < 10000 else "✅")
        wx = _re.findall(r"\b(TSRA|SHRA|RA|SN|DZ|FG|BR|HZ)\b", metar)
        if wx:
            out["天气现象"] = {"TSRA": "雷暴阵雨⚠️", "SHRA": "阵雨", "RA": "雨", "SN": "雪",
                              "DZ": "毛毛雨", "FG": "雾", "BR": "薄雾", "HZ": "霾"}.get(wx[0], wx[0])
        clouds = _re.findall(r"(FEW|SCT|BKN|OVC)(\d{3})", metar)
        if clouds:
            cover = max((c for c, _ in clouds), key=lambda x: {"FEW": 1, "SCT": 2, "BKN": 3, "OVC": 4}.get(x, 0))
            out["云况"] = cover + "(" + str(len(clouds)) + "层) " + ("阴天信号" if cover in ("BKN", "OVC") else ("可拍信号" if cover == "FEW" else "过渡"))
        t = _re.search(r"\s(\d{2})/(\d{2})\s", metar)
        if t:
            out["温度"] = t.group(1) + "°C 露点" + t.group(2) + "°C"
            if int(t.group(1)) - int(t.group(2)) <= 2:
                out["结露风险"] = "温差≤2°C ⚠️高,注意镜头除露"
    except Exception as e:
        out["METAR失败"] = str(e)[:60]
    try:
        r2 = await client.get(f"{BASE or 'http://127.0.0.1:1888/v2/api'}/weather-data", timeout=8)
        d2 = r2.json().get("Response", {})
        if isinstance(d2, dict):
            out["NINA侧"] = {"云量": d2.get("CloudCover"), "湿度": d2.get("Humidity")}
    except Exception:
        out["NINA侧"] = "不可用"
    concl = []
    ph = str(out.get("天气现象", ""))
    if "⚠️" in ph:
        concl.append("METAR实测" + ph + " — 若NINA云量不高则预报滞后,以实测为准")
    cc = out.get("NINA侧", {}).get("云量") if isinstance(out.get("NINA侧"), dict) else None
    cover = str(out.get("云况", ""))
    if cc is not None and cover:
        if cc > 85 and "阴天" in cover:
            concl.append("两源一致阴天 ✅可信")
        elif cc > 85 and "可拍" in cover:
            concl.append("⚠️分歧: 预报阴但实测云少 — 可能好窗口,出摊前再确认")
        elif cc < 40 and "阴天" in cover:
            concl.append("⚠️分歧: 预报好但实测阴 — 小心白跑")
    if out.get("结露风险"):
        concl.append(out["结露风险"])
    out["交叉结论"] = concl or ["无明显冲突"]
    return out


async def _guide_rescue():
    """导星失锁自动抢救: 暂停序列→重导→稳定→恢复序列"""
    log.info("🚨 导星失锁抢救流程启动")
    steps = []
    r = await client.get(f"{BASE or 'http://127.0.0.1:1888/v2/api'}/equipment/guider/info", timeout=8)
    g = r.json().get("Response", {}) if r.status_code == 200 else {}
    state = str(g.get("State", ""))
    steps.append("当前导星状态: " + state)
    if "lost" not in state.lower():
        return {"结论": "导星未失锁,无需抢救", "状态": state}
    try:
        r2 = await client.get(f"{BASE or 'http://127.0.0.1:1888/v2/api'}/sequence/pause", timeout=8)
        steps.append("序列已暂停" if r2.status_code == 200 else "序列暂停返回: " + str(r2.status_code))
    except Exception as e:
        steps.append("序列暂停失败: " + str(e)[:50])
    try:
        await client.get(f"{BASE or 'http://127.0.0.1:1888/v2/api'}/equipment/guider/stop-guiding", timeout=8)
        steps.append("旧导星已停止")
    except Exception:
        pass
    import asyncio as _a
    await _a.sleep(5)
    try:
        r4 = await client.get(f"{BASE or 'http://127.0.0.1:1888/v2/api'}/equipment/guider/guide", timeout=8)
        steps.append("重新导星指令已发 " + ("✓" if r4.status_code == 200 else "✗"))
    except Exception as e:
        return {"结论": "重导失败,请人工介入", "步骤": steps, "错误": str(e)[:80]}
    for i in range(9):
        await _a.sleep(10)
        try:
            r5 = await client.get(f"{BASE or 'http://127.0.0.1:1888/v2/api'}/equipment/guider/info", timeout=8)
            s5 = str(r5.json().get("Response", {}).get("State", ""))
            steps.append(str((i + 1) * 10) + "s 导星: " + s5)
            if "lost" not in s5.lower() and ("loop" in s5.lower() or "guid" in s5.lower() or i >= 3):
                await client.get(f"{BASE or 'http://127.0.0.1:1888/v2/api'}/sequence/resume", timeout=8)
                steps.append("序列已恢复 ✓")
                return {"结论": "抢救成功,导星恢复+序列续拍", "步骤": steps}
        except Exception:
            continue
    return {"结论": "90秒未稳定,序列保持暂停,建议人工检查", "步骤": steps}
