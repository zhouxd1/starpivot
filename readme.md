# 🌌 星枢 StarPivot AstroAI

**N.I.N.A 全自动天文摄影系统的私有化、全中文、AI 智能控制中枢。**

解决 NINA 生态插件全英文、无原生中文 AI 自动化能力的痛点——用一句中文指挥整套天文设备。

```
"今晚拍什么?" → 推荐目标+最佳时段+月距+焦段匹配
"把CCD降到零下10度" → 真实制冷指令
"开始拍巫师星云" → GOTO→导星→序列 一键串联
```

## ✨ 功能

- **全中文 AI 对话控制** — 自然语言指挥 NINA(DeepSeek/智谱/Kimi/通义/豆包/OpenAI/Gemini/OpenRouter/自定义端点,12 通道自动降级)
- **136 个中文 MCP 工具** — 相机/赤道仪/调焦/滤轮/导星/序列/圆顶/平场/旋转器/开关/天气,全设备覆盖
- **观测规划** — 137 目标离线星表 + 中天时刻 + 月相月距避让 + 位置四级检测 + 拍摄参数计算器(12 传感器/光污染分级)
- **监控驾驶舱** — 三栏大屏:实时画面/序列进度/9 设备状态/气象四宫格/云量趋势/HFR 曲线,8 秒刷新
- **安全守护** — 天气智能判定/风险分级工具/日程提醒/进度播报/红光模式
- **数据沉淀** — 观测报告(七段式 Markdown)+ SQLite 历史库("巫师星云拍了多久"秒答)
- **一键开拍** — GOTO→到达确认→导星→序列 全自动串联
- **Electron 桌面壳** — 托盘常驻/全局热键/红光模式

## 📦 下载

- ** Releases 下载开箱即用的桌面版(星枢.exe)**: [github.com/zhouxd1/starpivot/releases](https://github.com/zhouxd1/starpivot/releases)
- 源码运行见下方快速开始

## 🚀 快速开始

```bash
# 1. 环境: Windows 10/11 + Python 3.10-3.12 + N.I.N.A + Advanced-API 插件(1888端口)
# 2. 安装
uv venv && uv pip install -r requirements.txt   # 或 pip install -r requirements.txt

# 3. 首次运行(自动生成 .env 模板)
python main.py

# 4. 浏览器打开 http://127.0.0.1:8899
#    → 设置面板填模型 Key(秒生效) + 观测位置 + 望远镜 → 开用
```

**打包 exe**(分发用):`python build_exe.py` → `dist2/StarPivot/`

## 📁 结构

```
starpivot/
├── main.py               # FastAPI 服务(对话/监控/设置/报告)
├── astro_agent/          # 模型路由(12通道) + 观测规划 + 参数计算 + 日程引擎
├── mcp_engine/           # 136 中文工具库 + 执行器(风险分级/参数修复)
├── nina_sdk/             # Advanced-API 封装(英进中出)
├── static/index.html     # 三栏监控驾驶舱
├── data/targets.json     # 137 目标离线星表
└── report_builder.py     # 观测报告生成器
```

## ⚠️ 注意

- 需本机运行 N.I.N.A 并安装 [Advanced-API](https://github.com/duddie-nina/Advanced-Api-NINA) 插件(默认端口 1888)
- 打包的未签名 exe 可能被杀软拦截,请添加信任
- 模型 Key 保存在本地 `.env`,不会上传

## License

MIT
