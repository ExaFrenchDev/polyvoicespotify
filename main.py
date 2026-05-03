import os
import requests
from flask import Flask, request, jsonify, Response

app = Flask(__name__)

LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

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
        requests.post(url, headers=headers, json={
            "roblox_user_id": user_id,
            "lastfm_username": username
        })
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
            return jsonify({"playing": False})
        track = tracks[0] if isinstance(tracks, list) else tracks
        if track.get("@attr", {}).get("nowplaying") != "true":
            return jsonify({"playing": False})
        images = track.get("image", [])
        cover_url = next((img["#text"] for img in images if img.get("size") == "large"), "")
        proxied_cover = ""
        if cover_url:
            proxied_cover = f"https://polyvoicespotify.onrender.com/cover-proxy?url={requests.utils.quote(cover_url, safe='')}"
        return jsonify({
            "playing": True,
            "title": track.get("name", "Inconnu"),
            "artist": track.get("artist", {}).get("#text", "Inconnu"),
            "album": track.get("album", {}).get("#text", ""),
            "cover": proxied_cover
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
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    if domain not in allowed_domains:
        return jsonify({"error": "Domaine non autorisé"}), 403
    try:
        resp = requests.get(url, timeout=5)
        content_type = resp.headers.get("Content-Type", "image/jpeg")
        return Response(resp.content, content_type=content_type)
    except Exception as e:
        print(f"Erreur cover proxy: {e}")
        return jsonify({"error": "Fetch échoué"}), 500

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
