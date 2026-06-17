#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI-POCStudio: 智能漏洞复现与 POC 调试终端
主程序入口
"""

import json
import os
import sys
import tkinter as tk
from tkinter import messagebox

# 将项目根目录加入 Python 路径
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)


def load_config() -> dict:
    """加载配置文件"""
    config_path = os.path.join(PROJECT_DIR, "config", "settings.json")
    default_config = {
        "ai": {
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "",
            "model": "deepseek-chat",
            "max_tokens": 4096,
            "temperature": 0.3
        },
        "proxy": {
            "enabled": False,
            "http": "http://127.0.0.1:7890",
            "https": "http://127.0.0.1:7890"
        },
        "crawler": {
            "github_token": "",
            "refresh_interval": 300
        },
        "theme": "dark"
    }

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            # 合并默认值（防止缺少字段）
            for key in default_config:
                if key not in config:
                    config[key] = default_config[key]
                elif isinstance(default_config[key], dict):
                    for sub_key in default_config[key]:
                        if sub_key not in config[key]:
                            config[key][sub_key] = default_config[key][sub_key]
            return config
        except Exception as e:
            print(f"[!] 配置文件加载失败: {e}，使用默认配置")
            return default_config
    else:
        # 创建默认配置文件
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        return default_config


def show_disclaimer():
    """显示免责声明弹窗"""
    root = tk.Tk()
    root.withdraw()

    disclaimer_text = (
        "⚠️ 免责声明 ⚠️\n\n"
        "AI-POCStudio 是一款面向网络安全研究人员的\n"
        "智能漏洞复现与 POC 调试工具。\n\n"
        "本工具仅用于合法授权的网络安全自查与教学研究。\n\n"
        "使用者应严格遵守当地法律法规，\n"
        "因违规使用导致的任何法律纠纷由使用者自行承担。\n\n"
        "开发者不对因使用本工具造成的任何损害承担责任。\n\n"
        "点击 [同意] 继续使用，点击 [退出] 关闭程序。"
    )

    result = messagebox.askokcancel("AI-POCStudio — 用户许可协议", disclaimer_text)
    root.destroy()
    return result


def main():
    """主函数"""
    # 1. 显示免责声明
    if not show_disclaimer():
        sys.exit(0)

    # 2. 加载配置
    config = load_config()

    # 3. 检查依赖
    try:
        import customtkinter
        import requests
        import trafilatura
        import openai
    except ImportError as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "依赖缺失",
            f"缺少必要的 Python 库: {e}\n\n"
            f"请执行: pip install -r requirements.txt"
        )
        sys.exit(1)

    # 4. 启动主窗口
    from gui.main_window import MainWindow
    app = MainWindow(config)
    app.mainloop()


if __name__ == "__main__":
    main()
