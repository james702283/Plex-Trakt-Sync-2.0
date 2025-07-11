# FORCE UPDATE - ensure this version overwrites remote
import sys
import os
import subprocess
import json
import traceback
import uuid
from threading import Thread, Event
from flask import Flask, request, jsonify, render_template
from waitress import serve
import time
import re
from datetime import datetime, UTC, timedelta
import atexit
import webbrowser

# --- SELF-AWARE LAUNCHER STUB ---
VENV_PYTHON = os.path.abspath(os.path.join(os.path.dirname(__file__), 'venv', 'Scripts', 'python.exe'))
CURRENT_PYTHON = os.path.abspath(sys.executable)
if CURRENT_PYTHON.lower() != VENV_PYTHON.lower():
    print(f"--- LAUNCHER: Re-launching with the correct one from the virtual environment... ---")
    subprocess.call([VENV_PYTHON, __file__] + sys.argv[1:])
    sys.exit(0)
# --- END OF LAUNCHER STUB ---

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import state
from config.ConfigLoader import load_config, save_config
from plex_api.PlexApi import PlexApi
from trakt_api.TraktApi import TraktApi
from metadata.tmdb_api import TMDbApi

## FIX: TqdmToLog is now a simple passthrough. It no longer updates any state.
class TqdmToLog:
    def write(self, s):
        sys.stderr.write(s)
        sys.stderr.flush()
        s = s.strip()
        if not s: return
        with state.log_lock:
            if state.LIVE_LOG_LINES and state.LIVE_LOG_LINES[-1].lstrip().startswith(('Scanning', 'Comparing', 'Applying')):
                state.LIVE_LOG_LINES[-1] = s
            else:
                state.LIVE_LOG_LINES.append(s)
    def flush(self):
        sys.stderr.flush()

app = Flask(__name__, template_folder="templates", static_folder="static")
SCHEDULER = BackgroundScheduler()

def reset_progress_stats():
    with state.progress_lock:
        state.SYNC_PROGRESS_STATS.update({
            "status": "idle", "current_library": "N/A", "is_syncing": False,
            "current_item_name": "",
            "item": {"name": "", "progress_percent": 0, "progress_text": ""},
            "overall": {"progress_percent": 0, "progress_text": "", "library_progress_text": ""},
            "rate": {"value_raw": 0, "text": "0 items/s"},
            "time": {"elapsed": "00:00", "remaining": "00:00"}
        })
        state.ITEMS_PROCESSED_COUNT = 0

def log(message):
    with state.log_lock:
        print(message)
        sanitized_message = message.replace('<', '<').replace('>', '>')
        state.LIVE_LOG_LINES.append(sanitized_message)

def progress_updater(total_items, stop_event, start_time):
    last_count = 0
    last_time = start_time
    
    while not stop_event.is_set():
        with state.progress_lock:
            current_count = state.ITEMS_PROCESSED_COUNT
            if total_items > 0:
                overall_percent = (current_count / total_items) * 100
                state.SYNC_PROGRESS_STATS["overall"]["progress_percent"] = overall_percent
                state.SYNC_PROGRESS_STATS["overall"]["progress_text"] = f"{current_count}/{total_items}"

            now = datetime.now(UTC)
            elapsed_seconds = (now - start_time).total_seconds()
            state.SYNC_PROGRESS_STATS["time"]["elapsed"] = str(timedelta(seconds=int(elapsed_seconds)))

            time_delta = (now - last_time).total_seconds()
            if time_delta > 1: # Update rate every second
                count_delta = current_count - last_count
                rate = count_delta / time_delta
                state.SYNC_PROGRESS_STATS["rate"]["value_raw"] = rate
                state.SYNC_PROGRESS_STATS["rate"]["text"] = f"{rate:.2f} items/s"
                
                if rate > 0:
                    remaining_items = total_items - current_count
                    remaining_seconds = remaining_items / rate
                    state.SYNC_PROGRESS_STATS["time"]["remaining"] = str(timedelta(seconds=int(remaining_seconds)))
                
                last_count = current_count
                last_time = now

        time.sleep(0.5) # Update UI twice a second for smoothness

def sync_worker():
    from run_sync import run_plugins 
    if not state.sync_lock.acquire(blocking=False):
        log("[WARN] Sync requested, but a sync is already in progress.")
        return
    
    state.SYNC_CANCEL_REQUESTED = False 
    stop_updater_event = Event()
    updater_thread = None

    try:
        with state.log_lock: state.LIVE_LOG_LINES.clear()
        reset_progress_stats()
        with state.progress_lock:
            state.SYNC_PROGRESS_STATS["is_syncing"] = True
            state.SYNC_PROGRESS_STATS["status"] = "scanning"
            state.SYNC_PROGRESS_STATS["current_library"] = "Initializing..."
        start_time = datetime.now(UTC)
        log("[INFO] --- SYNC PROCESS STARTED ---")
        status = "Failed"

        try:
            config = load_config()
            plex_api = PlexApi(baseurl=config.get("PLEX_URL"), token=config.get("PLEX_TOKEN"), log=log)
            trakt_api = TraktApi(client_id=config.get("TRAKT_CLIENT_ID"), client_secret=config.get("TRAKT_CLIENT_SECRET"), log=log, oauth_token_data=config.get("TRAKT_OAUTH_TOKEN"))
            
            library_ids = config.get("PLEX_LIBRARIES", [])
            log("[INFO] Calculating total number of items to sync...")
            total_items = plex_api.get_total_item_count(library_ids)
            log(f"[INFO] Found a total of {total_items} items to scan across all libraries.")

            updater_thread = Thread(target=progress_updater, args=(total_items, stop_updater_event, start_time), daemon=True)
            updater_thread.start()

            run_plugins(plex_api, trakt_api, config, log, TqdmToLog)
            status = "Completed"
        except Exception as e:
            log(f"[FATAL] An error occurred in the sync worker: {e}"); log(traceback.format_exc())
        finally:
            if updater_thread:
                stop_updater_event.set()
                updater_thread.join(timeout=2)

            log_message = "[CANCEL] --- SYNC PROCESS CANCELLED BY USER ---" if state.SYNC_CANCEL_REQUESTED else "[INFO] --- SYNC PROCESS FINISHED ---"
            log(log_message)
            if state.SYNC_CANCEL_REQUESTED: status = "Cancelled"
            
            end_time = datetime.now(UTC)
            with state.progress_lock: items_scanned_count = state.ITEMS_PROCESSED_COUNT
            history_entry = {"id": str(uuid.uuid4()), "start_time": start_time.isoformat(), "end_time": end_time.isoformat(), "duration_seconds": int((end_time - start_time).total_seconds()), "status": status, "items_added": items_scanned_count}
            
            SYNC_HISTORY_FILE = "sync_history.json"
            try:
                with open(SYNC_HISTORY_FILE, 'r+') as f:
                    history_data = json.load(f); history_data.insert(0, history_entry); f.seek(0); f.truncate(); json.dump(history_data[:50], f, indent=4)
            except (FileNotFoundError, json.JSONDecodeError):
                with open(SYNC_HISTORY_FILE, 'w') as f: json.dump([entry for entry in [history_entry] if entry], f, indent=4)
            
            reset_progress_stats()
    finally:
        state.sync_lock.release()

# ... (rest of file is unchanged)
def update_schedule(config):
    job_id = 'scheduled_sync'
    job = SCHEDULER.get_job(job_id)
    interval_hours = config.get("SYNC_INTERVAL_HOURS", 0)

    if interval_hours and interval_hours > 0:
        trigger = IntervalTrigger(hours=interval_hours)
        if job:
            if job.trigger.interval.total_seconds() != timedelta(hours=interval_hours).total_seconds():
                job.reschedule(trigger); log(f"[INFO] Rescheduled sync job to run every {interval_hours} hours.")
        else:
            first_run_time = datetime.now(UTC) + timedelta(hours=interval_hours)
            SCHEDULER.add_job(sync_worker, trigger, id=job_id, name='Scheduled Sync', next_run_time=first_run_time)
            log(f"[INFO] Scheduled sync job to run every {interval_hours} hours. First run at {first_run_time.isoformat()}")
    elif job:
        job.remove(); log("[INFO] Automatic sync disabled.")

@app.route("/")
def index(): return render_template("index.html")

@app.route("/api/status")
def status():
    cfg = load_config()
    job = SCHEDULER.get_job('scheduled_sync')
    return jsonify({
        "sync_in_progress": state.sync_lock.locked(), "plex_authorized": bool(cfg.get("PLEX_TOKEN")), 
        "trakt_authorized": bool(cfg.get("TRAKT_OAUTH_TOKEN")), "next_sync_time": job.next_run_time.isoformat() if job else None,
        "config": cfg
    })

@app.route("/api/config", methods=["GET", "POST"])
def config_route():
    if request.method == "POST":
        current_config = load_config(); new_data = request.get_json(force=True)
        current_config.update(new_data); save_config(current_config)
        update_schedule(current_config)
        return jsonify({"status": "success", "message": "Configuration saved."})
    return jsonify(load_config())

@app.route("/api/run-sync", methods=["POST"])
def run_sync_route():
    if state.sync_lock.locked(): return jsonify({"status": "error", "message": "Sync already in progress."}), 409
    Thread(target=sync_worker, daemon=True).start()
    return jsonify({"status": "success", "message": "Sync process started."})

@app.route("/api/stop-sync", methods=["POST"])
def stop_sync_route():
    if not state.sync_lock.locked():
        return jsonify({"status": "error", "message": "No sync is currently in progress."}), 404
    state.SYNC_CANCEL_REQUESTED = True
    return jsonify({"status": "success", "message": "Cancellation request sent. The sync will stop after the current batch of items."})

@app.route("/api/plex/on-deck")
def plex_on_deck_route():
    if state.sync_lock.locked(): return jsonify({"error": "Unavailable while a sync is running."}), 429
    cfg = load_config()
    try:
        plex_api = PlexApi(cfg.get("PLEX_URL"), cfg.get("PLEX_TOKEN"), log)
        if not plex_api.is_configured: return jsonify({"error": "Plex is not authorized."}), 401
        tmdb_api = TMDbApi(cfg.get("TMDB_API_KEY"), log)
        on_deck_items = plex_api.server.library.onDeck()
        ui_items = []
        for item in on_deck_items:
            progress = (item.viewOffset / item.duration) * 100 if item.duration else 0
            if item.type == 'movie':
                imdb_id = next((g.id.split('//')[1] for g in item.guids if 'imdb' in g.id), None)
                tmdb_id = next((g.id.split('//')[1] for g in item.guids if 'tmdb' in g.id), None)
                ui_items.append({"type": "movie","title": item.title,"subtitle": str(item.year),"poster": tmdb_api.get_poster(media_type='movie', imdb_id=imdb_id, tmdb_id=tmdb_id),"progress": round(progress),"last_watched": item.lastViewedAt.isoformat() if item.lastViewedAt else "N/A"})
            elif item.type == 'episode':
                plex_show = item.show()
                imdb_id = next((g.id.split('//')[1] for g in plex_show.guids if 'imdb' in g.id), None)
                tmdb_id = next((g.id.split('//')[1] for g in plex_show.guids if 'tmdb' in g.id), None)
                subtitle = f"S{item.seasonNumber:02d}E{item.index:02d}: {item.title}" if item.seasonNumber is not None and item.index is not None else "Episode data missing"
                ui_items.append({"type": "episode","title": item.grandparentTitle,"subtitle": subtitle,"poster": tmdb_api.get_poster(media_type='tv', imdb_id=imdb_id, tmdb_id=tmdb_id),"progress": round(progress),"last_watched": item.lastViewedAt.isoformat() if item.lastViewedAt else "N/A"})
        return jsonify({"items": ui_items})
    except Exception as e:
        log(f"[ERROR] Failed to fetch Plex On Deck: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to fetch Plex On Deck: {e}"}), 500

@app.route("/api/trakt-history")
def trakt_history_route():
    if state.sync_lock.locked(): return jsonify({"status": "sync_in_progress"}), 429
    cfg = load_config()
    try:
        trakt_api = TraktApi(cfg.get("TRAKT_CLIENT_ID"), cfg.get("TRAKT_CLIENT_SECRET"), log, cfg.get("TRAKT_OAUTH_TOKEN"))
        tmdb_api = TMDbApi(cfg.get("TMDB_API_KEY"), log)
        ui_items = trakt_api.get_watched_history_for_ui()
        ui_items.sort(key=lambda x: x.get('watched_at', ''), reverse=True)
        for item in ui_items:
            media_type_for_poster = 'tv' if item['type'] == 'episode' else 'movie'
            item['poster'] = tmdb_api.get_poster(media_type=media_type_for_poster, imdb_id=item['ids'].get('imdb'), tmdb_id=item['ids'].get('tmdb'))
        return jsonify({"items": ui_items})
    except Exception as e: return jsonify({"error": "Failed to fetch Trakt history."}), 500

@app.route("/api/sync-progress")
def sync_progress(): 
    with state.progress_lock: return jsonify(state.SYNC_PROGRESS_STATS)

@app.route("/api/sync-history")
def get_sync_history():
    SYNC_HISTORY_FILE = "sync_history.json"
    try:
        with open(SYNC_HISTORY_FILE, "r") as f: return jsonify(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError): return jsonify([])

@app.route("/api/live-log")
def live_log(): 
    with state.log_lock: return jsonify(state.LIVE_LOG_LINES)
    
@app.route("/api/plex/libraries", methods=["GET"])
def get_plex_libraries():
    cfg = load_config()
    try:
        plex_api = PlexApi(cfg.get("PLEX_URL"), cfg.get("PLEX_TOKEN"), log)
        return jsonify(plex_api.get_libraries())
    except Exception as e: return jsonify({"error": str(e)}), 500
    
@app.route("/api/plex-auth/get-pin", methods=["POST"])
def get_plex_pin():
    try:
        plex_api = PlexApi(None, None, log)
        pin_data = plex_api.get_pin(str(uuid.uuid4()))
        return jsonify(pin_data)
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route("/api/plex-auth/check-pin", methods=["POST"])
def check_plex_pin():
    data = request.get_json(force=True)
    pin_id = data.get("id")
    client_identifier = data.get("client_id")
    if not client_identifier:
        return jsonify({"error": "Client identifier is missing."}), 400
    try:
        plex_api = PlexApi(None, None, log)
        auth_result = plex_api.check_pin(pin_id, client_identifier)
        if auth_result.get("auth_token"):
            cfg = load_config(); cfg["PLEX_TOKEN"] = auth_result["auth_token"]; save_config(cfg)
            return jsonify({"status": "success", "auth_token": auth_result["auth_token"]})
        return jsonify(auth_result)
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route("/api/trakt-auth/initiate-auth", methods=["POST"])
def initiate_trakt_auth():
    cfg = load_config()
    try:
        trakt_api = TraktApi(cfg.get("TRAKT_CLIENT_ID"), cfg.get("TRAKT_CLIENT_SECRET"), log)
        return jsonify(trakt_api.initiate_device_auth())
    except Exception as e: return jsonify({"error": f"Failed to initiate Trakt auth: {e}"}), 500

@app.route("/api/trakt-auth/check-auth", methods=["POST"])
def check_trakt_auth():
    cfg = load_config()
    try:
        device_code = request.get_json(force=True).get("device_code")
        trakt_api = TraktApi(cfg.get("TRAKT_CLIENT_ID"), cfg.get("TRAKT_CLIENT_SECRET"), log)
        token_data = trakt_api.check_device_auth(device_code)
        if token_data:
            cfg["TRAKT_OAUTH_TOKEN"] = token_data; save_config(cfg)
            return jsonify({"status": "success"})
        return jsonify({"status": "pending"})
    except Exception as e: return jsonify({"error": f"An error occurred: {e}"}), 500

if __name__ == "__main__":
    host = "0.0.0.0"; port = 8080
    public_url = f"http://localhost:{port}"
    print(f"--- Plex Trakt Sync Web Interface ---")
    print(f"Access the dashboard at: {public_url}")
    
    initial_config = load_config()
    if not SCHEDULER.running:
        SCHEDULER.start()
        update_schedule(initial_config)
        print("Scheduler started.")
        
    serve(app, host=host, port=port)