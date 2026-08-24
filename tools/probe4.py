import asyncio, json, sys, io, subprocess, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
PORT = 9226
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
async def main():
    proc = subprocess.Popen([EDGE, "--headless=new", f"--remote-debugging-port={PORT}",
        "--user-data-dir=" + os.environ['LOCALAPPDATA'] + r"\Temp\ep4",
        "--no-first-run", "--disable-sync", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(5)
    import websockets, urllib.request
    tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
    ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page")
    async with websockets.connect(ws_url, max_size=10**7) as ws:
        await ws.send(json.dumps({"id": 0, "method": "Page.enable"}))
        await ws.send(json.dumps({"id": 99, "method": "Page.navigate", "params": {"url": "http://127.0.0.1:8899/"}}))
        await asyncio.sleep(6)
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
            "expression": "typeof loadMonitor + '|' + typeof monMount", "returnByValue": True}}))
        while True:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if m.get("id") == 1:
                print("类型:", m["result"]["result"].get("value"))
                break
        # 手动执行并抓异常
        await ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {
            "expression": "(async()=>{try{const r=await fetch(String.fromCharCode(47)+String.fromCharCode(97)+String.fromCharCode(112)+String.fromCharCode(105)+String.fromCharCode(47)+String.fromCharCode(109)+String.fromCharCode(111)+String.fromCharCode(110)+String.fromCharCode(105)+String.fromCharCode(116)+String.fromCharCode(111)+String.fromCharCode(114)+String.fromCharCode(41)).then(x=>x.json());const d=window.__m=r;const m=d[String.fromCharCode(36132)+String.fromCharCode(36947)+String.fromCharCode(20202)];return String.fromCharCode(25441)+JSON.stringify(Object.keys(d))}catch(e){return String.fromCharCode(69)+String.fromCharCode(82)+String.fromCharCode(82)+String.fromCharCode(58)+e.message}})()",; return 'DONE: '+document.getElementById('monMount').innerHTML.slice(0,90)}catch(e){return 'ERR: '+e.message+' @'+(e.stack.split(String.fromCharCode(10))[1]||'')}})()",
            "awaitPromise": True, "returnByValue": True}}))
        while True:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if m.get("id") == 2:
                print("手动执行:", str(m["result"]["result"].get("value"))[:200])
                break
    proc.kill()
asyncio.run(main())
