import os
import json
import pandas as pd
from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for, session
import io

app = Flask(__name__)
# This secret key is needed to securely manage user sessions
app.secret_key = 'your_super_secret_key_change_me' 

# --- CONFIGURATION ---
STATE_FILE = 'auction_state.json'
PLAYERS_FILE = 'players.json'
ADMIN_PASSWORD = "dcl"  # The password to access the auction
INITIAL_TEAM_POINTS = 110000
TEAMS = [
    "Naman Communication", "bhagat sing club", "Yaar Albela", "Maa Santoshi", "Ramdevariya",
    "Maa Karni club", "Lemda Eleven", "Risingin Star", "Pareek Patrolium",
    "Rajasthan Royal", "Baba Blastar", "khetarpal Eleven", "Zehrili Nagin"
]

auction_state = {}

# --- STATE MANAGEMENT FUNCTIONS ---
def load_state():
    global auction_state
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            auction_state = json.load(f)
    else:
        initialize_state()

def save_state():
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(auction_state, f, indent=4)

def initialize_state():
    """Initialize a fresh auction state from the base players file."""
    global auction_state
    print("Attempting to initialize a new auction state...")
    try:
        # Check if the file exists before trying to open it
        if not os.path.exists(PLAYERS_FILE):
            print(f"CRITICAL ERROR: The file '{PLAYERS_FILE}' was not found.")
            print(f"Please make sure '{PLAYERS_FILE}' is in the root directory of your project.")
            # We set a default empty state to prevent a crash, but the app will be empty
            auction_state = {"players": {}, "teams": {}, "unsold_player_ids": [], "last_transaction": None}
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

    except json.JSONDecodeError as e:
        print(f"CRITICAL ERROR: The '{PLAYERS_FILE}' file has a JSON syntax error: {e}")
        print("Please validate your JSON file content.")
        auction_state = {"players": {}, "teams": {}, "unsold_player_ids": [], "last_transaction": None}
    except Exception as e:
        print(f"An unexpected error occurred during initialization: {e}")
        auction_state = {"players": {}, "teams": {}, "unsold_player_ids": [], "last_transaction": None}
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
    # Pass the full state to the template for rendering
    return render_template('teams.html', state=auction_state)

# --- API ENDPOINTS FOR JAVASCRIPT ---
@app.route('/api/state')
def get_state():
    if not session.get('logged_in'): return jsonify({"error": "Not authenticated"}), 401
    return jsonify(auction_state)

@app.route('/api/next_player')
def next_player():
    if not session.get('logged_in'): return jsonify({"error": "Not authenticated"}), 401
    import random
    unsold_ids = auction_state['unsold_player_ids']
    if not unsold_ids:
        return jsonify(None) # No players left
    
    player_id = random.choice(unsold_ids)
    player_data = auction_state['players'][str(player_id)]
    return jsonify(player_data)

@app.route('/api/sell', methods=['POST'])
def sell_player():
    if not session.get('logged_in'): return jsonify({"error": "Not authenticated"}), 401
    data = request.json
    player_id = data.get('playerId')
    team_name = data.get('teamName')
    points = data.get('points', 0)

    if player_id not in auction_state['unsold_player_ids']:
        return jsonify({"error": "Player already sold or invalid"}), 400
    
    previous_team_state = auction_state['teams'][team_name].copy()
    
    auction_state['teams'][team_name]['players'].append(player_id)
    auction_state['teams'][team_name]['points'] -= points
    auction_state['unsold_player_ids'].remove(player_id)
    
    auction_state['last_transaction'] = {
        "type": "sell", "player_id": player_id, "team_name": team_name,
        "points": points, "previous_team_state": previous_team_state
    }
    save_state()
    return jsonify({"success": True, "state": auction_state})

@app.route('/api/undo', methods=['POST'])
def undo():
    if not session.get('logged_in'): return jsonify({"error": "Not authenticated"}), 401
    last_tx = auction_state.get('last_transaction')
    if not last_tx or last_tx['type'] != 'sell':
        return jsonify({"error": "No sale to undo"}), 400

    player_id = last_tx['player_id']
    auction_state['teams'][last_tx['team_name']] = last_tx['previous_team_state']
    auction_state['unsold_player_ids'].append(player_id)
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
    all_players_dict = auction_state.get('players', {})
    teams_summary = []

    for team_name, team_data in auction_state.get('teams', {}).items():
        teams_summary.append({
            "Team Name": team_name,
            "Players Bought": len(team_data['players']),
            "Points Remaining": team_data['points']
        })
        roster_data = []
        for player_id in team_data.get('players', []):
            player_info = all_players_dict.get(str(player_id), {})
            roster_data.append({
                "Player ID": player_info.get('id'),
                "Player Name": player_info.get('player_name'),
                "Father's Name": player_info.get('father_name')
            })
        df_roster = pd.DataFrame(roster_data)
        safe_sheet_name = ''.join(e for e in team_name if e.isalnum())[:31]
        df_roster.to_excel(writer, sheet_name=safe_sheet_name, index=False)
        
    df_summary = pd.DataFrame(teams_summary)
    df_summary.to_excel(writer, sheet_name='Summary', index=False)
    
    writer.close()
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='DCL_Auction_Report.xlsx')

if __name__ == '__main__':
    from waitress import serve
    load_state()
    print("Starting development server with Waitress on http://127.0.0.1:5000")
    serve(app, host='0.0.0.0', port=5000)