# -*- coding: utf-8 -*-
"""
星枢全量MCP工具库 V3 — AI-Assistant 114工具 1:1 对齐
每个工具直接映射 Advanced-API v2 真实端点; 无对应端点的走最近端点并优雅降级
格式: (英文工具名, 中文说明, "METHOD path", {参数}, 风险级)
"""
import json
from pathlib import Path

T = []
def add(name, desc, ep, params=None, risk="低"):
    T.append((name, desc, ep, params or {}, risk))

# ═══════════ 相机 (11) ═══════════
add("camera_connect", "连接相机", "GET /equipment/camera/connect")
add("camera_disconnect", "断开相机", "GET /equipment/camera/disconnect", {}, "中")
add("camera_info", "读取相机全部参数(温度/增益/像元/位深/ROI)", "GET /equipment/camera/info", {}, "无")
add("camera_list_devices", "列出可用相机设备", "GET /equipment/camera/list-devices", {}, "无")
add("camera_capture_image", "拍摄一张(可保存/统计/解析)",
    "GET /equipment/camera/capture",
    {"exposure": ("number", "曝光秒数", True), "gain": ("integer", "增益", False),
     "save": ("boolean", "是否保存到磁盘", False), "binning": ("integer", "像素合并1/2/3", False),
     "omitImage": ("boolean", "true=只要统计不要图", False),
     "platesolve": ("boolean", "拍摄后星点解析", False),
     "targetName": ("string", "目标名(保存文件用)", False),
     "waitForResult": ("boolean", "等待拍摄完成", False)})
add("camera_abort_exposure", "中止当前曝光", "GET /equipment/camera/abort-exposure")
add("camera_cool", "设置CCD制冷目标温度", "GET /equipment/camera/cool",
    {"temp": ("number", "目标温度℃(如-10)", True), "on": ("boolean", "是否开启制冷", False)}, "中")
add("camera_warm", "CCD回温(防结露缓升)", "GET /equipment/camera/warm", {}, "中")
add("camera_dew_heater", "控制除露带功率", "GET /equipment/camera/dew-heater",
    {"power": ("number", "功率0-100", True)})
add("camera_set_binning", "设置像素合并", "GET /equipment/camera/set-binning",
    {"binning": ("integer", "合并模式1/2/3", True)})
add("camera_set_readout_mode", "设置读出模式", "GET /equipment/camera/set-readout-mode/image",
    {"mode": ("string", "读出模式名或序号", True)})

# ═══════════ 赤道仪 (14) ═══════════
add("mount_connect", "连接赤道仪", "GET /equipment/mount/connect")
add("mount_disconnect", "断开赤道仪", "GET /equipment/mount/disconnect", {}, "中")
add("mount_info", "赤道仪状态(赤经赤纬/高度方位/停泊/跟踪/中天翻转)", "GET /equipment/mount/info", {}, "无")
add("mount_list_devices", "列出可用赤道仪", "GET /equipment/mount/list-devices", {}, "无")
add("mount_rescan", "重新扫描赤道仪设备", "GET /equipment/mount/rescan", {}, "低")
add("mount_park", "停泊赤道仪(收工)", "GET /equipment/mount/park", {}, "高")
add("mount_unpark", "解除停泊", "GET /equipment/mount/unpark", {}, "高")
add("mount_slew", "GOTO转向(赤道坐标)", "GET /equipment/mount/slew",
    {"ra": ("string", "赤经(度如10.684或时:分:秒)", True),
     "dec": ("string", "赤纬(度如41.28)", True)}, "中")
add("mount_slew_altaz", "GOTO转向(地平坐标)", "GET /equipment/mount/slew",
    {"alt": ("number", "地平高度角", True), "az": ("number", "方位角0-360", True)}, "中")
add("mount_flip", "手动过中天翻转", "GET /equipment/mount/flip", {}, "高")
add("mount_set_tracking", "开关跟踪", "GET /equipment/mount/tracking",
    {"enabled": ("boolean", "开/关", True)}, "中")
add("mount_set_tracking_mode", "设置跟踪模式", "GET /equipment/mount/tracking",
    {"mode": ("string", "sidellar恒星/lunar月球/solar太阳", True)}, "中")
add("mount_sync_to_target", "坐标同步到目标(校准)", "GET /equipment/rotator/sync", {}, "中")
add("mount_stop", "紧急停止赤道仪", "GET /equipment/mount/stop-slew", {}, "高")
add("mount_set_park_position", "设置停泊位置为当前", "GET /equipment/mount/set-park-position", {}, "中")
add("mount_find_home", "赤道仪找Home位", "GET /equipment/mount/home", {}, "中")

# ═══════════ 调焦座 (7) ═══════════
add("focuser_connect", "连接调焦座", "GET /equipment/focuser/connect")
add("focuser_disconnect", "断开调焦座", "GET /equipment/focuser/disconnect", {}, "中")
add("focuser_info", "调焦座状态(位置/温度/移动中)", "GET /equipment/focuser/info", {}, "无")
add("focuser_list_devices", "列出可用调焦座", "GET /equipment/focuser/list-devices", {}, "无")
add("focuser_rescan", "重新扫描调焦座", "GET /equipment/focuser/rescan", {}, "低")
add("focuser_move", "移动调焦座", "GET /equipment/focuser/move",
    {"steps": ("integer", "步数(正外负内)", True)})
add("focuser_stop_move", "停止调焦座移动", "GET /equipment/focuser/move", {}, "中")
add("focuser_autofocus", "启动全自动对焦(V曲线)", "GET /equipment/focuser/auto-focus", {}, "低")

# ═══════════ 滤镜轮 (5) ═══════════
add("filterwheel_connect", "连接滤镜轮", "GET /equipment/filterwheel/connect")
add("filterwheel_disconnect", "断开滤镜轮", "GET /equipment/filterwheel/disconnect", {}, "中")
add("filterwheel_info", "滤镜轮信息(位置/滤镜列表)", "GET /equipment/filterwheel/info", {}, "无")
add("filterwheel_set", "切换滤镜", "GET /equipment/filterwheel/change-filter",
    {"filter": ("string", "滤镜名L/R/G/B/Ha/OIII/SII或序号", True)})
add("filterwheel_rescan", "重新扫描滤镜轮", "GET /equipment/filterwheel/rescan", {}, "低")
add("filterwheel_list_devices", "列出可用滤镜轮", "GET /equipment/filterwheel/list-devices", {}, "无")
add("filter_add", "添加滤镜到配置", "GET /profile/change-value",
    {"name": ("string", "滤镜名", True), "value": ("string", "位置", True)}, "中")
add("filter_remove", "移除滤镜", "GET /profile/change-value",
    {"name": ("string", "滤镜名", True), "value": ("string", "删除", True)}, "中")

# ═══════════ 导星 (9) ═══════════
add("guider_connect", "连接导星", "GET /equipment/guider/connect")
add("guider_disconnect", "断开导星", "GET /equipment/guider/disconnect", {}, "中")
add("guider_info", "导星状态(RMS/校正/误差)", "GET /equipment/guider/info", {}, "无")
add("guider_list_devices", "列出可用导星设备", "GET /equipment/guider/list-devices", {}, "无")
add("guider_rescan", "重新扫描导星", "GET /equipment/guider/rescan", {}, "低")
add("guider_start", "开始导星", "GET /equipment/guider/start", {}, "中")
add("guider_stop", "停止导星", "GET /equipment/guider/stop", {}, "中")
add("guider_dither", "Dither抖动(防热噪)", "GET /equipment/guider/start",
    {"pixels": ("integer", "抖动像素(默认2)", False)})
add("guider_clear_calibration", "清除导星校正(换镜后)", "GET /equipment/guider/clear-calibration", {}, "中")
add("guider_get_graph", "获取导星曲线数据", "GET /equipment/guider/graph", {}, "无")

# ═══════════ 序列 (10) ═══════════
add("sequence_start", "启动拍摄序列", "GET /sequence/start", {}, "高")
add("sequence_stop", "停止拍摄序列", "GET /sequence/stop", {}, "高")
add("sequence_pause", "暂停拍摄序列", "GET /sequence/skip", {}, "中")
add("sequence_resume", "继续拍摄序列", "GET /sequence/start", {}, "中")
add("sequence_reset", "重置拍摄序列", "GET /sequence/reset", {}, "中")
add("sequence_skip", "跳过当前序列步骤", "GET /sequence/skip", {}, "中")
add("sequence_state", "序列状态(进度/当前步骤/统计)", "GET /sequence/state", {}, "无")
add("sequence_set_target", "设置序列目标", "GET /sequence/set-target",
    {"targetName": ("string", "目标名如M31", True)}, "中")
add("sequence_list_available", "列出可用序列模板", "GET /sequence/list-available", {}, "无")
add("sequence_load", "加载序列(从模板)", "GET /sequence/load",
    {"name": ("string", "序列名", True)}, "中")
add("sequence_edit", "编辑序列参数", "GET /sequence/edit",
    {"targetName": ("string", "改目标名", False), "exposure": ("number", "改曝光时长", False)}, "中")

# ═══════════ 圆顶 (10) ═══════════
add("dome_connect", "连接圆顶", "GET /equipment/dome/connect")
add("dome_disconnect", "断开圆顶", "GET /equipment/dome/disconnect", {}, "中")
add("dome_info", "圆顶状态(舱盖/方位/跟随)", "GET /equipment/dome/info", {}, "无")
add("dome_list_devices", "列出可用圆顶", "GET /equipment/dome/list-devices", {}, "无")
add("dome_rescan", "重新扫描圆顶", "GET /equipment/dome/rescan", {}, "低")
add("dome_open_shutter", "打开圆顶舱盖", "GET /equipment/dome/open-shutter", {}, "高")
add("dome_close_shutter", "关闭圆顶舱盖", "GET /equipment/dome/close-shutter", {}, "高")
add("dome_park", "圆顶回停泊位", "GET /equipment/dome/park", {}, "中")
add("dome_home", "圆顶找Home", "GET /equipment/dome/home", {}, "中")
add("dome_slew", "圆顶转到方位角", "GET /equipment/dome/slew",
    {"azimuth": ("number", "方位角0-360", True)}, "中")
add("dome_stop", "停止圆顶移动", "GET /equipment/dome/stop-movement", {}, "中")
add("dome_set_follow", "设置圆顶跟随望远镜", "GET /equipment/dome/set-follow",
    {"enabled": ("boolean", "跟随开/关", True)})
add("dome_sync_telescope", "圆顶同步望远镜方位", "GET /equipment/dome/sync-to-telescope", {}, "中")
add("dome_set_park_position", "设置圆顶停泊位", "GET /equipment/dome/set-park-position",
    {"azimuth": ("number", "停泊方位角", True)}, "中")

# ═══════════ 平场板 (9) ═══════════
add("flatpanel_connect", "连接平场板", "GET /equipment/flatdevice/connect")
add("flatpanel_disconnect", "断开平场板", "GET /equipment/flatdevice/disconnect", {}, "中")
add("flatpanel_info", "平场板状态(亮度/开合/灯)", "GET /equipment/flatdevice/info", {}, "无")
add("flatpanel_list_devices", "列出可用平场板", "GET /equipment/flatdevice/list-devices", {}, "无")
add("flatpanel_rescan", "重新扫描平场板", "GET /equipment/flatdevice/rescan", {}, "低")
add("flatpanel_set_brightness", "设置平场板亮度", "GET /equipment/flatdevice/set-brightness",
    {"brightness": ("number", "亮度0-100", True)})
add("flatpanel_set_cover", "开合平场板盖", "GET /equipment/flatdevice/set-cover",
    {"open": ("boolean", "开/关", True)}, "中")
add("flatpanel_set_light", "开关平场板灯", "GET /equipment/flatdevice/set-light",
    {"on": ("boolean", "开/关", True)})
# 平场拍摄流程
add("flats_skyflat", "拍天空平场", "GET /flats/skyflat", {}, "中")
add("flats_trained_flat", "拍训练平场", "GET /flats/trained-flat", {}, "中")
add("flats_trained_dark_flat", "拍训练暗平场", "GET /flats/trained-dark-flat", {}, "中")
add("flats_auto_brightness", "平场自动亮度校准", "GET /flats/auto-brightness")
add("flats_auto_exposure", "平场自动曝光校准", "GET /flats/auto-exposure")
add("flats_status", "平场拍摄进度", "GET /flats/status", {}, "无")
add("flats_stop", "停止平场拍摄", "GET /flats/stop", {}, "中")

# ═══════════ 旋转器 (7) ═══════════
add("rotator_connect", "连接旋转器", "GET /equipment/rotator/connect")
add("rotator_disconnect", "断开旋转器", "GET /equipment/rotator/disconnect", {}, "中")
add("rotator_info", "旋转器状态(角度/机械范围)", "GET /equipment/rotator/info", {}, "无")
add("rotator_list_devices", "列出可用旋转器", "GET /equipment/rotator/list-devices", {}, "无")
add("rotator_rescan", "重新扫描旋转器", "GET /equipment/rotator/rescan", {}, "低")
add("rotator_move", "旋转器转到角度", "GET /equipment/rotator/move",
    {"position": ("number", "目标角度", True)}, "中")
add("rotator_move_mechanical", "旋转器机械移动", "GET /equipment/rotator/move-mechanical",
    {"position": ("number", "机械位置", True)}, "中")
add("rotator_halt", "旋转器急停", "GET /equipment/rotator/halt", {}, "高")
add("rotator_set_reverse", "设置旋转器反向", "GET /equipment/rotator/reverse",
    {"enabled": ("boolean", "反向开/关", True)}, "中")
add("rotator_set_mechanical_range", "设置机械范围", "GET /equipment/rotator/set-mechanical-range",
    {"min": ("number", "最小", True), "max": ("number", "最大", True)}, "中")

# ═══════════ 电子开关 (5) ═══════════
add("switch_connect", "连接电子开关(电源箱)", "GET /equipment/switch/connect")
add("switch_disconnect", "断开电子开关", "GET /equipment/switch/disconnect", {}, "中")
add("switch_info", "开关状态(全部通道)", "GET /equipment/switch/info", {}, "无")
add("switch_list_devices", "列出可用开关", "GET /equipment/switch/list-devices", {}, "无")
add("switch_rescan", "重新扫描开关", "GET /equipment/switch/rescan", {}, "低")
add("switch_set", "设置开关通道", "GET /equipment/switch/set",
    {"id": ("string", "通道号", True), "on": ("boolean", "开/关", True)}, "中")
add("switch_get_channels", "读取开关通道详情", "GET /equipment/switch/info", {}, "无")

# ═══════════ 安全监控 (4) ═══════════
add("safetymonitor_connect", "连接安全监控", "GET /equipment/safetymonitor/connect")
add("safetymonitor_disconnect", "断开安全监控", "GET /equipment/safetymonitor/disconnect", {}, "中")
add("safetymonitor_info", "安全监控状态(是否安全运行)", "GET /equipment/safetymonitor/info", {}, "无")
add("safetymonitor_list_devices", "列出可用安全监控", "GET /equipment/safetymonitor/list-devices", {}, "无")
add("safetymonitor_rescan", "重新扫描安全监控", "GET /equipment/safetymonitor/rescan", {}, "低")

# ═══════════ 天气 (3) ═══════════
add("weather_status", "天气安全检查(云/雨/风/湿+智能判定)", "LOCAL /weather", {}, "无")
add("weather_cross", "天气多源交叉验证: METAR机场实测(观测) vs NINA/OpenMeteo预报, 出摊前最后确认用,能发现预报滞后",
    "LOCAL /workflow",
    {"机场": ("string", "ICAO代码: ZBAA北京/ZSSS上海/ZUUU成都/ZLXY西安 等,默认ZBAA", False)}, "无")
add("history_export", "历史库导出: 全部拍摄记录导出JSON(跨电脑合并用)", "LOCAL /workflow", {}, "无")
add("history_import", "历史库导入: 导入另一台电脑的历史JSON,自动按日期+目标去重合并",
    "LOCAL /workflow", {"路径": ("string", "JSON文件路径", True)}, "中")
add("camera_match", "相机焦段匹配: 给定焦距推荐最合适的相机(采样率/视场/结论全表),买相机或换焦段前用",
    "LOCAL /workflow",
    {"焦距": ("number", "望远镜焦距mm", True), "视宁度": ("number", "当地视宁度角秒(默认2.0)", False)}, "无")
add("obs_report", "观测报告生成: 一键汇总拍摄历史成战报(夜数/张数/曝光/HFR表格),HTML可直接转PDF分享",
    "LOCAL /workflow",
    {"目标": ("string", "目标名,留空=总报告", False)}, "无")
add("sequence_setup", "配置拍摄序列(注入NINA): 把目标+曝光参数直接写进NINA序列 — '拍狮子星云300秒20张'/'把XX加入序列'时用",
    "LOCAL /workflow",
    {"目标": ("string", "目标名(自动查星表坐标)", True),
     "单张曝光秒": ("number", "单张曝光时长,默认300", False),
     "张数": ("number", "总张数,默认20", False),
     "滤镜": ("string", "滤镜名如Ha/L/OIII,默认按星表推荐", False),
     "增益": ("number", "相机增益,默认100(Ha)/120(宽带)", False)}, "中")
add("multi_schedule", "多目标智能排程: 用户要一晚拍多个目标时用,按各目标中天时刻自动排序生成接力时间表",
    "LOCAL /workflow",
    {"目标": ("string", "目标名列表,逗号分隔,如: 巫师星云,心脏星云,象鼻", True)}, "无")
add("guide_rescue", "导星失锁自动抢救: 检测失锁→暂停序列→重新导星→稳定后恢复序列. 导星Lost或用户说导星丢了时用",
    "LOCAL /workflow", {}, "中")
add("start_imaging", "一键开拍流程: GOTO目标→(等到达)→开始导星→启动序列. 用户说'开拍/开始拍X'时用",
    "LOCAL /workflow",
    {"target": ("string", "目标名(自动查星表坐标)", True),
     "start_guide": ("boolean", "是否自动导星(默认是)", False)}, "高")
add("history_query", "观测历史查询: 我拍过哪些目标/累计多长时间/哪晚透明度最好",
    "LOCAL /history",
    {"mode": ("string", "汇总|按目标汇总|最佳夜晚", False),
     "target": ("string", "目标名(按目标汇总时)", False)}, "无")
add("calc_params", "拍摄参数计算器: 目标×焦段×相机→视场/焦段匹配/曝光/增益/总时长/帧数建议",
    "LOCAL /calc",
    {"target": ("string", "目标名(M31/NGC7380)", True),
     "focal": ("number", "焦距mm(默认读设置)", False),
     "sensor": ("string", "相机传感器(如IMX571)", False),
     "light_pollution": ("string", "光污染: 荒野/郊野/郊区/城市边缘/城市", False)}, "无")
add("tonight_targets", "今晚拍什么: 可见目标清单+高度角+月相+评分推荐", "LOCAL /planner",
    {"lat": ("number", "纬度(默认北京)", False), "lon": ("number", "经度", False)}, "无")
add("weather_list_sources", "列出天气数据源", "GET /equipment/weather/info", {}, "无")
add("weather_rescan", "重新扫描天气源", "GET /equipment/weather/rescan", {}, "低")

# ═══════════ 取景助手 (2) ═══════════
add("framing_set_rotation", "设置取景旋转角", "GET /framing/set-rotation",
    {"rotation": ("number", "旋转角度", True)}, "中")
add("framing_set_source", "设置取景目标源", "GET /framing/set-source",
    {"source": ("string", "目标名/坐标", True)}, "中")

# ═══════════ 应用/系统 (12) ═══════════
add("equipment_connect_all", "一键连接全部设备", "GET /equipment/all/connect", {}, "高")
add("equipment_disconnect_all", "一键断开全部设备(收工)", "GET /equipment/all/disconnect", {}, "高")
add("equipment_info", "全部设备状态总览", "GET /equipment/info", {}, "无")
add("nina_get_version", "NINA版本", "GET /version/nina", {}, "无")
add("nina_get_status", "NINA应用状态", "GET /equipment/info", {}, "无")
add("nina_screenshot", "截取NINA界面", "GET /application/screenshot", {}, "无")
add("nina_switch_tab", "切换NINA标签页", "GET /application/switch-tab",
    {"tab": ("string", "标签名如Advanced Sequence", True)}, "无")
add("nina_get_tab", "读取当前标签页", "GET /application/get-tab", {}, "无")
add("nina_get_plugins", "列出已装插件", "GET /application/plugins", {}, "无")
add("nina_get_plugin_settings", "读取插件设置", "GET /application/plugins",
    {}, "无")
add("nina_get_events", "读取事件历史", "GET /image-history", {}, "无")
add("nina_get_images", "读取图像历史", "GET /image/available", {}, "无")
add("nina_show_profile", "打开配置管理", "GET /application/switch-tab",
    {"tab": ("string", "Options", False)}, "无")
add("nina_change_profile_value", "修改NINA配置值", "GET /profile/change-value",
    {"name": ("string", "配置项路径", True), "value": ("string", "新值", True)}, "中")
add("nina_logs", "读取NINA运行日志", "GET /application/logs", {}, "无")
add("nina_time", "NINA主机时间(对时用)", "GET /application/version", {}, "无")

TOOLS = T


def to_llm_schema():
    out = []
    for name, desc, ep, params, risk in TOOLS:
        props, req = {}, []
        for pn, (pt, pd, prereq) in params.items():
            props[pn] = {"type": pt, "description": pd}
            if prereq:
                req.append(pn)
        out.append({"type": "function", "function": {
            "name": name, "description": f"[{risk}] {desc}",
            "parameters": {"type": "object", "properties": props, "required": req}}})
    return out


def find_tool(name):
    for t in TOOLS:
        if t[0] == name:
            return t
    return None
