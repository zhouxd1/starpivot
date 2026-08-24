# -*- coding: utf-8 -*-
"""CDP抓页面console报错"""
import asyncio, json, sys, io, subprocess, time, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = 9223
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

async def main():
    proc = subprocess.Popen([EDGE, f"--headless=new", f"--remote-debugging-port={PORT}",
                             "--user-data-dir=" + os.environ['LOCALAPPDATA'] + r"\Temp\edgeprobe",
                             "--no-first-run", "http://127.0.0.1:8899/"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(6)
    import websockets
    import urllib.request
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
    ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
    async with websockets.connect(ws_url, max_size=10**7) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
        await ws.send(json.dumps({"id": 2, "method": "Log.enable"}))
        t0 = time.time()
        while time.time() - t0 < 8:
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            except asyncio.TimeoutError:
                break
            if msg.get("method") in ("Runtime.consoleAPICalled", "Runtime.exceptionThrown"):
                if msg["method"] == "Runtime.exceptionThrown":
                    d = msg["params"]["exceptionDetails"]
                    print("EXC:", d.get("text"), "-", (d.get("exception") or {}).get("description", "")[:200])
                else:
                    a = msg["params"]
                    if a.get("type") in ("error", "warning"):
                        vals = " ".join(str(v.get("value", "")) for v in a.get("args", []))
                        print(a["type"].upper() + ":", vals[:200])
    proc.kill()

asyncio.run(main())
