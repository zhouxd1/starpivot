import asyncio, json, sys, io, subprocess, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = 9230
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
async def main():
    proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}",
        "--user-data-dir=" + os.environ['LOCALAPPDATA'] + r"\Temp\ep8",
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
            (1, "document.getElementById('monMount')?document.getElementById('monMount').innerText.slice(0,60):'NO'"),
            (2, "document.getElementById('monWx')?document.getElementById('monWx').innerText.slice(0,60):'NO'"),
            (3, "document.getElementById('monCam')?document.getElementById('monCam').innerText.slice(0,50):'NO'"),
            (4, "document.getElementById('topTime')?document.getElementById('topTime').textContent:'NO'")]:
            await ws.send(json.dumps({"id": eid, "method": "Runtime.evaluate",
                                      "params": {"expression": expr, "returnByValue": True}}))
        got = set(); t0 = time.time()
        while time.time() - t0 < 12 and len(got) < 4:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=4))
            except asyncio.TimeoutError:
                continue
            if m.get("id") in (1, 2, 3, 4):
                got.add(m["id"])
                print(f"[{m['id']}]", str(m["result"]["result"].get("value"))[:90])
    proc.kill()
asyncio.run(main())
