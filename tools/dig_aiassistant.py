# -*- coding: utf-8 -*-
"""从 AI Assistant dll 抓 MCP 工具定义"""
import re, sys, io
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
DLL = r"C:\Users\love_\AppData\Local\NINA\Plugins\3.0.0\AI Assistant\NINA.Plugin.AIAssistant.dll"
data = open(DLL, "rb").read()
print(f"dll大小: {len(data)//1024}KB")

# .NET字符串=UTF-16LE
text16 = data.decode("utf-16-le", errors="ignore")
text8 = data.decode("utf-8", errors="ignore")

# 1. JSON片段(MCP工具定义常见结构)
for pat, label in [
    (r'"(?:name|Name)"\s*:\s*"([A-Za-z_][\w]{3,50})"', "JSON name字段"),
    (r'"(?:description|Description)"\s*:\s*"([^"]{10,120})"', "JSON描述"),
]:
    found = re.findall(pat, text8) + re.findall(pat, text16)
    uniq = list(dict.fromkeys(found))
    print(f"\n=== {label} ({len(uniq)}) ===")
    for x in uniq[:50]:
        print("  ", x)
