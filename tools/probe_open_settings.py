import asyncio, json, sys, io, subprocess, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = 9247
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
async def main():
    proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}",
        "--user-data-dir=" + os.environ['LOCALAPPDATA'] + r"\Temp\ep47",
        "--no-first-run", "--disable-sync", "--window-size=1280,820", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(5)
    import websockets, urllib.request
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
    ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
    async with websockets.connect(ws_url, max_size=10**7) as ws:
        await ws.send(json.dumps({"id": 0, "method": "Page.enable"}))
        await ws.send(json.dumps({"id": 99, "method": "Page.navigate", "params": {"url": "http://127.0.0.1:8899/"}}))
        await asyncio.sleep(7)
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": "openSettings(); 'opened'", "returnByValue": True}}))
        await asyncio.sleep(14)  # 等Leaflet CDN
        await ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate",
            "params": {"expression": "typeof initObsMap+'|'+(document.getElementById('obsMap')?document.getElementById('obsMap').offsetHeight:-1)+'|'+(typeof L)", "returnByValue": True}}))
        await ws.send(json.dumps({"id": 3, "method": "Page.captureScreenshot", "params": {"format": "png"}}))
        t0 = time.time(); shot = None
        while time.time() - t0 < 12:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=4))
            except asyncio.TimeoutError:
                continue
            if m.get("id") == 3:
                shot = m["result"]["data"]
                break
            if m.get("id") == 2:
                print('obsMap高度:', m["result"]["result"].get("value"))
        if shot:
            import base64
            open(r'C:\Users\love_\starpivot\reports\obsmap.png', 'wb').write(base64.b64decode(shot))
            print('截图saved: reports/obsmap.png')
    proc.kill()
asyncio.run(main())
