import asyncio, json, sys, io, subprocess, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = 9259
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
async def main():
    proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}",
        "--user-data-dir=" + os.environ['LOCALAPPDATA'] + r"\Temp\ep59",
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
          await new Promise(r=>setTimeout(r,300));
          const m=document.getElementById("obsMap");
          m.scrollIntoView({block:"center"});
          await new Promise(r=>setTimeout(r,500));
          const r2=m.getBoundingClientRect();
          // 找可滚动的祖先
          let sc=null, el=m.parentElement;
          while(el && el!==document.body){
            const st=getComputedStyle(el);
            if((st.overflowY==="auto"||st.overflowY==="scroll")&&el.scrollHeight>el.clientHeight){sc=el.tagName+"."+el.className;break}
            el=el.parentElement;
          }
          return `obsMap: top=${Math.round(r2.top)} h=${Math.round(r2.height)} w=${Math.round(r2.width)} | 滚动祖先=${sc} | setPanel可见=${document.getElementById("setPanel").offsetHeight}`;
        })()'''
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
            "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
        t0 = time.time()
        while time.time() - t0 < 15:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=4))
            except asyncio.TimeoutError:
                continue
            if m.get("id") == 1:
                print(m["result"]["result"].get("value"))
                break
    proc.kill()
asyncio.run(main())
