# 移动端与小程序安全

移动端和小程序的共同点：**客户端完全在攻击者手里**，且常有独立的登录态机制。

## 1. 本地存储

| 平台 | 正确做法 | 禁止 |
|---|---|---|
| iOS | Keychain（`kSecAttrAccessibleWhenUnlockedThisDeviceOnly`） | UserDefaults 存 token/密码 |
| Android | Keystore + EncryptedSharedPreferences | 明文 SharedPreferences、外部存储 |
| 小程序 | `wx.setStorage` 只放非敏感数据 | 存 token 以外的敏感信息（且 token 应短时效） |

- token 尽量短时效 + 服务端可撤销；长期凭证不落本地明文。
- 退出登录时清除本地凭证与服务端会话。
- 截图/剪贴板：敏感页面禁止截屏（Android `FLAG_SECURE`），敏感内容不自动复制到剪贴板。

## 2. 传输

- 强制 TLS 1.2+；Android `network_security_config` 只信任系统 CA（debug 变体例外且不进 release）。
- 证书固定：pin 公钥哈希（SPKI），准备备用 pin，避免证书轮换把用户锁死。
- 禁止 `InsecureSkipVerify` / `verify=False` / 自定义信任所有证书的 `TrustManager`。
- 移动端请求签名与防重放见 `api-integrity-and-tampering.md`。

## 3. WebView

- 关闭不必要的文件访问：Android `setAllowFileAccess(false)`、`setAllowFileAccessFromFileURLs(false)`、`setAllowUniversalAccessFromFileURLs(false)`。
- 只加载白名单域名；`shouldOverrideUrlLoading` / `onShouldStartLoadWithRequest` 做域名校验。
- JS 桥（`addJavascriptInterface`）只暴露必要方法，且校验来源页面；Android API 17+ 才安全，仍要做参数校验。
- 不在 WebView 里注入用户可控的 JS；`evaluateJavascript` 的参数要编码。
- 敏感页面禁止在 WebView 中渲染，或至少禁用缓存。

## 4. root / 越狱检测

- 只作为**风控信号**（提高验证强度、限流、人工审核），**不作为鉴权依据**。
- 检测可被绕过（Magisk Hide、Zygisk、Frida 隐藏），不要以为检测到就一定安全。
- 真正防护靠服务端：接口鉴权、行为风控、设备指纹（弱信号）。

## 5. 微信小程序

**登录态流程**（这是最容易做错的地方）：

```
小程序 wx.login() → code
   ↓ 发给自己的后端
后端 code2session → { openid, session_key }
   ↓
后端签发自己的会话（token/session id），session_key 只留在服务端
   ↓
后续请求用后端会话，不用 session_key
```

红线：

- **`session_key` 绝不下发前端**。它可解密用户数据、校验签名，泄露等于账号被接管。
- `code` 一次性、5 分钟内有效，后端校验失败要重新 `wx.login()`。
- 手机号授权：`getPhoneNumber` 返回的加密数据在后端用 `session_key` 解密，不信任前端传来的手机号。
- 小程序端不要存长期凭证；`wx.setStorage` 中的 token 应短时效 + 可撤销。
- 小程序接口与 H5 共用时，鉴权逻辑要统一，不要给小程序开「免鉴权」后门。

## 6. 小程序其他风险

- 页面跳转 `wx.navigateTo` 的目标来自参数时，校验为站内路径（防跳转到钓鱼页）。
- `web-view` 组件加载域名必须在微信后台配置白名单，且校验参数。
- 分享参数可被篡改：分享卡片带来的用户身份要在后端校验（防伪造邀请）。
- 小程序包本身可被反编译，前端代码等同公开：不在小程序里放密钥、算法密钥、内部接口签名密钥。

## 7. 移动端特有的业务风险

- 设备指纹 + 行为风控（异常登录、批量操作、模拟器批量注册）。
- 位置/相机/通讯录等权限只在需要时申请，并说明用途；最小化收集。
- 推送 token 与用户绑定要鉴权，防他人冒绑。
- 应用完整性（签名校验）只作信号；渠道包/热更新要签名验证，防止被篡改下发。

## 8. 发布与运维

- release 包关闭调试（Android `debuggable=false`，iOS 不打包调试符号）。
- 禁止在 release 中保留测试后门、mock 开关、日志打印敏感数据。
- 混淆/加固提高逆向成本，但不当安全边界（同 `api-integrity-and-tampering.md` 第 8 节）。
- 灰度发布与强制升级策略：旧版本有漏洞时要能强制升级。

## 9. 快速自查

- [ ] 敏感数据进 Keychain/Keystore，不进明文存储
- [ ] TLS + 证书固定，release 不信任用户证书
- [ ] WebView 文件访问关闭、加载域名白名单、JS 桥最小暴露
- [ ] 小程序 `session_key` 只在服务端，`code` 一次性校验
- [ ] 手机号等授权数据在后端解密，不信任前端值
- [ ] root/越狱检测只作信号
- [ ] release 无调试开关、无敏感日志
