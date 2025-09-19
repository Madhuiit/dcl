import os
import json
import pandas as pd
from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for, session
import io

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_change_me_for_real'

# --- CONFIGURATION ---
DATA_DIR = os.getenv('RENDER_DATA_DIR', '.')
STATE_FILE = os.path.join(DATA_DIR, 'auction_state.json')
PLAYERS_FILE = 'players.json'
ADMIN_PASSWORD = "dcl"
INITIAL_TEAM_POINTS = 110000
TEAMS = [
    "Naman Communication", "bhagat sing club", "Yaar Albela", "Maa Santoshi", "Ramdevariya",
    "Maa Karni club", "Lemda Eleven", "Rising Star", "Pareek Patrolium",
    "Rajasthan Royal", "Kevin XI", "khetarpal Eleven", "Dadoji Eleven" ,"Zabaj Cricket Club"
]
auction_state = {}

# --- STATE MANAGEMENT ---
def initialize_state():
    global auction_state
    try:
        with open(PLAYERS_FILE, 'r', encoding='utf-8') as f:
            players = json.load(f)
        auction_state = {
            "players": {str(p['id']): p for p in players},
            # NEW: Team players are now objects with id and points
            "teams": {name: {"points": INITIAL_TEAM_POINTS, "players": []} for name in TEAMS},
            "unsold_player_ids": [p['id'] for p in players],
            "last_transaction": None
        }
        save_state()
        print("SUCCESS: New auction state initialized.")
    except Exception as e:
        print(f"CRITICAL ERROR during initialization: {e}")
        auction_state = {}

def load_state():
    global auction_state
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'teams' in data and 'players' in data:
                    auction_state = data
                    print("SUCCESS: Auction state loaded.")
                    return
        except Exception as e:
            print(f"WARNING: State file corrupt: {e}. Re-initializing.")
    initialize_state()

def save_state():
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(auction_state, f, indent=4)

@app.before_request
def check_and_load_state():
    if not auction_state and request.endpoint not in ['static', 'login']:
        print("State empty, loading state before request...")
        load_state()

# --- PAGE ROUTES ---
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
    return jsonify(auction_state['players'][str(player_id)])

@app.route('/api/sell', methods=['POST'])
def sell_player():
    if not session.get('logged_in'): return jsonify({"error": "Not authenticated"}), 401
    data = request.json
    player_id, team_name, points = data.get('playerId'), data.get('teamName'), data.get('points', 0)
    if player_id not in auction_state.get('unsold_player_ids', []): return jsonify({"error": "Player already sold"}), 400
    
    previous_team_state = auction_state['teams'][team_name].copy()
    
    # NEW: Store player as an object with their sale price
    auction_state['teams'][team_name]['players'].append({"id": player_id, "points": points})
    auction_state['teams'][team_name]['points'] -= points
    auction_state['unsold_player_ids'].remove(player_id)
    
    auction_state['last_transaction'] = {
        "type": "sell", "player_id": player_id, "team_name": team_name,
        "points": points, "previous_team_state": previous_team_state
    }
    save_state()
    return jsonify({"success": True, "state": auction_state})

# NEW: API endpoint to handle searching for players
@app.route('/api/search_players')
def search_players():
    if not session.get('logged_in'): return jsonify({"error": "Not authenticated"}), 401
    query = request.args.get('q', '').lower()
    if len(query) < 2:
        return jsonify([])
    
    unsold_ids = set(auction_state.get('unsold_player_ids', []))
    all_players = auction_state.get('players', {})
    
    matches = []
    for player_id, player_data in all_players.items():
        if int(player_id) in unsold_ids:
            if query in player_data['player_name'].lower() or query == str(player_id):
                matches.append(player_data)
    
    return jsonify(matches[:10]) # Return max 10 matches

# NEW: API endpoint to edit a player's sale price
@app.route('/api/edit_sale', methods=['POST'])
def edit_sale():
    if not session.get('logged_in'): return jsonify({"error": "Not authenticated"}), 401
    data = request.json
    player_id, team_name, new_points = data.get('playerId'), data.get('teamName'), data.get('newPoints')

    team = auction_state['teams'].get(team_name)
    if not team: return jsonify({"error": "Team not found"}), 404
    
    player_to_edit = None
    old_points = 0
    for p in team['players']:
        if p['id'] == player_id:
            player_to_edit = p
            old_points = p.get('points', 0)
            break
            
    if not player_to_edit: return jsonify({"error": "Player not found in team"}), 404
    
    # Calculate the difference and adjust team points
    point_difference = old_points - new_points
    team['points'] += point_difference
    
    # Update the player's sale price
    player_to_edit['points'] = new_points
    
    # Clear last transaction to prevent accidental undo
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

# (Other routes like reset and export remain the same)
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
    teams_summary = []

    for team_name, team_data in auction_state.get('teams', {}).items():
        teams_summary.append({
            "Team Name": team_name,
            "Players Bought": len(team_data.get('players', [])),
            "Points Remaining": team_data.get('points', 0)
        })
        
        roster_data = []
        # Loop through each sale object in the team's player list
        for sale_info in team_data.get('players', []):
            player_id = sale_info.get('id')
            player_details = all_players.get(str(player_id), {})
            
            # --- THIS IS THE MODIFIED PART ---
            # Create a new, clean record with only the columns we want.
            # The 'photo' column is intentionally left out.
            clean_player_record = {
                "Player ID": player_details.get('id'),
                "Player Name": player_details.get('player_name'),
                "Father's Name": player_details.get('father_name'),
                "Sold For Points": sale_info.get('points')  # <-- Here is the new column
            }
            roster_data.append(clean_player_record)
        
        df_roster = pd.DataFrame(roster_data)
        safe_sheet_name = ''.join(e for e in team_name if e.isalnum())[:31]
        df_roster.to_excel(writer, sheet_name=safe_sheet_name, index=False)
        
    df_summary = pd.DataFrame(teams_summary)
    df_summary.to_excel(writer, sheet_name='Summary', index=False)
    
    writer.close()
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='DCL_Auction_Report.xlsx'
    )
if __name__ == '__main__':
    from waitress import serve
    load_state()
    print("Starting development server with Waitress on http://127.0.0.1:5000")
    serve(app, host='0.0.0.0', port=5000)