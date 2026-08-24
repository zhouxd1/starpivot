import asyncio, json, sys, io, subprocess, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = 9232
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
async def main():
    proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}",
        "--user-data-dir=" + os.environ['LOCALAPPDATA'] + r"\Temp\epa",
        "--no-first-run", "--disable-sync", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(5)
    import websockets, urllib.request
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
    ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
    async with websockets.connect(ws_url, max_size=10**7) as ws:
        await ws.send(json.dumps({"id": 0, "method": "Page.enable"}))
        await ws.send(json.dumps({"id": 99, "method": "Page.navigate", "params": {"url": "http://127.0.0.1:8899/"}}))
        await asyncio.sleep(6)
        expr = ("(async()=>{const d=await fetch('/api/monitor').then(x=>x.json());"
                "const s=d['\u5e8f\u5217'];"
                "const el=document.getElementById('monSeq');"
                "if(!el) return 'NO-ELEM monSeq';"
                "el.innerHTML='<b>'+s+'\u5df2\u62ed\u6253</b>';"
                "return 'WROTE:'+el.innerText.slice(0,40)})()")
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                  "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
        t0 = time.time()
        while time.time() - t0 < 10:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            except asyncio.TimeoutError:
                continue
            if m.get("id") == 1:
                r = m.get("result", {})
                if "exceptionDetails" in r:
                    ed = r["exceptionDetails"]
                    print("[直写异常]", ed.get("text"), str((ed.get("exception") or {}).get("description",""))[:220])
                else:
                    print("[直写monSeq]", str(r.get("result", {}).get("value"))[:100])
                break
        # 页面自己8秒周期的loadMonitor是否终于跑起来了(等一轮)
        await asyncio.sleep(9)
        await ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate",
            "params": {"expression": "document.getElementById('monMount').innerText.slice(0,50)", "returnByValue": True}}))
        t0 = time.time()
        while time.time() - t0 < 8:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            except asyncio.TimeoutError:
                continue
            if m.get("id") == 2:
                print("[9秒后monMount]", str(m["result"]["result"].get("value"))[:80])
                break
    proc.kill()
asyncio.run(main())
