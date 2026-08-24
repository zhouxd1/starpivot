# -*- coding: utf-8 -*-
"""
星枢模型层 — 模型无关: Ollama本地 / DeepSeek / 智谱, auto自动降级
"""
import json, time, logging
import httpx
from utils.config import CFG

log = logging.getLogger("starpivot")


class ModelRouter:
    """通用模型路由: 适配所有常用模型(任何OpenAI兼容端点), .env零改码接入
    内置: Ollama本地/DeepSeek/智谱; 自定义: STARPIVOT_CHANNELS(JSON数组, 接任意模型)"""

    def __init__(self):
        self.route = CFG.get("MODEL_ROUTE", "auto")
        self.channels = []
        # 内置通道(常用模型全家桶)
        BUILTIN = {
            "DEEPSEEK":  ("DeepSeek",  "https://api.deepseek.com/v1",                     "deepseek-chat"),
            "ZHIPU":     ("智谱GLM",   "https://open.bigmodel.cn/api/paas/v4",            "glm-4-flash"),
            "MOONSHOT":  ("Kimi",      "https://api.moonshot.cn/v1",                      "moonshot-v1-8k"),
            "QWEN":      ("通义千问",  "https://dashscope.aliyuncs.com/compatible-mode/v1","qwen-plus"),
            "DOUBAO":    ("豆包",      "https://ark.cn-beijing.volces.com/api/v3",        "doubao-pro-32k"),
            "MINIMAX":   ("MiniMax",   "https://api.minimax.chat/v1",                     "abab6.5s-chat"),
            "OPENAI":    ("OpenAI",    "https://api.openai.com/v1",                       "gpt-4o-mini"),
            "GEMINI":    ("Gemini",    "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.0-flash"),
            "OPENROUTER":("OpenRouter","https://openrouter.ai/api/v1",                    "openai/gpt-4o-mini"),
        }
        for envk, (name, base, model) in BUILTIN.items():
            if CFG.get(f"{envk}_API_KEY"):
                self.channels.append({"名": name, "类型": "openai兼容",
                    "base": base, "key": CFG[f"{envk}_API_KEY"], "model": model})
        # ★ 通用自定义: base_url + model + key 三字段(任何OpenAI兼容端点)
        if CFG.get("CUSTOM_BASE_URL") and CFG.get("CUSTOM_API_KEY"):
            self.channels.append({"名": "自定义", "类型": "openai兼容",
                "base": CFG["CUSTOM_BASE_URL"].rstrip("/"),
                "key": CFG["CUSTOM_API_KEY"],
                "model": CFG.get("CUSTOM_MODEL") or "custom-model"})
        # 排序: cloud优先时云端在前(本地殿后), local纯本地, auto本地优先云端兜底
        if self.route == "cloud":
            self.channels.sort(key=lambda c: c["名"] == "Ollama本地")
        elif self.route == "local":
            self.channels = [c for c in self.channels if c["名"] == "Ollama本地"] or self.channels
        self._cooldown = {}   # 通道名 → 冷却截止
        log.info(f"模型通道注册: {[c['名'] for c in self.channels]} (路由={self.route})")

    async def chat(self, messages, tools=None, temperature=0.2, max_tokens=1500) -> dict:
        """统一入口, 返回 {content, tool_calls, channel}"""
        order = [c for c in self.channels if self._cooldown.get(c["名"], 0) < time.time()]
        order = order or self.channels
        last_err = None
        for ch in order:
            try:
                t0 = time.time()
                payload = {"model": ch["model"], "messages": messages,
                           "temperature": temperature, "max_tokens": max_tokens}
                if tools:
                    payload["tools"] = tools
                async with httpx.AsyncClient(timeout=90) as c:
                    r = await c.post(ch["base"] + "/chat/completions",
                                     headers={"Authorization": f'Bearer {ch["key"]}'},
                                     json=payload)
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP{r.status_code}: {r.text[:100]}")
                msg = r.json()["choices"][0]["message"]
                out = {"content": msg.get("content") or "",
                       "tool_calls": None, "channel": ch["名"],
                       "耗时": round(time.time() - t0, 1)}
                tcs = msg.get("tool_calls")
                if tcs:
                    parsed = []
                    for tc in tcs:
                        try:
                            args = json.loads(tc["function"]["arguments"] or "{}")
                        except Exception:
                            args = {}
                        parsed.append({"name": tc["function"]["name"], "args": args})
                    out["tool_calls"] = parsed
                log.info(f"🧠 {ch['名']} {out['耗时']}s tools={bool(out['tool_calls'])}")
                return out
            except Exception as e:
                last_err = e
                log.warning(f"通道{ch['名']}失败: {str(e)[:80]}, 切下一个")
                self._cooldown[ch["名"]] = time.time() + 60
        return {"content": f"所有模型通道不可用(最后错误: {last_err})", "tool_calls": None,
                "channel": "无", "耗时": 0}
