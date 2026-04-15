

// grab the buttons and containers from the page
const loadGamesBtn = document.getElementById('loadGamesBtn');
const gamesContainer = document.getElementById('gamesContainer');
const weekSelect = document.getElementById('weekSelect');
const homeLink = document.getElementById('homeLink');
const customGameLink = document.getElementById('customGameLink');
const nbaLink = document.getElementById('nbaLink');
const nbaContainer = document.getElementById('nbaContainer');
const controlsDiv = document.querySelector('.controls');

// nba elements
const loadNBAGamesBtn = document.getElementById('loadNBAGamesBtn');
const nbaGamesContainer = document.getElementById('nbaGamesContainer');
const nbaDateSelect = document.getElementById('nbaDateSelect');

// custom game elements
const customGameContainer = document.getElementById('customGameContainer');
const homeYearSelect = document.getElementById('homeYearSelect');
const homeTeamSelect = document.getElementById('homeTeamSelect');
const awayYearSelect = document.getElementById('awayYearSelect');
const awayTeamSelect = document.getElementById('awayTeamSelect');
const homeTeamPreview = document.getElementById('homeTeamPreview');
const awayTeamPreview = document.getElementById('awayTeamPreview');
const predictCustomBtn = document.getElementById('predictCustomBtn');
const customResultContainer = document.getElementById('customResultContainer');

// where the server is running
const API_BASE_URL = 'http://localhost:5000';

// navigation handling
homeLink.addEventListener('click', (e) => {
    e.preventDefault();
    showHomePage();
});

customGameLink.addEventListener('click', (e) => {
    e.preventDefault();
    showCustomGamePage();
});

nbaLink.addEventListener('click', (e) => {
    e.preventDefault();
    showNBAPage();
});

function showHomePage() {
    homeLink.classList.add('active');
    customGameLink.classList.remove('active');
    nbaLink.classList.remove('active');
    controlsDiv.style.display = 'flex';
    gamesContainer.style.display = 'grid';
    customGameContainer.style.display = 'none';
    nbaContainer.style.display = 'none';
}

function showNBAPage() {
    nbaLink.classList.add('active');
    homeLink.classList.remove('active');
    customGameLink.classList.remove('active');
    controlsDiv.style.display = 'none';
    gamesContainer.style.display = 'none';
    customGameContainer.style.display = 'none';
    nbaContainer.style.display = 'block';
}

function showCustomGamePage() {
    customGameLink.classList.add('active');
    homeLink.classList.remove('active');
    nbaLink.classList.remove('active');
    controlsDiv.style.display = 'none';
    gamesContainer.style.display = 'none';
    nbaContainer.style.display = 'none';
    customGameContainer.style.display = 'block';
    
    // initialize year dropdowns if not already done
    if (homeYearSelect.options.length <= 1) {
        populateYearDropdowns();
    }
}

// when they click load games
loadGamesBtn.addEventListener('click', loadGames);

// main function that gets the games and shows them
async function loadGames() {
    // show loading spinner while we wait
    gamesContainer.innerHTML = '<div class="loading"><div class="spinner"></div>Loading NFL Games...</div>';

    try {
        // figure out which week they want
        const selection = weekSelect.value;
        let url = `${API_BASE_URL}/api/games`;
        
        if (selection === 'full') {
            url += '?season=full';
            gamesContainer.innerHTML = '<div class="loading"><div class="spinner"></div>Loading Full Season...</div>';
        } else if (selection !== 'current') {
            url += `?week=${selection}`;
        }
        
        const response = await fetch(url);
        
        if (!response.ok) {
           throw new Error(`Could not load games`)
        }
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error || 'Failed to load games');
        }
        
        gamesContainer.innerHTML = '';
        
        // show each game
        if (data.games && data.games.length > 0) {
            data.games.forEach((game, index) => {
                const gameCard = createGameCard(game, index + 1);
                gamesContainer.appendChild(gameCard);
            });
            
            // if current week and any games are live, auto-refresh every 5 seconds
            const hasLiveGames = data.games.some(g => g.live_data && g.live_data.is_live);
            if (selection === 'current' && hasLiveGames) {
                const liveMsg = document.createElement('div');
                liveMsg.className = 'live-refresh-msg';
                liveMsg.innerHTML = ' LIVE - Predictions updating every 5 seconds';
                gamesContainer.insertBefore(liveMsg, gamesContainer.firstChild);
                startLiveRefresh('nfl');
            } else {
                stopLiveRefresh('nfl');
            }
        } else {
            gamesContainer.innerHTML = '<div class="no-games">No games available for this week.</div>';
        }
        
    } catch (error) {
        console.error('Error loading games:', error);
        gamesContainer.innerHTML = `
            <div class="error-message">
                <h3>Unable to Load Games</h3>
                <p>Please make sure the prediction server is running and try again.</p>
            </div>
        `;
        stopLiveRefresh('nfl');
    }
}

// live refresh intervals
let nflLiveInterval = null;
let nbaLiveInterval = null;

// track previous scores for animation
let previousNBAScores = {};

function startLiveRefresh(sport) {
    if (sport === 'nfl') {
        if (nflLiveInterval) clearInterval(nflLiveInterval);
        nflLiveInterval = setInterval(() => {
            if (weekSelect.value === 'current') {
                loadCurrentGamesQuiet();
            } else {
                stopLiveRefresh('nfl');
            }
        }, 5000);
    } else if (sport === 'nba') {
        if (nbaLiveInterval) clearInterval(nbaLiveInterval);
        nbaLiveInterval = setInterval(() => {
            if (nbaDateSelect.value === 'today') {
                loadNBAGamesQuiet();
            } else {
                stopLiveRefresh('nba');
            }
        }, 5000);
    }
}

function stopLiveRefresh(sport) {
    if (sport === 'nfl' && nflLiveInterval) {
        clearInterval(nflLiveInterval);
        nflLiveInterval = null;
    } else if (sport === 'nba' && nbaLiveInterval) {
        clearInterval(nbaLiveInterval);
        nbaLiveInterval = null;
    }
}

// quiet reload of current week live games without spinner
async function loadCurrentGamesQuiet() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/games`);
        if (!response.ok) return;

        const data = await response.json();
        if (!data.success || !data.games) return;

        const hasLiveGames = data.games.some(g => g.live_data && g.live_data.is_live);
        if (!hasLiveGames) {
            stopLiveRefresh('nfl');
        }

        const existingMsg = gamesContainer.querySelector('.live-refresh-msg');
        gamesContainer.innerHTML = '';
        if (existingMsg) gamesContainer.appendChild(existingMsg);

        data.games.forEach((game, index) => {
            const gameCard = createGameCard(game, index + 1);
            gamesContainer.appendChild(gameCard);
        });
    } catch (error) {
        console.error('Error refreshing live games:', error);
    }
}

// builds the html for each game card
function createGameCard(game, gameNumber) {
    const card = document.createElement('div');
    card.className = 'game-card';
    
    // check for live data
    const liveData = game.live_data || {};
    const isLive = liveData.is_live || false;
    const isFinal = liveData.is_final || false;

    // make the date look nice
    let dateStr = '';
    if (game.game_date) {
        const date = new Date(game.game_date);
        dateStr = date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
    }

    // show week number or playoff round
    let weekInfo = '';
    if (game.round) {
        weekInfo = `<div class="week-badge playoff">${game.round}</div>`;
    } else if (game.week) {
        weekInfo = `<div class="week-badge">Week ${game.week}</div>`;
    }

    // flag any rookie qbs
    let rookieIndicator = '';
    if (game.analysis) {
        if (game.analysis.home_qb?.is_rookie) {
            rookieIndicator += `<span class="rookie-badge" title="Rookie QB: ${game.analysis.home_qb.qb_name}">${game.home_team} - Rookie QB</span>`;
        }
        if (game.analysis.away_qb?.is_rookie) {
            rookieIndicator += `<span class="rookie-badge" title="Rookie QB: ${game.analysis.away_qb.qb_name}">${game.away_team} - Rookie QB</span>`;
        }
    }

    // show how many guys are hurt
    let injuryInfo = '';
    if (game.analysis) {
        const homeInjuries = game.analysis.home_injuries?.total_injuries || 0;
        const awayInjuries = game.analysis.away_injuries?.total_injuries || 0;
        
        if (homeInjuries > 0 || awayInjuries > 0) {
            injuryInfo = `<div class="injury-info">
                <span title="${homeInjuries} injuries">${game.home_team}: ${homeInjuries} injuries</span>
                <span title="${awayInjuries} injuries">${game.away_team}: ${awayInjuries} injuries</span>
            </div>`;
        }
    }

    // their records and streaks
    let formInfo = '';
    if (game.analysis) {
        const homeForm = game.analysis.home_form || {};
        const awayForm = game.analysis.away_form || {};
        const homeRecord = `${homeForm.wins || 0}W-${homeForm.losses || 0}L`;
        const awayRecord = `${awayForm.wins || 0}W-${awayForm.losses || 0}L`;
        const homeStreak = homeForm.streak || 'N/A';
        const awayStreak = awayForm.streak || 'N/A';
        
        formInfo = `<div class="form-info">
            <small>Season Record - ${game.home_team}: ${homeRecord} (${homeStreak}) | ${game.away_team}: ${awayRecord} (${awayStreak})</small>
        </div>`;
    }
    
    // build live score display
    let liveScoreDisplay = '';
    let statusBadge = '';
    let liveProbDisplay = '';
    
    if (isLive) {
        statusBadge = '<div class="status-badge live-badge">LIVE</div>';
        liveScoreDisplay = `
            <div class="live-score">
                <span class="score">${liveData.home_score || 0}</span>
                <span class="score-separator">-</span>
                <span class="score">${liveData.away_score || 0}</span>
            </div>
            <div class="game-clock">Q${liveData.period || 1} - ${liveData.clock || '15:00'}</div>
        `;
        liveProbDisplay = `
            <div class="live-probability">
                <div class="live-prob-label">Live Win Probability</div>
                <div class="live-prob-bar">
                    <div class="live-prob-fill home" style="width: ${liveData.live_probability || 50}%"></div>
                </div>
                <div class="live-prob-values">
                    <span>${game.home_team}: ${liveData.live_probability || 50}%</span>
                    <span>${game.away_team}: ${(100 - (liveData.live_probability || 50)).toFixed(1)}%</span>
                </div>
            </div>
        `;
    } else if (isFinal) {
        statusBadge = '<div class="status-badge final-badge">FINAL</div>';
        liveScoreDisplay = `
            <div class="final-score">
                <span class="score">${liveData.home_score || 0}</span>
                <span class="score-separator">-</span>
                <span class="score">${liveData.away_score || 0}</span>
            </div>
        `;
    }

    card.innerHTML = `
        <h3>Game ${gameNumber}</h3>
        <div class="badge-container">
            ${weekInfo}
            ${statusBadge}
        </div>
        ${dateStr ? `<div class="game-date">${dateStr}</div>` : ''}
        ${game.venue ? `<div class="venue">${game.venue}</div>` : ''}
        <div class="matchup">
            <span class="team">${game.away_team}</span>
            <span class="vs">@</span>
            <span class="team">${game.home_team}</span>
        </div>
        ${liveScoreDisplay}
        ${liveProbDisplay}
        ${rookieIndicator ? `<div class="rookie-indicators">${rookieIndicator}</div>` : ''}
        ${injuryInfo}
        <div class="prediction">
            <div class="prediction-label">${isFinal ? 'Final Result' : 'Predicted Winner'}</div>
            <div class="predicted-winner">${game.predicted_winner}</div>
            <div class="confidence">${isLive ? 'Live' : ''} Confidence: ${game.confidence}%</div>
            ${!isLive && !isFinal ? `<div class="confidence">Predicted Score: ${game.predicted_score}</div>` : ''}
        </div>
        ${formInfo}
    `;
    
    // add live class for styling
    if (isLive) {
        card.classList.add('live-game');
    } else if (isFinal) {
        card.classList.add('final-game');
    }

    return card;
}

// ========== CUSTOM GAME PREDICTOR FUNCTIONS ==========

// populate year dropdowns (1970 - 2025)
function populateYearDropdowns() {
    const currentYear = 2025;
    const startYear = 1970;
    
    for (let year = currentYear; year >= startYear; year--) {
        const homeOption = document.createElement('option');
        homeOption.value = year;
        homeOption.textContent = year;
        homeYearSelect.appendChild(homeOption);
        
        const awayOption = document.createElement('option');
        awayOption.value = year;
        awayOption.textContent = year;
        awayYearSelect.appendChild(awayOption);
    }
    
    // set default to current year
    homeYearSelect.value = currentYear;
    awayYearSelect.value = currentYear;
    
    // load teams for default year
    loadTeamsForYear(homeYearSelect, homeTeamSelect, currentYear);
    loadTeamsForYear(awayYearSelect, awayTeamSelect, currentYear);
}

// load teams that existed in a given year
async function loadTeamsForYear(yearSelect, teamSelect, year) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/teams/year/${year}`);
        const data = await response.json();
        
        if (data.success && data.teams) {
            // clear existing options except the first placeholder
            teamSelect.innerHTML = '<option value="">Select a team...</option>';
            
            data.teams.forEach(team => {
                const option = document.createElement('option');
                option.value = team.abbreviation;
                // show historical name if different from current
                if (team.historical_name && team.historical_name !== team.name) {
                    option.textContent = `${team.historical_name}`;
                } else {
                    option.textContent = team.name;
                }
                option.dataset.logo = team.logo;
                teamSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading teams:', error);
    }
}

// load team stats preview
async function loadTeamPreview(teamAbbr, year, previewContainer) {
    if (!teamAbbr) {
        previewContainer.innerHTML = '<div class="team-preview-empty">Select a team to see stats</div>';
        return;
    }
    
    previewContainer.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    previewContainer.classList.add('loading');
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/teams/${teamAbbr}/stats?year=${year}`);
        const data = await response.json();
        
        previewContainer.classList.remove('loading');
        
        if (data.success && data.stats) {
            const stats = data.stats;
            const logoUrl = `https://a.espncdn.com/i/teamlogos/nfl/500/${teamAbbr.toLowerCase()}.png`;
            
            previewContainer.innerHTML = `
                <div class="team-preview-content">
                    <img src="${logoUrl}" alt="${teamAbbr}" class="team-preview-logo" onerror="this.style.display='none'">
                    <div class="team-preview-name">${stats.team} (${stats.year})</div>
                    <div class="team-preview-stats">
                        <div class="preview-stat">
                            <div class="preview-stat-label">Record</div>
                            <div class="preview-stat-value">${stats.wins}-${stats.losses}${stats.ties > 0 ? '-' + stats.ties : ''}</div>
                        </div>
                        <div class="preview-stat">
                            <div class="preview-stat-label">Win %</div>
                            <div class="preview-stat-value">${(stats.win_pct * 100).toFixed(1)}%</div>
                        </div>
                        <div class="preview-stat">
                            <div class="preview-stat-label">PPG</div>
                            <div class="preview-stat-value">${stats.ppg.toFixed(1)}</div>
                        </div>
                        <div class="preview-stat">
                            <div class="preview-stat-label">PPG Allowed</div>
                            <div class="preview-stat-value">${stats.ppg_allowed.toFixed(1)}</div>
                        </div>
                    </div>
                    ${!stats.found ? '<div class="data-disclaimer">* Estimated stats</div>' : ''}
                </div>
            `;
        } else {
            previewContainer.innerHTML = `<div class="team-preview-empty">${data.error || 'Unable to load stats'}</div>`;
        }
    } catch (error) {
        console.error('Error loading team preview:', error);
        previewContainer.classList.remove('loading');
        previewContainer.innerHTML = '<div class="team-preview-empty">Error loading stats</div>';
    }
}

// predict custom game
async function predictCustomGame() {
    const homeTeam = homeTeamSelect.value;
    const homeYear = parseInt(homeYearSelect.value);
    const awayTeam = awayTeamSelect.value;
    const awayYear = parseInt(awayYearSelect.value);
    
    if (!homeTeam || !awayTeam) {
        customResultContainer.innerHTML = `
            <div class="error-message">
                <h3>Select Both Teams</h3>
                <p>Please select a team for both home and away sides.</p>
            </div>
        `;
        return;
    }
    
    if (homeTeam === awayTeam && homeYear === awayYear) {
        customResultContainer.innerHTML = `
            <div class="error-message">
                <h3>Same Team Selected</h3>
                <p>Please select different teams or different years.</p>
            </div>
        `;
        return;
    }
    
    // show loading state
    predictCustomBtn.disabled = true;
    predictCustomBtn.textContent = 'Predicting...';
    customResultContainer.innerHTML = '<div class="loading"><div class="spinner"></div>Analyzing matchup...</div>';
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/predict/custom`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                home_team: homeTeam,
                home_year: homeYear,
                away_team: awayTeam,
                away_year: awayYear,
                neutral_site: false
            })
        });
        
        const data = await response.json();
        
        if (data.success && data.prediction) {
            displayCustomResult(data.prediction);
        } else {
            customResultContainer.innerHTML = `
                <div class="error-message">
                    <h3>Prediction Error</h3>
                    <p>${data.error || 'Unable to generate prediction'}</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error predicting game:', error);
        customResultContainer.innerHTML = `
            <div class="error-message">
                <h3>Connection Error</h3>
                <p>Please make sure the prediction server is running.</p>
            </div>
        `;
    } finally {
        predictCustomBtn.disabled = false;
        predictCustomBtn.textContent = 'Predict Game';
    }
}

// display the custom game prediction result
function displayCustomResult(prediction) {
    const home = prediction.home_team;
    const away = prediction.away_team;
    const pred = prediction.prediction;
    
    // Get team ratings (default to N/A if not available)
    const homeRating = home.rating ? home.rating.toFixed(1) : 'N/A';
    const awayRating = away.rating ? away.rating.toFixed(1) : 'N/A';
    const homePointDiff = home.point_diff ? (home.point_diff > 0 ? '+' : '') + home.point_diff.toFixed(1) : 'N/A';
    const awayPointDiff = away.point_diff ? (away.point_diff > 0 ? '+' : '') + away.point_diff.toFixed(1) : 'N/A';
    
    customResultContainer.innerHTML = `
        <div class="custom-result">
            <div class="custom-result-header">
                <h3>Prediction Result</h3>
            </div>
            
            <div class="custom-result-matchup">
                <div class="result-team">
                    <img src="https://a.espncdn.com/i/teamlogos/nfl/500/${home.abbreviation.toLowerCase()}.png" 
                         alt="${home.abbreviation}" 
                         style="width: 50px; height: 50px; margin-bottom: 0.5rem;"
                         onerror="this.style.display='none'">
                    <div class="result-team-name">${home.name}</div>
                    <div class="result-team-year">${home.year} Season</div>
                    <div class="result-team-record">${home.record} (${home.win_pct}%)</div>
                    <div class="result-team-rating">
                        <span class="rating-label">Power Rating:</span> 
                        <span class="rating-value ${parseFloat(homeRating) >= 0 ? 'positive' : 'negative'}">${homeRating}</span>
                    </div>
                    <div class="result-team-diff">Point Diff: ${homePointDiff}/game</div>
                </div>
                
                <div class="result-vs">VS</div>
                
                <div class="result-team">
                    <img src="https://a.espncdn.com/i/teamlogos/nfl/500/${away.abbreviation.toLowerCase()}.png" 
                         alt="${away.abbreviation}" 
                         style="width: 50px; height: 50px; margin-bottom: 0.5rem;"
                         onerror="this.style.display='none'">
                    <div class="result-team-name">${away.name}</div>
                    <div class="result-team-year">${away.year} Season</div>
                    <div class="result-team-record">${away.record} (${away.win_pct}%)</div>
                    <div class="result-team-rating">
                        <span class="rating-label">Power Rating:</span> 
                        <span class="rating-value ${parseFloat(awayRating) >= 0 ? 'positive' : 'negative'}">${awayRating}</span>
                    </div>
                    <div class="result-team-diff">Point Diff: ${awayPointDiff}/game</div>
                </div>
            </div>
            
            <div class="custom-result-prediction">
                <div class="prediction-winner-label">Predicted Winner</div>
                <div class="prediction-winner-name">${pred.winner}</div>
                <div class="prediction-details">
                    <div class="prediction-detail">
                        <div class="prediction-detail-label">Win Probability</div>
                        <div class="prediction-detail-value confidence-${pred.confidence >= 70 ? 'high' : pred.confidence >= 55 ? 'medium' : 'low'}">${pred.confidence}%</div>
                    </div>
                    <div class="prediction-detail">
                        <div class="prediction-detail-label">Predicted Score</div>
                        <div class="prediction-detail-value">${pred.predicted_score}</div>
                    </div>
                    <div class="prediction-detail">
                        <div class="prediction-detail-label">Spread</div>
                        <div class="prediction-detail-value">${pred.spread || 'N/A'}</div>
                    </div>
                    ${pred.neutral_site ? `
                    <div class="prediction-detail">
                        <div class="prediction-detail-label">Venue</div>
                        <div class="prediction-detail-value">Neutral Site</div>
                    </div>
                    ` : `
                    <div class="prediction-detail">
                        <div class="prediction-detail-label">Home Advantage</div>
                        <div class="prediction-detail-value">+2.5 pts</div>
                    </div>
                    `}
                </div>
            </div>
            
            ${pred.analysis ? `
            <div class="custom-result-analysis">
                <h4>Matchup Analysis</h4>
                <p>${pred.analysis}</p>
            </div>
            ` : ''}
            
            ${(!home.data_found || !away.data_found) ? `
            <div class="data-disclaimer">
                * Some statistics are estimated due to limited historical data
            </div>
            ` : ''}
        </div>
    `;
}

// event listeners for custom game predictor
homeYearSelect.addEventListener('change', () => {
    loadTeamsForYear(homeYearSelect, homeTeamSelect, homeYearSelect.value);
    homeTeamPreview.innerHTML = '<div class="team-preview-empty">Select a team to see stats</div>';
});

awayYearSelect.addEventListener('change', () => {
    loadTeamsForYear(awayYearSelect, awayTeamSelect, awayYearSelect.value);
    awayTeamPreview.innerHTML = '<div class="team-preview-empty">Select a team to see stats</div>';
});

homeTeamSelect.addEventListener('change', () => {
    loadTeamPreview(homeTeamSelect.value, homeYearSelect.value, homeTeamPreview);
});

awayTeamSelect.addEventListener('change', () => {
    loadTeamPreview(awayTeamSelect.value, awayYearSelect.value, awayTeamPreview);
});

predictCustomBtn.addEventListener('click', predictCustomGame);

// ========== NBA PREDICTOR FUNCTIONS ==========

// load nba games when button is clicked
if (loadNBAGamesBtn) {
    loadNBAGamesBtn.addEventListener('click', loadNBAGames);
}

async function loadNBAGames() {
    // show loading spinner while we wait
    nbaGamesContainer.innerHTML = '<div class="loading"><div class="spinner"></div>Loading NBA Games...</div>';

    try {
        // figure out which date they want
        const selection = nbaDateSelect.value;
        let url = `${API_BASE_URL}/api/nba/games`;
        
        // calculate date based on selection
        const today = new Date();
        let dateStr = '';
        
        if (selection === 'today') {
            dateStr = formatDate(today);
        } else if (selection === 'tomorrow') {
            const tomorrow = new Date(today);
            tomorrow.setDate(tomorrow.getDate() + 1);
            dateStr = formatDate(tomorrow);
        } else if (selection === 'yesterday') {
            const yesterday = new Date(today);
            yesterday.setDate(yesterday.getDate() - 1);
            dateStr = formatDate(yesterday);
        }
        
        if (dateStr) {
            url += `?date=${dateStr}`;
        }
        
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error('Could not load NBA games');
        }
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error || 'Failed to load NBA games');
        }
        
        nbaGamesContainer.innerHTML = '';
        
        // show each game
        if (data.games && data.games.length > 0) {
            // initialize score tracking for animations
            previousNBAScores = {};
            data.games.forEach(game => {
                const liveData = game.live_data || {};
                previousNBAScores[game.game_id] = {
                    home: liveData.home_score || 0,
                    away: liveData.away_score || 0
                };
            });
            
            data.games.forEach((game, index) => {
                const gameCard = createNBAGameCard(game, index + 1);
                nbaGamesContainer.appendChild(gameCard);
            });
            
            // if today and any games are live, auto-refresh every 5 seconds
            const hasLiveGames = data.games.some(g => g.live_data && g.live_data.is_live);
            if (selection === 'today' && hasLiveGames) {
                const liveMsg = document.createElement('div');
                liveMsg.className = 'live-refresh-msg';
                liveMsg.innerHTML = ' LIVE - Predictions updating every 5 seconds';
                nbaGamesContainer.insertBefore(liveMsg, nbaGamesContainer.firstChild);
                startLiveRefresh('nba');
            } else {
                stopLiveRefresh('nba');
            }
        } else {
            nbaGamesContainer.innerHTML = '<div class="no-games">No NBA games available for this date.</div>';
            stopLiveRefresh('nba');
        }
        
    } catch (error) {
        console.error('Error loading NBA games:', error);
        nbaGamesContainer.innerHTML = `
            <div class="error-message">
                <h3>Unable to Load NBA Games</h3>
                <p>Please make sure the prediction server is running and try again.</p>
            </div>
        `;
        stopLiveRefresh('nba');
    }
}

// quiet reload for NBA without loading spinner
async function loadNBAGamesQuiet() {
    try {
        const today = new Date();
        const dateStr = formatDate(today);
        const response = await fetch(`${API_BASE_URL}/api/nba/games?date=${dateStr}`);
        if (!response.ok) return;

        const data = await response.json();
        if (!data.success || !data.games) return;

        const hasLiveGames = data.games.some(g => g.live_data && g.live_data.is_live);
        if (!hasLiveGames) {
            stopLiveRefresh('nba');
        }

        // check for score changes before rebuilding
        const scoreChanges = {};
        data.games.forEach(game => {
            const gameId = game.game_id;
            const liveData = game.live_data || {};
            const homeScore = liveData.home_score || 0;
            const awayScore = liveData.away_score || 0;
            
            if (previousNBAScores[gameId]) {
                scoreChanges[gameId] = {
                    homeIncreased: homeScore > previousNBAScores[gameId].home,
                    awayIncreased: awayScore > previousNBAScores[gameId].away
                };
            }
            previousNBAScores[gameId] = { home: homeScore, away: awayScore };
        });

        const existingMsg = nbaGamesContainer.querySelector('.live-refresh-msg');
        nbaGamesContainer.innerHTML = '';
        if (existingMsg) nbaGamesContainer.appendChild(existingMsg);

        data.games.forEach((game, index) => {
            const gameCard = createNBAGameCard(game, index + 1, scoreChanges[game.game_id]);
            nbaGamesContainer.appendChild(gameCard);
        });
    } catch (error) {
        console.error('Error refreshing NBA games:', error);
    }
}

// format date as YYYYMMDD for espn api
function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}${month}${day}`;
}

// builds the html for each nba game card
function createNBAGameCard(game, gameNumber, scoreChanges = null) {
    const card = document.createElement('div');
    card.className = 'game-card nba-game-card';
    
    // check for live data
    const liveData = game.live_data || {};
    const isLive = liveData.is_live || false;
    const isFinal = liveData.is_final || false;
    
    // check for score animations
    const homeScoreClass = scoreChanges?.homeIncreased ? 'score score-increased' : 'score';
    const awayScoreClass = scoreChanges?.awayIncreased ? 'score score-increased' : 'score';

    // make the date look nice
    let dateStr = '';
    if (game.game_date) {
        const date = new Date(game.game_date);
        dateStr = date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
    }

    // their records and streaks
    let formInfo = '';
    if (game.analysis) {
        const homeForm = game.analysis.home_form || {};
        const awayForm = game.analysis.away_form || {};
        const homeRecord = `${homeForm.wins || 0}W-${homeForm.losses || 0}L`;
        const awayRecord = `${awayForm.wins || 0}W-${awayForm.losses || 0}L`;
        
        formInfo = `<div class="form-info">
            <small>Season Record - ${game.home_team}: ${homeRecord} | ${game.away_team}: ${awayRecord}</small>
        </div>`;
    }
    
    // build live score display
    let liveScoreDisplay = '';
    let statusBadge = '';
    let liveProbDisplay = '';
    
    if (isLive) {
        statusBadge = '<div class="status-badge live-badge">LIVE</div>';
        liveScoreDisplay = `
            <div class="live-score">
                <span class="${homeScoreClass}">${liveData.home_score || 0}</span>
                <span class="score-separator">-</span>
                <span class="${awayScoreClass}">${liveData.away_score || 0}</span>
            </div>
            <div class="game-clock">Q${liveData.period || 1} - ${liveData.clock || '12:00'}</div>
        `;
        liveProbDisplay = `
            <div class="live-probability">
                <div class="live-prob-label">Live Win Probability</div>
                <div class="live-prob-bar">
                    <div class="live-prob-fill home" style="width: ${liveData.live_probability || 50}%"></div>
                </div>
                <div class="live-prob-values">
                    <span>${game.home_team}: ${liveData.live_probability || 50}%</span>
                    <span>${game.away_team}: ${(100 - (liveData.live_probability || 50)).toFixed(1)}%</span>
                </div>
            </div>
        `;
    } else if (isFinal) {
        statusBadge = '<div class="status-badge final-badge">FINAL</div>';
        liveScoreDisplay = `
            <div class="final-score">
                <span class="score">${liveData.home_score || 0}</span>
                <span class="score-separator">-</span>
                <span class="score">${liveData.away_score || 0}</span>
            </div>
        `;
    }

    card.innerHTML = `
        <h3>Game ${gameNumber}</h3>
        <div class="badge-container">
            <div class="sport-badge nba-badge">NBA</div>
            ${statusBadge}
        </div>
        ${dateStr ? `<div class="game-date">${dateStr}</div>` : ''}
        ${game.venue ? `<div class="venue">${game.venue}</div>` : ''}
        <div class="matchup">
            <span class="team">${game.away_team}</span>
            <span class="vs">@</span>
            <span class="team">${game.home_team}</span>
        </div>
        ${liveScoreDisplay}
        ${liveProbDisplay}
        <div class="prediction nba-prediction">
            <div class="prediction-label">${isFinal ? 'Final Result' : 'Predicted Winner'}</div>
            <div class="predicted-winner">${game.predicted_winner}</div>
            <div class="confidence">${isLive ? 'Live' : ''} Confidence: ${game.confidence}%</div>
            ${!isLive && !isFinal ? `<div class="confidence">Predicted Score: ${game.predicted_score}</div>` : ''}
        </div>
        ${formInfo}
    `;
    
    // add live class for styling
    if (isLive) {
        card.classList.add('live-game');
    } else if (isFinal) {
        card.classList.add('final-game');
    }

    return card;
}
