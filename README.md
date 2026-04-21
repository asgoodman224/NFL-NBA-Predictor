# NFL & NBA Game Predictor

A full-stack Flask web app that predicts NFL and NBA game outcomes using an Elo rating system, with live score updates, confidence percentages, and custom historical matchup simulations.

## Features

- NFL weekly/current/full-season game predictions
- NBA daily game predictions
- Live game tracking with auto-refresh and live win probability updates
- Elo-based prediction model for both leagues
- Custom historical matchup simulator for NFL and NBA
- Team/year validation for historical matchups
- Optional SportsData.io support for enhanced NFL context (injuries/depth details)

## Tech Stack

- Backend: Flask, Flask-CORS
- Frontend: HTML, CSS, Vanilla JavaScript
- Data Sources: ESPN public endpoints, optional SportsData.io
- Deployment: Gunicorn (Procfile included)

## Project Structure

```text
.
|-- nfl.py            # Main Flask app + NFL predictor + shared static file routes
|-- nba.py            # NBA predictor blueprint and API routes
|-- index.html        # Frontend page
|-- script.js         # Frontend logic and API calls
|-- style.css         # Styling
|-- requirements.txt  # Python dependencies
|-- Procfile          # Gunicorn startup command
```

## Setup

### 1. Clone and enter the project

```bash
git clone <your-repo-url>
cd NFL-Predictor
```

### 2. Create and activate a virtual environment

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Optional environment variables

Create a `.env` file in the root if you want enhanced NFL data:

```env
SPORTSDATA_API_KEY=your_key_here
```

## Run Locally

### Development

```bash
python nfl.py
```

you can run it on my website: https://nfl-nba-predictor.onrender.com/

### Production-style (Gunicorn)

```bash
gunicorn nfl:app
```

The included Procfile uses:

```text
web: gunicorn nfl:app
```

## Using the Website

### NFL tab

- Select current week, a specific week, playoffs, or full season
- Click Load Games to view predictions
- Live games auto-refresh every 5 seconds

### NBA tab

- Select today/tomorrow/yesterday
- Click Load Games to view predictions
- Live games auto-refresh every 5 seconds when applicable

### Custom Game tab

- Switch between NFL Custom and NBA Custom
- Pick year + team for home and away sides
- Run a historical matchup prediction

## API Endpoints

### General

- `GET /` - Serve frontend
- `GET /api` - API overview
- `GET /api/status` - Service and feature status

### NFL

- `GET /api/games`
	- Query params:
		- `week=<1-22>`
		- `season=full`
		- `type=postseason`
		- `year=<season year>`
- `POST /api/predict` - Predict a single NFL game payload
- `GET /api/elo` - NFL Elo ratings
- `GET /api/teams` - All NFL teams
- `GET /api/teams/year/<year>` - NFL teams that existed that year
- `GET /api/teams/<abbr>/stats?year=<year>` - Historical NFL team stats
- `POST /api/predict/custom` - Historical NFL custom matchup

### NBA

- `GET /api/nba/games?date=YYYYMMDD` - NBA games + predictions for date
- `GET /api/nba/teams` - All NBA teams
- `GET /api/nba/teams/year/<year>` - NBA teams that existed that year
- `GET /api/nba/teams/<abbr>/stats?year=<year>` - Historical NBA team stats
- `GET /api/nba/standings` - NBA standings
- `GET /api/nba/elo` - NBA Elo ratings
- `POST /api/nba/predict/custom` - Historical NBA custom matchup

## Example Requests

Get current NFL games:

```bash
curl http://localhost:5000/api/games
```

Get NFL week 1 in 2025:

```bash
curl "http://localhost:5000/api/games?week=1&year=2025"
```

Get NBA games for a specific date:

```bash
curl "http://localhost:5000/api/nba/games?date=20260421"
```

NFL custom matchup:

```bash
curl -X POST http://localhost:5000/api/predict/custom \
	-H "Content-Type: application/json" \
	-d '{
		"home_team": "KC",
		"home_year": 2023,
		"away_team": "SF",
		"away_year": 2019,
		"neutral_site": false
	}'
```

## Notes

- Predictions are for entertainment purposes only.
- Live scores and game availability depend on upstream API availability.
- Historical team naming/availability is constrained by configured team metadata and year rules in the backend.

## License

Add your preferred license here (for example, MIT) if you plan to distribute publicly.
