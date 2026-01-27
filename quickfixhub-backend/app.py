from flask import Flask
from flask_cors import CORS
from config import Config
from extensions import bcrypt, login_manager
from routes.auth import auth_bp, USERS
from routes.service_request import service_bp
from routes.provider import provider_bp
from models.user import User

app = Flask(__name__)
app.config.from_object(Config)

CORS(
    app,
    supports_credentials=True,
    origins=["http://localhost:8080"]
)

bcrypt.init_app(app)
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    for record in USERS.values():
        if record["user"]["id"] == user_id:
            return User(**record["user"])
    return None

app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(service_bp, url_prefix="/api/service")
app.register_blueprint(provider_bp, url_prefix="/api/provider")

@app.route("/")
def health():
    return {"status": "running"}

if __name__ == "__main__":
    app.run(debug=True)
