import asyncio, json, sys, io, subprocess, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = 9241
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
async def main():
    proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}",
        "--user-data-dir=" + os.environ['LOCALAPPDATA'] + r"\Temp\ep41",
        "--no-first-run", "--disable-sync", "--window-size=1280,820", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(5)
    import websockets, urllib.request
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
    ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
    async with websockets.connect(ws_url, max_size=10**7) as ws:
        await ws.send(json.dumps({"id": 0, "method": "Page.enable"}))
        await ws.send(json.dumps({"id": 99, "method": "Page.navigate", "params": {"url": "http://127.0.0.1:8899/"}}))
        await asyncio.sleep(8)
        expr = r'''(()=>{const L=document.querySelector('.col-l');if(!e)return 'no col-l';
const kids=[...L.children].map(e=>{const r=e.getBoundingClientRect();const cs=getComputedStyle(e);
return e.className.split(' ')[0]+':'+Math.round(r.width)+'x'+Math.round(r.height)+' flex='+cs.flex});
return 'col-l kids: '+kids.join(' | ')})()'''.replace("if(!e)","if(!L)")
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": expr, "returnByValue": True}}))
        t0 = time.time()
        while time.time() - t0 < 12:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=4))
            except asyncio.TimeoutError:
                continue
            if m.get("id") == 1:
                v = m["result"]["result"].get("value")
                print(v if v else str(m["result"])[:200])
                break
    proc.kill()
asyncio.run(main())
