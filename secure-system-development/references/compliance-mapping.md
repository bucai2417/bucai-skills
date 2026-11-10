# 合规映射：OWASP / ASVS / 等保 2.0 / PIPL

把本 skill 的规则对到标准清单上，用于评审汇报、等保测评、客户审计。**合规是下限，不是安全上限**：通过 ASVS 不代表系统安全，只代表没有明显遗漏。

## 1. OWASP Top 10 (2021) → 本 skill 章节

| 编号 | 名称 | 对应章节 |
|---|---|---|
| A01 | Broken Access Control | `auth-and-session.md` 第 9、10 节；`web-vulnerability-prevention.md` 第 11 节 |
| A02 | Cryptographic Failures | `auth-and-session.md` 第 1 节；`operations-and-secrets.md` 第 1、7 节 |
| A03 | Injection | `web-vulnerability-prevention.md` 第 1–2、8–9 节；`ai-llm-security.md` 第 5 节 |
| A04 | Insecure Design | `SKILL.md` 阶段一；`business-logic-and-race-conditions.md` |
| A05 | Security Misconfiguration | `http-routing-cors-seo.md` 第 3–4、9 节；`operations-and-secrets.md` 第 2–4 节 |
| A06 | Vulnerable and Outdated Components | `web-vulnerability-prevention.md` 第 14 节；`operations-and-secrets.md` 第 3 节 |
| A07 | Identification and Authentication Failures | `auth-and-session.md` 全文 |
| A08 | Software and Data Integrity Failures | `api-integrity-and-tampering.md`；`async-architecture.md` 第 5 节 |
| A09 | Security Logging and Monitoring Failures | `operations-and-secrets.md` 第 6、8 节 |
| A10 | Server-Side Request Forgery | `web-vulnerability-prevention.md` 第 5 节 |

## 2. OWASP ASVS 4.0.3 关键章节

| 章节 | 主题 | 对应 |
|---|---|---|
| V1 | 架构、设计与威胁建模 | `SKILL.md` 阶段一 + `assets/threat-model-template.md` |
| V2 | 认证 | `auth-and-session.md` 第 1–7 节 |
| V3 | 会话管理 | `auth-and-session.md` 第 4 节 |
| V4 | 访问控制 | `auth-and-session.md` 第 9 节 |
| V5 | 输入校验 | `web-vulnerability-prevention.md` 第 1 节 |
| V6 | 密码学 | `auth-and-session.md` 第 1 节；`operations-and-secrets.md` 第 1 节 |
| V7 | 错误处理与日志 | `web-vulnerability-prevention.md` 第 13 节；`operations-and-secrets.md` 第 6 节 |
| V8 | 数据保护 | `operations-and-secrets.md` 第 7 节 |
| V9 | 通信安全 | `web-vulnerability-prevention.md` 第 12 节；`mobile-and-miniprogram.md` 第 2 节 |
| V10 | 恶意代码 | `web-vulnerability-prevention.md` 第 7–8 节 |
| V11 | 业务逻辑 | `business-logic-and-race-conditions.md` |
| V12 | 文件与资源 | `web-vulnerability-prevention.md` 第 6–7 节 |
| V13 | API 与 Web 服务 | `web-vulnerability-prevention.md` 第 15 节；`api-integrity-and-tampering.md` |
| V14 | 配置 | `http-routing-cors-seo.md` 第 4、9 节；`operations-and-secrets.md` 第 2 节 |

等级建议：L1（基础）、L2（多数系统）、L3（金融/医疗/高敏感）。

## 3. 等保 2.0（GB/T 22239-2019）三级技术要点

| 控制点 | 要求 | 对应 |
|---|---|---|
| 身份鉴别 | 口令复杂度、定期更换、登录失败处理、双因素 | `auth-and-session.md` 第 1、2、6 节 |
| 访问控制 | 最小权限、分离职责、默认账户管理 | `auth-and-session.md` 第 9 节 |
| 安全审计 | 审计覆盖、记录内容、保护与留存（≥6 个月） | `operations-and-secrets.md` 第 6 节 |
| 入侵防范 | 最小安装、漏洞修补、入侵检测 | `SKILL.md` 阶段四；`operations-and-secrets.md` 第 8 节 |
| 恶意代码防范 | 病毒防护、及时更新 | `web-vulnerability-prevention.md` 第 7 节 |
| 数据完整性 | 传输/存储完整性校验 | `api-integrity-and-tampering.md`；`operations-and-secrets.md` 第 7 节 |
| 数据保密性 | 加密传输与存储 | 同上 |
| 数据备份恢复 | 本地备份、异地备份、恢复测试 | `database-concurrency.md` 第 11 节 |
| 剩余信息保护 | 内存/存储中敏感数据清除 | `operations-and-secrets.md` 第 7 节 |
| 个人信息保护 | 最小化收集、访问控制、告知同意 | `operations-and-secrets.md` 第 7 节；第 4 节 |
| 安全管理制度/人员/建设/运维 | 制度、培训、变更管理、应急预案 | `operations-and-secrets.md` 第 8 节 |

## 4. 中国个人信息保护法（PIPL）与数据安全法

| 要求 | 落地 |
|---|---|
| 最小必要原则 | 表单只收必需字段；不用的数据不存 |
| 告知同意 | 隐私政策明示收集目的与范围；敏感信息单独同意 |
| 单独同意场景 | 生物识别、金融账户、行踪轨迹、14 岁以下未成年人 |
| 个人权利 | 查询、复制、更正、删除、可携带；提供入口 |
| 跨境传输 | 需安全评估/标准合同/认证；默认不跨境 |
| 数据分类分级 | 明确敏感等级，差异化保护 |
| 日志留存 | 网络日志 ≥ 6 个月（网络安全法第 21 条） |
| 安全事件通知 | 发生泄露立即补救并通知用户与主管部门 |
| 委托处理 | 与第三方签数据处理协议，明确责任与安全措施 |

## 5. 使用建议

1. **评审汇报**：先跑 `scripts/scan_redlines.py`，再按第 1 节 OWASP 表逐项说明覆盖情况。
2. **等保测评**：用第 3 节表格作为自检清单，每项对应到具体实现位置（代码/配置/文档）。
3. **客户审计**：ASVS 等级 + PIPL 第 4 节，比笼统说「我们很安全」有效得多。
4. **不要做的**：只拿一张 ASVS 勾选表当安全证明；合规不等于没有漏洞。

## 6. 版本说明

- OWASP Top 10 使用 2021 版（当前最新正式版）。
- ASVS 使用 4.0.3。若升级到 5.x，章节编号会变，届时更新本文件。
- 等保引用 GB/T 22239-2019 三级技术要求；二级要求更宽松，四级更严。
