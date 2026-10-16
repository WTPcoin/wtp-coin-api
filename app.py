import os
import time
from flask import Flask, request, jsonify
from pymongo import MongoClient
from pymongo.errors import PyMongoError

app = Flask(__name__)

API_TOKEN = os.environ.get("WTP_API_TOKEN", "")
MONGODB_URI = os.environ.get("MONGODB_URI", "")
ALLOWED_ORIGIN = "*"

mongo_client = (
    MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    if MONGODB_URI else None
)

stats_collection = (
    mongo_client["wtpcoin"]["blockchain_stats"]
    if mongo_client else None
)


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
    if stats_collection is None:
        return jsonify({"error": "Database is not configured."}), 503

    try:
        saved = stats_collection.find_one({"_id": "latest"})
    except PyMongoError:
        return jsonify({"error": "Database temporarily unavailable."}), 503

    if saved is None:
        return jsonify({
            "project": "We The People Coin",
            "connected": False,
            "message": "Waiting for your computer to send blockchain statistics."
        }), 200

    saved.pop("_id", None)
    saved["connected"] = True
    return jsonify(saved)


@app.route("/api/update", methods=["POST", "OPTIONS"])
def update():
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

    saved_stats = {
        "_id": "latest",
        "project": "We The People Coin",
        "read_only": True,
        "block_count": block_count,
        "latest_block": latest_block,
        "latest_hash": latest_hash,
        "total_mining_rewards": rewards,
        "last_update": int(time.time())
    }

    if stats_collection is None:
        return jsonify({"error": "Database is not configured."}), 503

    try:
        stats_collection.replace_one(
            {"_id": "latest"},
            saved_stats,
            upsert=True
        )
    except PyMongoError:
        return jsonify({"error": "Could not save statistics to database."}), 503

    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
