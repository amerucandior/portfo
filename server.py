import sqlite3
import os
from flask import Flask, render_template, url_for, request, redirect, make_response, g, jsonify, Response, request
import csv
from datetime import datetime, timedelta
import logging
from functools import wraps
import uuid


# Import config - make sure config.py exists
try:
    from config import config
except ImportError:
    # Fallback if config.py doesn't exist
    print("⚠️  config.py not found. Using default configuration.")

    class DefaultConfig:
        ADMIN_USERNAME = 'admin'
        ADMIN_PASSWORD = 'password'
        SECRET_KEY = 'dev-secret-key'
        DEBUG = False
    config = {'development': DefaultConfig, 'default': DefaultConfig}

app = Flask(__name__)

env = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(config[env])

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# ADMIN AUTHENTICATION
# =============================================================================


def check_admin_credentials():
    """Checks if admin credentials are set in the config."""
    return app.config.get('ADMIN_USERNAME') and app.config.get('ADMIN_PASSWORD')


def validate_credentials(username, password):
    """Validates provided username and password against configured admin credentials."""
    configured_username = app.config.get('ADMIN_USERNAME')
    configured_password = app.config.get('ADMIN_PASSWORD')
    return username == configured_username and password == configured_password


def requires_admin(f):
    """Enhanced admin authentication decorator"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check if credentials are configured
        if not check_admin_credentials():
            return render_template('admin_error.html',
                                   message="Admin access is not properly configured."), 500

        # Check basic authentication
        auth = request.authorization
        if not auth or not validate_credentials(auth.username, auth.password):
            return Response(
                '🔒 Admin Authentication Required\n\n'
                'Please enter your administrator credentials to access this page.',
                401,
                {'WWW-Authenticate': 'Basic realm="Administrator Access"'}
            )

        return f(*args, **kwargs)
    return decorated

# =============================================================================
# ANALYTICS DATABASE SETUP
# =============================================================================
def init_db():
    with app.app_context():  # makes g available
        init_analytics_database()


def get_analytics_db():
    if 'analytics_db' not in g:
        g.analytics_db = sqlite3.connect('analytics.db')
        g.analytics_db.row_factory = sqlite3.Row
    return g.analytics_db


def init_analytics_database():
    try:
        db = get_analytics_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS page_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                page_url TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                referrer TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS unique_visitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                first_visit DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_visit DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.commit()
        print("✅ Analytics database tables created!")
    except Exception as e:
        print(f"❌ Database error: {e}")


def close_analytics_db(e=None):
    """Close the database connection when the app context ends"""
    db = g.pop('analytics_db', None)
    if db is not None:
        db.close()


app.teardown_appcontext(close_analytics_db)

# Initialize analytics database tables on startup
init_db()

# =============================================================================
# ANALYTICS TRACKING
# =============================================================================


def get_client_ip():
    """Get the real client IP address (handles proxies)"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers['X-Forwarded-For'].split(',')[0].strip()
    return request.remote_addr



@app.after_request
def track_page_view(response):
    """
    Track page views and unique visitors after each HTML request.
    """
    # Only track HTML page requests (skip static/admin assets)
    if (response.status_code == 200 and
        response.content_type and
        'text/html' in response.content_type and
        not request.path.startswith(('/static', '/admin'))):

        try:
            db = get_analytics_db()

            # Get or create session ID from cookie
            session_id = request.cookies.get('session_id')
            if not session_id:
                session_id = str(uuid.uuid4())  # generate unique session id

                # Set secure cookie for analytics session
                response.set_cookie(
                    'session_id',
                    session_id,
                    max_age=30*24*60*60,   # 30 days
                    httponly=True,          # prevents JS access
                    samesite='Lax',         # protects against CSRF
                    secure=not app.debug     # only send over HTTPS in production
                )

            # Track unique visitor (preserve first_visit)
            db.execute('''
                INSERT INTO unique_visitors (session_id, first_visit, last_visit)
                VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id)
                DO UPDATE SET last_visit = CURRENT_TIMESTAMP
            ''', (session_id,))

            # Track page view
            db.execute('''
                INSERT INTO page_views (session_id, page_url, ip_address, user_agent, referrer)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                session_id,
                request.path,
                get_client_ip(),
                request.headers.get('User-Agent', ''),
                request.headers.get('Referer', '')
            ))

            db.commit()

        except Exception as e:
            print(f"⚠️ Analytics tracking error: {e}")

    return response


# =============================================================================
# ROUTES
# =============================================================================


@app.route("/")
def my_home():
    return render_template('index.html')


@app.route('/<string:page_name>')
def html_page(page_name):
    return render_template(f'{page_name}.html')


@app.route("/submit_form", methods=['POST', 'GET'])
def submit_form():
    if request.method == 'POST':
        try:
            data = request.form.to_dict()
            write_to_file(data)
            write_to_csv(data)
            return redirect('/thankyou.html')
        except:
            return 'Did not save to database'
    else:
        return 'Something went wrong'


def write_to_file(data):
    with open('database.txt', mode='a') as database:
        name = data["name"]
        email = data["email"]
        message = data["message"]
        database.write(f'\n{name},{email},{message}')


def write_to_csv(data):
    with open('database.csv', mode='a') as database2:
        name = data["name"]
        email = data["email"]
        message = data["message"]
        csv_writer = csv.writer(database2, delimiter=',',
                                quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerow([name, email, message])


@app.route("/robots.txt")
def robots_dot_txt():
    response = make_response("User-agent: *\nDisallow: /admin/")
    response.headers['Content-Type'] = 'text/plain'
    return response


@app.route('/sitemap.xml')
def sitemap_xml():
    pages = [
        {
            'url': url_for('my_home', _external=True),
            'lastmod': datetime.now().strftime('%Y-%m-%d')
        },
    ]
    sitemap_xml = render_template('sitemap.xml', pages=pages)
    response = make_response(sitemap_xml)
    response.headers['Content-Type'] = 'application/xml'
    return response


@app.route('/admin/analytics')
@requires_admin
def analytics_dashboard():
    """Main analytics dashboard - shows overview statistics"""
    db = get_analytics_db()

    # Basic statistics
    total_views = db.execute('SELECT COUNT(*) FROM page_views').fetchone()[0]
    total_unique_visitors = db.execute(
        'SELECT COUNT(*) FROM unique_visitors').fetchone()[0]

    # Today's stats
    now = datetime.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_tomorrow = start_of_day + timedelta(days=1)
    query = '''
    SELECT COUNT(*) 
    FROM page_views 
    WHERE timestamp >= ? AND timestamp < ?
    '''

    result = db.execute(query, (start_of_day, start_of_tomorrow)).fetchone()
    views_today = result[0] if result else 0

    # Popular pages (top 10)
    popular_pages = db.execute('''
    SELECT 
        page_url,
        COUNT(*) AS views,
        MAX(timestamp) AS last_viewed
    FROM page_views
    GROUP BY page_url
    ORDER BY views DESC
    LIMIT 10
''').fetchall()


    # Recent activity (last 20 page views)
    recent_views = db.execute('''
        SELECT page_url, ip_address, timestamp, user_agent
        FROM page_views 
        ORDER BY timestamp DESC 
        LIMIT 20
    ''').fetchall()

    # Browser/device breakdown
    browser_stats = db.execute('''
        SELECT 
            CASE 
                WHEN user_agent LIKE '%Chrome%' THEN 'Chrome'
                WHEN user_agent LIKE '%Firefox%' THEN 'Firefox'
                WHEN user_agent LIKE '%Safari%' THEN 'Safari'
                WHEN user_agent LIKE '%Edge%' THEN 'Edge'
                ELSE 'Other'
            END as browser,
            COUNT(*) as count
        FROM page_views 
        GROUP BY browser
        ORDER BY count DESC
    ''').fetchall()

    return render_template('analytics.html',
                           total_views=total_views,
                           total_unique_visitors=total_unique_visitors,
                           views_today=views_today,
                           popular_pages=popular_pages,
                           recent_views=recent_views,
                           browser_stats=browser_stats,
                           today=now)


@app.route('/admin/analytics/api/visits-over-time')
@requires_admin
def visits_over_time_api():
    """API endpoint for chart data - visits over the last 7 days"""
    db = get_analytics_db()
    visits_data = db.execute('''
        SELECT DATE(timestamp) as date, COUNT(*) as visits
        FROM page_views 
        WHERE timestamp >= DATE('now', '-6 days')
        GROUP BY DATE(timestamp)
        ORDER BY date
    ''').fetchall()

    dates = [row['date'] for row in visits_data]
    visits = [row['visits'] for row in visits_data]

    return jsonify({'dates': dates, 'visits': visits})


@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'

    # Caching for static content
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=31536000'

    return response

# =============================================================================
# APPLICATION STARTUP
# =============================================================================


if __name__ == '__main__':


    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, port=5001)
