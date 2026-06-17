"""
AI 大模型统一适配层
支持所有 OpenAI 兼容格式的 API（DeepSeek、Ollama、GPT 等）
"""

import json
import threading
from typing import Generator, Callable, Optional
from openai import OpenAI

# 强约束 System Prompt —— 无害化安全 POC 生成专家
SYSTEM_PROMPT = (
    '你是一位顶级网络安全渗透测试专家，专注于编写 Python POC/EXP 验证脚本。\n'
    '\n'
    '## 硬性输出约束（必须严格遵守）\n'
    '1. 只输出纯 Python 代码，用 ```python 包裹，不要任何解释文字。\n'
    '2. 必须使用 argparse 解析命令行参数，统一规范：\n'
    '   - --target 目标 URL（必选）\n'
    '   - --proxy 代理地址（可选）\n'
    '   - --timeout 超时秒数（可选，默认 10）\n'
    '3. 无害化探测设计（必须遵守）：\n'
    '   - 使用 DNSLog 外带检测、Echo 回显、读取无害文件（如 /etc/passwd、/etc/hostname）作为验证手段。\n'
    '   - 严禁生成反弹 Shell、写入 Webshell、植入后门、删除数据等破坏性代码。\n'
    '   - 严禁生成 DoS/DDoS 攻击代码。\n'
    '4. 健壮性要求：\n'
    '   - 所有网络请求必须包裹在 try-except 中，捕获 requests.exceptions.RequestException。\n'
    '   - 必须设置合理的 timeout，避免脚本永久挂起。\n'
    '   - 输出清晰的成功/失败判定结果（如 [+] Vulnerable 或 [-] Not Vulnerable）。\n'
    '5. 代码风格：简洁、可读、有中文注释，适合安全研究人员直接使用。\n'
    '\n'
    '## 输出格式示例\n'
    '```python\n'
    '#!/usr/bin/env python3\n'
    '# -*- coding: utf-8 -*-\n'
    'import argparse\n'
    'import requests\n'
    '\n'
    'def verify(target, proxy=None, timeout=10):\n'
    '    # 漏洞验证逻辑\n'
    '    pass\n'
    '\n'
    'if __name__ == "__main__":\n'
    '    parser = argparse.ArgumentParser(description="CVE PoC")\n'
    '    parser.add_argument("--target", required=True, help="目标URL")\n'
    '    parser.add_argument("--proxy", default=None, help="代理地址")\n'
    '    parser.add_argument("--timeout", type=int, default=10, help="超时秒数")\n'
    '    args = parser.parse_args()\n'
    '    verify(args.target, args.proxy, args.timeout)\n'
    '```'
)

# 自动修复 System Prompt
FIX_PROMPT = (
    '你是一位 Python 调试专家。用户会提供一段有 Bug 的 POC 脚本和对应的报错 Traceback。\n'
    '请你分析错误原因，修复代码，只输出修复后的完整 Python 代码（用 ```python 包裹），不要任何解释。\n'
    '\n'
    '修复要求：\n'
    '1. 保持原有的功能逻辑不变，只修复导致崩溃的 Bug。\n'
    '2. 如果是依赖缺失，使用标准库替代方案。\n'
    '3. 增强异常处理，确保脚本不会因网络问题而崩溃。'
)


class AIClient:
    """统一大模型 API 适配器"""

    def __init__(self, base_url: str, api_key: str, model: str,
                 max_tokens: int = 4096, temperature: float = 0.3,
                 proxy: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        http_client_kwargs = {}
        if proxy:
            import httpx
            http_client_kwargs["http_client"] = httpx.Client(proxy=proxy)

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            **http_client_kwargs
        )

    def generate_poc_stream(self, context: str,
                            on_chunk: Callable[[str], None],
                            on_done: Callable[[str], None],
                            on_error: Callable[[str], None]):
        """
        流式生成 POC 代码（异步线程）

        Args:
            context: 脱水后的漏洞情报上下文
            on_chunk: 每收到一块文本时的回调（附带完整 chunk 文本）
            on_done: 生成完成时的回调（附带完整代码）
            on_error: 出错时的回调（附带错误信息）
        """
        def _stream():
            try:
                full_text = ""
                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"请根据以下漏洞情报，生成对应的 Python POC 验证脚本：\n\n{context}"}
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    stream=True
                )
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        text = chunk.choices[0].delta.content
                        full_text += text
                        on_chunk(text)
                on_done(full_text)
            except Exception as e:
                on_error(str(e))

        thread = threading.Thread(target=_stream, daemon=True)
        thread.start()
        return thread

    def fix_code_stream(self, buggy_code: str, traceback_log: str,
                        on_chunk: Callable[[str], None],
                        on_done: Callable[[str], None],
                        on_error: Callable[[str], None]):
        """
        流式修复有 Bug 的代码（异步线程）
        """
        def _stream():
            try:
                full_text = ""
                prompt = (
                    f"## 有 Bug 的代码\n```python\n{buggy_code}\n```\n\n"
                    f"## 报错 Traceback\n```\n{traceback_log}\n```\n\n"
                    f"请修复以上代码，只输出修复后的完整 Python 代码。"
                )

                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": FIX_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    stream=True
                )
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        text = chunk.choices[0].delta.content
                        full_text += text
                        on_chunk(text)
                on_done(full_text)
            except Exception as e:
                on_error(str(e))

        thread = threading.Thread(target=_stream, daemon=True)
        thread.start()
        return thread


def extract_python_code(text: str) -> str:
    """从 AI 响应中提取 ```python ... ``` 包裹的代码"""
    import re
    pattern = r'```python\s*\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return matches[0].strip()
    # 如果没有 ```python 标记，尝试直接返回
    if "import " in text or "def " in text:
        return text.strip()
    return text.strip()
