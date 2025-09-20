document.addEventListener('DOMContentLoaded', () => {
    let state = {};
    let currentPlayer = null;

    const ui = {
        playerSearch: document.getElementById('player-search'),
        searchResults: document.getElementById('search-results'),
        playerCard: document.getElementById('player-card'),
        auctionControls: document.getElementById('auction-controls'),
        nextBtn: document.getElementById('next-btn'),
        soldBtn: document.getElementById('sold-btn'),
        skipBtn: document.getElementById('skip-btn'),
        undoBtn: document.getElementById('undo-btn'),
        sellModal: document.getElementById('sell-modal'),
        sellForm: document.getElementById('sell-form'),
        modalPlayerName: document.getElementById('modal-player-name'),
        sellPointsInput: document.getElementById('sell-points'),
        sellTeamSelect: document.getElementById('sell-team'),
        modalCancelBtn: document.getElementById('modal-cancel-btn'),
    };

    async function apiCall(endpoint, method = 'GET', body = null) {
    const options = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) options.body = JSON.stringify(body);
    try {
        const response = await fetch(endpoint, options);
        // If the response is not OK, try to parse the JSON error message
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || `API call failed: ${response.statusText}`);
        }
        return response.json();
    } catch (error) {
        // Now the alert will show the specific message from the server
        alert(`Error: ${error.message}`);
        console.error(`Error with ${method} ${endpoint}:`, error);
        return null;
    }
}
    function render(newState) {
        if (!newState) return;
        state = newState;
        renderPlayerCard();
        updateButtonStates();
    }

    function renderWelcomeScreen() {
        const unsoldCount = state.unsold_player_ids.length;
        ui.playerCard.innerHTML = `
            <div class="welcome-screen">
                <h1>Welcome, Auctioneer</h1>
                <p>${unsoldCount > 0 ? `${unsoldCount} players remain.` : 'All players sold!'}</p>
                <p>Use the search bar or click "Next Random Player".</p>
            </div>`;
        ui.auctionControls.classList.remove('hidden');
        ui.nextBtn.disabled = unsoldCount === 0;
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

    async function handleNextPlayer() {
        const nextPlayerData = await apiCall('/api/next_player');
        currentPlayer = nextPlayerData;
        renderPlayerCard();
        updateButtonStates();
    }

    function handleSkipPlayer() {
        currentPlayer = null;
        renderPlayerCard();
        updateButtonStates();
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
        if (points < 0 || !teamName) return;

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

    async function handleSearch(e) {
        const query = e.target.value;
        if (query.length < 2) {
            ui.searchResults.innerHTML = '';
            ui.searchResults.classList.add('hidden');
            return;
        }
        const results = await apiCall(`/api/search_players?q=${query}`);
        ui.searchResults.innerHTML = '';
        if (results && results.length > 0) {
            results.forEach(player => {
                const item = document.createElement('div');
                item.className = 'search-result-item';
                item.textContent = `${player.player_name} (ID: ${player.id})`;
                item.dataset.playerId = player.id;
                ui.searchResults.appendChild(item);
            });
            ui.searchResults.classList.remove('hidden');
        } else {
            ui.searchResults.classList.add('hidden');
        }
    }
    
    function handleSearchResultClick(e) {
        if (e.target.classList.contains('search-result-item')) {
            const playerId = e.target.dataset.playerId;
            currentPlayer = state.players[playerId];
            ui.playerSearch.value = '';
            ui.searchResults.classList.add('hidden');
            renderPlayerCard();
            updateButtonStates();
        }
    }

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
    ui.playerSearch.addEventListener('input', handleSearch);
    ui.searchResults.addEventListener('click', handleSearchResultClick);

    initializeAuction();
});