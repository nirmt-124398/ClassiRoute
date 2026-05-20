# Implementation Guide — Payments & Billing

> This guide covers what you'd need to implement if you ever want to charge for ClassiRoute usage. For now the project is a hobby — this is a reference for later.

## Architecture Overview

```
User → Makes API call → Request Logged (tokens, tier, model)
                              ↓
                    Metering Service (counts monthly usage)
                              ↓
                    Billing Service (checks quota, calculates invoice)
                              ↓
                    Payment Processor (Stripe / Paddle / LemonSqueezy)
```

## Database Tables to Add

### 1. Usage Records

```sql
CREATE TABLE usage_records (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    virtual_key_id UUID REFERENCES virtual_keys(id) ON DELETE SET NULL,
    month         DATE NOT NULL,  -- first day of billing month
    input_tokens  BIGINT NOT NULL DEFAULT 0,
    output_tokens BIGINT NOT NULL DEFAULT 0,
    request_count INT NOT NULL DEFAULT 0,
    cost_usd      NUMERIC(12,6) NOT NULL DEFAULT 0,
    UNIQUE(user_id, month)
);
```

### 2. Subscriptions / Plans

```sql
CREATE TABLE subscription_plans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,       -- "Free", "Pro", "Enterprise"
    price_monthly   NUMERIC(10,2) NOT NULL,       -- $0, $20, $100
    request_limit   INT,                          -- max requests/month (NULL = unlimited)
    token_limit     BIGINT,                       -- max tokens/month (NULL = unlimited)
    tier_access     INT NOT NULL DEFAULT 2,       -- max tier accessible (0=weak only, 2=all)
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE user_subscriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id         UUID NOT NULL REFERENCES subscription_plans(id),
    stripe_sub_id   VARCHAR(255),                 -- Stripe subscription ID
    status          VARCHAR(50) NOT NULL DEFAULT 'active',  -- active, cancelled, past_due
    current_period_start DATE NOT NULL,
    current_period_end   DATE NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);
```

## Metering (Usage Counting)

Every time `_log()` runs in `api/v1/chat.py`, update the monthly usage counter:

```python
async def increment_usage(db, user_id, input_tokens, output_tokens, cost_usd):
    month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
    
    # Upsert pattern
    stmt = text("""
        INSERT INTO usage_records (user_id, month, input_tokens, output_tokens, request_count, cost_usd)
        VALUES (:uid, :month, :in_tok, :out_tok, 1, :cost)
        ON CONFLICT (user_id, month) DO UPDATE SET
            input_tokens  = usage_records.input_tokens + :in_tok,
            output_tokens = usage_records.output_tokens + :out_tok,
            request_count = usage_records.request_count + 1,
            cost_usd      = usage_records.cost_usd + :cost
    """)
    await db.execute(stmt, {
        "uid": str(user_id), "month": month,
        "in_tok": input_tokens, "out_tok": output_tokens, "cost": cost_usd
    })
    await db.commit()
```

## Rate Limiting by Plan Tier

In `core/dependencies.py`, make rate limits dynamic per user's plan:

```python
PLAN_LIMITS = {
    "free":       {"chat": (20, 60),  "api": (100, 60)},
    "pro":        {"chat": (200, 60), "api": (1000, 60)},
    "enterprise": {"chat": (1000, 60),"api": (5000, 60)},
}
```

## Payment Processor Integration

### Stripe (recommended)

| Endpoint | Purpose |
|---|---|
| `POST /billing/create-checkout` | Create Stripe Checkout Session → redirect to Stripe |
| `POST /billing/webhook` | Stripe webhook receiver (idempotent) |
| `GET /billing/portal` | Redirect to Stripe Customer Portal (manage subscription) |
| `GET /billing/status` | Return current plan + usage stats |

**Webhook events to handle:**
- `checkout.session.completed` → activate subscription
- `customer.subscription.updated` → plan change
- `customer.subscription.deleted` → downgrade to free
- `invoice.payment_failed` → mark past_due, warn user

### Paddle (alternative)

Same pattern but webhooks are `subscription_created`, `subscription_updated`, `subscription_cancelled`.

### LemonSqueezy (simplest)

Same pattern. Fewer webhook events. Best for indie makers.

## Middleware: Check Access Before Routing

Before routing a prompt, check if the user's subscription allows this tier:

```python
async def check_tier_access(virtual_key: VirtualKey, requested_tier: int, db: AsyncSession):
    # Get user's max allowed tier from subscription
    user_sub = await get_active_subscription(db, virtual_key.user_id)
    if user_sub and user_sub.plan.tier_access < requested_tier:
        # Upgrade not possible — user's plan doesn't allow this tier
        raise HTTPException(402, "Upgrade required for this model tier")
```

## Migration Strategy

Since the project uses `Base.metadata.create_all` (no Alembic):

```bash
# 1. Add models to db/models.py
# 2. Run ALTER TABLE / CREATE TABLE manually:
PGPASSWORD=classiroute psql -h localhost -U postgres -d classiroute -f scripts/migration_001_billing.sql

# 3. Or run a Python migration script that executes raw SQL:
python -m scripts.migrate_billing
```

Better long-term: **add Alembic**. Initialize once, then every schema change is a `alembic revision --autogenerate -m "description"`.

## Testing Billing

```python
@pytest.mark.integration
async def test_plan_upgrade_grants_tier_access(jwt_headers, client):
    # 1. Register on free plan
    # 2. Try to access tier 2 model → expect 402
    # 3. Simulate Stripe webhook "subscription_created" for pro plan
    # 4. Try tier 2 again → expect 200
```

## Security Notes

- **Stripe webhooks**: Always verify `stripe-signature` header with your webhook secret
- **Idempotency**: Webhooks may retry — use idempotency keys or `ON CONFLICT DO NOTHING`
- **Never trust client-side tier info**: The model routing decision must be server-enforced
- **Usage data is revenue**: Monitor metering pipeline with alerts if it stops incrementing

## Folder Structure to Add

```
api/v1/
  billing.py        ← Stripe webhooks + checkout + portal
scripts/
  migrate_billing.sql  ← raw SQL for new tables
  seed_plans.sql       ← insert Free/Pro/Enterprise plans
docs/
  implementation-guide.md  ← this file
```

## Dependencies to Add

```toml
dependencies = [
    "stripe>=11.0.0",
]
```
