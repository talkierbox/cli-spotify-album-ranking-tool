#!/usr/bin/env python3
"""
Album Tier List from a Spotify Playlist (CLI)
Use python 3.8+
"""

from __future__ import annotations

import os
import sys
import math
import json
import ast
import re
import glob
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from dotenv import load_dotenv

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
except ImportError:
    print("Missing dependency: spotipy. Install with `pip install spotipy`.")
    sys.exit(1)
    
load_dotenv(dotenv_path="secrets.env")

@dataclass
class AlbumInfo:
    album_id: str
    name: str
    artists: str
    url: str
    image_url: Optional[str]
    playlist_track_titles: List[str] = field(default_factory=list)

    @property
    def count_in_playlist(self) -> int:
        return len(self.playlist_track_titles)

# ---------------------------
# Spotify helpers
# ---------------------------

SCOPES = "playlist-read-private playlist-read-collaborative"

def get_spotify_client() -> spotipy.Spotify:
    """
    Initialize Spotipy client using OAuth. Expects:
      SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, SPOTIPY_REDIRECT_URI
    """
    # Minimal sanity check for credentials
    if not os.getenv("SPOTIPY_CLIENT_ID"):
        print("SPOTIPY_CLIENT_ID not set.")
    if not os.getenv("SPOTIPY_CLIENT_SECRET"):
        print("SPOTIPY_CLIENT_SECRET not set.")
    if not os.getenv("SPOTIPY_REDIRECT_URI"):
        print("SPOTIPY_REDIRECT_URI not set.")

    auth_manager = SpotifyOAuth(scope=SCOPES, open_browser=True, cache_path=".spotipy_cache")
    return spotipy.Spotify(auth_manager=auth_manager)

def parse_playlist_id(link: str) -> str:
    link = link.strip()
    if link.startswith("spotify:playlist:"):
        return link.split(":")[-1]
    if "open.spotify.com/playlist/" in link:
        core = link.split("open.spotify.com/playlist/")[1]
        return core.split("?")[0].split("/")[0]
    return link  # raw ID

def fetch_albums_from_playlist(sp: spotipy.Spotify, playlist_id: str, min_tracks_per_album: int = 4) -> List[AlbumInfo]:
    """
    Crawl playlist items and group by album; keep albums with count >= threshold.
    """
    albums: Dict[str, AlbumInfo] = {}
    limit, offset = 100, 0

    while True:
        page = sp.playlist_items(playlist_id, limit=limit, offset=offset)
        items = page.get("items", [])
        if not items:
            break

        for it in items:
            track = it.get("track")
            if not track:
                continue
            album = track.get("album")
            if not album:
                continue
            a_id = album.get("id")
            if not a_id:
                continue  # local/unsupported

            images = album.get("images") or []
            img_url = images[0]["url"] if images else None
            url = album.get("external_urls", {}).get("spotify", f"https://open.spotify.com/album/{a_id}")
            artists = ", ".join([a["name"] for a in album.get("artists", [])])

            if a_id not in albums:
                albums[a_id] = AlbumInfo(
                    album_id=a_id,
                    name=album.get("name", "Unknown Album"),
                    artists=artists,
                    url=url,
                    image_url=img_url,
                    playlist_track_titles=[]
                )
            title = track.get("name", "Unknown Track")
            albums[a_id].playlist_track_titles.append(title)

        offset += len(items)
        if len(items) < limit:
            break

    filtered = [a for a in albums.values() if a.count_in_playlist >= min_tracks_per_album]
    filtered.sort(key=lambda x: (-x.count_in_playlist, x.artists.lower(), x.name.lower()))
    return filtered

# ---------------------------
# Interactive ranking (binary insertion with comparisons)
# ---------------------------

# Global counter for tracking comparisons
_comparison_count = 0
_total_comparisons = 0

def print_album(a: AlbumInfo) -> None:
    print(f"  {a.name} — {a.artists}  (tracks in playlist: {a.count_in_playlist})")
    print(f"  {a.url}")

def ask_preference(a: AlbumInfo, b: AlbumInfo) -> int:
    """
    Return 1 if user prefers a over b; 2 if b over a.
    """
    global _comparison_count, _total_comparisons
    
    while True:
        remaining = _total_comparisons - _comparison_count
        print(f"\n=== Comparison {_comparison_count + 1}/{_total_comparisons} ({remaining} remaining) ===")
        print("Which album do you prefer?")
        print(" [1]")
        print_album(a)
        print(" [2]")
        print_album(b)
        choice = input("Choose 1/2 (or 'i' for track list, 'q' to quit): ").strip().lower()
        if choice == "1":
            _comparison_count += 1
            return 1
        if choice == "2":
            _comparison_count += 1
            return 2
        if choice == "i":
            print("\n--- Track snippets from this playlist ---")
            print(f"{a.name}:")
            for t in a.playlist_track_titles[:10]:
                print(f"   - {t}")
            if len(a.playlist_track_titles) > 10:
                print(f"   ...(+{len(a.playlist_track_titles)-10} more)")
            print(f"\n{b.name}:")
            for t in b.playlist_track_titles[:10]:
                print(f"   - {t}")
            if len(b.playlist_track_titles) > 10:
                print(f"   ...(+{len(b.playlist_track_titles)-10} more)")
            print("-----------------------------------------\n")
            continue
        if choice == "q":
            print("Aborted.")
            sys.exit(0)
        print("Invalid input. Try again.")

def estimate_comparisons(n: int) -> int:
    """Estimate total comparisons needed for binary insertion sort."""
    if n <= 1:
        return 0
    # Binary insertion sort: sum from i=1 to n-1 of log2(i)
    total = 0
    for i in range(2, n + 1):
        total += math.ceil(math.log2(i))
    return total

def rank_albums_by_comparisons(albums: List[AlbumInfo]) -> List[AlbumInfo]:
    """
    Binary insertion sort using interactive comparisons with progress tracking.
    """
    global _comparison_count, _total_comparisons
    
    if not albums:
        return []
    
    # Initialize counters
    _comparison_count = 0
    _total_comparisons = estimate_comparisons(len(albums))
    
    print(f"\n🎵 Starting album ranking!")
    print(f"📊 Estimated comparisons needed: ~{_total_comparisons}")
    
    ordered: List[AlbumInfo] = [albums[0]]
    for i in range(1, len(albums)):
        x = albums[i]
        lo, hi = 0, len(ordered)
        while lo < hi:
            mid = (lo + hi) // 2
            pref = ask_preference(x, ordered[mid])  # prefer x over mid?
            if pref == 1:
                hi = mid
            else:
                lo = mid + 1
        ordered.insert(lo, x)
        progress = (_comparison_count / _total_comparisons) * 100 if _total_comparisons > 0 else 100
        print(f"✅ Inserted: {x.name} — position {lo+1} of {len(ordered)} | Progress: {progress:.1f}%")
    
    print(f"\n🎉 Ranking complete! Used {_comparison_count} comparisons.")
    return ordered

# ---------------------------
# Percentile-based scoring
# ---------------------------

def round_to_quarter(x: float) -> float:
    return round(x * 4) / 4.0

_percent_pat = re.compile(r"^\s*(\d+(\.\d+)?)\s*%?\s*$")

def _parse_key_to_frac(k) -> Optional[float]:
    """
    Accepts keys like 0.9, 90, '90', '90%', '0.9'.
    Returns fraction in [0,1] or None if invalid.
    """
    if isinstance(k, (int, float)):
        val = float(k)
        if val > 1.0:
            val = val / 100.0
        return min(max(val, 0.0), 1.0)
    if isinstance(k, str):
        m = _percent_pat.match(k)
        if not m:
            return None
        val = float(m.group(1))
        if "%" in k or val > 1.0:
            val = val / 100.0
        return min(max(val, 0.0), 1.0)
    return None

def parse_thresholds_dict(s: str) -> Dict[float, float]:
    """
    Parse a user-supplied dict mapping percentile -> score.
    Keys may be 0–1, 0–100, or '90%'. Values are scores (e.g., 6..10).
    """
    if not s.strip():
        # sensible default
        return {
            0.99: 10.0,
            0.90: 9.5,
            0.75: 8.75,
            0.25: 7.5,
            0.00: 6.0,
        }
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        # try Python literal dict
        data = ast.literal_eval(s)
    out: Dict[float, float] = {}
    for k, v in data.items():
        frac = _parse_key_to_frac(k)
        if frac is None:
            continue
        try:
            score = float(v)
        except Exception:
            continue
        out[frac] = score
    if not out:
        raise ValueError("Could not parse any valid thresholds.")
    # ensure 0.0 is present (floor)
    if 0.0 not in out:
        out[0.0] = min(out.values())
    # ensure 1.0 is present (ceiling) to make behavior obvious; use max
    if 1.0 not in out:
        out[1.0] = max(out.values())
    return out

def percentile_from_rank(rank_index: int, n: int) -> float:
    """
    Best item (rank_index=0) -> 1.0 ; worst (rank_index=n-1) -> 0.0.
    """
    if n <= 1:
        return 1.0
    return 1.0 - (rank_index / (n - 1))

def assign_scores_percentile(
    ranked: List[AlbumInfo],
    thresholds: Dict[float, float],
    clamp_min: float = 6.0,
    clamp_max: float = 10.0,
    quarter_round: bool = True,
    interpolate: bool = False,
) -> List[Tuple[int, AlbumInfo, float]]:
    """
    Map each album to a score by its percentile among ranked items.

    thresholds: dict {fraction in [0,1]: score}. Interpreted as lower bounds.
      Example (sorted descending by percentile):
        {1.00: 10, 0.90: 9.75, 0.75: 9.5, 0.60: 9.25, 0.40: 8.5, 0.20: 7.5, 0.00: 6}
    Behavior:
      - step (default): pick the highest threshold <= album's percentile
      - interpolate=True: piecewise-linear interpolate between adjacent thresholds
      - quarter_round: round to nearest 0.25 to include .25/.5/.75
      - clamp to [clamp_min, clamp_max]
    """
    if not ranked:
        return []

    # sort thresholds ascending by percentile for easier neighbor lookup
    pts = sorted((max(0.0, min(1.0, p)), float(s)) for p, s in thresholds.items())
    results: List[Tuple[int, AlbumInfo, float]] = []

    for r, album in enumerate(ranked):
        p = percentile_from_rank(r, len(ranked))

        # find bracketing points
        lo_p, lo_s = pts[0]
        hi_p, hi_s = pts[-1]
        for i in range(len(pts)):
            if pts[i][0] <= p:
                lo_p, lo_s = pts[i]
            if pts[i][0] >= p:
                hi_p, hi_s = pts[i]
                break

        if not interpolate or lo_p == hi_p:
            score = lo_s if p >= lo_p else hi_s  # step function
        else:
            # linear interpolation between lo and hi
            t = 0.0 if hi_p == lo_p else (p - lo_p) / (hi_p - lo_p)
            score = lo_s + t * (hi_s - lo_s)

        # clamp and round
        score = max(clamp_min, min(clamp_max, score))
        if quarter_round:
            score = round_to_quarter(score)

        results.append((r + 1, album, float(score)))

    return results

# ---------------------------
# CSV export
# ---------------------------

def maybe_export_csv(rows: List[Tuple[int, AlbumInfo, float]]) -> None:
    ans = input("Export results to CSV? [y/N]: ").strip().lower()
    if ans != "y":
        return
    path = input("CSV path (default: album_tiers.csv): ").strip() or "album_tiers.csv"
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "score", "album", "artists", "tracks_in_playlist", "album_url", "album_id"])
        for rank, album, score in rows:
            w.writerow([rank, score, album.name, album.artists, album.count_in_playlist, album.url, album.album_id])
    print(f"Wrote {path}")

# ---------------------------
# CSV import for rescoring
# ---------------------------

def load_albums_from_csv(csv_path: str) -> List[AlbumInfo]:
    """
    Load album ranking from existing CSV file.
    """
    import csv
    albums = []
    
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                album = AlbumInfo(
                    album_id=row.get("album_id", ""),
                    name=row.get("album", "Unknown Album"),
                    artists=row.get("artists", "Unknown Artist"),
                    url=row.get("album_url", ""),
                    image_url=None,  # Not stored in CSV
                    playlist_track_titles=[]  # Will be empty for CSV imports
                )
                # Set track count from CSV
                try:
                    track_count = int(row.get("tracks_in_playlist", "0"))
                    album.playlist_track_titles = [f"Track {i+1}" for i in range(track_count)]
                except ValueError:
                    pass
                albums.append(album)
        
        print(f"✅ Loaded {len(albums)} albums from {csv_path}")
        return albums
        
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return []

def find_csv_files() -> List[str]:
    """
    Find CSV files in the current directory.
    """
    return glob.glob("*.csv")

# ---------------------------
# Main flow
# ---------------------------

def main():
    print("=== Spotify Album Tier List Builder ===")
    
    # Check for existing CSV files
    csv_files = find_csv_files()
    if csv_files:
        print(f"\n📁 Found existing CSV file(s): {', '.join(csv_files)}")
        rescore_choice = input("Would you like to rescore an existing CSV instead of fresh ranking? [y/N]: ").strip().lower()
        
        if rescore_choice == "y":
            if len(csv_files) == 1:
                csv_path = csv_files[0]
                print(f"Using: {csv_path}")
            else:
                print("\nSelect CSV file:")
                for i, csv_file in enumerate(csv_files, 1):
                    print(f" [{i}] {csv_file}")
                try:
                    choice = int(input("Choose number: ").strip()) - 1
                    if 0 <= choice < len(csv_files):
                        csv_path = csv_files[choice]
                    else:
                        print("Invalid choice. Using first file.")
                        csv_path = csv_files[0]
                except ValueError:
                    print("Invalid input. Using first file.")
                    csv_path = csv_files[0]
            
            # Load albums from CSV (already ranked)
            ranked = load_albums_from_csv(csv_path)
            if not ranked:
                print("Failed to load CSV. Starting fresh ranking instead.")
            else:
                print(f"📊 Loaded ranking from {csv_path}")
                # Skip to scoring section
                print("\n=== Rescoring from CSV ===")
                print("Current ranking:")
                for i, album in enumerate(ranked, 1):
                    print(f"{i:>2}. {album.name} — {album.artists} (tracks: {album.count_in_playlist})")
                
                input("\nPress Enter to proceed with rescoring...")
                
                # Jump to scoring section
                print("\n=== Scoring (Percentile-based) ===")
                print("Provide a dict mapping percentile -> score. Keys can be 0–1, 0–100, or strings like '90%'.")
                print("Press Enter for a sensible default: {99%:10, 90%:9.5, 75%:8.75, 25%:7.5, 0%:6}")
                raw = input("Thresholds dict: ").strip()
                try:
                    thresholds = parse_thresholds_dict(raw)
                except Exception as e:
                    print(f"Could not parse thresholds ({e}). Using default.")
                    thresholds = parse_thresholds_dict("")

                try:
                    clamp_min = float(input("Min clamp (default 6.0): ").strip() or "6.0")
                    clamp_max = float(input("Max clamp (default 10.0): ").strip() or "10.0")
                    if clamp_max <= clamp_min:
                        print("Max must be > min. Using 6.0–10.0.")
                        clamp_min, clamp_max = 6.0, 10.0
                except ValueError:
                    clamp_min, clamp_max = 6.0, 10.0

                quarter_ans = (input("Round to nearest 0.25? [Y/n]: ").strip().lower() or "y") == "y"
                interp_ans = (input("Piecewise-linear interpolate between thresholds? [y/N]: ").strip().lower() or "n") == "y"

                scored = assign_scores_percentile(
                    ranked,
                    thresholds=thresholds,
                    clamp_min=clamp_min,
                    clamp_max=clamp_max,
                    quarter_round=quarter_ans,
                    interpolate=interp_ans,
                )

                print("\n=== Final Album Tier List (Rescored) ===")
                for rank, album, score in scored:
                    print(f"{rank:>2}. {album.name} — {album.artists}  |  Score: {score:>4}  |  In-playlist tracks: {album.count_in_playlist}")
                    print(f"    {album.url}")

                maybe_export_csv(scored)
                print("\nDone. Enjoy your rescored tier list!")
                return

    print("You'll be asked to log in to Spotify in a browser if needed.\n")

    sp = get_spotify_client()

    playlist_link = input("Paste your Spotify playlist link/URI/ID: ").strip()
    if not playlist_link:
        print("No playlist provided.")
        sys.exit(1)
    playlist_id = parse_playlist_id(playlist_link)

    try:
        meta = sp.playlist(playlist_id, fields="name,owner(display_name)")
        print(f"\nPlaylist: {meta.get('name','(unknown)')}  |  Owner: {meta.get('owner',{}).get('display_name','(unknown)')}")
    except spotipy.SpotifyException as e:
        print(f"Failed to read playlist: {e}")
        sys.exit(1)

    try:
        min_tracks = input("Minimum tracks per album to include (default 4): ").strip()
        min_tracks_per_album = int(min_tracks) if min_tracks else 4
    except ValueError:
        min_tracks_per_album = 4

    print("\nFetching albums…")
    albums = fetch_albums_from_playlist(sp, playlist_id, min_tracks_per_album)
    if not albums:
        print(f"No albums found with ≥ {min_tracks_per_album} tracks in this playlist.")
        sys.exit(0)

    print(f"Found {len(albums)} album(s) meeting the threshold.\n")
    for a in albums:
        print(f"- {a.name} — {a.artists} (tracks in playlist: {a.count_in_playlist})")

    print(f"\n🎮 Ready to start ranking? You'll compare albums head-to-head!")
    print("💡 Tip: Use 'i' during any comparison to see track lists")
    input("Press Enter to begin ranking…")
    
    ranked = rank_albums_by_comparisons(albums)

    # -------- Scoring (Percentile-based) --------
    print("\n=== Scoring (Percentile-based) ===")
    print("Provide a dict mapping percentile -> score. Keys can be 0–1, 0–100, or strings like '90%'.")
    print("Press Enter for a sensible default: {99%:10, 90%:9.5, 75%:8.75, 25%:7.5, 0%:6}")
    raw = input("Thresholds dict: ").strip()
    try:
        thresholds = parse_thresholds_dict(raw)
    except Exception as e:
        print(f"Could not parse thresholds ({e}). Using default.")
        thresholds = parse_thresholds_dict("")

    try:
        clamp_min = float(input("Min clamp (default 6.0): ").strip() or "6.0")
        clamp_max = float(input("Max clamp (default 10.0): ").strip() or "10.0")
        if clamp_max <= clamp_min:
            print("Max must be > min. Using 6.0–10.0.")
            clamp_min, clamp_max = 6.0, 10.0
    except ValueError:
        clamp_min, clamp_max = 6.0, 10.0

    quarter_ans = (input("Round to nearest 0.25? [Y/n]: ").strip().lower() or "y") == "y"
    interp_ans = (input("Piecewise-linear interpolate between thresholds? [y/N]: ").strip().lower() or "n") == "y"

    scored = assign_scores_percentile(
        ranked,
        thresholds=thresholds,
        clamp_min=clamp_min,
        clamp_max=clamp_max,
        quarter_round=quarter_ans,
        interpolate=interp_ans,
    )

    print("\n=== Final Album Tier List ===")
    for rank, album, score in scored:
        print(f"{rank:>2}. {album.name} — {album.artists}  |  Score: {score:>4}  |  In-playlist tracks: {album.count_in_playlist}")
        print(f"    {album.url}")

    maybe_export_csv(scored)
    print("\nDone. Enjoy your tier list!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted. Bye.")
