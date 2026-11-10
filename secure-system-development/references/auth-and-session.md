# 认证与会话安全

登录是攻击成本最低、收益最高的入口。这里的目标不是「加个验证码」，而是让爆破、撞库、枚举、会话劫持、越权都变得不划算，同时不给攻击者提供把你用户锁死的杠杆。

## 1. 密码存储

- 用 Argon2id（`memoryCost≈19456 KiB, timeCost=2, parallelism=1`）或 bcrypt（cost ≥ 12）或 scrypt。禁止 MD5/SHA1/SHA256 裸哈希、禁止可逆加密、禁止自研算法。
- 密码规则：长度优先（≥ 8，上限 128 防 DoS），不做强制复杂度组合，在注册时对比已泄露密码库（HIBP 前缀 k-anonymity 查询）。
- 哈希参数存进数据库（`$argon2id$v=19$m=...`），便于以后升级 cost。
- 比较哈希用库自带函数（恒定时间），不要自己 `===`。

```ts
const hash = await argon2.hash(password, { type: argon2.argon2id });
const ok = await argon2.verify(user.password_hash, password); // 恒定时间
```

## 2. 防爆破与撞库

分层限速，按风险加权，不是单一阈值：

| 维度 | 典型策略 | 存储 |
|---|---|---|
| 单账号 | 5 次失败/15 分钟 → 渐进延迟；20 次 → 要求验证码；持续失败 → 临时锁定 15 分钟 | Redis 键 `login:fail:user:{id}` |
| 单 IP | 50 次/10 分钟，超限 429 + 冷却 | Redis 滑动窗口 / 令牌桶 |
| 单 IP+账号 | 10 次/10 分钟 | 组合键 |
| 全局 | 登录接口总量限流，防分布式撞库 | 网关层 |

实现要点：

- 计数器带 TTL，登录成功清零对应账号维度（不清 IP 维度，防「正确一次再爆」）。
- 返回统一 `429 Too Many Requests`，带 `Retry-After`，不要提示「你的账号被锁定」——那会让攻击者拿到锁定他人的手段。
- **优先延迟与 IP 封禁，账号锁定只作为最后手段且时间短**，否则攻击者用你的锁定策略把任意账号打死（拒绝服务）。
- 分布式部署下，计数必须放共享存储（Redis），不能用进程内存。
- 记录失败事件（IP、UA、设备指纹哈希、时间）用于风控和事后分析；不要记录明文密码。

```ts
async function checkLoginRate(userKey: string, ip: string) {
  const [u, i] = await Promise.all([
    redis.incr(`login:fail:user:${userKey}`),
    redis.incr(`login:fail:ip:${ip}`),
  ]);
  if (u === 1) redis.expire(`login:fail:user:${userKey}`, 900);
  if (i === 1) redis.expire(`login:fail:ip:${ip}`, 600);
  if (u > 5) await sleep(Math.min(2 ** (u - 5) * 200, 3000)); // 渐进延迟
  return { blocked: u > 20 || i > 50, captchaRequired: u > 8 };
}
```

## 3. 防账号枚举

注册、登录、找回密码、验证码发送的响应必须一致：

- 文案统一：「账号或密码错误」「如果该邮箱存在，我们已发送邮件」。
- 耗时统一：账号不存在时也执行一次假的 `argon2.verify`（对固定 dummy hash），避免时序差暴露账号存在性。
- 状态码统一，不要「用户不存在 404 / 密码错误 401」。
- 注册接口如果必须提示已注册，应改为「发送了验证邮件」的流程。

## 4. 会话

- session id 用 CSPRNG ≥ 128 bit（`crypto.randomBytes(32).toString('base64url')`），存服务端（Redis），不要放自签名的用户信息。
- **登录成功后轮换 session id**，并清除旧记录——防会话固定攻击。
- Cookie：`HttpOnly; Secure; SameSite=Lax`（跨站必须用 cookie 时评估 `SameSite=None; Secure` 并配合 CSRF token）；设置 `Path=/`、合理 `Max-Age`；敏感会话优先 `__Host-` 前缀。
- 会话空闲超时 + 绝对超时（如 30 分钟空闲 / 12 小时绝对）；改密、改绑、登出全部设备 → 作废全部会话。
- 登出要服务端删除会话，不能只清前端 cookie。
- 并发会话策略明确：允许多设备则在会话列表里可单独撤销。

## 5. JWT（如果使用）

- 服务端固定允许的算法（`algorithms: ['RS256']`），拒绝 `none` 与 HS/RS 混淆。
- 有效期短（access 5–15 分钟），refresh token 轮换 + 检测重放（旧 refresh 被用 → 整链作废）。
- payload 不放敏感数据（JWT 只是签名不是加密）；需要即时撤销就维护 `jti` 黑名单或改用服务端会话。
- 不要在 URL/query 里传 token（会进日志和 Referer）。
- 前端存储优先内存 + HttpOnly cookie 刷新，避免 localStorage 长期存放高价值 token。

## 6. 多因素与验证码

- OTP：6–8 位、有效期 ≤ 5 分钟、一次性消费、按账号与 IP 限发（如 1 次/分钟，5 次/小时）、错误 5 次作废重发。
- 发送验证码的接口必须限流并且防枚举（见第 3 节），否则就是短信轰炸机。
- TOTP 校验默认允许 ±1 个时间窗；防重放（记录已用 code/time step）。
- 高风险操作（新设备登录、改密、提现）强制二验。

## 7. 密码重置与找回

- token：≥ 128 bit 随机、一次性、≤ 15 分钟、在服务端存储哈希、绑定 user + 用途 + 发起时间。
- 使用后立即失效，并通知用户；改密成功后作废全部会话。
- 重置链接不要带账号信息（防枚举），页面文案中性。
- 禁止「密保问题」这类弱凭证。

## 8. CSRF

- 优先 `SameSite=Lax/Strict`；跨站场景加 double-submit 或同步 token。
- 只对状态改变（POST/PUT/PATCH/DELETE）校验；token 与 session 绑定。
- 重要：CORS 不是 CSRF 防护，二者机制不同，别互相替代。

## 9. 授权（越权防护）

- 认证解决「你是谁」，授权解决「你能做什么」。每个接口都要显式判断。
- 对象级权限（IDOR）：查询时带属主条件，而不是查出来再判断。

```ts
const order = await db.one(
  'SELECT * FROM orders WHERE id = $1 AND user_id = $2', [id, req.user.id]
); // 没有行 → 404，不区分"不存在"与"不属于你"
```

- 功能级权限（BFLA）：管理接口用独立中间件强制角色校验，且路由前缀隔离（`/admin`）。
- 默认拒绝：新增接口必须显式声明需要的权限，未声明即拒绝。
- 多租户系统：所有查询强制带 `tenant_id`，用统一的数据访问层保证，不靠开发者自觉。

## 10. 管理后台

- 独立域名/子域 + IP 白名单或 VPN；不与用户端共享 cookie/session。
- 强制 MFA；操作审计日志（谁、何时、从哪、改了什么）。
- 高风险操作（导出全量数据、改权限、删数据）二次确认 + 双人复核。

## 11. 记住我 / 第三方登录

- 「记住我」= 长期 token（随机、哈希存库、可撤销、绑定设备），不是长期有效 session。
- OAuth/OIDC：校验 `state`（CSRF）、校验 `nonce`（OIDC）、严格校验 `redirect_uri` 完全匹配、校验 id_token 签名与 `aud/iss/exp`。
- 不要信任第三方返回的 email 直接关联本地账号（需验证），否则可被账号接管。
