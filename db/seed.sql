-- StackAtlas demo database: a deliberately "vibe-coded" SaaS schema.
-- Realistic mess: naming drift, missing FKs, orphaned tables, magic status
-- values, mixed timestamp conventions, undocumented jsonb blobs.
-- Usage: createdb vibeshop && psql vibeshop -f seed.sql

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL,                      -- no unique index (bug waiting to happen)
    name TEXT,
    plan TEXT DEFAULT 'free',                 -- 'free' | 'pro' | 'team' (undocumented)
    stripe_customer_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- No FK to users. jsonb blob nobody remembers the shape of.
CREATE TABLE user_prefs (
    user_id BIGINT,
    prefs JSONB,
    updated TIMESTAMPTZ
);

-- camelCase drift: an AI codegen session created this one.
CREATE TABLE workspaces (
    id BIGSERIAL PRIMARY KEY,
    "ownerId" BIGINT,                         -- should be FK to users.id
    name TEXT,
    "createdAt" TIMESTAMPTZ DEFAULT now()
);

-- LEGACY: replaced by orders_v2 in Aug 2025, never dropped.
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    total NUMERIC(10,2),
    status TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- The "real" orders table. Magic single-char status values.
CREATE TABLE orders_v2 (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,                           -- FK dropped during a hotfix migration
    workspace_id BIGINT,
    amount_cents INTEGER,
    status TEXT DEFAULT 'p',                  -- 'p'=pending 'c'=complete 'x'=cancelled 'r'=refunded
    meta JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- BUG: order_id still references legacy orders, not orders_v2.
CREATE TABLE order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT REFERENCES orders(id),
    product_id BIGINT,
    qty INTEGER DEFAULT 1,
    unit_price_cents INTEGER
);

CREATE TABLE products (
    id BIGSERIAL PRIMARY KEY,
    sku TEXT,
    title TEXT,
    price_cents INTEGER,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Orphan: zero reads since the catalog migration.
CREATE TABLE product_catalog_old (
    pid INTEGER,
    name VARCHAR(255),
    price FLOAT,                              -- float for money (!)
    cat VARCHAR(64)
);

-- No FK to orders_v2; reconciliation happens "in the app".
CREATE TABLE payments (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT,
    stripe_event_id TEXT,
    amount_cents INTEGER,
    state TEXT,                               -- yet another status vocabulary
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Raw webhook dumps. 40MB of jsonb and growing.
CREATE TABLE stripe_events (
    id TEXT PRIMARY KEY,
    payload JSONB,
    received_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE sessions (
    token TEXT PRIMARY KEY,
    user_id BIGINT REFERENCES users(id),
    expires_at TIMESTAMPTZ
);

-- Epoch-integer timestamps while everything else is timestamptz.
CREATE TABLE analytics_events (
    id BIGSERIAL PRIMARY KEY,
    uid BIGINT,                               -- means user_id, named differently
    event TEXT,
    props JSONB,
    ts BIGINT                                 -- unix epoch seconds
);

CREATE TABLE feature_flags (
    flag TEXT PRIMARY KEY,
    enabled BOOLEAN DEFAULT false,
    rollout JSONB
);

-- Junk left behind by a one-off backfill script.
CREATE TABLE tmp_backfill_20250811 (
    row_data JSONB
);

-- ---------------------------------------------------------------------------
-- Seed data (small but query-able)
--
-- Hardened per EVAL_AND_BASELINE_PLAN.md so every trap yields a CLEARLY wrong
-- baseline number instead of a coincidental match:
--   1. legacy orders.total values are stale/disjoint from any orders_v2-based
--      figure (were 49+190=239, same as the correct answer — now 99+250+15).
--   2. order_items stays empty (real line items live in orders_v2.meta) —
--      powers the flagship order_items -> orders (legacy) trap.
--   3. orders_v2 has 17 rows across all 4 statuses and 3 workspaces so
--      cents-vs-dollars and status-code errors produce distinctive wrong
--      totals, not near-misses.
-- ---------------------------------------------------------------------------
-- Signup dates spread across several days so "signups per day" has real
-- variety instead of one INSERT-time timestamp for every row.
INSERT INTO users (email, name, plan, stripe_customer_id, created_at) VALUES
 ('maya@driftlabs.io',  'Maya Chen',    'team', 'cus_QX81', '2026-08-20 09:12:00+00'),
 ('sam@driftlabs.io',   'Sam Ortiz',    'pro',  'cus_QX82', '2026-08-20 14:03:00+00'),
 ('lee@solofounder.dev','Lee Park',     'free', NULL,       '2026-08-22 08:47:00+00'),
 ('ana@driftlabs.io',   'Ana Gupta',    'pro',  'cus_QX84', '2026-08-22 19:30:00+00'),
 ('kai@northwind.io',   'Kai Fischer',  'team', 'cus_QX90', '2026-08-25 11:05:00+00'),
 ('priya@northwind.io', 'Priya Nair',   'free', NULL,       '2026-08-25 16:52:00+00'),
 -- duplicate signup: same email re-registered via a second OAuth provider.
 -- No unique index on users.email, so both rows live forever.
 ('maya@driftlabs.io',  'Maya C.',      'free', NULL,       '2026-08-27 10:18:00+00');

INSERT INTO user_prefs (user_id, prefs, updated) VALUES
 (1, '{"theme":"dark","digest":"daily","beta":true}', now()),
 (3, '{"theme":"light","digest":"off"}', now());

INSERT INTO workspaces ("ownerId", name) VALUES
 (1, 'Drift Labs'), (3, 'Lee Sandbox'), (5, 'Northwind');

-- Legacy totals are stale numbers unrelated to any orders_v2 figure — an
-- agent that sums this table instead of orders_v2 gets a visibly wrong,
-- not-almost-right, number.
INSERT INTO orders (user_id, total, status) VALUES
 (1, 99.00, 'completed'), (2, 250.00, 'completed'), (3, 15.00, 'completed');

INSERT INTO orders_v2 (user_id, workspace_id, amount_cents, status, meta) VALUES
 (1, 1, 4900,  'c', '{"src":"web"}'),
 (2, 1, 19000, 'c', '{"src":"api","coupon":"LAUNCH20"}'),
 (3, 2, 900,   'p', '{"src":"web"}'),
 (4, 1, 4900,  'x', '{"src":"web","reason":"duplicate"}'),
 (1, 1, 12000, 'r', '{"src":"api"}'),
 (5, 3, 19000, 'c', '{"src":"web"}'),
 (6, 3, 900,   'p', '{"src":"web"}'),
 (2, 1, 4900,  'c', '{"src":"web"}'),
 (4, 1, 900,   'c', '{"src":"web","coupon":"SEAT1"}'),
 (5, 3, 4900,  'x', '{"src":"web","reason":"payment_failed"}'),
 (1, 1, 19000, 'c', '{"src":"api"}'),
 (6, 3, 12000, 'r', '{"src":"web"}'),
 (3, 2, 4900,  'c', '{"src":"web"}'),
 (2, 1, 900,   'x', '{"src":"web","reason":"test_order"}'),
 (5, 3, 19000, 'p', '{"src":"api"}'),
 (4, 1, 12000, 'c', '{"src":"web","coupon":"LAUNCH20"}'),
 (1, 1, 4900,  'r', '{"src":"web"}');

-- One inactive product so "active products" is a real filter, not a no-op.
INSERT INTO products (sku, title, price_cents, active) VALUES
 ('PLN-PRO',  'Pro Plan (monthly)',  4900,  true),
 ('PLN-TEAM', 'Team Plan (monthly)', 19000, true),
 ('ADD-SEAT', 'Extra seat',           900,  true),
 ('PLN-LEGACY', 'Legacy Solo Plan (discontinued)', 2900, false);

INSERT INTO product_catalog_old (pid, name, price, cat) VALUES
 (1, 'Pro Plan', 49.0, 'plans');

-- Canonical refund source: payments.state='refunded', keyed to the orders_v2
-- row it refunds via order_id. orders_v2.status='r' flags the SAME event
-- from the order's point of view — summing both double-counts a refund.
INSERT INTO payments (order_id, stripe_event_id, amount_cents, state) VALUES
 (1, 'evt_1QaA', 4900,  'succeeded'),
 (2, 'evt_1QaB', 19000, 'succeeded'),
 (5, 'evt_1QaC', 12000, 'refunded'),
 (6, 'evt_1QaD', 19000, 'succeeded'),
 (8, 'evt_1QaE', 4900,  'succeeded'),
 (9, 'evt_1QaF', 900,   'succeeded'),
 (11,'evt_1QaG', 19000, 'succeeded'),
 (12,'evt_1QaH', 12000, 'refunded'),
 (13,'evt_1QaI', 4900,  'succeeded'),
 (16,'evt_1QaJ', 12000, 'succeeded'),
 (17,'evt_1QaK', 4900,  'refunded');

INSERT INTO stripe_events (id, payload) VALUES
 ('evt_1QaA', '{"type":"payment_intent.succeeded","amount":4900}'),
 ('evt_1QaB', '{"type":"payment_intent.succeeded","amount":19000}'),
 ('evt_1QaC', '{"type":"charge.refunded","amount":12000}'),
 ('evt_1QaD', '{"type":"payment_intent.succeeded","amount":19000}'),
 ('evt_1QaK', '{"type":"charge.refunded","amount":4900}');

-- ts = unix epoch seconds, spanning the same window as users.created_at
-- above (2026-08-20 .. 2026-08-27), but as an integer, not a timestamptz.
INSERT INTO analytics_events (uid, event, props, ts) VALUES
 (1, 'page_view',   '{"path":"/dashboard"}', 1787302320),
 (1, 'run_report',  '{"report":"weekly"}',   1787305920),
 (3, 'page_view',   '{"path":"/pricing"}',   1787475620),
 (5, 'page_view',   '{"path":"/dashboard"}', 1787734820),
 (5, 'run_report',  '{"report":"monthly"}',  1787738420),
 (6, 'page_view',   '{"path":"/pricing"}',   1787756120),
 (2, 'page_view',   '{"path":"/dashboard"}', 1787305920),
 (4, 'page_view',   '{"path":"/billing"}',   1787506200);

INSERT INTO feature_flags (flag, enabled, rollout) VALUES
 ('new_billing_page', true,  '{"pct":100}'),
 ('agent_context_api', false, '{"pct":10,"allow":[1]}');
