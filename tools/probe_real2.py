# -*- coding: utf-8 -*-
"""连真实壳(9333) — 极简诊断"""
import asyncio, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import websockets, urllib.request

async def main():
    tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9333/json").read())
    ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page" and "8899" in t.get("url", ""))
    async with websockets.connect(ws_url, max_size=10**7) as ws:
        expr = ("(async()=>{"
                "const m=document.getElementById('obsMap');"
                "const L=(typeof window.L!=='undefined');"
                "let v='?';try{const r=await fetch('/vendor/leaflet.js');v=r.status}catch(e){v='err:'+e.message}"
                "let t='?';try{const r=await fetch('/api/tile/10/857/416');const b=await r.blob();t=r.status+'/'+b.size+'B'}catch(e){t='err'}"
                "const sc=[...document.scripts].map(s=>s.src).filter(s=>s.includes('leaflet')||s.includes('vendor'));"
                "return 'L='+L+' | vendor='+v+' | tile='+t+' | 页面脚本='+sc+' | obsMap='+(m?m.offsetWidth+'x'+m.offsetHeight:'无')+' | initObsMap='+(typeof initObsMap);"
                "})()")
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
        while True:
            m = json.loads(await ws.recv())
            if m.get("id") == 1:
                r = m.get("result", {}).get("result", {})
                print("结果:", r.get("value") or m.get("result", {}).get("exceptionDetails", {}).get("text"))
                break
asyncio.run(main())
