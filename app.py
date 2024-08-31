from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from telethon import TelegramClient, sync

from flask_session import Session
from flask_caching import Cache
from werkzeug.security import generate_password_hash, check_password_hash
import os
import pymysql
from google_auth_oauthlib.flow import Flow
from googleapiclient.errors import HttpError
import logging
import json
import asyncio
from telethon.sessions import StringSession
from asyncio import new_event_loop, set_event_loop

from youtube_upload import upload_to_youtube

# Allow HTTP for local development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

pymysql.install_as_MySQLdb()

db_password = os.environ.get("DB_PASSWORD")
app = Flask(__name__)
app.config['SECRET_KEY'] = '9490596234'
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql://root:{db_password}@localhost/multi_upload_platform_DB'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Silence the deprecation warning

# Configure server-side session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = '/tmp/flask_session/'  # Ensure this directory exists and is writable
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour
Session(app)

# Configure caching
app.config['CACHE_TYPE'] = 'filesystem'
app.config['CACHE_DIR'] = '/tmp/flask_cache/'  # Ensure this directory exists and is writable
cache = Cache(app)

db = SQLAlchemy(app)

api_id = 25627453
api_hash = '42d20a459418d7b8642c25dc4adaae94'


# client = TelegramClient(StringSession(), api_id, api_hash)
# client.start()

# Load the session string from file (or any other storage)
try:
    with open('telegram_session.txt', 'r') as f:
        session_string = f.read().strip()
except FileNotFoundError:
    session_string = None

# Initialize the client with the session string
if session_string:
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
else:
    client = TelegramClient(StringSession(), api_id, api_hash)
    with client:
        # Only prompt for login if no session exists
        session_string = client.session.save()
        with open('telegram_session.txt', 'w') as f:
            f.write(session_string)

# Optional: Connect the client manually if needed
# client.connect()

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

TELEGRAM_BOT_TOKEN = '7475371840:AAHS5fb9CXrIAPD-llsLG4qVcFRMloON-X0'
TELEGRAM_CHAT_ID = '-4201010865'

# Load OAuth 2.0 client secrets
with open('client_secret.json') as f:
    client_secrets = json.load(f)

# Setup OAuth 2.0 Flow
flow = Flow.from_client_config(
    client_secrets,
    scopes=['https://www.googleapis.com/auth/youtube.upload'],
    redirect_uri='http://localhost:5000/oauth2callback'
)

# YouTube category mapping
CATEGORY_MAPPING = {
    'Film & Animation': '1',
    'Autos & Vehicles': '2',
    'Music': '10',
    'Pets & Animals': '15',
    'Sports': '17',
    'Travel & Events': '19',
    'Gaming': '20',
    'People & Blogs': '22',
    'Comedy': '23',
    'Entertainment': '24',
    'News & Politics': '25',
    'Howto & Style': '26',
    'Education': '27',
    'Science & Technology': '28',
    'Nonprofits & Activism': '29'
}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session.permanent = True
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        return render_template('dashboard.html')
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        video_file = request.files['video_file']
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        tags = request.form['tags'].split(',')

        if video_file:
            video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_file.filename)
            video_file.save(video_path)

            session_data = {
                'video_path': video_path,
                'title': title,
                'description': description,
                'category': category,
                'tags': tags
            }
            cache.set('session_data', session_data)

            logging.info(f"Video path: {video_path}")
            logging.info(f"Title: {title}")
            logging.info(f"Description: {description}")
            logging.info(f"Category: {category}")
            logging.info(f"Tags: {tags}")

            return redirect(url_for('authorize'))

    return render_template('upload.html')

@app.route('/authorize')
def authorize():
    logging.info('Starting OAuth flow')
    authorization_url, state = flow.authorization_url()
    cache.set('state', state)
    logging.info(f"Authorization URL: {authorization_url}")
    logging.info(f"State: {state}")
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    logging.info('OAuth callback invoked')
    state = cache.get('state')
    logging.info(f"State from cache: {state}")

    if not state or state != request.args.get('state'):
        flash('Invalid state parameter')
        return redirect(url_for('dashboard'))

    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials

    session_data = cache.get('session_data')
    if not session_data:
        flash('Missing session data.')
        logging.error('Missing session data.')
        return redirect(url_for('dashboard'))

    video_path = session_data.get('video_path')
    title = session_data.get('title')
    description = session_data.get('description')
    category = CATEGORY_MAPPING.get(session_data.get('category'))
    tags = session_data.get('tags')

    logging.info(f"Video path: {video_path}")
    logging.info(f"Title: {title}")
    logging.info(f"Description: {description}")
    logging.info(f"Category: {category}")
    logging.info(f"Tags: {tags}")

    if not all([video_path, title, description, category, tags]):
        flash('Missing required session data.')
        logging.error('Missing required session data.')
        return redirect(url_for('dashboard'))

    try:
        upload_to_youtube(video_path, title, description, category, tags, credentials)
        flash('Video uploaded successfully to YouTube!')
    except HttpError as e:
        flash(f'An HTTP error {e.resp.status} occurred:\n{e.content}')
        logging.error(f'An HTTP error {e.resp.status} occurred:\n{e.content}')
    return redirect(url_for('dashboard'))


@app.route('/upload_telegram', methods=['GET', 'POST'])
def upload_telegram():
    if request.method == 'POST':
        video_file = request.files['video_file']
        caption = request.form['caption']

        if video_file:
            video_path = os.path.join('uploads', video_file.filename)
            video_file.save(video_path)

            # Use the pre-initialized client
            asyncio.run(send_to_telegram(video_path, caption))

            flash('Video uploaded to Telegram!')
            return redirect(url_for('dashboard'))

    return render_template('upload_telegram.html')

# Now the client is ready to be used for sending files
async def send_to_telegram(video_path, caption):
    # Use the client to send the file
    async with client:
        await client.send_file('me', video_path, caption=caption)

@app.route('/urls')
def list_urls():
    import urllib
    output = []
    for rule in app.url_map.iter_rules():
        methods = ','.join(rule.methods)
        url = urllib.parse.unquote(f"{rule.endpoint}: {rule}")
        output.append(f"{url} [{methods}]")
    return '<br>'.join(output)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    if not os.path.exists(app.config['SESSION_FILE_DIR']):
        os.makedirs(app.config['SESSION_FILE_DIR'])
    if not os.path.exists(app.config['CACHE_DIR']):
        os.makedirs(app.config['CACHE_DIR'])
    with app.app_context():
        db.create_all()
    app.run(debug=True)

