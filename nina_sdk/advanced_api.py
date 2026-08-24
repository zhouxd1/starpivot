# -*- coding: utf-8 -*-
"""
星枢 NINA SDK — Advanced-API 封装(真机) + Mock模式(无NINA开发)
对外100%中文, 真机英文字段在此层全部消化
"""
import asyncio, json, random, time
import httpx

from pathlib import Path
from utils.config import CFG


class NinaSDK:
    def __init__(self):
        self.mock = CFG.get("NINA_MOCK", "true").lower() == "true"
        self.base = (f'http://{CFG.get("NINA_API_HOST","127.0.0.1")}:'
                     f'{CFG.get("NINA_API_PORT","1888")}/v2/api')   # Advanced-API v2 真实前缀
        self.client = httpx.AsyncClient(timeout=15)
        self._mock_state = {
            "温度": -10.2, "目标温度": -10.0, "制冷开启": True, "制冷功率": 45,
            "增益": 120, "偏置": 10,
            "赤经": "00:42:44", "赤纬": "+41:16:09", "跟踪中": True, "已停泊": False,
            "对焦位置": 15230, "HFR": 2.85,
            "当前滤镜": "L", "滤镜列表": ["L", "R", "G", "B", "Ha", "OIII", "SII"],
            "导星中": True, "导星RMS": 0.68,
            "序列状态": "运行中", "序列进度": "12/60", "已拍张数": 12,
            "设备在线": {"相机": True, "赤道仪": True, "调焦座": True, "滤镜轮": True, "导星相机": True},
        }

    # ---------- 底层请求 ----------
    async def _get(self, path, **kw):
        if self.mock:
            return self._mock_route(path, kw)
        r = await self.client.get(self.base + path, params=kw)
        r.raise_for_status()
        return r.json()

    async def _post(self, path, payload):
        if self.mock:
            return self._mock_route(path, payload)
        r = await self.client.post(self.base + path, json=payload)
        r.raise_for_status()
        return r.json()

    # ---------- Mock路由(开发期模拟NINA) ----------
    def _mock_route(self, path, payload):
        s = self._mock_state
        time.sleep(0.05)   # 模拟网络
        if "camera" in path and "cooler" in path:
            if isinstance(payload, dict) and "目标温度" in str(payload):
                s["目标温度"] = payload.get("目标温度", s["目标温度"])
                s["制冷开启"] = payload.get("是否开启", True)
            return {"状态": "ok", "温度": s["温度"], "目标温度": s["目标温度"], "制冷功率": s["制冷功率"]}
        if "camera/exposure" in path:
            return {"状态": "ok", "平均": 5230 + random.randint(-50, 50), "中位数": 5180,
                    "标准差": 310, "文件": None if not payload.get("是否保存") else "LIGHT_001.fits"}
        if "camera" in path:
            return {"温度": s["温度"], "增益": s["增益"], "偏置": s["偏置"], "像元": "3.76μm", "位深": 16}
        if "mount/goto" in path:
            s["跟踪中"] = True
            return {"状态": "转向完成", "赤经": s["赤经"], "赤纬": s["赤纬"]}
        if "mount/park" in path:
            s["已停泊"] = True; s["跟踪中"] = False
            return {"状态": "已停泊"}
        if "mount" in path:
            return {"赤经": s["赤经"], "赤纬": s["赤纬"], "跟踪中": s["跟踪中"], "已停泊": s["已停泊"]}
        if "focuser/fullaf" in path:
            s["HFR"] = round(random.uniform(2.2, 2.6), 2)
            s["对焦位置"] += random.randint(-300, 300)
            return {"状态": "对焦完成", "最终HFR": s["HFR"], "位置": s["对焦位置"], "耗时秒": 95}
        if "focuser" in path:
            s["对焦位置"] += payload.get("步数", 0)
            return {"状态": "ok", "位置": s["对焦位置"]}
        if "filterwheel" in path:
            if isinstance(payload, dict) and "滤镜" in payload:
                s["当前滤镜"] = str(payload["滤镜"])
            return {"位置": s["滤镜列表"].index(s["当前滤镜"]) + 1 if s["当前滤镜"] in s["滤镜列表"] else 1,
                    "名称": s["当前滤镜"], "列表": s["滤镜列表"]}
        if "guider" in path and "dither" in path:
            return {"状态": "抖动完成", "收敛耗时秒": 6.2}
        if "guider" in path:
            if isinstance(payload, dict) and "是否开启" in payload:
                s["导星中"] = payload["是否开启"]
            return {"导星中": s["导星中"], "RMS": s["导星RMS"]}
        if "plate" in path:
            return {"赤经": s["赤经"], "赤纬": s["赤纬"], "像素比例": 1.85, "置信度": 0.97}
        if "sequence" in path:
            if isinstance(payload, dict) and "操作" in payload:
                op = payload["操作"]
                s["序列状态"] = {"启动": "运行中", "停止": "已停止", "暂停": "已暂停", "继续": "运行中"}.get(op, s["序列状态"])
            return {"状态": s["序列状态"], "进度": s["序列进度"], "已拍": s["已拍张数"]}
        if "status" in path or "all" in path:
            return dict(s)
        return {"状态": "ok"}

    # ---------- 中文业务方法(MCP引擎调用这些; 真机=Advanced-API v2, 返回值全部转中文) ----------
    def _zh(self, d: dict) -> dict:
        """英文响应 → 中文结构化(真机模式统一出口)"""
        M = {"Response": "数据", "TargetTemp": "目标温度", "AtTargetTemp": "已达目标温度",
             "Temperature": "温度", "CoolerPower": "制冷功率", "CoolerOn": "制冷开启",
             "Gain": "增益", "Offset": "偏置", "CameraState": "相机状态",
             "RightAscension": "赤经", "Declination": "赤纬", "AtPark": "已停泊",
             "Tracking": "跟踪中", "Altitude": "地平高度", "Azimuth": "方位角",
             "SideOfPier": "镜筒位置", "TimeToMeridianFlip": "距中天翻转分钟",
             "Name": "名称", "Connected": "已连接", "Position": "位置",
             "HFR": "HFR", "Stars": "星点数", "Error": "错误", "Success": "成功"}
        out = {}
        for k, v in (d or {}).items():
            if isinstance(v, dict):
                v = self._zh(v)
            elif isinstance(v, list):
                v = [self._zh(x) if isinstance(x, dict) else x for x in v]
            out[M.get(k, k)] = v
        return out

    async def _get_zh(self, path, **kw):
        r = await self._get(path, **kw)
        return self._zh(r) if not self.mock else r

    async def _post_zh(self, path, payload):
        r = await self._post(path, payload)
        return self._zh(r) if not self.mock else r

    async def 相机_制冷(self, 目标温度, 是否开启=True):
        if self.mock:
            return await self._post("/camera/cooler", {"目标温度": 目标温度, "是否开启": 是否开启})
        r = await self._get(f"/equipment/camera/cool",
                            Temp=目标温度, On=str(是否开启).lower())
        return {"状态": "指令已发送", "目标温度": 目标温度, "详情": r}

    async def 相机_曝光(self, 曝光时长, 增益=120, 偏置=10, 是否保存=False):
        if self.mock:
            return await self._post("/camera/exposure",
                {"曝光时长": 曝光时长, "增益": 增益, "偏置": 偏置, "是否保存": 是否保存})
        r = await self._get("/equipment/camera/capture",
                            exposure=曝光时长, gain=增益, save=str(是否保存).lower(),
                            waitForResult="true", omitImage="true")
        return self._zh(r)

    async def 相机_读参数(self):
        return await self._get_zh("/equipment/camera/info")

    async def 赤道仪_GOTO(self, 目标):
        if self.mock:
            return await self._post("/mount/goto", {"目标": 目标})
        # 目标名→坐标由LLM/解析服务处理, 这里接收赤道坐标
        return {"提示": "请提供赤道坐标或先用星点解析同步", "目标": 目标}

    async def 赤道仪_跟踪(self, 是否开启, 模式="恒星"):
        if self.mock:
            return await self._post("/mount/tracking", {"是否开启": 是否开启, "模式": 模式})
        r = await self._get("/equipment/mount/set-tracking", enabled=str(是否开启).lower())
        return {"状态": "跟踪已开启" if 是否开启 else "跟踪已停止", "详情": self._zh(r)}

    async def 赤道仪_停泊(self):
        if self.mock:
            return await self._post("/mount/park", {})
        r = await self._get("/equipment/mount/park")
        return {"状态": "停泊指令已发送", "详情": self._zh(r)}

    async def 赤道仪_坐标同步(self, 赤经, 赤纬):
        if self.mock:
            return await self._post("/mount/sync", {"赤经": 赤经, "赤纬": 赤纬})
        r = await self._get("/equipment/mount/sync-to-target")
        return {"状态": "同步完成", "详情": self._zh(r)}

    async def 调焦_移动(self, 步数, 方向="外"):
        s = 步数 if 方向 == "外" else -步数
        if self.mock:
            return await self._post("/focuser/move", {"步数": s})
        r = await self._get("/equipment/focuser/move", steps=s)
        return {"状态": "移动完成", "详情": self._zh(r)}

    async def 调焦_全自动对焦(self, 曝光时长=3, 滤镜="当前"):
        if self.mock:
            return await self._post("/focuser/fullaf", {"曝光时长": 曝光时长, "滤镜": 滤镜})
        r = await self._get("/equipment/focuser/auto-focus")
        return {"状态": "自动对焦已启动", "详情": self._zh(r)}

    async def 滤镜轮_切换(self, 滤镜):
        if self.mock:
            return await self._post("/filterwheel/set", {"滤镜": 滤镜})
        r = await self._get("/equipment/filterwheel/set", filter=滤镜)
        return {"状态": "滤镜切换完成", "详情": self._zh(r)}

    async def 滤镜轮_位置(self):
        return await self._get_zh("/equipment/filterwheel/info")

    async def 导星_启停(self, 是否开启):
        if self.mock:
            return await self._post("/guider/enable", {"是否开启": 是否开启})
        r = await self._get("/equipment/guider" + ("/start" if 是否开启 else "/stop"))
        return {"状态": "导星已启动" if 是否开启 else "导星已停止", "详情": self._zh(r)}

    async def 导星_Dither(self, 像素=2):
        if self.mock:
            return await self._post("/guider/dither", {"像素": 像素})
        r = await self._get("/equipment/guider/dither", pixels=像素)
        return {"状态": "抖动完成", "详情": self._zh(r)}

    async def 星点解析(self, 曝光时长=5):
        if self.mock:
            return await self._post("/platesolve", {"曝光时长": 曝光时长})
        r = await self._get("/equipment/camera/capture",
                            exposure=曝光时长, omitImage="true", platesolve="true",
                            waitForResult="true")
        return self._zh(r)

    async def 序列_控制(self, 操作):
        if self.mock:
            return await self._post("/sequence/control", {"操作": 操作})
        m = {"启动": "start", "停止": "stop", "暂停": "pause", "继续": "resume", "重置": "reset"}
        r = await self._get(f"/sequence/{m.get(操作, 'start')}")
        return {"状态": f"序列{操作}指令已发送", "详情": self._zh(r)}

    async def 状态总览(self, 明细="概要"):
        return await self._get_zh("/equipment/info")

    async def 天气_安全检查(self):
        """天气全量+智能安全判断(NINA SafetyMonitor未配置时星枢自己算)"""
        r = await self._get("/equipment/weather/info")
        d = r.get("Response", r) if isinstance(r, dict) else {}
        if d.get("SafeToOperate") is not None:
            safe = bool(d.get("SafeToOperate"))
            basis = "NINA安全监控判定"
        else:
            # 星枢规则判定(保守阈值)
            reasons = []
            safe = True
            cloud = d.get("CloudCover")
            rain = d.get("RainRate")
            wind = d.get("WindSpeed")
            gust = d.get("WindGust")
            hum = d.get("Humidity")
            if isinstance(cloud, (int, float)) and cloud > 90:
                safe = False; reasons.append(f"云量{cloud:.0f}%过高")
            if isinstance(rain, (int, float)) and rain > 0:
                safe = False; reasons.append(f"降雨率{rain}>0,正在下雨")
            if isinstance(gust, (int, float)) and gust > 40:
                safe = False; reasons.append(f"阵风{gust:.0f}km/h过强")
            if isinstance(wind, (int, float)) and wind > 30:
                safe = False; reasons.append(f"风速{wind:.0f}km/h过强")
            if isinstance(hum, (int, float)) and hum > 95:
                safe = False; reasons.append(f"湿度{hum:.0f}%过高,结露风险")
            basis = "星枢规则判定" + ("(云量70-90%建议关注)" if isinstance(cloud, (int, float)) and 70 <= cloud <= 90 else "")
            if isinstance(cloud, (int, float)) and 70 <= cloud <= 90 and safe:
                reasons.append(f"云量{cloud:.0f}%,观测条件一般")
        return {
            "天气安全": "✅ 安全,可正常拍摄" if safe else "⚠️ 不安全,建议停泊避险",
            "判定依据": basis,
            "风险明细": reasons or ["各项指标正常"],
            "温度": d.get("Temperature"), "湿度": d.get("Humidity"),
            "云量": f'{d.get("CloudCover")}%' if d.get("CloudCover") is not None else None,
            "风速": d.get("WindSpeed"), "阵风": d.get("WindGust"),
            "降雨率": d.get("RainRate"), "气压": d.get("Pressure"),
        }
