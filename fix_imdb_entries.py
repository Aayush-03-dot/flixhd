import os
from app import app, db, Movie

# --- CONFIGURATION ---
# This is the correct base URL for your iframe provider.
IFRAME_BASE_URL = "https://player.videasy.net/movie/"

def fix_iframe_codes():
    """
    Finds movies in the database that have an incorrect iframe embed code
    (containing an IMDb 'tt' ID) and updates it using the correct numeric
    TMDB ID stored in the same record.
    """
    
    # This 'app_context' is necessary for the script to interact with the database.
    with app.app_context():
        # Find all movies where the embed_code looks like it contains an IMDb ID.
        # We assume the 'tmdb_id' field was stored correctly as a number.
        movies_to_fix = Movie.query.filter(Movie.embed_code.like('%tt%')).all()

        if not movies_to_fix:
            print("No movies with incorrect iframe codes found. Everything looks good!")
            return

        print(f"Found {len(movies_to_fix)} movies with incorrect iframe codes. Starting correction...")
        
        fixed_count = 0
        error_count = 0

        for movie in movies_to_fix:
            # Check if the tmdb_id is valid and numeric.
            if movie.tmdb_id and movie.tmdb_id.isdigit():
                correct_tmdb_id = movie.tmdb_id
                
                # Generate the new, correct embed code.
                new_embed_code = f'<iframe style="border:1px #FFFFFF none" src="{IFRAME_BASE_URL}{correct_tmdb_id}" title="iFrame" width="100%" height="600px" scrolling="no" frameborder="no" allow="fullscreen"></iframe>'
                
                print(f"Fixing '{movie.title}' (ID: {movie.id})...")
                print(f"  - Old embed src: {movie.embed_code}")
                print(f"  + New embed src: {new_embed_code}")

                # Update only the embed_code field.
                movie.embed_code = new_embed_code
                fixed_count += 1
            else:
                print(f"-> SKIPPING '{movie.title}': The stored TMDB ID ('{movie.tmdb_id}') is not a valid number.")
                error_count += 1

        # Commit all the fixes to the database at once.
        if fixed_count > 0:
            try:
                print(f"\nCommitting {fixed_count} fixes to the database...")
                db.session.commit()
                print("Successfully saved all corrections.")
            except Exception as e:
                db.session.rollback()
                print(f"\nFATAL: A database error occurred during commit. No changes were saved. Error: {e}")
        else:
            print("\nNo movies were fixed.")

    print("\n--- Correction Script Complete ---")
    print(f"Movies Fixed: {fixed_count}")
    print(f"Movies Skipped: {error_count}")


if __name__ == '__main__':
    # ✨ THIS LINE IS NOW CORRECTED ✨
    fix_iframe_codes()
