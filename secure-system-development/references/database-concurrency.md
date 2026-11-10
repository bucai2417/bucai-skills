# 数据库设计与高并发

目标：在流量上来之前就把「索引、事务、锁、幂等、缓存」设计对，而不是等挂了再优化。

## 1. 表结构

- 主键：业务量小用自增 bigint，分布式用雪花/ULID；不要用可枚举且有业务含义的字段做 PK。
- 金额用 `BIGINT` 存分或 `DECIMAL(18,2)`，禁止 float/double；汇率、比例用 DECIMAL 并明确精度。
- 时间用 `TIMESTAMPTZ`（或统一 UTC 存 long），不要用本地时区字符串。
- 状态用 short 码 + 注释/字典表，不用自由文本。
- 必填字段 `NOT NULL` + 默认值；用 `CHECK` 约束兜底关键不变量（如 `balance >= 0`）。
- 预留 `created_at`、`updated_at`（必要时 `deleted_at`）；更新时间用应用层或触发器统一维护。
- 逻辑删除：要么加 `deleted_at` 并在唯一索引里带上（见本节末），要么归档表，避免「删了还能注册同一邮箱」这类问题。

## 2. 索引（先于一切优化）

- 每个高频查询都要有支撑索引；设计阶段就把查询列出来，按查询建索引。
- 联合索引按「等值列在前、范围列在后」，遵循最左前缀；排序字段放在联合索引末尾。
- 覆盖索引减少回表（`EXPLAIN` 里出现 `Using index`）。
- 不要给低区分度列单独建索引；不要建一堆只用一次的索引（写放大）。
- 唯一索引既是约束也是并发安全的工具（幂等键、业务唯一性）。
- 上线前必须 `EXPLAIN (ANALYZE, BUFFERS)`：禁止出现 `Seq Scan`（大表）、`Using temporary; Using filesort`、嵌套循环扫大表。

```sql
-- 查询：WHERE tenant_id = ? AND status = ? ORDER BY created_at DESC
CREATE INDEX CONCURRENTLY idx_order_tenant_status_time
  ON orders (tenant_id, status, created_at DESC);
```

- 大表加索引用 `CONCURRENTLY`（PG）或在线 DDL（MySQL 8 INSTANT/INPLACE），避免锁表。

## 3. 查询模式

- 禁止 `SELECT *`，只取需要的列。
- 分页：深 offset 会越翻越慢，改用游标（keyset）：

```sql
SELECT id, title, created_at FROM posts
WHERE created_at < $cursor_time OR (created_at = $cursor_time AND id < $cursor_id)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

- 列表接口必须有 `LIMIT` 上限（如 ≤ 100），排序稳定（带唯一列作为 tie-breaker）。
- 避免 N+1：批量 `IN`、JOIN、或在应用层做 DataLoader 批处理。
- 计数（`COUNT(*)` 大表）用近似值或维护计数表，不要实时全表统计。
- 模糊搜索用专用索引（PG `pg_trgm`/全文索引，MySQL 前缀索引），不要 `LIKE '%x%'` 全表扫。

## 4. 事务与隔离级别

- 事务尽量短：只包必要的写操作；**事务内禁止 HTTP 调用、发消息、渲染模板、读大文件**。
- 隔离级别默认 READ COMMITTED（PG 默认）即可；需要「读一致性快照」用 REPEATABLE READ；不用 SERIALIZABLE 除非必要（重试成本高）。
- 死锁：固定加锁顺序（按主键升序更新），捕获死锁错误后小重试；长事务是死锁与膨胀的根源。
- 悲观锁 `SELECT ... FOR UPDATE` 只锁必要行，且必须在事务内；能不用就不用。
- 乐观锁：`version` 列，更新时 `WHERE version = ?`，失败重试。

## 5. 并发写与库存/余额

先查后改一定出错。用条件更新把判断和写入合成一条语句：

```sql
-- 扣库存/扣余额
UPDATE account SET balance = balance - $1 WHERE id = $2 AND balance >= $1;
-- 影响 0 行 → 余额不足或并发冲突
```

- 秒杀/热点库存：数据库行锁会在热点上排队。方案：Redis 预扣（Lua 原子）+ 异步落库 + 幂等校验，数据库做最终扣减兜底。
- 热点行：单个计数器拆桶（`counter_0..N` 随机写，读时求和），或 Redis 累加后定时合并。

## 6. 幂等（必须设计，不是可选）

- 写接口带 `Idempotency-Key`，落地到唯一索引表：

```sql
CREATE TABLE idempotency (
  key TEXT PRIMARY KEY,
  scope TEXT NOT NULL,
  response JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- 插入冲突 → 返回已存响应
```

- 业务唯一索引兜底：`UNIQUE(user_id, order_no)`、`UNIQUE(platform, external_id)`（回调去重）。
- 支付/退款回调必须幂等：先查状态机，非法状态直接返回成功（避免上游重复推送）。
- 消息消费幂等：`UNIQUE(message_id)` 或去重表 + 事务内消费。

## 7. 缓存

- 模式：cache-aside（读缓存 → 未命中查库 → 回填）；写操作「先更新库，再删缓存」，或延迟双删。
- 防穿透：查不到的 key 缓存空值（短 TTL）或加布隆过滤器。
- 防击穿：热点 key 过期时用互斥锁/单飞（singleflight），只让一个请求回源。
- 防雪崩：TTL 加随机抖动；缓存集群多副本；降级直接读库并限流。
- 不要缓存权限判定结果过久；权限变更要能立即失效（版本号/主动删除）。
- 缓存与数据库一致性：接受最终一致，但要在业务上定义可接受窗口；强一致场景不走缓存。

## 8. 连接池与服务保护

- `pool.max` 经验值：`(CPU 核数 * 2) + 磁盘并行度`，且保证 `实例数 × pool.max + 运维连接 < DB max_connections`。
- 配置获取连接超时（如 3s）、查询超时、空闲回收；超时要快速失败，不能无限排队。
- 数据库前面可以加 PGBouncer/代理做连接复用。
- 慢查询日志长期开启，定期复查。

## 9. 读写分离与分库分表

- 先做索引 → 缓存 → 读写分离，最后才分片。
- 读写分离：强一致读（刚写完就读）走主库，其余走从库；注意主从延迟导致的「下单后查不到订单」。
- 分片时机：单表 > 千万级或单库连接/IO 打满再考虑。分片键选择要保证主要查询都带分片键（如 `tenant_id`/`user_id`）。
- 分片后避免跨分片 JOIN 与分布式事务；需要的聚合走宽表或异步汇总。
- 全局 ID：雪花算法（时钟回拨处理）或号段模式，保证趋势递增利于 B+ 树。

## 10. 数据一致性

- 禁止「写库 + 发 MQ」双写（中间失败就不一致）。用 Outbox 表 + CDC（Debezium/Canal）或本地消息表。
- 跨服务事务优先用 Saga/补偿，不轻易上 2PC。
- 对账：支付、账务类业务必须有日终对账与差异修复流程。

## 11. 变更与运维

- Schema 变更走迁移工具，可回滚；破坏性变更分两步（先加列，再切读，最后删旧列）。
- 大批量更新分批执行（每批 ≤ 1k 行）并限速，避免主从延迟与锁等待。
- 备份：全量 + binlog/WAL 增量，定期做恢复演练；备份文件加密。
- 数据库账号：应用账号按库/表授权，禁止 root；只读账号单独发放。
