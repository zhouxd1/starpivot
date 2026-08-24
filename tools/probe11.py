# 连星枢壳窗口? 壳没开调试口。间接验证: 壳加载8899, 同URL在edge渲染是否2位小数
import asyncio, json, sys, io, subprocess, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = 9233
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
async def main():
    proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}",
        "--user-data-dir=" + os.environ['LOCALAPPDATA'] + r"\Temp\ep11",
        "--no-first-run", "--disable-sync", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(5)
    import websockets, urllib.request
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
    ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
    async with websockets.connect(ws_url, max_size=10**7) as ws:
        await ws.send(json.dumps({"id": 0, "method": "Page.enable"}))
        await ws.send(json.dumps({"id": 99, "method": "Page.navigate", "params": {"url": "http://127.0.0.1:8899/"}}))
        await asyncio.sleep(7)
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": "document.getElementById('monWx')?document.getElementById('monWx').innerText.replace(/\n/g,'|').slice(0,100):'NO'", "returnByValue": True}}))
        t0 = time.time()
        while time.time() - t0 < 10:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            except asyncio.TimeoutError:
                continue
            if m.get("id") == 1:
                print("[monWx]", str(m["result"]["result"].get("value"))[:120])
                break
    proc.kill()
asyncio.run(main())
