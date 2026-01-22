-- Таблица офферов
CREATE TABLE IF NOT EXISTS offers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Таблица кампаний
CREATE TABLE IF NOT EXISTS campaigns (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    offer_url TEXT NOT NULL,
    offer_id INTEGER REFERENCES offers(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Таблица событий
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
    event_type VARCHAR(50) NOT NULL,
    email VARCHAR(255) NOT NULL,
    domain VARCHAR(255) NOT NULL,
    ip VARCHAR(45),
    user_agent TEXT,
    extra_params JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Таблица для хранения количества отправленных писем по доменам в кампаниях
CREATE TABLE IF NOT EXISTS campaign_domain_emails (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    domain VARCHAR(255) NOT NULL,
    emails_sent INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(campaign_id, domain)
);

-- Индексы для производительности
CREATE INDEX IF NOT EXISTS idx_events_campaign ON events(campaign_id);
CREATE INDEX IF NOT EXISTS idx_events_email ON events(email);
CREATE INDEX IF NOT EXISTS idx_events_domain ON events(domain);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at);
CREATE INDEX IF NOT EXISTS idx_campaigns_offer ON campaigns(offer_id);
CREATE INDEX IF NOT EXISTS idx_campaign_domain_emails_campaign ON campaign_domain_emails(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_domain_emails_domain ON campaign_domain_emails(domain);
