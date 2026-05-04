import os
import time
import io
import requests
from PIL import Image
from flask import Flask, request, jsonify, Response
from urllib.parse import urlparse, quote

app = Flask(__name__)

LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

track_cache = {}
duration_cache = {}

def get_track_duration(title, artist):
    track_id = f"{title}--{artist}"
    if track_id in duration_cache:
        return duration_cache[track_id]
    try:
        resp = requests.get(
            "https://musicbrainz.org/ws/2/recording/",
            params={"query": f'recording:"{title}" AND artist:"{artist}"', "fmt": "json", "limit": 1},
            headers={"User-Agent": "PolyVoiceRoblox/1.0 (contact@example.com)"},
            timeout=4
        )
        data = resp.json()
        recordings = data.get("recordings", [])
        if recordings and recordings[0].get("length"):
            duration = recordings[0]["length"] // 1000
            duration_cache[track_id] = duration
            return duration
    except Exception as e:
        print(f"Erreur MusicBrainz: {e}")
    duration_cache[track_id] = None
    return None

def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def get_lastfm_username(roblox_user_id):
    try:
        url = f"{SUPABASE_URL}/rest/v1/linked_accounts?roblox_user_id=eq.{roblox_user_id}&select=lastfm_username"
        response = requests.get(url, headers=supabase_headers())
        data = response.json()
        if data and len(data) > 0:
            return data[0]["lastfm_username"]
        return None
    except:
        return None

@app.route("/link", methods=["POST"])
def link_account():
    data = request.get_json()
    if not data or "robloxUserId" not in data or "lastfmUsername" not in data:
        return jsonify({"error": "robloxUserId et lastfmUsername requis"}), 400
    user_id = str(data["robloxUserId"])
    username = data["lastfmUsername"].strip()
    if not username:
        return jsonify({"error": "Username vide"}), 400
    try:
        url = f"{SUPABASE_URL}/rest/v1/linked_accounts"
        headers = supabase_headers()
        headers["Prefer"] = "resolution=merge-duplicates"
        requests.post(url, headers=headers, json={"roblox_user_id": user_id, "lastfm_username": username})
        return jsonify({"success": True})
    except Exception as e:
        print(f"Erreur Supabase link: {e}")
        return jsonify({"success": False}), 500

@app.route("/now-playing/<roblox_user_id>", methods=["GET"])
def now_playing(roblox_user_id):
    lastfm_username = get_lastfm_username(roblox_user_id)
    if not lastfm_username:
        return jsonify({"playing": False, "reason": "Compte Last.fm non lié"})
    try:
        response = requests.get("https://ws.audioscrobbler.com/2.0/", params={
            "method": "user.getrecenttracks",
            "user": lastfm_username,
            "api_key": LASTFM_API_KEY,
            "format": "json",
            "limit": 1
        })
        data = response.json()
        tracks = data.get("recenttracks", {}).get("track", [])
        if not tracks:
            track_cache.pop(roblox_user_id, None)
            return jsonify({"playing": False})

        track = tracks[0] if isinstance(tracks, list) else tracks
        if track.get("@attr", {}).get("nowplaying") != "true":
            track_cache.pop(roblox_user_id, None)
            return jsonify({"playing": False})

        title = track.get("name", "Inconnu")
        artist = track.get("artist", {}).get("#text", "Inconnu")
        track_id = f"{title}--{artist}"

        now = time.time()
        cached = track_cache.get(roblox_user_id)
        if cached and cached["track_id"] == track_id:
            elapsed = int(now - cached["started_at"])
        else:
            elapsed = 0
            track_cache[roblox_user_id] = {"track_id": track_id, "started_at": now}

        duration = get_track_duration(title, artist)

        images = track.get("image", [])
        cover_url = next((img["#text"] for img in images if img.get("size") == "large"), "")
        proxied_cover = ""
        if cover_url:
            proxied_cover = f"https://polyvoicespotify.onrender.com/cover-proxy?url={quote(cover_url, safe='')}"

        return jsonify({
            "playing": True,
            "title": title,
            "artist": artist,
            "album": track.get("album", {}).get("#text", ""),
            "cover": proxied_cover,
            "elapsed": elapsed,
            "duration": duration
        })
    except Exception as e:
        print(f"Erreur Last.fm: {e}")
        return jsonify({"playing": False}), 500

@app.route("/cover-proxy", methods=["GET"])
def cover_proxy():
    url = request.args.get("url", "")
    if not url or not url.startswith("https://"):
        return jsonify({"error": "URL invalide"}), 400
    allowed_domains = ["lastfm.freetls.fastly.net", "lastfm-img2.akamaized.net"]
    domain = urlparse(url).netloc
    if domain not in allowed_domains:
        return jsonify({"error": "Domaine non autorisé"}), 403
    try:
        resp = requests.get(url, timeout=5)
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA").resize((174, 174))
        out = io.BytesIO()
        img.save(out, format="PNG")
        return Response(out.getvalue(), content_type="image/png")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/is-linked/<roblox_user_id>", methods=["GET"])
def is_linked(roblox_user_id):
    username = get_lastfm_username(roblox_user_id)
    return jsonify({"linked": username is not None})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
