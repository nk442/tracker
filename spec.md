# Click Tracker MVP - Specification

## Tech Stack

- **Backend:** Python, FastAPI
- **Database:** PostgreSQL
- **Templates:** Jinja2
- **Frontend:** HTMX (dynamic updates without JS)

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         YOUR SYSTEM                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │ example1.com │    │ example2.com │    │ example3.com │          │
│  │   Server 1   │    │   Server 2   │    │   Server 3   │          │
│  │  (MTA+Site)  │    │  (MTA+Site)  │    │  (MTA+Site)  │          │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘          │
│         │                   │                   │                   │
│         │    Send events    │                   │                   │
│         └───────────────────┼───────────────────┘                   │
│                             ▼                                        │
│                    ┌────────────────┐                                │
│                    │    TRACKER     │                                │
│                    │  tracker.com   │                                │
│                    └────────────────┘                                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Flow

1. **User creates campaign** in tracker: "Dog Food US, Wellgreen" + offer URL
2. **User gets campaign_id** from dashboard
3. **User's software** generates email links with encoded data
4. **User sends emails** from multiple domains
5. **Recipient clicks** → lands on sender's domain
6. **Landing script sends events** to tracker API
7. **User views stats** grouped by domain

---

## Database Schema

```sql
CREATE TABLE campaigns (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    offer_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE events (
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

CREATE INDEX idx_events_campaign ON events(campaign_id);
CREATE INDEX idx_events_email ON events(email);
CREATE INDEX idx_events_domain ON events(domain);
```

---

## API Endpoint

### `GET /api/event`

| Param | Required | Description |
|-------|----------|-------------|
| `cid` | Yes | Campaign ID |
| `event` | Yes | `email_click`, `landing_click`, `conversion` |
| `email` | Yes | User's email |
| `domain` | Yes | Sending domain |
| `*` | No | Any extra params → stored in JSONB |

**Example:**

```
GET /api/event?cid=5&event=email_click&email=john@gmail.com&domain=example1.com
```

**Response:**

```json
{"status": "ok", "event_id": 12345}
```

---

## Pages

### Home `/`

```
┌─────────────────────────────────────────────────────────────┐
│  TRACKER                                    [+ New Campaign] │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Your Campaigns                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ ID │ Name                    │ Clicks │ Conv │ Created  ││
│  ├────┼─────────────────────────┼────────┼──────┼──────────┤│
│  │ 5  │ Dog Food US, Wellgreen  │ 1,234  │ 89   │ Jan 15   ││
│  │ 4  │ Cat Toys EU, PetCo      │ 856    │ 42   │ Jan 12   ││
│  │ 3  │ Fish Oil CA, HealthPlus │ 2,100  │ 156  │ Jan 10   ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**HTMX:** Table auto-refreshes every 30 seconds via `hx-trigger="every 30s"`

---

### Create Campaign `/create`

```
┌─────────────────────────────────────────────────────────────┐
│  TRACKER                                                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Create New Campaign                                         │
│                                                              │
│  Campaign Name                                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Dog Food US, Wellgreen                                  ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Offer URL                                                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ https://wellgreen.com/dog-food-offer?aff=123            ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  [Create Campaign]                                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**HTMX:** Form submits via `hx-post="/campaigns"` without page reload

---

### Campaign Detail `/campaign/<id>`

```
┌─────────────────────────────────────────────────────────────┐
│  TRACKER                                         [← Back]    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Dog Food US, Wellgreen                                      │
│  Offer: https://wellgreen.com/dog-food-offer?aff=123        │
│  Campaign ID: 5  [Copy]                                      │
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│                                                              │
│  OVERALL STATS                          (auto-updates)       │
│  ┌────────────┬────────────┬────────────┬────────────┐      │
│  │ Email      │ Landing    │ Conver-    │ Conv.      │      │
│  │ Clicks     │ Clicks     │ sions      │ Rate       │      │
│  ├────────────┼────────────┼────────────┼────────────┤      │
│  │ 1,234      │ 567        │ 89         │ 7.2%       │      │
│  └────────────┴────────────┴────────────┴────────────┘      │
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│                                                              │
│  STATS BY DOMAIN                        (auto-updates)       │
│  ┌──────────────────┬────────┬─────────┬───────┬───────┐    │
│  │ Domain           │ E.Click│ L.Click │ Conv  │ Rate  │    │
│  ├──────────────────┼────────┼─────────┼───────┼───────┤    │
│  │ example1.com     │ 450    │ 210     │ 35    │ 7.8%  │    │
│  │ example2.com     │ 380    │ 178     │ 28    │ 7.4%  │    │
│  │ example3.com     │ 404    │ 179     │ 26    │ 6.4%  │    │
│  └──────────────────┴────────┴─────────┴───────┴───────┘    │
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│                                                              │
│  USER JOURNEYS                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Filter: [All domains ▼]  [All events ▼]  [Search email]│ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌──────────────────────┬────────┬─────────┬───────┬──────┐ │
│  │ Email                │ Domain │ E.Click │L.Click│ Conv │ │
│  ├──────────────────────┼────────┼─────────┼───────┼──────┤ │
│  │ john@gmail.com       │ ex1.co │ ✓       │ ✓     │ ✓    │ │
│  │ jane@yahoo.com       │ ex2.co │ ✓       │ ✓     │ ✗    │ │
│  │ bob@hotmail.com      │ ex1.co │ ✓       │ ✗     │ ✗    │ │
│  │ alice@gmail.com      │ ex3.co │ ✓       │ ✓     │ ✓    │ │
│  └──────────────────────┴────────┴─────────┴───────┴──────┘ │
│  Showing 50 of 1,234 users                    [Load more]   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**HTMX Features:**
- Stats auto-refresh every 10s: `hx-trigger="every 10s"`
- Domain filter updates table: `hx-get="/campaign/5/users?domain=example1.com"`
- "Load more" appends rows: `hx-get="/campaign/5/users?offset=50" hx-swap="beforeend"`
- Search email filters live: `hx-trigger="keyup changed delay:500ms"`