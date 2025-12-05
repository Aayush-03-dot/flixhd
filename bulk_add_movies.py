import os
import requests
import json
import sys

# This allows the script to import from your main app file
from app import app, db, Movie, Series 

# --- CONFIGURATION ---
# The base URL for the iframe. The TMDB ID will be added to the end.
IFRAME_BASE_URL = "https://player.videasy.net/movie/"

# --- MAIN SCRIPT LOGIC ---
def bulk_add_movies():
    """
    This script fetches movie data from TMDB for a list of IDs,
    constructs an iframe embed code, and saves them to the database.
    """
    
    # /// --- EDIT THIS LIST --- ///
    # Add all the TMDB IDs you want to upload here, separated by commas.
    TMDB_IDS_TO_ADD = [
        
        "680",      # Example: Pulp Fiction
        "550",      # Example: Fight Club
       
"tt15354916", "tt15748830", "tt11663228", "tt14993250", "tt15732324", "tt18266472", "tt18561736", "tt3691740", "tt12844910", "tt15464390", "tt1187043", "tt14914988", "tt3741834", "tt13131610", "tt22188452", "tt28568397", "tt21908676", "tt15441054", "tt27542289", "tt0454876", "tt0249371", "tt0838221", "tt5074352", "tt8239946", "tt15428134", "tt24485052", "tt1954470", "tt15433600", "tt13751694", "tt15891388", "tt19755170", "tt6277462", "tt20913276", "tt18411490", "tt8672856", "tt15501640", "tt0083987", "tt2338151", "tt1188996", "tt3405236", "tt26324936", "tt8108198", "tt23036080", "tt22086334", "tt15380630", "tt0986264", "tt4430212", "tt22297828", "tt10083340", "tt27012110", "tt15245240", "tt13818368", "tt15302222", "tt1024943", "tt0248126", "tt24268454", "tt13131350", "tt0367110", "tt3863552", "tt27501039", "tt2980648", "tt10811166", "tt22892546", "tt2283748", "tt12915716", "tt15073166", "tt5935704", "tt1562872", "tt2176013", "tt15128068", "tt14099334", "tt1562871", "tt10028196", "tt1285241", "tt15654262", "tt0172684", "tt0461936", "tt0238936", "tt8130968", "tt11905536", "tt2350496", "tt15576460", "tt0891592", "tt13334578", "tt12735488", "tt0347304", "tt0361411", "tt6571548", "tt27989067", "tt3735246", "tt0195002", "tt5946128", "tt9052870", "tt15145764", "tt2178470", "tt7142506", "tt14295590", "tt0374887", "tt3495026", "tt28540171", "tt6148156", "tt0169102", "tt28282716", "tt18413766", "tt10280296", "tt3679040", "tt15134398", "tt2016894", "tt13130760", "tt11976134", "tt2555736", "tt0112870", "tt28259207", "tt7700730", "tt15600222", "tt23554840", "tt1093370", "tt7838252", "tt10895576", "tt15832148", "tt13130308", "tt8011276", "tt1166100", "tt5997666", "tt2082197", "tt1266583", "tt7212754", "tt3390572", "tt13131232", "tt1787988", "tt4559006", "tt1280558", "tt5638474", "tt7098658", "tt0292490", "tt13781794", "tt14152140", "tt11460992", "tt4635372", "tt6452574", "tt16077702", "tt1839596", "tt5690142", "tt6988116", "tt10324144", "tt8439854", "tt13130948", "tt6527426", "tt13028258", "tt0405508", "tt9263550", "tt4535650", "tt13449624", "tt2395469", "tt2112124", "tt7430722", "tt10295212", "tt7255568", "tt14428598", "tt4934950", "tt15281704", "tt26445483", "tt12856788", "tt2905838", "tt0222012", "tt7518786", "tt15516726", "tt0420332", "tt2215477", "tt5970844", "tt15680228", "tt0449999", "tt11934846", "tt27124947", "tt10230404", "tt16539454", "tt12357758", "tt8108202", "tt0265343", "tt1934231", "tt21262240", "tt0347473", "tt0284137", "tt15360286", "tt0488414", "tt0871510", "tt0213890", "tt1029231", "tt8983202", "tt12567088", "tt7721946", "tt2461132", "tt6692354", "tt4832640", "tt4110568", "tt10644708", "tt3702652", "tt6978268", "tt0379370", "tt0195231", "tt11112808", "tt15392282", "tt3678782", "tt3477214", "tt7919680", "tt2806788", "tt15257644", "tt2882328", "tt1182937", "tt5956100", "tt1395054", "tt15567704", "tt10233718", "tt15175188", "tt0073707", "tt25403492", "tt8144834", "tt11314148", "tt2387495", "tt8907992", "tt3767372", "tt27502523", "tt8816184", "tt0296574", "tt1821480", "tt0164538", "tt21626284", "tt14438964", "tt8291224", "tt9531772", "tt2980794", "tt3148502", "tt21403688", "tt1849718", "tt2224317", "tt1185420", "tt9248940", "tt12861850", "tt1833673", "tt14988886", "tt11027830", "tt15048614", "tt8426926", "tt6967980", "tt14479746", "tt18072316", "tt15309708", "tt0995740", "tt14042066", "tt12393526", "tt4900716", "tt21383812", "tt15979666", "tt13732212", "tt16139258", "tt15361028", "tt14209618", "tt1261047", "tt7363076", "tt0400234", "tt8902990", "tt2172071", "tt0449994", "tt5301942", "tt10733228", "tt3322420", "tt7059844", "tt0109555", "tt9537292", "tt15709840", "tt0422091", "tt7485048", "tt5918074", "tt0441048", "tt5460276", "tt10980562", "tt3495030", "tt6712014", "tt3175038", "tt2372222", "tt1836912", "tt12834962", "tt5080556", "tt15315164", "tt9104736", "tt0110222", "tt1926313", "tt1230448", "tt0473367", "tt8110330", "tt0242519", "tt0995031", "tt2203308", "tt1185442", "tt5885564", "tt4228746", "tt14091818", "tt7212726", "tt2067010", "tt1620719", "tt15281402", "tt12862042", "tt28362963", "tt0432637", "tt0211934", "tt1639426", "tt0240200", "tt1438298", "tt0254481", "tt0118983", "tt2229842", "tt2429640", "tt10840884", "tt6108090", "tt10598156", "tt0432047", "tt27470893", "tt9851854", "tt9054970", "tt4977530", "tt4169250", "tt1948150", "tt2356180", "tt13438922", "tt6129302", "tt1985981", "tt8396128", "tt1629376", "tt8907986", "tt26008876", "tt2181831", "tt2408040", "tt10888594", "tt4435072", "tt2527238", "tt27744786", "tt2168910", "tt0061842", "tt0126871", "tt0805184", "tt6484982", "tt8983180", "tt2213054", "tt6711660", "tt3678938", "tt13545522", "tt1274295", "tt1373156", "tt0259534", "tt6206564", "tt7399470", "tt8366590", "tt9635540", "tt6455162", "tt4434004", "tt11112532", "tt9105014", "tt14398454", "tt2106537", "tt0453671", "tt11947158", "tt1144804", "tt24225606", "tt2436516", "tt0104561", "tt13510660", "tt15314640", "tt0920464", "tt13491110", "tt3159708", "tt8504014", "tt1328634", "tt0102071", "tt3447364", "tt11783766", "tt11821912", "tt0800956", "tt5121000", "tt5571734", "tt13919802", "tt5108476", "tt7581902", "tt0337578", "tt15717242", "tt0059246", "tt5882970", "tt0367495", "tt0378072", "tt2377938", "tt14107554", "tt14339846", "tt2317337", "tt1729637", "tt5477608", "tt23023596", "tt11260832", "tt9569610", "tt0096028", "tt5472374", "tt0795434", "tt0488798", "tt0106333", "tt2762334", "tt2309764", "tt4129428", "tt13885320", "tt3043252", "tt10786774", "tt26768638", "tt9877170", "tt1227762", "tt2855648", "tt7431594", "tt10230426", "tt3679000", "tt5474036", "tt0374271", "tt15891396", "tt4559046", "tt5785170", "tt0418460", "tt2372678", "tt0156985", "tt8984572", "tt0154685", "tt1954598", "tt1077248", "tt15163652", "tt7778680", "tt0995752", "tt0152836", "tt6475412", "tt11816092", "tt6836936", "tt1428459", "tt1980986", "tt3848892", "tt22099068", "tt0418362", "tt0278291", "tt1182972", "tt5745450", "tt1327035", "tt15509266", "tt0248185", "tt0050870", "tt15204306", "tt10393870", "tt12782448", "tt0411469", "tt1321869", "tt9614452", "tt11873440", "tt4814290", "tt8983220", "tt8066940", "tt0330082", "tt0113526", "tt4007558", "tt9637132", "tt7721800", "tt10350922", "tt22932536", "tt10230414", "tt0133024", "tt17511156", "tt0151150", "tt13130532", "tt0049041", "tt0488906", "tt28364203", "tt20872920", "tt4399594", "tt0109117", "tt9248952", "tt8869978", "tt2424988", "tt0807758", "tt0319020", "tt5235880", "tt0114234", "tt21848358", "tt5705876", "tt0451850", "tt0164550", "tt8960382", "tt2181931", "tt13989310", "tt13491678", "tt5165344", "tt0464160", "tt2309987", "tt1572311", "tt8055888", "tt0150992", "tt7886848", "tt0375611", "tt1385824", "tt0439662", "tt22743064", "tt27425164", "tt0382383", "tt0111068", "tt1084972", "tt9172840", "tt1620933", "tt9098938", "tt11680920", "tt10739666", "tt9052960", "tt6923462", "tt0347332", "tt10443846", "tt0323013", "tt7725596", "tt1836987", "tt10062614", "tt13795296", "tt0099652", "tt4864932", "tt2979920", "tt1891884", "tt7469726", "tt0456144", "tt8908002", "tt1916728", "tt8108274", "tt18250130", "tt11651796", "tt5120640", "tt16139054", "tt13381376", "tt7218518", "tt15341044", "tt5662932", "tt1433810", "tt0085178", "tt8948790", "tt9420648", "tt0499375", "tt28494851", "tt0444781", "tt13143988", "tt13793230", "tt2226666", "tt23804378", "tt0991346", "tt6531196", "tt1841542", "tt16915334", "tt1667838", "tt0315642", "tt1146325", "tt2556308", "tt10534500", "tt7529298", "tt13534808", "tt0246729", "tt8361196", "tt5325684", "tt3410408", "tt0845448", "tt4430136", "tt15482442", "tt0233422", "tt0346723", "tt5255710", "tt0448206", "tt1395025", "tt4387040", "tt5456546", "tt28290264", "tt0356982", "tt2077833", "tt13912632", "tt15416100", "tt6964940", "tt0405266", "tt0405507", "tt0272736", "tt5632164", "tt4874298", "tt17425020", "tt7363104", "tt3859980", "tt9766332", "tt1708453", "tt0098999", "tt0120540", "tt9614460", "tt1499201", "tt1734110", "tt4699202", "tt11948256", "tt2385104", "tt13022984", "tt23875550", "tt0093578", "tt8130904", "tt7180544", "tt0052954", "tt0093949", "tt2302416", "tt0419058", "tt21998526", "tt5764096", "tt1301698", "tt10023024", "tt11199356", "tt10243678", "tt11142762", "tt1949548", "tt2072227", "tt6170954", "tt3696192", "tt11095208", "tt2417560", "tt0222024", "tt0082797", "tt5465370", "tt8108200", "tt1049405", "tt6264938", "tt0085743", "tt12045028", "tt4334260", "tt2301155", "tt1918965", "tt0886539", "tt0234000", "tt1433905", "tt1610452", "tt6514196", "tt5686868", "tt0307873", "tt0291376", "tt1017456", "tt28152747", "tt0466460", "tt21398196", "tt1562859", "tt6972140", "tt0077451", "tt4906960", "tt19838608", "tt1714866", "tt3337550", "tt9511468", "tt0200087", "tt2978626", "tt22036406", "tt10309902", "tt13825336", "tt7881550", "tt0430328", "tt1573072", "tt5668770", "tt13623916", "tt3823392", "tt4865436", "tt8907974", "tt10483386", "tt0119861", "tt0294662", "tt6354784", "tt11364772", "tt15121860", "tt0811066", "tt15614274", "tt12740760", "tt11102262", "tt2797242", "tt23472806", "tt9348296", "tt10895556", "tt0173080", "tt8108268", "tt7618184", "tt2112131", "tt8550208", "tt17592606", "tt1202540", "tt1890363", "tt28782545", "tt27539086", "tt5316648", "tt1275863", "tt0250415", "tt3614516", "tt23864864", "tt20840000", "tt3554418", "tt10699086", "tt0118751", "tt6588966", "tt4909752", "tt11046300", "tt0083578", "tt0110546", "tt23475174", "tt3679060", "tt11433822", "tt0477253", "tt1092005", "tt6102396", "tt0488836", "tt19394258", "tt0100095", "tt3717068", "tt8983164", "tt9648672", "tt8983228", "tt8733898", "tt10152736", "tt0216817", "tt7027278", "tt1291465", "tt9248972", "tt19864958", "tt1532957", "tt0116950", "tt9537274", "tt8176040", "tt0227194", "tt3019620", "tt2198235", "tt2621000", "tt0415908", "tt0110076", "tt6143422", "tt6926486", "tt0477252", "tt0220757", "tt4354740", "tt10230422", "tt16867258", "tt3802576", "tt0337971", "tt5713232", "tt0068257", "tt1736552", "tt0054098", "tt5613834", "tt1230165", "tt12882620", "tt2929690", "tt28635101", "tt26229612", "tt0136352", "tt0114726", "tt10964430", "tt1918886", "tt22311492", "tt10333912", "tt5743656", "tt8581230", "tt2658126", "tt0107311", "tt1120897", "tt0454431", "tt9176296", "tt6277440", "tt13562940", "tt0105866"

        # Add as many more IDs as you want...
    ]
    # /// -------------------- ///
    
    # Get the TMDB API key from the environment
    api_key = app.config.get('TMDB_API_KEY')
    if not api_key:
        print("ERROR: TMDB_API_KEY not found in your environment. Please check your .env file.")
        return

    print(f"Found {len(TMDB_IDS_TO_ADD)} movie IDs to process.")
    
    movies_added_count = 0
    movies_skipped_count = 0

    # This 'app_context' is necessary to allow the script to use the database
    with app.app_context():
        # Get all existing TMDB IDs from the database to avoid duplicates
        existing_movie_ids = {movie.tmdb_id for movie in Movie.query.with_entities(Movie.tmdb_id).all()}
        existing_series_ids = {series.tmdb_id for series in Series.query.with_entities(Series.tmdb_id).all()}
        all_existing_ids = existing_movie_ids.union(existing_series_ids)

        for tmdb_id in TMDB_IDS_TO_ADD:
            print(f"\nProcessing TMDB ID: {tmdb_id}...")

            # Check if this movie already exists in the database
            if tmdb_id in all_existing_ids:
                print(f"-> SKIPPING: A movie or series with TMDB ID '{tmdb_id}' already exists.")
                movies_skipped_count += 1
                continue

            # Fetch data from TMDB API
            try:
                url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={api_key}&append_to_response=credits"
                response = requests.get(url, timeout=10)
                response.raise_for_status() # Raise an error for bad responses (4xx or 5xx)
                data = response.json()
                
                # Construct the iframe embed code
                embed_code = f'<iframe style="border:1px #FFFFFF none" src="{IFRAME_BASE_URL}{tmdb_id}" title="iFrame" width="100%" height="600px" scrolling="no" frameborder="no" allow="fullscreen"></iframe>'

                # Extract cast info
                cast_data = data.get('credits', {}).get('cast', [])
                actors_list = []
                for member in cast_data[:10]: # Get top 10 actors
                    if member.get('name'):
                        actors_list.append({
                            "name": member.get('name'),
                            "profile_path": member.get('profile_path')
                        })
                
                # Create a new Movie object
                new_movie = Movie(
                    tmdb_id=str(data.get('id')),
                    title=data.get('title'),
                    description=data.get('overview'),
                    embed_code=embed_code,
                    poster_url=f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}" if data.get('poster_path') else None,
                    release_date=data.get('release_date'),
                    director=next((member['name'] for member in data.get('credits', {}).get('crew', []) if member.get('job') == 'Director'), None),
                    genre=", ".join([genre['name'] for genre in data.get('genres', [])]),
                    cast=json.dumps(actors_list),
                    content_type='movie'
                )

                # Add the new movie to the database session
                db.session.add(new_movie)
                print(f"-> ADDING: '{new_movie.title}' to the database.")
                movies_added_count += 1

            except requests.exceptions.RequestException as e:
                print(f"-> ERROR: Could not fetch data for TMDB ID '{tmdb_id}'. Reason: {e}")
            except Exception as e:
                print(f"-> ERROR: An unexpected error occurred for TMDB ID '{tmdb_id}': {e}")

        # Commit all the changes to the database at once
        if movies_added_count > 0:
            try:
                print("\nCommitting changes to the database...")
                db.session.commit()
                print("Successfully saved all new movies to the database.")
            except Exception as e:
                db.session.rollback()
                print(f"\nFATAL: A database error occurred during commit. No movies were saved. Error: {e}")
        else:
            print("\nNo new movies to add.")

    print("\n--- Bulk Add Complete ---")
    print(f"Movies Added: {movies_added_count}")
    print(f"Movies Skipped (already exist): {movies_skipped_count}")


if __name__ == '__main__':
    bulk_add_movies()
