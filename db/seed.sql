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
-- ---------------------------------------------------------------------------
INSERT INTO users (email, name, plan, stripe_customer_id) VALUES
 ('maya@driftlabs.io',  'Maya Chen',    'team', 'cus_QX81'),
 ('sam@driftlabs.io',   'Sam Ortiz',    'pro',  'cus_QX82'),
 ('lee@solofounder.dev','Lee Park',     'free', NULL),
 ('ana@driftlabs.io',   'Ana Gupta',    'pro',  'cus_QX84');

INSERT INTO user_prefs (user_id, prefs, updated) VALUES
 (1, '{"theme":"dark","digest":"daily","beta":true}', now()),
 (3, '{"theme":"light","digest":"off"}', now());

INSERT INTO workspaces ("ownerId", name) VALUES
 (1, 'Drift Labs'), (3, 'Lee Sandbox');

INSERT INTO orders (user_id, total, status) VALUES
 (1, 49.00, 'completed'), (2, 190.00, 'completed');

INSERT INTO orders_v2 (user_id, workspace_id, amount_cents, status, meta) VALUES
 (1, 1, 4900,  'c', '{"src":"web"}'),
 (2, 1, 19000, 'c', '{"src":"api","coupon":"LAUNCH20"}'),
 (3, 2, 900,   'p', '{"src":"web"}'),
 (4, 1, 4900,  'x', '{"src":"web","reason":"duplicate"}'),
 (1, 1, 12000, 'r', '{"src":"api"}');

INSERT INTO products (sku, title, price_cents) VALUES
 ('PLN-PRO',  'Pro Plan (monthly)',  4900),
 ('PLN-TEAM', 'Team Plan (monthly)', 19000),
 ('ADD-SEAT', 'Extra seat',           900);

INSERT INTO product_catalog_old (pid, name, price, cat) VALUES
 (1, 'Pro Plan', 49.0, 'plans');

INSERT INTO payments (order_id, stripe_event_id, amount_cents, state) VALUES
 (1, 'evt_1QaA', 4900,  'succeeded'),
 (2, 'evt_1QaB', 19000, 'succeeded'),
 (5, 'evt_1QaC', 12000, 'refunded');

INSERT INTO stripe_events (id, payload) VALUES
 ('evt_1QaA', '{"type":"payment_intent.succeeded","amount":4900}'),
 ('evt_1QaB', '{"type":"payment_intent.succeeded","amount":19000}'),
 ('evt_1QaC', '{"type":"charge.refunded","amount":12000}');

INSERT INTO analytics_events (uid, event, props, ts) VALUES
 (1, 'page_view',   '{"path":"/dashboard"}', 1751500000),
 (1, 'run_report',  '{"report":"weekly"}',   1751503600),
 (3, 'page_view',   '{"path":"/pricing"}',   1751507200);

INSERT INTO feature_flags (flag, enabled, rollout) VALUES
 ('new_billing_page', true,  '{"pct":100}'),
 ('agent_context_api', false, '{"pct":10,"allow":[1]}');
