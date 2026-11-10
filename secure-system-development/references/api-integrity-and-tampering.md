# 接口完整性与防篡改

针对「抓包改包、重放、伪造响应、中间人、客户端绕过」。核心事实：**客户端上的一切都可被改**。签名、证书固定、加固只能提高攻击成本，真相必须由服务端重算。

## 1. 威胁模型

| 攻击 | 手法 | 防御 |
|---|---|---|
| 改包 | 中间人代理改请求参数（价格、数量、user_id、角色） | 服务端重算 + 请求签名 + 参数白名单 |
| 重放 | 抓到一个合法请求，重复发送（领券、提现、支付回调） | nonce 去重 + 时间窗 + 幂等键 |
| 伪造响应 | 本地劫持返回，把「支付失败」改成「成功」 | 服务端签名响应 + 服务端二次确认 |
| 中间人 | 装根证书解密流量 | TLS + 证书固定（移动端） |
| 客户端绕过 | 改 APK/JS 跳过前端校验 | 前端校验只作体验，服务端强制 |
| 密钥提取 | 从客户端提取密钥复用 | 客户端密钥视为公开，不下发真正的长期密钥 |

## 2. 传输层

- 强制 HTTPS，TLS 1.2+，禁用弱套件；HSTS。
- 移动端**证书固定**（pin 证书公钥哈希，不只 pin 域名），并准备备用 pin 防轮换锁死。
- release 包禁止 `verify=False` / `rejectUnauthorized: false` / `InsecureSkipVerify: true`；禁止信任用户安装的根证书（Android `network_security_config` 显式只信任系统 CA，调试配置只在 debug 变体）。
- WebView 加载外部 URL 走域名白名单，禁止任意跳转。

## 3. 请求签名

签名串构造（字段顺序固定，服务端与客户端一致）：

```
stringToSign =
  METHOD + "\n" +
  PATH + "\n" +
  sortedQuery(k=v&k=v, key 升序, URL 编码) + "\n" +
  hex(sha256(body)) + "\n" +
  timestamp + "\n" +
  nonce
signature = hex(HMAC_SHA256(secret, stringToSign))
```

请求头携带：`X-Timestamp`、`X-Nonce`、`X-Signature`、`X-App-Id`（区分客户端类型）。

服务端校验顺序（任一失败即拒绝，返回 401）：

```js
const { timestamp, nonce, signature, appId } = headers;
if (Math.abs(Date.now() - Number(timestamp)) > 300_000) return reject('expired');   // ±5 分钟
const raw = [method, path, sortedQuery, sha256(body), timestamp, nonce].join('\n');
const expected = hmacSha256(secretFor(appId), raw);
if (!timingSafeEqual(expected, signature)) return reject('bad-signature');
const ok = await redis.set(`nonce:${appId}:${nonce}`, 1, 'NX', 'EX', 600);           // 去重
if (!ok) return reject('replay');
```

Go 版要点：用 `hmac.New(sha256.New, []byte(secret))`；query 排序用 `url.Values.Encode()`（它已按键升序且做了编码）；比较用 `hmac.Equal`。

## 4. 服务端重算：签名的前提

签名只证明「请求没被改」，不证明「请求合法」。两者都要：

- 价格、折扣、运费、佣金：服务端按商品与规则重算，与客户端值不一致直接拒绝。
- `user_id`、`tenant_id`、`role`、`status`：从会话/令牌推导，不接受客户端传入。
- 库存、余额、次数：条件更新原子扣减（见 `database-concurrency.md`）。
- 订单状态：状态机校验，非法跃迁拒绝（见 `business-logic-and-race-conditions.md`）。

## 5. 响应完整性

高价值响应（支付结果、授权结果、余额、提现状态）附签名：

```js
res.setHeader('X-Signature', hmacSha256(secret, res.bodyJson));
res.setHeader('X-Timestamp', Date.now());
```

- 客户端校验签名失败时**不展示成功**，并强制回服务端查询状态。
- 但记住：能改客户端的人也能跳过校验。所以支付/提现最终态必须由服务端主动查询渠道或对账确认，响应签名只是让普通改包工具失效。
- 客户端不要缓存「已成功」状态作为唯一真相。

## 6. 防重放细节

- nonce 必须是密码学随机（`crypto.randomBytes`），长度 ≥ 16 字节。
- 去重存储 TTL = 时间窗 + 余量（如窗口 300s，TTL 600s）。
- 时钟漂移：允许 ±300s；返回错误时给出服务端时间供客户端校正，但不放宽窗口。
- 分布式部署：nonce 存 Redis（共享），不能用进程内存。
- 支付回调这类第三方请求，用渠道自己的签名与重放机制（如微信支付 `Wechatpay-Serial`、时间戳校验），不要自创。

## 7. 幂等键

与签名互补：签名防篡改，幂等键防重复。

```http
POST /api/orders
Idempotency-Key: 7f3a9c2e-...
```

- 服务端在唯一索引表记录 key + 作用域 + 响应；重复请求返回已存响应。
- 与 `business-logic-and-race-conditions.md` 的幂等章节保持同一套表结构，不要两套。

## 8. 客户端加固的边界（明确不做什么）

**可以提高成本但不能当安全边界**：代码混淆、加壳、反调试、root 检测、模拟器检测、完整性自校验。

- 这些手段一律可被绕过（改字节、hook、内存 patch）。
- 因此：不依赖客户端判定权限、不依赖客户端判定支付成功、不把长期密钥放进客户端。
- 客户端密钥的正确用法：只用于「防篡改」的门槛（配合服务端重算），不作为身份凭证。
- 真正的身份凭证：服务端签发的短生命周期会话/JWT（见 `auth-and-session.md`）。

## 9. 调试与日志红线

- 生产禁止打印完整请求体/响应体（含密码、token、支付信息）。
- 抓包开关、mock 开关、`/debug` 路由默认关闭，启动时断言生产环境为关闭。
- 错误响应不区分「签名错/时间过期/nonce 重复」的细节给客户端（防探测），但服务端日志要区分。
- 签名失败与重放尝试要计入风控指标并告警。

## 10. 常见错误清单

- ❌ 把签名密钥写进前端 JS / APK → 视为公开，改包者可直接重签。
- ❌ 只签 query 不签 body → 改 body 绕过。
- ❌ query 未排序就签名 → 服务端与客户端结果不一致（偶发失败）。
- ❌ 时间窗不校验 → 抓到一次即可永久重放。
- ❌ nonce 存内存 → 多实例部署失效。
- ❌ 依赖 `X-Forwarded-For` 判定来源而不校验代理 → 可伪造 IP。
- ❌ 用 `==` 比较签名 → 时序攻击；用恒定时间比较。
