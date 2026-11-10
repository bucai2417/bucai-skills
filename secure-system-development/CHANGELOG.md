# Changelog

## 1.2.1 — 2026-11-05

修复平台上架解析失败。

### 修复

- `SKILL.md` frontmatter 补充平台必填的 `display_name`（安全系统开发规范）与 `display_name_en`（Secure System Development）
- `tools/package_skill.py` 校验新增这两个字段（缺失或超过 64 字符即报错），避免再次上传后才发现

### 变更

- `.codex-plugin/plugin.json` 版本同步为 1.2.1

## 1.2.0 — 2026-11-05

上架平台适配。

### 新增

- `assets/icon-512.png` — 512×512 应用图标（52 KB），盾牌 + `</>` 几何设计
- `tools/make_icon.py` — 程序化生成图标，无需外部服务；可复现、可改色
- `agents/openai.yaml` 增加 `icon_small` / `icon_large` / `brand_color`

### 变更

- `SKILL.md` frontmatter 补齐平台必填字段：顶层 `version`、`author`、`description_zh`、`description_en`
- `description` 收敛为核心触发条件（≤1024 字符），长尾关键词移入正文新增的「何时使用（触发场景）」章节
- `tools/package_skill.py` 校验四条描述字段与版本格式；平台包自动剔除 `.codex-plugin/`、`agents/`、`.gitignore`、`.gitattributes`
- `.codex-plugin/plugin.json` 版本同步为 1.2.0，补齐 homepage / repository / author
- `README.md` 新增「上架 Skill 平台」章节与图标；修正 `~/.claud/skills/` 路径大小写并补充 Windows 说明

## 1.1.0 — 2026-11-04

工程化与发布自动化版本。

### 新增

- `.github/workflows/ci.yml` — Push / PR 自动校验：frontmatter 校验、扫描器自测、自身红线扫描、打包并上传 artifact
- `.github/workflows/release.yml` — 推送 `v*` tag 自动发布：校验 tag 与 `metadata.version` 一致 → 自测 → 打包 → 创建 GitHub Release 并附 `.skill` 与 `.zip`
- `tests/test_scanner_rules.py` — 扫描器自测：断言 13 条核心规则命中、误报抑制生效、干净目录退出码为 0
- `tools/package_skill.py` — 打包工具移入仓库；新增 `--print-version`，`--src` 默认 `.`
- `docs/publishing.md` — 发布与分发指南移入仓库

### 变更

- 版本号唯一来源统一为 `SKILL.md` 的 `metadata.version`，打包与 CI/Release 均从此读取
- `README.md` 重写：新增「它解决什么问题」（10 个真实事故场景对照）、「它有什么用」（按阶段说明）、覆盖范围表、版本与发布流程
- 打包排除目录新增 `.github/`、`tools/`、`docs/`、`tests/`，发布包只含 agent 需要的文件

## 1.0.0 — 2026-11-04

首个通用发布版本。可在 Claud / Claud Code、Codex / OpenAI 插件、以及任意读取 Markdown 的 agent 中使用。

### 主文件

- `SKILL.md`：中英双语触发描述；场景判定表（公开站点 / 登录后产品 / 管理后台 / 内部系统 / 纯 API）；9 组红线清单；四阶段流程（设计 → 实现 → 上线评审 → 运行时缓解）。
- 移除 SKILL.md 内写死的内部域名，改为指向 `references/internal-policy.example.md` 的可选模板。

### references（12 个）

既有 7 个：

- `auth-and-session.md` — 密码存储、防爆破、防枚举、会话、JWT、2FA、重置、CSRF、越权、管理后台
- `web-vulnerability-prevention.md` — 输入校验、SQLi、XSS、CSRF、SSRF、路径穿越、上传、命令执行、反序列化、开放重定向、响应头、日志、供应链、API 特有风险
- `business-logic-and-race-conditions.md` — 信任边界、金额支付、优惠券、库存、状态机、TOCTOU、限购、账号业务、导出滥用、邀请防刷、风控
- `database-concurrency.md` — 表结构、索引、查询模式、事务、并发写、幂等、缓存、连接池、读写分离、分库分表、一致性、运维
- `async-architecture.md` — 同步边界、超时、重试、队列、Outbox、限流背压、分布式锁、事件循环、优雅停机、可观测、前端配合
- `http-routing-cors-seo.md` — 适用性矩阵、404、状态码、CORS、响应头、URL 规范化、缓存、公开站点收录清单、后台禁止收录、网关加固
- `operations-and-secrets.md` — 密钥、配置多环境、CI/CD、容器云、邮件安全、日志审计、数据生命周期、监控应急

新增 5 个：

- `api-integrity-and-tampering.md` — 抓包改包威胁模型、TLS 与证书固定、请求签名（HMAC + timestamp + nonce + body hash）、服务端重算、响应签名、防重放、幂等键、客户端加固边界、调试日志红线、常见错误
- `ai-llm-security.md` — 提示注入（直接/间接）、工具调用 schema 与最小权限、RAG 投毒与租户隔离、模型输出处理、密钥与供应商、日志隐私、成本滥用、Agent 自主执行
- `mobile-and-miniprogram.md` — 本地存储、传输与证书固定、WebView、root 检测定位、小程序 `code2session` 与 `session_key` 红线、小程序其他风险、设备风控、发布运维
- `compliance-mapping.md` — OWASP Top 10 (2021) 与 ASVS 4.0.3 映射、等保 2.0 三级技术要点、PIPL/数据安全法/网络安全法要点
- `internal-policy.example.md` — 资产保护条款通用模板（占位域名，不含真实地址）

### scripts

- `scan_redlines.py` — 纯 Python 3 标准库，无第三方依赖。18 类规则：SQL001/SQL004/SQL005（拼接 SQL 与模板插值）、XSS001（HTML sink）、XSS002（eval/new Function）、TEMPLATE001（SSTI）、CORS001（通配）、CORS002（反射 Origin）、ROUTE001-003（软 404）、SECRET001-006（硬编码密钥）、CMD001（命令执行）、NET001（关闭证书校验）、DEBUG001（调试开启）、UPLOAD001（上传路径）、NOSQL001（操作符注入）、CRYPTO001（MD5/SHA1 存密码）、CRYPTO002（Math.random 生成凭证）、LOG001（敏感字段入日志）、CMP001（`==` 比较签名）。
  - 输出格式：`--format text|json|sarif`（SARIF 2.1.0，可接 CI）
  - 门禁：`--fail-on none|low|medium|high`；过滤：`--min-severity`、`--exclude`
  - 误报抑制：行内 `redline: ignore` 或 `redline: ignore RULE_ID[,RULE_ID]`
  - 文档排除：`--code-only` 跳过 `.md/.mdx/.rst/.txt/.adoc`
  - 强制 UTF-8 输出，Windows GBK 控制台下 SARIF/JSON 仍可被 CI 解析

### assets

- `threat-model-template.md` — 项目信息、数据流图、资产权限、STRIDE 表、9 项必填结论、评审结论
- `review-checklist.md` — 按 A 公开站点 / B 登录后产品 / C 管理后台 / D 内部系统 / E 纯 API 分组，另加通用项

### 发布元数据

- `README.md`（多 agent 安装说明）、`AGENTS.md`（非 skill-aware agent 入口）、`LICENSE`（MIT）、`CHANGELOG.md`、`.codex-plugin/plugin.json`、`agents/openai.yaml`

### 验证记录

- `quick_validate.py`（官方校验器）：`Skill is valid!`
- `description` 长度：726 字符（上限 1024）
- `python scripts/scan_redlines.py --help`：正常退出
- 在含 13 类问题的样例目录上运行：`high=9 medium=4 low=0 total=13`，13 个规则 ID 全部命中
- `--format sarif`：输出可被 `json.load` 解析，`version=2.1.0`，results=13
- `--format json`：输出可解析
- `--fail-on none`：退出码 0；干净目录 `--fail-on high`：退出码 0；含高危：退出码 1
- 行内抑制：`redline: ignore`（全抑制）、`redline: ignore XSS002`（按 ID 抑制）验证通过
- `--code-only` 扫描 skill 自身：0 命中（规则正则字面量已加抑制标记）
- `grep -ri` 内部域名：0 命中（仅 CHANGELOG 记录该验证动作本身）
- 中文 fix 路径在 GBK 控制台下显示乱码（已知限制，JSON/SARIF 与文件内容不受影响）
