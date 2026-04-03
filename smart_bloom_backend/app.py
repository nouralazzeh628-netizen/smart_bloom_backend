import openai
openai.api_key = "YOUR_API_KEY"
from flask import Flask, jsonify, request
from db import get_db_connection
# to protect admin rols we will use json web tokens 
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
    get_jwt
)
app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = "super-secret-key-change-this"
jwt = JWTManager(app)
from functools import wraps
import db
print(db.__file__)
#connecting my files 
from routes.auth_routes import auth_bp
from routes.user_routes import user_bp
from routes.flower_routes import flower_bp
from routes.cart_routes import cart_bp
from routes.order_routes import order_bp
from routes.admin_routes import admin_bp
from routes.reminders import reminders_bp
from routes.bouquet import bouquet_bp
#blueprint
app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(flower_bp)
app.register_blueprint(cart_bp)
app.register_blueprint(order_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(reminders_bp)
app.register_blueprint(bouquet_bp)


# Main page
@app.route("/")
def home():
    return "Smart Bloom Store Backend is running "        
        
if __name__ == "__main__":
    app.run(debug=True)


