# 上线前评审清单

按项目类型选一组勾选，不要全选。每组末尾的「通用」项所有类型都要过。

## A. 公开站点（官网 / 博客 / 文档 / 商城前台）

- [ ] 不存在的路径返回真实 404，不 302/200 跳首页
- [ ] SPA fallback 只对已知前台路由生效，`/api` 与带扩展名路径直接 404
- [ ] sitemap.xml 只列返回 200 的规范 URL
- [ ] canonical 指定规范 URL，参数页指回主页面
- [ ] robots.txt 不含后台/内部路径
- [ ] 已下架内容返回 404/410，不 301 到首页
- [ ] 私有页面（用户中心、订单）带 noindex
- [ ] 结构化数据（JSON-LD）只标注页面真实内容
- [ ] 多语言站点用 hreflang + 独立 URL
- [ ] 预发/测试环境整站 noindex 或 Basic Auth
- [ ] 全站 HTTPS，HTTP → HTTPS 301
- [ ] 公开表单有 CSRF 防护与提交频控

## B. 登录后产品（SaaS / 工具站 / 社区）

A 组的公开页部分 + 以下：

- [ ] 密码用 Argon2id/bcrypt(cost≥12)/scrypt
- [ ] 登录按「账号 + IP」双维度限速，渐进延迟
- [ ] 登录错误文案与耗时一致，不泄露账号存在性
- [ ] 登录成功后轮换 session id
- [ ] Cookie：HttpOnly + Secure + SameSite
- [ ] 每个接口校验对象归属（防 IDOR）
- [ ] 敏感操作要求二次验证或 re-auth 窗口
- [ ] 密码重置 token 高熵、一次性、≤15 分钟
- [ ] 私有页面 noindex
- [ ] 会话空闲超时 + 绝对超时
- [ ] 登出服务端删除会话

## C. 管理后台（admin / 运营 / 客服 / 审核）

- [ ] 独立域名或子域，与用户端隔离 cookie
- [ ] IP 白名单 / VPN / 零信任接入
- [ ] 强制 MFA
- [ ] 整站 `X-Robots-Tag: noindex`，robots `Disallow: /`
- [ ] 不生成 sitemap，无 canonical/OG/JSON-LD
- [ ] 全部写操作有审计日志（谁、何时、从哪、改了什么）
- [ ] 高风险操作（导出全量、改权限、删数据）二次确认
- [ ] 角色权限服务端强制，前端隐藏按钮不算
- [ ] 后台接口与用户端接口物理隔离
- [ ] 会话与用户端不共用
- [ ] 敏感数据导出需审批 + 水印/追踪
- [ ] 后台登录失败告警

## D. 内部 / 个人系统

- [ ] 强制鉴权（不做匿名访问）
- [ ] 整站 `X-Robots-Tag: noindex` + robots `Disallow: /`
- [ ] 不放在公网默认路径（`/admin`、`/console`、`/nas`）
- [ ] 网络层限制（VPN / 内网 / IP 白名单）
- [ ] 不靠「隐蔽性」当安全措施
- [ ] 404 返回真实 404（保证监控准确）
- [ ] 依赖及时更新，开启自动安全更新
- [ ] 备份可用且有恢复演练
- [ ] 默认账号/口令已改，无测试后门
- [ ] 日志至少本地可查

## E. 纯 API（REST / GraphQL / 服务间）

- [ ] 每个接口显式鉴权（认证 + 授权）
- [ ] 输入 schema 校验，未知字段拒绝
- [ ] SQL 参数化，禁止拼接
- [ ] 限流（按 key / 用户 / IP）
- [ ] 分页上限 + 稳定排序
- [ ] 响应字段最小化（不直接序列化 ORM 实体）
- [ ] 错误响应不含堆栈/内部信息
- [ ] 有版本号与弃用策略
- [ ] GraphQL 关闭生产 introspection，限制深度/复杂度
- [ ] WebSocket 握手鉴权 + Origin 校验
- [ ] 敏感接口签名 + 防重放（如支付/资金）
- [ ] CORS 精确白名单

## 通用（所有项目）

- [ ] `python scripts/scan_redlines.py <目录> --fail-on high` 高危清零
- [ ] 依赖扫描（npm audit / pip-audit / govulncheck / OWASP Dependency-Check）
- [ ] 仓库/镜像/日志/前端 bundle 无密钥；`.env` 不在版本库
- [ ] 容器非 root、只读根文件系统、最小端口
- [ ] 数据库账号最小权限，无 root
- [ ] 安全响应头：HSTS、CSP、X-Content-Type-Options、Referrer-Policy、frame-ancestors
- [ ] 敏感接口 `Cache-Control: no-store`
- [ ] 全局错误处理，不泄露内部细节
- [ ] 日志结构化 + 敏感字段脱敏
- [ ] 备份 + 恢复演练
- [ ] 关键路径压测（登录、下单、列表）
- [ ] 监控告警：登录失败率、5xx、队列积压、慢查询
- [ ] 邮件域 SPF/DKIM/DMARC
- [ ] 数据保留期与删除流程明确
- [ ] 安全事件响应预案（谁负责、怎么隔离、怎么通知）
