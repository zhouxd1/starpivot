import asyncio, json, sys, io, subprocess, time, os, base64
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = 9253
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
async def main():
    proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}",
        "--user-data-dir=" + os.environ['LOCALAPPDATA'] + r"\Temp\ep53",
        "--no-first-run", "--disable-sync", "--window-size=1280,820", "http://127.0.0.1:8899/?t=1787630713"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(7)
    import websockets, urllib.request
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
    ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
    async with websockets.connect(ws_url, max_size=10**7) as ws:
        await ws.send(json.dumps({"id": 0, "method": "Page.enable"}))
        # 真实点击setBtn(页面内click, 走onclick handler)
        expr = '''(async()=>{
          document.getElementById("setBtn").click();
          await new Promise(r=>setTimeout(r,800));
          const panel=document.getElementById("setPanel");
          const disp=panel.style.display;
          if(disp!=="block") return "点击后面板="+disp+" ✗";
          await new Promise(r=>setTimeout(r,6000));
          const m=document.getElementById("obsMap");
          const r2=m.getBoundingClientRect();
          if(r2.height<50) return "面板开了但地图没初始化(h="+r2.height+") — observer或CDN问题";
          m.scrollIntoView({block:"center"});
          await new Promise(r=>setTimeout(r,2000));
          
          // 搜索崇明岛(不等待,触发即可)
          document.getElementById("obsSearch").value="崇明岛";
          obsGeocode();

        })()'''
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
        t0 = time.time(); res = None
        while time.time() - t0 < 35:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            except asyncio.TimeoutError:
                continue
            if m.get("id") == 1:
                res = m["result"]["result"].get("value")
                break
        print("点击结果:", res)
        if res and res.startswith("OK"):
            await ws.send(json.dumps({"id": 2, "method": "Page.captureScreenshot", "params": {"format": "png"}}))
            t0 = time.time()
            while time.time() - t0 < 10:
                try:
                    m = json.loads(await asyncio.wait_for(ws.recv(), timeout=4))
                except asyncio.TimeoutError:
                    continue
                if m.get("id") == 2:
                    open(r'C:\Users\love_\starpivot\reports\obsmap_click.png', 'wb').write(base64.b64decode(m["result"]["data"]))
                    print("截图saved")
                    break
    proc.kill()
asyncio.run(main())
