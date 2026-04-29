# NFL & NBA Game Predictor

Live site:
https://nfl-nba-predictor.onrender.com/

## How the Website Works

This website has three main sections:

1. NFL tab
- Choose a week (current week, specific week, playoffs, or full season).
- Click Load Games.
- You will see matchup cards with predictions, confidence, and live/final score info.

2. NBA tab
- Choose a date from the dropdown (wider date range supported).
- Click Load Games.
- You will see NBA matchup predictions and live/final game updates.

3. Custom Game tab
- Switch between NFL Custom and NBA Custom.
- Pick home team/year and away team/year.
- Click Predict to run a historical matchup prediction.

## What You Need Installed

- Python 3.10+ (recommended)
- pip (comes with most Python installs)
Python packages used by this repo are in requirements.txt and include:
- Flask
- flask-cors
- requests
- python-dotenv
- gunicorn

## Run From This Repo

1. Open a terminal in the repository root.

2. Create and activate a virtual environment.

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

3. Install dependencies.
```bash
pip install -r requirements.txt
```

4. Start the app.
```bash
python nfl.py
```

5. Open in your browser:
http://localhost:5000

## Optional Environment Variable

If you want enhanced NFL data, create a .env file in the repo root with:

```env
SPORTSDATA_API_KEY=your_key_here
```

The app still runs without this key.
