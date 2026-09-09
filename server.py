# -*- coding: utf-8 -*-
"""
KiloCode Token Dashboard · Local Data Service
Reads token usage data from kilo.db and serves it to the frontend.
"""
import json
import os
import sqlite3
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8766
DB_PATH = r"C:\Users\CatJiang\.local\share\kilo\kilo.db"
HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")


def get_db():
    # Read-only + timeout avoids "database is locked" when KiloCode writes concurrently
    uri = "file:" + DB_PATH.replace("\\", "/") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def parse_time_filter(query):
    """Parse time filter from query parameters."""
    mode = "all"
    days = None
    start_ts = None
    end_ts = None
    
    # Check for direct date range parameters first
    if "start=" in query and "end=" in query:
        start_str = query.split("start=")[1].split("&")[0]
        end_str = query.split("end=")[1].split("&")[0]
        try:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d")
            end_dt = datetime.strptime(end_str, "%Y-%m-%d")
            end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            start_ts = int(start_dt.timestamp() * 1000)
            end_ts = int(end_dt.timestamp() * 1000)
            mode = "custom"
        except:
            mode = "all"
    elif "mode=" in query:
        mode = query.split("mode=")[1].split("&")[0]
        
        if mode == "custom":
            if "start=" in query and "end=" in query:
                start_str = query.split("start=")[1].split("&")[0]
                end_str = query.split("end=")[1].split("&")[0]
                try:
                    start_dt = datetime.strptime(start_str, "%Y-%m-%d")
                    end_dt = datetime.strptime(end_str, "%Y-%m-%d")
                    end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                    start_ts = int(start_dt.timestamp() * 1000)
                    end_ts = int(end_dt.timestamp() * 1000)
                except:
                    mode = "all"
        elif mode == "today":
            start_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            start_ts = int(start_dt.timestamp() * 1000)
            end_ts = int(end_dt.timestamp() * 1000)
        elif mode == "yesterday":
            yesterday = datetime.now() - timedelta(days=1)
            start_dt = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
            start_ts = int(start_dt.timestamp() * 1000)
            end_ts = int(end_dt.timestamp() * 1000)
        elif mode == "24h":
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(hours=24)
            start_ts = int(start_dt.timestamp() * 1000)
            end_ts = int(end_dt.timestamp() * 1000)
        elif mode in ("7d", "14d", "30d"):
            days_map = {"7d": 7, "14d": 14, "30d": 30}
            days = days_map[mode]
        elif mode == "month":
            now = datetime.now()
            start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_dt = (start_dt + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
            start_ts = int(start_dt.timestamp() * 1000)
            end_ts = int(end_dt.timestamp() * 1000)
        elif mode == "lastMonth":
            now = datetime.now()
            first_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_month_end = first_this_month - timedelta(seconds=1)
            last_month_start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            start_ts = int(last_month_start.timestamp() * 1000)
            end_ts = int(last_month_end.timestamp() * 1000)
    
    return mode, days, start_ts, end_ts


def build_where_clause(mode, days, start_ts, end_ts):
    """Build WHERE clause and params for time filtering."""
    base = "data LIKE '%tokens%' AND json_extract(data, '$.tokens.total') IS NOT NULL"
    
    if mode == "all":
        return base, []
    elif mode in ("today", "yesterday", "24h", "month", "lastMonth", "custom"):
        return f"{base} AND time_created >= ? AND time_created <= ?", [start_ts, end_ts]
    elif mode in ("7d", "14d", "30d"):
        days_map = {"7d": 7, "14d": 14, "30d": 30}
        return f"{base} AND time_created > ?", [int((datetime.now() - timedelta(days=days_map[mode])).timestamp() * 1000)]
    return base, []


def get_summary(query):
    conn = get_db()
    try:
        mode, days, start_ts, end_ts = parse_time_filter(query)
        where, params = build_where_clause(mode, days, start_ts, end_ts)
        
        cur = conn.execute(f"""
            SELECT 
                COALESCE(SUM(json_extract(data, '$.tokens.total')), 0) as total_tokens,
                COALESCE(MAX(json_extract(data, '$.tokens.total')), 0) as peak_tokens,
                COUNT(DISTINCT session_id) as session_count,
                COUNT(*) as msg_count
            FROM message 
            WHERE {where}
        """, params)
        row = cur.fetchone()
        
        total_tokens = row["total_tokens"]
        peak_tokens = row["peak_tokens"]
        session_count = row["session_count"]
        msg_count = row["msg_count"]
        
        # Longest chat duration
        cur = conn.execute(f"""
            SELECT 
                session_id,
                MIN(time_created) as session_start,
                MAX(time_created) as session_end
            FROM message 
            WHERE {where}
            GROUP BY session_id
        """, params)
        
        longest_duration = 0
        for row in cur.fetchall():
            duration = (row["session_end"] - row["session_start"]) / 1000 / 60
            if duration > longest_duration:
                longest_duration = duration
        
        hours = int(longest_duration // 60)
        minutes = int(longest_duration % 60)
        longest_chat = f"{hours}小时{minutes}分钟" if hours > 0 else f"{minutes}分钟"
        
        # Streaks
        cur = conn.execute(f"""
            SELECT DISTINCT DATE(time_created / 1000, 'unixepoch', 'localtime') as activity_date
            FROM message 
            WHERE {where}
            ORDER BY activity_date DESC
        """, params)
        dates = [row["activity_date"] for row in cur.fetchall()]
        
        current_streak = 0
        longest_streak = 0
        streak = 1
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        if dates:
            if dates[0] == today or dates[0] == yesterday:
                current_streak = 1
                for i in range(1, len(dates)):
                    d1 = datetime.strptime(dates[i-1], "%Y-%m-%d")
                    d2 = datetime.strptime(dates[i], "%Y-%m-%d")
                    diff = (d1 - d2).days
                    if diff == 1:
                        current_streak += 1
                    else:
                        break
            
            longest_streak = 1
            streak = 1
            for i in range(1, len(dates)):
                d1 = datetime.strptime(dates[i-1], "%Y-%m-%d")
                d2 = datetime.strptime(dates[i], "%Y-%m-%d")
                diff = (d1 - d2).days
                if diff == 1:
                    streak += 1
                    longest_streak = max(longest_streak, streak)
                else:
                    streak = 1
        
        return {
            "total_tokens": total_tokens,
            "peak_tokens": peak_tokens,
            "longest_chat": longest_chat,
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "session_count": session_count,
            "msg_count": msg_count
        }
    finally:
        conn.close()


def get_daily_data(query):
    conn = get_db()
    try:
        mode, days, start_ts, end_ts = parse_time_filter(query)
        where, params = build_where_clause(mode, days, start_ts, end_ts)
        
        cur = conn.execute(f"""
            SELECT 
                DATE(time_created / 1000, 'unixepoch', 'localtime') as date,
                json_extract(data, '$.providerID') as provider,
                json_extract(data, '$.modelID') as model,
                SUM(json_extract(data, '$.tokens.total')) as total_tokens,
                COUNT(*) as msg_count
            FROM message 
            WHERE {where}
            GROUP BY date, provider, model
            ORDER BY date ASC, total_tokens DESC
        """, params)
        
        rows = cur.fetchall()
        result = []
        for row in rows:
            result.append({
                "date": row["date"],
                "provider": row["provider"],
                "model": row["model"],
                "total_tokens": row["total_tokens"],
                "msg_count": row["msg_count"]
            })
        return result
    finally:
        conn.close()


def get_model_distribution(query):
    conn = get_db()
    try:
        # Check for direct date range parameters
        if "start=" in query and "end=" in query:
            start_str = query.split("start=")[1].split("&")[0]
            end_str = query.split("end=")[1].split("&")[0]
            try:
                start_dt = datetime.strptime(start_str, "%Y-%m-%d")
                end_dt = datetime.strptime(end_str, "%Y-%m-%d")
                end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
                start_ts = int(start_dt.timestamp() * 1000)
                end_ts = int(end_dt.timestamp() * 1000)
                where = "data LIKE '%tokens%' AND json_extract(data, '$.tokens.total') IS NOT NULL AND time_created >= ? AND time_created <= ?"
                params = [start_ts, end_ts]
            except:
                where = "data LIKE '%tokens%' AND json_extract(data, '$.tokens.total') IS NOT NULL"
                params = []
        else:
            mode, days, start_ts, end_ts = parse_time_filter(query)
            where, params = build_where_clause(mode, days, start_ts, end_ts)
        
        cur = conn.execute(f"""
            SELECT 
                json_extract(data, '$.providerID') as provider,
                json_extract(data, '$.modelID') as model,
                SUM(json_extract(data, '$.tokens.total')) as total_tokens,
                COUNT(*) as msg_count
            FROM message 
            WHERE {where}
            GROUP BY provider, model
            ORDER BY total_tokens DESC
        """, params)
        
        rows = cur.fetchall()
        result = []
        for row in rows:
            result.append({
                "provider": row["provider"],
                "model": row["model"],
                "total_tokens": row["total_tokens"],
                "msg_count": row["msg_count"]
            })
        return result
    finally:
        conn.close()


def get_activity_data(query):
    conn = get_db()
    try:
        mode, days, start_ts, end_ts = parse_time_filter(query)
        where, params = build_where_clause(mode, days, start_ts, end_ts)
        
        # Use local time for date extraction to avoid timezone issues
        cur = conn.execute(f"""
            SELECT 
                DATE(MIN(time_created) / 1000, 'unixepoch', 'localtime') as min_date,
                DATE(MAX(time_created) / 1000, 'unixepoch', 'localtime') as max_date
            FROM message 
            WHERE {where}
        """, params)
        row = cur.fetchone()
        
        if not row or not row["min_date"]:
            return {"start": "", "end": "", "daily": {}}
        
        min_date = datetime.strptime(row["min_date"], "%Y-%m-%d")
        max_date = datetime.strptime(row["max_date"], "%Y-%m-%d")
        
        # Always extend to at least today (local date)
        today = datetime.now().date()
        if max_date.date() < today:
            max_date = datetime.combine(today, datetime.min.time())
        
        cur = conn.execute(f"""
            SELECT 
                DATE(time_created / 1000, 'unixepoch', 'localtime') as date,
                SUM(json_extract(data, '$.tokens.total')) as total_tokens,
                COUNT(*) as msg_count
            FROM message 
            WHERE {where}
            GROUP BY date
            ORDER BY date ASC
        """, params)
        
        daily_map = {}
        for row in cur.fetchall():
            daily_map[row["date"]] = {
                "total_tokens": row["total_tokens"],
                "msg_count": row["msg_count"]
            }
        
        return {
            "start": min_date.strftime("%Y-%m-%d"),
            "end": max_date.strftime("%Y-%m-%d"),
            "daily": daily_map
        }
    finally:
        conn.close()


def get_today_data():
    """Get today's token usage."""
    conn = get_db()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        start_of_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_ts = int(start_of_day.timestamp() * 1000)
        end_ts = int((start_of_day + timedelta(days=1)).timestamp() * 1000) - 1
        
        cur = conn.execute("""
            SELECT 
                COALESCE(SUM(json_extract(data, '$.tokens.total')), 0) as total_tokens,
                COUNT(*) as msg_count
            FROM message 
            WHERE data LIKE '%tokens%' AND json_extract(data, '$.tokens.total') IS NOT NULL
                AND time_created >= ? AND time_created <= ?
        """, (start_ts, end_ts))
        
        row = cur.fetchone()
        return {
            "date": today,
            "total_tokens": row["total_tokens"],
            "msg_count": row["msg_count"]
        }
    finally:
        conn.close()


def get_recent_sessions(limit=100):
    """Get the most recent assistant request records with token breakdown."""
    conn = get_db()
    try:
        cur = conn.execute("""
            SELECT m.id, m.session_id, m.time_created, m.data, s.title as session_title
            FROM message m
            LEFT JOIN session s ON s.id = m.session_id
            WHERE m.data LIKE '%tokens%' AND json_extract(m.data,'$.role') = 'assistant'
            ORDER BY m.time_created DESC
            LIMIT ?
        """, (limit,))
        result = []
        for row in cur.fetchall():
            try:
                d = json.loads(row["data"])
            except Exception:
                continue
            tokens = d.get("tokens", {}) or {}
            cache = tokens.get("cache", {}) or {}
            title = (row["session_title"] or "").replace("\n", " ").replace("\r", " ").strip()
            result.append({
                "time": datetime.fromtimestamp(row["time_created"] / 1000).strftime("%m-%d %H:%M:%S"),
                "provider": d.get("providerID", "") or "",
                "model": d.get("modelID", "") or "",
                "input": tokens.get("input", 0) or 0,
                "output": tokens.get("output", 0) or 0,
                "reasoning": tokens.get("reasoning", 0) or 0,
                "cache_read": cache.get("read", 0) or 0,
                "cache_write": cache.get("write", 0) or 0,
                "total": tokens.get("total", 0) or 0,
                "cost": d.get("cost", 0) or 0,
                "session": (row["session_id"] or "")[-8:],
                "title": title
            })
        return result
    finally:
        conn.close()


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self._cors()
        self.end_headers()

    def do_GET(self):
        try:
            if self.path == "/" or self.path == "/index.html":
                with open(HTML_PATH, "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            elif self.path.startswith("/api/summary"):
                data = get_summary(self.path.split("?")[1] if "?" in self.path else "")
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
            elif self.path.startswith("/api/daily"):
                data = get_daily_data(self.path.split("?")[1] if "?" in self.path else "")
                self._send(200, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            elif self.path.startswith("/api/models"):
                data = get_model_distribution(self.path.split("?")[1] if "?" in self.path else "")
                self._send(200, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            elif self.path.startswith("/api/activity"):
                data = get_activity_data(self.path.split("?")[1] if "?" in self.path else "")
                self._send(200, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            elif self.path.startswith("/api/today"):
                data = get_today_data()
                self._send(200, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            elif self.path.startswith("/api/sessions"):
                data = get_recent_sessions()
                self._send(200, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            else:
                self._send(404, b"not found", "text/plain; charset=utf-8")
        except Exception as e:
            self._send(500, str(e).encode("utf-8"), "text/plain; charset=utf-8")

    def log_message(self, fmt, *args):
        pass


def main():
    import time
    class Server(ThreadingHTTPServer):
        allow_reuse_address = True
        daemon_threads = True
    try:
        srv = Server(("127.0.0.1", PORT), Handler)
    except OSError:
        print("Token 面板服务已经在运行了，无需重复启动。")
        return
    print("=" * 48)
    print("  KiloCode Token 面板服务已启动")
    print("  面板地址:  http://127.0.0.1:%d/" % PORT)
    print("  数据来源:  %s" % DB_PATH)
    print("  仅本机可访问（127.0.0.1），关闭本窗口即停止服务")
    print("=" * 48)
    while True:
        try:
            srv.serve_forever()
            break
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("服务异常，5 秒后自动重启:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
