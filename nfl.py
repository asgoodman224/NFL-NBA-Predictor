from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv

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
        """this is where the magic happens - predicts who wins"""
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
        
        # crunch all the numbers
        home_score = self.calculate_prediction_score(
            home_stats, home_qb, home_form, home_injuries, is_home=True
        )
        away_score = self.calculate_prediction_score(
            away_stats, away_qb, away_form, away_injuries, is_home=False
        )
        
        # whoever has the higher score wins
        predicted_winner = game_info['home_team'] if home_score > away_score else game_info['away_team']
        confidence = abs(home_score - away_score)
        # bigger gap = more confident, but cap it at 95%
        confidence_pct = min(60 + (confidence * 3), 95)
        
        # now predict the actual score using their averages
        home_ppg = self.get_team_ppg(home_team)
        away_ppg = self.get_team_ppg(away_team)
        home_ppg_allowed = self.get_team_ppg_allowed(home_team)
        away_ppg_allowed = self.get_team_ppg_allowed(away_team)
        
        # mix their scoring with how much the other team allows
        # and adjust based on whos favored
        score_diff = home_score - away_score
        
        home_predicted = round((home_ppg + away_ppg_allowed) / 2 + (score_diff * 0.5))
        away_predicted = round((away_ppg + home_ppg_allowed) / 2 - (score_diff * 0.5))
        
        # home team gets a small boost
        home_predicted += 2
        away_predicted -= 1
        
        # make sure scores are realistic
        home_predicted = max(10, min(50, home_predicted))
        away_predicted = max(10, min(50, away_predicted))
        
        if home_score > away_score:
            predicted_score = f"{home_predicted}-{away_predicted}"
        else:
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
            'analysis': {
                'home_score': round(home_score, 1),
                'away_score': round(away_score, 1),
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
            '/api/status - Check API status'
        ]
    })

if __name__ == '__main__':
    print("=" * 60)
    print("NFL PREDICTOR API STARTING")
    print("=" * 60)
    print("\nAPI Status:")
    print(f"  ESPN API: Active (No key required)")
    print(f"  SportsData.io: {'Active' if API_KEYS['SPORTSDATA_IO'] else 'No API Key'}")
    print("\nFeatures:")
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

