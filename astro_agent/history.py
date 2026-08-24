# -*- coding: utf-8 -*-
"""
星枢 观测历史库 — SQLite 沉淀每晚拍摄记录
表 sessions: 每晚一条(日期/目标/张数/总曝光/HFR均值/天气快照/报告路径)
查询工具 history_query 供AI调用: "我M31拍了多久了?" "哪晚透明度最好?"
"""
import json, sqlite3, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB = ROOT / "data" / "history.db"


def _conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS sessions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            日期 TEXT, 目标 TEXT, 张数 INTEGER DEFAULT 0,
            总曝光秒 INTEGER DEFAULT 0, HFR均值 REAL,
            云量 REAL, 湿度 REAL, 温度 REAL,
            序列状态 TEXT, 备注 TEXT, 报告路径 TEXT,
            创建时间 TEXT DEFAULT (datetime('now','localtime')))""")


def upsert_session(日期, 目标, 张数=None, 总曝光秒=None, HFR均值=None,
                   云量=None, 湿度=None, 温度=None, 序列状态=None, 报告路径=None):
    """同日同目标只更新不重复插"""
    init()
    with _conn() as c:
        row = c.execute("SELECT id,张数,总曝光秒 FROM sessions WHERE 日期=? AND 目标=?",
                        (日期, 目标)).fetchone()
        if row:
            c.execute("""UPDATE sessions SET
                张数=COALESCE(?,张数), 总曝光秒=COALESCE(?,总曝光秒),
                HFR均值=COALESCE(?,HFR均值), 云量=COALESCE(?,云量),
                湿度=COALESCE(?,湿度), 温度=COALESCE(?,温度),
                序列状态=COALESCE(?,序列状态), 报告路径=COALESCE(?,报告路径)
                WHERE id=?""",
                (张数, 总曝光秒, HFR均值, 云量, 湿度, 温度, 序列状态, 报告路径, row["id"]))
            return row["id"]
        cur = c.execute("""INSERT INTO sessions
            (日期,目标,张数,总曝光秒,HFR均值,云量,湿度,温度,序列状态,报告路径)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (日期, 目标, 张数, 总曝光秒, HFR均值, 云量, 湿度, 温度, 序列状态, 报告路径))
        return cur.lastrowid


def query(mode="汇总", target=None, limit=20):
    """中文查询接口"""
    init()
    with _conn() as c:
        if mode == "按目标汇总" and target:
            rows = c.execute("""SELECT 目标, COUNT(DISTINCT 日期) AS 晚数,
                SUM(张数) AS 总张数, SUM(总曝光秒) AS 总秒,
                ROUND(AVG(HFR均值),2) AS 平均HFR
                FROM sessions WHERE 目标 LIKE ? GROUP BY 目标""",
                (f"%{target}%",)).fetchall()
            out = []
            for r in rows:
                h = (r["总秒"] or 0) / 3600
                out.append({"目标": r["目标"], "拍摄晚数": r["晚数"],
                            "累计张数": r["总张数"] or 0,
                            "累计小时": round(h, 1),
                            "平均HFR": r["平均HFR"],
                            "完成度参考": "已够一版" if h >= 6 else ("过半" if h >= 3 else "刚起步")})
            return {"查询": f"{target} 汇总", "结果": out}

        if mode == "最佳夜晚":
            rows = c.execute("""SELECT 日期, 目标, 云量, HFR均值, 张数, 总曝光秒
                FROM sessions WHERE 云量 IS NOT NULL
                ORDER BY 云量 ASC LIMIT ?""", (limit,)).fetchall()
            return {"查询": "透明度最好的夜晚", "结果": [
                {"日期": r["日期"], "目标": r["目标"], f"云量": r["云量"],
                 "HFR": r["HFR均值"], "张数": r["张数"]} for r in rows]}

        # 默认最近记录
        rows = c.execute("""SELECT * FROM sessions
            ORDER BY 日期 DESC LIMIT ?""", (limit,)).fetchall()
        return {"查询": "最近观测记录", "结果": [dict(r) for r in rows]}


def auto_capture_from_nina():
    """从NINA拉当前序列状态入库(供scheduler每30s调用)"""
    import httpx
    from utils.config import CFG
    base = f'http://{CFG.get("NINA_API_HOST","127.0.0.1")}:{CFG.get("NINA_API_PORT","1888")}/v2/api'
    try:
        seq = httpx.get(base + "/sequence/state", timeout=8).json().get("Response", {})
        wx = httpx.get(base + "/equipment/weather/info", timeout=8).json().get("Response", {})
        if not isinstance(seq, dict) or not seq.get("TargetName"):
            return None
        cnt = seq.get("ImageCount") or 0
        if not cnt:
            return None
        hfr = seq.get("HFR")
        upsert_session(
            日期=f"{datetime.now():%Y-%m-%d}", 目标=seq.get("TargetName"),
            张数=int(cnt) if isinstance(cnt, (int, float)) else 0,
            总曝光秒=int(cnt * seq["ExposureTime"]) if seq.get("ExposureTime") else None,
            HFR均值=float(hfr) if isinstance(hfr, (int, float)) else None,
            云量=wx.get("CloudCover") if isinstance(wx.get("CloudCover"), (int, float)) else None,
            湿度=wx.get("Humidity") if isinstance(wx.get("Humidity"), (int, float)) else None,
            温度=wx.get("Temperature") if isinstance(wx.get("Temperature"), (int, float)) else None,
            序列状态=str(seq.get("Status", ""))[:30])
        return f"已入库: {seq.get('TargetName')} {cnt}张"
    except Exception:
        return None


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    init()
    # 自测
    upsert_session("2026-08-22", "NGC7380巫师星云", 张数=48, 总曝光秒=14400,
                   HFR均值=2.1, 云量=35, 湿度=72, 温度=22)
    upsert_session("2026-08-22", "NGC7380巫师星云", 张数=60, 总曝光秒=18000)  # 更新不重复
    r = query("按目标汇总", "巫师")
    print(json.dumps(r, ensure_ascii=False, indent=1))
