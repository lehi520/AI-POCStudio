<div align="center">

# 🛡️ AI-POCStudio

### 智能漏洞复现与 POC 自动化调试终端

**数据绝不上云，内网完全可控**

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20Mac-lightgrey)]()

<br/>

一款面向 **红队 / SRC / 安服人员** 的 AI 驱动漏洞复现与 POC 自动化调试桌面终端。

粘贴漏洞情报 → AI 流式生成 POC → 沙箱一键运行 → 报错自动修复，全流程闭环。

<img src="https://img.shields.io/badge/🔒 Privacy First-100%25 Local-brightgreen?style=for-the-badge" alt="Privacy First" />

</div>

---

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| 🧠 **AI 生成 POC** | 对接 DeepSeek / GPT / Ollama 等 OpenAI 兼容模型，流式输出代码 |
| 🔒 **100% 隐私** | 无缝适配本地 Ollama 离线模型，漏洞资产数据绝不上云 |
| 📡 **CVE 情报监控** | 实时抓取全球最新 CVE 公告，卡片式展示，一键复现 |
| 🔍 **长文智能脱水** | trafilatura + 正则提取 CVE 编号、攻击路径、Payload 等核心要素 |
| ⚡ **沙箱异步执行** | subprocess 隔离运行，实时逐行回显 stdout/stderr |
| 🔧 **AI 自动修复** | 报错 Traceback 自动回传 AI，一键重写修复代码 |
| 🌐 **代理灵活配置** | 境外 CVE 走代理，UI 输入框实时同步，无需重启 |

---

## 📸 工作流演示

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  📡 CVE 情报监控  │ ──→ │  🧠 AI 生成 POC   │ ──→ │  ⚡ 沙箱运行测试  │
│  卡片式展示       │     │  流式打字机渲染    │     │  实时控制台回显   │
│  一键复现         │     │  代码高亮行号      │     │  参数自动注入     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                ↑                         │
                                │    🔧 AI 一键校正        │
                                └─────────────────────────┘
                                     报错自动修复闭环
```

---

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/lehi520/AI-POCStudio.git
cd AI-POCStudio
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置 API

编辑 `config/settings.json`，填入你的 API 配置：

```json
{
  "ai": {
    "base_url": "https://api.deepseek.com/v1",
    "api_key": "sk-xxxxxxxxxxxxxxxx",
    "model": "deepseek-chat"
  },
  "proxy": {
    "enabled": true,
    "http": "http://127.0.0.1:7890",
    "https": "http://127.0.0.1:7890"
  }
}
```

#### 支持的 AI 后端

| 后端 | base_url | 说明 |
|------|----------|------|
| **DeepSeek** | `https://api.deepseek.com/v1` | 国产高性价比代码模型 |
| **GPT-4o** | `https://api.openai.com/v1` | OpenAI 官方接口 |
| **Ollama 本地** | `http://localhost:11434/v1` | 完全离线，零数据外泄 |

> 💡 **内网/断网场景**：使用 Ollama 本地模型，所有数据留在本机，企业安全合规无忧。

### 4. 启动

```bash
python main.py
```


## 📂 项目结构

```
AI-POCStudio/
│
├── core/                      # 核心业务逻辑层（纯 Python，无 UI 依赖）
│   ├── ai_client.py           # 统一 AI API 适配器（流式 Prompt + 自动修复）
│   ├── crawler.py             # CVE 最新公告抓取（CVE 5.0 自愈解析）
│   ├── parser.py              # 网页正文提取 + 长文脱水（CVE/Payload/路径提取）
│   └── executor.py            # subprocess 沙箱（异步执行 + 实时输出捕获）
│
├── gui/                       # 视图层（CustomTkinter 暗黑科技风）
│   ├── components.py          # 自定义组件（卡片、控制台、代码编辑器、状态栏）
│   └── main_window.py         # 三段式主窗口 + 全业务流程串联
│
├── config/
│   └── settings.json          # 动态配置（API 密钥、代理、模型选择）
│
├── assets/
│   └── dark_theme.json        # 暗黑主题配色方案
│
├── main.py                    # 主程序入口（免责声明 + 环境检查 + 启动 GUI）
└── requirements.txt           # 第三方依赖声明
```

---

## ⚙️ 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    GUI 视图层 (CustomTkinter)              │
│  三段式布局 │ 卡片组件 │ 流式控制台 │ 代码编辑器 │ 状态栏    │
├─────────────────────────────────────────────────────────┤
│                   Core 业务逻辑层 (纯 Python)              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ ai_client│ │ crawler  │ │ parser   │ │ executor │  │
│  │ OpenAI   │ │ CVE 抓取  │ │ trafilat │ │ subprocess│ │
│  │ 流式 API  │ │ 自愈解析  │ │ 正则脱水  │ │ 沙箱隔离  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
├─────────────────────────────────────────────────────────┤
│                   外部服务（可选）                          │
│  DeepSeek API │ Ollama 本地 │ CVE.circl.lu │ 目标站点    │
└─────────────────────────────────────────────────────────┘
```

---

## 🔑 关键设计

### 无害化安全约束

System Prompt 硬编码以下规则：

- ✅ 只生成 **验证性** 代码（DNSLog / Echo 回显 / 读取无害文件）
- ❌ **严禁** 反弹 Shell、Webshell、后门植入、DoS 攻击
- ✅ 必须使用 `argparse` 规范参数（`--target` / `--proxy` / `--timeout`）
- ✅ 必须包含完整的 `try-except` 异常处理

### CVE 5.0 自愈解析器

针对 `cve.circl.lu` API 返回的 JSON 结构不一致问题，内置三层降级解析：

1. 标准路径查找（`cveMetadata.cveId`）
2. 根节点键名遍历（`id` / `cve` / `summary`）
3. 终极递归扫描（遍历全树取最长技术文本）

---

## 📋 依赖

| 库 | 用途 |
|----|------|
| `customtkinter` | GUI 框架 |
| `openai` | 统一 AI API 调用（兼容 DeepSeek / Ollama） |
| `requests` | HTTP 请求 |
| `trafilatura` | 网页正文智能提取 |

---

## ⚠️ 免责声明

本工具仅用于 **合法授权的网络安全自查与教学研究**。

使用者应严格遵守当地法律法规，因违规使用导致的任何法律纠纷由使用者自行承担。

---


<div align="center">

**如果这个项目对你有帮助，请给个 ⭐ Star 支持一下！**

</div>
