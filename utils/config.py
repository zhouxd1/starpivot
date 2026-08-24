# -*- coding: utf-8 -*-
"""config.py 重写 — frozen感知 + 内联模板"""
import shutil
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller: .env 放 exe 同级目录
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent

CFG = {}

INLINE_ENV = (
    "# 星枢配置 — 填入你的模型Key\n"
    "DEEPSEEK_API_KEY=\n"
    "ZHIPU_API_KEY=\n"
    "MODEL_ROUTE=auto\n"
    "STARPIVOT_CHANNELS=\n"
    "NINA_API_HOST=127.0.0.1\n"
    "NINA_API_PORT=1888\n"
    "NINA_MOCK=false\n"
    "OBS_LAT=40.0\n"
    "OBS_LON=116.4\n"
)


def load():
    CFG.clear()
    env = ROOT / ".env"
    if not env.exists():
        example = ROOT / ".env.example"
        if example.exists():
            shutil.copy(example, env)
        else:
            env.write_text(INLINE_ENV, encoding="utf-8")
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            CFG[k.strip()] = v.strip()


load()
