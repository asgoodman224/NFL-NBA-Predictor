

// grab the buttons and containers from the page
const loadGamesBtn = document.getElementById('loadGamesBtn');
const gamesContainer = document.getElementById('gamesContainer');
const weekSelect = document.getElementById('weekSelect');

// where the server is running
const API_BASE_URL = 'http://localhost:5000';

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
