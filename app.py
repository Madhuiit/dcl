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
    "Maa Karni club", "Lemda Eleven", "Risingin Star", "Pareek Patrolium",
    "Rajasthan Royal", "Baba Blastar", "khetarpal Eleven", "Zehrili Nagin"
]

auction_state = {}

# --- STATE MANAGEMENT FUNCTIONS ---
def initialize_state():
    global auction_state
    try:
        with open(PLAYERS_FILE, 'r', encoding='utf-8') as f:
            players = json.load(f)
        auction_state = {
            "players": {str(p['id']): p for p in players},
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
                    print("SUCCESS: Auction state loaded from file.")
                    return
        except Exception as e:
            print(f"WARNING: State file was corrupt: {e}. Re-initializing.")
    
    initialize_state()

def save_state():
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(auction_state, f, indent=4)

@app.before_request
def check_and_load_state():
    if not auction_state and request.endpoint not in ['static']:
        print("State is empty, triggering load_state() before request...")
        load_state()

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
    player_id = data.get('playerId')
    original_team_name = data.get('originalTeamName')
    new_team_name = data.get('newTeamName')
    new_points = data.get('newPoints')

    if not all([player_id, original_team_name, new_team_name, new_points is not None]):
        return jsonify({"error": "Missing data for transfer."}), 400

    original_team = auction_state['teams'].get(original_team_name)
    new_team = auction_state['teams'].get(new_team_name)

    if not original_team or not new_team:
        return jsonify({"error": "Original or new team not found."}), 404

    player_sale_info = None
    for i, sale in enumerate(original_team['players']):
        if sale['id'] == player_id:
            player_sale_info = sale
            original_team['players'].pop(i) # Remove from original team
            break

    if not player_sale_info:
        return jsonify({"error": f"Player {player_id} not found in {original_team_name}'s roster."}), 404

    # Adjust points for original team
    old_points_paid = player_sale_info.get('points', 0)
    original_team['points'] += old_points_paid # Refund points to original team

    # Add player to new team
    player_sale_info['points'] = new_points # Update points for new sale
    new_team['players'].append(player_sale_info)
    new_team['points'] -= new_points # Deduct points from new team

    # Clear last transaction as this is an explicit edit
    auction_state['last_transaction'] = None
    save_state()
    return jsonify({"success": True})

@app.route('/api/unsell_player', methods=['POST'])
def unsell_player():
    if not session.get('logged_in'): return jsonify({"error": "Not authenticated"}), 401
    data = request.json
    player_id = data.get('playerId')
    team_name = data.get('teamName')

    if not all([player_id, team_name]):
        return jsonify({"error": "Missing player ID or team name for unsell operation."}), 400

    team = auction_state['teams'].get(team_name)
    if not team:
        return jsonify({"error": f"Team '{team_name}' not found."}), 404

    player_sale_info = None
    player_index_in_team = -1
    for i, sale in enumerate(team['players']):
        if sale['id'] == player_id:
            player_sale_info = sale
            player_index_in_team = i
            break

    if not player_sale_info:
        return jsonify({"error": f"Player {player_id} not found in {team_name}'s roster."}), 404

    # Remove player from team
    team['players'].pop(player_index_in_team)
    
    # Refund points to the team
    points_paid = player_sale_info.get('points', 0)
    team['points'] += points_paid

    # Add player back to unsold list if not already there
    if player_id not in auction_state['unsold_player_ids']:
        auction_state['unsold_player_ids'].append(player_id)
    
    # Clear last transaction as this is an explicit edit
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
            player_info['Sold For Points'] = p.get('points') # Changed 'sold_for_points' to 'Sold For Points' for consistency
            roster.append(player_info)
        df_roster = pd.DataFrame(roster)
        safe_name = ''.join(e for e in team if e.isalnum())[:31]
        df_roster.to_excel(writer, sheet_name=safe_name, index=False)
    pd.DataFrame(summary).to_excel(writer, sheet_name='Summary', index=False)
    writer.close()
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='DCL_Auction_Report.xlsx')

if __name__ == '__main__':
    from waitress import serve
    load_state() 
    print("Starting development server with Waitress on http://127.0.0.1:5000")
    serve(app, host='0.0.0.0', port=5000)