Sync watch status from Plex server(s) to Radarr using tags.

[![Hippocratic License HL3-BDS-ECO-EXTR-FFD-LAW-MIL](https://img.shields.io/static/v1?label=Hippocratic%20License&message=HL3-BDS-ECO-EXTR-FFD-LAW-MIL&labelColor=5e2751&color=bc8c3d)](https://firstdonoharm.dev/version/3/0/bds-eco-extr-ffd-law-mil.html)

Run with:

```bash
docker run \
	-e PLEX_SERVERS=https://plex.local:$token,https://another_plex.remote:$token \
	-e PLEX_LIBRARY_NAMES=Movies,4K_Movies \
	-e RADARR_URL=https://radarr.local/radarr \
	-e RADARR_API_KEY=$api_key \
	-e HC_BASE=https://hc-ping.com/12345 # healthchecks.io ping URL \
	ghcr.io/d3mystified/plex-radarr-watchstatus:main
```
