import os
import json
import pandas as pd
from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for, session
import io

app = Flask(__name__)
# This secret key is needed to securely manage user sessions
app.secret_key = 'your_super_secret_key_change_me' 

# --- CONFIGURATION ---
DATA_DIR = os.getenv('RENDER_DATA_DIR', '.')
STATE_FILE = os.path.join(DATA_DIR, 'auction_state.json')
PLAYERS_FILE = 'players.json'
ADMIN_PASSWORD = "dcl"
INITIAL_TEAM_POINTS = 110000
TEAMS = [
    "Naman Communication", "bhagat sing club", "Yaar Albela", "Maa Santoshi", "Ramdevariya",
    "Maa Karni club", "Lemda Eleven", "Risingin Star", "Pareek Patrolium",
    "Rajasthan Royal", "Baba Blastar", "khetarpal Eleven", "Zehrili Nagin"
]

auction_state = {}

# --- STATE MANAGEMENT FUNCTIONS ---
def initialize_state():
    """Initialize a fresh auction state from the base players file."""
    global auction_state
    print("Attempting to initialize a new auction state...")
    try:
        if not os.path.exists(PLAYERS_FILE):
            print(f"CRITICAL ERROR: The file '{PLAYERS_FILE}' was not found.")
            auction_state = {}
            return

        with open(PLAYERS_FILE, 'r', encoding='utf-8') as f:
            players = json.load(f)
        
        auction_state = {
            "players": {str(p['id']): p for p in players},
            "teams": {name: {"points": INITIAL_TEAM_POINTS, "players": []} for name in TEAMS},
            "unsold_player_ids": [p['id'] for p in players],
            "last_transaction": None
        }
        save_state()
        print("New auction state initialized SUCCESSFULLY.")

    except Exception as e:
        print(f"CRITICAL ERROR during initialization: {e}")
        auction_state = {}

def load_state():
    """Load state from file, or initialize if the file is missing or corrupt."""
    global auction_state
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'teams' in data and 'players' in data:
                    auction_state = data
                    print("Auction state successfully loaded from file.")
                    return
        except Exception as e:
            print(f"WARNING: State file was corrupt: {e}. Re-initializing.")
    
    initialize_state()

def save_state():
    """Save the current auction state to the file."""
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(auction_state, f, indent=4)

# ===============================================================
#  THE FINAL FIX: This function runs before every request.
#  It acts as a safety net if the initial load failed.
# ===============================================================
@app.before_request
def check_and_load_state():
    # 'not auction_state' is a simple way to check if the dictionary is empty.
    # We also exclude static files to avoid running this logic unnecessarily.
    if not auction_state and request.endpoint not in ['static', 'login']:
        print("State is empty on request, attempting to load state again...")
        load_state()
# ===============================================================


# --- AUTHENTICATION & PAGE ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('auction'))
        else:
            return render_template('login.html', error="Incorrect Password")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return redirect(url_for('auction'))

@app.route('/auction')
def auction():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('auction.html')

@app.route('/teams')
def teams():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('teams.html', state=auction_state)

# --- API ENDPOINTS ---
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
    player_data = auction_state['players'][str(player_id)]
    return jsonify(player_data)

@app.route('/api/sell', methods=['POST'])
def sell_player():
    if not session.get('logged_in'): return jsonify({"error": "Not authenticated"}), 401
    data = request.json
    player_id, team_name, points = data.get('playerId'), data.get('teamName'), data.get('points', 0)
    if player_id not in auction_state.get('unsold_player_ids', []): return jsonify({"error": "Player already sold or invalid"}), 400
    
    previous_team_state = auction_state['teams'][team_name].copy()
    auction_state['teams'][team_name]['players'].append(player_id)
    auction_state['teams'][team_name]['points'] -= points
    auction_state['unsold_player_ids'].remove(player_id)
    auction_state['last_transaction'] = {"type": "sell", "player_id": player_id, "team_name": team_name, "points": points, "previous_team_state": previous_team_state}
    save_state()
    return jsonify({"success": True, "state": auction_state})

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

@app.route('/api/export/excel')
def export_excel():
    if not session.get('logged_in'): return redirect(url_for('login'))
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')
    all_players = auction_state.get('players', {})
    summary = []
    for team, data in auction_state.get('teams', {}).items():
        summary.append({"Team Name": team, "Players Bought": len(data['players']), "Points Remaining": data['points']})
        roster = [all_players.get(str(pid)) for pid in data['players']]
        df_roster = pd.DataFrame(roster)
        safe_name = ''.join(e for e in team if e.isalnum())[:31]
        df_roster.to_excel(writer, sheet_name=safe_name, index=False)
    pd.DataFrame(summary).to_excel(writer, sheet_name='Summary', index=False)
    writer.close()
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='DCL_Auction_Report.xlsx')

@app.route('/debug')
def debug():
    if not session.get('logged_in'): return redirect(url_for('login'))
    # ... (debug function remains the same)
    cwd, dir_contents = os.getcwd(), os.listdir('.')
    players_file_exists = os.path.exists(PLAYERS_FILE)
    players_content = "File could not be read."
    if players_file_exists:
        try:
            with open(PLAYERS_FILE, 'r', encoding='utf-8') as f:
                json.load(f)
                players_content = f"File '{PLAYERS_FILE}' was found and is valid JSON."
        except Exception as e:
            players_content = f"ERROR reading file: {str(e)}"
    else:
        players_content = f"ERROR: File '{PLAYERS_FILE}' was NOT found."
    return jsonify({
        "MESSAGE": "Debug page.", "CURRENT_WORKING_DIRECTORY": cwd, "FILES_IN_DIRECTORY": sorted(dir_contents),
        "DOES_PLAYERS_JSON_EXIST": players_file_exists, "PLAYERS_JSON_READ_STATUS": players_content,
        "CURRENT_AUCTION_STATE": auction_state,
    })

# Initial load attempt when the Gunicorn worker starts
load_state()

if __name__ == '__main__':
    from waitress import serve
    print("Starting development server with Waitress on http://127.0.0.1:5000")
    serve(app, host='0.0.0.0', port=5000)