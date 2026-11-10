# Secure System Development

Design and review any website, backend service, or API without shipping the usual security holes.

## Read this first

Full rules: [`SKILL.md`](SKILL.md). Read it before writing authentication, database schemas, request handlers, or deployment config.

Fast check:

```bash
python scripts/scan_redlines.py ./src --fail-on high
```

## The twelve non-negotiables

1. All input is untrusted: query, body, headers, cookies, uploads, webhooks, queue messages, third-party responses.
2. Fail closed. When validation or authorization is unclear, deny.
3. Passwords: Argon2id / bcrypt (cost ≥ 12) / scrypt. Never MD5/SHA1.
4. Rate-limit login by both account and IP; make failure text and timing identical so accounts cannot be enumerated.
5. Rotate the session id on login. Cookies get HttpOnly + Secure + SameSite.
6. Authentication is not authorization. Every handler checks that the caller owns the object.
7. SQL is always parameterized. Table and column names come from a whitelist, never from user input.
8. Encode on output per context. Any raw-HTML sink must go through a sanitizer.
9. Server-side recompute for money, price, discount, and permission. Client values are display only.
10. Every write that matters is idempotent; stock and balance use conditional updates, never read-then-write.
11. Missing paths return a real HTTP 404. Never fall back to the homepage.
12. Secrets live in env vars or a secret manager. Never in the repo, image layers, frontend bundle, or logs.

## CORS and indexing

- CORS: exact Origin allowlist. Never `*` with credentials, never reflect the request Origin.
- Indexing: only public sites (marketing, blog, docs) should be indexed. Admin panels, internal tools, and personal systems get `X-Robots-Tag: noindex` plus real authentication.

## Where to go next

| Topic | File |
|---|---|
| Auth, sessions, JWT, 2FA, IDOR | `references/auth-and-session.md` |
| Injection, XSS, SSRF, uploads, API risks | `references/web-vulnerability-prevention.md` |
| Business logic and race conditions | `references/business-logic-and-race-conditions.md` |
| Database concurrency, indexes, idempotency | `references/database-concurrency.md` |
| Async, queues, retries, shutdown | `references/async-architecture.md` |
| 404, status codes, CORS, caching, SEO | `references/http-routing-cors-seo.md` |
| Secrets, CI/CD, containers, email, audit | `references/operations-and-secrets.md` |
| Request/response signing, replay, pinning | `references/api-integrity-and-tampering.md` |
| Prompt injection, tool permissions, RAG | `references/ai-llm-security.md` |
| Mobile and mini-program | `references/mobile-and-miniprogram.md` |
| OWASP / ASVS / 等保 2.0 / PIPL | `references/compliance-mapping.md` |

## Templates

- `assets/threat-model-template.md` — fill this before coding.
- `assets/review-checklist.md` — pick the group that matches your project type.
