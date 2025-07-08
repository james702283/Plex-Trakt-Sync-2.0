# app.py
import json
import traceback
import uuid
from threading import Thread
from flask import Flask, request, jsonify, render_template, send_from_directory
from waitress import serve
import webbrowser
import time
import re
from datetime import datetime, UTC
import os

from config.ConfigLoader import load_config, save_config
from plex_api.PlexApi import PlexApi
from trakt_api.TraktApi import TraktApi
from run_sync import run_plugins
from metadata.tmdb_api import TMDbApi

SYNC_PROGRESS_STATS = {"status": "idle", "current_library": "N/A"}
SYNC_HISTORY_FILE = "sync_history.json"
LIVE_LOG_LINES = []
SYNC_IN_PROGRESS = False
CLIENT_IDENTIFIER = str(uuid.uuid4())
ACTUAL_ITEMS_ADDED = 0

app = Flask(__name__, template_folder="templates", static_folder="static")

def reset_progress_stats():
    global SYNC_PROGRESS_STATS, ACTUAL_ITEMS_ADDED
    SYNC_PROGRESS_STATS = {"status": "idle", "current_library": "N/A"}
    ACTUAL_ITEMS_ADDED = 0

def log(message):
    print(message)
    LIVE_LOG_LINES.append(message)
    global SYNC_PROGRESS_STATS, ACTUAL_ITEMS_ADDED
    if not SYNC_IN_PROGRESS: return

    library_match = re.search(r"--- Processing Plex Library: '([^']*)'", message)
    if library_match:
        SYNC_PROGRESS_STATS.update({"status": "scanning", "current_library": library_match.group(1)})
        return
    
    response_match = re.search(r"Trakt response:.*?'added': {'movies': (\d+), 'episodes': (\d+)}", message)
    if response_match:
        movies_added = int(response_match.group(1))
        episodes_added = int(response_match.group(2))
        ACTUAL_ITEMS_ADDED += (movies_added + episodes_added)
        return

    if "--- Submitting batch" in message:
        SYNC_PROGRESS_STATS["status"] = "submitting"
        return

def sync_worker():
    global SYNC_IN_PROGRESS, LIVE_LOG_LINES
    SYNC_IN_PROGRESS = True
    LIVE_LOG_LINES.clear()
    reset_progress_stats()
    start_time = datetime.now(UTC)
    log("--- SYNC PROCESS STARTED ---")
    
    status = "Failed"

    try:
        config = load_config()
        plex_api = PlexApi(baseurl=config.get("PLEX_URL"), token=config.get("PLEX_TOKEN"), log=log)
        trakt_api = TraktApi(client_id=config.get("TRAKT_CLIENT_ID"), client_secret=config.get("TRAKT_CLIENT_SECRET"), log=log, oauth_token_data=config.get("TRAKT_OAUTH_TOKEN"))
        
        run_plugins(plex_api, trakt_api, config, log)
        
        status = "Completed"
    except Exception as e:
        log(f"[FATAL] An error occurred in the sync worker: {e}")
        log(traceback.format_exc())
    finally:
        log("--- SYNC PROCESS FINISHED ---")
        end_time = datetime.now(UTC)
        try:
            history_entry = {"id": str(uuid.uuid4()), "start_time": start_time.isoformat(), "end_time": end_time.isoformat(), "duration_seconds": int((end_time - start_time).total_seconds()), "status": status, "items_added": ACTUAL_ITEMS_ADDED, "log": list(LIVE_LOG_LINES)}
            try:
                with open(SYNC_HISTORY_FILE, 'r+') as f:
                    history_data = json.load(f)
                    history_data.insert(0, history_entry)
                    f.seek(0)
                    f.truncate()
                    json.dump(history_data[:50], f, indent=4)
            except (FileNotFoundError, json.JSONDecodeError):
                with open(SYNC_HISTORY_FILE, 'w') as f:
                    json.dump([history_entry], f, indent=4)
        except Exception as e:
            log(f"[ERROR] Could not save sync session to history: {e}")

        SYNC_IN_PROGRESS = False
        SYNC_PROGRESS_STATS["status"] = "finished"

@app.route("/")
def index(): return render_template("index.html")

@app.route("/api/trakt-history")
def trakt_history_route():
    if SYNC_IN_PROGRESS:
        return jsonify({"status": "sync_in_progress", "message": "History is unavailable while a sync is running."}), 429

    cfg = load_config()
    try:
        trakt_api = TraktApi(client_id=cfg.get("TRAKT_CLIENT_ID"), client_secret=cfg.get("TRAKT_CLIENT_SECRET"), log=log, oauth_token_data=cfg.get("TRAKT_OAUTH_TOKEN"))
        tmdb_api = TMDbApi(api_key=cfg.get("TMDB_API_KEY"), log=log)

        ui_items = trakt_api.get_watched_history_for_ui()

        for item in ui_items:
            imdb_id = item['ids'].get('imdb')
            tmdb_id = item['ids'].get('tmdb')
            item['poster'] = tmdb_api.get_poster(media_type='movie' if item['type'] == 'movie' else 'tv', imdb_id=imdb_id, tmdb_id=tmdb_id)
        
        return jsonify({"items": ui_items})
    except Exception as e:
        log(f"[ERROR] Failed to fetch Trakt/TMDB history for UI: {e}")
        log(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/static/<path:path>')
def send_static(path): return send_from_directory('static', path)
@app.route("/api/status")
def status():
    cfg = load_config()
    return jsonify({"sync_in_progress": SYNC_IN_PROGRESS, "plex_authorized": bool(cfg.get("PLEX_TOKEN")), "trakt_authorized": bool(cfg.get("TRAKT_OAUTH_TOKEN"))})
@app.route("/api/sync-progress")
def sync_progress(): return jsonify(SYNC_PROGRESS_STATS)
@app.route("/api/sync-history")
def get_sync_history():
    try:
        with open(SYNC_HISTORY_FILE, "r") as f: history = json.load(f)
        return jsonify(history)
    except FileNotFoundError: return jsonify([])
    except Exception as e: return jsonify({"error": str(e)}), 500
@app.route("/api/config", methods=["GET", "POST"])
def config_route():
    if request.method == "POST":
        current_config = load_config()
        new_data = request.get_json(force=True)
        current_config.update(new_data)
        save_config(current_config)
        return jsonify({"status": "success", "message": "Configuration saved."})
    return jsonify(load_config())
@app.route("/api/plex-auth/get-pin", methods=["POST"])
def get_plex_pin():
    try:
        plex_api = PlexApi(baseurl=None, token=None, log=log)
        pin_data = plex_api.get_pin(CLIENT_IDENTIFIER)
        return jsonify(pin_data)
    except Exception as e: return jsonify({"error": str(e)}), 500
@app.route("/api/plex-auth/check-pin", methods=["POST"])
def check_plex_pin():
    try:
        data = request.get_json(force=True)
        pin_id = data.get("id")
        plex_api = PlexApi(baseurl=None, token=None, log=log)
        auth_result = plex_api.check_pin(pin_id, CLIENT_IDENTIFIER)
        if auth_result.get("auth_token"):
            cfg = load_config()
            cfg["PLEX_TOKEN"] = auth_result["auth_token"]
            save_config(cfg)
            return jsonify({"status": "success", "message": "Plex authorized successfully.", "auth_token": auth_result["auth_token"]})
        else: return jsonify({"status": "pending", "message": "Authorization pending."})
    except Exception as e: return jsonify({"error": str(e)}), 500
@app.route("/api/plex/libraries", methods=["GET"])
def get_plex_libraries():
    cfg = load_config()
    try:
        plex_api = PlexApi(cfg.get("PLEX_URL"), cfg.get("PLEX_TOKEN"), log)
        return jsonify(plex_api.get_libraries())
    except Exception as e: return jsonify({"error": str(e)}), 500
@app.route("/api/trakt-auth/initiate-auth", methods=["POST"])
def initiate_trakt_auth():
    cfg = load_config()
    try:
        trakt_api = TraktApi(cfg.get("TRAKT_CLIENT_ID"), cfg.get("TRAKT_CLIENT_SECRET"), log=log)
        return jsonify(trakt_api.initiate_device_auth())
    except Exception as e: return jsonify({"error": f"Failed to initiate Trakt auth: {e}"}), 500
@app.route("/api/trakt-auth/check-auth", methods=["POST"])
def check_trakt_auth():
    try:
        data = request.get_json(force=True)
        trakt_api = TraktApi(cfg.get("TRAKT_CLIENT_ID"), cfg.get("TRAKT_CLIENT_SECRET"), log=log)
        token_data = trakt_api.check_device_auth(data.get("device_code"))
        if token_data:
            cfg["TRAKT_OAUTH_TOKEN"] = token_data
            save_config(cfg)
            return jsonify({"status": "success", "message": "Trakt authorized successfully."})
        else: return jsonify({"status": "pending", "message": "Authorization pending."})
    except Exception as e: return jsonify({"error": f"An error occurred while checking auth: {e}"}), 500
@app.route("/api/run-sync", methods=["POST"])
def run_sync_route():
    if SYNC_IN_PROGRESS: return jsonify({"status": "error", "message": "Sync is already in progress."}), 409
    sync_thread = Thread(target=sync_worker)
    sync_thread.start()
    return jsonify({"status": "success", "message": "Sync process started."})
@app.route("/api/live-log")
def live_log(): return jsonify(LIVE_LOG_LINES)

if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8080
    url = f"http://localhost:{port}"
    print(f"--- Plex Trakt Sync Web Interface ---\nStarting server, access at: {url}")
    if not os.path.exists(SYNC_HISTORY_FILE):
        with open(SYNC_HISTORY_FILE, 'w') as f: json.dump([], f)
        print(f"Created '{SYNC_HISTORY_FILE}'.")
    webbrowser.open(url)
    serve(app, host=host, port=port)