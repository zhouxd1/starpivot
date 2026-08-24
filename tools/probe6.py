import asyncio, json, sys, io, subprocess, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = 9228
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
EXPR = "(async()=>{const d=await fetch('/api/monitor').then(x=>x.json());" \
       "const s=d['\u5e8f\u5217'];" \
       "const m=d['\u8d64\u9053\u4eea'];const g=d['\u5bfc\u661f'];const c=d['\u76f8\u673a'];" \
       "const f=d['\u7535\u8c03'];const fw=d['\u6ee4\u8f6e'];const ro=d['\u65cb\u8f6c\u5668'];const w=d['\u5929\u6c14'];" \
       "try{ return 'ALL-OK' }catch(e){return 'E:'+e.message}})()"
async def main():
    proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}",
        "--user-data-dir=" + os.environ['LOCALAPPDATA'] + r"\Temp\ep6",
        "--no-first-run", "--disable-sync", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(5)
    import websockets, urllib.request
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
    ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
    async with websockets.connect(ws_url, max_size=10**7) as ws:
        await ws.send(json.dumps({"id": 0, "method": "Page.enable"}))
        await ws.send(json.dumps({"id": 99, "method": "Page.navigate", "params": {"url": "http://127.0.0.1:8899/"}}))
        await asyncio.sleep(6)
        # 复刻loadMonitor完整模板串(带中文属性), 看哪步炸
        expr = "(async()=>{try{const d=await fetch('/api/monitor').then(x=>x.json());"
        expr += "const s=d['\u5e8f\u5217'];"
        # 序列模板
        expr += "const h1 = s.\u72b6\u6001!=='\u7a7a\u95f2' ? `<b>${s.\u76ee\u6807||''}</b><span>${s.\u5df2\u62cd||0}</span>` : 'IDLE';";
        expr += "return 'T1-OK:'+h1.slice(0,40);"
        expr += "}catch(e){return 'T1-ERR:'+e.message}})()"
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                  "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
        t0 = time.time(); got = False
        while time.time() - t0 < 12 and not got:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            except asyncio.TimeoutError:
                continue
            if m.get("id") == 1:
                got = True
                print("[T1]", str(m["result"]["result"].get("value"))[:150])
    proc.kill()
asyncio.run(main())
