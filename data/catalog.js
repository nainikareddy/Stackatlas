// StackAtlas catalog — GENERATED from mcp_server/catalog.json by
// pipeline/render_dashboard_data.py. Do not hand-edit; re-run the script
// after regenerating the catalog so the dashboard and the MCP server never
// tell two different stories again.

export const catalog = {
  database: "vibeshop",
  generatedAt: "2026-08-30T06:40:14Z",
  healthScore: 45,
  stats: { tables: 14, columns: 61, fkCoverage: 0.27, docCoverage: 1.0, orphans: 1 },
  tables: [
    {
      name: "analytics_events", rows: 8, status: "warning", pos: { x: 100, y: 90 },
      readsPerDay: 42, writesPerDay: 8,
      doc: "Stores generic product-analytics events (event name + free-form JSON props) tied to a user via `uid`, used for lightweight usage tracking such as page views and report runs. Table is tiny (~8 rows) and low-traffic (42 reads/8 writes per day), suggesting it's either newly instrumented, a dev/staging artifact, or events are being persisted elsewhere (e.g. a real analytics pipeline) and this table is largely vestigial. Every nullable column (uid, event, props, ts) can be null, so consumers must defensively handle missing user attribution, missing event names, empty payloads, and missing/invalid timestamps.",
      issues: ["`uid` has no enforced foreign key to users, so orphaned or misattributed events are possible and joins must handle NULL/unmatched uid", "`ts` is a bigint with no documented unit (epoch seconds vs milliseconds ambiguous) and no default, so ordering/filtering by time is unreliable without a convention check", "`event` is a free-text column with no enum/check constraint \u2014 only 'page_view' and 'run_report' observed, but nothing prevents typos or inconsistent naming (e.g. 'pageView' vs 'page_view') from fragmenting analytics downstream", "`props` is unstructured jsonb with no schema validation, so shape can silently drift per event type and break downstream parsers", "All non-PK columns are nullable, including `event` and `ts`, allowing effectively empty/no-op event rows", "Extremely low row count and write volume relative to a stated analytics purpose suggests this table may be unused/deprecated in favor of another event pipeline \u2014 worth confirming before building on it"],
      columns: [
        { name: "id", type: "bigint", doc: "Auto-incrementing surrogate primary key for the event row." },
        { name: "uid", type: "bigint", doc: "References the acting user's id in `users`, but the FK is unenforced and the column is nullable, so orphaned or anonymous events are possible.", flag: true },
        { name: "event", type: "text", doc: "Free-text event name; observed values 'page_view' (user viewed a page) and 'run_report' (user executed a report), but the column has no enum constraint so new values can be typo'd or inconsistently cased.", flag: true },
        { name: "props", type: "jsonb", doc: "Unstructured jsonb payload holding event-specific metadata with no enforced schema, so its shape can vary silently by event type.", flag: true },
        { name: "ts", type: "bigint", doc: "Bigint timestamp of the event with no documented unit (seconds vs milliseconds) and no default, so time-based queries risk misinterpretation.", flag: true }
      ],
    },
    {
      name: "feature_flags", rows: 2, status: "warning", pos: { x: 310, y: 90 },
      readsPerDay: 1, writesPerDay: 2,
      doc: "A tiny key-value table used for feature-flag toggles: `flag` is the human-readable flag name (primary key, e.g. 'agent_context_api', 'new_billing_page'), `enabled` is a simple boolean kill-switch, and `rollout` presumably holds structured targeting/percentage-rollout rules as JSON. With only 2 rows and 1 read/2 writes per day, this looks like a low-traffic config table rather than a high-throughput flag service (no evaluation/audit log, no per-environment or per-user segmentation columns).",
      issues: ["`enabled` is nullable with no CHECK constraint, so a NULL is possible and its semantic meaning (same as false? unset/unknown?) is undefined and unenforced by the schema.", "`rollout` is an unconstrained jsonb blob with no schema/JSON-schema validation, so its shape (percentages, user lists, environment targeting) is undocumented and can drift silently between rows.", "No `updated_at`/`updated_by` or audit columns, so there's no way to tell who flipped a flag or when, which is risky for a table that directly controls production behavior.", "No environment or scope column (e.g. dev/staging/prod), so if this table is shared across environments there's no way to differentiate rollout state per environment.", "`flag` has no naming convention enforced (free-text primary key), risking typos causing silent no-ops in application code that checks for an exact flag string."],
      columns: [
        { name: "flag", type: "text", doc: "Free-text primary key naming the feature flag (observed values: 'agent_context_api', 'new_billing_page'); any typo when checking this string in code silently fails open/closed with no error.", flag: true },
        { name: "enabled", type: "boolean", doc: "Boolean toggle observed as True/False that gates the feature, but is nullable with default 'false' and no constraint preventing an ambiguous NULL state.", flag: true },
        { name: "rollout", type: "jsonb", doc: "Unvalidated jsonb payload presumably holding gradual-rollout or targeting rules, with no enforced schema so its structure can vary unpredictably row to row.", flag: true }
      ],
    },
    {
      name: "order_items", rows: 0, status: "critical", pos: { x: 520, y: 90 },
      readsPerDay: 42, writesPerDay: 0,
      doc: "order_items stores line-item records (product + quantity + price) belonging to an order, intended to be joined to an order header table via order_id. The table currently has zero rows and receives no writes (42 reads/day with no inserts), suggesting it is either unused, pre-production, or has been superseded. Critically, the enforced FK on order_id still points to the deprecated 'orders' table while live order data lives in 'orders_v2', so any enforced referential integrity is against the wrong table and the real relationship is unenforced.",
      issues: ["order_id has an enforced FK to the deprecated 'orders' table instead of the live 'orders_v2' table, so referential integrity is effectively broken/meaningless", "order_id -> orders_v2 relationship is not enforced at the DB level, allowing orphaned line items", "product_id -> products relationship is not enforced, allowing references to non-existent or deleted products", "order_id, product_id, qty, and unit_price_cents are all nullable, so a row could exist with no order, no product, and no price", "unit_price_cents is stored as a plain integer with no currency column, so multi-currency correctness relies entirely on application convention", "table has 0 rows and 0 writes/day despite 42 reads/day, indicating it may be dead/orphaned code path querying an empty or unused table", "no unique constraint on (order_id, product_id), so duplicate line items for the same product on the same order are possible"],
      columns: [
        { name: "id", type: "bigint", doc: "Auto-incrementing surrogate primary key generated from order_items_id_seq." },
        { name: "order_id", type: "bigint", doc: "Intended to reference the parent order, but its enforced FK points to the deprecated 'orders' table while actual orders live in unreferenced 'orders_v2', and the column is nullable so orphaned/parentless line items are possible.", flag: true },
        { name: "product_id", type: "bigint", doc: "References the purchased product in 'products' but has no enforced FK and is nullable, so dangling or missing product references can occur silently.", flag: true },
        { name: "qty", type: "integer", doc: "Quantity of the product ordered, defaults to 1 but is nullable so a null could be misread as zero or missing data by downstream aggregations.", flag: true },
        { name: "unit_price_cents", type: "integer", doc: "Price per unit stored as an integer in cents (avoiding float rounding issues) but is nullable with no associated currency field, so a null or missing currency context can silently corrupt total calculations.", flag: true }
      ],
    },
    {
      name: "orders", rows: 3, status: "critical", pos: { x: 730, y: 90 },
      readsPerDay: 42, writesPerDay: 3,
      doc: "The `orders` table is a legacy order-header table (only 3 rows, 3 writes/day) that appears to have been superseded by `orders_v2` \u2014 the `order_items.order_id` foreign key is documented as broken because it still targets this deprecated table while live order data has moved to `orders_v2`. Treat any read from this table as potentially stale; new integrations should confirm with the data owner whether `orders_v2` is now the source of truth before building on `orders`. The only observed `status` value is `completed`, but the column has no enum/check constraint so other free-text values could appear undetected.",
      issues: ["order_items.order_id FK is broken/points at this deprecated orders table instead of orders_v2, meaning order line-item joins here can silently return stale or incomplete data", "status is unconstrained free text with only 'completed' observed in samples \u2014 no CHECK constraint or enum to prevent typos or undocumented states", "user_id is nullable despite being a FK to users, allowing orphaned or user-less order rows", "total is nullable with no currency/unit column, risking NULL-as-zero bugs in revenue aggregation", "created_at is nullable even though it has a now() default, so explicit NULL inserts can break chronological ordering/audit trails", "Table is nearly empty (3 rows) with very low write volume relative to an active orders system, consistent with it being deprecated in favor of orders_v2 \u2014 reads_per_day (42) far exceeding writes (3) suggests consumers may be querying stale data unaware of the migration"],
      columns: [
        { name: "id", type: "bigint", doc: "Auto-incrementing bigint primary key generated from the orders_id_seq sequence; standard surrogate key with no known issues." },
        { name: "user_id", type: "bigint", doc: "Bigint FK to users.id (enforced at the DB level) but nullable, so order rows can exist without an associated user \u2014 check for orphaned/guest records before assuming referential completeness.", flag: true },
        { name: "total", type: "numeric", doc: "Order total stored as numeric (correctly avoiding float rounding issues for money), but nullable and lacking any currency column, so NULL vs 0 and currency unit must be inferred from context.", flag: true },
        { name: "status", type: "text", doc: "Free-text order status with no CHECK/enum constraint; only 'completed' has been observed in live data, so any other value written here is unvalidated and could indicate a typo or an undocumented state.", flag: true },
        { name: "created_at", type: "timestamp with time zone", doc: "Timestamptz order-creation time defaulting to now() at insert, but the column is nullable so explicit NULLs are possible and would break time-based sorting/reporting.", flag: true }
      ],
    },
    {
      name: "orders_v2", rows: 17, status: "warning", pos: { x: 940, y: 90 },
      readsPerDay: 45, writesPerDay: 17,
      doc: "orders_v2 is the current orders table (note the '_v2' suffix implying a prior schema migration/replacement) tracking purchase/order records tied to a user and workspace, with money stored as integer cents and lifecycle tracked via a single-letter status code. At only ~17 rows with 45 reads/17 writes per day, this is either a very early-stage or low-volume table; all foreign-key-like relationships (user_id, workspace_id, and inbound refs from order_items/payments) are unenforced at the DB level, so referential integrity depends entirely on application code.",
      issues: ["No enforced foreign keys: user_id -> users, workspace_id -> workspaces, and inbound order_items.order_id / payments.order_id -> orders_v2.id are all unenforced, risking orphaned rows on either side.", "status is a free-text column with no CHECK constraint or enum; observed codes are 'c', 'p', 'r', 'x' with no documented mapping stored in-schema, so meaning relies entirely on tribal knowledge.", "user_id and workspace_id are nullable, making it unclear if an order can legitimately exist without an owner or workspace, or if this is just missing-data drift.", "amount_cents and status have no default/not-null guarantee beyond status's default, so amount_cents can be NULL, which is ambiguous for a monetary field (NULL vs 0).", "Table name suggests a v1->v2 migration; no indication of what changed or whether a legacy 'orders' table still exists/needs deprecation cleanup.", "meta jsonb column is untyped/unvalidated, so its structure can drift silently across rows with no schema enforcement."],
      columns: [
        { name: "id", type: "bigint", doc: "Auto-incrementing bigint primary key generated from the orders_v2_id_seq sequence." },
        { name: "user_id", type: "bigint", doc: "Nullable bigint intended to reference users.id, but the relationship is unenforced so orphaned or missing references are possible.", flag: true },
        { name: "workspace_id", type: "bigint", doc: "Nullable bigint intended to reference workspaces.id, but the relationship is unenforced so orphaned or missing references are possible.", flag: true },
        { name: "amount_cents", type: "integer", doc: "Order total stored as an integer count of cents (not a float), but is nullable so NULL must be handled distinctly from a zero-amount order.", flag: true },
        { name: "status", type: "text", doc: "Single-letter unconstrained status code defaulting to 'p'; observed values are 'p' (pending), 'c' (completed), 'r' (refunded), and 'x' (canceled/void) based on sampled data, but no DB constraint prevents other values.", flag: true },
        { name: "meta", type: "jsonb", doc: "Freeform jsonb column for arbitrary order metadata with no schema validation, so structure may vary row to row.", flag: true },
        { name: "created_at", type: "timestamp with time zone", doc: "Timestamptz defaulting to now() at insert time, marking when the order row was created." }
      ],
    },
    {
      name: "payments", rows: 11, status: "warning", pos: { x: 100, y: 240 },
      readsPerDay: 43, writesPerDay: 11,
      doc: "The payments table records payment attempts against orders, tracking Stripe event references, amounts, and settlement state; it's a tiny table (~11 rows, 43 reads/day, 11 writes/day) suggesting it's either new, low-volume, or a staging/test table. The observed state values are 'succeeded' (payment captured) and 'refunded' (payment reversed) \u2014 note there is no enforced constraint preventing other free-text values, and no 'failed' or 'pending' state has been observed despite being a plausible payment lifecycle stage. The order_id link to orders_v2 is NOT enforced by a foreign key, and the naming (orders_v2) hints at a prior schema migration that this table may or may not have been updated to fully align with.",
      issues: ["order_id \u2192 orders_v2 relationship is not enforced by a FK, allowing orphaned or invalid payment-order links", "state is a free-text column with no CHECK constraint or enum type; only 'succeeded' and 'refunded' observed but any string could be inserted", "amount_cents stored as integer with no currency column \u2014 assumes a single implicit currency and unit (cents), which is fragile if multi-currency support is ever added", "no updated_at column, so state transitions (e.g. succeeded \u2192 refunded) are not timestamped or auditable", "stripe_event_id has no uniqueness constraint, risking duplicate processing of the same Stripe webhook event", "order_id, stripe_event_id, amount_cents, and state are all nullable, allowing incomplete/garbage payment rows with no order or amount", "table name 'orders_v2' suggests a past migration; unclear if payments.order_id was updated to match the v2 schema or still references a legacy table"],
      columns: [
        { name: "id", type: "bigint", doc: "Auto-incrementing primary key for the payment record." },
        { name: "order_id", type: "bigint", doc: "References orders_v2.id but has no enforced foreign key, so referential integrity is not guaranteed at the DB level.", flag: true },
        { name: "stripe_event_id", type: "text", doc: "Stripe's event identifier for this payment/refund, nullable and not enforced unique, so duplicate webhook deliveries could create duplicate rows.", flag: true },
        { name: "amount_cents", type: "integer", doc: "Payment amount stored as an integer in cents (not dollars/float), with no accompanying currency column.", flag: true },
        { name: "state", type: "text", doc: "Free-text payment status; observed values are 'succeeded' (payment captured) and 'refunded' (payment reversed), with no DB-level constraint stopping other values.", flag: true },
        { name: "created_at", type: "timestamp with time zone", doc: "Timestamp (with timezone) the payment row was created, defaulting to now(); no updated_at exists to track later state changes like refunds.", flag: true }
      ],
    },
    {
      name: "product_catalog_old", rows: 1, status: "critical", pos: { x: 310, y: 240 },
      readsPerDay: 0, writesPerDay: 1,
      doc: "This is a legacy, essentially abandoned product catalog table (1 row, zero reads/day, only a single write ever recorded) that appears to have been superseded by a newer catalog table given the '_old' suffix; it stores basic product/plan info (name, price, category) with no primary key or constraints. New engineers should treat this as a deprecated artifact not to build new features against, and confirm with the team whether it can be archived or dropped.",
      issues: ["No primary key defined despite having a 'pid' column that looks intended as one \u2014 pid is not marked primaryKey and is nullable, so uniqueness/referential integrity cannot be enforced", "'price' stored as double precision (float) instead of a fixed-point/decimal or integer-cents type, risking rounding errors in monetary calculations", "All columns (pid, name, price, cat) are nullable with no NOT NULL constraints or defaults, allowing incomplete/garbage rows", "Table name suffix '_old' combined with 0 reads/day and only 1 approx row strongly suggests this is a deprecated/orphaned table that should be archived or dropped rather than left live", "'cat' is an unconstrained free-text enum-like column (sampled value 'plans') with no lookup table or CHECK constraint, so valid categories are undocumented", "No relationships/foreign keys defined at all, so this table is fully disconnected from the rest of the schema and can't be joined reliably"],
      columns: [
        { name: "pid", type: "integer", doc: "Likely intended as the product identifier / primary key, but it is not enforced as one and is nullable, so it cannot be relied upon for uniqueness or joins.", flag: true },
        { name: "name", type: "character varying", doc: "Free-text product/plan name; the only observed value is 'Pro Plan', consistent with this table being a stale snapshot of plan data." },
        { name: "price", type: "double precision", doc: "Product price stored as a double precision float, which is unsafe for exact monetary arithmetic and should be decimal/numeric or integer cents instead.", flag: true },
        { name: "cat", type: "character varying", doc: "Free-text category code with no enforced value set; the only observed value 'plans' indicates this row represents a subscription plan, not a physical product.", flag: true }
      ],
    },
    {
      name: "products", rows: 4, status: "warning", pos: { x: 520, y: 240 },
      readsPerDay: 43, writesPerDay: 4,
      doc: "Tiny catalog table (4 rows) holding the products/plans that can be sold \u2014 subscription plans (PLN-*) and add-ons (ADD-SEAT) \u2014 referenced by order_items.product_id via an unenforced FK. `active` (sampled False/True) gates whether a SKU is purchasable; the 'PLN-LEGACY' row shows the convention of marking retired plans by appending '(discontinued)' to the title rather than using a status column, so `active=false` combined with title text is currently the only deprecation signal. price_cents stores money as integer cents, not a float, which is correct but must be respected by any code doing arithmetic on it.",
      issues: ["order_items.product_id -> products.id relationship is not DB-enforced (no real foreign key), so orphaned or invalid product_id values are possible", "sku, title, price_cents, active, and created_at are all nullable despite being effectively required for a functioning catalog row", "no unique constraint documented on sku, so duplicate SKUs are not prevented at the schema level", "product deprecation is signaled informally via title text ('(discontinued)') plus active=false instead of a dedicated status/lifecycle column, which is easy to miss or mis-filter on", "no updated_at column, so price or title changes (e.g., price_cents edits) are not auditable"],
      columns: [
        { name: "id", type: "bigint", doc: "Auto-incrementing bigint primary key generated from products_id_seq." },
        { name: "sku", type: "text", doc: "Human-assigned product code (e.g. 'PLN-PRO', 'ADD-SEAT'); nullable and with no enforced uniqueness despite acting as the natural business key.", flag: true },
        { name: "title", type: "text", doc: "Display name of the product; note the observed convention of appending '(discontinued)' to titles of retired plans like 'Legacy Solo Plan (discontinued)' instead of a dedicated status field.", flag: true },
        { name: "price_cents", type: "integer", doc: "Price stored as an integer number of cents (not a float), but nullable so missing pricing is possible for a listed product.", flag: true },
        { name: "active", type: "boolean", doc: "Boolean gate (observed values True/False) controlling whether the product is currently purchasable; defaults to true and is the primary \u2014 but informal \u2014 deprecation flag.", flag: true },
        { name: "created_at", type: "timestamp with time zone", doc: "Timestamptz defaulting to now() marking row creation; there is no corresponding updated_at to track later edits.", flag: true }
      ],
    },
    {
      name: "sessions", rows: 0, status: "warning", pos: { x: 730, y: 240 },
      readsPerDay: 1, writesPerDay: 0,
      doc: "The sessions table stores active login session tokens mapping to users, with an expiration timestamp for session invalidation. The table currently has approximately 0 rows and sees only 1 read/day and 0 writes/day, suggesting this feature is unused, deprecated, or not yet fully wired into the application. A new engineer should verify whether session management has moved to a different mechanism (e.g. JWT, external auth provider, or another table) before building on this.",
      issues: ["user_id is nullable despite being enforced as a foreign key to users, allowing orphaned/anonymous sessions with no owning user", "expires_at is nullable, meaning sessions can exist with no expiration -- a potential security risk if application code doesn't defensively handle null as 'never expires'", "No created_at/issued_at timestamp column, making it impossible to audit when a session was created or how long it has been alive", "Zero writes/day and ~0 rows with only 1 read/day strongly suggests this table is dead or orphaned functionality rather than actively used session storage", "No index/uniqueness note on user_id despite it being a common lookup pattern (e.g. 'find all sessions for user') beyond the token primary key"],
      columns: [
        { name: "token", type: "text", doc: "Primary key; the opaque session token string presented by the client to authenticate a request." },
        { name: "user_id", type: "bigint", doc: "Foreign key to users.id identifying the session owner, but nullable so some sessions may have no associated user -- confirm this is intentional (e.g. pre-auth sessions) and not a data gap.", flag: true },
        { name: "expires_at", type: "timestamp with time zone", doc: "Timestamp (with time zone) after which the session should be treated as invalid; being nullable means some sessions may never expire unless application logic enforces a default.", flag: true }
      ],
    },
    {
      name: "stripe_events", rows: 5, status: "warning", pos: { x: 940, y: 240 },
      readsPerDay: 1, writesPerDay: 5,
      doc: "Stores raw incoming Stripe webhook events for idempotency tracking and audit/debugging purposes, keyed by Stripe's own event ID (e.g. evt_1QaA). At only ~5 rows with 5 writes/day and 1 read/day, this table sees essentially no real-world volume yet, suggesting it's either newly deployed or Stripe integration is in early/test stage. Any consumer must treat 'payload' as the sole source of truth for event type and data since no columns decompose it (no event_type, no processed/status flag).",
      issues: ["No 'event_type' or 'type' column extracted from payload, forcing any query filtering by event kind to do jsonb parsing on every read", "No processing/status column (e.g. processed_at, status) to track whether the event was consumed by downstream logic, risking duplicate or missed processing", "payload is nullable, meaning an event row can exist with no actual data, which is nonsensical for a webhook log and likely indicates missing NOT NULL constraint", "received_at is nullable despite having a now() default, so it can still be explicitly set to NULL, undermining its use as a reliable audit timestamp", "No relationships/foreign keys to other tables (e.g. customers, subscriptions, invoices) despite Stripe events typically referencing such objects, making cross-referencing require manual jsonb path extraction", "No index or column for Stripe's own event 'type' or 'created' timestamp (as opposed to received_at, which is this system's ingestion time, not Stripe's event time), risking confusion between when Stripe generated the event and when this system recorded it"],
      columns: [
        { name: "id", type: "text", doc: "Primary key storing Stripe's native event ID string (prefix 'evt_'), used directly for webhook idempotency checks." },
        { name: "payload", type: "jsonb", doc: "Full raw JSON body of the Stripe webhook event; nullable, so downstream code must not assume event data is always present.", flag: true },
        { name: "received_at", type: "timestamp with time zone", doc: "Timestamp this system ingested the webhook, defaulting to now() but nullable and distinct from Stripe's own event-creation timestamp embedded in payload.", flag: true }
      ],
    },
    {
      name: "tmp_backfill_20250811", rows: 0, status: "warning", pos: { x: 100, y: 390 },
      readsPerDay: 0, writesPerDay: 0,
      doc: "This is a one-off temporary backfill table (name-dated 2025-08-11) that dumps arbitrary rows as opaque jsonb blobs, with zero reads/writes and zero rows currently \u2014 indicating the backfill job it supported has already completed or was abandoned. It has no primary key, no relationships, and no schema on its payload, so it should never be treated as a source of truth or referenced by application code. New engineers should confirm the backfill is fully migrated/verified and then drop this table rather than build anything on top of it.",
      issues: ["No primary key defined, making rows non-addressable and preventing dedup or safe partial updates", "orphan_candidate flag is true and table has 0 reads/writes/rows, strongly suggesting it's dead and should be dropped", "Table name is date-stamped ('tmp_backfill_20250811'), a naming pattern indicating intended temporary/one-time use, not a permanent schema object", "row_data is an unstructured jsonb blob with no schema, constraints, or documentation of expected keys/types", "No relationships to any other table, so provenance of the backfilled data (which table/rows it came from) is untracked", "No timestamp columns (created_at/updated_at) to establish freshness or lifecycle of the backfill data"],
      columns: [
        { name: "row_data", type: "jsonb", doc: "Unstructured jsonb payload holding whatever data was captured during the 2025-08-11 backfill, with no enforced schema, no sample values observed, and no documented key structure.", flag: true }
      ],
    },
    {
      name: "user_prefs", rows: 2, status: "warning", pos: { x: 310, y: 390 },
      readsPerDay: 0, writesPerDay: 2,
      doc: "Stores per-user preference blobs as opaque JSONB, keyed loosely by user_id, with an updated timestamp; at ~2 rows and 2 writes/day with zero reads, this table is essentially unused/vestigial in current workloads and has no primary key or enforced foreign key to users. Any agent modifying this data must treat prefs as a schemaless JSON document with no documented shape, and must not assume referential integrity to the users table.",
      issues: ["No primary key defined on user_prefs, so duplicate rows per user_id are possible and upserts cannot rely on a unique constraint.", "user_id -> users relationship is not enforced by a foreign key, allowing orphaned rows if a user is deleted.", "All columns (user_id, prefs, updated) are nullable, so rows with null user_id or null prefs are permitted and could silently break lookups.", "prefs is unstructured jsonb with no schema/validation, making it easy for writers to introduce inconsistent or malformed preference keys over time.", "updated has no default (e.g., no default now() or trigger), so it can be null or stale if application code forgets to set it on write.", "reads_per_day is 0 despite writes_per_day of 2, suggesting this table may be dead/orphaned functionality worth confirming before further investment."],
      columns: [
        { name: "user_id", type: "bigint", doc: "Intended foreign key to users.id, but the relationship is unenforced and the column is nullable, so integrity depends entirely on application code.", flag: true },
        { name: "prefs", type: "jsonb", doc: "Opaque JSONB blob holding arbitrary user preference data with no enforced schema or documented key structure.", flag: true },
        { name: "updated", type: "timestamp with time zone", doc: "Timestamptz meant to record last modification time, but has no default value so it relies on the application to set it correctly on every write.", flag: true }
      ],
    },
    {
      name: "users", rows: 7, status: "warning", pos: { x: 520, y: 390 },
      readsPerDay: 49, writesPerDay: 7,
      doc: "Core users table (only 7 rows \u2014 likely a demo/early-stage tenant) storing account identity, plan tier, and Stripe billing linkage; referenced by orders, sessions, and several unenforced FKs across the schema. New engineers must know that `plan` is an unconstrained free-text enum ('free'/'pro'/'team') with no CHECK constraint, and that only 4 of 7 users have a `stripe_customer_id`, meaning paid-plan status and billing ID presence are not guaranteed to be in sync.",
      issues: ["plan column is unconstrained text acting as an enum ('free', 'pro', 'team' observed) \u2014 no CHECK constraint or lookup table prevents typos or new invalid values", "name has duplicate/drifted entries for the same person (e.g. 'Maya C.' vs 'Maya Chen'), indicating no normalization or dedup logic on write", "stripe_customer_id is nullable with no uniqueness constraint enforced at the DB level shown here, and only a subset of users have one, so billing joins must handle NULLs explicitly", "Only 2 of 6 downstream relationships (orders, sessions) are enforced FKs; analytics_events.uid, orders_v2.user_id, user_prefs.user_id, and workspaces.ownerId all reference users without DB-level enforcement, risking orphaned rows", "workspaces.ownerId uses camelCase while every other relationship uses snake_case (user_id), indicating naming drift likely from a different service/ORM", "orders_v2 existing alongside orders suggests a migration in progress; unclear which is canonical, risking split/duplicated order data tied to this users table", "created_at is nullable despite having a now() default, so backfilled or bulk-inserted rows could have NULL timestamps"],
      columns: [
        { name: "id", type: "bigint", doc: "Auto-incrementing bigint surrogate primary key generated via users_id_seq." },
        { name: "email", type: "text", doc: "User's login/contact email, appears unique in samples but no explicit uniqueness constraint is shown here.", flag: true },
        { name: "name", type: "text", doc: "Nullable display name that shows drift for the same user (e.g. 'Maya C.' vs 'Maya Chen'), so it should not be used as a dedup key.", flag: true },
        { name: "plan", type: "text", doc: "Free-text subscription tier defaulting to 'free', observed values are exactly 'free', 'pro', and 'team' with no DB-level constraint restricting future values.", flag: true },
        { name: "stripe_customer_id", type: "text", doc: "Nullable Stripe customer reference populated only for paying users (4 of 7 sampled), so code must null-check before billing lookups.", flag: true },
        { name: "created_at", type: "timestamp with time zone", doc: "Timestamptz defaulting to now() at insert time, but nullable so historical/backfilled rows may lack a value.", flag: true }
      ],
    },
    {
      name: "workspaces", rows: 3, status: "warning", pos: { x: 730, y: 390 },
      readsPerDay: 42, writesPerDay: 3,
      doc: "The workspaces table represents tenant/workspace containers that group orders and are owned by a user; at only ~3 rows and 42 reads/day it's a small, low-write reference table likely used for multi-tenancy scoping. Both its relationships (ownerId -> users, orders_v2.workspace_id -> workspaces) are application-level only, not enforced by DB constraints, so referential integrity depends entirely on app logic.",
      issues: ["ownerId has no enforced foreign key to users; orphaned or invalid owner references are possible", "orders_v2.workspace_id -> workspaces relationship is not enforced, so orders could reference a deleted or nonexistent workspace", "ownerId is nullable with no default, allowing ownerless workspaces with no documented meaning for null", "name is nullable with no default and no uniqueness constraint, so duplicate or blank workspace names are possible", "createdAt is nullable despite having a now() default, so backfilled or bulk-inserted rows could have NULL creation timestamps"],
      columns: [
        { name: "id", type: "bigint", doc: "Auto-incrementing primary key generated from workspaces_id_seq, used as the stable identifier referenced (informally) by orders_v2.workspace_id." },
        { name: "ownerId", type: "bigint", doc: "Intended foreign key to users.id identifying the workspace owner, but nullable and unenforced at the DB level, so it can silently point to a missing or deleted user or be left NULL.", flag: true },
        { name: "name", type: "text", doc: "Human-readable workspace label (e.g. 'Drift Labs', 'Lee Sandbox', 'Northwind'); nullable with no uniqueness constraint so duplicates or NULLs are possible.", flag: true },
        { name: "createdAt", type: "timestamp with time zone", doc: "Timestamptz defaulting to now() at insert time, but still nullable so historical or migrated rows may lack a creation timestamp.", flag: true }
      ],
    }
  ],
  edges: [
    { from: "orders", to: "users", enforced: true },
    { from: "order_items", to: "orders", enforced: true, broken: true, note: "FK targets deprecated table; live data is in orders_v2" },
    { from: "sessions", to: "users", enforced: true },
    { from: "analytics_events", to: "users", enforced: false },
    { from: "order_items", to: "orders_v2", enforced: false },
    { from: "order_items", to: "products", enforced: false },
    { from: "orders_v2", to: "users", enforced: false },
    { from: "orders_v2", to: "workspaces", enforced: false },
    { from: "payments", to: "orders_v2", enforced: false },
    { from: "user_prefs", to: "users", enforced: false },
    { from: "workspaces", to: "users", enforced: false }
  ],
};

// Canned agent answers — identical in substance to what the MCP server
// returns, so the UI console and a live Claude-over-MCP session tell the
// same story. Hand-authored narrative copy (pipeline/render_dashboard_data.py
// docstring), not derived from the catalog, except the health/FK-coverage
// figures quoted below, which are filled in from the real catalog.
export const agentAnswers = [
  {
    match: ["status", "orders_v2"],
    q: "What does orders_v2.status mean?",
    a: "orders_v2.status uses magic single-character values: 'p' = pending, 'c' = complete, 'x' = cancelled, 'r' = refunded. There is no CHECK constraint \u2014 values are enforced only in app code. Note: this is one of THREE status vocabularies in this schema (legacy orders uses full words like 'completed'; payments uses Stripe's 'succeeded'/'refunded'). For revenue, filter status = 'c'.",
  },
  {
    match: ["drop", "safe"],
    q: "Which tables are safe to drop?",
    a: "Two candidates. (1) tmp_backfill_20250811 \u2014 empty scratch table from a one-off script, unreferenced, drop immediately. (2) product_catalog_old \u2014 zero reads in 90 days, superseded by products; archive then drop. NOT safe: legacy `orders` \u2014 it looks dead (0 writes) but order_items.order_id still holds an enforced FK to it. Re-point that FK to orders_v2 first.",
  },
  {
    match: ["revenue"],
    q: "Where does revenue come from?",
    a: "Revenue lives in orders_v2.amount_cents filtered to status='c' (complete), cross-checked against payments.amount_cents where state='succeeded'. Caveats: amounts are in cents (legacy orders used dollar numerics \u2014 don't union them naively), refunds appear as status='r' in orders_v2 AND state='refunded' in payments, and the payments\u2194orders_v2 join is unenforced (no FK), so expect stragglers.",
  },
  {
    match: ["join", "analytics", "users"],
    q: "How do I join analytics_events to users?",
    a: "analytics_events.uid is users.id under a drifted name (no FK). Join: analytics_events.uid = users.id. Timestamp caution: analytics_events.ts is unix epoch seconds, so use to_timestamp(ts) before comparing against timestamptz columns like users.created_at.",
  },
  {
    match: ["order_items", "empty"],
    q: "Why is order_items empty?",
    a: "order_items.order_id has an enforced FK to the DEPRECATED orders table, not orders_v2. Inserts with v2 order ids violate the constraint, so app code worked around it by stuffing line items into orders_v2.meta. Fix: re-point the FK to orders_v2, backfill from meta, then delete the workaround. This is the highest-priority integrity bug in the schema.",
  },
  {
    match: ["health", "worst", "risk"],
    q: "What are the biggest risks in this schema?",
    a: "Health score 45/100. Top risks: (1) order_items FK points at a deprecated table \u2014 line-item data is hiding in a jsonb blob; (2) FK coverage is 27% \u2014 several tables have unenforced joins; (3) multiple competing status vocabularies invite mis-filtered revenue queries; (4) users.email has no unique index; (5) stripe_events grows unboundedly with no retention policy.",
  },
];
