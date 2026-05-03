from flask import Flask, request, jsonify
import requests
import os
app = Flask(__name__)

# ============================================================
#  CONFIGURATION — Remplace par ta vraie clé API Last.fm
# ============================================================
LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY")  # https://www.last.fm/api/account/create
# ============================================================

# Stockage en mémoire : { roblox_user_id: lastfm_username }
user_links = {}


# -----------------------------------------------------------
# POST /link
# Roblox envoie { robloxUserId, lastfmUsername }
# -----------------------------------------------------------
@app.route("/link", methods=["POST"])
def link_account():
    data = request.get_json()

    if not data or "robloxUserId" not in data or "lastfmUsername" not in data:
        return jsonify({"error": "robloxUserId et lastfmUsername requis"}), 400

    user_id = str(data["robloxUserId"])
    username = data["lastfmUsername"].strip()

    if not username:
        return jsonify({"error": "Username vide"}), 400

    user_links[user_id] = username
    print(f"Lien créé : Roblox {user_id} → Last.fm {username}")
    return jsonify({"success": True})


# -----------------------------------------------------------
# GET /now-playing/<roblox_user_id>
# Roblox appelle cette route pour savoir ce que le joueur écoute
# -----------------------------------------------------------
@app.route("/now-playing/<roblox_user_id>", methods=["GET"])
def now_playing(roblox_user_id):
    lastfm_username = user_links.get(str(roblox_user_id))

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
        is_now_playing = track.get("@attr", {}).get("nowplaying") == "true"

        if not is_now_playing:
            return jsonify({"playing": False})

        # Récupération de la pochette (taille "large" = 174x174px)
        images = track.get("image", [])
        cover = next((img["#text"] for img in images if img.get("size") == "large"), "")

        return jsonify({
            "playing": True,
            "title": track.get("name", "Inconnu"),
            "artist": track.get("artist", {}).get("#text", "Inconnu"),
            "album": track.get("album", {}).get("#text", ""),
            "cover": cover
        })

    except Exception as e:
        print(f"Erreur Last.fm: {e}")
        return jsonify({"playing": False, "error": "Erreur serveur"}), 500


# -----------------------------------------------------------
# GET /health — Pour vérifier que le serveur tourne
# -----------------------------------------------------------
@app.route("/is-linked/<roblox_user_id>", methods=["GET"])
def is_linked(roblox_user_id):
    linked = str(roblox_user_id) in user_links
    return jsonify({"linked": linked})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "linkedAccounts": len(user_links)})


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
