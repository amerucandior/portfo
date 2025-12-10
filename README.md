# Portfo

A small Flask site for a personal portfolio with a contact form and lightweight analytics stored in SQLite. It renders static pages from `templates/`, tracks page views and unique visitors, and exposes a basic-auth–protected dashboard for quick insights.

## Features
- Static pages served from `templates/` with `/` and dynamic `/<page_name>` routes.
- Contact form posts to `/submit_form`, writing submissions to `database.txt` and `database.csv`.
- Analytics tracking via cookies: page views, unique visitors, referrers, IPs, user agents, timestamps.
- Admin dashboard at `/admin/analytics` with simple charts and summaries (basic auth).
- `robots.txt` and `sitemap.xml` endpoints baked in.

## Setup
1) Prereqs: Python 3.10+ recommended, virtualenv.
2) Install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
3) Configure environment (optional `.env`):
```
ADMIN_USERNAME=admin
ADMIN_PASSWORD=password
SECRET_KEY=dev-secret-key
# Comma-separated list; defaults to loopback if omitted
ALLOWED_IPS=127.0.0.1,::1
# development (default) or production
FLASK_ENV=development
# Enables debug reloader/logging when set to "true"
FLASK_DEBUG=false
```

## Run the app
```bash
python server.py
```
- The server listens on port `5001`. Visit `http://localhost:5001/`.
- Access the analytics dashboard at `http://localhost:5001/admin/analytics` using the admin credentials above.

## Data storage
- Analytics live in `analytics.db` (SQLite) with tables:
  - `unique_visitors(session_id, first_visit, last_visit)`
  - `page_views(session_id, page_url, ip_address, user_agent, referrer, timestamp)`
- Form submissions append to `database.txt` and `database.csv`. Rotate or move these if running in production.

## Project structure
- `server.py` — Flask app, routes, analytics tracking, security headers.
- `config.py` — Environment-driven configuration.
- `templates/` — HTML pages including `index.html` and `analytics.html`.
- `static/` — Static assets.
- `requirements.txt` — Python dependencies.

## Notes
- Basic auth protects the admin dashboard only; rotate credentials and use HTTPS in production (`secure` cookie flag is enabled automatically when not in debug).
- The app sets simple security headers (`X-Content-Type-Options`, `X-Frame-Options`) and long caching for `/static/`.
- If you change `FLASK_ENV` to a value not in `config`, ensure `config` has a matching key or fallback to `default`.
