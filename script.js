

// grab the buttons and containers from the page
const loadGamesBtn = document.getElementById('loadGamesBtn');
const gamesContainer = document.getElementById('gamesContainer');
const weekSelect = document.getElementById('weekSelect');
const homeLink = document.getElementById('homeLink');
const customGameLink = document.getElementById('customGameLink');
const controlsDiv = document.querySelector('.controls');

// custom game elements
const customGameContainer = document.getElementById('customGameContainer');
const homeYearSelect = document.getElementById('homeYearSelect');
const homeTeamSelect = document.getElementById('homeTeamSelect');
const awayYearSelect = document.getElementById('awayYearSelect');
const awayTeamSelect = document.getElementById('awayTeamSelect');
const homeTeamPreview = document.getElementById('homeTeamPreview');
const awayTeamPreview = document.getElementById('awayTeamPreview');
const neutralSiteCheck = document.getElementById('neutralSiteCheck');
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

function showHomePage() {
    homeLink.classList.add('active');
    customGameLink.classList.remove('active');
    controlsDiv.style.display = 'flex';
    gamesContainer.style.display = 'grid';
    customGameContainer.style.display = 'none';
}

function showCustomGamePage() {
    customGameLink.classList.add('active');
    homeLink.classList.remove('active');
    controlsDiv.style.display = 'none';
    gamesContainer.style.display = 'none';
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
    }
}

// builds the html for each game card
function createGameCard(game, gameNumber) {
    const card = document.createElement('div');
    card.className = 'game-card';

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

    card.innerHTML = `
        <h3>Game ${gameNumber}</h3>
        ${weekInfo}
        ${dateStr ? `<div class="game-date">${dateStr}</div>` : ''}
        ${game.venue ? `<div class="venue">${game.venue}</div>` : ''}
        <div class="matchup">
            <span class="team">${game.away_team}</span>
            <span class="vs">@</span>
            <span class="team">${game.home_team}</span>
        </div>
        ${rookieIndicator ? `<div class="rookie-indicators">${rookieIndicator}</div>` : ''}
        ${injuryInfo}
        <div class="prediction">
            <div class="prediction-label">Predicted Winner</div>
            <div class="predicted-winner">${game.predicted_winner}</div>
            <div class="confidence">Confidence: ${game.confidence}%</div>
            <div class="confidence">Predicted Score: ${game.predicted_score}</div>
        </div>
        ${formInfo}
    `;

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
    const neutralSite = neutralSiteCheck.checked;
    
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
                neutral_site: neutralSite
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
