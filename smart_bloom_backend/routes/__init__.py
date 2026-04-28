from flask_cors import CORS

def create_app():
    app = flask(__name__)
    
    # ✅ Add this
    CORS(app, resources={r"/*": {"origins": "http://127.0.0.1:5500"}})
    
    # ... rest of your code