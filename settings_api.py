# -*- coding: utf-8 -*-
"""系统设置API — 挂到main.py(独立模块避免转义地狱)"""
import re
from pathlib import Path


def register_settings_api(app, ROOT):
    ENV_FILE = ROOT / ".env"

    def _read_env():
        cur = {}
        if ENV_FILE.exists():
            for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
                m = re.match(r"^([A-Z_]+)=(.*)", line.strip())
                if m:
                    cur[m.group(1)] = m.group(2)
        return cur

    @app.get("/api/settings")
    async def api_get_settings():
        d = _read_env()
        def _mask(k):
            v = d.get(k, "")
            return (v[:6] + "***" + v[-4:]) if len(v) > 14 else (v[:4] + "***" if v else "")
        keys = ["DEEPSEEK", "ZHIPU", "MOONSHOT", "QWEN", "DOUBAO",
                "MINIMAX", "OPENAI", "GEMINI", "OPENROUTER"]
        out = {"OBS_LAT": d.get("OBS_LAT", "40.0"),
               "OBS_LON": d.get("OBS_LON", "116.4"),
               "SITE_NAME": d.get("SITE_NAME", "我的观测点"),
               "TELESCOPE_FOCAL": d.get("TELESCOPE_FOCAL", ""),
               "TELESCOPE_NAME": d.get("TELESCOPE_NAME", ""),
               "MODEL_ROUTE": d.get("MODEL_ROUTE", "auto"),
               # 通用自定义(三字段)
               "CUSTOM_BASE_URL": d.get("CUSTOM_BASE_URL", ""),
               "CUSTOM_MODEL": d.get("CUSTOM_MODEL", ""),
               "CUSTOM_API_KEY_MASKED": _mask("CUSTOM_API_KEY"),
               "HAS_CUSTOM": bool(d.get("CUSTOM_API_KEY")) and bool(d.get("CUSTOM_BASE_URL"))}
        for k in keys:
            out[f"{k}_API_KEY_MASKED"] = _mask(f"{k}_API_KEY")
            out[f"HAS_{k}"] = bool(d.get(f"{k}_API_KEY"))
        return out

    @app.post("/api/settings")
    async def api_set_settings(body: dict):
        cur = _read_env()
        for k in ("OBS_LAT", "OBS_LON", "SITE_NAME",
                  "TELESCOPE_FOCAL", "TELESCOPE_NAME", "MODEL_ROUTE",
                  "CUSTOM_BASE_URL", "CUSTOM_MODEL", "CUSTOM_API_KEY",
                  "DEEPSEEK_API_KEY", "ZHIPU_API_KEY", "MOONSHOT_API_KEY",
                  "QWEN_API_KEY", "DOUBAO_API_KEY", "MINIMAX_API_KEY",
                  "OPENAI_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
            if k in body and body[k] is not None and str(body[k]).strip():
                cur[k] = str(body[k]).strip()
        lines = ["# starpivot settings (控制台生成)"]
        lines += [f"{k}={v}" for k, v in cur.items()]
        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # 热重载: 重读env + CFG版本号(main侧get_router检测到即重建)
        try:
            from utils.config import load as cfg_load
            cfg_load()
            import utils.config as _uc
            _uc.ROUTER_VER = getattr(_uc, "ROUTER_VER", 0) + 1
        except Exception as _e:
            pass
        # 保存后自动验证新增key(不阻塞, 快速反馈)
        verify = ""
        try:
            import httpx as _hx
            if cur.get("DEEPSEEK_API_KEY") and body.get("DEEPSEEK_API_KEY"):
                r = _hx.post("https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {cur['DEEPSEEK_API_KEY']}"},
                    json={"model": "deepseek-chat", "messages": [{"role": "user", "content": "OK"}],
                          "max_tokens": 3}, timeout=15)
                verify = " · DeepSeek Key" + ("有效✅" if r.status_code == 200 else f"无效({r.status_code})❌")
        except Exception:
            pass
        return {"ok": True, "msg": "已保存, 模型配置已热生效" + verify}

    @app.post("/api/test_model")
    async def api_test_model(body: dict = None):
        import httpx
        cur = _read_env()
        results = []
        ok_any = False
        # DeepSeek
        if cur.get("DEEPSEEK_API_KEY"):
            try:
                r = await httpx.AsyncClient(timeout=20).post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {cur['DEEPSEEK_API_KEY']}"},
                    json={"model": "deepseek-chat",
                          "messages": [{"role": "user", "content": "回复OK"}], "max_tokens": 5})
                ok = r.status_code == 200
                ok_any |= ok
                results.append(("DeepSeek", "✅" if ok else f"❌{r.status_code}"))
            except Exception as e:
                results.append(("DeepSeek", f"❌{str(e)[:30]}"))
        # 智谱
        if cur.get("ZHIPU_API_KEY"):
            try:
                r = await httpx.AsyncClient(timeout=20).post(
                    "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                    headers={"Authorization": f"Bearer {cur['ZHIPU_API_KEY']}"},
                    json={"model": "glm-4-flash",
                          "messages": [{"role": "user", "content": "回复OK"}], "max_tokens": 5})
                ok = r.status_code == 200
                ok_any |= ok
                results.append(("智谱", "✅" if ok else f"❌{r.status_code}"))
            except Exception as e:
                results.append(("智谱", f"❌{str(e)[:30]}"))
        if not results:
            return {"ok": False, "msg": "未配置任何模型Key — 请填写后保存再测试"}
        return {"ok": ok_any,
                "msg": " | ".join(f"{n}:{s}" for n, s in results)}
