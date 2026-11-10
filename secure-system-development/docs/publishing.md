# 发布与分发指南

说明如何把 `secure-system-development` 发布给其他项目、其他 agent 或公开平台。

## 一、三个概念

| 概念 | 是什么 | 谁能用 |
|---|---|---|
| **skill 目录** | 根目录有 `SKILL.md`（含 YAML frontmatter），可带 `references/`、`scripts/`、`assets/` | 所有支持 skills 的 agent |
| **`.skill` 文件** | 本质是 zip，只是扩展名不同。解压后 `SKILL.md` 必须在**第一层** | Claud / Claud Code 平台安装 |
| **Codex 插件** | 独立布局：`.codex-plugin/plugin.json` + `skills/<名字>/SKILL.md`，`plugin.json` 写 `"skills": "./skills/"` | Codex / OpenAI 插件市场 |

**直接打 zip 能用吗？能，但有三个前提：**

1. 解压后 `SKILL.md` 在**第一层**，不能出现 `xxx/xxx/SKILL.md`。
2. 目标 agent 认识这个 skills 目录（见第二节）。
3. 压缩工具不能丢隐藏目录（`.codex-plugin/`）。部分第三方工具会丢，建议用仓库自带的 `tools/package_skill.py`。

---

## 二、各 agent 的安装位置

| Agent | 用户级目录 | 项目级目录 |
|---|---|---|
| Claud / Claud Code | `~/.Claud/skills/<name>/` | `<项目>/.Claud/skills/<name>/` |
| Codex | `~/.codex/skills/<name>/` | — |
| 通用 Agent Skills | `~/.agents/skills/<name>/` | — |
| cc-switch | `~/.cc-switch/skills/<name>/` | — |

Windows 上 `~` 是 `C:\Users\<用户名>\`。

---

## 三、版本号

版本号只有一个来源：`SKILL.md` 顶层 `version` 字段。

```bash
python tools/package_skill.py --print-version
```

平台还要求顶层 `description`、`description_zh`、`description_en`、`author`，缺失会在"配置技能"这一步解析失败。改版本时同步修改：

1. `SKILL.md` → `metadata.version`
2. `CHANGELOG.md` → 新增一节
3. 提交后打 tag `v<version>` 并推送

tag 与 `metadata.version` 不一致时，release 工作流会直接失败，避免发布错版本。

---

## 四、本地打包

```bash
# 在仓库根目录
python tools/package_skill.py --out dist
```

产出：

```
dist/
├── secure-system-development-<version>.skill   # Claud 平台
├── secure-system-development-<version>.zip     # 通用分发
└── codex-plugin/                               # Codex 插件
    ├── .codex-plugin/plugin.json               # "skills": "./skills/"
    └── skills/secure-system-development/       # 完整 skill
```

只校验不打包：

```bash
python tools/package_skill.py --check-only
```

校验内容：`name` 为 kebab-case 且 ≤64 字符；`description` ≤1024 字符且不含尖括号；`SKILL.md` 位于包根；`references/` 存在。

发布包会自动排除 `.github/`、`tools/`、`docs/`、`tests/`、`dist/`，只保留 agent 需要的文件。

---

## 五、自动发布（GitHub Actions）

本 skill 位于 bucai-skills 仓库，CI 与发布工作流统一放在仓库根目录 `.github/workflows/`。

### CI（每次 push / PR）

根目录 `.github/workflows/ci.yml` 会：

1. 校验全部 skill 的 `SKILL.md`
2. 跑扫描器自测 `tests/test_scanner_rules.py`
3. 用扫描器扫自身（`--code-only --fail-on high`）
4. 打包并上传 artifact

### Release（推送 tag）

```bash
git tag secure-system-development-v1.2.2
git push origin secure-system-development-v1.2.2
```

根目录 `.github/workflows/release.yml` 会：

1. 解析 `<skill>-v<version>` tag，确认目录存在
2. 校验 tag 与 `SKILL.md` 的 `version` 一致
3. 跑自测与自身扫描
4. 打包
5. 创建 GitHub Release，附带 `.skill`、`.zip` 与 Codex 插件包

也可以手动触发：Actions → release → Run workflow，输入 tag。

---

## 六、其他发布渠道

### A. 本机其他 agent

```powershell
copy-item -Recurse -Force ".\secure-system-development" "$env:USERPROFILE\.codex\skills\"
```

```bash
cp -r ./secure-system-development ~/.codex/skills/
```

### B. 给别人项目用（zip）

发 `dist/*.zip`，对方解压到自己的 skills 目录，**确认解压后直接看到 `SKILL.md`**。

只想引用规范而不安装 skill：把 `AGENTS.md` 合并进项目根目录，或直接引用 `SKILL.md`。

### C. Claud skill 平台

上传 `dist/*.skill`。

### D. Codex / OpenAI 插件市场

提交 `dist/codex-plugin/` 整个目录。

---

## 七、发布前检查清单

```bash
python tools/package_skill.py --check-only
python tests/test_scanner_rules.py
python scripts/scan_redlines.py . --code-only --exclude tests --fail-on high
python tools/package_skill.py --out dist
```

全部通过再发布。

---

## 八、常见错误

| 现象 | 原因 | 修复 |
|---|---|---|
| 平台提示 frontmatter 非法 | `description` 超 1024 字符，或含 `<` `>` | 压缩描述，去掉尖括号 |
| 装上后 agent 不触发 | `description` 太笼统 | 描述里写清使用场景，中英关键词都放 |
| 解压后找不到 SKILL.md | 压缩时多套了一层目录 | 用 `tools/package_skill.py` |
| Codex 识别不到 skill | `plugin.json` 的 `"skills"` 指向根目录 | 用 `dist/codex-plugin/` |
| release 工作流失败 | tag 与 `SKILL.md` 的 `version` 不一致 | 改版本号或改 tag |
| 中文输出乱码 | Windows 控制台 GBK | 脚本已强制 UTF-8；用编辑器看文件 |
