document.addEventListener('DOMContentLoaded', () => {
    // --- STATE MANAGEMENT ---
    let state = {};
    let currentPlayer = null;
    let availablePlayerIds = [];

    // --- DOM ELEMENTS ---
    const loginScreen = document.getElementById('login-screen');
    const loginForm = document.getElementById('login-form');
    const passwordInput = document.getElementById('password');
    const loginError = document.getElementById('login-error');
    const appContainer = document.getElementById('app-container');
    const playerCard = document.getElementById('player-card');
    const nextBtn = document.getElementById('next-btn');
    const soldBtn = document.getElementById('sold-btn');
    const skipBtn = document.getElementById('skip-btn');
    const undoBtn = document.getElementById('undo-btn');
    const navTeams = document.getElementById('nav-teams');
    const teamsDashboard = document.getElementById('teams-dashboard');

    // Modal elements
    const sellModal = document.getElementById('sell-modal');
    const sellForm = document.getElementById('sell-form');
    const modalPlayerName = document.getElementById('modal-player-name');
    const sellPointsInput = document.getElementById('sell-points');
    const sellTeamSelect = document.getElementById('sell-team');
    const modalCancelBtn = document.getElementById('modal-cancel-btn');

    // --- CONFIGURATION ---
    const ADMIN_PASSWORD = "dcl"; // Your simple frontend password

    // --- LOGIN LOGIC ---
    loginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        if (passwordInput.value === ADMIN_PASSWORD) {
            loginScreen.classList.add('hidden');
            appContainer.classList.remove('hidden');
            fetchStateAndRender();
        } else {
            loginError.textContent = 'Incorrect Password.';
        }
    });

    // --- API COMMUNICATION ---
    async function fetchStateAndRender() {
        try {
            const response = await fetch('/api/state');
            state = await response.json();
            render();
        } catch (error) {
            console.error("Failed to fetch state:", error);
        }
    }

    // --- RENDER FUNCTIONS ---
    function render() {
        // Filter out sold players to find who is available
        const soldIds = new Set(state.sold_players);
        availablePlayerIds = state.unsold_player_ids.filter(id => !soldIds.has(id));

        renderNav();
        renderTeamsDashboard();
        renderPlayerCard();
        updateButtonStates();
    }

    function renderNav() {
        navTeams.innerHTML = '';
        for (const teamName in state.teams) {
            const link = document.createElement('a');
            link.className = 'nav-link';
            link.href = '#'; // In a more complex app, this would be a route like /teams/teamName
            link.textContent = teamName;
            navTeams.appendChild(link);
        }
    }

    function renderTeamsDashboard() {
        teamsDashboard.innerHTML = '<h2>Teams Dashboard</h2>';
        for (const teamName in state.teams) {
            const team = state.teams[teamName];
            const item = document.createElement('div');
            item.className = 'team-dashboard-item';
            item.innerHTML = `
                <span class="team-name">${teamName} (${team.players.length} players)</span>
                <span class="team-points">${team.points.toLocaleString()} PTS</span>
            `;
            teamsDashboard.appendChild(item);
        }
    }

    function renderPlayerCard() {
        if (currentPlayer) {
            let playerIconHTML;
            if (currentPlayer.photo && currentPlayer.photo.trim() !== '') {
                playerIconHTML = `<img src="/${currentPlayer.photo}" alt="${currentPlayer.player_name}" class="player-photo">`;
            } else {
                const initial = currentPlayer.player_name ? currentPlayer.player_name.charAt(0) : '?';
                playerIconHTML = `<div class="player-icon">${initial.toUpperCase()}</div>`;
            }
            playerCard.innerHTML = `
                ${playerIconHTML}
                <h2 id="player-name">${currentPlayer.player_name}</h2>
                <p id="father-name">S/O: ${currentPlayer.father_name}</p>
                <span id="player-id">ID: ${currentPlayer.id}</span>
            `;
        } else {
            playerCard.innerHTML = `<div class="card-placeholder"><p>Click "Next Player" to begin!</p></div>`;
            if (availablePlayerIds.length === 0) {
                 playerCard.innerHTML = `<div class="card-placeholder"><h2>Auction Completed!</h2></div>`;
            }
        }
    }
    
    function updateButtonStates() {
        soldBtn.disabled = !currentPlayer;
        skipBtn.disabled = !currentPlayer;
        nextBtn.disabled = !!currentPlayer || availablePlayerIds.length === 0;
        undoBtn.disabled = !state.last_transaction || state.last_transaction.type !== 'sell';
    }

    // --- EVENT HANDLERS ---
    nextBtn.addEventListener('click', () => {
        if (availablePlayerIds.length > 0) {
            const randomIndex = Math.floor(Math.random() * availablePlayerIds.length);
            const nextPlayerId = availablePlayerIds[randomIndex];
            currentPlayer = state.players[nextPlayerId];
            availablePlayerIds.splice(randomIndex, 1); // Remove from local available list
            render();
        }
    });

    skipBtn.addEventListener('click', () => {
        if(currentPlayer) {
            currentPlayer = null;
            render();
        }
    });
    
    soldBtn.addEventListener('click', () => {
        if (!currentPlayer) return;
        modalPlayerName.textContent = currentPlayer.player_name;
        sellTeamSelect.innerHTML = '<option value="" disabled selected>Select a Team</option>';
        for (const teamName in state.teams) {
            const option = document.createElement('option');
            option.value = teamName;
            option.textContent = `${teamName} (${state.teams[teamName].points.toLocaleString()} PTS)`;
            sellTeamSelect.appendChild(option);
        }
        sellModal.classList.remove('hidden');
    });

    modalCancelBtn.addEventListener('click', () => {
        sellModal.classList.add('hidden');
        sellForm.reset();
    });

    sellForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const points = parseInt(sellPointsInput.value, 10);
        const teamName = sellTeamSelect.value;
        const team = state.teams[teamName];

        if (points > team.points) {
            alert(`${teamName} does not have enough points!`);
            return;
        }

        const response = await fetch('/api/sell', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                playerId: currentPlayer.id,
                teamName: teamName,
                points: points
            })
        });

        if(response.ok) {
            currentPlayer = null;
            sellModal.classList.add('hidden');
            sellForm.reset();
            fetchStateAndRender();
        } else {
            alert("Failed to sell player.");
        }
    });
    
    undoBtn.addEventListener('click', async () => {
        const response = await fetch('/api/undo', { method: 'POST' });
        if(response.ok) {
            fetchStateAndRender();
        } else {
            alert("Nothing to undo.");
        }
    });
});