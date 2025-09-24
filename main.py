import logging
import os
import plexapi
from plexapi.server import PlexServer
from pyarr import RadarrAPI

# Set to "true" to see what the script would do without making changes.
DRY_RUN = os.getenv('DRY_RUN', 'false').lower() == 'true'

# Comma-separated list of Plex servers, each in the format: http://<url>:<port>:<token>
# Example: "http://192.168.1.10:32400:TOKEN_A,http://plex.example.com:32400:TOKEN_B"
PLEX_SERVERS_STR = os.getenv('PLEX_SERVERS')
# Comma-separated list of library names to scan on each server
PLEX_LIBRARY_NAMES = os.getenv('PLEX_LIBRARY_NAMES', 'Movies').split(',')

# Radarr connection details
RADARR_URL = os.getenv('RADARR_URL')
RADARR_API_KEY = os.getenv('RADARR_API_KEY')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def validate_config():
    """Validates that all necessary environment variables are set."""
    if not all([PLEX_SERVERS_STR, RADARR_URL, RADARR_API_KEY]):
        logging.error("Missing required environment variables. Please set PLEX_SERVERS, RADARR_URL, and RADARR_API_KEY.")
        return False
    return True

def get_plex_data():
    """Connects to Plex servers and discovers all users, including the admin."""
    plex_servers = []
    all_users = set()
    admin_user = None

    if not PLEX_SERVERS_STR:
        return [], [], None

    for server_info in PLEX_SERVERS_STR.split(','):
        try:
            # Safely split URL and token (handles colons in URL)
            url, token = server_info.strip().rsplit(':', 1)
            server = PlexServer(url, token)

            # Get account details to find users
            account = server.myPlexAccount()

            # Set the admin user if not already set
            if not admin_user:
                admin_user = account.title

            # Add the main account holder (admin)
            all_users.add(account.title)
            # Add all managed users
            for user in account.users():
                all_users.add(user.title)

            plex_servers.append(server)
            logging.info(f"Successfully connected to Plex server: {server.friendlyName}")
        except Exception as e:
            logging.warning(f"Could not connect to or get users from server entry '{server_info}'. Skipping. Error: {e}")

    return plex_servers, list(all_users), admin_user

def main():
    """Main function to sync watch statuses."""
    if not validate_config():
        exit(1)

    # Connect to Radarr
    try:
        radarr = RadarrAPI(RADARR_URL, RADARR_API_KEY)
        logging.info("Successfully connected to Radarr.")
    except Exception as e:
        logging.error(f"Could not connect to Radarr: {e}")
        return

    # Get Plex Servers and Users
    plex_servers, plex_users, admin_user = get_plex_data()
    if not plex_servers or not plex_users:
        logging.error("Could not connect to any Plex servers or find users. Exiting.")
        return
    logging.info(f"Found users to process: {plex_users}")
    if admin_user:
        logging.info(f"Admin user identified as: {admin_user}")

    # Build a Plex library lookup map
    logging.info("Building Plex movie lookup maps...")
    plex_lookup_maps = {}
    for server in plex_servers:
        server_map = {}
        for library_name in PLEX_LIBRARY_NAMES:
            try:
                movie_library = server.library.section(library_name)
                for plex_movie in movie_library.all():
                    if not hasattr(plex_movie, 'guids'):
                        continue
                    for guid in plex_movie.guids:
                        if guid.id.startswith('tmdb://'):
                            try:
                                tmdb_id = int(guid.id.split('//')[1])
                                server_map[tmdb_id] = plex_movie.ratingKey
                                break
                            except (ValueError, IndexError):
                                continue
                logging.info(f"Built map for '{server.friendlyName} - {library_name}' with {len(server_map)} movies.")
            except Exception as e:
                logging.warning(f"Could not build map for library '{library_name}' on server '{server.friendlyName}': {e}")
        plex_lookup_maps[server.machineIdentifier] = server_map

    # Get all movies and tags from Radarr
    radarr_movies = radarr.get_movie()
    radarr_tags = radarr.get_tag()
    logging.info(f"Found {len(radarr_movies)} movies in Radarr.")
    
    dry_run_data = {user: {'add': [], 'remove': []} for user in plex_users}

    # Main Sync Logic
    for movie in radarr_movies:
        movie_title = movie['title']
        radarr_tmdb_id = movie.get("tmdbId")
        if not radarr_tmdb_id:
            logging.info(f"No TMDB Id for movie {movie_title}. Skipping...")
            continue

        logging.info(f"Processing movie: {movie_title} (TMDB ID: {radarr_tmdb_id})")
        plex_guid = f"tmdb://{radarr_tmdb_id}"

        for user in plex_users:
            watched_status_per_server = {}
            
            for server in plex_servers:
                try:
                    rating_key = plex_lookup_maps.get(server.machineIdentifier, ()).get(radarr_tmdb_id)
                    if not rating_key:
                        continue

                    server_for_user = server if user == admin_user else server.switchUser(user)
                    user_specific_plex_movie = server_for_user.fetchItem(rating_key)
                    watched_status_per_server[server.friendlyName] = user_specific_plex_movie.isWatched
                except plexapi.exceptions.NotFound:
                    # Movie not found in plex
                    continue

            if not watched_status_per_server:
                continue
            
            is_watched = True if True in watched_status_per_server.values() else False
            if len(set(watched_status_per_server.values())) > 1:
                logging.warning(f"Conflict for '{movie_title}' and user '{user}'. Watched statuses: {watched_status_per_server}. Marking as watched.")
                is_watched = True

            # Tagging Logic
            tag_name = f"watched_by_{user}".lower()
            tag_id = next((tag['id'] for tag in radarr_tags if tag['label'] == tag_name), None)
            movie_tags = movie.get('tags', [])
            
            if is_watched:
                if tag_id not in movie_tags:
                    if DRY_RUN:
                        dry_run_data[user]['add'].append(movie_title)
                    else:
                        if not tag_id:
                            new_tag = radarr.create_tag(label=tag_name)
                            print(new_tag)
                            tag_id = new_tag['id']
                            radarr_tags.append(new_tag)
                        
                        movie['tags'].append(tag_id)
                        radarr.upd_movie(movie)
                        logging.info(f"Added tag '{tag_name}' to '{movie_title}'.")
            else:
                if tag_id and tag_id in movie_tags:
                    if DRY_RUN:
                        dry_run_data[user]['remove'].append(movie_title)
                    else:
                        movie['tags'].remove(tag_id)
                        radarr.upd_movie(movie)
                        logging.info(f"Removed tag '{tag_name}' from '{movie_title}'.")

    # Dry-run output
    if DRY_RUN:
        logging.info("\n--- DRY RUN SUMMARY ---")
        for user, actions in dry_run_data.items():
            if actions['add'] or actions['remove']:
                logging.info(f"\n--- User: {user} ---")
                if actions['add']:
                    logging.info("Movies to be tagged as watched:")
                    for title in actions['add']:
                        logging.info(f"- {title}")
                if actions['remove']:
                    logging.info("\nMovies to have 'watched' tag removed:")
                    for title in actions['remove']:
                        logging.info(f"- {title}")
        logging.info("\n--- END OF DRY RUN SUMMARY ---")

if __name__ == '__main__':
    main()
