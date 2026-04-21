from flask import Blueprint, jsonify, request
import requests
import math

# create blueprint for nba routes
nba_bp = Blueprint('nba', __name__)


class NBAPredictor:
    """predicts nba games using Elo rating system - more accurate than logistic regression"""
    def __init__(self):
        self.espn_base_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
        self.cache = {}
        self.cache_timeout = 3600
        
        # ========== ELO RATING SYSTEM ==========
        # Elo parameters tuned for NBA
        self.BASE_ELO = 1500  # starting rating for all teams
        self.K_FACTOR = 20  # how much ratings change per game
        self.HOME_ADVANTAGE = 100  # home court worth ~100 Elo (~3.5 pts) - stronger in NBA
        self.elo_ratings = {}  # current Elo for each team
        
        # initialize all teams with base Elo
        self.initialize_elo_ratings()
        
        # build Elo from completed games
        self.train_elo_model()
    
    # all 30 nba teams
    NBA_TEAMS = {
        'ATL': {'name': 'Atlanta Hawks', 'city': 'Atlanta', 'founded': 1946},
        'BOS': {'name': 'Boston Celtics', 'city': 'Boston', 'founded': 1946},
        'BKN': {'name': 'Brooklyn Nets', 'city': 'Brooklyn', 'founded': 1967},
        'CHA': {'name': 'Charlotte Hornets', 'city': 'Charlotte', 'founded': 1988},
        'CHI': {'name': 'Chicago Bulls', 'city': 'Chicago', 'founded': 1966},
        'CLE': {'name': 'Cleveland Cavaliers', 'city': 'Cleveland', 'founded': 1970},
        'DAL': {'name': 'Dallas Mavericks', 'city': 'Dallas', 'founded': 1980},
        'DEN': {'name': 'Denver Nuggets', 'city': 'Denver', 'founded': 1967},
        'DET': {'name': 'Detroit Pistons', 'city': 'Detroit', 'founded': 1941},
        'GS': {'name': 'Golden State Warriors', 'city': 'Golden State', 'founded': 1946},
        'HOU': {'name': 'Houston Rockets', 'city': 'Houston', 'founded': 1967},
        'IND': {'name': 'Indiana Pacers', 'city': 'Indiana', 'founded': 1967},
        'LAC': {'name': 'LA Clippers', 'city': 'Los Angeles', 'founded': 1970},
        'LAL': {'name': 'Los Angeles Lakers', 'city': 'Los Angeles', 'founded': 1947},
        'MEM': {'name': 'Memphis Grizzlies', 'city': 'Memphis', 'founded': 1995},
        'MIA': {'name': 'Miami Heat', 'city': 'Miami', 'founded': 1988},
        'MIL': {'name': 'Milwaukee Bucks', 'city': 'Milwaukee', 'founded': 1968},
        'MIN': {'name': 'Minnesota Timberwolves', 'city': 'Minnesota', 'founded': 1989},
        'NO': {'name': 'New Orleans Pelicans', 'city': 'New Orleans', 'founded': 2002},
        'NY': {'name': 'New York Knicks', 'city': 'New York', 'founded': 1946},
        'OKC': {'name': 'Oklahoma City Thunder', 'city': 'Oklahoma City', 'founded': 1967},
        'ORL': {'name': 'Orlando Magic', 'city': 'Orlando', 'founded': 1989},
        'PHI': {'name': 'Philadelphia 76ers', 'city': 'Philadelphia', 'founded': 1946},
        'PHX': {'name': 'Phoenix Suns', 'city': 'Phoenix', 'founded': 1968},
        'POR': {'name': 'Portland Trail Blazers', 'city': 'Portland', 'founded': 1970},
        'SAC': {'name': 'Sacramento Kings', 'city': 'Sacramento', 'founded': 1945},
        'SA': {'name': 'San Antonio Spurs', 'city': 'San Antonio', 'founded': 1967},
        'TOR': {'name': 'Toronto Raptors', 'city': 'Toronto', 'founded': 1995},
        'UTA': {'name': 'Utah Jazz', 'city': 'Utah', 'founded': 1974},
        'WAS': {'name': 'Washington Wizards', 'city': 'Washington', 'founded': 1961}
    }
    
    # team id mapping for espn api
    TEAM_IDS = {
        'ATL': 1, 'BOS': 2, 'BKN': 17, 'CHA': 30, 'CHI': 4, 'CLE': 5, 'DAL': 6, 'DEN': 7,
        'DET': 8, 'GS': 9, 'HOU': 10, 'IND': 11, 'LAC': 12, 'LAL': 13, 'MEM': 29, 'MIA': 14,
        'MIL': 15, 'MIN': 16, 'NO': 3, 'NY': 18, 'OKC': 25, 'ORL': 19, 'PHI': 20, 'PHX': 21,
        'POR': 22, 'SAC': 23, 'SA': 24, 'TOR': 28, 'UTA': 26, 'WAS': 27
    }
    
    def get_games_by_date(self, date_str=None):
        """gets games for a specific date from espn"""
        try:
            if date_str:
                url = f"{self.espn_base_url}/scoreboard?dates={date_str}"
            else:
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
            print(f"Error fetching NBA games: {e}")
            return []
    
    def parse_espn_game(self, event):
        """pulls out the important stuff from espn's game data including live scores"""
        try:
            competition = event['competitions'][0]
            competitors = competition['competitors']
            
            home_team = next(team for team in competitors if team['homeAway'] == 'home')
            away_team = next(team for team in competitors if team['homeAway'] == 'away')
            
            # get each teams win-loss record
            home_record = home_team.get('records', [{}])[0].get('summary', '0-0') if home_team.get('records') else '0-0'
            away_record = away_team.get('records', [{}])[0].get('summary', '0-0') if away_team.get('records') else '0-0'
            
            # ========== LIVE SCORE DATA ==========
            status_obj = event.get('status', {})
            status_type = status_obj.get('type', {})
            
            # game state: pre, in, post
            game_state = status_type.get('state', 'pre')
            is_live = game_state == 'in'
            is_final = status_type.get('completed', False)
            
            # get current scores
            home_score = int(home_team.get('score', 0)) if home_team.get('score') else 0
            away_score = int(away_team.get('score', 0)) if away_team.get('score') else 0
            
            # get game clock info
            clock = status_obj.get('displayClock', '')
            period = status_obj.get('period', 0)
            
            # period display for NBA (1st, 2nd, 3rd, 4th, OT)
            period_names = {1: '1st', 2: '2nd', 3: '3rd', 4: '4th'}
            period_display = period_names.get(period, f'OT{period-4}' if period > 4 else '')
            
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
                'status': status_type.get('description', 'Scheduled'),
                # live game data
                'is_live': is_live,
                'is_final': is_final,
                'game_state': game_state,
                'home_score': home_score,
                'away_score': away_score,
                'clock': clock,
                'period': period,
                'period_display': period_display
            }
        except Exception as e:
            print(f"Error parsing NBA game: {e}")
            return None
    
    def get_standings(self, year=2026):
        """grabs the current nba standings"""
        cache_key = f'nba_standings_{year}'
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        standings = {}
        
        try:
            url = f"{self.espn_base_url}/standings?season={year}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # dig through espns format
                children = data.get('children', [])
                
                for conference in children:
                    entries = conference.get('standings', {}).get('entries', [])
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
                
                self.cache[cache_key] = standings
        except Exception as e:
            print(f"Error fetching NBA standings: {e}")
        
        return standings
    
    def get_team_stats(self, team_abbr):
        """looks up how good a team is based on their record"""
        cache_key = f'nba_team_stats_{team_abbr}'
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        stats = {
            'offense_rating': 70,
            'defense_rating': 70,
            'recent_form': 70,
            'win_pct': 0.5
        }
        
        try:
            standings = self.get_standings()
            if standings and team_abbr in standings:
                team_record = standings[team_abbr]
                wins = team_record.get('wins', 0)
                losses = team_record.get('losses', 0)
                total = wins + losses
                
                if total > 0:
                    win_pct = wins / total
                    stats['offense_rating'] = 50 + (win_pct * 50)
                    stats['defense_rating'] = 50 + (win_pct * 50)
                    stats['win_pct'] = win_pct
                    
                    pts_for = team_record.get('points_for', 0)
                    pts_against = team_record.get('points_against', 0)
                    if pts_for > 0 and pts_against > 0:
                        pts_diff = (pts_for - pts_against) / total
                        stats['offense_rating'] = min(100, max(50, 70 + pts_diff / 2))
                        stats['defense_rating'] = min(100, max(50, 70 - (pts_against / total - 110) / 2))
        except Exception as e:
            print(f"Error fetching NBA team stats: {e}")
        
        self.cache[cache_key] = stats
        return stats
    
    def get_team_ppg(self, team_abbr):
        """how many points does this team usually score"""
        standings = self.get_standings()
        if standings and team_abbr in standings:
            team = standings[team_abbr]
            games = team.get('wins', 0) + team.get('losses', 0)
            if games > 0:
                return team.get('points_for', 0) / games
        return 110.0  # nba league average
    
    def get_team_ppg_allowed(self, team_abbr):
        """how many points does this team give up per game"""
        standings = self.get_standings()
        if standings and team_abbr in standings:
            team = standings[team_abbr]
            games = team.get('wins', 0) + team.get('losses', 0)
            if games > 0:
                return team.get('points_against', 0) / games
        return 110.0  # league average

    def get_historical_team_stats(self, team_abbr, year):
        """gets a team's stats for a specific NBA season with fallback estimates"""
        standings = self.get_standings(year)
        team_data = standings.get(team_abbr, {}) if standings else {}

        if team_data:
            wins = team_data.get('wins', 0)
            losses = team_data.get('losses', 0)
            total_games = wins + losses

            if total_games > 0:
                points_for = team_data.get('points_for', 0)
                points_against = team_data.get('points_against', 0)
                ppg = points_for / total_games if points_for > 0 else 110.0
                ppg_allowed = points_against / total_games if points_against > 0 else 110.0
                point_diff = ppg - ppg_allowed

                return {
                    'team': self.NBA_TEAMS[team_abbr]['name'],
                    'abbreviation': team_abbr,
                    'year': year,
                    'wins': wins,
                    'losses': losses,
                    'win_pct': wins / total_games,
                    'ppg': ppg,
                    'ppg_allowed': ppg_allowed,
                    'point_diff': point_diff,
                    'found': True
                }

        # fallback estimate when season standings are unavailable
        team_elo = self.get_team_elo(team_abbr)
        elo_delta = team_elo - self.BASE_ELO
        estimated_win_pct = max(0.2, min(0.8, 0.5 + (elo_delta / 800)))
        estimated_wins = round(estimated_win_pct * 82)
        estimated_losses = 82 - estimated_wins
        estimated_ppg = 110 + (elo_delta / 50)
        estimated_ppg_allowed = 110 - (elo_delta / 60)

        return {
            'team': self.NBA_TEAMS[team_abbr]['name'],
            'abbreviation': team_abbr,
            'year': year,
            'wins': estimated_wins,
            'losses': estimated_losses,
            'win_pct': estimated_win_pct,
            'ppg': estimated_ppg,
            'ppg_allowed': estimated_ppg_allowed,
            'point_diff': estimated_ppg - estimated_ppg_allowed,
            'found': False
        }

    def predict_custom_game(self, home_team, home_year, away_team, away_year, neutral_site=False):
        """predicts a custom historical NBA matchup between any two teams"""
        home_stats = self.get_historical_team_stats(home_team, home_year)
        away_stats = self.get_historical_team_stats(away_team, away_year)

        # blend season strength and point differential into a power rating
        home_rating = (home_stats['win_pct'] * 100) + (home_stats['point_diff'] * 1.8)
        away_rating = (away_stats['win_pct'] * 100) + (away_stats['point_diff'] * 1.8)

        if not neutral_site:
            home_rating += 3.5  # NBA home-court advantage

        rating_diff = home_rating - away_rating
        home_win_prob = 1 / (1 + math.exp(-rating_diff / 8.0))

        if home_win_prob >= 0.5:
            winner = home_stats['team']
            confidence = round(home_win_prob * 100, 1)
        else:
            winner = away_stats['team']
            confidence = round((1 - home_win_prob) * 100, 1)

        confidence = max(50.0, min(99.0, confidence))

        # score model around tempo/scoring environment of both teams
        home_score = round((home_stats['ppg'] + away_stats['ppg_allowed']) / 2)
        away_score = round((away_stats['ppg'] + home_stats['ppg_allowed']) / 2)

        if not neutral_site:
            home_score += 2

        # enforce winner alignment with probability
        if home_win_prob >= 0.5 and home_score <= away_score:
            home_score = away_score + 3
        elif home_win_prob < 0.5 and away_score <= home_score:
            away_score = home_score + 3

        home_score = max(85, min(145, home_score))
        away_score = max(85, min(145, away_score))

        spread = f"{home_stats['team']} {'-' if home_win_prob >= 0.5 else '+'}{abs(round((home_score - away_score), 1))}"

        return {
            'home_team': {
                'name': home_stats['team'],
                'abbreviation': home_team,
                'year': home_year,
                'record': f"{home_stats['wins']}-{home_stats['losses']}",
                'win_pct': round(home_stats['win_pct'] * 100, 1),
                'rating': round(home_rating, 1),
                'point_diff': round(home_stats['point_diff'], 1),
                'data_found': home_stats['found']
            },
            'away_team': {
                'name': away_stats['team'],
                'abbreviation': away_team,
                'year': away_year,
                'record': f"{away_stats['wins']}-{away_stats['losses']}",
                'win_pct': round(away_stats['win_pct'] * 100, 1),
                'rating': round(away_rating, 1),
                'point_diff': round(away_stats['point_diff'], 1),
                'data_found': away_stats['found']
            },
            'prediction': {
                'winner': winner,
                'confidence': confidence,
                'predicted_score': f"{home_score}-{away_score}",
                'spread': spread,
                'neutral_site': neutral_site,
                'analysis': (
                    f"{home_stats['team']} ({home_year}) vs {away_stats['team']} ({away_year}): "
                    f"home win probability {round(home_win_prob * 100, 1)}%."
                )
            }
        }
    
    def get_recent_form(self, team_abbr):
        """checks if a team is hot or cold lately"""
        cache_key = f'nba_recent_form_{team_abbr}'
        
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
            standings = self.get_standings()
            if standings and team_abbr in standings:
                team_record = standings[team_abbr]
                wins = team_record.get('wins', 0)
                losses = team_record.get('losses', 0)
                total = wins + losses
                
                if total > 0:
                    win_pct = wins / total
                    form['form_rating'] = round(30 + (win_pct * 70))
                    form['wins'] = wins
                    form['losses'] = losses
                    form['last_5'] = f"{wins}W-{losses}L"
        except Exception as e:
            print(f"Error fetching NBA recent form: {e}")
        
        self.cache[cache_key] = form
        return form
    
    def get_completed_games(self, year=2026):
        """gets games that have already been played with their results"""
        completed_games = []
        
        try:
            # get recent completed games from scoreboard
            url = f"{self.espn_base_url}/scoreboard"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                for event in data.get('events', []):
                    status = event.get('status', {}).get('type', {}).get('completed', False)
                    if status:
                        game_data = self.parse_completed_game(event)
                        if game_data:
                            completed_games.append(game_data)
        except Exception as e:
            print(f"Error fetching completed NBA games: {e}")
        
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
            
            home_win = 1 if home_score > away_score else 0
            
            return {
                'home_team_abbr': home_team['team']['abbreviation'],
                'away_team_abbr': away_team['team']['abbreviation'],
                'home_score': home_score,
                'away_score': away_score,
                'home_win': home_win
            }
        except Exception as e:
            print(f"Error parsing completed NBA game: {e}")
            return None
    
    # ========== ELO RATING SYSTEM METHODS ==========
    
    def initialize_elo_ratings(self):
        """sets all NBA teams to base Elo rating"""
        for team_abbr in self.NBA_TEAMS.keys():
            self.elo_ratings[team_abbr] = self.BASE_ELO
        
        print(f"Initialized Elo ratings for {len(self.NBA_TEAMS)} NBA teams")
    
    def expected_win_probability(self, team_elo, opponent_elo, home_advantage=0):
        """calculates expected win probability using Elo formula
        
        The formula: E = 1 / (1 + 10^((opponent_elo - team_elo - home_advantage) / 400))
        """
        exponent = (opponent_elo - team_elo - home_advantage) / 400
        return 1 / (1 + math.pow(10, exponent))
    
    def update_elo(self, winner_elo, loser_elo, margin=None, k_factor=None):
        """updates Elo ratings after a game
        
        Returns: (new_winner_elo, new_loser_elo)
        
        Margin of victory multiplier for NBA:
        - NBA games can have big margins, so we use log to dampen effect
        """
        if k_factor is None:
            k_factor = self.K_FACTOR
        
        # expected probability that winner wins
        expected = self.expected_win_probability(winner_elo, loser_elo)
        
        # actual result is 1 (win) vs expected
        actual = 1
        
        # base Elo change
        change = k_factor * (actual - expected)
        
        # margin of victory multiplier (makes blowouts matter more)
        if margin is not None and margin > 0:
            elo_diff = abs(winner_elo - loser_elo)
            # log formula dampens huge margins in NBA
            mov_multiplier = math.log(margin + 1) * (2.2 / (elo_diff * 0.001 + 2.2))
            # cap the multiplier for NBA since margins can be huge
            mov_multiplier = min(mov_multiplier, 2.5)
            change *= mov_multiplier
        
        new_winner_elo = winner_elo + change
        new_loser_elo = loser_elo - change
        
        return new_winner_elo, new_loser_elo
    
    def train_elo_model(self):
        """builds Elo ratings from completed games this season"""
        print("\n========== BUILDING NBA ELO RATINGS ==========")
        
        completed_games = self.get_completed_games()
        
        if len(completed_games) < 5:
            print(f"Only {len(completed_games)} NBA games found. Using preset Elo ratings.")
            self.use_preset_elo()
            return
        
        print(f"Processing {len(completed_games)} completed NBA games...")
        
        games_processed = 0
        for game in completed_games:
            try:
                home_team = game['home_team_abbr']
                away_team = game['away_team_abbr']
                home_score = game['home_score']
                away_score = game['away_score']
                
                # make sure we have ratings for both teams
                if home_team not in self.elo_ratings:
                    self.elo_ratings[home_team] = self.BASE_ELO
                if away_team not in self.elo_ratings:
                    self.elo_ratings[away_team] = self.BASE_ELO
                
                # determine winner and margin
                if home_score > away_score:
                    winner = home_team
                    loser = away_team
                    margin = home_score - away_score
                elif away_score > home_score:
                    winner = away_team
                    loser = home_team
                    margin = away_score - home_score
                else:
                    # no ties in NBA
                    continue
                
                # update ratings
                winner_elo = self.elo_ratings[winner]
                loser_elo = self.elo_ratings[loser]
                
                new_winner_elo, new_loser_elo = self.update_elo(
                    winner_elo, loser_elo, margin=margin
                )
                
                self.elo_ratings[winner] = new_winner_elo
                self.elo_ratings[loser] = new_loser_elo
                games_processed += 1
                
            except Exception as e:
                print(f"Error processing NBA game: {e}")
                continue
        
        print(f"\nNBA Elo ratings built from {games_processed} games!")
        
        # show top and bottom teams
        sorted_teams = sorted(self.elo_ratings.items(), key=lambda x: x[1], reverse=True)
        print("\nTop 5 NBA Teams by Elo:")
        for team, elo in sorted_teams[:5]:
            print(f"  {team}: {elo:.0f}")
        print("\nBottom 5 NBA Teams by Elo:")
        for team, elo in sorted_teams[-5:]:
            print(f"  {team}: {elo:.0f}")
    
    def use_preset_elo(self):
        """uses preset Elo ratings based on recent NBA performance"""
        # preset ratings based on 2025-26 season expectations
        preset_ratings = {
            'BOS': 1620,  # celtics - defending champs
            'OKC': 1600,  # thunder - young stars
            'DEN': 1590,  # nuggets - jokic
            'MIL': 1580,  # bucks - giannis
            'PHX': 1575,  # suns - big 3
            'MIN': 1570,  # timberwolves - solid
            'NYK': 1565,  # knicks - improved
            'CLE': 1560,  # cavaliers - good team
            'LAL': 1555,  # lakers - lebron
            'DAL': 1550,  # mavericks - luka
            'MIA': 1545,  # heat - consistent  
            'SAC': 1540,  # kings - fun team
            'PHI': 1535,  # sixers - embiid
            'GS': 1530,   # warriors - curry
            'NO': 1525,   # pelicans - injuries
            'IND': 1520,  # pacers - young
            'LAC': 1515,  # clippers - post kawhi
            'ATL': 1510,  # hawks - average
            'HOU': 1505,  # rockets - rebuilding
            'ORL': 1500,  # magic - young
            'CHI': 1495,  # bulls - mid
            'TOR': 1490,  # raptors - rebuilding
            'MEM': 1485,  # grizzlies - injuries
            'SA': 1480,   # spurs - wemby developing
            'BKN': 1475,  # nets - rebuilding
            'UTA': 1470,  # jazz - tanking
            'POR': 1465,  # blazers - rebuilding
            'CHA': 1460,  # hornets - young
            'DET': 1455,  # pistons - rebuilding
            'WAS': 1450,  # wizards - worst record
        }
        
        for team, rating in preset_ratings.items():
            self.elo_ratings[team] = rating
        
        print("Using preset NBA Elo ratings based on recent performance")
    
    def get_team_elo(self, team_abbr):
        """gets current Elo rating for a team"""
        if team_abbr not in self.elo_ratings:
            self.elo_ratings[team_abbr] = self.BASE_ELO
        return self.elo_ratings[team_abbr]
    
    def predict_with_elo(self, home_team_abbr, away_team_abbr):
        """uses Elo ratings to predict who wins
        
        Returns win probability for home team (0-1)
        """
        home_elo = self.get_team_elo(home_team_abbr)
        away_elo = self.get_team_elo(away_team_abbr)
        
        # home team gets home court advantage added to their Elo
        home_win_prob = self.expected_win_probability(
            home_elo, away_elo, home_advantage=self.HOME_ADVANTAGE
        )
        
        return home_win_prob
    
    def calculate_live_win_probability(self, home_team_abbr, away_team_abbr, 
                                        home_score, away_score, period, clock=''):
        """calculates in-game win probability based on score and time remaining
        
        Blends pre-game Elo probability with current game state.
        As the game progresses, the current score matters more.
        
        NBA: 4 quarters of 12 minutes each = 48 minutes total
        """
        # get pre-game probability from Elo
        pregame_prob = self.predict_with_elo(home_team_abbr, away_team_abbr)
        
        # if game hasn't started, return pregame probability
        if period == 0 or (home_score == 0 and away_score == 0 and period <= 1):
            return pregame_prob, 0.0  # (probability, time_elapsed_pct)
        
        # calculate time elapsed (0 to 1)
        # NBA: 4 quarters, 12 min each
        try:
            # parse clock (format: "MM:SS" or "M:SS")
            if clock and ':' in clock:
                parts = clock.split(':')
                minutes = int(parts[0])
                seconds = int(parts[1]) if len(parts) > 1 else 0
                time_left_in_period = minutes + seconds / 60
            else:
                time_left_in_period = 12  # assume start of period
            
            # total time elapsed
            completed_quarters = min(period - 1, 4)
            if period <= 4:
                time_elapsed = (completed_quarters * 12) + (12 - time_left_in_period)
            else:
                # overtime (5 min periods)
                time_elapsed = 48 + ((period - 4 - 1) * 5) + (5 - min(time_left_in_period, 5))
            
            total_game_time = 48  # regulation
            time_elapsed_pct = min(time_elapsed / total_game_time, 1.0)
        except:
            time_elapsed_pct = (period - 1) / 4  # fallback
        
        # score differential impact
        score_diff = home_score - away_score
        
        # in NBA, scoring is higher so each point is worth less probability
        # roughly 0.02 win probability per point, scaling with time
        
        # score-based probability (logistic function)
        # NBA has more variance, so we use a smaller coefficient
        score_prob = 1 / (1 + math.exp(-score_diff * 0.08))
        
        # weight based on time elapsed
        # NBA has more comebacks than NFL, so keep more pregame weight longer
        # start: 75% pregame, 25% score
        # end: 5% pregame, 95% score
        pregame_weight = max(0.05, 0.75 - (time_elapsed_pct * 0.7))
        score_weight = 1 - pregame_weight
        
        live_prob = (pregame_prob * pregame_weight) + (score_prob * score_weight)
        
        # cap between 0.01 and 0.99
        live_prob = max(0.01, min(0.99, live_prob))
        
        return live_prob, time_elapsed_pct
    
    def update_elo_from_result(self, home_team_abbr, away_team_abbr, home_score, away_score):
        """updates Elo ratings after a game finishes
        
        Called automatically when a game transitions to 'final' status
        """
        if home_score == away_score:
            return  # no ties in NBA
        
        if home_score > away_score:
            winner = home_team_abbr
            loser = away_team_abbr
            margin = home_score - away_score
        else:
            winner = away_team_abbr
            loser = home_team_abbr
            margin = away_score - home_score
        
        winner_elo = self.get_team_elo(winner)
        loser_elo = self.get_team_elo(loser)
        
        new_winner_elo, new_loser_elo = self.update_elo(
            winner_elo, loser_elo, margin=margin
        )
        
        self.elo_ratings[winner] = new_winner_elo
        self.elo_ratings[loser] = new_loser_elo
        
        print(f"NBA Elo Updated: {winner} {winner_elo:.0f} -> {new_winner_elo:.0f}, "
              f"{loser} {loser_elo:.0f} -> {new_loser_elo:.0f}")
        
        return {
            'winner': winner,
            'loser': loser,
            'winner_elo_change': new_winner_elo - winner_elo,
            'loser_elo_change': new_loser_elo - loser_elo
        }

    def predict_game(self, game_info):
        """predicts who wins an nba game using Elo ratings"""
        home_team = game_info['home_team_abbr']
        away_team = game_info['away_team_abbr']
        
        home_record_str = game_info.get('home_record', '0-0')
        away_record_str = game_info.get('away_record', '0-0')
        
        def parse_record(record_str):
            parts = record_str.split('-')
            wins = int(parts[0]) if parts[0].isdigit() else 0
            losses = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            return wins, losses
        
        home_wins, home_losses = parse_record(home_record_str)
        away_wins, away_losses = parse_record(away_record_str)
        
        home_stats = self.get_team_stats(home_team)
        away_stats = self.get_team_stats(away_team)
        
        if home_wins + home_losses > 0:
            home_stats['win_pct'] = home_wins / (home_wins + home_losses)
        if away_wins + away_losses > 0:
            away_stats['win_pct'] = away_wins / (away_wins + away_losses)
        
        home_form = self.get_recent_form(home_team)
        away_form = self.get_recent_form(away_team)
        
        home_form['wins'] = home_wins
        home_form['losses'] = home_losses
        away_form['wins'] = away_wins
        away_form['losses'] = away_losses
        
        # ========== LIVE GAME HANDLING ==========
        is_live = game_info.get('is_live', False)
        is_final = game_info.get('is_final', False)
        home_score = game_info.get('home_score', 0)
        away_score = game_info.get('away_score', 0)
        period = game_info.get('period', 0)
        clock = game_info.get('clock', '')
        
        # USE ELO RATING SYSTEM to predict the winner
        pregame_prob = self.predict_with_elo(home_team, away_team)
        
        # if game is live, calculate live win probability
        if is_live:
            home_win_prob, time_elapsed_pct = self.calculate_live_win_probability(
                home_team, away_team, home_score, away_score, period, clock
            )
        elif is_final:
            # game is over - winner has 100% probability
            if home_score > away_score:
                home_win_prob = 1.0
            elif away_score > home_score:
                home_win_prob = 0.0
            else:
                home_win_prob = 0.5
            time_elapsed_pct = 1.0
        else:
            # game hasn't started - use pregame probability
            home_win_prob = pregame_prob
            time_elapsed_pct = 0.0
        
        if home_win_prob >= 0.5:
            predicted_winner = game_info['home_team']
            confidence_pct = home_win_prob * 100
        else:
            predicted_winner = game_info['away_team']
            confidence_pct = (1 - home_win_prob) * 100
        
        confidence_pct = max(50, min(99, confidence_pct))
        
        # predict score using team averages
        home_ppg = self.get_team_ppg(home_team)
        away_ppg = self.get_team_ppg(away_team)
        home_ppg_allowed = self.get_team_ppg_allowed(home_team)
        away_ppg_allowed = self.get_team_ppg_allowed(away_team)
        
        prob_diff = (pregame_prob - 0.5) * 2  # use pregame for score prediction
        
        home_predicted = round((home_ppg + away_ppg_allowed) / 2 + (prob_diff * 5))
        away_predicted = round((away_ppg + home_ppg_allowed) / 2 - (prob_diff * 5))
        
        # home team gets a small boost
        home_predicted += 2
        
        # nba scores typically between 90-130
        home_predicted = max(90, min(140, home_predicted))
        away_predicted = max(90, min(140, away_predicted))
        
        # winner should have higher score
        if home_win_prob >= 0.5:
            if home_predicted <= away_predicted:
                home_predicted = away_predicted + 4
            predicted_score = f"{home_predicted}-{away_predicted}"
        else:
            if away_predicted <= home_predicted:
                away_predicted = home_predicted + 4
            predicted_score = f"{away_predicted}-{home_predicted}"
        
        # get Elo ratings for response
        home_elo = self.get_team_elo(home_team)
        away_elo = self.get_team_elo(away_team)
        
        # build live data object
        live_data = {
            'is_live': is_live,
            'is_final': is_final,
            'home_score': home_score,
            'away_score': away_score,
            'period': period,
            'clock': clock,
            'pregame_probability': round(pregame_prob * 100, 1),
            'live_probability': round(home_win_prob * 100, 1) if is_live else None,
            'time_elapsed_pct': round(time_elapsed_pct * 100, 1) if is_live else None
        }
        
        return {
            'game_id': game_info['game_id'],
            'home_team': game_info['home_team'],
            'away_team': game_info['away_team'],
            'venue': game_info['venue'],
            'game_date': game_info['game_date'],
            'predicted_winner': predicted_winner,
            'confidence': round(confidence_pct, 1),
            'predicted_score': predicted_score,
            'home_win_probability': round(home_win_prob * 100, 1),
            'prediction_method': 'elo',
            'live_data': live_data,
            'analysis': {
                'home_win_prob': round(home_win_prob * 100, 1),
                'away_win_prob': round((1 - home_win_prob) * 100, 1),
                'home_elo': round(home_elo),
                'away_elo': round(away_elo),
                'elo_diff': round(home_elo - away_elo),
                'home_form': home_form,
                'away_form': away_form
            }
        }


# create the nba predictor
nba_predictor = NBAPredictor()


# ========== NBA API ENDPOINTS ==========

@nba_bp.route('/api/nba/games', methods=['GET'])
def get_nba_games():
    """main endpoint - returns nba games with predictions
    pass date parameter like ?date=20260414 for specific date
    """
    try:
        date = request.args.get('date')
        
        games = nba_predictor.get_games_by_date(date)
        
        if not games:
            return jsonify({
                'success': True,
                'count': 0,
                'games': [],
                'message': 'No NBA games found for this date'
            })
        
        predictions = [nba_predictor.predict_game(game) for game in games]
        
        return jsonify({
            'success': True,
            'count': len(predictions),
            'games': predictions,
            'api_status': {
                'espn': True
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'games': []
        }), 500


@nba_bp.route('/api/nba/teams', methods=['GET'])
def get_nba_teams():
    """returns all 30 nba teams"""
    try:
        teams = []
        for abbr, info in nba_predictor.NBA_TEAMS.items():
            teams.append({
                'abbreviation': abbr,
                'name': info['name'],
                'city': info['city'],
                'founded': info['founded'],
                'logo': f"https://a.espncdn.com/i/teamlogos/nba/500/{abbr.lower()}.png"
            })
        return jsonify({
            'success': True,
            'count': len(teams),
            'teams': sorted(teams, key=lambda x: x['name'])
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@nba_bp.route('/api/nba/teams/year/<int:year>', methods=['GET'])
def get_nba_teams_by_year(year):
    """returns NBA teams that existed in a given year"""
    try:
        if year < 1946 or year > 2026:
            return jsonify({
                'success': False,
                'error': 'Year must be between 1946 and 2026'
            }), 400

        teams = []
        for abbr, info in nba_predictor.NBA_TEAMS.items():
            if info.get('founded', 9999) <= year:
                teams.append({
                    'abbreviation': abbr,
                    'name': info['name'],
                    'city': info['city'],
                    'founded': info['founded'],
                    'logo': f"https://a.espncdn.com/i/teamlogos/nba/500/{abbr.lower()}.png"
                })

        return jsonify({
            'success': True,
            'count': len(teams),
            'year': year,
            'teams': sorted(teams, key=lambda x: x['name'])
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@nba_bp.route('/api/nba/teams/<abbr>/stats', methods=['GET'])
def get_nba_team_historical_stats(abbr):
    """returns NBA team stats for a specific year"""
    try:
        year = request.args.get('year', type=int)
        if not year:
            return jsonify({
                'success': False,
                'error': 'Year parameter is required'
            }), 400

        if year < 1946 or year > 2026:
            return jsonify({
                'success': False,
                'error': 'Year must be between 1946 and 2026'
            }), 400

        abbr = abbr.upper()
        if abbr not in nba_predictor.NBA_TEAMS:
            return jsonify({
                'success': False,
                'error': f'Unknown team abbreviation: {abbr}'
            }), 400

        team_info = nba_predictor.NBA_TEAMS[abbr]
        if team_info['founded'] > year:
            return jsonify({
                'success': False,
                'error': f"{team_info['name']} didn't exist in {year}. Team founded in {team_info['founded']}."
            }), 400

        stats = nba_predictor.get_historical_team_stats(abbr, year)
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@nba_bp.route('/api/nba/standings', methods=['GET'])
def get_nba_standings():
    """returns current nba standings"""
    try:
        standings = nba_predictor.get_standings()
        return jsonify({
            'success': True,
            'standings': standings
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@nba_bp.route('/api/nba/elo', methods=['GET'])
def get_nba_elo_ratings():
    """returns current Elo ratings for all NBA teams"""
    try:
        sorted_teams = sorted(nba_predictor.elo_ratings.items(), key=lambda x: x[1], reverse=True)
        
        ratings = []
        for rank, (team, elo) in enumerate(sorted_teams, 1):
            team_info = nba_predictor.NBA_TEAMS.get(team, {})
            ratings.append({
                'rank': rank,
                'team': team,
                'name': team_info.get('name', team),
                'elo': round(elo),
                'above_average': round(elo - 1500)
            })
        
        return jsonify({
            'success': True,
            'prediction_method': 'elo',
            'base_elo': nba_predictor.BASE_ELO,
            'k_factor': nba_predictor.K_FACTOR,
            'home_advantage': nba_predictor.HOME_ADVANTAGE,
            'count': len(ratings),
            'ratings': ratings
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@nba_bp.route('/api/nba/predict/custom', methods=['POST'])
def predict_nba_custom_game():
    """predicts a custom historical NBA matchup"""
    try:
        data = request.json

        home_team = data.get('home_team', '').upper()
        away_team = data.get('away_team', '').upper()
        home_year = int(data.get('home_year', 2026))
        away_year = int(data.get('away_year', 2026))
        neutral_site = data.get('neutral_site', False)

        if home_team not in nba_predictor.NBA_TEAMS:
            return jsonify({
                'success': False,
                'error': f'Unknown home team: {home_team}'
            }), 400

        if away_team not in nba_predictor.NBA_TEAMS:
            return jsonify({
                'success': False,
                'error': f'Unknown away team: {away_team}'
            }), 400

        if home_year < 1946 or home_year > 2026:
            return jsonify({
                'success': False,
                'error': 'Home year must be between 1946 and 2026'
            }), 400

        if away_year < 1946 or away_year > 2026:
            return jsonify({
                'success': False,
                'error': 'Away year must be between 1946 and 2026'
            }), 400

        home_info = nba_predictor.NBA_TEAMS[home_team]
        away_info = nba_predictor.NBA_TEAMS[away_team]

        if home_info['founded'] > home_year:
            return jsonify({
                'success': False,
                'error': f"{home_info['name']} didn't exist in {home_year}. Team founded in {home_info['founded']}."
            }), 400

        if away_info['founded'] > away_year:
            return jsonify({
                'success': False,
                'error': f"{away_info['name']} didn't exist in {away_year}. Team founded in {away_info['founded']}."
            }), 400

        prediction = nba_predictor.predict_custom_game(home_team, home_year, away_team, away_year, neutral_site)

        return jsonify({
            'success': True,
            'prediction': prediction
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
