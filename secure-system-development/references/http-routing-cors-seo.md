# HTTP、路由、CORS 与 SEO

这一层的问题往往不是「被攻破」，而是「状态码用错导致搜索引擎收录垃圾页、缓存串数据、跨域配置变成漏洞」。

## 0. 先分清哪些规则对所有项目生效

| 内容 | 公开站点 | 登录后产品 | 管理后台 | 内部/个人系统 | 纯 API |
|---|---|---|---|---|---|
| 404 状态码、状态码语义 | 必须 | 必须 | 必须 | 必须 | 必须 |
| CORS、安全响应头、缓存策略 | 必须 | 必须 | 必须 | 必须 | 必须 |
| robots/sitemap/canonical/结构化数据 | 必须 | 仅公开单页 | **禁止** | **禁止** | 不适用 |
| 预发/测试环境 noindex | 必须 | 必须 | 必须 | 必须 | 不适用 |

判定问题：「这个 URL 应不应该被搜索引擎收录？」应该 → 执行第 7 节；不应该 → 执行第 8 节。**后台、内部系统、个人工具默认走第 8 节，不要给它们做 SEO，那只会扩大攻击面。**

## 1. 404 必须是 404（不跳首页）

**软 404**：路径不存在却返回 `200`（渲染首页或跳转首页），是搜索引擎最忌讳的情况之一——爬虫会把大量不存在的 URL 当作有效页面收录，导致站点质量下降、真实页面被稀释。

规则：

- 不存在的路径：HTTP 状态码 `404` + 404 页面（或 API 的 JSON 错误体）。
- 不要用 `302/301` 把未知路径重定向到首页。
- SPA 的 history fallback 只对**构建期已知的前台路由**生效：
  - `/api/*`、`/assets/*`、带扩展名的路径 → 一律 404；
  - 非 `GET` 请求 → 不回落；
  - 未知前台路由 → 落到前端 NotFound 组件，并且**状态码仍应是 404**（需要 SSR/预渲染/边缘函数才能设置状态码；纯静态托管做不到时，至少在边缘函数或反向代理层按路由清单判断）。
- 每个「已删除/已下架」的内容页：返回 `410 Gone` 或 404，不要重定向到首页。
- 404 页面不要自动跳转；给用户导航入口即可。

Nginx 示例（SPA 放行已知路由、其余 404）：

```nginx
map $http_accept $wants_html { default 0; "~*text/html" 1; }

server {
  location /api/   { try_files "" =404; }          # API 前缀绝不回落
  location /assets/ { try_files $uri =404; }       # 静态资源不存在即 404

  location / {
    if ($wants_html = 0) { return 404; }
    try_files $uri $uri/ @spa;
  }

  location @spa {
    # 只允许已知路由回落到 index.html，其余 404
    if ($request_uri ~* "^/(login|dashboard|pricing|docs)(/|$)") {
      add_header Cache-Control "no-store";
      try_files /index.html =404;
    }
    return 404;
  }

  error_page 404 /404.html;
  location = /404.html { internal; }
}
```

Express 示例（末尾兜底，先静态，再 SPA，再 404）：

```ts
app.use(express.static('public'));                 // 静态资源
app.use('/api', apiRouter);                        // API 自行返回 401/403/404

const knownRoutes = new Set(['/login', '/dashboard', '/pricing', '/docs']);
app.get('*', (req, res, next) => {
  if (path.extname(req.path)) return next();       // 带扩展名 → 404
  if (!req.accepts('html')) return next();         // 非浏览器请求 → 404
  if (![...knownRoutes].some(r => req.path === r || req.path.startsWith(r + '/'))) return next();
  res.sendFile(path.join(dist, 'index.html'));     // 注意：状态码仍是 200
});

app.use((req, res) => res.status(404).json({ code: 'NOT_FOUND' }));
```

> 纯 SPA 托管无法给未知路由设 404 状态码，这正是要在 CDN/边缘函数或 SSR 层解决的；如果只能静态托管，就在边缘层做路由清单判断。

这条规则对所有项目都成立。区别在于动机：公开站点是为了不被收录垃圾页；后台和内部系统是为了监控准确、避免用户误以为「系统还在」、避免软 404 掩盖真实故障。

## 2. 状态码语义

| 码 | 用途 | 常见误用 |
|---|---|---|
| 200 | 成功 | 用 200 返回业务错误（应 4xx） |
| 201 | 创建成功 | 创建接口返回 200（可接受但不规范） |
| 204 | 成功无内容 | 返回 `{}` 空体 |
| 301 | 永久重定向 | 临时跳转用 301 被浏览器永久缓存 |
| 302/307 | 临时重定向 | 307 保留方法，302 可能变 GET |
| 400 | 请求格式错误 | 把校验失败都写成 400 |
| 401 | 未认证 | 未登录返回 403 |
| 403 | 已认证但无权限 | 与 404 混用导致泄露资源存在性 |
| 404 | 不存在 | 无权限时也用 404（视安全策略，可接受但需一致） |
| 409 | 状态冲突/版本冲突 | 用 400 表示重复提交 |
| 422 | 语义校验失败 | — |
| 429 | 限流 | 返回 500 |
| 500 | 服务端未预期错误 | 返回堆栈/内部信息 |

- 未登录访问受保护 API：返回 401，前端收到 401 后跳登录并带 `return_url`（服务端校验 return_url 必须是站内路径，防开放重定向）。
- 登录页本身返回 200；受保护页面在 SSR 场景可 302 到登录页（这是合法的重定向，和「404 跳首页」是两回事）。

## 3. CORS（精确白名单）

- 允许来源用**精确集合**匹配，禁止 `*`（尤其是带 credentials 时浏览器也会拒绝），禁止反射任意 Origin，禁止 `includes`/前缀匹配（`https://a.com.evil.com` 会被误放行）。
- 需要带 cookie 时：`Access-Control-Allow-Credentials: true` + 明确 Origin + 前端 `withCredentials`。
- 预检 `OPTIONS` 正确响应，并缓存 `Access-Control-Max-Age`。
- 允许的方法与头最小化；不要 `Access-Control-Allow-Headers: *`（带 credentials 时无效且过宽）。

```ts
const ALLOWED = new Set(['https://www.example.com', 'https://admin.example.com']);
app.use((req, res, next) => {
  const origin = req.headers.origin;
  if (origin && ALLOWED.has(origin)) {
    res.setHeader('Access-Control-Allow-Origin', origin);
    res.setHeader('Vary', 'Origin');
    res.setHeader('Access-Control-Allow-Credentials', 'true');
    res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PUT,PATCH,DELETE');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, Idempotency-Key');
    res.setHeader('Access-Control-Max-Age', '600');
  }
  if (req.method === 'OPTIONS') return res.sendStatus(204);
  next();
});
```

- CORS 不是访问控制：它只约束浏览器，curl/服务端照样能访问。真正的访问控制必须靠服务端鉴权。
- 不要用 `Access-Control-Allow-Origin: null`。

## 4. 安全响应头

见 `web-vulnerability-prevention.md` 第 12 节。至少要上：HSTS、CSP、`X-Content-Type-Options: nosniff`、`Referrer-Policy`、`frame-ancestors 'none'`。

## 5. URL 规范化与重定向

- 统一尾部斜杠、统一大小写、统一 `www` 与非 `www`（只保留一套，另一套 301）。
- 重定向链不超过 1 跳；避免 A→B→C。
- 重定向目标禁止来自用户参数，除非通过白名单校验。
- 已废弃 URL 用 301 到新地址，不要 302（会被反复请求）。

## 6. 缓存策略

- 认证/个人数据响应：`Cache-Control: no-store`。
- 静态资源：内容哈希文件名 + `Cache-Control: public, max-age=31536000, immutable`。
- HTML 入口：`no-cache`（每次校验），避免发布后用户拿到旧壳。
- CDN 缓存要区分 `Vary`（Origin、Accept-Encoding、Cookie），不要把带用户身份的响应缓存给所有人。
- 防止缓存投毒：不要缓存 4xx/5xx 带用户输入的响应；Host 头参与缓存键时要校验 Host 合法性。

## 7. 公开站点：收录优化清单

只对官网、博客、文档、商城前台、帮助中心这类「希望被搜到」的页面生效。

- `robots.txt` 只写抓取规则，**不要写后台路径**（它本身公开，等于给攻击者一份目录表）。
- `sitemap.xml` 只列返回 200 的规范 URL；下架内容及时移除；分站点/分类型拆多个 sitemap。
- `canonical` 指定规范 URL，参数页（`?sort=`、`?utm_`）统一指回主页面。
- 404 返回真实 404，搜索引擎据此剔除索引——这是「不跳首页」的核心收益；已删除内容用 410 或 404，不要 301 到首页。
- 私有页面（用户资料、订单、后台）用 `noindex`，不要用 robots 屏蔽（被屏蔽的页面仍可能被索引 URL 而显示空内容）。
- SSR/预渲染保证爬虫拿到完整 HTML；纯 CSR 的站点至少给搜索引擎可读的骨架与 meta。
- 结构化数据（JSON-LD）：组织、面包屑、文章、商品；只标注页面上真实存在的内容，虚假标注会被惩罚。
- 多语言站点用 `hreflang` + 独立 URL，不要用 cookie/JS 自动跳转语言。
- 预发、测试、内部环境整站 `noindex` + Basic Auth，避免与线上重复内容竞争排名。

## 8. 后台、内部系统、个人系统：反向操作（禁止收录）

这些系统的目标是**不被搜到、不被爬、不被扫**，SEO 优化在这里是负收益。

```nginx
# 整站禁止索引（响应头优先于 meta，覆盖所有文件类型）
add_header X-Robots-Tag "noindex, nofollow, noarchive" always;

# robots 拒绝全部抓取（只是减少噪音，不是访问控制）
location = /robots.txt {
    add_header Content-Type text/plain;
    return 200 "User-agent: *\nDisallow: /\n";
}
```

- 不生成 sitemap.xml；即使存在也要返回 404。
- 不做 canonical / 结构化数据 / OG 标签——没有搜索结果页，只有多余的信息泄露。
- 访问控制靠认证 + 网络层（VPN/IP 白名单/独立子域），**不要靠 robots.txt 或「路径没被收录」当安全措施**。
- 后台入口独立域名或子域，与用户端隔离 cookie；登录页也不应被搜索引擎缓存。
- 内部系统的 404 同样要返回真 404：否则监控分不清「路径打错」和「服务正常」，也会掩盖路由配置错误。

## 9. 网关层的通用加固

- 请求体大小上限（如 JSON ≤ 1 MB，上传单独受限）。
- 请求头大小/数量上限、请求超时、慢请求断开。
- 全局限流 + 关键接口限流（登录、发码、下单、搜索）。
- 屏蔽不必要的 HTTP 方法（TRACE/TRACK）；`OPTIONS` 只做预检。
- 健康检查与错误页统一，不暴露内部拓扑与版本。
- 管理/内部接口不要挂在公网路径上，用独立域名 + 网络层白名单。
