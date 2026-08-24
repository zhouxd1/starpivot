import asyncio, json, sys, io, subprocess, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = 9227
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

EXPR = "(async()=>{try{const d=await fetch('/api/monitor').then(x=>x.json());"
EXPR += "return 'KEYS:'+JSON.stringify(Object.keys(d));"
EXPR += "}catch(e){return 'ERR:'+e.message}})()"

EXPR2 = "(async()=>{try{"
EXPR2 += "const d=await fetch('/api/monitor').then(x=>x.json());"
EXPR2 += "const m=d['\u8d64\u9053\u4eea'];"
EXPR2 += "document.getElementById('monMount').innerHTML='<b>RA '+m['\u8d64\u7ecf']+'</b>';"
EXPR2 += "return 'INJ-OK:'+document.getElementById('monMount').innerHTML.slice(0,60);"
EXPR2 += "}catch(e){return 'ERR2:'+e.message}})()"


async def main():
    proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}",
        "--user-data-dir=" + os.environ['LOCALAPPDATA'] + r"\Temp\ep5",
        "--no-first-run", "--disable-sync", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(5)
    import websockets, urllib.request
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
    ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
    async with websockets.connect(ws_url, max_size=10**7) as ws:
        await ws.send(json.dumps({"id": 0, "method": "Page.enable"}))
        await ws.send(json.dumps({"id": 99, "method": "Page.navigate", "params": {"url": "http://127.0.0.1:8899/"}}))
        await asyncio.sleep(6)
        # 1: 页面fetch是否通
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                  "params": {"expression": EXPR, "awaitPromise": True, "returnByValue": True}}))
        # 2: 直接注入渲染
        await ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate",
                                  "params": {"expression": EXPR2, "awaitPromise": True, "returnByValue": True}}))
        seen = set()
        t0 = time.time()
        while time.time() - t0 < 15 and len(seen) < 2:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            except asyncio.TimeoutError:
                continue
            if m.get("id") in (1, 2) and m["id"] not in seen:
                seen.add(m["id"])
                v = m["result"]["result"].get("value", str(m["result"])[:150])
                print(f"[{m['id']}]", str(v)[:200])
    proc.kill()

asyncio.run(main())
