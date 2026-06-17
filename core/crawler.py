"""
安全情报爬虫 —— 仅保留 CVE 最新公告抓取
"""

import re
import threading
import requests
import urllib3
from typing import List, Dict, Callable
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SecurityCrawler:
    """CVE 情报爬虫"""

    def __init__(self, proxy: dict = None):
        if isinstance(proxy, str) and proxy.strip():
            self.proxy = {"http": proxy, "https": proxy}
        else:
            self.proxy = proxy or {}
        self._stop_event = threading.Event()
        self._thread = None

    # ════════════════ CVE 5.0 智能自愈解析 ════════════════

    def _smart_find_cve_id(self, item: dict) -> str:
        meta = item.get("cveMetadata") or item.get("cvemetadata") or {}
        if isinstance(meta, dict):
            for k in ["cveId", "cveID", "cveid", "cve_id"]:
                if meta.get(k):
                    return str(meta.get(k))
        for k in ["id", "cve", "cveId", "cve_id"]:
            if item.get(k):
                return str(item.get(k))
        match = re.search(r'CVE-\d{4}-\d{4,7}', str(item), re.IGNORECASE)
        return match.group(0).upper() if match else "Unknown-CVE"

    def _smart_find_description(self, item: dict) -> str:
        for k in ["summary", "description", "desc", "detail"]:
            if item.get(k) and isinstance(item.get(k), str):
                return item.get(k)
        containers = item.get("containers") or {}
        if isinstance(containers, dict):
            cna = containers.get("cna") or {}
            if isinstance(cna, dict):
                descs = cna.get("descriptions")
                if isinstance(descs, list) and descs:
                    if isinstance(descs[0], dict) and descs[0].get("value"):
                        return str(descs[0].get("value"))
        text_pool = []
        def _walk(node):
            if isinstance(node, dict):
                for v in node.values():
                    _walk(v)
            elif isinstance(node, list):
                for v in node:
                    _walk(v)
            elif isinstance(node, str) and len(node) > 25:
                if not node.startswith("http") and "cve-" not in node.lower():
                    text_pool.append(node)
        _walk(item)
        return max(text_pool, key=len) if text_pool else "No description available."

    def _smart_find_date(self, item: dict) -> str:
        meta = item.get("cveMetadata") or {}
        if isinstance(meta, dict):
            for k in ["datePublished", "dateUpdated"]:
                if meta.get(k):
                    return str(meta.get(k))[:10]
        match = re.search(r'\d{4}-\d{2}-\d{2}', str(item))
        return match.group(0) if match else "Time N/A"

    def fetch_latest_cves(self, limit: int = 10) -> List[Dict]:
        """抓取最新官方 CVE 公告（境外流量，走用户代理）"""
        results = []
        try:
            resp = requests.get(
                "https://cve.circl.lu/api/last",
                headers={"User-Agent": "Mozilla/5.0"},
                proxies=self.proxy,
                verify=False,
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()

            current_year = str(datetime.now().year)
            if data and isinstance(data, list):
                for item in data:
                    if len(results) >= limit:
                        break
                    if not isinstance(item, dict):
                        continue
                    cve_id = self._smart_find_cve_id(item)
                    # 只保留当年的 CVE（如 CVE-2026-xxxxx）
                    if f"CVE-{current_year}-" not in cve_id:
                        continue
                    results.append({
                        "cve": cve_id,
                        "desc": str(self._smart_find_description(item)).strip()[:300],
                        "date": self._smart_find_date(item),
                    })
        except Exception as e:
            print(f"[Crawler 错误] CVE 抓取失败: {e}")
            results.append({"cve": "[网络异常]", "desc": f"无法加载CVE公告: {e}", "date": ""})
        return results

    def format_hotlist(self, cves: List[Dict], **_) -> str:
        """格式化输出"""
        lines = [f"═══ 最新 CVE 公告   {datetime.now().strftime('%Y-%m-%d %H:%M')} ═══\n"]
        if cves:
            for cve in cves[:10]:
                lines.append(f"  {cve['cve']}")
                lines.append(f"    {cve['desc'][:120]}...")
                lines.append(f"    📅 {cve.get('date', '')}")
                lines.append("")
        else:
            lines.append("  暂无数据\n")
        return '\n'.join(lines)

    def start_auto_refresh(self, interval: int, callback: Callable[[str], None]):
        def _loop():
            while not self._stop_event.is_set():
                try:
                    cves = self.fetch_latest_cves()
                    callback(self.format_hotlist(cves))
                except Exception as e:
                    callback(f"[自动刷新失败] {e}")
                self._stop_event.wait(interval)
        self._stop_event.clear()
        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop_auto_refresh(self):
        self._stop_event.set()
