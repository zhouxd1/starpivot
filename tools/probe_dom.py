import asyncio, json, sys, io, subprocess, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = 9251
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
async def main():
    proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}",
        "--user-data-dir=" + os.environ['LOCALAPPDATA'] + r"\Temp\ep51",
        "--no-first-run", "--disable-sync", "--window-size=1280,820", "http://127.0.0.1:8899/"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(7)
    import websockets, urllib.request
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
    ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
    async with websockets.connect(ws_url, max_size=10**7) as ws:
        await ws.send(json.dumps({"id": 0, "method": "Page.enable"}))
        expr = '''(()=>{
          const m=document.getElementById("obsMap");
          if(!m) return "obsMap不存在!";
          const r=m.getBoundingClientRect();
          const p=m.parentElement;
          return `位置: top=${Math.round(r.top)} left=${Math.round(r.left)} w=${Math.round(r.width)} h=${Math.round(r.height)} | 父容器class=${p.className||p.tagName} | 在setPanel内=${!!m.closest("#setPanel")}`;
        })()'''
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": expr, "returnByValue": True}}))
        t0 = time.time()
        while time.time() - t0 < 12:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=4))
            except asyncio.TimeoutError:
                continue
            if m.get("id") == 1:
                print(m["result"]["result"].get("value"))
                break
    proc.kill()
asyncio.run(main())
