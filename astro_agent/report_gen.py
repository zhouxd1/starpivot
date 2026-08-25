# -*- coding: utf-8 -*-
"""观测报告生成: 汇总历史库+星表+天气 → HTML报告(可Edge转PDF)"""
import sys, io, json, sqlite3, datetime as dt
from pathlib import Path

ROOT = Path(__file__).parent.parent
REP_DIR = ROOT / "reports"
REP_DIR.mkdir(exist_ok=True)

def _h(msgs):
    """会话消息转html(供报告嵌入最近对话摘要)"""
    return "<br>".join(str(m)[:200] for m in (msgs or [])[-6:])

def build_report(target: str = "") -> dict:
    """生成观测报告HTML; target空=总览, 有=单目标战报"""
    import glob
    db = ROOT / "data" / "history.db"
    rows = []
    if db.exists():
        conn = sqlite3.connect(str(db))
        try:
            if target:
                rows = conn.execute(
                    "SELECT 日期,目标,张数,总曝光秒,HFR均值 FROM sessions WHERE 目标 LIKE ? ORDER BY 日期 DESC LIMIT 30",
                    (f"%{target}%",)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT 日期,目标,张数,总曝光秒,HFR均值 FROM sessions ORDER BY 日期 DESC LIMIT 30").fetchall()
        finally:
            conn.close()
    # 汇总统计
    total_h = sum((r[3] or 0) for r in rows) / 3600
    n_nights = len({r[0] for r in rows})
    n_frames = sum((r[2] or 0) for r in rows)
    hfrs = [r[4] for r in rows if r[4]]
    avg_hfr = sum(hfrs) / len(hfrs) if hfrs else 0
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    title = f"🌌 {target} 战报" if target else "🌌 星枢·观测总报告"
    trs = "".join(
        f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2] or 0}</td>"
        f"<td>{(r[3] or 0)/3600:.1f}h</td><td>{r[4] or '-'}</td></tr>" for r in rows)
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{title}</title>
<style>
body{{font-family:'Microsoft YaHei';background:#0b1220;color:#e8f0ff;padding:36px 44px;margin:0}}
h1{{font-size:26px;color:#5eead4;margin:0 0 4px}}
.meta{{color:#7d93b8;font-size:13px;margin-bottom:22px}}
.stats{{display:flex;gap:14px;margin-bottom:24px}}
.st{{flex:1;background:#132039;border:1px solid #29406b;border-radius:14px;padding:16px;text-align:center}}
.st b{{display:block;font-size:26px;color:#93c5fd;margin-top:4px}}
.st span{{font-size:12px;color:#7d93b8}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#182a4d;padding:10px;text-align:left;color:#93c5fd}}
td{{padding:9px 10px;border-bottom:1px solid #1d2f52}}
tr:nth-child(even) td{{background:rgba(24,42,77,.35)}}
.foot{{margin-top:22px;color:#54688a;font-size:11.5px;text-align:center}}
</style></head><body>
<h1>{title}</h1>
<div class="meta">星枢 StarPivot 生成 · {now}</div>
<div class="stats">
<div class="st"><span>累计夜数</span><b>{n_nights}</b></div>
<div class="st"><span>累计张数</span><b>{n_frames}</b></div>
<div class="st"><span>累计曝光</span><b>{total_h:.1f}h</b></div>
<div class="st"><span>平均HFR</span><b>{avg_hfr:.2f}</b></div>
</div>
<table><tr><th>日期</th><th>目标</th><th>张数</th><th>总曝光</th><th>HFR</th></tr>{trs}</table>
<div class="foot">StarPivot · 数据来自本机拍摄历史库 · 可直接打印为PDF(Ctrl+P)</div>
</body></html>"""
    name = f"obs_report_{target or 'all'}_{dt.datetime.now():%Y%m%d_%H%M}.html".replace(" ", "_")
    p = REP_DIR / name
    p.write_text(html, encoding="utf-8")
    return {"报告": str(p), "夜数": n_nights, "张数": n_frames,
            "总曝光小时": round(total_h, 1), "平均HFR": round(avg_hfr, 2),
            "提示": "HTML已生成,浏览器打开可Ctrl+P存PDF; 或直接发这个文件给星友"}

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print(build_report(sys.argv[1] if len(sys.argv) > 1 else ""))
