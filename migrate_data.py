# migrate_json_to_db.py
import json
import os
from app import app, db, Movie, User, MovieRequest # Import your app and models
from werkzeug.security import generate_password_hash
import uuid

# File paths from your old project
MOVIES_FILE = 'movies.json'
USERS_FILE = 'users.json'
REQUESTS_FILE = 'requests.json'
PENDING_USERS_FILE = 'pending_users.json' # Note: Pending users are not migrated as they are temporary.

def migrate():
    """
    Reads data from JSON files and populates the SQLAlchemy database.
    This should only be run ONCE.
    """
    with app.app_context():
        print("Starting migration...")

        # --- Migrate Users ---
        if os.path.exists(USERS_FILE):
            print(f"Migrating users from {USERS_FILE}...")
            with open(USERS_FILE, 'r') as f:
                try:
                    users_data = json.load(f)
                    for user_dict in users_data:
                        # Check if user already exists
                        if User.query.filter_by(email=user_dict['email']).first():
                            print(f"  - Skipping user {user_dict['email']} (already exists).")
                            continue
                        
                        new_user = User(
                            username=user_dict['username'],
                            email=user_dict['email'],
                            password=user_dict['password'], # Assumes password is a HASH already
                            security_question=user_dict.get('security_question', 'Legacy User - Question not set'),
                            security_answer=user_dict.get('security_answer', 'Legacy User - Answer not set')
                        )
                        db.session.add(new_user)
                        print(f"  - Adding user: {new_user.username}")
                except json.JSONDecodeError:
                    print(f"Could not parse {USERS_FILE}. Skipping.")
            db.session.commit()
            print("Users migration complete.")

        # --- Migrate Movies ---
        if os.path.exists(MOVIES_FILE):
            print(f"Migrating movies from {MOVIES_FILE}...")
            with open(MOVIES_FILE, 'r') as f:
                try:
                    movies_data = json.load(f)
                    for movie_dict in movies_data:
                        # Check if movie already exists by ID or title
                        if Movie.query.get(movie_dict['id']) or Movie.query.filter_by(title=movie_dict['title']).first():
                            print(f"  - Skipping movie '{movie_dict['title']}' (already exists).")
                            continue

                        # Convert genre list to comma-separated string
                        genre_str = ', '.join(movie_dict.get('genre', [])) if isinstance(movie_dict.get('genre'), list) else movie_dict.get('genre', '')
                        cast_str = ', '.join(movie_dict.get('cast', [])) if isinstance(movie_dict.get('cast'), list) else movie_dict.get('cast', '')

                        new_movie = Movie(
                            id=movie_dict.get('id', str(uuid.uuid4())),
                            title=movie_dict['title'],
                            description=movie_dict.get('description'),
                            embed_code=movie_dict['embed_code'],
                            poster_url=movie_dict.get('poster_url'),
                            thumbnail=movie_dict.get('thumbnail'),
                            release_date=movie_dict.get('release_date'),
                            director=movie_dict.get('director'),
                            genre=genre_str,
                            cast=cast_str,
                            tmdb_id=movie_dict.get('tmdb_id')
                        )
                        db.session.add(new_movie)
                        print(f"  - Adding movie: {new_movie.title}")
                except json.JSONDecodeError:
                    print(f"Could not parse {MOVIES_FILE}. Skipping.")
            db.session.commit()
            print("Movies migration complete.")
        
        # --- Migrate Requests ---
        if os.path.exists(REQUESTS_FILE):
            print(f"Migrating requests from {REQUESTS_FILE}...")
            with open(REQUESTS_FILE, 'r') as f:
                try:
                    requests_data = json.load(f)
                    for req_dict in requests_data:
                         # Very basic check to avoid duplicates
                        if MovieRequest.query.filter_by(title=req_dict['title']).first():
                            print(f"  - Skipping request '{req_dict['title']}' (already exists).")
                            continue

                        new_req = MovieRequest(
                            title=req_dict['title'],
                            link=req_dict.get('link'),
                            notes=req_dict.get('notes'),
                            status=req_dict.get('status', 'Pending')
                            # Date will be set to now by default
                        )
                        db.session.add(new_req)
                        print(f"  - Adding request: {new_req.title}")
                except json.JSONDecodeError:
                    print(f"Could not parse {REQUESTS_FILE}. Skipping.")
            db.session.commit()
            print("Requests migration complete.")

        print("\nMigration finished successfully!")

if __name__ == '__main__':
    migrate()