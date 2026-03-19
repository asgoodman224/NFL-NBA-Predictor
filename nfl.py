from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

# grab any saved settings from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# my api keys go here
API_KEYS = {
    'ESPN_API': '',  # espn doesn't need a key which is nice
    'SPORTSDATA_IO': os.environ.get('SPORTSDATA_API_KEY', ''),  
}

class NFLPredictor:
    def __init__(self):
        self.espn_base_url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
        self.sportsdata_base_url = "https://api.sportsdata.io/v3/nfl"
        self.cache = {}
        self.cache_timeout = 3600  # cache stuff for an hour so we dont spam the api
        
        # logistic regression model for predictions
        self.model = LogisticRegression(max_iter=1000, random_state=42)
        self.scaler = StandardScaler()
        self.model_trained = False
        
        # train the model when we start up
        self.train_model()
        
    def get_current_week_games(self):
        """gets this weeks games from espn"""
        try:
            url = f"{self.espn_base_url}/scoreboard"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            games = []
            if 'events' in data:
                for event in data['events']:
                    game_info = self.parse_espn_game(event)
                    if game_info:
                        games.append(game_info)
            
            return games
        except Exception as e:
            print(f"Error fetching games from ESPN: {e}")
            return self.get_fallback_games()
    
    def get_week_games(self, season_type=2, week=1, year=2025):
        """grabs games for whatever week you want
        season_type: 1=preseason, 2=regular season, 3=playoffs
        """
        try:
            url = f"{self.espn_base_url}/scoreboard?seasontype={season_type}&week={week}&dates={year}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            games = []
            if 'events' in data:
                for event in data['events']:
                    game_info = self.parse_espn_game(event)
                    if game_info:
                        game_info['week'] = week
                        game_info['season_type'] = season_type
                        games.append(game_info)
            
            return games
        except Exception as e:
            print(f"Error fetching week {week} games: {e}")
            return []
    
    def get_full_season(self, year=2025):
        """gets every single game in the season - takes a bit"""
        all_games = []
        
        # loop through all 18 weeks of regular season
        print(f"Fetching {year} regular season...")
        for week in range(1, 19):
            games = self.get_week_games(season_type=2, week=week, year=year)
            all_games.extend(games)
            print(f"  Week {week}: {len(games)} games")
        
        # now grab the playoff games too
        print(f"Fetching {year} postseason...")
        postseason_names = {1: 'Wild Card', 2: 'Divisional', 3: 'Conference Championships', 4: 'Super Bowl'}
        for week in range(1, 5):
            games = self.get_week_games(season_type=3, week=week, year=year)
            for game in games:
                game['round'] = postseason_names.get(week, f'Postseason Week {week}')
            all_games.extend(games)
            print(f"  {postseason_names.get(week, f'Week {week}')}: {len(games)} games")
        
        return all_games
    
    def parse_espn_game(self, event):
        """pulls out the important stuff from espn's game data"""
        try:
            competition = event['competitions'][0]
            competitors = competition['competitors']
            
            home_team = next(team for team in competitors if team['homeAway'] == 'home')
            away_team = next(team for team in competitors if team['homeAway'] == 'away')
            
            # get each teams win-loss record
            home_record = home_team.get('records', [{}])[0].get('summary', '0-0') if home_team.get('records') else '0-0'
            away_record = away_team.get('records', [{}])[0].get('summary', '0-0') if away_team.get('records') else '0-0'
            
            return {
                'game_id': event['id'],
                'home_team': home_team['team']['displayName'],
                'away_team': away_team['team']['displayName'],
                'home_team_abbr': home_team['team']['abbreviation'],
                'away_team_abbr': away_team['team']['abbreviation'],
                'home_record': home_record,
                'away_record': away_record,
                'game_date': event.get('date', ''),
                'venue': competition.get('venue', {}).get('fullName', 'TBD'),
                'status': event.get('status', {}).get('type', {}).get('description', 'Scheduled')
            }
        except Exception as e:
            print(f"Error parsing game: {e}")
            return None
    
    def get_team_stats(self, team_abbr):
        """looks up how good a team is based on their record"""
        cache_key = f'team_stats_{team_abbr}'
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        stats = {
            'offense_rating': 70,
            'defense_rating': 70,
            'recent_form': 70,
            'win_pct': 0.5
        }
        
        # check standings to see how many games theyve won
        try:
            standings = self.get_standings()
            if standings and team_abbr in standings:
                team_record = standings[team_abbr]
                wins = team_record.get('wins', 0)
                losses = team_record.get('losses', 0)
                total = wins + losses
                
                if total > 0:
                    win_pct = wins / total
                    # better record = better ratings basically
                    stats['offense_rating'] = 50 + (win_pct * 50)
                    stats['defense_rating'] = 50 + (win_pct * 50)
                    stats['win_pct'] = win_pct
                    
                    # also factor in if they score a lot vs give up a lot
                    pts_for = team_record.get('points_for', 0)
                    pts_against = team_record.get('points_against', 0)
                    if pts_for > 0 and pts_against > 0:
                        pts_diff = (pts_for - pts_against) / total
                        # teams that outscore opponents get bumped up
                        stats['offense_rating'] = min(100, max(50, 70 + pts_diff))
                        stats['defense_rating'] = min(100, max(50, 70 - (pts_against / total - 20)))
        except Exception as e:
            print(f"Error fetching team stats: {e}")
        
        self.cache[cache_key] = stats
        return stats
    
    def get_standings(self, year=2025):
        """grabs the current nfl standings"""
        cache_key = f'standings_{year}'
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        standings = {}
        
        try:
            url = f"{self.espn_base_url}/standings?season={year}"
            response = requests.get(url, timeout=10)
            
            print(f"Standings API URL: {url}")
            print(f"Standings API response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # debugging stuff to see whats in the response
                print(f"Standings response keys: {list(data.keys())}")
                
                # dig through espns weird nested format
                children = data.get('children', [])
                print(f"Found {len(children)} conferences in standings")
                
                for group in children:
                    for division in group.get('children', []):
                        entries = division.get('standings', {}).get('entries', [])
                        for team_standing in entries:
                            team = team_standing.get('team', {})
                            team_abbr = team.get('abbreviation', '')
                            
                            stats_list = team_standing.get('stats', [])
                            stats_dict = {s['name']: s['value'] for s in stats_list if 'name' in s}
                            
                            standings[team_abbr] = {
                                'wins': int(stats_dict.get('wins', 0)),
                                'losses': int(stats_dict.get('losses', 0)),
                                'points_for': float(stats_dict.get('pointsFor', 0)),
                                'points_against': float(stats_dict.get('pointsAgainst', 0))
                            }
                
                print(f"Found {len(standings)} teams in standings")
                if standings:
                    sample_team = list(standings.keys())[0]
                    print(f"Sample team {sample_team}: {standings[sample_team]}")
                else:
                    print("No teams found - checking alternate structure...")
                    # espn sometimes formats things differently so check that too
                    if 'standings' in data:
                        print(f"Found 'standings' key with {len(data['standings'])} items")
                
                self.cache[cache_key] = standings
        except Exception as e:
            print(f"Error fetching standings: {e}")
        
        return standings
    
    def get_recent_form(self, team_abbr):
        """checks if a team is hot or cold lately"""
        cache_key = f'recent_form_{team_abbr}'
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        form = {
            'last_5': 'N/A',
            'wins': 0,
            'losses': 0,
            'streak': 'N/A',
            'form_rating': 50
        }
        
        try:
            # look up their recent games
            url = f"{self.espn_base_url}/teams"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # find the team were looking for
                for team_group in data.get('sports', [{}])[0].get('leagues', [{}])[0].get('teams', []):
                    team = team_group.get('team', {})
                    if team.get('abbreviation') == team_abbr:
                        # pull their record
                        record = team.get('record', {}).get('items', [{}])
                        if record:
                            stats = record[0].get('stats', [])
                            stats_dict = {s['name']: s['value'] for s in stats if 'name' in s}
                            
                            # see if theyre on a winning or losing streak
                            streak_val = stats_dict.get('streak', 0)
                            if streak_val > 0:
                                form['streak'] = f"W{int(streak_val)}"
                            elif streak_val < 0:
                                form['streak'] = f"L{int(abs(streak_val))}"
                        
                        # done with this team
                        break
            
            # calculate how well theyre doing overall
            standings = self.get_standings()
            if standings and team_abbr in standings:
                team_record = standings[team_abbr]
                wins = team_record.get('wins', 0)
                losses = team_record.get('losses', 0)
                total = wins + losses
                
                if total > 0:
                    win_pct = wins / total
                    form['form_rating'] = round(30 + (win_pct * 70))  # 30-100 scale
                    form['wins'] = wins
                    form['losses'] = losses
                    form['last_5'] = f"{wins}W-{losses}L"
                    
        except Exception as e:
            print(f"Error fetching recent form: {e}")
        
        self.cache[cache_key] = form
        return form
    
    def get_team_ppg(self, team_abbr):
        """how many points does this team usually score"""
        standings = self.get_standings()
        if standings and team_abbr in standings:
            team = standings[team_abbr]
            games = team.get('wins', 0) + team.get('losses', 0)
            if games > 0:
                return team.get('points_for', 0) / games
        return 22.0  # just use league average if we cant find it
    
    def get_team_ppg_allowed(self, team_abbr):
        """how many points does this team give up per game"""
        standings = self.get_standings()
        if standings and team_abbr in standings:
            team = standings[team_abbr]
            games = team.get('wins', 0) + team.get('losses', 0)
            if games > 0:
                return team.get('points_against', 0) / games
        return 22.0  # league average as backup
    
    def get_completed_games(self, year=2025):
        """gets games that have already been played with their results"""
        completed_games = []
        
        try:
            # go through each week and find finished games
            for week in range(1, 19):
                url = f"{self.espn_base_url}/scoreboard?seasontype=2&week={week}&dates={year}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'events' in data:
                        for event in data['events']:
                            # only grab games that finished
                            status = event.get('status', {}).get('type', {}).get('completed', False)
                            if status:
                                game_data = self.parse_completed_game(event)
                                if game_data:
                                    completed_games.append(game_data)
        except Exception as e:
            print(f"Error fetching completed games: {e}")
        
        return completed_games
    
    def parse_completed_game(self, event):
        """pulls out the results from a finished game"""
        try:
            competition = event['competitions'][0]
            competitors = competition['competitors']
            
            home_team = next(team for team in competitors if team['homeAway'] == 'home')
            away_team = next(team for team in competitors if team['homeAway'] == 'away')
            
            home_score = int(home_team.get('score', 0))
            away_score = int(away_team.get('score', 0))
            
            # home team won = 1, away team won = 0
            home_win = 1 if home_score > away_score else 0
            
            return {
                'home_team_abbr': home_team['team']['abbreviation'],
                'away_team_abbr': away_team['team']['abbreviation'],
                'home_score': home_score,
                'away_score': away_score,
                'home_win': home_win
            }
        except Exception as e:
            print(f"Error parsing completed game: {e}")
            return None
    
    def extract_features(self, home_team_abbr, away_team_abbr):
        """builds the feature array for logistic regression"""
        # get all the stats we can about both teams
        home_stats = self.get_team_stats(home_team_abbr)
        away_stats = self.get_team_stats(away_team_abbr)
        
        home_form = self.get_recent_form(home_team_abbr)
        away_form = self.get_recent_form(away_team_abbr)
        
        home_ppg = self.get_team_ppg(home_team_abbr)
        away_ppg = self.get_team_ppg(away_team_abbr)
        
        home_ppg_allowed = self.get_team_ppg_allowed(home_team_abbr)
        away_ppg_allowed = self.get_team_ppg_allowed(away_team_abbr)
        
        # features: difference between home and away team stats
        features = [
            home_stats.get('win_pct', 0.5) - away_stats.get('win_pct', 0.5),  # win % diff
            home_stats.get('offense_rating', 70) - away_stats.get('offense_rating', 70),  # offense diff
            home_stats.get('defense_rating', 70) - away_stats.get('defense_rating', 70),  # defense diff
            home_form.get('form_rating', 50) - away_form.get('form_rating', 50),  # recent form diff
            home_ppg - away_ppg,  # scoring diff
            away_ppg_allowed - home_ppg_allowed,  # points allowed diff (flipped so positive = good for home)
            home_ppg - home_ppg_allowed,  # home point differential
            away_ppg - away_ppg_allowed,  # away point differential (will be subtracted)
            1  # home field advantage indicator
        ]
        
        return np.array(features)
    
    def train_model(self):
        """trains the logistic regression model on completed games"""
        print("Training logistic regression model...")
        
        completed_games = self.get_completed_games()
        
        if len(completed_games) < 10:
            # not enough data - use default coefficients based on nfl research
            print(f"Only {len(completed_games)} games found. Using preset model weights.")
            self.use_preset_model()
            return
        
        print(f"Found {len(completed_games)} completed games for training")
        
        X = []  # features
        y = []  # outcomes (1 = home win, 0 = away win)
        
        for game in completed_games:
            try:
                features = self.extract_features(game['home_team_abbr'], game['away_team_abbr'])
                X.append(features)
                y.append(game['home_win'])
            except Exception as e:
                print(f"Error extracting features: {e}")
                continue
        
        if len(X) < 10:
            print("Not enough valid training samples. Using preset model.")
            self.use_preset_model()
            return
        
        X = np.array(X)
        y = np.array(y)
        
        # scale the features for better model performance
        X_scaled = self.scaler.fit_transform(X)
        
        # train the model
        self.model.fit(X_scaled, y)
        self.model_trained = True
        
        # show how the model weighted each feature
        print("\nLogistic Regression Model Trained!")
        print("Feature Weights:")
        feature_names = ['Win%', 'Offense', 'Defense', 'Form', 'PPG', 'PPG Allowed', 'Home Diff', 'Away Diff', 'Home Field']
        for name, coef in zip(feature_names, self.model.coef_[0]):
            print(f"  {name}: {coef:.3f}")
        print(f"  Intercept: {self.model.intercept_[0]:.3f}")
        
        # quick accuracy check
        predictions = self.model.predict(X_scaled)
        accuracy = np.mean(predictions == y)
        print(f"\nTraining Accuracy: {accuracy*100:.1f}%")
    
    def use_preset_model(self):
        """uses preset weights when we dont have enough training data"""
        # these weights are based on typical nfl prediction factors
        # win % diff is most important, followed by point differential
        self.model.coef_ = np.array([[2.5, 0.5, 0.4, 0.3, 0.6, 0.5, 0.8, -0.6, 0.4]])
        self.model.intercept_ = np.array([0.1])  # slight home advantage
        self.model.classes_ = np.array([0, 1])
        
        # set up a basic scaler that doesn't change much
        self.scaler.mean_ = np.zeros(9)
        self.scaler.scale_ = np.ones(9)
        self.scaler.var_ = np.ones(9)
        self.scaler.n_features_in_ = 9
        self.scaler.n_samples_seen_ = 100
        
        self.model_trained = True
        print("Using preset model weights for predictions")
    
    def predict_with_model(self, home_team_abbr, away_team_abbr):
        """uses the trained model to predict who wins"""
        features = self.extract_features(home_team_abbr, away_team_abbr)
        features_scaled = self.scaler.transform(features.reshape(1, -1))
        
        # get probability that home team wins
        home_win_prob = self.model.predict_proba(features_scaled)[0][1]
        
        return home_win_prob
    
    def analyze_quarterback(self, team_abbr):
        """figures out how good their qb is"""
        qb_analysis = {
            'is_rookie': False,
            'experience_years': 0,
            'completion_percentage': 0,
            'touchdown_ratio': 0,
            'interception_ratio': 0,
            'rating': 0,
            'games_started': 0,
            'qb_name': 'Unknown'
        }
        
        # if we have the sportsdata api key we can get detailed stats
        if API_KEYS['SPORTSDATA_IO']:
            try:
                url = f"{self.sportsdata_base_url}/scores/json/Players/{team_abbr}"
                headers = {'Ocp-Apim-Subscription-Key': API_KEYS['SPORTSDATA_IO']}
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    players = response.json()
                    # find the starter
                    qbs = [p for p in players if p.get('Position') == 'QB' and p.get('DepthOrder') == 1]
                    if qbs:
                        qb = qbs[0]
                        qb_analysis.update(self.parse_qb_stats(qb))
            except Exception as e:
                print(f"Error analyzing QB: {e}")
        
        # otherwise just estimate based on how the team does
        qb_analysis['rating'] = self.estimate_qb_rating(team_abbr)
        
        return qb_analysis
    
    def parse_qb_stats(self, qb_data):
        """pulls out the qb info we care about"""
        # only mark as rookie if theyve actually started games this year
        # otherwise its probably a backup who hasnt played
        experience = qb_data.get('Experience', 1)
        games_started = qb_data.get('Started', 0)
        is_starter = games_started > 0 or qb_data.get('DepthOrder', 99) == 1
        
        return {
            'qb_name': qb_data.get('Name', 'Unknown'),
            'is_rookie': experience <= 1 and is_starter,
            'experience_years': experience,
            'games_started': games_started
        }
    
    def estimate_qb_rating(self, team_abbr):
        """guesses how good the qb is based on team success"""
        # use their actual record if we have it
        standings = self.get_standings()
        if standings and team_abbr in standings:
            team_record = standings[team_abbr]
            wins = team_record.get('wins', 0)
            losses = team_record.get('losses', 0)
            total = wins + losses
            if total > 0:
                # winning teams usually have good qbs
                win_pct = wins / total
                return 60 + (win_pct * 35)
        
        # otherwise use my rankings of the qbs
        elite_qbs = ['KC', 'BAL', 'DET', 'PHI', 'BUF']
        good_qbs = ['SF', 'GB', 'CIN', 'HOU', 'LAC', 'MIA']
        average_qbs = ['DAL', 'SEA', 'TB', 'MIN', 'ATL', 'PIT']
        
        if team_abbr in elite_qbs:
            return 92
        elif team_abbr in good_qbs:
            return 82
        elif team_abbr in average_qbs:
            return 72
        else:
            return 65
    
    # sportsdata uses numbers instead of team abbreviations for some reason
    TEAM_IDS = {
        'ARI': 1, 'ATL': 2, 'BAL': 3, 'BUF': 4, 'CAR': 5, 'CHI': 6, 'CIN': 7, 'CLE': 8,
        'DAL': 9, 'DEN': 10, 'DET': 11, 'GB': 12, 'HOU': 13, 'IND': 14, 'JAX': 15, 'KC': 16,
        'LV': 17, 'LAC': 18, 'LAR': 19, 'MIA': 20, 'MIN': 21, 'NE': 22, 'NO': 23, 'NYG': 24,
        'NYJ': 25, 'PHI': 26, 'PIT': 27, 'SF': 28, 'SEA': 29, 'TB': 30, 'TEN': 31, 'WSH': 32
    }
    
    def get_all_depth_charts(self):
        """grabs every teams depth chart in one call"""
        cache_key = 'depth_charts'
        
        # dont call the api if we already have this
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        if API_KEYS['SPORTSDATA_IO']:
            try:
                url = f"{self.sportsdata_base_url}/scores/json/DepthCharts"
                headers = {'Ocp-Apim-Subscription-Key': API_KEYS['SPORTSDATA_IO']}
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    self.cache[cache_key] = response.json()
                    return self.cache[cache_key]
            except Exception as e:
                print(f"Error fetching depth charts: {e}")
        
        return []
    
    def analyze_depth_chart(self, team_abbr):
        """checks how good their backup players are"""
        depth_analysis = {
            'key_injuries': 0,
            'depth_quality': 50,
            'backup_experience': 0,
            'third_string_impact': 0
        }
        
        # use the cached depth charts
        depth_charts = self.get_all_depth_charts()
        
        if depth_charts:
            # look up this team by their id number
            team_id = self.TEAM_IDS.get(team_abbr)
            team_data = next((d for d in depth_charts if d.get('TeamID') == team_id), None)
            
            if team_data:
                # get all their players from each unit
                all_players = []
                for unit in ['Offense', 'Defense', 'SpecialTeams']:
                    players = team_data.get(unit, [])
                    if players:
                        all_players.extend(players)
                
                depth_analysis.update(self.calculate_depth_impact(all_players))
        
        return depth_analysis
    
    def calculate_depth_impact(self, depth_data):
        """figures out if their bench is better or worse than average"""
        if not depth_data:
            return {'depth_quality': 50, 'backup_experience': 0}
        
        total_players = len(depth_data)
        
        # count how many starters vs backups they have
        starters = len([p for p in depth_data if p.get('DepthOrder', 1) == 1])
        second_string = len([p for p in depth_data if p.get('DepthOrder', 1) == 2])
        third_plus = len([p for p in depth_data if p.get('DepthOrder', 1) >= 3])
        
        # more backups = better depth
        # typical team has around 22 starters and 22 backups
        
        # score them based on how deep their roster is
        depth_ratio = (second_string + third_plus) / max(starters, 1)
        
        # turn that into a 0-100 score
        # 1.0 ratio is average (50), more depth = higher score
        depth_score = 50 + (depth_ratio - 1.0) * 40
        
        # keep it reasonable
        depth_score = max(30, min(90, depth_score))
        
        return {
            'depth_quality': round(depth_score),
            'backup_experience': second_string + third_plus,
            'starters': starters,
            'second_string': second_string,
            'third_plus': third_plus
        }
    
    def get_injury_report(self, team_abbr):
        """checks whos hurt on the team"""
        cache_key = f'injuries_{team_abbr}'
        
        # use cached version if we have it
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        injuries = {
            'total_injuries': 0,
            'key_player_injuries': 0,
            'impact_score': 0
        }
        
        if API_KEYS['SPORTSDATA_IO']:
            try:
                url = f"{self.sportsdata_base_url}/scores/json/Injuries/{team_abbr}"
                headers = {'Ocp-Apim-Subscription-Key': API_KEYS['SPORTSDATA_IO']}
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    injury_data = response.json()
                    injuries['total_injuries'] = len(injury_data)
                    
                    # injuries to important positions matter more
                    key_positions = ['QB', 'RB', 'WR', 'TE', 'OL', 'DL', 'LB', 'DB']
                    injuries['key_player_injuries'] = sum(1 for inj in injury_data if inj.get('Position') in key_positions)
                    injuries['impact_score'] = min(injuries['key_player_injuries'] * 10, 50)
            except Exception as e:
                print(f"Error fetching injuries: {e}")
        
        self.cache[cache_key] = injuries
        return injuries
    
    def predict_game(self, game_info):
        """this is where the magic happens - uses logistic regression to predict who wins"""
        home_team = game_info['home_team_abbr']
        away_team = game_info['away_team_abbr']
        
        # grab their records from the game data
        home_record_str = game_info.get('home_record', '0-0')
        away_record_str = game_info.get('away_record', '0-0')
        
        # break apart the win-loss string like "13-4"
        def parse_record(record_str):
            parts = record_str.split('-')
            wins = int(parts[0]) if parts[0].isdigit() else 0
            losses = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            return wins, losses
        
        home_wins, home_losses = parse_record(home_record_str)
        away_wins, away_losses = parse_record(away_record_str)
        
        # get all the info we need on both teams
        home_stats = self.get_team_stats(home_team)
        away_stats = self.get_team_stats(away_team)
        
        # use the actual records if we got them
        if home_wins + home_losses > 0:
            home_stats['win_pct'] = home_wins / (home_wins + home_losses)
        if away_wins + away_losses > 0:
            away_stats['win_pct'] = away_wins / (away_wins + away_losses)
        
        home_qb = self.analyze_quarterback(home_team)
        away_qb = self.analyze_quarterback(away_team)
        
        home_form = self.get_recent_form(home_team)
        away_form = self.get_recent_form(away_team)
        
        # put the real records into the form data
        home_form['wins'] = home_wins
        home_form['losses'] = home_losses
        home_form['last_5'] = home_record_str
        away_form['wins'] = away_wins
        away_form['losses'] = away_losses
        away_form['last_5'] = away_record_str
        
        home_injuries = self.get_injury_report(home_team)
        away_injuries = self.get_injury_report(away_team)
        
        # USE LOGISTIC REGRESSION to predict the winner
        home_win_prob = self.predict_with_model(home_team, away_team)
        
        # whoever has higher probability wins
        if home_win_prob >= 0.5:
            predicted_winner = game_info['home_team']
            confidence_pct = home_win_prob * 100
        else:
            predicted_winner = game_info['away_team']
            confidence_pct = (1 - home_win_prob) * 100
        
        # cap confidence between 50-95%
        confidence_pct = max(50, min(95, confidence_pct))
        
        # now predict the actual score using their averages
        home_ppg = self.get_team_ppg(home_team)
        away_ppg = self.get_team_ppg(away_team)
        home_ppg_allowed = self.get_team_ppg_allowed(home_team)
        away_ppg_allowed = self.get_team_ppg_allowed(away_team)
        
        # mix their scoring with how much the other team allows
        # adjust based on predicted probability
        prob_diff = (home_win_prob - 0.5) * 2  # scale to -1 to 1
        
        home_predicted = round((home_ppg + away_ppg_allowed) / 2 + (prob_diff * 5))
        away_predicted = round((away_ppg + home_ppg_allowed) / 2 - (prob_diff * 5))
        
        # home team gets a small boost
        home_predicted += 1
        
        # make sure scores are realistic
        home_predicted = max(10, min(50, home_predicted))
        away_predicted = max(10, min(50, away_predicted))
        
        # winner should have higher score
        if home_win_prob >= 0.5:
            if home_predicted <= away_predicted:
                home_predicted = away_predicted + 3
            predicted_score = f"{home_predicted}-{away_predicted}"
        else:
            if away_predicted <= home_predicted:
                away_predicted = home_predicted + 3
            predicted_score = f"{away_predicted}-{home_predicted}"
        
        return {
            'game_id': game_info['game_id'],
            'home_team': game_info['home_team'],
            'away_team': game_info['away_team'],
            'venue': game_info['venue'],
            'game_date': game_info['game_date'],
            'week': game_info.get('week'),
            'round': game_info.get('round'),
            'predicted_winner': predicted_winner,
            'confidence': round(confidence_pct, 1),
            'predicted_score': predicted_score,
            'home_win_probability': round(home_win_prob * 100, 1),
            'analysis': {
                'home_win_prob': round(home_win_prob * 100, 1),
                'away_win_prob': round((1 - home_win_prob) * 100, 1),
                'home_qb': home_qb,
                'away_qb': away_qb,
                'home_injuries': home_injuries,
                'away_injuries': away_injuries,
                'home_form': home_form,
                'away_form': away_form
            }
        }
    
    def calculate_prediction_score(self, stats, qb, form, injuries, is_home):
        """adds up all the factors to get a teams overall score"""
        score = 0
        
        # winning percentage matters most - half the score
        win_pct = stats.get('win_pct', 0.5)
        score += win_pct * 50
        
        # how good is their offense and defense
        score += stats.get('offense_rating', 70) * 0.15
        score += stats.get('defense_rating', 70) * 0.10
        
        # qb play is huge in the nfl
        qb_rating = qb.get('rating', 75)
        if qb.get('is_rookie', False):
            qb_rating *= 0.90  # rookies usually struggle a bit
        score += qb_rating * 0.15
        
        # are they playing well lately
        form_rating = form.get('form_rating', 50)
        score += form_rating * 0.05
        
        # injuries hurt (pun intended)
        injury_impact = injuries.get('impact_score', 0)
        score -= injury_impact * 0.10
        
        # playing at home helps
        if is_home:
            score += 4
        
        return score
    
    def get_fallback_games(self):
        """backup games in case espn is down"""
        return [
            {
                'game_id': '1',
                'home_team': 'Kansas City Chiefs',
                'away_team': 'Buffalo Bills',
                'home_team_abbr': 'KC',
                'away_team_abbr': 'BUF',
                'game_date': datetime.now().isoformat(),
                'venue': 'Arrowhead Stadium',
                'status': 'Scheduled'
            },
            {
                'game_id': '2',
                'home_team': 'San Francisco 49ers',
                'away_team': 'Dallas Cowboys',
                'home_team_abbr': 'SF',
                'away_team_abbr': 'DAL',
                'game_date': datetime.now().isoformat(),
                'venue': 'Levi\'s Stadium',
                'status': 'Scheduled'
            }
        ]
    
    # ========== HISTORICAL TEAM DATA FOR CUSTOM GAME PREDICTOR ==========
    
    # all 32 nfl teams with their founding years and any name/location changes
    NFL_TEAMS = {
        'ARI': {'name': 'Arizona Cardinals', 'city': 'Arizona', 'founded': 1920, 'history': [
            {'years': (1920, 1959), 'name': 'Chicago Cardinals', 'abbr': 'CHI'},
            {'years': (1960, 1987), 'name': 'St. Louis Cardinals', 'abbr': 'STL'},
            {'years': (1988, 1993), 'name': 'Phoenix Cardinals', 'abbr': 'PHO'},
            {'years': (1994, 2099), 'name': 'Arizona Cardinals', 'abbr': 'ARI'}
        ]},
        'ATL': {'name': 'Atlanta Falcons', 'city': 'Atlanta', 'founded': 1966},
        'BAL': {'name': 'Baltimore Ravens', 'city': 'Baltimore', 'founded': 1996},
        'BUF': {'name': 'Buffalo Bills', 'city': 'Buffalo', 'founded': 1960},
        'CAR': {'name': 'Carolina Panthers', 'city': 'Carolina', 'founded': 1995},
        'CHI': {'name': 'Chicago Bears', 'city': 'Chicago', 'founded': 1920},
        'CIN': {'name': 'Cincinnati Bengals', 'city': 'Cincinnati', 'founded': 1968},
        'CLE': {'name': 'Cleveland Browns', 'city': 'Cleveland', 'founded': 1950, 'history': [
            {'years': (1950, 1995), 'name': 'Cleveland Browns', 'abbr': 'CLE'},
            {'years': (1999, 2099), 'name': 'Cleveland Browns', 'abbr': 'CLE'}  # returned in 1999
        ]},
        'DAL': {'name': 'Dallas Cowboys', 'city': 'Dallas', 'founded': 1960},
        'DEN': {'name': 'Denver Broncos', 'city': 'Denver', 'founded': 1960},
        'DET': {'name': 'Detroit Lions', 'city': 'Detroit', 'founded': 1930},
        'GB': {'name': 'Green Bay Packers', 'city': 'Green Bay', 'founded': 1921},
        'HOU': {'name': 'Houston Texans', 'city': 'Houston', 'founded': 2002},
        'IND': {'name': 'Indianapolis Colts', 'city': 'Indianapolis', 'founded': 1953, 'history': [
            {'years': (1953, 1983), 'name': 'Baltimore Colts', 'abbr': 'BAL'},
            {'years': (1984, 2099), 'name': 'Indianapolis Colts', 'abbr': 'IND'}
        ]},
        'JAX': {'name': 'Jacksonville Jaguars', 'city': 'Jacksonville', 'founded': 1995},
        'KC': {'name': 'Kansas City Chiefs', 'city': 'Kansas City', 'founded': 1960, 'history': [
            {'years': (1960, 1962), 'name': 'Dallas Texans', 'abbr': 'DAL'},
            {'years': (1963, 2099), 'name': 'Kansas City Chiefs', 'abbr': 'KC'}
        ]},
        'LV': {'name': 'Las Vegas Raiders', 'city': 'Las Vegas', 'founded': 1960, 'history': [
            {'years': (1960, 1981), 'name': 'Oakland Raiders', 'abbr': 'OAK'},
            {'years': (1982, 1994), 'name': 'Los Angeles Raiders', 'abbr': 'LAR'},
            {'years': (1995, 2019), 'name': 'Oakland Raiders', 'abbr': 'OAK'},
            {'years': (2020, 2099), 'name': 'Las Vegas Raiders', 'abbr': 'LV'}
        ]},
        'LAC': {'name': 'Los Angeles Chargers', 'city': 'Los Angeles', 'founded': 1960, 'history': [
            {'years': (1960, 1960), 'name': 'Los Angeles Chargers', 'abbr': 'LAC'},
            {'years': (1961, 2016), 'name': 'San Diego Chargers', 'abbr': 'SD'},
            {'years': (2017, 2099), 'name': 'Los Angeles Chargers', 'abbr': 'LAC'}
        ]},
        'LAR': {'name': 'Los Angeles Rams', 'city': 'Los Angeles', 'founded': 1936, 'history': [
            {'years': (1936, 1945), 'name': 'Cleveland Rams', 'abbr': 'CLE'},
            {'years': (1946, 1994), 'name': 'Los Angeles Rams', 'abbr': 'LA'},
            {'years': (1995, 2015), 'name': 'St. Louis Rams', 'abbr': 'STL'},
            {'years': (2016, 2099), 'name': 'Los Angeles Rams', 'abbr': 'LAR'}
        ]},
        'MIA': {'name': 'Miami Dolphins', 'city': 'Miami', 'founded': 1966},
        'MIN': {'name': 'Minnesota Vikings', 'city': 'Minnesota', 'founded': 1961},
        'NE': {'name': 'New England Patriots', 'city': 'New England', 'founded': 1960, 'history': [
            {'years': (1960, 1970), 'name': 'Boston Patriots', 'abbr': 'BOS'},
            {'years': (1971, 2099), 'name': 'New England Patriots', 'abbr': 'NE'}
        ]},
        'NO': {'name': 'New Orleans Saints', 'city': 'New Orleans', 'founded': 1967},
        'NYG': {'name': 'New York Giants', 'city': 'New York', 'founded': 1925},
        'NYJ': {'name': 'New York Jets', 'city': 'New York', 'founded': 1960, 'history': [
            {'years': (1960, 1962), 'name': 'New York Titans', 'abbr': 'NYT'},
            {'years': (1963, 2099), 'name': 'New York Jets', 'abbr': 'NYJ'}
        ]},
        'PHI': {'name': 'Philadelphia Eagles', 'city': 'Philadelphia', 'founded': 1933},
        'PIT': {'name': 'Pittsburgh Steelers', 'city': 'Pittsburgh', 'founded': 1933},
        'SF': {'name': 'San Francisco 49ers', 'city': 'San Francisco', 'founded': 1946},
        'SEA': {'name': 'Seattle Seahawks', 'city': 'Seattle', 'founded': 1976},
        'TB': {'name': 'Tampa Bay Buccaneers', 'city': 'Tampa Bay', 'founded': 1976},
        'TEN': {'name': 'Tennessee Titans', 'city': 'Tennessee', 'founded': 1960, 'history': [
            {'years': (1960, 1996), 'name': 'Houston Oilers', 'abbr': 'HOU'},
            {'years': (1997, 1998), 'name': 'Tennessee Oilers', 'abbr': 'TEN'},
            {'years': (1999, 2099), 'name': 'Tennessee Titans', 'abbr': 'TEN'}
        ]},
        'WSH': {'name': 'Washington Commanders', 'city': 'Washington', 'founded': 1932, 'history': [
            {'years': (1932, 1936), 'name': 'Boston Braves/Redskins', 'abbr': 'BOS'},
            {'years': (1937, 2019), 'name': 'Washington Redskins', 'abbr': 'WAS'},
            {'years': (2020, 2021), 'name': 'Washington Football Team', 'abbr': 'WAS'},
            {'years': (2022, 2099), 'name': 'Washington Commanders', 'abbr': 'WSH'}
        ]}
    }
    
    def get_all_teams(self):
        """returns all 32 nfl teams with their info"""
        teams = []
        for abbr, info in self.NFL_TEAMS.items():
            teams.append({
                'abbreviation': abbr,
                'name': info['name'],
                'city': info['city'],
                'founded': info['founded'],
                'logo': f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr.lower()}.png"
            })
        return sorted(teams, key=lambda x: x['name'])
    
    def get_teams_for_year(self, year):
        """returns teams that existed in a given year"""
        teams = []
        for abbr, info in self.NFL_TEAMS.items():
            if info['founded'] <= year:
                # check if team had a different name/location that year
                historical_name = info['name']
                if 'history' in info:
                    for era in info['history']:
                        if era['years'][0] <= year <= era['years'][1]:
                            historical_name = era['name']
                            break
                
                teams.append({
                    'abbreviation': abbr,
                    'name': info['name'],
                    'historical_name': historical_name,
                    'city': info['city'],
                    'logo': f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr.lower()}.png"
                })
        return sorted(teams, key=lambda x: x['name'])
    
    def get_historical_team_stats(self, team_abbr, year):
        """gets a teams stats from a specific year using espn api"""
        cache_key = f'historical_stats_{team_abbr}_{year}'
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        stats = {
            'team': team_abbr,
            'year': year,
            'wins': 0,
            'losses': 0,
            'ties': 0,
            'win_pct': 0.5,
            'points_for': 0,
            'points_against': 0,
            'point_differential': 0,
            'ppg': 22.0,
            'ppg_allowed': 22.0,
            'found': False
        }
        
        # Try method 1: ESPN team schedule/record endpoint
        try:
            team_id = self.TEAM_IDS.get(team_abbr)
            if team_id:
                url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/schedule?season={year}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Get record from team info
                    team_info = data.get('team', {})
                    record_items = team_info.get('record', {}).get('items', [])
                    
                    if record_items:
                        for record_item in record_items:
                            if record_item.get('type') == 'total' or record_item.get('description') == 'Overall Record':
                                record_stats = record_item.get('stats', [])
                                stats_dict = {s['name']: s['value'] for s in record_stats if 'name' in s}
                                
                                wins = int(stats_dict.get('wins', 0))
                                losses = int(stats_dict.get('losses', 0))
                                ties = int(stats_dict.get('ties', 0))
                                
                                if wins + losses > 0:
                                    total_games = wins + losses + ties
                                    
                                    # Calculate points from events
                                    pts_for = 0
                                    pts_against = 0
                                    events = data.get('events', [])
                                    
                                    for event in events:
                                        competitions = event.get('competitions', [])
                                        for comp in competitions:
                                            competitors = comp.get('competitors', [])
                                            for competitor in competitors:
                                                if competitor.get('id') == str(team_id):
                                                    score = competitor.get('score', {})
                                                    if isinstance(score, dict):
                                                        pts_for += int(score.get('value', 0))
                                                    else:
                                                        pts_for += int(score) if score else 0
                                                else:
                                                    score = competitor.get('score', {})
                                                    if isinstance(score, dict):
                                                        pts_against += int(score.get('value', 0))
                                                    else:
                                                        pts_against += int(score) if score else 0
                                    
                                    # If we couldn't get points from events, estimate
                                    if pts_for == 0:
                                        pts_for = total_games * 22
                                        pts_against = total_games * 22
                                    
                                    stats.update({
                                        'wins': wins,
                                        'losses': losses,
                                        'ties': ties,
                                        'win_pct': wins / total_games if total_games > 0 else 0.5,
                                        'points_for': pts_for,
                                        'points_against': pts_against,
                                        'point_differential': pts_for - pts_against,
                                        'ppg': pts_for / total_games if total_games > 0 else 22.0,
                                        'ppg_allowed': pts_against / total_games if total_games > 0 else 22.0,
                                        'found': True
                                    })
                                    
                                    self.cache[cache_key] = stats
                                    return stats
                                break
        except Exception as e:
            print(f"Method 1 failed for {team_abbr} {year}: {e}")
        
        # Try method 2: ESPN standings endpoint
        try:
            url = f"{self.espn_base_url}/standings?season={year}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # dig through espns nested format
                children = data.get('children', [])
                
                for group in children:
                    for division in group.get('children', []):
                        entries = division.get('standings', {}).get('entries', [])
                        for team_standing in entries:
                            team = team_standing.get('team', {})
                            team_abbr_found = team.get('abbreviation', '')
                            
                            if team_abbr_found == team_abbr:
                                stats_list = team_standing.get('stats', [])
                                stats_dict = {s['name']: s['value'] for s in stats_list if 'name' in s}
                                
                                wins = int(stats_dict.get('wins', 0))
                                losses = int(stats_dict.get('losses', 0))
                                ties = int(stats_dict.get('ties', 0))
                                total_games = wins + losses + ties
                                
                                if total_games > 0:
                                    pts_for = float(stats_dict.get('pointsFor', 0))
                                    pts_against = float(stats_dict.get('pointsAgainst', 0))
                                    
                                    stats.update({
                                        'wins': wins,
                                        'losses': losses,
                                        'ties': ties,
                                        'win_pct': wins / total_games if total_games > 0 else 0.5,
                                        'points_for': pts_for,
                                        'points_against': pts_against,
                                        'point_differential': pts_for - pts_against,
                                        'ppg': pts_for / total_games if total_games > 0 else 22.0,
                                        'ppg_allowed': pts_against / total_games if total_games > 0 else 22.0,
                                        'found': True
                                    })
                                    
                                    self.cache[cache_key] = stats
                                    return stats
                                
        except Exception as e:
            print(f"Method 2 failed for {team_abbr} {year}: {e}")
        
        # Try method 3: ESPN scoreboard historical
        try:
            wins = 0
            losses = 0
            ties = 0
            pts_for = 0
            pts_against = 0
            
            team_id = self.TEAM_IDS.get(team_abbr)
            
            # Get games for each week
            for week in range(1, 19):
                url = f"{self.espn_base_url}/scoreboard?seasontype=2&week={week}&dates={year}"
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    for event in data.get('events', []):
                        status = event.get('status', {}).get('type', {}).get('completed', False)
                        if not status:
                            continue
                            
                        competition = event.get('competitions', [{}])[0]
                        competitors = competition.get('competitors', [])
                        
                        team_found = False
                        team_score = 0
                        opp_score = 0
                        
                        for competitor in competitors:
                            comp_abbr = competitor.get('team', {}).get('abbreviation', '')
                            score = int(competitor.get('score', 0))
                            
                            if comp_abbr == team_abbr:
                                team_found = True
                                team_score = score
                            else:
                                opp_score = score
                        
                        if team_found:
                            pts_for += team_score
                            pts_against += opp_score
                            
                            if team_score > opp_score:
                                wins += 1
                            elif team_score < opp_score:
                                losses += 1
                            else:
                                ties += 1
            
            total_games = wins + losses + ties
            if total_games >= 10:  # at least 10 games found
                stats.update({
                    'wins': wins,
                    'losses': losses,
                    'ties': ties,
                    'win_pct': wins / total_games if total_games > 0 else 0.5,
                    'points_for': pts_for,
                    'points_against': pts_against,
                    'point_differential': pts_for - pts_against,
                    'ppg': pts_for / total_games if total_games > 0 else 22.0,
                    'ppg_allowed': pts_against / total_games if total_games > 0 else 22.0,
                    'found': True
                })
                
                self.cache[cache_key] = stats
                return stats
                
        except Exception as e:
            print(f"Method 3 failed for {team_abbr} {year}: {e}")
        
        # fallback: use preset ratings based on known good/bad teams from history
        stats = self.get_fallback_historical_stats(team_abbr, year)
        self.cache[cache_key] = stats
        return stats
    
    def get_fallback_historical_stats(self, team_abbr, year):
        """fallback stats for years where api data isnt available"""
        # comprehensive historical data for notable seasons
        legendary_seasons = {
            # 1970s
            ('MIA', 1972): {'wins': 14, 'losses': 0, 'ppg': 27.5, 'ppg_allowed': 12.2},  # perfect season
            ('MIA', 1973): {'wins': 12, 'losses': 2, 'ppg': 24.8, 'ppg_allowed': 14.8},
            ('PIT', 1974): {'wins': 10, 'losses': 3, 'ppg': 20.6, 'ppg_allowed': 12.3},
            ('PIT', 1975): {'wins': 12, 'losses': 2, 'ppg': 23.6, 'ppg_allowed': 12.4},
            ('OAK', 1976): {'wins': 13, 'losses': 1, 'ppg': 24.6, 'ppg_allowed': 17.1},
            ('DAL', 1977): {'wins': 12, 'losses': 2, 'ppg': 21.9, 'ppg_allowed': 13.4},
            ('PIT', 1978): {'wins': 14, 'losses': 2, 'ppg': 22.9, 'ppg_allowed': 13.8},
            ('PIT', 1979): {'wins': 12, 'losses': 4, 'ppg': 26.0, 'ppg_allowed': 16.5},
            # 1980s
            ('SF', 1981): {'wins': 13, 'losses': 3, 'ppg': 22.2, 'ppg_allowed': 15.6},
            ('SF', 1984): {'wins': 15, 'losses': 1, 'ppg': 29.2, 'ppg_allowed': 14.3},
            ('CHI', 1985): {'wins': 15, 'losses': 1, 'ppg': 28.5, 'ppg_allowed': 12.4},
            ('NYG', 1986): {'wins': 14, 'losses': 2, 'ppg': 23.9, 'ppg_allowed': 14.8},
            ('SF', 1989): {'wins': 14, 'losses': 2, 'ppg': 27.6, 'ppg_allowed': 15.8},
            # 1990s
            ('SF', 1990): {'wins': 14, 'losses': 2, 'ppg': 22.8, 'ppg_allowed': 14.8},
            ('BUF', 1991): {'wins': 13, 'losses': 3, 'ppg': 28.6, 'ppg_allowed': 20.1},
            ('DAL', 1992): {'wins': 13, 'losses': 3, 'ppg': 25.3, 'ppg_allowed': 16.4},
            ('DAL', 1993): {'wins': 12, 'losses': 4, 'ppg': 23.5, 'ppg_allowed': 14.4},
            ('SF', 1994): {'wins': 13, 'losses': 3, 'ppg': 29.8, 'ppg_allowed': 17.3},
            ('DAL', 1995): {'wins': 12, 'losses': 4, 'ppg': 26.8, 'ppg_allowed': 18.0},
            ('GB', 1996): {'wins': 13, 'losses': 3, 'ppg': 28.4, 'ppg_allowed': 13.5},
            ('GB', 1997): {'wins': 13, 'losses': 3, 'ppg': 26.4, 'ppg_allowed': 17.1},
            ('DEN', 1997): {'wins': 12, 'losses': 4, 'ppg': 29.1, 'ppg_allowed': 18.1},
            ('DEN', 1998): {'wins': 14, 'losses': 2, 'ppg': 32.4, 'ppg_allowed': 18.4},
            ('MIN', 1998): {'wins': 15, 'losses': 1, 'ppg': 34.8, 'ppg_allowed': 19.4},
            # 2000s
            ('BAL', 2000): {'wins': 12, 'losses': 4, 'ppg': 20.8, 'ppg_allowed': 10.3},
            ('STL', 2001): {'wins': 14, 'losses': 2, 'ppg': 31.4, 'ppg_allowed': 17.1},
            ('NE', 2003): {'wins': 14, 'losses': 2, 'ppg': 20.9, 'ppg_allowed': 14.9},
            ('NE', 2004): {'wins': 14, 'losses': 2, 'ppg': 27.3, 'ppg_allowed': 16.5},
            ('PIT', 2004): {'wins': 15, 'losses': 1, 'ppg': 24.3, 'ppg_allowed': 15.7},
            ('IND', 2005): {'wins': 14, 'losses': 2, 'ppg': 26.7, 'ppg_allowed': 16.9},
            ('NE', 2007): {'wins': 16, 'losses': 0, 'ppg': 36.8, 'ppg_allowed': 17.1},
            ('IND', 2009): {'wins': 14, 'losses': 2, 'ppg': 26.6, 'ppg_allowed': 19.1},
            ('NO', 2009): {'wins': 13, 'losses': 3, 'ppg': 31.9, 'ppg_allowed': 20.3},
            # 2010s
            ('GB', 2011): {'wins': 15, 'losses': 1, 'ppg': 35.0, 'ppg_allowed': 22.4},
            ('NE', 2011): {'wins': 13, 'losses': 3, 'ppg': 32.1, 'ppg_allowed': 21.4},
            ('DEN', 2013): {'wins': 13, 'losses': 3, 'ppg': 37.9, 'ppg_allowed': 24.9},
            ('SEA', 2013): {'wins': 13, 'losses': 3, 'ppg': 26.1, 'ppg_allowed': 14.4},
            ('NE', 2014): {'wins': 12, 'losses': 4, 'ppg': 29.2, 'ppg_allowed': 19.6},
            ('CAR', 2015): {'wins': 15, 'losses': 1, 'ppg': 31.3, 'ppg_allowed': 19.2},
            ('NE', 2016): {'wins': 14, 'losses': 2, 'ppg': 27.6, 'ppg_allowed': 15.6},
            ('PHI', 2017): {'wins': 13, 'losses': 3, 'ppg': 28.6, 'ppg_allowed': 18.4},
            ('LAR', 2018): {'wins': 13, 'losses': 3, 'ppg': 32.9, 'ppg_allowed': 24.0},
            ('NO', 2018): {'wins': 13, 'losses': 3, 'ppg': 31.5, 'ppg_allowed': 22.1},
            ('SF', 2019): {'wins': 13, 'losses': 3, 'ppg': 29.9, 'ppg_allowed': 19.4},
            ('BAL', 2019): {'wins': 14, 'losses': 2, 'ppg': 33.2, 'ppg_allowed': 17.6},
            # 2020s
            ('KC', 2020): {'wins': 14, 'losses': 2, 'ppg': 29.6, 'ppg_allowed': 22.6},
            ('BUF', 2020): {'wins': 13, 'losses': 3, 'ppg': 31.3, 'ppg_allowed': 21.1},
            ('GB', 2020): {'wins': 13, 'losses': 3, 'ppg': 31.8, 'ppg_allowed': 24.1},
            ('TB', 2020): {'wins': 11, 'losses': 5, 'ppg': 30.8, 'ppg_allowed': 22.2},
            ('TB', 2021): {'wins': 13, 'losses': 4, 'ppg': 30.1, 'ppg_allowed': 20.9},
            ('GB', 2021): {'wins': 13, 'losses': 4, 'ppg': 26.5, 'ppg_allowed': 21.8},
            ('PHI', 2022): {'wins': 14, 'losses': 3, 'ppg': 28.1, 'ppg_allowed': 20.2},
            ('KC', 2022): {'wins': 14, 'losses': 3, 'ppg': 29.2, 'ppg_allowed': 21.7},
            ('SF', 2022): {'wins': 13, 'losses': 4, 'ppg': 26.5, 'ppg_allowed': 19.2},
            ('BUF', 2022): {'wins': 13, 'losses': 3, 'ppg': 28.4, 'ppg_allowed': 17.9},
            ('DAL', 2023): {'wins': 12, 'losses': 5, 'ppg': 29.9, 'ppg_allowed': 18.5},
            ('SF', 2023): {'wins': 12, 'losses': 5, 'ppg': 28.4, 'ppg_allowed': 17.5},
            ('BAL', 2023): {'wins': 13, 'losses': 4, 'ppg': 28.4, 'ppg_allowed': 16.5},
            ('DET', 2023): {'wins': 12, 'losses': 5, 'ppg': 27.1, 'ppg_allowed': 22.1},
            ('KC', 2023): {'wins': 11, 'losses': 6, 'ppg': 21.8, 'ppg_allowed': 17.3},
            ('MIA', 2023): {'wins': 11, 'losses': 6, 'ppg': 29.2, 'ppg_allowed': 21.5},
            ('KC', 2024): {'wins': 15, 'losses': 2, 'ppg': 23.3, 'ppg_allowed': 19.3},
            ('DET', 2024): {'wins': 15, 'losses': 2, 'ppg': 33.2, 'ppg_allowed': 21.3},
            ('PHI', 2024): {'wins': 14, 'losses': 3, 'ppg': 27.2, 'ppg_allowed': 18.8},
            ('BUF', 2024): {'wins': 13, 'losses': 4, 'ppg': 30.9, 'ppg_allowed': 22.4},
            ('MIN', 2024): {'wins': 14, 'losses': 3, 'ppg': 24.5, 'ppg_allowed': 20.8},
            # Some bad teams for comparison
            ('CLE', 2017): {'wins': 0, 'losses': 16, 'ppg': 14.6, 'ppg_allowed': 25.6},
            ('DET', 2008): {'wins': 0, 'losses': 16, 'ppg': 16.8, 'ppg_allowed': 32.3},
            ('CAR', 2001): {'wins': 1, 'losses': 15, 'ppg': 14.3, 'ppg_allowed': 20.6},
        }
        
        # Handle Raiders abbreviation changes
        if team_abbr == 'LV':
            for lookup_abbr in ['LV', 'OAK']:
                if (lookup_abbr, year) in legendary_seasons:
                    data = legendary_seasons[(lookup_abbr, year)]
                    total = data['wins'] + data['losses']
                    return {
                        'team': team_abbr,
                        'year': year,
                        'wins': data['wins'],
                        'losses': data['losses'],
                        'ties': 0,
                        'win_pct': data['wins'] / total,
                        'points_for': data['ppg'] * total,
                        'points_against': data['ppg_allowed'] * total,
                        'point_differential': (data['ppg'] - data['ppg_allowed']) * total,
                        'ppg': data['ppg'],
                        'ppg_allowed': data['ppg_allowed'],
                        'found': True,
                        'source': 'historical_preset'
                    }
        
        # Handle Rams abbreviation changes  
        if team_abbr == 'LAR':
            for lookup_abbr in ['LAR', 'STL', 'LA']:
                if (lookup_abbr, year) in legendary_seasons:
                    data = legendary_seasons[(lookup_abbr, year)]
                    total = data['wins'] + data['losses']
                    return {
                        'team': team_abbr,
                        'year': year,
                        'wins': data['wins'],
                        'losses': data['losses'],
                        'ties': 0,
                        'win_pct': data['wins'] / total,
                        'points_for': data['ppg'] * total,
                        'points_against': data['ppg_allowed'] * total,
                        'point_differential': (data['ppg'] - data['ppg_allowed']) * total,
                        'ppg': data['ppg'],
                        'ppg_allowed': data['ppg_allowed'],
                        'found': True,
                        'source': 'historical_preset'
                    }
        
        if (team_abbr, year) in legendary_seasons:
            data = legendary_seasons[(team_abbr, year)]
            total = data['wins'] + data['losses']
            return {
                'team': team_abbr,
                'year': year,
                'wins': data['wins'],
                'losses': data['losses'],
                'ties': 0,
                'win_pct': data['wins'] / total,
                'points_for': data['ppg'] * total,
                'points_against': data['ppg_allowed'] * total,
                'point_differential': (data['ppg'] - data['ppg_allowed']) * total,
                'ppg': data['ppg'],
                'ppg_allowed': data['ppg_allowed'],
                'found': True,
                'source': 'historical_preset'
            }
        
        # generic fallback - assume average team
        return {
            'team': team_abbr,
            'year': year,
            'wins': 8,
            'losses': 8,
            'ties': 0,
            'win_pct': 0.5,
            'points_for': 352,
            'points_against': 352,
            'point_differential': 0,
            'ppg': 22.0,
            'ppg_allowed': 22.0,
            'found': False,
            'source': 'fallback'
        }
    
    def predict_custom_game(self, home_team, home_year, away_team, away_year, neutral_site=False):
        """predicts a matchup between any two teams from any years using real statistical analysis"""
        import math
        import random
        
        # get historical stats for both teams
        home_stats = self.get_historical_team_stats(home_team, home_year)
        away_stats = self.get_historical_team_stats(away_team, away_year)
        
        # get team names for display
        home_info = self.NFL_TEAMS.get(home_team, {})
        away_info = self.NFL_TEAMS.get(away_team, {})
        
        home_name = home_info.get('name', home_team)
        away_name = away_info.get('name', away_team)
        
        # get historical name if different
        if 'history' in home_info:
            for era in home_info['history']:
                if era['years'][0] <= home_year <= era['years'][1]:
                    home_name = era['name']
                    break
        
        if 'history' in away_info:
            for era in away_info['history']:
                if era['years'][0] <= away_year <= era['years'][1]:
                    away_name = era['name']
                    break
        
        # ========== CALCULATE TEAM POWER RATINGS ==========
        # Using Pythagorean expectation (Bill James formula adapted for NFL)
        # Expected Win% = PF^2.37 / (PF^2.37 + PA^2.37)
        
        def pythagorean_expectation(ppg, ppg_allowed):
            """Calculate expected win% using Pythagorean formula"""
            if ppg <= 0 or ppg_allowed <= 0:
                return 0.5
            exponent = 2.37  # NFL-specific exponent
            pf_exp = ppg ** exponent
            pa_exp = ppg_allowed ** exponent
            return pf_exp / (pf_exp + pa_exp)
        
        def calculate_team_rating(stats):
            """Calculate overall team rating (0-100 scale)"""
            # Point differential per game is the best predictor
            point_diff = stats['ppg'] - stats['ppg_allowed']
            
            # Pythagorean win expectation
            pyth_win_pct = pythagorean_expectation(stats['ppg'], stats['ppg_allowed'])
            
            # Offensive rating (points scored relative to league average ~22)
            off_rating = (stats['ppg'] - 22) * 3  # Each point above/below avg = 3 rating points
            
            # Defensive rating (points allowed relative to league average)
            def_rating = (22 - stats['ppg_allowed']) * 3  # Lower is better
            
            # Combine factors
            # Base rating of 50, adjusted by:
            # - Point differential (major factor)
            # - Pythagorean expectation (accounts for scoring balance)
            # - Actual win percentage (proven results)
            
            rating = 50
            rating += point_diff * 2  # Each point of differential = 2 rating points
            rating += (pyth_win_pct - 0.5) * 30  # Pythagorean adjustment
            rating += (stats['win_pct'] - 0.5) * 20  # Win% adjustment
            
            # Cap between 20-95
            return max(20, min(95, rating))
        
        home_rating = calculate_team_rating(home_stats)
        away_rating = calculate_team_rating(away_stats)
        
        # ========== MATCHUP ANALYSIS ==========
        # How does each team's offense match up against the other's defense?
        
        # Home offense vs Away defense
        # If home team scores 30 PPG and away allows 25 PPG, expected = ~27.5
        home_expected_offense = (home_stats['ppg'] * 0.6 + away_stats['ppg_allowed'] * 0.4)
        
        # Away offense vs Home defense  
        away_expected_offense = (away_stats['ppg'] * 0.6 + home_stats['ppg_allowed'] * 0.4)
        
        # Adjust for era differences (teams from different eras may have different scoring environments)
        # Normalize to average ~22 PPG
        home_era_avg = (home_stats['ppg'] + home_stats['ppg_allowed']) / 2
        away_era_avg = (away_stats['ppg'] + away_stats['ppg_allowed']) / 2
        combined_era_avg = (home_era_avg + away_era_avg) / 2
        
        # Scale expected scores to a normalized environment
        era_adjustment = 22 / combined_era_avg if combined_era_avg > 0 else 1
        home_expected_offense *= era_adjustment
        away_expected_offense *= era_adjustment
        
        # ========== HOME FIELD ADVANTAGE ==========
        # NFL home field advantage is worth approximately 2.5-3 points
        HOME_FIELD_ADVANTAGE = 2.5
        
        if not neutral_site:
            home_expected_offense += HOME_FIELD_ADVANTAGE * 0.4  # Offense boost
            away_expected_offense -= HOME_FIELD_ADVANTAGE * 0.4  # Defense tougher at home
        
        # ========== WIN PROBABILITY CALCULATION ==========
        # Use rating difference to calculate win probability
        # Each point of rating difference = ~2.5% win probability shift
        
        rating_diff = home_rating - away_rating
        
        # Add home field advantage to rating diff (worth ~3 rating points)
        if not neutral_site:
            rating_diff += 3
        
        # Convert rating difference to probability using logistic function
        # This creates an S-curve where big differences = high confidence
        # but very close matchups = near 50/50
        
        def logistic_probability(diff, k=0.08):
            """Convert rating difference to win probability"""
            return 1 / (1 + math.exp(-k * diff))
        
        home_win_prob = logistic_probability(rating_diff)
        
        # ========== PREDICTED SCORE CALCULATION ==========
        # Base scores on expected offensive output
        home_predicted = home_expected_offense
        away_predicted = away_expected_offense
        
        # Adjust based on win probability (winner tends to score more)
        prob_adjustment = (home_win_prob - 0.5) * 6
        home_predicted += prob_adjustment
        away_predicted -= prob_adjustment
        
        # Add some variance based on team styles
        # High-scoring teams have more variance
        home_variance = (home_stats['ppg'] - 22) * 0.1
        away_variance = (away_stats['ppg'] - 22) * 0.1
        
        # Round to realistic NFL scores
        home_predicted = round(home_predicted + home_variance)
        away_predicted = round(away_predicted + away_variance)
        
        # Ensure scores are realistic (NFL games typically 14-45 range)
        home_predicted = max(7, min(52, home_predicted))
        away_predicted = max(7, min(52, away_predicted))
        
        # Ensure the predicted winner actually has the higher score
        if home_win_prob >= 0.5:
            if home_predicted <= away_predicted:
                # Margin based on probability
                margin = max(3, round((home_win_prob - 0.5) * 20))
                home_predicted = away_predicted + margin
        else:
            if away_predicted <= home_predicted:
                margin = max(3, round((0.5 - home_win_prob) * 20))
                away_predicted = home_predicted + margin
        
        # ========== FORMAT OUTPUT ==========
        if home_win_prob >= 0.5:
            predicted_winner = f"{home_name} ({home_year})"
            confidence = home_win_prob * 100
            predicted_score = f"{home_predicted}-{away_predicted}"
            spread = f"{home_name} -{abs(home_predicted - away_predicted)}"
        else:
            predicted_winner = f"{away_name} ({away_year})"
            confidence = (1 - home_win_prob) * 100
            predicted_score = f"{away_predicted}-{home_predicted}"
            spread = f"{away_name} -{abs(away_predicted - home_predicted)}"
        
        # Don't let confidence go below 50% (that would mean other team wins)
        # or above 98% (nothing is certain in sports)
        confidence = max(50.1, min(98, confidence))
        
        # Generate analysis text
        home_point_diff = home_stats['ppg'] - home_stats['ppg_allowed']
        away_point_diff = away_stats['ppg'] - away_stats['ppg_allowed']
        
        analysis_parts = []
        
        # Compare eras
        if abs(home_year - away_year) >= 10:
            analysis_parts.append(f"Cross-era matchup spanning {abs(home_year - away_year)} years.")
        
        # Describe the matchup
        if abs(home_rating - away_rating) < 3:
            analysis_parts.append("This projects as a very close game between evenly-matched teams.")
        elif home_rating > away_rating:
            analysis_parts.append(f"The {home_name} have a significant edge based on their dominant {home_year} season.")
        else:
            analysis_parts.append(f"The {away_name} have a significant edge based on their dominant {away_year} season.")
        
        # Add scoring context
        if home_stats['ppg'] > 28 and away_stats['ppg'] > 28:
            analysis_parts.append("Both teams featured high-powered offenses, expect a shootout.")
        elif home_stats['ppg_allowed'] < 18 and away_stats['ppg_allowed'] < 18:
            analysis_parts.append("Both teams featured elite defenses, expect a low-scoring battle.")
        
        analysis = " ".join(analysis_parts)
        
        return {
            'home_team': {
                'abbreviation': home_team,
                'name': home_name,
                'year': home_year,
                'record': f"{home_stats['wins']}-{home_stats['losses']}",
                'ppg': round(home_stats['ppg'], 1),
                'ppg_allowed': round(home_stats['ppg_allowed'], 1),
                'win_pct': round(home_stats['win_pct'] * 100, 1),
                'rating': round(home_rating, 1),
                'point_diff': round(home_point_diff, 1),
                'data_found': home_stats.get('found', False)
            },
            'away_team': {
                'abbreviation': away_team,
                'name': away_name,
                'year': away_year,
                'record': f"{away_stats['wins']}-{away_stats['losses']}",
                'ppg': round(away_stats['ppg'], 1),
                'ppg_allowed': round(away_stats['ppg_allowed'], 1),
                'win_pct': round(away_stats['win_pct'] * 100, 1),
                'rating': round(away_rating, 1),
                'point_diff': round(away_point_diff, 1),
                'data_found': away_stats.get('found', False)
            },
            'prediction': {
                'winner': predicted_winner,
                'confidence': round(confidence, 1),
                'predicted_score': predicted_score,
                'spread': spread,
                'home_win_probability': round(home_win_prob * 100, 1),
                'neutral_site': neutral_site,
                'rating_diff': round(rating_diff, 1),
                'analysis': analysis
            },
            'matchup_analysis': {
                'home_expected_points': round(home_expected_offense, 1),
                'away_expected_points': round(away_expected_offense, 1),
                'home_point_diff': round(home_point_diff, 1),
                'away_point_diff': round(away_point_diff, 1)
            }
        }

# create the predictor object
predictor = NFLPredictor()

@app.route('/api/games', methods=['GET'])
def get_games():
    """main endpoint - returns games with predictions
    you can pass week number, season=full for everything, etc
    """
    try:
        week = request.args.get('week')
        season = request.args.get('season')
        season_type = request.args.get('type', 'current')
        year = int(request.args.get('year', 2025))
        
        # playoff round names
        postseason_names = {1: 'Wild Card', 2: 'Divisional', 3: 'Conference Championships', 4: 'Super Bowl'}
        
        if season == 'full':
            # user wants the whole season
            games = predictor.get_full_season(year=year)
        elif week:
            # user picked a specific week
            week_num = int(week)
            if week_num > 18:
                # thats a playoff week
                postseason_week = week_num - 18
                games = predictor.get_week_games(season_type=3, week=postseason_week, year=year)
                # label it with the round name
                for game in games:
                    game['round'] = postseason_names.get(postseason_week, f'Postseason Week {postseason_week}')
            else:
                games = predictor.get_week_games(season_type=2, week=week_num, year=year)
        elif season_type == 'postseason':
            # grab all playoff games
            games = []
            for w in range(1, 5):
                week_games = predictor.get_week_games(season_type=3, week=w, year=year)
                for game in week_games:
                    game['round'] = postseason_names.get(w, f'Postseason Week {w}')
                games.extend(week_games)
        else:
            # just show this weeks games
            games = predictor.get_current_week_games()
        
        predictions = [predictor.predict_game(game) for game in games]
        
        return jsonify({
            'success': True,
            'count': len(predictions),
            'games': predictions,
            'api_status': {
                'espn': True,
                'sportsdata_io': bool(API_KEYS['SPORTSDATA_IO']),
                'using_enhanced_data': bool(API_KEYS['SPORTSDATA_IO'])
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'games': []
        }), 500

@app.route('/api/predict', methods=['POST'])
def predict_single_game():
    """lets you predict one game at a time"""
    try:
        data = request.json
        prediction = predictor.predict_game(data)
        return jsonify({
            'success': True,
            'prediction': prediction
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/status', methods=['GET'])
def api_status():
    """quick check to see if everything is working"""
    return jsonify({
        'status': 'online',
        'apis': {
            'espn': 'active',
            'sportsdata_io': 'active' if API_KEYS['SPORTSDATA_IO'] else 'no_key',
        },
        'features': {
            'basic_predictions': True,
            'rookie_qb_analysis': True,
            'depth_chart_analysis': bool(API_KEYS['SPORTSDATA_IO']),
            'injury_reports': bool(API_KEYS['SPORTSDATA_IO']),
            'enhanced_stats': bool(API_KEYS['SPORTSDATA_IO'])
        }
    })

@app.route('/')
def home():
    """just shows basic info about the api"""
    return jsonify({
        'message': 'NFL Predictor API',
        'version': '1.0',
        'endpoints': [
            '/api/games - Get all games with predictions',
            '/api/predict - Predict a single game',
            '/api/status - Check API status',
            '/api/teams - Get all NFL teams',
            '/api/teams/year/<year> - Get teams that existed in a given year',
            '/api/teams/<abbr>/stats - Get historical stats for a team',
            '/api/predict/custom - Predict a custom historical matchup'
        ]
    })

# ========== CUSTOM GAME PREDICTOR ENDPOINTS ==========

@app.route('/api/teams', methods=['GET'])
def get_all_teams():
    """returns all 32 nfl teams"""
    try:
        teams = predictor.get_all_teams()
        return jsonify({
            'success': True,
            'count': len(teams),
            'teams': teams
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/teams/year/<int:year>', methods=['GET'])
def get_teams_for_year(year):
    """returns teams that existed in a specific year"""
    try:
        if year < 1920 or year > 2026:
            return jsonify({
                'success': False,
                'error': 'Year must be between 1920 and 2026'
            }), 400
        
        teams = predictor.get_teams_for_year(year)
        return jsonify({
            'success': True,
            'year': year,
            'count': len(teams),
            'teams': teams
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/teams/<abbr>/stats', methods=['GET'])
def get_team_historical_stats(abbr):
    """gets stats for a team from a specific year"""
    try:
        year = request.args.get('year', type=int)
        if not year:
            return jsonify({
                'success': False,
                'error': 'Year parameter is required'
            }), 400
        
        if year < 1970 or year > 2025:
            return jsonify({
                'success': False,
                'error': 'Year must be between 1970 and 2025'
            }), 400
        
        abbr = abbr.upper()
        if abbr not in predictor.NFL_TEAMS:
            return jsonify({
                'success': False,
                'error': f'Unknown team abbreviation: {abbr}'
            }), 400
        
        # check if team existed that year
        team_info = predictor.NFL_TEAMS[abbr]
        if team_info['founded'] > year:
            return jsonify({
                'success': False,
                'error': f"{team_info['name']} didn't exist in {year}. Team founded in {team_info['founded']}."
            }), 400
        
        stats = predictor.get_historical_team_stats(abbr, year)
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/predict/custom', methods=['POST'])
def predict_custom_game():
    """predicts a matchup between any two historical teams"""
    try:
        data = request.json
        
        home_team = data.get('home_team', '').upper()
        away_team = data.get('away_team', '').upper()
        home_year = int(data.get('home_year', 2025))
        away_year = int(data.get('away_year', 2025))
        neutral_site = data.get('neutral_site', False)
        
        # validate teams
        if home_team not in predictor.NFL_TEAMS:
            return jsonify({
                'success': False,
                'error': f'Unknown home team: {home_team}'
            }), 400
        
        if away_team not in predictor.NFL_TEAMS:
            return jsonify({
                'success': False,
                'error': f'Unknown away team: {away_team}'
            }), 400
        
        # validate years
        if home_year < 1970 or home_year > 2025:
            return jsonify({
                'success': False,
                'error': 'Home year must be between 1970 and 2025'
            }), 400
        
        if away_year < 1970 or away_year > 2025:
            return jsonify({
                'success': False,
                'error': 'Away year must be between 1970 and 2025'
            }), 400
        
        # check if teams existed in their respective years
        home_info = predictor.NFL_TEAMS[home_team]
        if home_info['founded'] > home_year:
            return jsonify({
                'success': False,
                'error': f"{home_info['name']} didn't exist in {home_year}. Team founded in {home_info['founded']}."
            }), 400
        
        away_info = predictor.NFL_TEAMS[away_team]
        if away_info['founded'] > away_year:
            return jsonify({
                'success': False,
                'error': f"{away_info['name']} didn't exist in {away_year}. Team founded in {away_info['founded']}."
            }), 400
        
        prediction = predictor.predict_custom_game(home_team, home_year, away_team, away_year, neutral_site)
        
        return jsonify({
            'success': True,
            'prediction': prediction
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    print("=" * 60)
    print("NFL PREDICTOR API STARTING")
    print("Using LOGISTIC REGRESSION for predictions")
    print("=" * 60)
    print("\nAPI Status:")
    print(f"  ESPN API: Active (No key required)")
    print(f"  SportsData.io: {'Active' if API_KEYS['SPORTSDATA_IO'] else 'No API Key'}")
    print("\nFeatures:")
    print("   Logistic Regression prediction model")
    print("   Real-time game schedules")
    print("   Rookie QB analysis")
    print("   Depth chart evaluation")
    print(f"   {'Enhanced' if API_KEYS['SPORTSDATA_IO'] else 'Basic'} injury reports")
    print(f"   {'Enhanced' if API_KEYS['SPORTSDATA_IO'] else 'Basic'} detailed player statistics")
    print("\nTo enable enhanced features:")
    print("  1. Get free API key from https://sportsdata.io")
    print("  2. Set environment variable: SPORTSDATA_API_KEY=your_key")
    print("=" * 60)
    print("\nServer running at http://localhost:5000")
    print("=" * 60)
    
    app.run(debug=True, port=5000)

