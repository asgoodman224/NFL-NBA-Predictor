// NFL Teams data for generating fake predictions
const nflTeams = [
    'Buffalo Bills', 'Miami Dolphins', 'New England Patriots', 'New York Jets',
    'Baltimore Ravens', 'Cincinnati Bengals', 'Cleveland Browns', 'Pittsburgh Steelers',
    'Houston Texans', 'Indianapolis Colts', 'Jacksonville Jaguars', 'Tennessee Titans',
    'Denver Broncos', 'Kansas City Chiefs', 'Las Vegas Raiders', 'Los Angeles Chargers',
    'Dallas Cowboys', 'New York Giants', 'Philadelphia Eagles', 'Washington Commanders',
    'Chicago Bears', 'Detroit Lions', 'Green Bay Packers', 'Minnesota Vikings',
    'Atlanta Falcons', 'Carolina Panthers', 'New Orleans Saints', 'Tampa Bay Buccaneers',
    'Arizona Cardinals', 'Los Angeles Rams', 'San Francisco 49ers', 'Seattle Seahawks'
];

// Get DOM elements
const loadGamesBtn = document.getElementById('loadGamesBtn');
const gamesContainer = document.getElementById('gamesContainer');

// Event listener for Load Games button
loadGamesBtn.addEventListener('click', loadGames);

// Function to load and display games
function loadGames() {
    // Clear previous games
    gamesContainer.innerHTML = '<div class="loading">Loading games...</div>';

    // Simulate API delay
    setTimeout(() => {
        gamesContainer.innerHTML = '';
        
        // Generate dummy matchups
        const games = generateDummyGames(8);
        
        // Display each game
        games.forEach((game, index) => {
            const gameCard = createGameCard(game, index + 1);
            gamesContainer.appendChild(gameCard);
        });
    }, 800);
}

// Function to generate dummy games
function generateDummyGames(numGames) {
    const games = [];
    const usedTeams = new Set();

    for (let i = 0; i < numGames; i++) {
        let homeTeam, awayTeam;

        // Ensure no team plays twice in the same week
        do {
            homeTeam = nflTeams[Math.floor(Math.random() * nflTeams.length)];
        } while (usedTeams.has(homeTeam));
        usedTeams.add(homeTeam);

        do {
            awayTeam = nflTeams[Math.floor(Math.random() * nflTeams.length)];
        } while (usedTeams.has(awayTeam) || awayTeam === homeTeam);
        usedTeams.add(awayTeam);

        // Generate prediction
        const prediction = generatePrediction(homeTeam, awayTeam);

        games.push({
            homeTeam,
            awayTeam,
            prediction
        });
    }

    return games;
}

// Function to generate prediction for a game
function generatePrediction(homeTeam, awayTeam) {
    // Randomly select winner (with slight home advantage)
    const homeAdvantage = 0.55; // 55% chance for home team
    const predictedWinner = Math.random() < homeAdvantage ? homeTeam : awayTeam;
    
    // Generate confidence percentage
    const confidence = Math.floor(Math.random() * 30) + 60; // 60-90%
    
    // Generate score prediction
    const winnerScore = Math.floor(Math.random() * 21) + 20; // 20-40
    const loserScore = Math.floor(Math.random() * (winnerScore - 3)) + 10; // 10 to (winner-3)

    return {
        winner: predictedWinner,
        confidence: confidence,
        score: predictedWinner === homeTeam 
            ? `${winnerScore}-${loserScore}` 
            : `${loserScore}-${winnerScore}`
    };
}

// Function to create a game card element
function createGameCard(game, gameNumber) {
    const card = document.createElement('div');
    card.className = 'game-card';

    card.innerHTML = `
        <h3>Game ${gameNumber}</h3>
        <div class="matchup">
            <span class="team">${game.awayTeam}</span>
            <span class="vs">@</span>
            <span class="team">${game.homeTeam}</span>
        </div>
        <div class="prediction">
            <div class="prediction-label">Predicted Winner</div>
            <div class="predicted-winner">${game.prediction.winner}</div>
            <div class="confidence">Confidence: ${game.prediction.confidence}%</div>
            <div class="confidence">Predicted Score: ${game.prediction.score}</div>
        </div>
    `;

    return card;
}

// Optional: Load games on page load
// window.addEventListener('load', loadGames);
