import asyncio, json, sys, io, subprocess, time, os, base64
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = 9257
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
async def main():
    proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}",
        "--user-data-dir=" + os.environ['LOCALAPPDATA'] + r"\Temp\ep57",
        "--no-first-run", "--disable-sync", "--window-size=1280,820", f"http://127.0.0.1:8899/?t={int(time.time())}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(7)
    import websockets, urllib.request
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
    ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
    async with websockets.connect(ws_url, max_size=10**7) as ws:
        await ws.send(json.dumps({"id": 0, "method": "Page.enable"}))
        expr = '''(async()=>{
          document.getElementById("setPanel").style.display="block";
          const s=document.createElement("script");
          s.src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js";
          document.head.appendChild(s);
          await new Promise(r=>{s.onload=r; setTimeout(r,9000)});
          if(typeof L==="undefined") return "Leaflet失败";
          const link=document.createElement("link"); link.rel="stylesheet"; link.href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css"; document.head.appendChild(link);
          // photon后端搜崇明岛
          const g=await(await fetch("/api/geocode?q="+encodeURIComponent("崇明岛"))).json();
          if(!g.ok) return "geocode失败";
          const m=L.map("obsMap",{attributionControl:false}).setView([g.lat,g.lon],10);
          L.tileLayer("https://webrd0{1,2,3}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}",{maxZoom:18,subdomains:["1","2","3"]}).addTo(m);
          L.marker([g.lat,g.lon]).addTo(m).bindPopup("📍 "+g.name);
          document.getElementById("obsSearch").value="崇明岛";
          document.getElementById("obsLabel").textContent="📍 "+g.lat.toFixed(4)+", "+g.lon.toFixed(4)+" ("+g.name+") — 已设为观测位置";
          await new Promise(r=>setTimeout(r,10000));
          document.getElementById("obsMap").scrollIntoView({block:"center"});
          await new Promise(r=>setTimeout(r,1500));
          return "OK 崇明岛:"+g.lat.toFixed(3)+","+g.lon.toFixed(3);
        })()'''
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
        t0 = time.time(); res = None
        while time.time() - t0 < 40:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            except asyncio.TimeoutError:
                continue
            if m.get("id") == 1:
                res = m["result"]["result"].get("value")
                break
        print("结果:", res)
        if res and str(res).startswith("OK"):
            await ws.send(json.dumps({"id": 2, "method": "Page.captureScreenshot", "params": {"format": "png"}}))
            t0 = time.time()
            while time.time() - t0 < 10:
                try:
                    m = json.loads(await asyncio.wait_for(ws.recv(), timeout=4))
                except asyncio.TimeoutError:
                    continue
                if m.get("id") == 2:
                    open(r'C:\Users\love_\starpivot\reports\map_final.png', 'wb').write(base64.b64decode(m["result"]["data"]))
                    print("最终截图saved")
                    break
    proc.kill()
asyncio.run(main())
