document.addEventListener('DOMContentLoaded', () => {
    // --- GLOBAL STATE ---
    let state = {};
    let currentPlayer = null;

    // --- DOM ELEMENT MAPPING ---
    const ui = {
        playerCard: document.getElementById('player-card'),
        auctionControls: document.getElementById('auction-controls'),
        nextBtn: document.getElementById('next-btn'),
        soldBtn: document.getElementById('sold-btn'),
        skipBtn: document.getElementById('skip-btn'),
        undoBtn: document.getElementById('undo-btn'),
        teamsDashboard: document.getElementById('teams-dashboard'),
        sellModal: document.getElementById('sell-modal'),
        sellForm: document.getElementById('sell-form'),
        modalPlayerName: document.getElementById('modal-player-name'),
        sellPointsInput: document.getElementById('sell-points'),
        sellTeamSelect: document.getElementById('sell-team'),
        modalCancelBtn: document.getElementById('modal-cancel-btn'),
    };

    // --- API FUNCTIONS ---
    async function apiCall(endpoint, method = 'GET', body = null) {
        const options = { method, headers: { 'Content-Type': 'application/json' } };
        if (body) options.body = JSON.stringify(body);
        try {
            const response = await fetch(endpoint, options);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `API call failed: ${response.statusText}`);
            }
            return response.json();
        } catch (error) {
            console.error(`Error with ${method} ${endpoint}:`, error);
            alert(`An error occurred: ${error.message}`);
            return null;
        }
    }

    // --- RENDER FUNCTIONS ---
    function render(newState) {
        if (!newState) return;
        state = newState;
        renderTeamsDashboard();
        renderPlayerCard();
        updateButtonStates();
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
        const unsoldCount = state.unsold_player_ids.length;
        ui.playerCard.innerHTML = `
            <div class="welcome-screen">
                <h1>Welcome, Auctioneer</h1>
                <p>${unsoldCount > 0 ? `${unsoldCount} players are ready.` : 'All players have been sold!'}</p>
                <button id="start-auction-btn">Begin Auction</button>
            </div>`;
        document.getElementById('start-auction-btn').addEventListener('click', () => {
            ui.auctionControls.classList.remove('hidden');
            handleNextPlayer();
        });
        ui.auctionControls.classList.add('hidden');
    }

    function renderPlayerCard() {
        if (currentPlayer) {
            const photoPath = currentPlayer.photo && currentPlayer.photo.trim() ? `/${currentPlayer.photo}` : null;
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
            renderWelcomeScreen();
        }
    }
    
    function updateButtonStates() {
        ui.soldBtn.disabled = !currentPlayer;
        ui.skipBtn.disabled = !currentPlayer;
        ui.nextBtn.disabled = !!currentPlayer;
        ui.undoBtn.disabled = !state.last_transaction;
    }

    // --- EVENT HANDLERS ---
    async function handleNextPlayer() {
        const nextPlayerData = await apiCall('/api/next_player');
        currentPlayer = nextPlayerData; // Will be null if no players left
        renderPlayerCard();
        updateButtonStates();
    }

    function handleSkipPlayer() {
        // Skipping simply means fetching the next player
        handleNextPlayer();
    }

    function handleOpenSellModal() {
        if (!currentPlayer) return;
        ui.modalPlayerName.textContent = currentPlayer.player_name;
        ui.sellTeamSelect.innerHTML = '<option value="" disabled selected>Select a Team</option>';
        Object.keys(state.teams).forEach(teamName => {
            const team = state.teams[teamName];
            const option = document.createElement('option');
            option.value = teamName;
            option.textContent = `${teamName} (${team.points.toLocaleString()} PTS Remaining)`;
            ui.sellTeamSelect.appendChild(option);
        });
        ui.sellModal.classList.remove('hidden');
    }

    async function handleConfirmSale(e) {
        e.preventDefault();
        const points = parseInt(ui.sellPointsInput.value, 10);
        const teamName = ui.sellTeamSelect.value;
        if (points < 0 || !teamName) {
            alert("Please enter a valid point value and select a team."); return;
        }

        const team = state.teams[teamName];
        if (points > team.points) {
            alert(`${teamName} does not have enough points!`); return;
        }

        const response = await apiCall('/api/sell', 'POST', { playerId: currentPlayer.id, teamName, points });
        if (response) {
            currentPlayer = null;
            ui.sellModal.classList.add('hidden');
            ui.sellForm.reset();
            render(response.state);
        }
    }
    
    async function handleUndo() {
        const response = await apiCall('/api/undo', 'POST');
        if (response) {
            currentPlayer = null;
            render(response.state);
        }
    }
    
    // --- INITIALIZATION ---
    async function initializeAuction() {
        const initialState = await apiCall('/api/state');
        render(initialState);
    }

    ui.nextBtn.addEventListener('click', handleNextPlayer);
    ui.skipBtn.addEventListener('click', handleSkipPlayer);
    ui.soldBtn.addEventListener('click', handleOpenSellModal);
    ui.modalCancelBtn.addEventListener('click', () => ui.sellModal.classList.add('hidden'));
    ui.sellForm.addEventListener('submit', handleConfirmSale);
    ui.undoBtn.addEventListener('click', handleUndo);

    initializeAuction(); // Start the app
});