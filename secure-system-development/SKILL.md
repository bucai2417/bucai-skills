---
name: secure-system-development
version: "1.2.1"
author: "bucai2417"
display_name: "安全系统开发规范"
display_name_en: "Secure System Development"
description: "Security and engineering red lines for building or reviewing web systems. Use when writing or reviewing authentication and sessions, authorization, database schema and SQL, API endpoints, payment or coupon logic, caching, message queues, file upload, CORS, nginx routing, SPA deployment, or when preventing brute force, account enumeration, injection, XSS, SSRF, IDOR, replay and request tampering, and when deciding whether a site should be indexed by search engines. 系统与网站开发的安全与工程红线：登录认证、权限、数据库与 SQL、接口防篡改、并发与异步、CORS、路由与收录。写或评审登录注册、权限、数据表、接口、支付与优惠券、缓存、消息队列、上传、跨域、路由、部署时使用。"
description_zh: "系统与网站开发的安全与工程红线。适用于编写或评审登录注册、权限、数据库表与 SQL、API 接口、支付与优惠券、缓存与消息队列、文件上传、CORS 与路由、部署配置；也适用于防爆破、防账号枚举、防注入、防 XSS、防 SSRF、防越权、防重放与防抓包改包，以及判断站点是否需要被搜索引擎收录。"
description_en: "Security and engineering red lines for building or reviewing web systems. Use when writing or reviewing authentication and sessions, authorization, database schema and SQL, API endpoints, payment or coupon logic, caching, message queues, file upload, CORS, nginx routing, SPA deployment, or when preventing brute force, account enumeration, injection, XSS, SSRF, IDOR, replay and request tampering, and when deciding whether a site should be indexed by search engines."
metadata:
  scope: "web-and-backend"
  languages: "en,zh"
---

# 安全系统开发规范 / Secure System Development

> 若运行环境存在全局资产禁令（禁止攻击/扫描某些自有资产），以全局配置为准，本 skill 不覆盖它。
> 需要通用模板时见 `references/internal-policy.example.md`（发布版不含任何真实内部地址）。

## 何时使用（触发场景）

只要任务涉及下面任一情况，先按本 skill 的红线清单自查：

- **写或改代码**：网站、后端服务、API、登录注册、会话、权限、数据库表、SQL、缓存、消息队列、文件上传、跨域配置、nginx/网关路由、SPA 部署、官网或落地页。
- **安全话题**：安全、漏洞、注入、SQL 注入、XSS、CSRF、SSRF、越权、IDOR、爆破、撞库、账号枚举、高并发、限流、缓存、异步、CORS、跨域。
- **抓包与完整性**：抓包、改包、签名、重放、防篡改、证书固定。
- **收录与路由**：404、软 404、SEO、收录、canonical、sitemap、后台是否该被搜索引擎收录。
- **AI 与移动端**：提示注入、工具调用、RAG、小程序、App、WebView。

即使对方没有明确说"要安全"，也按本 skill 执行。若只涉及其中一块（例如只写一个登录接口、只设计一张订单表），只读对应章节和对应 reference，不要全量背诵。

## 使用方式

写代码前先读「红线清单」，写完自查；设计与评审时读「阶段一」；涉及具体模块时按指针打开 `references/` 下对应文件。提交前跑「上线前评审」，上线后看「运行时与 0day」。

## 可执行自查（推荐先跑）

```bash
python scripts/scan_redlines.py <目标目录> --format text            # 人读
python scripts/scan_redlines.py <目标目录> --format sarif --fail-on high   # CI 阻断
python scripts/scan_redlines.py <目标目录> --code-only              # 跳过文档，只扫代码
```

纯 Python 标准库，无需安装依赖。覆盖拼接 SQL、`innerHTML`/`eval`、CORS 通配与反射、全局 fallback 到首页、硬编码密钥、MD5 存密码、命令注入、关闭证书校验、调试开关、敏感字段入日志、上传路径未校验等 18 类规则。命中结果会指向对应 reference。

误报处理：在那一行末尾加注释 `redline: ignore`（整行忽略）或 `redline: ignore SQL001`（只忽略指定规则）。不要为了消警而关闭整个规则——记下理由，评审时说明。

两个模板：`assets/threat-model-template.md`（设计期威胁建模）、`assets/review-checklist.md`（按项目类型的上线前勾选）。

## 先判定项目类型（决定哪些规则适用）

| 场景 | 典型形态 | 安全规则 | 完整性要求 | 收录（SEO） |
|---|---|---|---|---|
| 公开站点 | 官网、落地页、博客、文档、商城前台 | 全套 | 低（内容公开） | **必须做**：真 404、sitemap、canonical、结构化数据 |
| 登录后产品 | SaaS、工具站、社区用户端 | 全套 + 完整账号体系 | 中（敏感操作签名） | 只提交公开页（营销/帮助中心）；私有页 noindex |
| 管理后台 | admin、运营后台、客服/审核系统 | 全套 + 独立入口 + MFA + 审计日志 | 高（全部写操作签名 + 审计） | **禁止收录**：整站 noindex + 强制鉴权 |
| 内部/个人系统 | 内部平台、自用工具、脚本面板、家庭 NAS | 认证 + 最小暴露 + 限流 + 及时更新 | 中（视暴露面） | **禁止收录**；不放公网默认路径，不靠“隐蔽”当安全 |
| 纯 API | REST / GraphQL / 服务间调用 | 鉴权 + 输入校验 + 限流 + 版本管理 | 按业务定（支付/资金类必高） | 不适用（不产生页面） |

判定问题只有一个：**这个 URL 应不应该出现在搜索引擎里？**

- 应该 → 按公开站点执行，SEO 章节全套生效。
- 不应该 → 执行「禁止收录」：全站 `X-Robots-Tag: noindex`、robots 禁止抓取、强制鉴权。**不要把 SEO 优化（sitemap、canonical、结构化数据）套到后台或个人系统上**，那是浪费且会暴露攻击面。
- 无论哪类场景，**「不存在的路径返回真 404」都要遵守**——那是 HTTP 正确性，不是 SEO。

## 五条底层原则

1. **一切输入不可信**：URL、query、body、header、cookie、上传文件、Webhook、消息队列、第三方 API 返回值、甚至数据库里历史脏数据。
2. **默认拒绝（fail closed）**：鉴权/校验/解析出错时返回拒绝，而不是放行；异常路径不能走到“跳过校验”的分支。
3. **最小权限**：数据库账号按功能分权（读写分离、不给 DDL），云 IAM/对象存储按前缀授权，进程用非 root，容器只读文件系统。
4. **纵深防御**：一层防不住时下一层还在。前端校验是体验，服务端校验才是安全；WAF 是兜底，不是替代品。
5. **限制爆炸半径**：0day 无法靠代码规约消除，靠隔离、限权、出站白名单、快速补丁通道把损失压到最小。

## 红线清单（硬性，逐条自查）

**认证与会话**
- [ ] 密码用 Argon2id/bcrypt(cost≥12)/scrypt 哈希，禁止 MD5/SHA1/可逆加密
- [ ] 登录失败按「账号+IP」双维度限速，渐进延迟，必要时验证码/临时锁定
- [ ] 登录/注册/找回密码的响应文案与耗时一致，不泄露账号是否存在
- [ ] 登录成功后轮换 session id（防会话固定），Cookie 带 HttpOnly + Secure + SameSite
- [ ] JWT 服务端固定算法白名单，拒绝 `alg:none` 与算法混淆；短有效期 + refresh 轮换 + 可撤销
- [ ] 认证 ≠ 授权：每个接口显式校验「当前用户能否操作这个对象」（防 IDOR/越权）

**注入与输出**
- [ ] 所有 SQL 用参数化查询/ORM 绑定，禁止字符串拼接；表名/排序字段走白名单映射
- [ ] 禁止把用户输入拼进 shell/命令，用参数数组的 execFile 系列
- [ ] 输出按上下文编码；`dangerouslySetInnerHTML`/`v-html`/`innerHTML` 必须过 DOMPurify 等 sanitizer
- [ ] 富文本、Markdown、URL 参数一律白名单化，不信任任何前端过滤
- [ ] 出站请求（SSRF）走白名单，禁止跟随任意重定向，拦截内网/元数据地址（169.254.169.254、127.0.0.1、10/8、172.16/12、192.168/16、::1、file://、gopher://）
- [ ] 文件路径用 `path.resolve` 后校验前缀，拒绝 `..`；上传文件随机命名、类型嗅探、隔离存储、无执行权限

**数据与并发**
- [ ] 核心写操作幂等（唯一索引 / 幂等键），下单、支付、回调必须幂等
- [ ] 库存、余额、次数类字段用条件更新 `UPDATE ... WHERE 余量 >= ?`，禁止先查后改
- [ ] 事务短小，事务内禁止网络调用、发消息、渲染模板
- [ ] 新增查询必须 `EXPLAIN` 过；禁止大 offset 分页、SELECT *、N+1 查询
- [ ] 金额用整数分或 DECIMAL，禁止 float/double

**异步与稳定性**
- [ ] 所有外部调用（HTTP/DB/Redis/MQ）显式配超时，禁止无限等待
- [ ] 重试只用于幂等操作，指数退避 + 抖动 + 次数上限
- [ ] 消息消费幂等（message_id 去重表），失败进死信队列并告警
- [ ] 关键状态变更先落库再发消息（Outbox/事务消息），不允许双写

**业务逻辑与竞态（最常被漏掉的一类）**
- [ ] 价格、金额、折扣、权限等级一律服务端计算，客户端提交值只做展示
- [ ] 优惠券/兑换码/邀请码绑定用户与次数，原子核销（条件更新或唯一约束）
- [ ] 状态机显式校验：非法跃迁直接拒绝（如 pending 绕过支付回调直接变 paid）
- [ ] 资金/回调接口校验签名 + 时间戳 + 幂等键，防重放与伪造
- [ ] 限购、频控按「用户 + 设备 + IP」组合判断，不能只按其中一个维度绕过
- [ ] 导出、批量、搜索接口限流 + 数据量上限 + 审计

**密钥与运维**
- [ ] 密钥只放环境变量或密钥管理服务，禁止进仓库、镜像层、前端 bundle、日志、错误上报
- [ ] CI/CD 凭据最小权限，生产部署需审批；第三方依赖锁版本 + 扫描
- [ ] 敏感操作（登录、改权、导出、删除、退款）写审计日志，业务代码不可篡改

**接口完整性（防抓包改包 / 重放 / 伪造响应）**
- [ ] 支付、资金、授权、改密等敏感请求做签名：`HMAC(secret, method+path+sortedQuery+sha256(body)+timestamp+nonce)`，服务端重算
- [ ] nonce 存储去重（TTL = 时间窗），时间窗 ±300s，拒绝过期与重放
- [ ] 敏感响应（支付结果、授权结果、余额）带服务端签名，客户端校验；但真相永远在服务端重查
- [ ] 客户端提交的任何“已校验”标记、价格、角色都不作为真相源；服务端重算/重查
- [ ] 移动端证书固定；release 包禁止信任用户证书、禁止开启调试与抓包开关
- [ ] 客户端加固（混淆/加固/反调试）只提高成本，不当安全边界；密钥不下发客户端

**AI / LLM 应用**
- [ ] 模型输出视为不可信输入：不 `eval`、不直接拼 HTML/SQL/命令、不直接执行工具参数
- [ ] 工具/函数调用最小权限 + 参数 schema 校验 + 高风险动作人工确认
- [ ] RAG 检索到的文档视为不可信内容，与系统提示隔离，防间接提示注入
- [ ] 系统提示与用户输入分离；不把密钥、内部规则放进可被诱导输出的位置
- [ ] 按用户/租户做成本与频率限流；日志脱敏（不记录完整提示中的敏感数据）

**移动端 / 小程序**
- [ ] 敏感数据存 Keychain(iOS) / Keystore(Android)，不用明文 SharedPreferences
- [ ] 传输强制 TLS + 证书固定；`InsecureSkipVerify`/`verify=False` 一律禁止
- [ ] WebView 关闭 file 访问与 JS 桥暴露面，`onShouldStartLoadWithRequest` 做域名白名单
- [ ] 小程序 `session_key` 只在服务端使用，绝不下发前端；`code2session` 后签发自有会话
- [ ] root/越狱检测只作为风控信号，不作为鉴权依据

**HTTP 与路由（所有场景）**
- [ ] 不存在的路径返回真正的 HTTP 404 + 404 页面，禁止 302/200 跳首页
- [ ] SPA 的 history fallback 只对「已知前台路由」生效；`/api`、带扩展名的静态资源一律 404
- [ ] CORS 用精确 Origin 白名单，禁止 `Access-Control-Allow-Origin: *` 搭配 credentials，禁止反射任意 Origin
- [ ] 生产开启安全响应头：HSTS、CSP、X-Content-Type-Options、Referrer-Policy、frame-ancestors
- [ ] 认证/敏感接口响应带 `Cache-Control: no-store`
- [ ] 错误响应不返回堆栈、SQL、框架版本、内部路径

**收录（仅公开站点需要；后台/内部系统反过来做）**
- [ ] 公开站点：sitemap 只列 200 页面、canonical 去重、robots 不泄露后台路径、预发环境整站 noindex
- [ ] 后台/内部/个人系统：整站 `X-Robots-Tag: noindex` + robots `Disallow: /`，不生成 sitemap，且必须鉴权（robots 不是访问控制）

## 阶段一：设计时

动手前用 5 分钟做一次轻量威胁建模：

1. **定场景**：对照上面的项目类型表，确认这是公开站点、后台、内部系统还是 API；据此决定是否执行 SEO 章节、暴露面有多大。
2. **画数据流**：用户 → 网关 → 服务 → 数据库/缓存/MQ/第三方，标出每个跨越信任边界的点。
3. **列资产并分级**：账号、凭证、支付、个人数据、管理后台，分别问「谁能读、谁能写、被篡改的后果、保留多久」。
4. **每个边界问三件事**：谁能到达？输入是否校验？失败时是否默认拒绝？
5. **定权限模型**：角色 → 资源 → 动作，在服务端强制，前端隐藏按钮不算；多租户系统额外定隔离策略。
6. **定异步边界**：哪些操作必须同步返回（登录、支付确认），哪些可以异步（通知、报表、导出）。

设计文档里至少要写明：项目类型与收录策略、认证方式、授权模型、敏感数据分级与加密、限流策略、幂等键、失败降级方式、日志与审计范围。

## 阶段二：实现时

### 认证与登录（最高优先级）

登录是最容易被爆破、撞库、绕过的入口。完整规则见 `references/auth-and-session.md`，核心不可妥协：

- 限速分层：单 IP、单账号、单设备指纹；失败计数用 Redis 过期键，不要只靠内存。
- 错误信息统一为「账号或密码错误」，耗时对齐（不存在账号也走一次假哈希，防时序枚举）。
- 登录成功后重新生成会话标识；旧会话作废。
- 敏感操作（改密、改绑、提现、删除）要求二次验证或最近一次认证时间（re-auth 窗口）。
- 密码重置 token：高熵、一次性、短时效（≤15 分钟）、绑定用户与用途。
- 管理后台独立入口、独立域名或 IP 白名单，不与用户端共用会话。

### 输入、注入与输出

见 `references/web-vulnerability-prevention.md`。原则：**入口统一校验（schema），出口按上下文编码**。

```ts
// 输入：用 schema 校验，未知字段拒绝，而不是“取需要的”
const LoginBody = z.object({ email: z.string().email(), password: z.string().min(8).max(128) }).strict();

// SQL：参数化，绝不拼接
await db.query('SELECT id, password_hash FROM users WHERE email = $1', [email]);
// 排序/表名这类无法参数化的位置：白名单
const orderBy = { created_at: 'created_at', amount: 'amount_cents' }[sort] ?? 'created_at';
```

- XSS：React/Vue 默认转义即可，危险 API 必须 sanitize；CSP 作为第二道防线。
- 越权：查询条件里带上 `owner_id = $currentUser`，不要「查出后在前端判断」。
- 反序列化/模板注入：不 `eval`，不把用户输入拼进模板/表达式/正则。
- 上传：限制大小与类型（按 magic bytes 嗅探）、随机文件名、存对象存储、图片重编码。

### 数据库与高并发

见 `references/database-concurrency.md`。要点：

- 索引先于优化：新查询上线前 `EXPLAIN`，关注 type=ALL、filesort、临时表。
- 分页用游标（keyset），不用深 offset；列表接口必须有稳定排序 + 上限。
- 热点写用「条件更新 + 行锁」，库存扣减示例：

```sql
UPDATE sku SET stock = stock - $1, version = version + 1
WHERE id = $2 AND stock >= $1;
-- 影响行数为 0 → 库存不足或并发冲突，按业务重试/失败
```

- 缓存三件套：防穿透（空值缓存/布隆过滤器）、防击穿（互斥锁/单飞）、防雪崩（TTL 加随机抖动）。
- 连接池上限要小于数据库 max_connections / 实例数，并配置获取超时。
- 规模上来再谈分库分表；先做索引、缓存、读写分离、冷热分离。

### 业务逻辑与竞态

见 `references/business-logic-and-race-conditions.md`。这类漏洞没有统一扫描器，只能靠设计时逐条想清楚：价格与金额服务端计算、优惠券原子核销、状态机校验、防重放、限购维度、导出限流。并发下的「先查后写」一律改成条件更新或加锁 + 幂等。

### 异步优先架构

见 `references/async-architecture.md`。系统默认按异步设计：

- IO 全部非阻塞；Node 里禁止在请求路径上用同步 fs/crypto 和重 CPU 计算（用 worker_threads）。
- 每个外部调用都要有超时；调用链上传递 trace id。
- 队列消费 = 至少一次投递，所以必须幂等；重试有上限，超限进 DLQ 并告警。
- 跨服务一致性用 Outbox/CDC，不双写。
- 长任务（导出、批量、审核）进队列，接口立即返回任务 id，前端轮询或 SSE 推送状态。
- 优雅停机：停止接新请求 → 等在途完成 → 关闭队列消费者 → 关闭连接。

### HTTP、路由、CORS 与 SEO

见 `references/http-routing-cors-seo.md`。三条最容易踩的：

1. **404 必须是 404**。不要全局 fallback 到首页：SPA 只对构建期已知路由回落 `index.html`，`/api/*` 和带扩展名的路径直接 404。
2. **CORS 精确白名单**，把 Origin 与配置项做集合相等，不 `includes`、不前缀匹配、不直接回显请求头。
3. **状态码语义正确**：401 未认证、403 无权限、404 不存在、409 冲突、422 校验失败、429 限流。

SEO 只对**公开站点**生效；后台与内部系统按上面场景表的「禁止收录」执行，不要给它们加 sitemap、canonical、结构化数据——那是给爬虫增加攻击面。

### 密钥、运维与邮件

见 `references/operations-and-secrets.md`。要点：密钥分层存放与轮换、CI/CD 最小权限、容器非 root、对象存储与云 IAM 最小化、审计日志不可篡改、邮件域配 SPF/DKIM/DMARC 防伪造、数据保留期与删除流程。

### 接口完整性与防篡改

见 `references/api-integrity-and-tampering.md`。抓包改包和重放是移动端与开放 API 的头号问题：请求签名（HMAC + timestamp + nonce + body hash）、服务端重算、敏感响应签名、nonce 去重、时间窗、证书固定。记住：客户端能改的一切都不可信，签名只是提高门槛，服务端重算才是真相。

### AI / LLM 应用安全

见 `references/ai-llm-security.md`。模型输出等同于外部输入：不执行、不直拼、不当 SQL/命令；工具调用最小权限 + schema 校验 + 高风险人工确认；RAG 内容不可信；按租户限流控成本。

### 移动端与小程序

见 `references/mobile-and-miniprogram.md`。Keychain/Keystore、证书固定、WebView 加固、小程序 `session_key` 不下发、root 检测仅作信号。

## 阶段三：上线前评审

按顺序过一遍，任何一项「不确定」都按未通过处理：

1. 红线清单 100% 勾选；再按项目类型核对：公开站点查 SEO 项，后台/内部系统查 noindex 与入口隔离，敏感业务查接口完整性。
2. 跑 `python scripts/scan_redlines.py <目录> --fail-on high`，高危必须清零。
3. 依赖扫描（npm audit / pip-audit / govulncheck / OWASP Dependency-Check），高危必须处理。
4. 密钥检查：仓库、镜像、日志、前端 bundle 里不得出现密钥；`.env` 不进版本库；CI 日志同样要查。
5. 容器/主机：非 root、只读根文件系统、最小端口暴露、出站白名单。
6. 监控与告警：登录失败率、5xx、队列积压、慢查询、异常出站请求。
7. 备份与恢复演练；数据库账号最小权限。
8. 压测关键路径（登录、下单、列表）确认限流与缓存生效。
9. 邮件域：SPF/DKIM/DMARC 配好，发信接口限流，避免被伪造发钓鱼邮件或被当垃圾源。
10. 数据生命周期：明确收集最小化、保留期、导出与删除流程；日志脱敏后留存。
11. 安全响应预案：谁负责、怎么隔离、怎么通知用户、怎么复盘。
12. 合规映射（如需）：对照 `references/compliance-mapping.md` 检查 OWASP/ASVS/等保/PIPL 项。

## 阶段四：运行时与 0day 缓解

代码规约防不住未知漏洞，靠以下手段限制影响：

- 出站默认拒绝 + 白名单（SSRF、供应链回连的第一道墙）。
- 关键服务沙箱/容器隔离，进程降权，seccomp/AppArmor 按需开启。
- 依赖锁定版本 + 可快速重建镜像；关注安全公告，预留紧急补丁通道。
- WAF/网关做通用特征拦截与限流，但别只依赖它。
- 行为监控：异常登录地理/设备跳变、批量读写、异常出站流量。
- 数据分级：敏感字段加密存储（AES-GCM/KMS），日志脱敏，导出需审批。

## references 索引

| 文件 | 何时读 |
|---|---|
| `references/auth-and-session.md` | 登录、注册、密码、JWT、2FA、找回密码、CSRF、越权、管理后台 |
| `references/web-vulnerability-prevention.md` | SQL 注入、XSS、SSRF、上传、路径穿越、反序列化、响应头、API 特有风险 |
| `references/business-logic-and-race-conditions.md` | 价格/金额、优惠券、库存、状态机、TOCTOU 竞态、限购、导出滥用 |
| `references/database-concurrency.md` | 建表、索引、事务、锁、幂等、缓存、读写分离、分库分表 |
| `references/async-architecture.md` | 超时、重试、队列消费、Outbox、背压、优雅停机、可观测性 |
| `references/http-routing-cors-seo.md` | 404、状态码、CORS、缓存、robots/sitemap、公开站点与后台的收录分流 |
| `references/operations-and-secrets.md` | 密钥、CI/CD、容器云、邮件域、审计日志、数据生命周期、应急 |
| `references/api-integrity-and-tampering.md` | 抓包改包、请求/响应签名、重放防护、证书固定、客户端加固边界 |
| `references/ai-llm-security.md` | 提示注入、工具调用权限、RAG 投毒、模型输出处理、成本限流 |
| `references/mobile-and-miniprogram.md` | 本地存储、证书固定、WebView、小程序登录态、root 检测 |
| `references/compliance-mapping.md` | OWASP Top 10 / ASVS / 等保 2.0 / PIPL 对照，做审计或评审汇报 |
| `references/internal-policy.example.md` | 需要自定义资产禁令模板时（占位域名，不含真实地址） |

## 交付约定

- 每次交付代码时，在回复里用 3–6 行说明本次涉及的安全决策（校验点、鉴权点、幂等键、限流、错误处理），不要略过。
- 先说明项目类型：如果交付的是后台或内部系统，明确指出「不做 SEO，整站 noindex」；只有公开站点才输出收录相关配置。
- 发现现有代码违反红线时，直接指出位置并给出修复，不要只说「建议加固」。
- 无法验证的部分（例如未实际发起攻击测试）明确写「未验证」，不要声称已通过安全测试。
