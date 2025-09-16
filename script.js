document.addEventListener('DOMContentLoaded', () => {
    // --- GLOBAL STATE ---
    let state = {};
    let currentPlayer = null;
    let availablePlayerIds = [];
    let auctionPhase = 'login'; // 'login', 'welcome', 'live'

    // --- DOM ELEMENT MAPPING ---
    const ui = {
        loginScreen: document.getElementById('login-screen'),
        appContainer: document.getElementById('app-container'),
        loginForm: document.getElementById('login-form'),
        passwordInput: document.getElementById('password'),
        loginError: document.getElementById('login-error'),
        playerCard: document.getElementById('player-card'),
        auctionControls: document.getElementById('auction-controls'),
        nextBtn: document.getElementById('next-btn'),
        soldBtn: document.getElementById('sold-btn'),
        skipBtn: document.getElementById('skip-btn'),
        undoBtn: document.getElementById('undo-btn'),
        navTeams: document.getElementById('nav-teams'),
        teamsDashboard: document.getElementById('teams-dashboard'),
        resetBtn: document.getElementById('reset-btn'),
        sellModal: document.getElementById('sell-modal'),
        sellForm: document.getElementById('sell-form'),
        modalPlayerName: document.getElementById('modal-player-name'),
        sellPointsInput: document.getElementById('sell-points'),
        sellTeamSelect: document.getElementById('sell-team'),
        modalCancelBtn: document.getElementById('modal-cancel-btn'),
    };

    const ADMIN_PASSWORD = "dcl";

    // --- API FUNCTIONS ---
    async function apiCall(endpoint, method = 'GET', body = null) {
        const options = { method, headers: { 'Content-Type': 'application/json' } };
        if (body) options.body = JSON.stringify(body);
        try {
            const response = await fetch(endpoint, options);
            if (!response.ok) throw new Error(`API call failed: ${response.statusText}`);
            return await response.json();
        } catch (error) {
            console.error(`Error with ${method} ${endpoint}:`, error);
            alert(`An error occurred: ${error.message}`);
            return null;
        }
    }
    
    // --- MAIN RENDER CONTROLLER ---
    function render() {
        if (auctionPhase === 'login') {
            ui.loginScreen.classList.remove('hidden');
            ui.appContainer.classList.add('hidden');
            return;
        }

        // If not login, show the app
        ui.loginScreen.classList.add('hidden');
        ui.appContainer.classList.remove('hidden');

        // Update parts of the app that are always visible
        renderNav();
        renderTeamsDashboard();

        // Update the main panel based on the phase
        if (auctionPhase === 'welcome') {
            renderWelcomeScreen();
            ui.auctionControls.classList.add('hidden');
        } else if (auctionPhase === 'live') {
            renderPlayerCard();
            ui.auctionControls.classList.remove('hidden');
        }

        updateButtonStates();
    }
    
    // --- COMPONENT RENDER FUNCTIONS ---
    function renderNav() {
        ui.navTeams.innerHTML = '';
        Object.keys(state.teams).forEach(teamName => {
            const link = document.createElement('a');
            link.className = 'nav-link';
            link.href = '#';
            link.textContent = teamName;
            ui.navTeams.appendChild(link);
        });
    }

    function renderTeamsDashboard() {
        ui.teamsDashboard.innerHTML = '<h2>Teams Dashboard</h2>';
        Object.keys(state.teams).sort().forEach(teamName => {
            const team = state.teams[teamName];
            const item = document.createElement('div');
            item.className = 'team-dashboard-item';
            item.innerHTML = `<span class="team-name">${teamName} (${team.players.length})</span><span class="team-points">${team.points.toLocaleString()}</span>`;
            ui.teamsDashboard.appendChild(item);
        });
    }

    function renderWelcomeScreen() {
        ui.playerCard.innerHTML = `
            <div class="welcome-screen">
                <h1>Welcome to the DCL Auction</h1>
                <p>${availablePlayerIds.length} players are ready to be auctioned.</p>
                <button id="start-auction-btn">Start Auction</button>
            </div>`;
        document.getElementById('start-auction-btn').addEventListener('click', () => {
            auctionPhase = 'live';
            render();
        });
    }

    function renderPlayerCard() {
        if (currentPlayer) {
            const photoPath = currentPlayer.photo && currentPlayer.photo.trim() !== '' ? `/${currentPlayer.photo}` : null;
            const initial = currentPlayer.player_name ? currentPlayer.player_name.charAt(0).toUpperCase() : '?';
            const iconHTML = photoPath
                ? `<img src="${photoPath}" alt="${currentPlayer.player_name}" class="player-photo">`
                : `<div class="player-icon">${initial}</div>`;

            ui.playerCard.innerHTML = `
                ${iconHTML}
                <h2 id="player-name">${currentPlayer.player_name}</h2>
                <p id="father-name">S/O: ${currentPlayer.father_name}</p>
                <span id="player-id">ID: ${currentPlayer.id}</span>`;
        } else {
            ui.playerCard.innerHTML = `<div class="card-placeholder">
                <p>${availablePlayerIds.length > 0 ? 'Click "Next Player" for the next round!' : 'All players have been sold!'}</p>
            </div>`;
        }
    }
    
    function updateButtonStates() {
        if (auctionPhase !== 'live') return;
        ui.soldBtn.disabled = !currentPlayer;
        ui.skipBtn.disabled = !currentPlayer;
        ui.nextBtn.disabled = !!currentPlayer || availablePlayerIds.length === 0;
        ui.undoBtn.disabled = !state.last_transaction || state.last_transaction.type !== 'sell';
    }

    // --- EVENT HANDLERS ---
    async function handleLogin(e) {
        e.preventDefault();
        if (ui.passwordInput.value === ADMIN_PASSWORD) {
            auctionPhase = 'welcome';
            const initialData = await apiCall('/api/state');
            if (initialData) {
                state = initialData;
                availablePlayerIds = [...state.unsold_player_ids];
                render();
            }
        } else {
            ui.loginError.textContent = 'Incorrect Password.';
        }
    }
    
    function handleNextPlayer() {
        if (availablePlayerIds.length > 0) {
            const randomIndex = Math.floor(Math.random() * availablePlayerIds.length);
            const nextPlayerId = availablePlayerIds.splice(randomIndex, 1)[0];
            currentPlayer = state.players[String(nextPlayerId)];
            render();
        }
    }

    function handleSkipPlayer() {
        if (currentPlayer) {
            availablePlayerIds.push(currentPlayer.id);
            currentPlayer = null;
            render();
        }
    }

    function handleOpenSellModal() {
        if (!currentPlayer) return;
        ui.modalPlayerName.textContent = currentPlayer.player_name;
        ui.sellTeamSelect.innerHTML = '<option value="" disabled selected>Select a Team</option>';
        Object.keys(state.teams).forEach(teamName => {
            const team = state.teams[teamName];
            const option = document.createElement('option');
            option.value = teamName;
            option.textContent = `${teamName} (${team.points.toLocaleString()} PTS)`;
            ui.sellTeamSelect.appendChild(option);
        });
        ui.sellModal.classList.remove('hidden');
    }

    async function handleConfirmSale(e) {
        e.preventDefault();
        const points = parseInt(ui.sellPointsInput.value, 10);
        const teamName = ui.sellTeamSelect.value;
        const team = state.teams[teamName];

        if (points < 0) {
            alert("Points cannot be negative."); return;
        }
        if (points > team.points) {
            alert(`${teamName} does not have enough points!`); return;
        }

        const newState = await apiCall('/api/sell', 'POST', {
            playerId: currentPlayer.id, teamName, points
        });
        if (newState) {
            state = newState;
            currentPlayer = null;
            ui.sellModal.classList.add('hidden');
            ui.sellForm.reset();
            render();
        }
    }
    
    async function handleUndo() {
        const newState = await apiCall('/api/undo', 'POST');
        if (newState) {
            state = newState;
            currentPlayer = null; // Clear the card after undo
            availablePlayerIds = [...state.unsold_player_ids];
            render();
        }
    }

    async function handleReset() {
        if (confirm("ARE YOU SURE you want to reset the entire auction? All progress will be lost!")) {
            const newState = await apiCall('/api/reset', 'POST');
            if (newState) {
                state = newState;
                currentPlayer = null;
                auctionPhase = 'welcome';
                availablePlayerIds = [...state.unsold_player_ids];
                render();
            }
        }
    }
    
    // --- INITIAL SETUP & EVENT LISTENERS ---
    ui.loginForm.addEventListener('submit', handleLogin);
    ui.nextBtn.addEventListener('click', handleNextPlayer);
    ui.skipBtn.addEventListener('click', handleSkipPlayer);
    ui.soldBtn.addEventListener('click', handleOpenSellModal);
    ui.modalCancelBtn.addEventListener('click', () => ui.sellModal.classList.add('hidden'));
    ui.sellForm.addEventListener('submit', handleConfirmSale);
    ui.undoBtn.addEventListener('click', handleUndo);
    ui.resetBtn.addEventListener('click', handleReset);

    render(); // Initial render for the login screen
});