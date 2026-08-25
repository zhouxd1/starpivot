# -*- coding: utf-8 -*-
"""连真实壳(9333调试口)诊断地图问题"""
import asyncio, json, sys, io, base64
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import websockets, urllib.request

async def main():
    tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9333/json").read())
    ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page" and "8899" in t.get("url", ""))
    async with websockets.connect(ws_url, max_size=10**7) as ws:
        # 开设置面板并初始化
        expr = "(async()=>{" + "const m=document.getElementById('obsMap');" + "const L=typeof window.L!=='undefined';" + "let v='?';try{const r=await fetch('/vendor/leaflet.js');v=r.status}catch(e){v='err'}" + "let t='?';try{const r=await fetch('/api/tile/10/857/416');const b=await r.blob();t=r.status+'/'+b.size+'B'}catch(e){t='err'}" + "const scripts=[...document.scripts].map(s=>s.src).filter(s=>s.includes('leaflet')||s.includes('vendor'));" + "return 'L='+L+' vendor='+v+' tile='+t+' scripts='+scripts+' obsMap='+(m?m.offsetWidth+'x'+m.offsetHeight:'无')+' html有initObsMap='+(typeof initObsMap);" + "})()"
await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
        import time
        t0 = time.time()
        while time.time() - t0 < 25:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            except asyncio.TimeoutError:
                continue
            print("MSG:", str(m)[:400])
            if m.get("id") == 1:
                raw = m["result"]["result"].get("value", "{}");  d = raw
                for k, v in d.items():
                    print(f"{k}: {str(v)[:100]}")
                break
asyncio.run(main())
