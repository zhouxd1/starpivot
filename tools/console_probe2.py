# -*- coding: utf-8 -*-
import asyncio, json, sys, io, subprocess, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = 9224
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

async def main():
    proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}",
                             "--user-data-dir=" + os.environ['LOCALAPPDATA'] + r"\Temp\edgeprobe2",
                             "--no-first-run", "http://127.0.0.1:8899/"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(6)
    import websockets, urllib.request
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
    ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
    async with websockets.connect(ws_url, max_size=10**7) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": "typeof loadMonitor", "returnByValue": True}}))
        r = json.loads(await ws.recv())
        print("loadMonitor类型:", r["result"]["result"].get("value"))
        await ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate",
            "params": {"expression": "typeof fetch", "returnByValue": True}}))
        r = json.loads(await ws.recv())
        print("fetch类型:", r["result"]["result"].get("value"))
        await ws.send(json.dumps({"id": 3, "method": "Runtime.evaluate",
            "params": {"expression": "JSON.stringify(Object.keys(window).filter(k=>k.includes('onitor')))", "returnByValue": True}}))
        r = json.loads(await ws.recv())
        print("window monitor相关:", r["result"]["result"].get("value"))
        await ws.send(json.dumps({"id": 4, "method": "Runtime.evaluate",
            "params": {"expression": "document.getElementById('monMount') ? document.getElementById('monMount').innerHTML.slice(0,80) : 'NO-ELEM'", "returnByValue": True}}))
        r = json.loads(await ws.recv())
        print("monMount当前:", r["result"]["result"].get("value"))
    proc.kill()

asyncio.run(main())
