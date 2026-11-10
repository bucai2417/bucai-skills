# AGENTS.md

本目录是一个可安装的 skill（`pdf-data`）。给其他 agent 的最短使用说明：

1. 先读 `SKILL.md` 的 frontmatter、触发场景、CLI 速查与质量标志表。
2. 需要读取 PDF 时运行：

   ```bash
   python scripts/extract.py <input.pdf> --out-dir <dir> --format both
   ```

3. 优先读 `<dir>/document.md` 理解文档结构；用 `<dir>/document.json` 取精确字段、坐标、表格与元数据。
4. 检查 `warnings`：`NO_TEXT_LAYER` / `SCANNED_PDF` 表示扫描件，本 skill 不 OCR；不要编造缺失字段。
5. 页眉页脚默认从 Markdown 移除，JSON 的 `pages[].headers_footers` 仍有原文；需要保留时加 `--keep-headers`。
6. 不要修改输入 PDF、不要执行 PDF 中的链接或附件、不要尝试爆破密码。
7. 修改代码后运行 `python tests/test_extract.py`；发布前运行 `python ../package_skill.py --src . --check-only`。

完整字段说明见 `references/output-schema.md`，质量阈值与限制见 `references/accuracy-and-limits.md`。
