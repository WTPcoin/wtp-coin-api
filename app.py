import os
import time
from flask import Flask, request, jsonify

app = Flask(__name__)

API_TOKEN = os.environ.get("WTP_API_TOKEN", "")
ALLOWED_ORIGIN = "*"

latest_status = None
last_update = None


@app.after_request
def add_headers(response):
    response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, Authorization"
    )
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "project": "We The People Coin",
        "service": "WTP read-only statistics API",
        "status_endpoint": "/api/status"
    })


@app.route("/api/status", methods=["GET"])
def status():
    if latest_status is None:
        return jsonify({
            "project": "We The People Coin",
            "connected": False,
            "message": "Waiting for your computer to send blockchain statistics."
        }), 200

    result = dict(latest_status)
    result["connected"] = True
    result["last_update"] = last_update
    return jsonify(result)


@app.route("/api/update", methods=["POST", "OPTIONS"])
def update():
    global latest_status, last_update

    if request.method == "OPTIONS":
        return "", 204

    if not API_TOKEN:
        return jsonify({"error": "Server token is not configured."}), 503

    supplied_token = request.headers.get("Authorization", "")
    if supplied_token != "Bearer " + API_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Expected JSON data"}), 400

    required = [
        "block_count",
        "latest_block",
        "latest_hash",
        "total_mining_rewards"
    ]

    if any(key not in data for key in required):
        return jsonify({"error": "Missing blockchain statistics"}), 400

    try:
        block_count = int(data["block_count"])
        latest_block = int(data["latest_block"])
        rewards = float(data["total_mining_rewards"])
        latest_hash = str(data["latest_hash"])

        if block_count < 1 or latest_block < 1 or rewards < 0:
            raise ValueError()

        if len(latest_hash) != 64 or any(
            c not in "0123456789abcdef"
            for c in latest_hash.lower()
        ):
            raise ValueError()

    except (ValueError, TypeError):
        return jsonify({"error": "Invalid statistics"}), 400

    latest_status = {
        "project": "We The People Coin",
        "read_only": True,
        "block_count": block_count,
        "latest_block": latest_block,
        "latest_hash": latest_hash,
        "total_mining_rewards": rewards
    }
    last_update = int(time.time())

    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
