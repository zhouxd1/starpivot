import asyncio, json, sys, io, subprocess, time, os, base64
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = 9249
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
async def main():
    proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}",
        "--user-data-dir=" + os.environ['LOCALAPPDATA'] + r"\Temp\ep49",
        "--no-first-run", "--disable-sync", "--window-size=1280,820", "http://127.0.0.1:8899/"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(8)
    import websockets, urllib.request
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
    ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
    async with websockets.connect(ws_url, max_size=10**7) as ws:
        await ws.send(json.dumps({"id": 0, "method": "Page.enable"}))
        # 显示面板+手动注入leaflet+创建地图
        expr = '''(async()=>{
          document.getElementById("setPanel").style.display="block";
          const s=document.createElement("script");
          s.src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
          document.head.appendChild(s);
          await new Promise(r=>{s.onload=r; setTimeout(r,10000)});
          if(typeof L==="undefined") return "Leaflet加载失败";
          const link=document.createElement("link"); link.rel="stylesheet"; link.href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"; document.head.appendChild(link);
          const m=L.map("obsMap",{attributionControl:false}).setView([40,116.4],7);
          L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:17}).addTo(m);
          L.marker([40,116.4]).addTo(m);
          await new Promise(r=>setTimeout(r,4000));
          document.getElementById("obsMap").scrollIntoView({block:"center"}); await new Promise(r=>setTimeout(r,1500)); return "map已建:"+document.getElementById("obsMap").offsetHeight+"px";
        })()'''
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
        t0 = time.time(); res = None
        while time.time() - t0 < 30:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            except asyncio.TimeoutError:
                continue
            if m.get("id") == 1:
                res = m["result"]["result"].get("value")
                break
        print("结果:", res)
        if res and "map已建" in str(res):
            await ws.send(json.dumps({"id": 2, "method": "Page.captureScreenshot", "params": {"format": "png"}}))
            t0 = time.time()
            while time.time() - t0 < 10:
                try:
                    m = json.loads(await asyncio.wait_for(ws.recv(), timeout=4))
                except asyncio.TimeoutError:
                    continue
                if m.get("id") == 2:
                    open(r'C:\Users\love_\starpivot\reports\obsmap_final.png', 'wb').write(base64.b64decode(m["result"]["data"]))
                    print("截图saved")
                    break
    proc.kill()
asyncio.run(main())
