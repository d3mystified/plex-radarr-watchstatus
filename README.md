Sync watch status from Plex server(s) to Radarr using tags.

Run with:

```
docker run \
	-e PLEX_SERVERS=https://plex.local:$token,https://another_plex.remote:$token \
	-e PLEX_LIBRARY_NAMES=Movies,4K_Movies \
	-e RADARR_URL=https://radarr.local/radarr \
	-e RADARR_API_KEY=$api_key \
	ghcr.io/d3mystified/plex-radarr-watchstatus:main
```
