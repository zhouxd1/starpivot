import asyncio, json, sys, io, subprocess, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = 9229
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
async def main():
    proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}",
        "--user-data-dir=" + os.environ['LOCALAPPDATA'] + r"\Temp\ep7",
        "--no-first-run", "--disable-sync", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(5)
    import websockets, urllib.request
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
    ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
    async with websockets.connect(ws_url, max_size=10**7) as ws:
        # 先挂exception监听再导航!
        await ws.send(json.dumps({"id": 0, "method": "Runtime.enable"}))
        await ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
        excs = []
        async def drain(t=8):
            t0=time.time()
            while time.time()-t0 < t:
                try:
                    m = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
                except asyncio.TimeoutError:
                    continue
                if m.get("method") == "Runtime.exceptionThrown":
                    d = m["params"]["exceptionDetails"]
                    excs.append(d.get("text","") + " | " + str((d.get("exception") or {}).get("description",""))[:220]
                                + " | line:" + str(d.get("lineNumber")))
                elif m.get("method") == "Runtime.consoleAPICalled" and m["params"]["type"] in ("error","warning"):
                    excs.append("console."+m["params"]["type"]+": " + " ".join(str(v.get("value",""))[:120] for v in m["params"].get("args",[])))
        await ws.send(json.dumps({"id": 99, "method": "Page.navigate", "params": {"url": "http://127.0.0.1:8899/"}}))
        await drain(9)
        print(f"捕获{len(excs)}条:")
        for e in excs[:8]: print(" ", e[:230])
    proc.kill()
asyncio.run(main())
