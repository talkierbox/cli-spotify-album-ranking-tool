# Spotify Album Tier List Builder

Interactive CLI tool to rank albums from your Spotify playlist and assign tier list scores.

## Features

- 🎵 Extract albums from any Spotify playlist
- 🏆 Interactive pairwise comparison ranking (tournament-style)
- 📊 Percentile-based scoring with customizable thresholds
- 📈 Progress tracking during comparisons
- 📄 CSV export for results
- 🔄 Rescore existing CSV files with new thresholds

## Setup

1. Install dependencies:
   ```bash
   pip install spotipy python-dotenv
   ```

2. Create Spotify app at [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)

3. Set environment variables:
Create a file called `secrets.env` and use the template from `example.env`!

## Usage

```bash
python main.py
```

1. Paste your Spotify playlist link
2. Set minimum tracks per album (default: 4)
3. Compare albums head-to-head until ranking is complete
4. Configure scoring thresholds (or use defaults)
5. Export to CSV

## Scoring

Default percentile thresholds:
- Top 1% → 10.0
- Top 10% → 9.5  
- Top 25% → 8.75
- Bottom 75% → 7.5
- Bottom → 6.0

Scores are rounded to nearest 0.25 (e.g., 8.25, 8.5, 8.75).

## Tips

- Use `i` during comparisons to see track lists
- The tool estimates ~log₂(n) comparisons per album
- CSV files in the directory can be rescored with new thresholds
