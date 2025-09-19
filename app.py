import os
import json
from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for, session
import pandas as pd
import io
# NEW: Import the Google Cloud Firestore library
from google.cloud import firestore

app = Flask(__name__)
app.secret_key = 'a_very_strong_secret_key_that_you_should_change'

# --- CONFIGURATION ---
# NEW: Initialize Firestore client. It will automatically use the project's credentials on Cloud Run.
db = firestore.Client()
STATE_DOC_REF = db.collection('auction').document('state') # Our database "file"

PLAYERS_FILE = 'players.json'
ADMIN_PASSWORD = "dcl"
INITIAL_TEAM_POINTS = 110000
TEAMS = [
    "Naman Communication", "bhagat sing club", "Yaar Albela", "Maa Santoshi", "Ramdevariya",
    "Maa Karni club", "Lemda Eleven", "Risingin Star", "Pareek Patrolium",
    "Rajasthan Royal", "Baba Blastar", "khetarpal Eleven", "Zehrili Nagin"
]
auction_state = {}

# --- STATE MANAGEMENT (NOW WITH FIRESTORE) ---
def initialize_state():
    """Build a fresh state from players.json and save it to Firestore."""
    global auction_state
    with open(PLAYERS_FILE, 'r', encoding='utf-8') as f:
        players = json.load(f)
    
    new_state = {
        "players": {str(p['id']): p for p in players},
        "teams": {name: {"points": INITIAL_TEAM_POINTS, "players": []} for name in TEAMS},
        "unsold_player_ids": [p['id'] for p in players],
        "last_transaction": None
    }
    STATE_DOC_REF.set(new_state) # Save to Firestore
    auction_state = new_state
    print("SUCCESS: New auction state INITIALIZED in Firestore.")

def load_state():
    """Load the auction state from Firestore."""
    global auction_state
    try:
        state_doc = STATE_DOC_REF.get()
        if state_doc.exists:
            auction_state = state_doc.to_dict()
            print("SUCCESS: Auction state LOADED from Firestore.")
        else:
            # If the document doesn't exist, it's the very first run
            initialize_state()
    except Exception as e:
        print(f"CRITICAL ERROR loading state from Firestore: {e}. Re-initializing.")
        initialize_state()

def save_state():
    """Save the current auction state to Firestore."""
    STATE_DOC_REF.set(auction_state)

# This function runs before every request to ensure the state is loaded into memory.
@app.before_request
def check_and_load_state():
    if not auction_state and request.endpoint not in ['static']:
        print("In-memory state is empty, loading from Firestore...")
        load_state()

# --- ROUTES AND API (No major changes needed, they use the global auction_state) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('auction'))
        else:
            return render_template('login.html', error="Incorrect Password")
    return render_template('login.html')

# (All your other routes like /logout, /auction, /teams, and all /api/... routes remain the same)
# ... [The rest of your app.py code for routes remains unchanged] ...
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))
@app.route('/')
def home():
    if not session.get('logged_in'): return redirect(url_for('login'))
    return redirect(url_for('auction'))
@app.route('/auction')
def auction():
    if not session.get('logged_in'): return redirect(url_for('login'))
    return render_template('auction.html')
@app.route('/teams')
def teams():
    if not session.get('logged_in'): return redirect(url_for('login'))
    return render_template('teams.html', state=auction_state)
@app.route('/api/state')
def get_state():
    if not session.get('logged_in'): return jsonify({"error": "Not authenticated"}), 401
    return jsonify(auction_state)
@app.route('/api/next_player')
def next_player():
    if not session.get('logged_in'): return jsonify({"error": "Not authenticated"}), 401
    import random
    unsold_ids = auction_state.get('unsold_player_ids', [])
    if not unsold_ids: return jsonify(None)
    player_id = random.choice(unsold_ids)
    return jsonify(auction_state['players'][str(player_id)])
@app.route('/api/sell', methods=['POST'])
def sell_player():
    if not session.get('logged_in'): return jsonify({"error": "Not authenticated"}), 401
    data = request.json
    player_id, team_name, points = data.get('playerId'), data.get('teamName'), data.get('points', 0)
    if player_id not in auction_state.get('unsold_player_ids', []): return jsonify({"error": "Player already sold"}), 400
    previous_team_state = auction_state['teams'][team_name].copy()
    auction_state['teams'][team_name]['players'].append({"id": player_id, "points": points})
    auction_state['teams'][team_name]['points'] -= points
    auction_state['unsold_player_ids'].remove(player_id)
    auction_state['last_transaction'] = {"type": "sell", "player_id": player_id, "team_name": team_name, "points": points, "previous_team_state": previous_team_state}
    save_state()
    return jsonify({"success": True, "state": auction_state})
@app.route('/api/transfer_sale', methods=['POST'])
def transfer_sale():
    if not session.get('logged_in'): return jsonify({"error": "Not authenticated"}), 401
    data = request.json
    player_id, original_team_name, new_team_name, new_points = data.get('playerId'), data.get('originalTeamName'), data.get('newTeamName'), data.get('newPoints')
    if not all([player_id, original_team_name, new_team_name, new_points is not None]): return jsonify({"error": "Missing data"}), 400
    original_team = auction_state['teams'].get(original_team_name)
    new_team = auction_state['teams'].get(new_team_name)
    if not original_team or not new_team: return jsonify({"error": "Team not found"}), 404
    player_sale_info = next((p for p in original_team['players'] if p['id'] == player_id), None)
    if not player_sale_info: return jsonify({"error": "Player not found in team"}), 404
    original_team['players'].remove(player_sale_info)
    original_team['points'] += player_sale_info.get('points', 0)
    player_sale_info['points'] = new_points
    new_team['players'].append(player_sale_info)
    new_team['points'] -= new_points
    auction_state['last_transaction'] = None
    save_state()
    return jsonify({"success": True})
@app.route('/api/unsell_player', methods=['POST'])
def unsell_player():
    if not session.get('logged_in'): return jsonify({"error": "Not authenticated"}), 401
    data = request.json
    player_id, team_name = data.get('playerId'), data.get('teamName')
    if not all([player_id, team_name]): return jsonify({"error": "Missing data"}), 400
    team = auction_state['teams'].get(team_name)
    if not team: return jsonify({"error": "Team not found"}), 404
    player_sale_info = next((p for p in team['players'] if p['id'] == player_id), None)
    if not player_sale_info: return jsonify({"error": "Player not found in team"}), 404
    team['players'].remove(player_sale_info)
    team['points'] += player_sale_info.get('points', 0)
    if player_id not in auction_state['unsold_player_ids']: auction_state['unsold_player_ids'].append(player_id)
    auction_state['last_transaction'] = None
    save_state()
    return jsonify({"success": True})
@app.route('/api/undo', methods=['POST'])
def undo():
    if not session.get('logged_in'): return jsonify({"error": "Not authenticated"}), 401
    last_tx = auction_state.get('last_transaction')
    if not last_tx or last_tx['type'] != 'sell': return jsonify({"error": "No sale to undo"}), 400
    auction_state['teams'][last_tx['team_name']] = last_tx['previous_team_state']
    auction_state['unsold_player_ids'].append(last_tx['player_id'])
    auction_state['last_transaction'] = None
    save_state()
    return jsonify({"success": True, "state": auction_state})
@app.route('/api/reset', methods=['POST'])
def reset_auction():
    if not session.get('logged_in'): return jsonify({"error": "Not authenticated"}), 401
    initialize_state()
    return jsonify({"success": True, "state": auction_state})
@app.route('/api/search_players')
def search_players():
    if not session.get('logged_in'): return jsonify({"error": "Not authenticated"}), 401
    query = request.args.get('q', '').lower()
    if len(query) < 2: return jsonify([])
    unsold_ids = set(auction_state.get('unsold_player_ids', []))
    matches = [p for p_id, p in auction_state.get('players', {}).items() if int(p_id) in unsold_ids and (query in p['player_name'].lower() or query == str(p_id))]
    return jsonify(matches[:10])
@app.route('/api/export/excel')
def export_excel():
    if not session.get('logged_in'): return redirect(url_for('login'))
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')
    all_players = auction_state.get('players', {})
    summary = []
    for team, data in auction_state.get('teams', {}).items():
        summary.append({"Team Name": team, "Players Bought": len(data['players']), "Points Remaining": data['points']})
        roster = []
        for p in data['players']:
            player_info = all_players.get(str(p['id']), {}).copy()
            player_info['Sold For Points'] = p.get('points')
            roster.append(player_info)
        df_roster = pd.DataFrame(roster)
        safe_name = ''.join(e for e in team if e.isalnum())[:31]
        df_roster.to_excel(writer, sheet_name=safe_name, index=False)
    pd.DataFrame(summary).to_excel(writer, sheet_name='Summary', index=False)
    writer.close()
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='DCL_Auction_Report.xlsx')


if __name__ == '__main__':
    # This block is for local development only
    load_state() 
    app.run(host='127.0.0.1', port=8080, debug=True)