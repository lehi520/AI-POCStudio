"""
AI-POCStudio 主窗口
三段式网格布局：情报中心 | AI协同代码编辑器 | 本地测试调试沙箱
"""

import json
import os
import threading
import webbrowser
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from core.ai_client import AIClient, extract_python_code
from core.parser import extract_text_from_url, dehydrate_text, build_ai_context
from core.crawler import SecurityCrawler
from core.executor import SandboxExecutor
from gui.components import StreamConsole, CodeEditor, HotListPanel, StatusBar


class MainWindow(ctk.CTk):
    """AI-POCStudio 主窗口"""

    def __init__(self, config: dict):
        super().__init__()

        self.config = config
        self.ai_client = None
        self.crawler = None
        self.executor = SandboxExecutor()

        # 情报缓存：存储完整的、未截断的原始数据（以 CVE 编号为 Key）
        self.cve_cache = {}   # {"CVE-2025-12345": "完整的漏洞描述原文...", ...}

        # 窗口基础配置
        self.title("AI-POCStudio | 智能漏洞复现与 POC 调试终端")
        self.geometry("1400x850")
        self.minsize(1200, 700)

        # 设置主题
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # 初始化 UI
        self._setup_ui()
        self._init_ai_client()
        self._init_crawler()

        # 绑定关闭事件
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_ui(self):
        """构建主界面"""
        # 主容器
        self.grid_columnconfigure(0, weight=2)  # 情报中心
        self.grid_columnconfigure(1, weight=3)  # AI 编辑器
        self.grid_columnconfigure(2, weight=2)  # 沙箱调试
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        # ════════════════ 第一栏：情报中心 ════════════════
        col1 = ctk.CTkFrame(self, fg_color="#0d1117", corner_radius=8)
        col1.grid(row=0, column=0, padx=(8, 4), pady=8, sticky="nsew")
        col1.grid_rowconfigure(0, weight=3)  # 热点列表（占大头）
        col1.grid_rowconfigure(2, weight=1)  # 脱水结果
        col1.grid_columnconfigure(0, weight=1)

        # -- 热点监控列表（卡片式） --
        self.hotlist_panel = HotListPanel(
            col1,
            on_reproduce=self._on_card_reproduce,
            on_open_url=self._on_card_open_url
        )
        self.hotlist_panel.grid(row=0, column=0, padx=5, pady=(5, 3), sticky="nsew")
        self.hotlist_panel.refresh_btn.configure(command=self._manual_refresh)

        # -- 手动输入区域（紧凑排列） --
        input_frame = ctk.CTkFrame(col1, fg_color="transparent")
        input_frame.grid(row=1, column=0, padx=5, pady=(0, 3), sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            input_frame, text="🔗 手动指定 URL 或粘贴文本",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#00ccff"
        ).grid(row=0, column=0, padx=2, pady=(0, 2), sticky="w")

        self.url_input = ctk.CTkTextbox(
            input_frame,
            height=60,
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color="#e0e0e0",
            fg_color="#161b22",
            scrollbar_button_color="#333333",
            wrap="word"
        )
        self.url_input.grid(row=1, column=0, padx=2, pady=(0, 3), sticky="ew")

        self.fetch_btn = ctk.CTkButton(
            input_frame, text="📡 同步抓取并长文脱水",
            height=30,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1a5276", hover_color="#2980b9",
            command=self._fetch_and_dehydrate
        )
        self.fetch_btn.grid(row=2, column=0, padx=2, pady=0, sticky="ew")

        # -- 脱水结果展示框 --
        ctk.CTkLabel(
            col1, text="📋 脱水后核心要素（可编辑）",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#00ccff"
        ).grid(row=2, column=0, padx=7, pady=(3, 0), sticky="sw")

        self.dehydrated_box = ctk.CTkTextbox(
            col1,
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color="#ffd700",
            fg_color="#161b22",
            scrollbar_button_color="#333333",
            scrollbar_button_hover_color="#555555",
            wrap="word"
        )
        self.dehydrated_box.grid(row=3, column=0, padx=5, pady=(0, 5), sticky="nsew")

        # ════════════════ 第二栏：AI 协同代码编辑器 ════════════════
        col2 = ctk.CTkFrame(self, fg_color="#0d1117", corner_radius=8)
        col2.grid(row=0, column=1, padx=4, pady=8, sticky="nsew")
        col2.grid_rowconfigure(1, weight=1)
        col2.grid_columnconfigure(0, weight=1)

        # -- 生成控制栏 --
        ctrl_frame = ctk.CTkFrame(col2, fg_color="transparent")
        ctrl_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ctrl_frame.grid_columnconfigure(0, weight=1)

        self.generate_btn = ctk.CTkButton(
            ctrl_frame, text="🔥 让 AI 生成标准 POC",
            height=38,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#e74c3c", hover_color="#c0392b",
            command=self._generate_poc
        )
        self.generate_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.stop_gen_btn = ctk.CTkButton(
            ctrl_frame, text="⏹ 停止", width=70, height=38,
            font=ctk.CTkFont(size=12),
            fg_color="#555555", hover_color="#777777",
            command=self._stop_generation
        )
        self.stop_gen_btn.grid(row=0, column=1, padx=(0, 5))

        # -- 代码编辑器 --
        self.code_editor = CodeEditor(col2)
        self.code_editor.grid(row=1, column=0, padx=5, pady=(0, 5), sticky="nsew")

        # ════════════════ 第三栏：本地测试调试沙箱 ════════════════
        col3 = ctk.CTkFrame(self, fg_color="#0d1117", corner_radius=8)
        col3.grid(row=0, column=2, padx=(4, 8), pady=8, sticky="nsew")
        col3.grid_rowconfigure(3, weight=1)
        col3.grid_columnconfigure(0, weight=1)

        # -- 目标配置 --
        target_frame = ctk.CTkFrame(col3, fg_color="transparent")
        target_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        target_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            target_frame, text="🎯 目标 URL",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ff6644"
        ).grid(row=0, column=0, padx=5, sticky="w")

        self.target_entry = ctk.CTkEntry(
            target_frame,
            placeholder_text="http://target.com/vuln",
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#161b22",
            text_color="#e0e0e0"
        )
        self.target_entry.grid(row=0, column=1, padx=5, sticky="ew")

        # 代理配置
        ctk.CTkLabel(
            target_frame, text="🌐 代理",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ff6644"
        ).grid(row=1, column=0, padx=5, sticky="w")

        self.proxy_entry = ctk.CTkEntry(
            target_frame,
            placeholder_text="http://127.0.0.1:7890 (可选)",
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#161b22",
            text_color="#e0e0e0"
        )
        self.proxy_entry.grid(row=1, column=1, padx=5, sticky="ew")

        # -- 运行按钮 --
        run_frame = ctk.CTkFrame(col3, fg_color="transparent")
        run_frame.grid(row=1, column=0, padx=5, pady=3, sticky="ew")
        run_frame.grid_columnconfigure(0, weight=1)
        run_frame.grid_columnconfigure(1, weight=0)

        self.run_btn = ctk.CTkButton(
            run_frame, text="⚡ 运行测试 (异步非阻塞)",
            height=35,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#27ae60", hover_color="#229954",
            command=self._run_script
        )
        self.run_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.stop_run_btn = ctk.CTkButton(
            run_frame, text="⏹ 终止", width=70, height=35,
            font=ctk.CTkFont(size=12),
            fg_color="#555555", hover_color="#777777",
            command=self._stop_script
        )
        self.stop_run_btn.grid(row=0, column=1)

        # -- 修复按钮 --
        self.fix_btn = ctk.CTkButton(
            col3, text="🔧 捕捉报错：AI 一键校正",
            height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#e67e22", hover_color="#d35400",
            command=self._auto_fix
        )
        self.fix_btn.grid(row=2, column=0, padx=5, pady=3, sticky="ew")

        # -- Console 控制台 --
        self.console = StreamConsole(col3, title="Console 输出")
        self.console.grid(row=3, column=0, padx=5, pady=(0, 5), sticky="nsew")

        # ════════════════ 底部状态栏 ════════════════
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=1, column=0, columnspan=3, padx=8, pady=(0, 8), sticky="ew")

        # 存储最新的 stderr 用于自动修复
        self._last_stderr = ""
        self._generation_thread = None

    def _init_ai_client(self):
        """初始化 AI 客户端"""
        ai_conf = self.config.get("ai", {})
        proxy_conf = self.config.get("proxy", {})

        proxy = None
        if proxy_conf.get("enabled") and proxy_conf.get("http"):
            proxy = proxy_conf["http"]

        if ai_conf.get("api_key"):
            try:
                self.ai_client = AIClient(
                    base_url=ai_conf.get("base_url", "https://api.deepseek.com/v1"),
                    api_key=ai_conf["api_key"],
                    model=ai_conf.get("model", "deepseek-chat"),
                    max_tokens=ai_conf.get("max_tokens", 4096),
                    temperature=ai_conf.get("temperature", 0.3),
                    proxy=proxy
                )
                self.status_bar.set_api_status(
                    f"已连接 ({ai_conf.get('model', 'unknown')})", True
                )
            except Exception as e:
                self.status_bar.set_api_status(f"连接失败: {e}", False)
        else:
            self.status_bar.set_api_status("未配置 API Key", False)

        if proxy_conf.get("enabled"):
            self.status_bar.set_proxy_status(proxy_conf.get("http", "未设置"))
        else:
            self.status_bar.set_proxy_status("未启用")

    def _init_crawler(self):
        """初始化爬虫（使用配置文件中的代理作为默认值）"""
        self.crawler = SecurityCrawler(
            proxy=self._get_crawler_proxy()
        )

    def _get_crawler_proxy(self) -> dict:
        """
        实时从右侧代理输入框读取代理配置
        优先使用 UI 输入框的值，回退到 config.json 的默认值
        """
        # 先看 UI 输入框有没有值
        ui_proxy = self.proxy_entry.get().strip()
        if ui_proxy:
            return {"http": ui_proxy, "https": ui_proxy}

        # 回退到配置文件
        proxy_conf = self.config.get("proxy", {})
        if proxy_conf.get("enabled") and proxy_conf.get("http"):
            return {"http": proxy_conf["http"], "https": proxy_conf.get("https", proxy_conf["http"])}

        return {}

    def _sync_crawler_proxy(self):
        """将当前代理配置同步到爬虫实例"""
        self.crawler.proxy = self._get_crawler_proxy()

    def _manual_refresh(self):
        """手动刷新 CVE 最新公告"""
        current_proxy = self._get_crawler_proxy()
        self.hotlist_panel.set_loading(True)
        self.status_bar.set_status("正在抓取 CVE 公告...", "#ffaa00")

        def _fetch():
            try:
                self.crawler.proxy = current_proxy
                cves = self.crawler.fetch_latest_cves()

                # 全量存入缓存（截断前）
                for cve in cves:
                    cve_id = cve.get("cve", "").strip()
                    if cve_id and not cve_id.startswith("["):
                        self.cve_cache[cve_id] = cve.get("desc", "")

                self.after(0, lambda: self.hotlist_panel.load_cards([], cves))
                self.after(0, lambda: self.status_bar.set_status(
                    f"CVE 刷新完成（已缓存 {len(self.cve_cache)} 条）"
                ))
            except Exception as e:
                self.after(0, lambda: self.status_bar.set_status(f"刷新失败: {e}", "#ff6644"))
            finally:
                self.after(0, lambda: self.hotlist_panel.set_loading(False))

        threading.Thread(target=_fetch, daemon=True).start()

    def _fetch_and_dehydrate(self):
        """抓取 URL 并执行长文脱水（优先查本地缓存）"""
        input_text = self.url_input.get("1.0", "end-1c").strip()
        if not input_text:
            messagebox.showwarning("提示", "请输入 URL 或要脱水的文本内容")
            return

        # 主线程读 UI 控件，传入后台线程（tkinter 限制：只能主线程访问控件）
        current_proxy = self._get_crawler_proxy()
        self.fetch_btn.configure(state="disabled", text="⏳ 抓取中...")
        self.status_bar.set_status("正在抓取并脱水...", "#ffaa00")

        def _process():
            try:
                import re
                raw_text = None
                cache_hit = False

                # 优先：检查输入是否为已缓存的 CVE 编号
                cve_match = re.search(r'(CVE-\d{4}-\d{4,7})', input_text, re.IGNORECASE)
                if cve_match:
                    cve_id = cve_match.group(1).upper()
                    if cve_id in self.cve_cache:
                        raw_text = self.cve_cache[cve_id]
                        cache_hit = True
                        self.after(0, lambda: self.status_bar.set_status(
                            f"✅ 命中本地缓存: {cve_id}（免网络请求）", "#00ff88"
                        ))

                # 回退：走网络抓取
                if not cache_hit:
                    if input_text.startswith(("http://", "https://")):
                        raw_text = extract_text_from_url(input_text, current_proxy or None)
                    else:
                        raw_text = input_text

                # 脱水处理
                dehydrated = dehydrate_text(raw_text)
                formatted = self._format_dehydrated(dehydrated)

                self.after(0, lambda: self.dehydrated_box.delete("1.0", "end"))
                self.after(0, lambda: self.dehydrated_box.insert("1.0", formatted))
                if not cache_hit:
                    self.after(0, lambda: self.status_bar.set_status("脱水完成，可编辑后发送给 AI"))
            except Exception as e:
                self.after(0, lambda: self.status_bar.set_status(f"脱水失败: {e}", "#ff6644"))
            finally:
                self.after(0, lambda: self.fetch_btn.configure(state="normal", text="📡 同步抓取并长文脱水"))

        threading.Thread(target=_process, daemon=True).start()

    def _format_dehydrated(self, dehydrated: dict) -> str:
        """格式化脱水结果为可编辑文本"""
        parts = []
        if dehydrated["cves"]:
            parts.append(f"[CVE编号] {', '.join(dehydrated['cves'])}")
        if dehydrated["keywords"]:
            parts.append(f"[漏洞类型] {', '.join(dehydrated['keywords'])}")
        if dehydrated["methods"]:
            parts.append(f"[请求方法] {', '.join(dehydrated['methods'])}")
        if dehydrated["paths"]:
            parts.append(f"[攻击路径]")
            for p in dehydrated["paths"][:10]:
                parts.append(f"  {p}")
        if dehydrated["params"]:
            parts.append(f"[漏洞参数] {', '.join(dehydrated['params'][:10])}")
        if dehydrated["payloads"]:
            parts.append(f"[Payload 示例]")
            for i, p in enumerate(dehydrated["payloads"][:5], 1):
                parts.append(f"  #{i}: {p}")
        if dehydrated["urls"]:
            parts.append(f"[相关链接]")
            for u in dehydrated["urls"][:5]:
                parts.append(f"  {u}")
        parts.append(f"\n[原文摘要]\n{dehydrated.get('summary', '')[:1500]}")
        return '\n'.join(parts)

    # ════════════════ 卡片交互回调 ════════════════

    def _on_card_reproduce(self, data: dict):
        """
        卡片 [🚀 一键复现] 回调
        从 CVE 缓存取完整描述，填入输入框和脱水框
        """
        url = data.get("url", "")
        cve_id = data.get("cve", "").strip()
        desc = data.get("desc", "")

        # 从缓存捞完整描述
        full_desc = desc
        cache_hit = False
        if cve_id and cve_id != "Unknown-CVE" and cve_id in self.cve_cache:
            full_desc = self.cve_cache[cve_id]
            cache_hit = True

        # 填充 URL 输入框
        self.url_input.delete("1.0", "end")
        self.url_input.insert("1.0", url if url else cve_id)

        # 填充脱水要素框
        self.dehydrated_box.delete("1.0", "end")
        prefill = []
        if cve_id and cve_id != "Unknown-CVE":
            prefill.append(f"[CVE编号] {cve_id}")
        if full_desc:
            prefill.append(f"[完整描述] {full_desc}")
        if url:
            prefill.append(f"[链接] {url}")
        if cache_hit:
            prefill.append(f"\n[数据来源] CVE本地缓存")
        self.dehydrated_box.insert("1.0", '\n'.join(prefill))

        self.status_bar.set_status(
            f"已载入: {cve_id}{'（缓存命中）' if cache_hit else ''}",
            "#00ff88" if cache_hit else "#00ccff"
        )

    def _on_card_open_url(self, url: str):
        """
        卡片 [🔗 查看原文] 回调
        唤醒系统默认浏览器打开链接
        """
        if url:
            webbrowser.open(url)
            self.status_bar.set_status(f"已在浏览器中打开: {url[:60]}")

    def _generate_poc(self):
        """调用 AI 生成 POC 代码"""
        if not self.ai_client:
            messagebox.showwarning("AI 未配置", "请先在 config/settings.json 中配置 API Key")
            return

        # 获取脱水后的情报上下文
        context = self.dehydrated_box.get("1.0", "end-1c").strip()
        if not context:
            messagebox.showwarning("提示", "请先抓取/粘贴漏洞情报并脱水，或直接在脱水框中输入漏洞描述")
            return

        # 开始流式生成
        self.code_editor.start_stream()
        self.generate_btn.configure(state="disabled")
        self.status_bar.set_status("AI 正在生成 POC...", "#ff6644")
        self.status_bar.set_thread_status("生成中...")

        def on_chunk(text):
            self.after(0, lambda t=text: self.code_editor.append_stream(t))

        def on_done(full_text):
            code = extract_python_code(full_text)
            self.after(0, lambda: self.code_editor.finish_stream(code))
            self.after(0, lambda: self.generate_btn.configure(state="normal"))
            self.after(0, lambda: self.status_bar.set_status("POC 生成完成"))
            self.after(0, lambda: self.status_bar.set_thread_status("空闲"))

        def on_error(err):
            self.after(0, lambda: self.code_editor.set_status(f"❌ 生成失败: {err}", "#ff4444"))
            self.after(0, lambda: self.generate_btn.configure(state="normal"))
            self.after(0, lambda: self.status_bar.set_status(f"生成失败: {err}", "#ff6644"))
            self.after(0, lambda: self.status_bar.set_thread_status("空闲"))

        self._generation_thread = self.ai_client.generate_poc_stream(
            context, on_chunk, on_done, on_error
        )

    def _stop_generation(self):
        """停止 AI 生成"""
        # 注意：OpenAI 流式请求无法中途取消线程，但可以忽略后续回调
        self.generate_btn.configure(state="normal")
        self.code_editor.set_status("⏹ 已停止生成", "#ffaa00")
        self.status_bar.set_status("生成已停止")
        self.status_bar.set_thread_status("空闲")

    def _run_script(self):
        """运行当前编辑器中的脚本"""
        code = self.code_editor.get_content().strip()
        if not code:
            messagebox.showwarning("提示", "编辑器中没有代码，请先生成或粘贴 POC 脚本")
            return

        # 构建命令行参数
        args = []
        target = self.target_entry.get().strip()
        if target:
            args.extend(["--target", target])

        proxy = self.proxy_entry.get().strip()
        if proxy:
            args.extend(["--proxy", proxy])

        # 清空控制台
        self.console.clear()
        self.console.append_line(f"{'='*50}")
        self.console.append_line(f"[*] 开始执行 POC 脚本")
        self.console.append_line(f"[*] 目标: {target or '未指定'}")
        self.console.append_line(f"[*] 代理: {proxy or '未启用'}")
        self.console.append_line(f"{'='*50}\n")

        self.run_btn.configure(state="disabled")
        self.status_bar.set_status("脚本执行中...", "#ffaa00")
        self.status_bar.set_thread_status("执行中...")
        self._last_stderr = ""

        def on_stdout(line):
            self.after(0, lambda l=line: self.console.append_line(l))

        def on_stderr(line):
            self._last_stderr += line + "\n"
            self.after(0, lambda l=line: self.console.append_line(f"[ERR] {l}"))

        def on_finish(exit_code, stderr):
            def _update():
                self.run_btn.configure(state="normal")
                self.console.append_line(f"\n{'='*50}")
                if exit_code == 0:
                    self.console.append_line(f"[✓] 脚本执行完成 (退出码: 0)")
                    self.status_bar.set_status("执行完成")
                else:
                    self.console.append_line(f"[✗] 脚本执行失败 (退出码: {exit_code})")
                    if stderr:
                        self.console.append_line(f"\n--- 错误输出 ---")
                        self.console.append_line(stderr)
                    self.status_bar.set_status(f"执行失败 (退出码: {exit_code})", "#ff6644")
                self.status_bar.set_thread_status("空闲")

            self.after(0, _update)

        self.executor.run_script(code, args, on_stdout, on_stderr, on_finish)

    def _stop_script(self):
        """终止正在运行的脚本"""
        if self.executor.is_running():
            self.executor.stop()
            self.console.append_line("\n[!] 用户手动终止脚本")
            self.run_btn.configure(state="normal")
            self.status_bar.set_status("脚本已终止", "#ffaa00")
            self.status_bar.set_thread_status("空闲")

    def _auto_fix(self):
        """AI 一键自动修复"""
        if not self.ai_client:
            messagebox.showwarning("AI 未配置", "请先在 config/settings.json 中配置 API Key")
            return

        current_code = self.code_editor.get_content().strip()
        stderr = self._last_stderr.strip()

        if not current_code:
            messagebox.showwarning("提示", "编辑器中没有代码")
            return

        if not stderr:
            # 尝试从控制台获取错误信息
            console_text = self.console.get_content()
            if "[ERR]" in console_text or "Error" in console_text or "Traceback" in console_text:
                stderr = console_text
            else:
                messagebox.showinfo("提示", "没有检测到报错信息。请先运行脚本并确保有错误输出。")
                return

        # 开始流式修复
        self.code_editor.start_stream()
        self.code_editor.set_status("🔧 AI 正在修复代码...", "#e67e22")
        self.fix_btn.configure(state="disabled")
        self.status_bar.set_status("AI 正在自动修复...", "#e67e22")
        self.status_bar.set_thread_status("修复中...")

        def on_chunk(text):
            self.after(0, lambda t=text: self.code_editor.append_stream(t))

        def on_done(full_text):
            code = extract_python_code(full_text)
            self.after(0, lambda: self.code_editor.finish_stream(code))
            self.after(0, lambda: self.fix_btn.configure(state="normal"))
            self.after(0, lambda: self.console.append_line("\n[🔧] AI 自动修复完成，请重新运行测试"))
            self.after(0, lambda: self.status_bar.set_status("自动修复完成"))
            self.after(0, lambda: self.status_bar.set_thread_status("空闲"))

        def on_error(err):
            self.after(0, lambda: self.code_editor.set_status(f"❌ 修复失败: {err}", "#ff4444"))
            self.after(0, lambda: self.fix_btn.configure(state="normal"))
            self.after(0, lambda: self.status_bar.set_status(f"修复失败: {err}", "#ff6644"))
            self.after(0, lambda: self.status_bar.set_thread_status("空闲"))

        self.ai_client.fix_code_stream(current_code, stderr, on_chunk, on_done, on_error)

    def _on_closing(self):
        """窗口关闭时清理资源"""
        self.executor.cleanup()
        self.crawler.stop_auto_refresh()
        self.destroy()
