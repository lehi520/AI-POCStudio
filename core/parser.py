"""
网页文本智能化去噪、脱水与要素提取
负责将异构安全文本（HTML、微信长文）转化为高密度结构化上下文
"""

import re
import trafilatura


def extract_text_from_html(html: str) -> str:
    """
    从 HTML 中提取正文，去噪脱水
    """
    text = trafilatura.extract(html, include_comments=False, include_tables=True,
                                favor_precision=True, deduplicate=True)
    if not text:
        # 降级：直接用正则去除标签
        text = re.sub(r'<[^>]+>', '', html)
        text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_text_from_url(url: str, proxy: dict = None) -> str:
    """
    从 URL 抓取并提取正文
    """
    import requests
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, proxies=proxy, timeout=15)
        resp.raise_for_status()
        return extract_text_from_html(resp.text)
    except Exception as e:
        return f"[抓取失败] {e}"


def dehydrate_text(raw_text: str) -> dict:
    """
    长文脱水：从原始文本中提取关键安全要素

    返回结构化字典：
    {
        "cves": [...],          # CVE 编号列表
        "urls": [...],          # 相关 URL
        "paths": [...],         # 攻击路径
        "params": [...],        # 漏洞参数
        "methods": [...],       # 请求方法 (GET/POST)
        "payloads": [...],      # 核心 Payload 块
        "keywords": [...],      # 关键技术词
        "summary": "..."        # 浓缩摘要
    }
    """
    result = {
        "cves": [],
        "urls": [],
        "paths": [],
        "params": [],
        "methods": [],
        "payloads": [],
        "keywords": [],
        "summary": ""
    }

    # 提取 CVE 编号
    result["cves"] = list(set(re.findall(
        r'CVE-\d{4}-\d{4,}', raw_text, re.IGNORECASE
    )))

    # 提取 URL
    result["urls"] = list(set(re.findall(
        r'https?://[^\s<>"\')\]]+', raw_text
    )))

    # 提取路径（如 /api/v1/xxx, /admin/login）
    result["paths"] = list(set(re.findall(
        r'(?:GET|POST|PUT|DELETE|PATCH)?\s*(/[a-zA-Z0-9_\-/.{}]+)', raw_text
    )))

    # 提取参数（如 ?id=xxx, param=xxx）
    result["params"] = list(set(re.findall(
        r'[?&]([a-zA-Z_][a-zA-Z0-9_]*)=', raw_text
    )))

    # 提取请求方法
    result["methods"] = list(set(re.findall(
        r'\b(GET|POST|PUT|DELETE|PATCH|OPTIONS)\b', raw_text, re.IGNORECASE
    )))

    # 提取 Payload 块（引号内的可疑内容、代码块）
    payload_patterns = [
        # 单引号/双引号内的长字符串（可能是 Payload）
        r'["\']([^"\']{20,})["\']',
        # 代码块
        r'```[\w]*\n(.*?)```',
        # 常见 Payload 特征
        r'((?:\{\{.*?\}\}|<script>.*?</script>|/\*\*/|UNION\s+SELECT|OR\s+1=1|'
        r'<%.*?%>|\$\{.*?\})[^\n]{0,100})',
    ]
    payloads = set()
    for pattern in payload_patterns:
        for match in re.findall(pattern, raw_text, re.DOTALL | re.IGNORECASE):
            cleaned = match.strip()
            if len(cleaned) > 5:
                payloads.add(cleaned[:500])  # 限制长度
    result["payloads"] = list(payloads)

    # 提取关键技术词
    tech_keywords = [
        'RCE', 'SSRF', 'XSS', 'SQLi', 'LFI', 'RFI', 'XXE', 'SSTI', 'CSRF',
        '反序列化', '权限绕过', '未授权', '任意文件读取', '任意文件上传',
        '命令注入', '代码注入', '目录遍历', '信息泄露', '弱口令',
        'deserialization', 'injection', 'bypass', 'overflow', 'upload',
        'readfile', 'include', 'eval', 'exec', 'system', 'Runtime',
    ]
    found_keywords = set()
    text_lower = raw_text.lower()
    for kw in tech_keywords:
        if kw.lower() in text_lower:
            found_keywords.add(kw)
    result["keywords"] = list(found_keywords)

    # 生成浓缩摘要（取前 2000 字符 + 关键要素拼接）
    lines = raw_text.split('\n')
    meaningful_lines = [
        line.strip() for line in lines
        if len(line.strip()) > 15
        and not re.match(r'^(#|!|>|-{3,}|={3,}|\*{3,})', line.strip())
    ]
    summary_parts = []

    if result["cves"]:
        summary_parts.append(f"CVE: {', '.join(result['cves'])}")
    if result["keywords"]:
        summary_parts.append(f"漏洞类型: {', '.join(result['keywords'])}")
    if result["methods"]:
        summary_parts.append(f"请求方法: {', '.join(result['methods'])}")
    if result["paths"]:
        summary_parts.append(f"路径: {', '.join(result['paths'][:5])}")
    if result["params"]:
        summary_parts.append(f"参数: {', '.join(result['params'][:5])}")

    # 取有意义的前若干行作为上下文
    context_text = '\n'.join(meaningful_lines[:30])
    summary_parts.append(f"\n--- 原文关键片段 ---\n{context_text[:2000]}")

    result["summary"] = '\n'.join(summary_parts)
    return result


def build_ai_context(dehydrated: dict) -> str:
    """
    将脱水后的结构化数据组装为送给 AI 的高密度上下文
    """
    parts = []

    if dehydrated["cves"]:
        parts.append(f"【漏洞编号】{', '.join(dehydrated['cves'])}")

    if dehydrated["keywords"]:
        parts.append(f"【漏洞类型】{', '.join(dehydrated['keywords'])}")

    if dehydrated["methods"]:
        parts.append(f"【请求方法】{', '.join(dehydrated['methods'])}")

    if dehydrated["paths"]:
        parts.append(f"【攻击路径】\n" + '\n'.join(f"  - {p}" for p in dehydrated["paths"][:10]))

    if dehydrated["params"]:
        parts.append(f"【漏洞参数】{', '.join(dehydrated['params'][:10])}")

    if dehydrated["payloads"]:
        parts.append(f"【Payload 示例】")
        for i, payload in enumerate(dehydrated["payloads"][:5], 1):
            parts.append(f"  Payload {i}:\n    {payload}")

    if dehydrated["urls"]:
        parts.append(f"【相关链接】\n" + '\n'.join(f"  - {u}" for u in dehydrated["urls"][:5]))

    if dehydrated["summary"]:
        parts.append(f"\n{dehydrated['summary']}")

    return '\n'.join(parts)
