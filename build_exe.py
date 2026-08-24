# -*- coding: utf-8 -*-
"""星枢打包配置 — PyInstaller"""
import PyInstaller.__main__
import sys

ARGS = [
    "main.py",
    "--name=StarPivot",
    "--onedir",                    # onedir比onefile启动快, 杀软误报少
    "--windowed",                  # 无控制台黑窗
    "--icon=app/assets/icon.ico",
    "--add-data=data;data",        # 星表
    "--add-data=astro_agent;astro_agent",  # 系统提示词
    "--add-data=static;static",    # 控制台
    "--add-data=utils;utils",
    "--add-data=mcp_engine;mcp_engine",
    "--add-data=nina_sdk;nina_sdk",
    "--add-data=report_builder.py;.",
    "--add-data=settings_api.py;.",
    "--add-data=.env.example;.",
    "--hidden-import=uvicorn.logging",
    "--hidden-import=uvicorn.loops.auto",
    "--hidden-import=uvicorn.protocols.http.auto",
    "--hidden-import=uvicorn.protocols.websockets.auto",
    "--hidden-import=websockets",
    "--exclude-module=tkinter",
    "--exclude-module=matplotlib",
    "--exclude-module=PyQt5",
    "--clean",
    "--noconfirm",
    "--distpath=dist2",
    "--workpath=build",
]
PyInstaller.__main__.run(ARGS)
