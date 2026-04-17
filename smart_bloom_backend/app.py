import openai
from flask_cors import CORS
openai.api_key = "YOUR_API_KEY"

from flask import Flask, jsonify, request
from db import get_db_connection
from apscheduler.schedulers.background import BackgroundScheduler
from scheduler_jobs import check_reminders_and_notify_job

# to protect admin roles we will use json web tokens
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
    get_jwt
)

from functools import wraps
import db

app = Flask(__name__)
CORS(app)

app.config["JWT_SECRET_KEY"] = "super-secret-key-change-this"

jwt = JWTManager(app)

# blocklist for revoked tokens
blocklist = set()

# check if token is revoked
@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    return jwt_payload["jti"] in blocklist

print(db.__file__)

# connecting my files
from routes.auth_routes import auth_bp
from routes.user_routes import user_bp
from routes.flower_routes import flower_bp
from routes.cart_routes import cart_bp
from routes.order_routes import order_bp
from routes.admin_routes import admin_bp
from routes.reminders import reminders_bp
from routes.img import img_bp

# blueprint
app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(flower_bp)
app.register_blueprint(cart_bp)
app.register_blueprint(order_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(reminders_bp)
app.register_blueprint(img_bp)

# scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_reminders_and_notify_job, trigger="cron", hour=9, minute=0)
scheduler.start()
# Main page
@app.route("/")
def home():
    return "Smart Bloom Store Backend is running "

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)