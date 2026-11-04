-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    telegram_id   BIGINT PRIMARY KEY,
    username      TEXT,
    name          TEXT,
    balance       INTEGER     NOT NULL DEFAULT 0,
    bonus         BOOLEAN     NOT NULL DEFAULT FALSE,
    low_balance   SMALLINT    NOT NULL DEFAULT 0,
    referrer_id   BIGINT,
    last_topup    TIMESTAMPTZ,
    last_charge   TIMESTAMPTZ,
    created       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tariff        TEXT        NOT NULL DEFAULT 'START'
                  CHECK (tariff IN ('START', 'STANDARD', 'PREMIUM')),
    devices SMALLINT NOT NULL DEFAULT 0 CHECK (devices >= 0)
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (LOWER(username));


-- Таблица подписок
CREATE TABLE IF NOT EXISTS subscriptions (
    id          SERIAL PRIMARY KEY,
    telegram_id BIGINT       NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    device      TEXT         NOT NULL,
    remark      TEXT         NOT NULL UNIQUE,
    sub_id      TEXT         NOT NULL UNIQUE,
    uuid        TEXT         NOT NULL UNIQUE,
    created     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_telegram_id ON subscriptions(telegram_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_sub_id ON subscriptions(sub_id);


-- Таблица тикетов поддержки
CREATE TABLE IF NOT EXISTS support (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT       NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    message     TEXT         NOT NULL,
    photo_id    TEXT,
    status      VARCHAR(20)  NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'answered', 'closed')),
    reply       TEXT,
    admin_id    BIGINT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    replied_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_support_user_id ON support(user_id);
CREATE INDEX IF NOT EXISTS idx_support_status ON support(status);


-- Таблица фортуны
CREATE TABLE IF NOT EXISTS fortune (
    id           SERIAL PRIMARY KEY,
    telegram_id  BIGINT       NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    promo_key    TEXT         NOT NULL,
    prize_key    TEXT         NOT NULL,
    prize_full   TEXT         NOT NULL,
    activated    BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    activated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_fortune_telegram_id ON fortune(telegram_id);


-- Таблица промокодов
CREATE TABLE IF NOT EXISTS promocodes (
    id          SERIAL PRIMARY KEY,
    code        TEXT         NOT NULL UNIQUE,              -- всегда в верхнем регистре
    amount      INTEGER      NOT NULL CHECK (amount > 0),  -- рубли
    max_uses    INTEGER      NOT NULL DEFAULT 0 CHECK (max_uses >= 0), -- 0 = без лимита
    used_count  INTEGER      NOT NULL DEFAULT 0,
    expires_at  TIMESTAMPTZ,                               -- NULL = бессрочно
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
 
CREATE TABLE IF NOT EXISTS promo_activations (
    id            SERIAL PRIMARY KEY,
    promo_id      INTEGER      NOT NULL REFERENCES promocodes(id) ON DELETE CASCADE,
    telegram_id   BIGINT       NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    activated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (promo_id, telegram_id)
);
 
CREATE INDEX IF NOT EXISTS idx_promo_activations_telegram_id ON promo_activations(telegram_id);