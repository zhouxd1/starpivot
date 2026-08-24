import asyncio, json, sys, io, subprocess, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = 9225
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
async def main():
    proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}",
        "--user-data-dir=" + os.environ['LOCALAPPDATA'] + r"\Temp\edgeprobe3",
        "--no-first-run", "--no-default-browser-check", "--disable-sync", "--disable-features=msEdgeSync", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(7)
    import websockets, urllib.request
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
    ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
    # 先连上再导航
    _pre = True
    async with websockets.connect(ws_url, max_size=10**7) as ws:
        # 收集console
        console = []
        async def pump(t=4):
            t0 = time.time()
            while time.time() - t0 < t:
                try:
                    m = json.loads(await asyncio.wait_for(ws.recv(), timeout=1))
                    if m.get("method") == "Runtime.consoleAPICalled":
                        args = " ".join(str(v.get("value", v.get("description", "")))[:150] for v in m["params"].get("args", []))
                        console.append(f'{m["params"]["type"]}: {args}')
                    elif m.get("method") == "Runtime.exceptionThrown":
                        d = m["params"]["exceptionDetails"]
                        console.append('EXC: ' + d.get("text", "") + " " + str((d.get("exception") or {}).get("description", ""))[:250])
                except asyncio.TimeoutError:
                    pass
        await ws.send(json.dumps({"id": 0, "method": "Page.enable"}))
        await ws.send(json.dumps({"id": 99, "method": "Page.navigate", "params": {"url": "http://127.0.0.1:8899/"}}))
        await asyncio.sleep(6)
        await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
        await pump(3)
        await ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {
            "expression": "document.title + ' | body前120字: ' + document.body.innerText.slice(0,120)", "returnByValue": True}}))
        while True:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=4))
            if "result" in m and m.get("id") == 2:
                print("页面:", m["result"]["result"].get("value", "")[:250])
                break
        print("--- console捕获 ---")
        for c in console[:10]:
            print(c[:220])
    proc.kill()
asyncio.run(main())
