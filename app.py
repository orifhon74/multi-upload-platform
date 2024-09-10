from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
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


# Helper to run asynchronous tasks in Flask
def run_async_task(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

# Route for sending verification code
@app.route('/send_code', methods=['POST'])
def send_code():
    phone_number = request.json.get('phone_number')
    client = TelegramClient(f'session_{phone_number}', api_id, api_hash)

    async def send_code_async():
        await client.connect()
        if not await client.is_user_authorized():
            await client.send_code_request(phone_number)
        return "Code sent to Telegram"

    result = run_async_task(send_code_async())
    return jsonify({'message': result})


@app.route('/login_telegram', methods=['GET', 'POST'])
def login_telegram():
    if request.method == 'POST':
        phone_number = request.form['phone_number']  # Get the phone number from the form

        async def send_code_async():
            client = TelegramClient(f'session_{phone_number}', api_id, api_hash)
            await client.connect()

            # Request the code and store the `phone_code_hash`
            if not await client.is_user_authorized():
                result = await client.send_code_request(phone_number)
                session['phone_code_hash'] = result.phone_code_hash  # Store the hash in the session

            await client.disconnect()

        # Use asyncio.run() to ensure there is an event loop
        asyncio.run(send_code_async())

        session['phone_number'] = phone_number

        # Redirect to the code entry page
        return redirect(url_for('enter_telegram_code'))

    return render_template('login_telegram.html')


@app.route('/enter_telegram_code', methods=['GET', 'POST'])
def enter_telegram_code():
    phone_number = session.get('phone_number')
    phone_code_hash = session.get('phone_code_hash')  # Retrieve the phone_code_hash from the session

    if request.method == 'POST':
        code = request.form['code']  # Get the code from the form

        async def login_async():
            client = TelegramClient(f'session_{phone_number}', api_id, api_hash)
            await client.connect()

            # Now sign in using the phone number, code, and phone_code_hash
            await client.sign_in(phone=phone_number, code=code, phone_code_hash=phone_code_hash)

            await client.disconnect()

        # Use asyncio.run() to ensure there is an event loop
        asyncio.run(login_async())

        flash('Logged in successfully!')
        return redirect(url_for('dashboard'))

    return render_template('enter_code.html', phone_number=phone_number)


@app.route('/upload_telegram_video', methods=['POST'])
def upload_telegram_video():
    phone_number = session.get('phone_number')  # Retrieve the logged-in user's phone number
    chat_id = request.form['chat_id']  # Get the chat/channel ID from the form
    caption = request.form['caption']  # Get the caption from the form
    video_file = request.files['video_file']  # Get the video file from the form

    if video_file:
        # Save the video file to a temporary location
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_file.filename)
        video_file.save(video_path)

        async def upload_async():
            client = TelegramClient(f'session_{phone_number}', api_id, api_hash)
            await client.connect()

            # Fetch the entity (chat/channel) based on the provided ID
            entity = await client.get_entity(int(chat_id))

            # Send the video to the resolved entity with the caption
            await client.send_file(entity, video_path, caption=caption)

            await client.disconnect()

        # Run the async function to upload the video
        asyncio.run(upload_async())

        flash('Video uploaded successfully to Telegram!')
        return redirect(url_for('dashboard'))

    flash('Please upload a video file.')
    return redirect(url_for('upload_telegram_video_page'))



@app.route('/upload_telegram_video_page', methods=['GET'])
def upload_telegram_video_page():
    phone_number = session.get('phone_number')  # Retrieve the logged-in user's phone number

    async def fetch_chats():
        client = TelegramClient(f'session_{phone_number}', api_id, api_hash)
        await client.connect()

        # Fetch the dialogs (chats/channels the user is part of)
        dialogs = await client.get_dialogs()

        # Store the dialog names and IDs in a list of tuples
        chats = [(dialog.id, dialog.title) for dialog in dialogs]

        await client.disconnect()

        return chats

    # Fetch the chats asynchronously
    chats = asyncio.run(fetch_chats())

    # Render the form and pass the chats to the template
    return render_template('upload_telegram.html', chats=chats)



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

