# -*- coding: utf-8 -*-
"""诊断col-l渲染: CDP查三个col的computed样式"""
import asyncio, json, sys, io, subprocess, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = 9239
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
async def main():
    proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}",
        "--user-data-dir=" + os.environ['LOCALAPPDATA'] + r"\Temp\ep39",
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
        expr = r'''(()=>{const s=(c)=>{const e=document.querySelector('.col-'+c);if(!e)return c+': NOT-FOUND';const cs=getComputedStyle(e);const r=e.getBoundingClientRect();return c+': display='+cs.display+' gridCol='+cs.gridColumn+' w='+Math.round(r.width)+' h='+Math.round(r.height)};const g=document.querySelector('.main');const gs=g?getComputedStyle(g):null;return [s('l'),s('m'),s('r'),'main-cols='+(gs?gs.gridTemplateColumns:'?'),'body-w='+document.body.clientWidth].join(' | ')})()'''
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
