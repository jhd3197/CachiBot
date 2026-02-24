<div align="center">
  <img src="../assets/hero.png" alt="CachiBot" width="800" />

  <h1>CachiBot</h1>

  <p><strong>铠甲 AI 智能体</strong></p>
  <p><em>可视化。透明。安全。</em></p>

  <p>
    <a href="../README.md">English</a> ·
    <a href="https://codewiki.google/github.com/jhd3197/cachibot">CodeWiki</a> ·
    <a href="README.es.md">Español</a> ·
    中文版 ·
    <a href="README.pt.md">Português</a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Windows" />
    <img src="https://img.shields.io/badge/macOS-000000?style=for-the-badge&logo=apple&logoColor=white" alt="macOS" />
    <img src="https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black" alt="Linux" />
  </p>

  <p>
    <a href="https://pypi.org/project/cachibot"><img src="https://img.shields.io/pypi/v/cachibot.svg" alt="PyPI" /></a>
    <a href="https://pypi.org/project/cachibot"><img src="https://img.shields.io/pypi/dm/cachibot.svg" alt="下载量" /></a>
    <a href="https://github.com/jhd3197/CachiBot/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="许可证" /></a>
    <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python" /></a>
    <a href="https://react.dev"><img src="https://img.shields.io/badge/React-19-61DAFB.svg" alt="React" /></a>
    <a href="https://github.com/jhd3197/CachiBot/stargazers"><img src="https://img.shields.io/github/stars/jhd3197/CachiBot?style=social" alt="Stars" /></a>
    <a href="https://discord.gg/V9bKwYVJ"><img src="https://img.shields.io/discord/1470624345188732992?label=Discord&logo=discord&logoColor=white&color=5865F2" alt="Discord" /></a>
  </p>

  <p>
    一个完全透明的可视化 AI 智能体平台。以委内瑞拉的犰狳（西班牙语：<em>cachicamo</em>）命名——如铠甲般安全、可审计、完全由你掌控。
  </p>

  <p>
    <a href="#安装">安装</a> ·
    <a href="#功能特性">功能特性</a> ·
    <a href="#支持的提供商">提供商</a> ·
    <a href="#安全性">安全性</a> ·
    <a href="#贡献">贡献</a> ·
    <a href="https://discord.gg/V9bKwYVJ">Discord</a>
  </p>

</div>

---

## 为什么选择 CachiBot？

大多数 AI 平台迫使你做出选择：没有自动化的聊天机器人界面、没有对话式 AI 的工作流构建器、或者需要数周才能上线的开发框架。

**CachiBot 三者兼得。** 创建专业机器人、部署到任何消息平台、在协作房间中运行，以及自动化工作流——一切都通过可视化仪表板完成，完全透明地了解你的智能体在做什么。

![arepa-war](https://github.com/user-attachments/assets/5996fc02-0c4c-4a61-a998-f007189494fd)

<p align="center">
  <a href="https://youtu.be/G8JEhkcRxD8">
    <img src="https://img.shields.io/badge/YouTube-观看演示-red?style=for-the-badge&logo=youtube&logoColor=white" alt="在YouTube上观看" />
  </a>
  <a href="https://cachibot.ai/marketplace/rooms/great-arepa-war?utm_source=github&utm_medium=readme&utm_campaign=arepa_war_room">
    <img src="https://img.shields.io/badge/CachiBot-查看房间-blue?style=for-the-badge&logo=google-chrome&logoColor=white" alt="在CachiBot上查看" />
  </a>
  <a href="https://dev.to/juandenis/ai-settles-the-ultimate-venezuelan-vs-colombian-arepa-debate-2ngm">
    <img src="https://img.shields.io/badge/Dev.to-阅读文章-0A0A0A?style=for-the-badge&logo=devdotto&logoColor=white" alt="在Dev.to上阅读" />
  </a>
</p>

## 安装

### Linux / macOS

```bash
curl -fsSL cachibot.ai/install.sh | bash
```

自动配置 Python、虚拟环境和 systemd 服务——一条命令搞定一切。

### Windows

```powershell
irm cachibot.ai/install.ps1 | iex
```

### pip

```bash
pip install cachibot
```

然后启动服务器：

```bash
cachibot server
```

打开 **http://localhost:5870** — 前端已打包并自动提供服务。无需单独的构建步骤。

### Docker

```bash
docker compose up
```

### 桌面应用

从 [GitHub Releases](https://github.com/jhd3197/CachiBot/releases) 下载适合你平台的安装包。提供 NSIS 安装程序（Windows）、DMG（macOS）和 AppImage/DEB/RPM（Linux）。支持自动更新。

### 配置 API 密钥

你可以直接在仪表板界面中配置 API 密钥——无需设置环境变量。只需打开设置面板，在那里添加你的密钥即可。

如果你更喜欢使用环境变量，也同样支持：

```bash
export OPENAI_API_KEY="your-key"       # OpenAI / GPT-4
export ANTHROPIC_API_KEY="your-key"    # Claude
export MOONSHOT_API_KEY="your-key"     # Kimi
# 或者使用本地 Ollama（无需密钥）
```

### 命令行用法

```bash
cachibot server                    # 启动仪表板
cachibot "总结这个项目"              # 运行单个任务
cachibot                           # 交互模式
cachibot --model claude/sonnet     # 覆盖模型
cachibot --workspace ./my-project  # 设置工作空间
cachibot --approve                 # 每个操作都需要批准
cachibot --verbose                 # 显示推理过程
cachibot diagnose                  # 检查安装健康状态
cachibot repair                    # 修复损坏的安装
cachi server                       # 短别名
```

## 功能特性

### 多智能体平台

- **无限专业机器人** — 创建具有自定义系统提示词、按机器人模型路由、能力开关和按提供商隔离 API 密钥的机器人
- **协作房间** — 多个机器人协同运行，支持 9 种响应模式：并行、顺序、链式、路由、辩论、瀑布、接力、共识和访谈
- **机器人市场** — 常见用例的预建机器人和房间模板，可从仪表板安装

### 基于能力的插件系统

每个机器人都有一组能力开关，控制可用的工具。插件根据这些开关动态加载，由 [Tukuy](https://github.com/jhd3197/Tukuy) 驱动：

| 能力 | 工具 |
|------|------|
| 代码执行 | 具有 AST 风险分析的沙箱化 Python |
| 文件操作 | 读取、写入、编辑、列表、信息——限定在工作空间内 |
| Git 操作 | Status、diff、log、commit、branch |
| Shell 访问 | 具有安全限制的 Shell 命令 |
| 网络访问 | 获取 URL、网络搜索、HTTP 请求 |
| 数据操作 | SQLite 查询、zip/tar 压缩 |
| 工作管理 | 任务、待办、作业、函数、调度 |
| 图像生成 | DALL-E、Google Imagen、Stability AI、Grok |
| 音频生成 | OpenAI TTS、ElevenLabs、Whisper 转录 |
| 编程智能体 | 启动 Claude Code、OpenAI Codex 或 Gemini CLI 作为子智能体 |
| 知识库 | 在上传的文档和笔记中进行语义搜索 |
| 自定义指令 | LLM 驱动的指令包（分析、写作、开发） |

### 平台集成

通过内置适配器将机器人部署到 **7 个消息平台**。连接存储加密、服务器重启后自动重连、并进行健康监控：

Telegram · Discord · Slack · Microsoft Teams · WhatsApp · Viber · LINE

### 知识库 & RAG

- 上传文档（PDF、TXT、MD、DOCX）——自动分块和嵌入
- 向量相似性搜索，可配置分块大小、重叠和相关性阈值
- 嵌入提供商：OpenAI、Ollama 或本地 FastEmbed（无需 API 密钥）
- 自由文本笔记作为额外知识来源
- 存储：SQLite 余弦相似性或 PostgreSQL pgvector

### 工作管理与自动化

- **工作项** — 顶级单元，带状态跟踪（待处理、进行中、已完成、失败、已取消、已暂停）
- **任务** — 工作项内的步骤，具有依赖跟踪和自动阻塞/解除阻塞
- **作业** — 后台智能体执行，由作业运行服务管理，通过 WebSocket 实时更新进度
- **待办** — 轻量级清单项目
- **函数** — 可复用的任务模板，具有类型化参数和步骤级依赖
- **调度** — Cron、间隔、一次性或事件触发的函数执行
- **脚本** — Python 脚本，具有版本历史、Monaco 编辑器和独立的执行沙箱

### 语音对话

通过专用语音界面与你的机器人实时进行语音转文本和文本转语音对话。

### OpenAI 兼容 API

CachiBot 暴露 `/v1/chat/completions` 和 `/v1/models` 端点，外部工具如 Cursor 或 VS Code 扩展可以像使用 OpenAI 模型一样使用你的机器人。通过开发者面板的 `cb-*` API 密钥进行认证。支持 SSE 流式传输。

### 安全与控制

- **可视化审批流程** — 在危险操作执行前批准或拒绝
- **沙箱化执行** — Python 在隔离环境中运行，具有基于 AST 的风险评分（安全 / 中等 / 危险）
- **工作空间隔离** — 所有文件访问限定在工作空间内
- **加密凭据** — 平台连接密钥使用 AES 加密存储
- **完整审计追踪** — 每个操作都记录了时间、Token 使用量和成本

### 认证与访问控制

- 基于 JWT 的认证，具有访问令牌和刷新令牌
- 自托管模式，通过设置向导进行本地用户管理
- 用户角色（管理员、用户），具有机器人所有权和基于组的访问控制
- 认证端点的速率限制

## 你能构建什么？

- **客户支持机器人** — 部署到 Telegram，配备文档知识库，自动回答常见问题
- **数据分析房间** — 3 个机器人（SQL 专家 + Python 分析师 + 报告撰写者）协作产出洞察
- **语音助手** — 通过 STT/TTS 与机器人对话，免手动管理任务和提醒
- **内容管线** — 研究机器人 + 写作机器人 + 图像生成器端到端制作博客文章
- **DevOps 智能体** — 监控代码仓库、运行沙箱脚本、按计划发送 Slack 告警
- **编程助手** — 启动 Claude Code 或 Codex 处理复杂编程任务的机器人

## 支持的提供商

CachiBot 使用 [Prompture](https://github.com/jhd3197/Prompture) 进行模型管理和自动发现——设置 API 密钥后，可用模型会自动显示。

| 提供商 | 示例模型 | 环境变量 |
|--------|---------|---------|
| OpenAI | GPT-4o, GPT-4, o1 | `OPENAI_API_KEY` |
| Anthropic | Claude Sonnet, Opus, Haiku | `ANTHROPIC_API_KEY` |
| Moonshot | Kimi K2.5 | `MOONSHOT_API_KEY` |
| Google | Gemini Pro, Flash | `GOOGLE_API_KEY` |
| Groq | Llama 3, Mixtral | `GROQ_API_KEY` |
| Grok / xAI | Grok-2 | `GROK_API_KEY` |
| OpenRouter | OpenRouter 上的任何模型 | `OPENROUTER_API_KEY` |
| Azure OpenAI | GPT-4, GPT-4o | `AZURE_OPENAI_API_KEY` |
| ZhipuAI | GLM-4 | `ZHIPUAI_API_KEY` |
| ModelScope | Qwen | `MODELSCOPE_API_KEY` |
| Stability AI | Stable Diffusion（图像生成） | `STABILITY_API_KEY` |
| ElevenLabs | 语音合成 | `ELEVENLABS_API_KEY` |
| Ollama | 任何本地模型 | *（无需密钥）* |
| LM Studio | 任何本地模型 | *（无需密钥）* |

所有密钥也可以通过仪表板界面配置，无需设置环境变量。

## 安全性

CachiBot 以安全性为核心原则构建。**可见性即是安全性** — AI 智能体最大的风险是不知道它们在做什么。

### 沙箱执行

Python 代码在受限环境中运行：

- **导入限制** — 仅允许安全模块（json、math、datetime 等）
- **路径限制** — 文件访问通过 SecurityContext 限制在工作空间内
- **执行超时** — 超时后终止代码（默认：30 秒）
- **风险分析** — 基于 AST 的评分（安全 / 中等 / 危险），在执行前完成
- **审批流程** — 危险操作需要通过仪表板进行明确批准

### 始终被阻止

无论配置如何，这些操作始终不被允许：`subprocess`、`os.system`、`ctypes`、`socket`、`ssl`、`importlib`、`eval`、`exec`、`pickle`、`marshal`。

## 配置

CachiBot 支持分层配置：环境变量覆盖工作空间 TOML，工作空间 TOML 覆盖用户 `~/.cachibot.toml`，用户配置覆盖默认值。所有选项请参阅 [`cachibot.example.toml`](../cachibot.example.toml)。

关键配置节：`[agent]`（模型、温度、最大迭代次数）、`[sandbox]`（允许的导入、超时）、`[knowledge]`（分块大小、嵌入模型、相似性阈值）、`[coding_agents]`（默认智能体、超时、CLI 路径）、`[database]`（SQLite 或 PostgreSQL URL）、`[auth]`（JWT 设置）。

## 贡献

欢迎贡献！完整指南请参阅 [CONTRIBUTING.md](../CONTRIBUTING.md)。快速开始：

```bash
git clone https://github.com/jhd3197/CachiBot.git
cd CachiBot

# 后端
python -m venv venv && source venv/bin/activate  # Windows 上使用 .\venv\Scripts\activate
pip install -e ".[dev]"

# 前端
cd frontend && npm install && cd ..

# 桌面端（可选 — 仅在开发 Electron 外壳时需要）
cd desktop && npm install && cd ..

# 运行所有服务
bash dev.sh              # Windows 上使用 .\dev.ps1
bash dev.sh desktop      # 包含 Electron
bash dev.sh watch-lint   # lint 监视器（保存时运行 ruff + ESLint）
```

请参阅 [CONTRIBUTING.md](../CONTRIBUTING.md) 了解所有开发脚本模式、项目结构、测试和代码风格指南。

## 社区

<p align="center">
  <a href="https://cachibot.ai">
    <img src="https://img.shields.io/badge/Website-cachibot.ai-blue?style=for-the-badge&logo=google-chrome&logoColor=white" alt="网站" />
  </a>
  <a href="https://discord.gg/V9bKwYVJ">
    <img src="https://img.shields.io/badge/Discord-加入社区-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord" />
  </a>
  <a href="https://github.com/jhd3197/CachiBot/issues">
    <img src="https://img.shields.io/badge/Issues-报告错误-red?style=for-the-badge&logo=github&logoColor=white" alt="Issues" />
  </a>
</p>

## 许可证

MIT 许可证 — 详见 [LICENSE](../LICENSE)。

## 致谢

- 使用 [Prompture](https://github.com/jhd3197/Prompture) 构建，用于结构化 LLM 交互和多模态驱动
- 插件系统由 [Tukuy](https://github.com/jhd3197/Tukuy) 驱动
- 以委内瑞拉的犰狳（西班牙语：*cachicamo*）命名

---

<p align="center">
  用心打造 by <a href="https://juandenis.com">Juan Denis</a>
</p>
