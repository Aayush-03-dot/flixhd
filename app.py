from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, jsonify, make_response, flash
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import timedelta, datetime
from flask_mail import Mail, Message
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from dotenv import load_dotenv
import random
import os
import uuid
import requests
import json
import certifi # For SSL certificates in some database connections
import math


# --- Database Imports ---
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
import pymysql # For MySQL connection


# --- Load Environment Variables ---
load_dotenv()
pymysql.install_as_MySQLdb()


app = Flask(__name__)


# -------------------------------------- Configuration ---------------------------------------------------------------------
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.ionos.co.uk')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() in ('true', '1', 't')
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'False').lower() in ('true', '1', 't')
app.config['PER_PAGE'] = 120

# ==================================== Define OTP expiration time (e.g., 15 minutes)===============================================
app.config['OTP_EXPIRATION_MINUTES'] = 15
mail = Mail(app)
app.secret_key = os.getenv('SECRET_KEY')
app.permanent_session_lifetime = timedelta(days=7)
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
csrf = CSRFProtect(app)


# tmdb API configuration

app.config['TMDB_API_KEY'] = os.getenv('TMDB_API_KEY')
app.config['TMDB_BASE_IMAGE_URL'] = "https://image.tmdb.org/t/p/w500"
app.config['TMDB_BACKDROP_IMAGE_URL'] = "https://image.tmdb.org/t/p/w1280"

ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
ADMIN_PASSWORD_HASH = generate_password_hash(os.getenv('ADMIN_PASSWORD'))

# --- Database Configuration ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

try:
    ssl_args = {'ssl_ca': certifi.where()}
except Exception as e:
    print(f"Warning: Could not find certifi CA bundle: {e}. SSL connection might fail if required by DB. Setting ssl_args to empty dict.")
    ssl_args = {}

db = SQLAlchemy(
    app,
    engine_options={
        "connect_args": ssl_args,
        "pool_recycle": 280
    }
)

migrate = Migrate(app, db)
# --- Helper Functions ---
class MyBaseForm(FlaskForm):
    pass

def admin_required(f):
    """
    Decorator to ensure the current session has 'admin' set to True.
    Returns JSON response for API calls or redirects to login for page requests.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin'):
            is_api_call = request.path.startswith('/api/admin/')
            is_ajax_request = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

            if is_api_call or is_ajax_request:
                return jsonify({'error': 'Unauthorized: Admin access required', 'code': 403}), 403
            flash('Admin access required. Please log in.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


def allowed_file(filename):
    """Checks if a file's extension is allowed for upload."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def nocache(view):
    """
    Decorator to add no-cache headers to a response.
    Useful for pages with sensitive user data or dynamic content.
    """
    @wraps(view)
    def no_cache_impl(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response
    return no_cache_impl

def get_display_thumbnail(item):
    """Determines the best thumbnail URL for display."""
    if item.poster_url:
        return item.poster_url
    elif item.thumbnail:
        return url_for('uploaded_file', filename=item.thumbnail, _external=True)
    else:
        return url_for('static', filename='default_poster.jpg', _external=True)

def get_display_backdrop(item):
    """Determines the best backdrop URL for display."""
    if hasattr(item, 'backdrop_url') and item.backdrop_url:
        return item.backdrop_url
    return get_display_thumbnail(item)

def send_otp_email(recipient_email, otp):
    """Sends an OTP email to the specified recipient."""
    try:
        html_content = render_template('otp_email.html', otp=otp)
        msg = Message('Your OTP for FlixHD' , sender=app.config['MAIL_USERNAME'], recipients=[recipient_email], html=html_content)
        mail.send(msg)
    except Exception as e:
        print(f"---!!! FAILED TO SEND EMAIL: {e} !!!---")
        import traceback
        traceback.print_exc()
        raise RuntimeError(f"Email service is currently unavailable: {e}")

def get_tmdb_movie_director(crew_data):
    """Extracts the director's name from TMDB crew data."""
    for member in crew_data:
        if member.get('job') == 'Director':
            return member.get('name')
    return None

def get_tmdb_top_actors(cast_data, count=10):
    """Extracts top actors' names and profile paths from TMDB cast data."""
    actors = []
    for member in cast_data[:count]:
        if member.get('name'):
            actors.append({"name": member.get('name'), "profile_path": member.get('profile_path')})
    return actors




#   ==================== SQLAlchemy Database Models =========================



class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    security_question = db.Column(db.String(256), nullable=False)
    security_answer = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    login_count = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self, include_sensitive=False):
        user_dict = {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'is_active': self.is_active,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'login_count': self.login_count
        }
        if include_sensitive:
            user_dict['security_question'] = self.security_question
        return user_dict

class PendingUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    security_question = db.Column(db.String(256), nullable=False)
    security_answer = db.Column(db.String(256), nullable=False)
    otp = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # NEW: to_dict method for JSON serialization
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'otp': self.otp,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Movie(db.Model):
    __tablename__ = 'movie'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tmdb_id = db.Column(db.String(20), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    embed_code = db.Column(db.Text, nullable=False)
    poster_url = db.Column(db.String(255), nullable=True)
    backdrop_url = db.Column(db.String(255), nullable=True)
    thumbnail = db.Column(db.String(255), nullable=True)
    release_date = db.Column(db.String(20), nullable=True)
    director = db.Column(db.String(100), nullable=True)
    genre = db.Column(db.Text, nullable=True)
    cast = db.Column(db.Text, nullable=True)
    download_url = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    content_type = db.Column(db.String(20), nullable=False, default='movie')

    @property
    def genre_list(self):
        return [g.strip() for g in self.genre.split(',')] if self.genre else []

    def to_dict(self):
        cast_list = []
        cast_display_string = ""
        if self.cast:
            try:
                cast_data = json.loads(self.cast)
                cast_list = cast_data
                cast_display_string = ", ".join([actor.get('name', '') for actor in cast_data])
            except (json.JSONDecodeError, TypeError):
                cast_list = []
                cast_display_string = self.cast

        return {
            "id": self.id,
            "tmdb_id": self.tmdb_id,
            "title": self.title,
            "description": self.description,
            "embed_code": self.embed_code,
            "poster_url": self.poster_url,
            "backdrop_url": self.backdrop_url,
            "thumbnail": self.thumbnail,
            "release_date": self.release_date,
            "director": self.director,
            "genre": self.genre,
            "cast": cast_list,
            "cast_display_string": cast_display_string,
            "created_at": self.created_at.isoformat(),
            "content_type": self.content_type,
            "display_thumbnail": get_display_thumbnail(self),
        }

class Series(db.Model):
    __tablename__ = 'series'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tmdb_id = db.Column(db.String(20), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    poster_url = db.Column(db.String(255), nullable=True)
    backdrop_url = db.Column(db.String(255), nullable=True)
    thumbnail = db.Column(db.String(255), nullable=True)
    release_date = db.Column(db.String(20), nullable=True)
    director = db.Column(db.String(100), nullable=True)
    genre = db.Column(db.Text, nullable=True)
    cast = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    last_updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True) # <--- ADD THIS LINE
    content_type = db.Column(db.String(20), nullable=False, default='series')
    seasons = db.relationship('Season', backref='series', lazy=True, cascade="all, delete-orphan", order_by="Season.id")
    download_url = db.Column(db.Text, nullable=True)


    @property
    def genre_list(self):
        return [g.strip() for g in self.genre.split(',')] if self.genre else []

    def to_dict(self):
        cast_list = []
        cast_display_string = ""
        if self.cast:
            try:
                cast_data = json.loads(self.cast)
                cast_list = cast_data
                cast_display_string = ", ".join([actor.get('name', '') for actor in cast_data])
            except (json.JSONDecodeError, TypeError):
                cast_list = []
                cast_display_string = self.cast

        return {
            "id": self.id,
            "tmdb_id": self.tmdb_id,
            "title": self.title,
            "description": self.description,
            "poster_url": self.poster_url,
            "backdrop_url": self.backdrop_url,
            "thumbnail": self.thumbnail,
            "release_date": self.release_date,
            "director": self.director,
            "genre": self.genre,
            "cast": cast_list,
            "cast_display_string": cast_display_string,
            "created_at": self.created_at.isoformat(),
            "content_type": self.content_type,
            "display_thumbnail": get_display_thumbnail(self),
             "download_url": self.download_url,
            "backdrop_display": get_display_backdrop(self),
            "last_updated_at": self.last_updated_at.isoformat() if self.last_updated_at else None, # <-- You can also add this to_dict for debugging/API if needed
        }

class Season(db.Model):
    __tablename__ = 'season'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    series_id = db.Column(db.String(36), db.ForeignKey('series.id'), nullable=False)
    episodes = db.relationship('Episode', backref='season', lazy=True, cascade="all, delete-orphan", order_by="Episode.number")

class Episode(db.Model):
    __tablename__ = 'episode'
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=True)
    embed_code = db.Column(db.Text, nullable=False)
    season_id = db.Column(db.Integer, db.ForeignKey('season.id'), nullable=False)
    
class MovieRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    link = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Pending')
    date = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "link": self.link,
            "notes": self.notes,
            "status": self.status,
            "date": self.date.strftime('%b %d, %Y')
        }

class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=True)
    message = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default='New') # 'New', 'Read', 'Archived'

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "subject": self.subject,
            "message": self.message,
            "date": self.date.strftime('%b %d, %Y %H:%M'),
            "status": self.status
        }


class Pagination:
    def __init__(self, page, per_page, total, items):
        self.page = page
        self.per_page = per_page
        self.total = total
        self.items = items
        self.pages = int(math.ceil(total / per_page)) if total > 0 else 0
        self.has_prev = self.page > 1
        self.prev_num = self.page - 1
        self.has_next = self.page < self.pages
        self.next_num = self.page + 1

    def iter_pages(self, left_edge=1, right_edge=1, left_current=1, right_current=2):
        last = 0
        for num in range(1, self.pages + 1):
            if num <= left_edge or \
               (self.page - left_current - 1 < num < self.page + right_current) or \
               num > self.pages - right_edge:
                if last + 1 != num:
                    yield None
                yield num
                last = num


# --- Context Processors for Navbar Genres ---
@app.context_processor
def inject_movie_genres():
    all_movies = Movie.query.all()
    genres = set()
    for movie in all_movies:
        if movie.genre:
            genres.update([g.strip() for g in movie.genre.split(',') if g.strip()])
    return dict(movie_genres=sorted(list(genres)))

@app.context_processor
def inject_series_genres():
    all_series = Series.query.all()
    genres = set()
    for series_item in all_series:
        if series_item.genre:
            genres.update([g.strip() for g in series_item.genre.split(',') if g.strip()])
    return dict(series_genres=sorted(list(genres)))


# --- Main Application Routes ---

@app.route('/')
@nocache
def index():
    form = MyBaseForm()
    if 'user' not in session:
        return redirect(url_for('login'))

    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search_query', '').strip()
    category = request.args.get('category', 'all').strip()

    # --- Fetching all genres for the filter dropdown (existing logic - NO CHANGE) ---
    all_movies_for_genres = Movie.query.all()
    all_series_for_genres = Series.query.all()

    all_genres = set()
    for item in all_movies_for_genres + all_series_for_genres:
        if item.genre:
            genres_list = [g.strip() for g in item.genre.split(',') if g.strip()]
            all_genres.update(genres_list)
    sorted_genres = sorted(list(all_genres))
    # --- End of existing genre fetching ---

    # --- NEW: Fetching Data for Specific Homepage Sections ---
    new_releases_limit = 30

    # Fetch movies by created_at (as before)
    new_release_movies = Movie.query.order_by(db.desc(Movie.created_at)).limit(new_releases_limit).all()

    # Fetch series by last_updated_at (THIS IS A CHANGE)
    # OLD: new_release_series = Series.query.order_by(db.desc(Series.created_at)).limit(new_releases_limit).all()
    new_release_series = Series.query.order_by(db.desc(Series.last_updated_at)).limit(new_releases_limit).all() # <--- MODIFIED LINE

    new_releases = new_release_movies + new_release_series
    # Sort the combined list by their respective latest timestamps (THIS IS A CHANGE)
    # OLD: new_releases.sort(key=lambda x: x.created_at, reverse=True)
    new_releases.sort(key=lambda x: x.last_updated_at if isinstance(x, Series) else x.created_at, reverse=True) # <--- MODIFIED LINE
    new_releases = new_releases[:new_releases_limit]

    category_limit = 30

    # --- Horror Content (modify to use last_updated_at for series) ---
    horror_movies = Movie.query.filter(Movie.genre.like('%Horror%')).order_by(db.desc(Movie.created_at)).limit(category_limit).all()
    # OLD: horror_series = Series.query.filter(Series.genre.like('%Horror%')).order_by(db.desc(Series.created_at)).limit(category_limit).all()
    horror_series = Series.query.filter(Series.genre.like('%Horror%')).order_by(db.desc(Series.last_updated_at)).limit(category_limit).all() # <--- MODIFIED LINE
    horror_content = horror_movies + horror_series
    # OLD: horror_content.sort(key=lambda x: x.created_at, reverse=True)
    horror_content.sort(key=lambda x: x.last_updated_at if isinstance(x, Series) else x.created_at, reverse=True) # <--- MODIFIED LINE
    horror_content = horror_content[:category_limit]


    # --- Crime Content (modify to use last_updated_at for series) ---
    crime_movies = Movie.query.filter(Movie.genre.like('%Crime%')).order_by(db.desc(Movie.created_at)).limit(category_limit).all()
    # OLD: crime_series = Series.query.filter(Series.genre.like('%Crime%')).order_by(db.desc(Series.created_at)).limit(category_limit).all()
    crime_series = Series.query.filter(Series.genre.like('%Crime%')).order_by(db.desc(Series.last_updated_at)).limit(category_limit).all() # <--- MODIFIED LINE
    crime_content = crime_movies + crime_series
    # OLD: crime_content.sort(key=lambda x: x.created_at, reverse=True)
    crime_content.sort(key=lambda x: x.last_updated_at if isinstance(x, Series) else x.created_at, reverse=True) # <--- MODIFIED LINE
    crime_content = crime_content[:category_limit]


    # --- Action Content (modify to use last_updated_at for series) ---
    action_movies = Movie.query.filter(Movie.genre.like('%Action%')).order_by(db.desc(Movie.created_at)).limit(category_limit).all()
    # OLD: action_series = Series.query.filter(Series.genre.like('%Action%')).order_by(db.desc(Series.created_at)).limit(category_limit).all()
    action_series = Series.query.filter(Series.genre.like('%Action%')).order_by(db.desc(Series.last_updated_at)).limit(category_limit).all() # <--- MODIFIED LINE
    action_content = action_movies + action_series
    # OLD: action_content.sort(key=lambda x: x.created_at, reverse=True)
    action_content.sort(key=lambda x: x.last_updated_at if isinstance(x, Series) else x.created_at, reverse=True) # <--- MODIFIED LINE
    action_content = action_content[:category_limit]


    # Apply display thumbnail for new sections (NO CHANGE)
    for item in new_releases:
        item.thumbnail_display = get_display_thumbnail(item)
    for item in horror_content:
        item.thumbnail_display = get_display_thumbnail(item)
    for item in crime_content:
        item.thumbnail_display = get_display_thumbnail(item)
    for item in action_content:
        item.thumbnail_display = get_display_thumbnail(item)


    # --- Existing: Main Paginated Content Logic (for "Trending Now" / Search / Filter) ---
    movies_query = Movie.query
    series_query = Series.query

    if category and category != 'all':
        if category == 'all-movies':
            series_query = series_query.filter(False) # Exclude series
        elif category == 'all-series':
            movies_query = movies_query.filter(False) # Exclude movies
        else:
            search_genre = f"%{category}%"
            movies_query = movies_query.filter(Movie.genre.like(search_genre))
            series_query = series_query.filter(Series.genre.like(search_genre))

    if search_query:
        search_term = f"%{search_query.lower()}%"
        movies_query = movies_query.filter(Movie.title.ilike(search_term))
        series_query = series_query.filter(Series.title.ilike(search_term))

    # IMPORTANT: Adjust the sorting here for the main paginated content too (THIS IS A CHANGE)
    all_content_filtered = movies_query.all() + series_query.all()
    # OLD: all_content_filtered.sort(key=lambda x: x.created_at, reverse=True)
    all_content_filtered.sort(key=lambda x: x.last_updated_at if hasattr(x, 'last_updated_at') else x.created_at, reverse=True) # <--- MODIFIED LINE

    total = len(all_content_filtered)
    per_page = app.config.get('PER_PAGE', 120)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_items = all_content_filtered[start:end]

    pagination = Pagination(page, per_page, total, paginated_items)

    for item in pagination.items:
        item.thumbnail_display = get_display_thumbnail(item)

    featured_item = None
    if page == 1 and not search_query and category == 'all':
        if paginated_items:
            featured_item = paginated_items[0] # The very latest item is the featured one
            featured_item.backdrop_display = get_display_backdrop(featured_item)
            # Ensure the featured item is NOT duplicated in the main paginated list
            # Filter out the featured item if it appears in the paginated list
            paginated_items = [item for item in paginated_items if item.id != featured_item.id]
            # Re-create pagination object if the list of items changed
            total_after_featured = total - 1 if featured_item else total
            pagination = Pagination(page, per_page, total_after_featured, paginated_items)


    return render_template(
        'index.html',
        pagination=pagination,
        featured_item=featured_item,
        search_query=search_query,
        category=category,
        form=form,
        genres=sorted_genres,
        # --- NEW: Pass the content for the new sections to the template ---
        new_releases=new_releases,
        horror_content=horror_content,
        crime_content=crime_content,
        action_content=action_content
    )

@app.route('/movie/<movie_id>')
@nocache
def movie_detail(movie_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    movie = Movie.query.get_or_404(movie_id)
    movie.display_poster = get_display_thumbnail(movie)
    movie.backdrop_display = get_display_backdrop(movie)

    cast_list = []
    if movie.cast:
        try:
            cast_list = json.loads(movie.cast)
        except (json.JSONDecodeError, TypeError):
            cast_list = [{'name': name.strip(), 'profile_path': None} for name in movie.cast.split(',')]

    related_movies = []
    if movie.genre:
        first_genre = movie.genre_list[0] if movie.genre_list else None
        if first_genre:
            related_movies_query = Movie.query.filter(Movie.genre.like(f'%{first_genre}%'), Movie.id != movie_id).limit(10)
            related_movies = related_movies_query.all()

    if not related_movies:
        related_movies = Movie.query.filter(Movie.id != movie_id).order_by(db.desc(Movie.created_at)).limit(5).all()

    for m_related in related_movies:
        m_related.thumbnail_display = get_display_thumbnail(m_related)

    return render_template('movie_detail.html', item=movie, cast=cast_list, director=movie.director, related_movies=related_movies)


@app.route('/series/<series_id>')
@nocache
def series_detail(series_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    series = Series.query.options(joinedload(Series.seasons).joinedload(Season.episodes)).get_or_404(series_id)
    series.display_poster = get_display_thumbnail(series)
    series.backdrop_display = get_display_backdrop(series)

    cast_list = []
    if series.cast:
        try:
            cast_list = json.loads(series.cast)
        except (json.JSONDecodeError, TypeError):
            cast_list = [{'name': name.strip(), 'profile_path': None} for name in series.cast.split(',')]

    related_series = []
    if series.genre:
        first_genre = series.genre_list[0] if series.genre_list else None
        if first_genre:
            related_series_candidates = Series.query.filter(Series.genre.like(f'%{first_genre}%'), Series.id != series_id).limit(10).all()
            related_series = random.sample(related_series_candidates, min(len(related_series_candidates), 5))

    for s_related in related_series:
        s_related.thumbnail_display = get_display_thumbnail(s_related)

    return render_template('movie_detail.html', item=series, cast=cast_list, director=series.director, related_movies=related_series)


# --- User Authentication Routes ---
@app.route('/register', methods=['GET', 'POST'])
@nocache
def register():
    form = MyBaseForm()
    if request.method == 'POST':
        print("--- DEBUG: REGISTRATION POST received ---")
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        security_question = request.form['security_question']
        security_answer = request.form['security_answer'].strip()

        if not all([username, email, password, security_question, security_answer]):
            flash("All fields are required.", 'error')
            return render_template('register.html', form=form, **request.form)

        now = datetime.utcnow()
        expiration_cutoff = now - timedelta(minutes=app.config['OTP_EXPIRATION_MINUTES'])

        # Clean up expired pending users for the given email/username
        expired_pending_email = PendingUser.query.filter_by(email=email).filter(PendingUser.created_at < expiration_cutoff).first()
        if expired_pending_email:
            db.session.delete(expired_pending_email)
            db.session.commit()
            print(f"--- DEBUG: Cleaned up expired pending user by email: {email} ---")

        expired_pending_username = PendingUser.query.filter_by(username=username).filter(PendingUser.created_at < expiration_cutoff).first()
        if expired_pending_username:
            db.session.delete(expired_pending_username)
            db.session.commit()
            print(f"--- DEBUG: Cleaned up expired pending user by username: {username} ---")

        # Check for active users or fresh pending users
        if User.query.filter_by(email=email).first() or PendingUser.query.filter_by(email=email).first():
            print(f"--- DEBUG: REGISTRATION FAILED: Email {email} already exists or is currently awaiting verification ---")
            flash('This email address is already registered or currently awaiting verification.', 'error')
            return render_template('register.html', form=form, **request.form)

        if User.query.filter_by(username=username).first() or PendingUser.query.filter_by(username=username).first():
            print(f"--- DEBUG: REGISTRATION FAILED: Username {username} already taken or is currently awaiting verification ---")
            flash('This username is already taken or currently awaiting verification.', 'error')
            return render_template('register.html', form=form, **request.form)

        otp = str(random.randint(100000, 999999))
        new_pending_user = PendingUser(username=username, email=email, password=generate_password_hash(password), security_question=security_question, security_answer=security_answer, otp=otp)
        db.session.add(new_pending_user)

        try:
            print(f"--- DEBUG: Attempting to send OTP to {email} ---")
            send_otp_email(email, otp)
            print("--- DEBUG: OTP Email sent successfully ---")

            db.session.commit()
            print("--- DEBUG: Pending user committed to database ---")

            session['pending_email'] = email
            print("--- DEBUG: Redirecting to verify_email page ---")
            return redirect(url_for('verify_email'))

        except Exception as e:
            print(f"---!!! DEBUG: AN ERROR OCCURRED IN REGISTRATION: {e} !!!---")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            flash('An error occurred on the server. Please try again later. (Email service issue likely)', 'error')

        return render_template('register.html', form=form, **request.form)
    return render_template('register.html', form=form)

@app.route('/verify_email', methods=['GET', 'POST'])
@nocache
def verify_email():
    form = MyBaseForm()
    pending_email = session.get('pending_email')
    if not pending_email:
        flash('Please register first.', 'info')
        return redirect(url_for('register'))

    pending_user = PendingUser.query.filter_by(email=pending_email).first()

    if not pending_user:
        flash('Your verification session has expired or been cancelled. Please register again.', 'error')
        session.pop('pending_email', None)
        return redirect(url_for('register'))

    now = datetime.utcnow()
    expiration_cutoff = now - timedelta(minutes=app.config['OTP_EXPIRATION_MINUTES'])
    if pending_user.created_at < expiration_cutoff:
        db.session.delete(pending_user)
        db.session.commit()
        flash('Your OTP has expired. Please register again to get a new one.', 'error')
        session.pop('pending_email', None)
        return redirect(url_for('register'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp', '').strip()

        if pending_user.otp == entered_otp:
            new_user = User(username=pending_user.username, email=pending_user.email, password=pending_user.password, security_question=pending_user.security_question, security_answer=pending_user.security_answer)
            db.session.add(new_user)
            db.session.delete(pending_user)
            db.session.commit()
            session.pop('pending_email', None)
            flash('Account verified successfully! Please log in.', 'success')
            return redirect(url_for('login', registration_success='true'))
        else:
            flash('Invalid OTP.', 'error')
            return render_template('verify_email.html', email=pending_email, form=form, otp=entered_otp)

    return render_template('verify_email.html', email=pending_email, form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = MyBaseForm()
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        pending_user = PendingUser.query.filter_by(email=email).first()

        now = datetime.utcnow()
        expiration_cutoff = now - timedelta(minutes=app.config['OTP_EXPIRATION_MINUTES'])

        if user:
            if not user.is_active:
                flash('Your account has been suspended. Please contact support.', 'error')
                return render_template('login.html', form=form, email=email)

            if check_password_hash(user.password, password):
                session.permanent = True
                session['user'] = user.username
                session['user_role'] = user.role
                session['user_id'] = user.id
                user.last_login_at = datetime.utcnow()
                user.login_count = (user.login_count or 0) + 1
                db.session.commit()
                flash('Login successful!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid email or password.', 'error')
                return render_template('login.html', form=form, email=email)
        elif pending_user:
            if pending_user.created_at < expiration_cutoff:
                db.session.delete(pending_user)
                db.session.commit()
                flash('Your previous registration attempt has expired. Please register again.', 'error')
                return redirect(url_for('register'))
            else:
                session['pending_email'] = email
                flash('Your account is awaiting email verification. Please check your email for the OTP.', 'info')
                return redirect(url_for('verify_email'))
        else:
            flash('Invalid email or password.', 'error')
            return render_template('login.html', form=form, email=request.args.get('email', ''))

    registration_success = request.args.get('registration_success')
    if registration_success == 'true':
        flash('Account verified successfully! Please log in.', 'success')

    return render_template('login.html', form=form, email=request.args.get('email', ''))


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    form = MyBaseForm()
    if request.method == 'POST':
        username_input = request.form.get('username', '').strip()
        user = User.query.filter(User.username.ilike(username_input)).first()
        if 'answer' in request.form:
            answer = request.form.get('answer', '').strip().lower()
            new_password = request.form.get('new_password', '').strip()
            if user and user.security_answer.lower() == answer:
                if not new_password:
                    flash('New password cannot be empty.', 'error')
                    return render_template('forgot_password.html', form=form, question=user.security_question, username=user.username)
                user.password = generate_password_hash(new_password)
                db.session.commit()
                flash('Password updated successfully!', 'success')
                return redirect(url_for('login'))
            else:
                flash('Incorrect answer.', 'error')
                return render_template('forgot_password.html', form=form, question=user.security_question if user else None, username=user.username if user else username_input)
        else:
            if user:
                return render_template('forgot_password.html', form=form, question=user.security_question, username=user.username)
            else:
                flash('Username not found.', 'error')
    return render_template('forgot_password.html', form=form)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/logout')
def user_logout():
    session.clear()
    flash("You have been successfully logged out.", "success")
    return redirect(url_for('login'))


# --- Admin Specific Routes ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    form = MyBaseForm()
    if request.method == 'POST':
        submitted_username = request.form['username']
        submitted_password = request.form['password']
        if submitted_username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, submitted_password):
            session['admin'] = True
            admin_user = User.query.filter_by(username=ADMIN_USERNAME).first()
            if admin_user:
                session['user_id'] = admin_user.id
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials', 'error')
            return redirect(url_for('admin_login'))
    return render_template('admin_login.html', form=form)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    session.pop('user_id', None)
    flash("You have been successfully logged out from admin panel.", "success")
    return redirect(url_for('index'))

@app.route('/admin/dashboard_view-flixhd-3cr3t_0x3e_dashboard_backend-admin_lxpsrwTHcIer74H-net')
@nocache
@admin_required
def admin_dashboard():
    form = MyBaseForm()
    return render_template('admin_dashboard.html', form=form)


# --- Admin Content Management API Routes ---

@app.route('/api/stats')
@nocache
@admin_required
def get_stats():
    """Fetches various statistics for the admin dashboard overview."""
    try:
        movie_count = db.session.query(Movie.id).count()
        series_count = db.session.query(Series.id).count()
        pending_requests = db.session.query(MovieRequest.id).filter_by(status='Pending').count()
        total_users = db.session.query(User.id).count()
        pending_users = db.session.query(PendingUser.id).count()
        total_new_messages = db.session.query(ContactMessage.id).filter_by(status='New').count()

        return jsonify({
            'totalMovies': movie_count,
            'totalSeries': series_count,
            'pendingRequests': pending_requests,
            'totalUsers': total_users,
            'pendingUsers': pending_users,
            'totalNewMessages': total_new_messages
        })
    except Exception as e:
        print(f"Error fetching stats: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch statistics.', 'details': str(e)}), 500


@app.route('/api/content', methods=['GET'])
@nocache
@admin_required
def get_content():
    """Fetches paginated list of all movies and series for management."""
    page = request.args.get('page', 1, type=int)
    per_page = 24

    movies = Movie.query.order_by(Movie.created_at.desc()).all()
    series = Series.query.order_by(Series.created_at.desc()).all()

    all_content = sorted(movies + series, key=lambda x: x.created_at, reverse=True)

    total = len(all_content)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_items = all_content[start:end]

    has_next = end < total
    next_page_number = page + 1 if has_next else None

    return jsonify({
        'items': [item.to_dict() for item in paginated_items],
        'has_next': has_next,
        'next_page_number': next_page_number,
        'total_items': total
    })

@app.route('/admin/add_content', methods=['POST'])
@nocache
@admin_required
def add_content():
    """Handles adding new movies or series, including TMDB data and file uploads."""
    if request.is_json:
        data = request.get_json()
        if not data.get('title'):
            return jsonify({'success': False, 'message': 'Series title is required.'}), 400

        new_series = Series(
            id=str(uuid.uuid4()),
            tmdb_id=data.get('tmdb_id'),
            title=data.get('title'),
            description=data.get('description'),
            genre=data.get('genres'),
            poster_url=data.get('poster_url'),
            backdrop_url=data.get('backdrop_url'),
            cast=json.dumps(data.get('actors', [])),
            director=data.get('director'),
            release_date=data.get('release_date'),
            download_url=data.get('download_url')
        )
        db.session.add(new_series)

        try:
            db.session.flush()
            for season_data in data.get('seasons', []):
                new_season = Season(title=season_data.get('title'), series_id=new_series.id)
                db.session.add(new_season)
                db.session.flush()
                for episode_data in season_data.get('episodes', []):
                    new_episode = Episode(number=episode_data.get('number'), title=episode_data.get('title'), embed_code=episode_data.get('embed_code'), season_id=new_season.id)
                    db.session.add(new_episode)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Series added successfully!', 'item': new_series.to_dict()})
        except Exception as e:
            db.session.rollback()
            print(f"Error adding series: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'Database error when adding series: {str(e)}'}), 500
    else:
        movie_title = request.form.get('title')
        movie_embed_code = request.form.get('movie_embed_code')
        movie_download_url = request.form.get('download_url')
        if not movie_title or not movie_embed_code:
            return jsonify({'success': False, 'message': 'Movie Title and Embed Code are required.'}), 400

        cast_json_from_hidden = request.form.get('actors_json')
        final_cast_data = None
        if cast_json_from_hidden and cast_json_from_hidden != 'undefined':
            final_cast_data = cast_json_from_hidden
        else:
            cast_text = request.form.get('actors')
            if cast_text:
                actors_list = [{'name': name.strip(), 'profile_path': None} for name in cast_text.split(',')]
                final_cast_data = json.dumps(actors_list)

        local_thumbnail_filename = None
        movie_thumbnail_file = request.files.get('thumbnail')
        if movie_thumbnail_file and allowed_file(movie_thumbnail_file.filename):
            try:
                filename = secure_filename(movie_thumbnail_file.filename)
                thumbnail_extension = os.path.splitext(filename)[1]
                local_thumbnail_filename = str(uuid.uuid4()) + thumbnail_extension
                thumbnail_path = os.path.join(app.config['UPLOAD_FOLDER'], local_thumbnail_filename)
                movie_thumbnail_file.save(thumbnail_path)
            except Exception as e:
                print(f"Error saving thumbnail file: {e}")
                return jsonify({'success': False, 'message': f'Error saving thumbnail: {e}'}), 500

        new_movie = Movie(
            id=str(uuid.uuid4()),
            tmdb_id=request.form.get('tmdb_id'),
            title=movie_title,
            description=request.form.get('description'),
            genre=request.form.get('genres'),
            embed_code=movie_embed_code,
            poster_url=request.form.get('poster_url') if not local_thumbnail_filename else None,
            backdrop_url=request.form.get('backdrop_url'),
            thumbnail=local_thumbnail_filename,
            cast=final_cast_data,
            director=request.form.get('director'),
            release_date=request.form.get('release_date'),
            download_url=movie_download_url,
        )
        db.session.add(new_movie)
        try:
            db.session.commit()
            return jsonify({'success': True, 'message': 'Movie added successfully!', 'item': new_movie.to_dict()})
        except Exception as e:
            db.session.rollback()
            print(f"Error adding movie: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'Database error when adding movie: {e}'}), 500

@app.route('/admin/edit/series/<series_id>', methods=['GET', 'POST'])
@nocache
@admin_required # Only admin can edit series
def edit_series(series_id):
    series = Series.query.options(joinedload(Series.seasons).joinedload(Season.episodes)).get_or_404(series_id)
    form = MyBaseForm()
    if request.method == 'POST':
        try:
            data = request.get_json()
            series.title = data.get('title')
            series.description = data.get('description')
            series.download_url = data.get('download_url')
            submitted_season_ids = {str(s['id']) for s in data.get('seasons', []) if s.get('id')}

            for season in list(series.seasons):
                if str(season.id) not in submitted_season_ids:
                    db.session.delete(season)
            for season_data in data.get('seasons', []):
                season_id = season_data.get('id')
                current_season = None
                if season_id:
                    current_season = Season.query.get(season_id)
                    if current_season:
                        current_season.title = season_data.get('title')
                else:
                    current_season = Season(series_id=series.id, title=season_data.get('title'))
                    db.session.add(current_season)
                    db.session.flush()
                if current_season:
                    submitted_episode_ids = {str(e['id']) for e in season_data.get('episodes', []) if e.get('id')}
                    for episode in list(current_season.episodes):
                        if str(episode.id) not in submitted_episode_ids:
                            db.session.delete(episode)
                    for episode_data in season_data.get('episodes', []):
                        episode_id = episode_data.get('id')
                        if episode_id:
                            episode = Episode.query.get(episode_id)
                            if episode:
                                episode.number = int(episode_data.get('number'))
                                episode.title = episode_data.get('title')
                                episode.embed_code = episode_data.get('embed_code')
                        else:
                            new_episode = Episode(season_id=current_season.id, number=int(episode_data.get('number')), title=episode_data.get('title'), embed_code=episode_data.get('embed_code'))
                            db.session.add(new_episode)
                            series.last_updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'success': True, 'message': 'Series updated successfully!', 'redirect': url_for('admin_dashboard')})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'An error occurred: {str(e)}'}), 500
    return render_template('edit_series.html', series=series, form=form)

@app.route('/admin/fetch_tmdb_data')
@admin_required
def fetch_tmdb_data_route():
    """Fetches movie or TV series details from TMDB API."""
    if not app.config['TMDB_API_KEY']:
        return jsonify({'error': 'TMDB API key not configured on server.'}), 500

    content_type = request.args.get('type', 'movie')
    title_query = request.args.get('title')
    tmdb_id_query = request.args.get('tmdb_id')
    api_key = app.config['TMDB_API_KEY']
    tmdb_data = None
    search_path = 'tv' if content_type == 'series' else 'movie'

    try:
        if tmdb_id_query:
            detail_url = f"https://api.themoviedb.org/3/{search_path}/{tmdb_id_query}?api_key={api_key}&append_to_response=credits"
            response = requests.get(detail_url, timeout=10)
            response.raise_for_status()
            tmdb_data = response.json()
        elif title_query:
            search_url = f"https://api.themoviedb.org/3/search/{search_path}?api_key={api_key}&query={title_query}"
            response = requests.get(search_url, timeout=10)
            response.raise_for_status()
            search_results = response.json()
            if search_results.get('results'):
                first_result_id = search_results['results'][0]['id']
                detail_url = f"https://api.themoviedb.org/3/{search_path}/{first_result_id}?api_key={api_key}&append_to_response=credits"
                response = requests.get(detail_url, timeout=10)
                response.raise_for_status()
                tmdb_data = response.json()

        if not tmdb_data:
            return jsonify({'not_found': True, 'message': 'Content not found on TMDB.'})

        final_data = {}
        if content_type == 'movie':
            final_data.update({'title': tmdb_data.get('title') or tmdb_data.get('original_title'), 'release_date': tmdb_data.get('release_date'), 'director': get_tmdb_movie_director(tmdb_data.get('credits', {}).get('crew', []))})
        else:
            creators = [creator['name'] for creator in tmdb_data.get('created_by', [])]
            final_data.update({'title': tmdb_data.get('name') or tmdb_data.get('original_name'), 'release_date': tmdb_data.get('first_air_date'), 'director': ", ".join(creators)})

        final_data.update({
            'tmdb_id': tmdb_data.get('id'),
            'overview': tmdb_data.get('overview'),
            'poster_url': f"https://image.tmdb.org/t/p/w500{tmdb_data.get('poster_path')}" if tmdb_data.get('poster_path') else None,
            'backdrop_url': f"https://image.tmdb.org/t/p/w1280{tmdb_data.get('backdrop_path')}" if tmdb_data.get('backdrop_path') else None,
            'genres': [genre['name'] for genre in tmdb_data.get('genres', [])],
            'actors': get_tmdb_top_actors(tmdb_data.get('credits', {}).get('cast', []), count=10),
        })
        return jsonify(final_data)
    except requests.exceptions.RequestException as e:
        print(f"TMDB API request failed: {e}")
        return jsonify({'error': f'TMDB API request failed: {e}', 'details': str(e)}), 500

@app.route('/api/movie/<movie_id>', methods=['POST'])
@admin_required
def api_edit_movie(movie_id):
    """Handles editing an existing movie."""
    movie = Movie.query.get_or_404(movie_id)
    form_data = request.form
    movie.title = form_data.get('title', movie.title)
    movie.description = form_data.get('description', movie.description)
    movie.release_date = form_data.get('release_date', movie.release_date)
    movie.director = form_data.get('director', movie.director)
    movie.embed_code = form_data.get('embed_code', movie.embed_code)
    movie.tmdb_id = form_data.get('tmdb_id', movie.tmdb_id)
    movie.genre = form_data.get('genres', movie.genre)
    movie.download_url = form_data.get('download_url', movie.download_url)

    cast_text = form_data.get('actors')
    if cast_text:
        actors_list = [{'name': name.strip(), 'profile_path': None} for name in cast_text.split(',')]
        movie.cast = json.dumps(actors_list)

    new_thumbnail_file = request.files.get('thumbnail')
    if new_thumbnail_file and allowed_file(new_thumbnail_file.filename):
        if movie.thumbnail and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], movie.thumbnail)):
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], movie.thumbnail))
            except Exception as e:
                print(f"Warning: Could not delete old thumbnail file {movie.thumbnail}: {e}")

        thumb_ext = os.path.splitext(new_thumbnail_file.filename)[1]
        new_filename = str(uuid.uuid4()) + thumb_ext
        new_thumbnail_file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))

        movie.thumbnail = new_filename
        movie.poster_url = None
    elif 'poster_url' in form_data:
        movie.poster_url = form_data.get('poster_url')

    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Movie updated successfully!', 'item': movie.to_dict()})
    except Exception as e:
        db.session.rollback()
        print(f"Error updating movie: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Failed to update movie: {e}'}), 500

@app.route('/delete/movie/<movie_id>', methods=['DELETE'])
@admin_required
def delete_movie(movie_id):
    """Deletes a movie and its associated thumbnail file."""
    movie = Movie.query.get_or_404(movie_id)

    if movie.thumbnail:
        thumbnail_path = os.path.join(app.config['UPLOAD_FOLDER'], movie.thumbnail)
        if os.path.exists(thumbnail_path):
            try:
                os.remove(thumbnail_path)
            except Exception as e:
                print(f"Error deleting thumbnail file {thumbnail_path}: {e}")

    try:
        db.session.delete(movie)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Movie deleted successfully!'})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting movie: {e}")
        return jsonify({'success': False, 'message': f'Failed to delete movie: {e}'}), 500

@app.route('/delete/series/<series_id>', methods=['DELETE'])
@admin_required
def delete_series(series_id):
    """Deletes a series and its associated thumbnail file (if any)."""
    series = Series.query.get_or_404(series_id)

    if series.thumbnail:
        thumbnail_path = os.path.join(app.config['UPLOAD_FOLDER'], series.thumbnail)
        if os.path.exists(thumbnail_path):
            try:
                os.remove(thumbnail_path)
            except Exception as e:
                print(f"Error deleting thumbnail file {thumbnail_path}: {e}")

    try:
        db.session.delete(series)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Series deleted successfully!'})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting series: {e}")
        return jsonify({'success': False, 'message': f'Failed to delete series: {e}'}), 500


# --- Admin User Management API Routes ---
@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_get_users():
    """Fetches paginated list of registered users for admin management."""
    page = request.args.get('page', 1, type=int)
    per_page = app.config.get('PER_PAGE', 20)
    
    search_query = request.args.get('search', '').strip()

    users_query = User.query

    if search_query:
        search_term = f"%{search_query}%"
        users_query = users_query.filter(
            (User.username.ilike(search_term)) |
            (User.email.ilike(search_term))
        )

    users = users_query.paginate(page=page, per_page=per_page, error_out=False)

    users_data = [user.to_dict() for user in users.items]
    return jsonify({
        'users': users_data,
        'total_users': users.total,
        'pages': users.pages,
        'current_page': users.page,
        'has_next': users.has_next,
        'has_prev': users.has_prev,
        'next_num': users.next_num,
        'prev_num': users.prev_num
    })


@app.route('/api/admin/users/<int:user_id>', methods=['GET', 'PUT', 'DELETE'])
@admin_required
def admin_manage_user(user_id):
    """Manages individual user details (get, update, delete)."""
    user = User.query.get_or_404(user_id)

    if request.method == 'GET':
        return jsonify(user.to_dict(include_sensitive=True))

    elif request.method == 'PUT':
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided.'}), 400

        if 'username' in data:
            if data['username'] != user.username and User.query.filter_by(username=data['username']).first():
                return jsonify({'success': False, 'message': 'Username already taken.'}), 400
            user.username = data['username']

        if 'email' in data:
            if data['email'] != user.email and User.query.filter_by(email=data['email']).first():
                return jsonify({'success': False, 'message': 'Email already registered.'}), 400
            user.email = data['email']

        if 'role' in data:
            if data['role'] in ['user', 'admin']:
                user.role = data['role']
            else:
                return jsonify({'success': False, 'message': 'Invalid role specified.'}), 400

        if 'is_active' in data:
            user.is_active = bool(data['is_active'])

        if 'password' in data and data['password']:
            user.password = generate_password_hash(data['password'])

        if 'security_question' in data:
            user.security_question = data['security_question']

        if 'security_answer' in data:
            user.security_answer = data['security_answer']


        try:
            db.session.commit()
            return jsonify({'success': True, 'message': 'User updated successfully.', 'user': user.to_dict()})
        except IntegrityError:
            db.session.rollback()
            print(f"Integrity error updating user {user_id}: {e}")
            return jsonify({'success': False, 'message': 'Database integrity error (e.g., duplicate username/email).'}), 409
        except Exception as e:
            db.session.rollback()
            print(f"Error updating user {user_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'Failed to update user: {str(e)}'}), 500

    elif request.method == 'DELETE':
        if user.id == session.get('user_id'):
            return jsonify({'success': False, 'message': 'You cannot delete your own account.'}), 403

        pending_user = PendingUser.query.filter_by(email=user.email).first()
        if pending_user:
            db.session.delete(pending_user)

        try:
            db.session.delete(user)
            db.session.commit()
            return jsonify({'success': True, 'message': 'User deleted successfully.'})
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting user {user_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'Failed to delete user: {str(e)}'}), 500

# --- User Movie Request Routes ---
@app.route('/request', methods=['GET', 'POST'])
def request_page():
    """Page for users to submit movie/series requests."""
    form = MyBaseForm()
    if request.method == 'POST':
        title = request.form.get('title')
        link = request.form.get('link')
        notes = request.form.get('notes')

        if not title:
            flash('Title is a required field.', 'error')
            return render_template('request.html', form=form, title=title, link=link, notes=notes)

        new_req = MovieRequest(title=title, link=link, notes=notes, status='Pending')
        db.session.add(new_req)
        try:
            db.session.commit()
            flash('Your request has been submitted successfully!', 'success')
            return redirect(url_for('request_page'))
        except Exception as e:
            db.session.rollback()
            print(f"Error submitting movie request: {e}")
            flash(f'Error submitting request: {e}', 'error')

    return render_template('request.html', form=form)

@app.route('/request/submit', methods=['POST'])
def submit_request():
    new_req = MovieRequest(title=request.form.get('movie-title'), link=request.form.get('movie-link'), notes=request.form.get('notes'), status='Pending')
    db.session.add(new_req)
    try:
        db.session.commit()
        flash('Your request has been submitted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Error submitting request (from /request/submit): {e}")
        flash(f'Error submitting request: {e}', 'error')
    return redirect(url_for('request_page'))

@app.route('/api/requests')
@nocache
@admin_required
def get_requests():
    """Fetches all movie requests for the admin panel."""
    try:
        requests = MovieRequest.query.order_by(MovieRequest.date.desc()).all()
        return jsonify([req.to_dict() for req in requests])
    except Exception as e:
        print(f"Error fetching requests: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch requests.', 'details': str(e)}), 500

@app.route('/request/complete/<int:request_id>', methods=['POST'])
@admin_required
def complete_request(request_id):
    """Marks a movie request as completed."""
    try:
        req = MovieRequest.query.get_or_404(request_id)
        req.status = 'Completed'
        db.session.commit()
        return jsonify({'success': True, 'updated_request': req.to_dict()})
    except Exception as e:
        print(f"Error completing request {request_id}: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Failed to mark request as complete: {str(e)}'}), 500

@app.route('/request/delete/<int:request_id>', methods=['DELETE'])
@admin_required
def delete_request(request_id):
    """Deletes a movie request."""
    try:
        req = MovieRequest.query.get_or_404(request_id)
        db.session.delete(req)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Request deleted successfully!'})
    except Exception as e:
        print(f"Error deleting request {request_id}: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Failed to delete request: {str(e)}'}), 500

# --- Contact Message Routes ---
@app.route('/contact', methods=['GET', 'POST'])
@nocache
def contact():
    """User-facing contact form to send messages to admin."""
    form = MyBaseForm()
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message_content = request.form.get('message')

        if not all([name, email, message_content]):
            flash('Name, Email, and Message are required fields.', 'error')
            return render_template('contact.html', form=form, name=name, email=email, subject=subject, message_content=message_content)

        new_message = ContactMessage(
            name=name,
            email=email,
            subject=subject,
            message=message_content,
            status='New'
        )
        db.session.add(new_message)
        try:
            db.session.commit()
            flash('Your message has been sent successfully!', 'success')
            return redirect(url_for('contact'))
        except Exception as e:
            db.session.rollback()
            print(f"Error sending contact message: {e}")
            import traceback
            traceback.print_exc()
            flash(f'Error sending message: {e}', 'error')

    return render_template('contact.html', form=form)




# --- Download Movie Route ---

@app.route('/download/<content_type>/<content_id>')
def download_content(content_type, content_id):
    """
    Redirects to a third-party download URL for a movie or series, restricted to logged-in users.
    """
    if 'user' not in session:
        flash('You must be logged in to access download links.', 'error')
        # Redirect back to the detail page for the correct content type
        if content_type == 'movie':
            return redirect(url_for('movie_detail', movie_id=content_id))
        elif content_type == 'series':
            return redirect(url_for('series_detail', series_id=content_id))
        return redirect(url_for('login')) # Fallback to login if type is unknown

    item = None
    if content_type == 'movie':
        item = Movie.query.get(content_id)
    elif content_type == 'series':
        item = Series.query.get(content_id)
    else:
        flash('Invalid content type for download.', 'error')
        return redirect(url_for('index'))

    if not item:
        flash(f'{content_type.capitalize()} not found.', 'error')
        return redirect(url_for('index'))

    if item.download_url:
        if item.download_url.startswith('http://') or item.download_url.startswith('https://'):
            print(f"Redirecting to external download URL for {content_type}: {item.download_url}")
            return redirect(item.download_url)
        else:
            flash(f'Invalid download URL configured for this {content_type}. Please contact support.', 'error')
            if content_type == 'movie':
                return redirect(url_for('movie_detail', movie_id=content_id))
            elif content_type == 'series':
                return redirect(url_for('series_detail', series_id=content_id))
    else:
        flash('Download link not available for this content.', 'info')
        if content_type == 'movie':
            return redirect(url_for('movie_detail', movie_id=content_id))
        elif content_type == 'series':
            return redirect(url_for('series_detail', series_id=content_id))

    return redirect(url_for('index')) # Final fallback

@app.route('/api/admin/messages', methods=['GET'])
@admin_required
def admin_get_messages():
    """Fetches all contact messages for the admin panel."""
    try:
        messages = ContactMessage.query.order_by(ContactMessage.date.desc()).all()
        return jsonify([msg.to_dict() for msg in messages])
    except Exception as e:
        print(f"Error fetching messages: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch messages.', 'details': str(e)}), 500


@app.route('/api/admin/messages/mark_read/<int:message_id>', methods=['POST'])
@admin_required
def admin_mark_message_read(message_id):
    """Marks a specific contact message as 'Read'."""
    try:
        message = ContactMessage.query.get_or_404(message_id)
        message.status = 'Read'
        db.session.commit()
        return jsonify({'success': True, 'updated_message': message.to_dict(), 'message': 'Message marked as read.'})
    except Exception as e:
        print(f"Error marking message {message_id} as read: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Failed to mark message as read: {str(e)}'}), 500


@app.route('/api/admin/messages/delete/<int:message_id>', methods=['DELETE'])
@admin_required
def admin_delete_message(message_id):
    """Deletes a specific contact message."""
    try:
        message = ContactMessage.query.get_or_404(message_id)
        db.session.delete(message)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Message deleted successfully!'})
    except Exception as e:
        print(f"Error deleting message {message_id}: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Failed to delete message: {str(e)}'}), 500

# --- NEW: Admin Pending User Management API Routes ---

@app.route('/api/admin/pending_users', methods=['GET'])
@admin_required
def admin_get_pending_users():
    """Fetches all pending user registrations for the admin panel."""
    try:
        pending_users = PendingUser.query.order_by(PendingUser.created_at.desc()).all()
        return jsonify([user.to_dict() for user in pending_users])
    except Exception as e:
        print(f"Error fetching pending users: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch pending users.', 'details': str(e)}), 500

@app.route('/api/admin/pending_users/approve/<int:pending_user_id>', methods=['POST'])
@admin_required
def admin_approve_pending_user(pending_user_id):
    """Approves a pending user, moving them to the active User table."""
    try:
        pending_user = PendingUser.query.get_or_404(pending_user_id)

        new_user = User(
            username=pending_user.username,
            email=pending_user.email,
            password=pending_user.password, # This is already hashed
            security_question=pending_user.security_question,
            security_answer=pending_user.security_answer,
            role='user', # Default role for new users
            is_active=True,
            last_login_at=datetime.utcnow(),
            login_count=0
        )
        db.session.add(new_user)
        db.session.delete(pending_user)

        db.session.commit()
        return jsonify({'success': True, 'message': f'User "{pending_user.username}" approved and activated!'})

    except IntegrityError as e:
        db.session.rollback()
        print(f"Integrity error approving user {pending_user_id}: {e}")
        # Check for specific duplicate key error if needed, otherwise general message
        if "Duplicate entry" in str(e):
            return jsonify({'success': False, 'message': 'Username or email already exists for an active user. Approval failed.'}), 409
        return jsonify({'success': False, 'message': f'Database integrity error during approval: {str(e)}'}), 409
    except Exception as e:
        db.session.rollback()
        print(f"Error approving pending user {pending_user_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Failed to approve user: {str(e)}'}), 500

@app.route('/api/admin/pending_users/delete/<int:pending_user_id>', methods=['DELETE'])
@admin_required
def admin_delete_pending_user(pending_user_id):
    """Deletes a pending user registration."""
    try:
        pending_user = PendingUser.query.get_or_404(pending_user_id)
        db.session.delete(pending_user)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Pending user registration deleted.'})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting pending user {pending_user_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Failed to delete pending user: {str(e)}'}), 500


# ... (existing imports and other routes)

@app.errorhandler(404)
def page_not_found(e):
    """
    Custom 404 Not Found page handler.
    """
    return render_template('404.html'), 404

# ... (rest of your app.py)


if __name__ == '__main__':
    with app.app_context():
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
        if not app.config.get('SQLALCHEMY_DATABASE_URI'):
            print("\nFATAL ERROR: DATABASE_URL is not set in the .env file.\n")
        else:
            print("Creating database tables if they don't exist...")
            try:
                db.create_all()
                print("Database tables checked and created if necessary.")
            except Exception as e:
                print(f"\nFATAL ERROR: Could not connect to database or create tables: {e}")
                print("Please check your DATABASE_URL in .env and ensure your database server is running.")
    is_debug = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    app.run(host='0.0.0.0', port=5000, debug=is_debug)
