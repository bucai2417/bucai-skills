# bucai-skills

![skills](https://img.shields.io/badge/skills-2-0EA5E9)
![license](https://img.shields.io/badge/license-see%20below-blue)
![ci](https://github.com/bucai2417/bucai-skills/actions/workflows/ci.yml/badge.svg)

> 一组可直接装进 AI agent 的技能包（skills）。
> 每个目录都是一个独立 skill：`SKILL.md` 定义触发条件与执行规范，`references/` 放深度资料，
> `scripts/` 放可运行工具。装进 agent 后，描述任务即可自动触发，无需手动翻文档。

---

## 技能目录

| Skill | 分类 | 版本 | 一句话说明 |
|---|---|---|---|
| [multi-bot-adapter](multi-bot-adapter/) | 渠道通信 | 1.0.0 | QQ 官方 Bot 与微信 wxclaw / iLink Bot 的扫码登录、收发消息、富媒体、语音与协议排错 |
| [secure-system-development](secure-system-development/) | 安全与工程 | 1.2.1 | 网站、后端与 API 的安全红线：认证、注入、并发、异步、防篡改、CORS、404 与收录 |

两个 skill 都支持中英双语描述，可被 Claud / Claud Code、Codex 以及通用 Agent Skills 加载。

---

## 快速开始

### 方式一：安装脚本（推荐）

```bash
git clone https://github.com/bucai2417/bucai-skills.git
cd bucai-skills

./install.sh                          # 安装全部 skill 到 ~/.Claud/skills
./install.sh multi-bot-adapter        # 只装指定 skill
./install.sh --target codex           # 装到 ~/.codex/skills
./install.sh --list                   # 查看仓库里有哪些 skill
```

Windows PowerShell：

```powershell
git clone https://github.com/bucai2417/bucai-skills.git
cd bucai-skills

.\install.ps1
.\install.ps1 multi-bot-adapter
.\install.ps1 -Target codex
```

脚本只复制 skill 目录，自动排除 `dist/`、`.git/`、`__pycache__/`。目标目录已存在时会拒绝覆盖，
确认要升级时加 `--force`（PowerShell 为 `-Force`）。

### 方式二：手动复制

```bash
git clone --depth 1 https://github.com/bucai2417/bucai-skills.git /tmp/bucai-skills
cp -r /tmp/bucai-skills/multi-bot-adapter ~/.Claud/skills/
```

确认目标目录里直接看到 `SKILL.md`：

```
~/.Claud/skills/multi-bot-adapter/SKILL.md
```

### 方式三：下载单个技能包

到 [Releases](https://github.com/bucai2417/bucai-skills/releases) 下载对应 tag 的
`.skill`（Claud / Claud Code）或 `.zip`（通用）。`.skill` 本质是 zip，解压后
`SKILL.md` 必须在第一层。

### 各 agent 的安装位置

| Agent | 用户级目录 | 项目级目录 |
|---|---|---|
| Claud / Claud Code | `~/.Claud/skills/<name>/` | `<项目>/.Claud/skills/<name>/` |
| Codex | `~/.codex/skills/<name>/` | — |
| 通用 Agent Skills | `~/.agents/skills/<name>/` | — |
| cc-switch | `~/.cc-switch/skills/<name>/` | — |

> Windows 上 `~` 是 `C:\Users\<用户名>\`。Claud 目录名可能是 `.Claud` 或 `.claud`，
> 以本机实际存在的为准；`install.sh` 默认使用 `~/.Claud/skills`，可用 `--dest` 指定任意路径。

---

## 使用方法

安装后重启 agent 会话，直接描述任务即可触发。也可以显式点名：

```text
$multi-bot-adapter 按适配器契约接入这个新渠道，并给出测试清单
$secure-system-development 按红线清单检查这个登录接口和建表语句
```

### multi-bot-adapter

**什么时候会自动触发**：给框架新增 QQ / 微信消息渠道，实现扫码登录、AppID/ClientSecret 或
Bot Token 认证、WebSocket 网关或长轮询收消息、文本/图片/文件/语音收发、管理员命令、定时推送，
或排查 `-14 session timeout`、401、`upload_param` 为空、AES 媒体乱码、重复回复等协议问题。

**示例请求**：

- 「给这个 agent 框架接入 QQ 官方机器人，支持群聊和私聊」
- 「微信 wxclaw 一直 -14，帮我核对请求头」
- 「QQ 发语音失败时改成发文件并补文本」
- 「照着现有渠道实现第三个平台，复用会话和产物能力」

完整说明见 [multi-bot-adapter/README.md](multi-bot-adapter/README.md)。

### secure-system-development

**什么时候会自动触发**：写或评审网站、后端、API、登录注册、权限、数据库表、支付与优惠券、
缓存、消息队列、上传、CORS、nginx/SPA 路由、部署配置，或讨论注入、XSS、SSRF、越权、
爆破、重放、防抓包改包、SEO 收录策略时。

**示例请求**：

- 「检查这个登录接口有没有爆破和账号枚举风险」
- 「下单扣库存这段并发安全吗」
- 「这个 SPA 的 404 和 CORS 配置有问题吗」
- 「跑一遍红线扫描，把高危项修掉」

它自带 18 条规则的可执行扫描器：

```bash
python secure-system-development/scripts/scan_redlines.py <目标目录> --format text
python secure-system-development/scripts/scan_redlines.py <目标目录> --fail-on high
```

完整说明见 [secure-system-development/README.md](secure-system-development/README.md)。

---

## 仓库结构

```text
bucai-skills/
├── README.md                        # 本文件：技能目录、安装、发布规范
├── LICENSE                          # 仓库级 MIT（各 skill 保留自己的许可证）
├── install.sh                       # macOS / Linux / Git Bash 安装脚本
├── install.ps1                      # Windows PowerShell 安装脚本
├── tools/package_skill.py           # 仓库统一打包/校验脚本
├── .github/workflows/
│   ├── ci.yml                       # 校验 + 打包全部 skill
│   └── release.yml                  # 按 tag 打包单个 skill 并发 Release
├── multi-bot-adapter/               # skill 1：多渠道机器人适配器
│   ├── SKILL.md
│   ├── README.md
│   ├── CHANGELOG.md
│   ├── LICENSE                      # Apache-2.0
│   ├── agents/openai.yaml
│   ├── .codex-plugin/plugin.json
│   ├── assets/                      # 图标
│   ├── references/                  # QQ / wxclaw 全量协议与契约
│   └── scripts/
└── secure-system-development/       # skill 2：安全系统开发规范
    ├── SKILL.md
    ├── README.md
    ├── CHANGELOG.md
    ├── LICENSE                      # MIT
    ├── agents/openai.yaml
    ├── .codex-plugin/plugin.json
    ├── assets/                      # 图标、威胁建模与评审模板
    ├── references/                  # 11 个专题文档
    ├── scripts/                     # scan_redlines.py
    ├── tests/
    └── tools/
```

---

## 版本与发布

每个 skill 独立使用语义化版本，版本号写在 `SKILL.md` 的 `version` 字段，
并与 `.codex-plugin/plugin.json`、`CHANGELOG.md` 保持一致。

发布标签格式：

```text
<skill-name>-v<version>
```

例如：

```bash
git tag multi-bot-adapter-v1.0.1
git tag secure-system-development-v1.2.2
git push origin --tags
```

`release.yml` 会：

1. 解析 tag，校验 `<skill-name>` 目录存在；
2. 校验 tag 版本与 `SKILL.md` 的 `version` 完全一致，不一致直接失败；
3. 运行该 skill 自己的打包脚本；
4. 创建 GitHub Release，并上传 `.skill`、`.zip` 和 Codex 插件包。

仓库本身不提交 `dist/` 产物，需要的用户从 Releases 下载。

---

## 新增一个 skill

1. 在仓库根目录新建 kebab-case 目录，例如 `my-new-skill/`。
2. 必填文件：

   | 文件 | 作用 |
   |---|---|
   | `SKILL.md` | 入口。YAML frontmatter + 触发条件 + 执行规范 |
   | `README.md` | 给人看的介绍、安装、使用示例 |
   | `CHANGELOG.md` | 版本记录 |
   | `LICENSE` | 许可证（可与仓库根不同） |
   | `agents/openai.yaml` | 平台展示名称、图标、默认提示词 |
   | `.codex-plugin/plugin.json` | Codex 插件元数据，`"skills": "./"` |
   | `assets/icon-512.png` | 展示图标 |

3. `SKILL.md` frontmatter 约束：

   - `name` 必须等于目录名，kebab-case，长度不超过 64；
   - `description` 不超过 1024 字符，不包含 `<` `>`；
   - 中英描述可放在 `description_zh` / `description_en`；
   - `description` 要写清「什么时候用」，否则 agent 不会主动触发。

4. 在根 `README.md` 的「技能目录」表格中补一行。
5. 本地跑 `python tools/package_skill.py --src <name> --check-only`，通过后推送到 `main`。
   `ci.yml` 会再次校验并构建，确认通过后再打 tag 发版。

---

## 本地校验

```bash
# 校验 frontmatter 与包布局
python tools/package_skill.py --src multi-bot-adapter --check-only
python tools/package_skill.py --src secure-system-development --check-only

# 安全 skill 自测 + 红线自查
cd secure-system-development
python tests/test_scanner_rules.py
python scripts/scan_redlines.py . --code-only --exclude tests --fail-on high
```

全部通过再推送。CI 会重复执行同样的检查。仓库级 `tools/package_skill.py` 对两个 skill
通用；新增 skill 也必须能被它校验和打包。

---

## 许可证

- 仓库级文件（README、安装脚本、工作流）：MIT，见 [LICENSE](LICENSE)。
- `multi-bot-adapter/`：Apache License 2.0，见 [其 LICENSE](multi-bot-adapter/LICENSE)。
- `secure-system-development/`：MIT，见 [其 LICENSE](secure-system-development/LICENSE)。

各 skill 目录内的许可证优先于仓库根许可证。

---

## 作者

bucai2417
