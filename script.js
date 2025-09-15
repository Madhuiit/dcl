document.addEventListener('DOMContentLoaded', () => {
    // --- STATE MANAGEMENT ---
    let allPlayers = [];
    let unsoldPlayers = [];
    let soldPlayers = [];
    let currentPlayer = null;
    let lastAction = { type: null, player: null };

    // --- DOM ELEMENTS ---
    const loginScreen = document.getElementById('login-screen');
    const loginForm = document.getElementById('login-form');
    const passwordInput = document.getElementById('password');
    const loginError = document.getElementById('login-error');
    
    const appContainer = document.getElementById('app-container');
    const playerCard = document.getElementById('player-card');
    
    const nextBtn = document.getElementById('next-btn');
    const soldBtn = document.getElementById('sold-btn');
    const undoBtn = document.getElementById('undo-btn');

    const soldPlayersList = document.getElementById('sold-players-list');
    const unsoldPlayersList = document.getElementById('unsold-players-list');
    const soldCountEl = document.getElementById('sold-count');
    const unsoldCountEl = document.getElementById('unsold-count');
    
    // --- CONFIGURATION ---
    const ADMIN_PASSWORD = "dcl"; // Set your simple admin password here

    // --- LOGIN LOGIC ---
    loginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        if (passwordInput.value === ADMIN_PASSWORD) {
            loginScreen.classList.add('hidden');
            appContainer.classList.remove('hidden');
            initAuction();
        } else {
            loginError.textContent = 'Incorrect Password. Please try again.';
            passwordInput.value = '';
        }
    });

    // --- AUCTION INITIALIZATION ---
    async function initAuction() {
        try {
            const response = await fetch('players.json');
            allPlayers = await response.json();
            // NEW: All players start in the 'unsold' list
            unsoldPlayers = [...allPlayers];
            updateUI();
        } catch (error) {
            console.error("Could not load player data:", error);
            playerCard.innerHTML = `<div class="card-placeholder"><p style="color:red;">Error: Could not load players.json.</p></div>`;
        }
    }
    
    // --- CORE AUCTION FUNCTIONS ---
    function getNextPlayer() {
        if (unsoldPlayers.length === 0) {
            showAuctionComplete();
            return;
        }
        // If a player is already on screen, put them back in the unsold list
        if (currentPlayer) {
            unsoldPlayers.push(currentPlayer);
        }

        const randomIndex = Math.floor(Math.random() * unsoldPlayers.length);
        currentPlayer = unsoldPlayers.splice(randomIndex, 1)[0];
        
        lastAction = { type: 'next', player: currentPlayer }; // For undoing a 'next' click
        updateUI();
        displayPlayer(currentPlayer);
    }

    function sellPlayer() {
        if (!currentPlayer) return;
        soldPlayers.push(currentPlayer);
        lastAction = { type: 'sell', player: currentPlayer };
        currentPlayer = null;
        updateUI();
    }
    
    function reAuctionPlayer(playerId) {
        // If a player is already on the card, put them back into the unsold list first
        if (currentPlayer) {
            unsoldPlayers.push(currentPlayer);
            currentPlayer = null;
        }

        const playerIndex = soldPlayers.findIndex(p => p.id === playerId);
        if (playerIndex > -1) {
            const playerToReAuction = soldPlayers.splice(playerIndex, 1)[0];
            currentPlayer = playerToReAuction;
            lastAction = { type: 'reauction', player: playerToReAuction };
            updateUI();
            displayPlayer(currentPlayer);
        }
    }

    function undoLastAction() {
        if (!lastAction.player) return;

        if (lastAction.type === 'sell') {
            const playerToUndo = soldPlayers.pop();
            unsoldPlayers.push(playerToUndo);
        }
        
        // Clear the current player if the undone player was the one on screen
        if (currentPlayer && currentPlayer.id === lastAction.player.id) {
            currentPlayer = null;
        }
        
        lastAction = { type: null, player: null }; // Clear last action
        updateUI();
    }

    // --- UI UPDATE FUNCTIONS ---
    function updateUI() {
        updateLists();
        updateButtonStates();
        if (!currentPlayer) {
            displayInitialMessage();
        }
    }

    function displayPlayer(player) {
        const playerInitial = player.player_name.charAt(0);
        playerCard.innerHTML = `
            <div class="player-icon">${playerInitial}</div>
            <h2 id="player-name">${player.player_name}</h2>
            <p id="father-name">S/O: ${player.father_name}</p>
            <span id="player-id">ID: ${player.id}</span>
        `;
    }

    function displayInitialMessage() {
         playerCard.innerHTML = `<div class="card-placeholder"><p>Click "Next Player" to draw from the UNSOLD list!</p></div>`;
    }
    
    function showAuctionComplete() {
        playerCard.innerHTML = `<div class="card-placeholder"><h2>Auction Completed!</h2><p>All players have been processed.</p></div>`;
        currentPlayer = null;
        updateButtonStates();
    }

    function updateLists() {
        soldPlayersList.innerHTML = '';
        unsoldPlayersList.innerHTML = '';

        soldPlayers.forEach(player => {
            const item = document.createElement('div');
            item.className = 'list-item list-item-sold';
            item.dataset.id = player.id; // Add data-id for click identification
            item.innerHTML = `
                <span class="player-info">${player.player_name}</span>
                <i class="fa-solid fa-retweet re-auction-icon" title="Re-Auction This Player"></i>
                <span class="player-id">ID: ${player.id}</span>
            `;
            soldPlayersList.appendChild(item);
        });

        unsoldPlayers.forEach(player => {
            const item = document.createElement('div');
            item.className = 'list-item list-item-unsold';
            item.innerHTML = `
                <span class="player-info">${player.player_name}</span>
                <span class="player-id">ID: ${player.id}</span>
            `;
            unsoldPlayersList.appendChild(item);
        });
        
        // Update counts
        soldCountEl.textContent = `(${soldPlayers.length})`;
        unsoldCountEl.textContent = `(${unsoldPlayers.length})`;
    }

    function updateButtonStates() {
        soldBtn.disabled = !currentPlayer;
        nextBtn.disabled = !!currentPlayer || unsoldPlayers.length === 0;
        undoBtn.disabled = lastAction.type !== 'sell';
    }

    // --- EVENT LISTENERS ---
    nextBtn.addEventListener('click', getNextPlayer);
    soldBtn.addEventListener('click', sellPlayer);
    undoBtn.addEventListener('click', undoLastAction);
    
    // Event listener for re-auctioning a sold player
    soldPlayersList.addEventListener('click', (e) => {
        const listItem = e.target.closest('.list-item-sold');
        if (listItem) {
            const playerId = parseInt(listItem.dataset.id, 10);
            reAuctionPlayer(playerId);
        }
    });
});