import asyncio, json, sys, io, subprocess, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = 9234
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
async def main():
    proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}",
        "--user-data-dir=" + os.environ['LOCALAPPDATA'] + r"\Temp\ep12",
        "--no-first-run", "--disable-sync", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(5)
    import websockets, urllib.request
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
    ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
    async with websockets.connect(ws_url, max_size=10**7) as ws:
        await ws.send(json.dumps({"id": 0, "method": "Page.enable"}))
        await ws.send(json.dumps({"id": 99, "method": "Page.navigate", "params": {"url": "http://127.0.0.1:8899/"}}))
        await asyncio.sleep(7)
        for eid, expr in [
            (1, "(async()=>{try{await saveSettings();return 'save ✓'}catch(e){return 'save ✗:'+e.message}})()"),
            (2, "(async()=>{try{await makeReport({target:{textContent:'',disabled:false}});return 'report ✓'}catch(e){return 'report ✗:'+e.message}})()")]:
            await ws.send(json.dumps({"id": eid, "method": "Runtime.evaluate",
                "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
        got=set(); t0=time.time()
        while time.time()-t0<25 and len(got)<2:
            try:
                m=json.loads(await asyncio.wait_for(ws.recv(), timeout=6))
            except asyncio.TimeoutError: continue
            if m.get("id") in (1,2) and m["id"] not in got:
                got.add(m["id"])
                v=m.get("result",{}).get("result",{}).get("value","?")
                print(f"[{m['id']}] {v}")
    proc.kill()
asyncio.run(main())
