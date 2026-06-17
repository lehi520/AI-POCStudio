"""
自定义 GUI 组件
包含流式控制台、带行号的代码编辑器等核心组件
"""

import customtkinter as ctk
import tkinter as tk


class StreamConsole(ctk.CTkFrame):
    """
    流式控制台组件
    绿字黑底，支持实时逐行追加，类似终端风格
    """

    def __init__(self, master, title: str = "Console", **kwargs):
        super().__init__(master, **kwargs)

        # 标题栏
        self.title_label = ctk.CTkLabel(
            self, text=f"  ● {title}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#00ff88", anchor="w"
        )
        self.title_label.pack(fill="x", padx=5, pady=(5, 0))

        # 控制台文本框
        self.textbox = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Consolas", size=13),
            text_color="#00ff41",
            fg_color="#0a0a0a",
            scrollbar_button_color="#333333",
            scrollbar_button_hover_color="#555555",
            wrap="word",
            state="disabled"
        )
        self.textbox.pack(fill="both", expand=True, padx=5, pady=5)

        # 清除按钮
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=5, pady=(0, 5))

        self.clear_btn = ctk.CTkButton(
            btn_frame, text="🗑 清空", width=70, height=28,
            font=ctk.CTkFont(size=12),
            fg_color="#333333", hover_color="#555555",
            command=self.clear
        )
        self.clear_btn.pack(side="right")

    def append_line(self, text: str, color: str = None):
        """追加一行文本"""
        self.textbox.configure(state="normal")
        if color:
            # 简单的颜色标记
            tag_name = f"color_{color.replace('#', '')}"
            self.textbox.insert("end", text + "\n")
        else:
            self.textbox.insert("end", text + "\n")
        self.textbox.configure(state="disabled")
        self.textbox.see("end")

    def append_stream(self, text: str):
        """流式追加文本（不换行）"""
        self.textbox.configure(state="normal")
        self.textbox.insert("end", text)
        self.textbox.configure(state="disabled")
        self.textbox.see("end")

    def set_content(self, text: str):
        """设置全部内容"""
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", text)
        self.textbox.configure(state="disabled")

    def clear(self):
        """清空控制台"""
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")

    def get_content(self) -> str:
        """获取全部内容"""
        return self.textbox.get("1.0", "end-1c")


class CodeEditor(ctk.CTkFrame):
    """
    带行号的代码编辑器
    支持流式打字机渲染和用户手动编辑
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        # 工具栏
        toolbar = ctk.CTkFrame(self, fg_color="transparent", height=35)
        toolbar.pack(fill="x", padx=5, pady=(5, 0))

        self.status_label = ctk.CTkLabel(
            toolbar, text="📝 就绪",
            font=ctk.CTkFont(size=12),
            text_color="#aaaaaa"
        )
        self.status_label.pack(side="left", padx=5)

        self.copy_btn = ctk.CTkButton(
            toolbar, text="📋 复制", width=70, height=28,
            font=ctk.CTkFont(size=12),
            fg_color="#333333", hover_color="#555555",
            command=self._copy_code
        )
        self.copy_btn.pack(side="right", padx=2)

        self.clear_btn = ctk.CTkButton(
            toolbar, text="🗑 清空", width=70, height=28,
            font=ctk.CTkFont(size=12),
            fg_color="#333333", hover_color="#555555",
            command=self.clear
        )
        self.clear_btn.pack(side="right", padx=2)

        # 编辑器区域（带行号）
        editor_frame = ctk.CTkFrame(self, fg_color="transparent")
        editor_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # 行号显示（用 tk.Text 实现精确的 yview 同步）
        self.line_numbers = tk.Text(
            editor_frame,
            width=5,
            font=("Consolas", 13),
            fg="#666666",
            bg="#1a1a2e",
            relief="flat",
            state="disabled",
            wrap="none",
            highlightthickness=0,
            takefocus=0,
            cursor="arrow"
        )
        self.line_numbers.pack(side="left", fill="y", padx=(0, 2))

        # 代码编辑框（用 tk.Text 实现精确滚动同步）
        self.textbox = tk.Text(
            editor_frame,
            font=("Consolas", 13),
            fg="#e0e0e0",
            bg="#1a1a2e",
            insertbackground="#e0e0e0",
            relief="flat",
            wrap="word",
            highlightthickness=0,
            undo=True
        )
        self.textbox.pack(side="left", fill="both", expand=True)

        # 滚动条
        scrollbar = ctk.CTkScrollbar(editor_frame, command=self._on_scroll)
        scrollbar.pack(side="right", fill="y")
        self.textbox.configure(yscrollcommand=lambda *args: self._on_text_scroll(args, scrollbar))
        self.line_numbers.configure(yscrollcommand=lambda *args: None)

        # 绑定事件
        self.textbox.bind("<KeyRelease>", lambda e: self._update_line_numbers())
        self.textbox.bind("<MouseWheel>", self._on_mousewheel)
        self.textbox.bind("<<Modified>>", self._on_modified)

        self._last_line_count = 0
        self._stream_buffer = ""

    def _on_scroll(self, *args):
        """滚动条回调：同步滚动代码和行号"""
        self.textbox.yview(*args)
        self.line_numbers.yview(*args)

    def _on_text_scroll(self, args, scrollbar):
        """代码框滚动时同步滚动条和行号"""
        scrollbar.set(*args)
        self.line_numbers.yview_moveto(args[0])

    def _on_mousewheel(self, event):
        """鼠标滚轮同步"""
        delta = -1 * (event.delta // 120) if event.delta else 0
        self.textbox.yview_scroll(delta, "units")
        self.line_numbers.yview_scroll(delta, "units")
        return "break"

    def _on_modified(self, event=None):
        """内容修改时更新行号"""
        self.textbox.edit_modified(False)
        self._update_line_numbers()

    def _update_line_numbers(self):
        """更新行号显示"""
        content = self.textbox.get("1.0", "end-1c")
        line_count = content.count('\n') + 1

        # 只在行数变化时重绘，避免频繁刷新
        if line_count == self._last_line_count:
            return
        self._last_line_count = line_count

        line_text = '\n'.join(str(i) for i in range(1, line_count + 1)) + '\n'
        self.line_numbers.configure(state="normal")
        self.line_numbers.delete("1.0", "end")
        self.line_numbers.insert("1.0", line_text)
        self.line_numbers.configure(state="disabled")

    def set_status(self, text: str, color: str = "#aaaaaa"):
        """设置状态标签"""
        self.status_label.configure(text=text, text_color=color)

    def start_stream(self):
        """开始流式写入模式"""
        self._stream_buffer = ""
        self._last_line_count = 0
        self.textbox.delete("1.0", "end")
        self._update_line_numbers()
        self.set_status("🔥 AI 正在生成代码...", "#ff6644")

    def append_stream(self, text: str):
        """流式追加文本"""
        self._stream_buffer += text
        self.textbox.configure(state="normal")
        self.textbox.insert("end", text)
        self.textbox.see("end")
        self._update_line_numbers()

    def finish_stream(self, full_code: str = None):
        """流式写入完成"""
        if full_code:
            self.set_content(full_code)
        self.set_status("✅ 代码生成完成", "#00ff88")

    def set_content(self, text: str):
        """设置全部内容"""
        self._last_line_count = 0
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", text)
        self._update_line_numbers()

    def get_content(self) -> str:
        """获取全部内容"""
        return self.textbox.get("1.0", "end-1c")

    def clear(self):
        """清空编辑器"""
        self.textbox.delete("1.0", "end")
        self._last_line_count = 0
        self._update_line_numbers()

    def _copy_code(self):
        """复制代码到剪贴板"""
        code = self.get_content()
        self.clipboard_clear()
        self.clipboard_append(code)
        self.set_status("📋 已复制到剪贴板", "#44aaff")
        self.after(2000, lambda: self.set_status("📝 就绪"))


class ThreatCard(ctk.CTkFrame):
    """
    单条威胁情报卡片
    支持 CVE 公告 和 GitHub/SANS 仓库两种样式
    """

    def __init__(self, master, data: dict, card_type: str = "cve",
                 on_reproduce=None, on_open_url=None, **kwargs):
        super().__init__(master, fg_color="#161b22", corner_radius=8, **kwargs)

        self.data = data
        self.card_type = card_type
        self.on_reproduce = on_reproduce
        self.on_open_url = on_open_url

        self._build_card()

    def _build_card(self):
        # ── 顶部色条 ──
        color_bar = ctk.CTkFrame(self, height=3, fg_color=self._get_accent_color())
        color_bar.pack(fill="x", padx=0, pady=0)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8, pady=(4, 6))

        # ── 标题行 ──
        header = ctk.CTkFrame(body, fg_color="transparent")
        header.pack(fill="x", pady=(0, 3))

        title_text, badge_text = self._get_header_info()
        ctk.CTkLabel(
            header, text=title_text,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e0e0e0", anchor="w",
            wraplength=220
        ).pack(side="left", fill="x", expand=True)

        if badge_text:
            ctk.CTkLabel(
                header, text=badge_text,
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color="#0d1117",
                fg_color=self._get_accent_color(),
                corner_radius=4, width=60, height=20
            ).pack(side="right", padx=(4, 0))

        # ── 描述 ──
        desc = self.data.get("desc", "")[:120]
        if desc:
            ctk.CTkLabel(
                body, text=desc,
                font=ctk.CTkFont(size=11),
                text_color="#999999", anchor="w",
                wraplength=280, justify="left"
            ).pack(fill="x", pady=(0, 3))

        # ── 底部：日期/来源 + 操作按钮 ──
        footer = ctk.CTkFrame(body, fg_color="transparent")
        footer.pack(fill="x")

        meta_text = self._get_meta_text()
        ctk.CTkLabel(
            footer, text=meta_text,
            font=ctk.CTkFont(size=10),
            text_color="#666666", anchor="w"
        ).pack(side="left")

        # 按钮区
        btn_area = ctk.CTkFrame(footer, fg_color="transparent")
        btn_area.pack(side="right")

        url = self.data.get("url", "")
        if url:
            ctk.CTkButton(
                btn_area, text="🔗 原文", width=55, height=22,
                font=ctk.CTkFont(size=10),
                fg_color="#30363d", hover_color="#484f58",
                text_color="#79c0ff",
                command=lambda: self._on_open_url()
            ).pack(side="right", padx=(3, 0))

        ctk.CTkButton(
            btn_area, text="🚀 复现", width=55, height=22,
            font=ctk.CTkFont(size=10),
            fg_color="#1a3a2a", hover_color="#245a3a",
            text_color="#3fb950",
            command=lambda: self._on_reproduce()
        ).pack(side="right")

    def _get_accent_color(self) -> str:
        if self.card_type == "cve":
            sev = str(self.data.get("severity", ""))
            try:
                score = float(sev)
                if score >= 9: return "#ff4444"
                if score >= 7: return "#ff8800"
                if score >= 4: return "#ffcc00"
                return "#44bb44"
            except (ValueError, TypeError):
                return "#ff6644"
        return "#00ccff"

    def _get_header_info(self):
        if self.card_type == "cve":
            cve_id = self.data.get("cve", "Unknown")
            badge = str(self.data.get("severity", ""))
            if badge and badge != "N/A":
                badge = f"CVSS {badge}"
            else:
                badge = ""
            return cve_id, badge
        else:
            name = self.data.get("name", "Unknown")
            stars = self.data.get("stars", 0)
            badge = f"⭐{stars}" if stars > 0 else ""
            return name, badge

    def _get_meta_text(self) -> str:
        if self.card_type == "cve":
            date = self.data.get("date", "")
            return f"📅 {date}" if date else ""
        else:
            source = self.data.get("source", "")
            return f"📡 {source}" if source else ""

    def _on_reproduce(self):
        if self.on_reproduce:
            self.on_reproduce(self.data)

    def _on_open_url(self):
        url = self.data.get("url", "")
        if url and self.on_open_url:
            self.on_open_url(url)


class HotListPanel(ctk.CTkFrame):
    """
    情报热点列表面板（卡片式）
    每条情报渲染为独立的 ThreatCard 卡片
    """

    def __init__(self, master, on_reproduce=None, on_open_url=None, **kwargs):
        super().__init__(master, **kwargs)

        self.on_reproduce = on_reproduce
        self.on_open_url = on_open_url
        self._cards = []

        # 标题
        title_bar = ctk.CTkFrame(self, fg_color="transparent")
        title_bar.pack(fill="x", padx=5, pady=(5, 0))

        ctk.CTkLabel(
            title_bar, text="  🌐 安全情报中心",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#00ccff", anchor="w"
        ).pack(side="left")

        self.loading_label = ctk.CTkLabel(
            title_bar, text="",
            font=ctk.CTkFont(size=11),
            text_color="#888888"
        )
        self.loading_label.pack(side="right", padx=5)

        # 可滚动卡片容器
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="#0d1117",
            scrollbar_button_color="#30363d",
            scrollbar_button_hover_color="#484f58"
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # 底部控制栏
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=5, pady=(0, 5))

        self.refresh_btn = ctk.CTkButton(
            btn_frame, text="🔄 手动刷新", width=100, height=28,
            font=ctk.CTkFont(size=12),
            fg_color="#1a5276", hover_color="#2980b9"
        )
        self.refresh_btn.pack(side="left", padx=2)

        self.auto_refresh_var = tk.BooleanVar(value=False)
        self.auto_refresh_cb = ctk.CTkCheckBox(
            btn_frame, text="自动刷新", width=100, height=28,
            font=ctk.CTkFont(size=12),
            variable=self.auto_refresh_var,
            fg_color="#1a5276", hover_color="#2980b9"
        )
        self.auto_refresh_cb.pack(side="left", padx=10)

        self.count_label = ctk.CTkLabel(
            btn_frame, text="",
            font=ctk.CTkFont(size=10),
            text_color="#666666"
        )
        self.count_label.pack(side="right", padx=5)

    def load_cards(self, repos: list, cves: list):
        """加载情报数据，渲染为卡片"""
        self.clear()
        total = 0

        # ── CVE 卡片 ──
        if cves and not (len(cves) == 1 and cves[0].get("cve", "").startswith("[")):
            section = ctk.CTkLabel(
                self.scroll_frame,
                text="  🔴 最新漏洞公告",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#ff6644", anchor="w"
            )
            section.pack(fill="x", padx=2, pady=(4, 2))
            self._cards.append(section)

            for cve_data in cves[:8]:
                card = ThreatCard(
                    self.scroll_frame, data=cve_data, card_type="cve",
                    on_reproduce=self.on_reproduce,
                    on_open_url=self.on_open_url
                )
                card.pack(fill="x", padx=2, pady=3)
                self._cards.append(card)
                total += 1

        # ── GitHub / SANS 卡片 ──
        if repos and not (len(repos) == 1 and repos[0].get("name", "").startswith("[")):
            is_sans = repos[0].get("source") != "GitHub"
            section_title = "  💥 全球实时威胁事件" if is_sans else "  ⭐ GitHub 热门 PoC"
            section = ctk.CTkLabel(
                self.scroll_frame,
                text=section_title,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#00ccff", anchor="w"
            )
            section.pack(fill="x", padx=2, pady=(8, 2))
            self._cards.append(section)

            for repo_data in repos[:8]:
                card = ThreatCard(
                    self.scroll_frame, data=repo_data, card_type="repo",
                    on_reproduce=self.on_reproduce,
                    on_open_url=self.on_open_url
                )
                card.pack(fill="x", padx=2, pady=3)
                self._cards.append(card)
                total += 1

        self.count_label.configure(text=f"共 {total} 条情报")

    def set_loading(self, loading: bool):
        if loading:
            self.loading_label.configure(text="⏳ 抓取中...")
        else:
            self.loading_label.configure(text="")

    def clear(self):
        for widget in self._cards:
            widget.destroy()
        self._cards.clear()
        self.count_label.configure(text="")


class StatusBar(ctk.CTkFrame):
    """
    底部状态栏
    显示 API 状态、代理、线程池等信息
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, height=30, **kwargs)

        self.api_label = ctk.CTkLabel(
            self, text="  API: 未配置",
            font=ctk.CTkFont(size=11),
            text_color="#888888", anchor="w"
        )
        self.api_label.pack(side="left", padx=10)

        self.proxy_label = ctk.CTkLabel(
            self, text="代理: 未启用",
            font=ctk.CTkFont(size=11),
            text_color="#888888"
        )
        self.proxy_label.pack(side="left", padx=20)

        self.thread_label = ctk.CTkLabel(
            self, text="线程池: 空闲",
            font=ctk.CTkFont(size=11),
            text_color="#888888"
        )
        self.thread_label.pack(side="left", padx=20)

        self.status_label = ctk.CTkLabel(
            self, text="就绪  ",
            font=ctk.CTkFont(size=11),
            text_color="#00ff88", anchor="e"
        )
        self.status_label.pack(side="right", padx=10)

    def set_api_status(self, text: str, connected: bool = False):
        """设置 API 状态"""
        color = "#00ff88" if connected else "#ff6644"
        self.api_label.configure(text=f"  API: {text}", text_color=color)

    def set_proxy_status(self, text: str):
        """设置代理状态"""
        self.proxy_label.configure(text=f"代理: {text}")

    def set_thread_status(self, text: str):
        """设置线程池状态"""
        self.thread_label.configure(text=f"线程池: {text}")

    def set_status(self, text: str, color: str = "#00ff88"):
        """设置右侧状态"""
        self.status_label.configure(text=f"{text}  ", text_color=color)
