# aws_app.py

from flask import Flask, send_from_directory
import os
import boto3

from config import Config
from extensions import bcrypt, login_manager
from routes.auth import auth_bp
from routes.service_request import service_bp
from routes.provider import provider_bp
from models.user import User
from db.dynamodb import users_table

# ----------------------------------
# Flask App (Serve React build)
# ----------------------------------
app = Flask(
    __name__,
    static_folder="frontend_dist",
    static_url_path=""
)
app.config.from_object(Config)

# ----------------------------------
# Extensions
# ----------------------------------
bcrypt.init_app(app)
login_manager.init_app(app)

# ----------------------------------
# AWS Configuration (IAM-based)
# ----------------------------------
AWS_REGION = "us-east-1"
SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:905418361023:aws_capstone_topic"

sns = boto3.client("sns", region_name=AWS_REGION)

# ----------------------------------
# SNS helper
# ----------------------------------
def send_sns(subject: str, message: str):
    if not SNS_TOPIC_ARN:
        return
    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message
        )
    except Exception as e:
        print("SNS publish error:", e)

# ----------------------------------
# Flask-Login user loader (DynamoDB)
# ----------------------------------
@login_manager.user_loader
def load_user(user_id):
    res = users_table.get_item(Key={"user_id": user_id})
    item = res.get("Item")
    return User(**item) if item else None

# ----------------------------------
# API Blueprints
# ----------------------------------
app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(service_bp, url_prefix="/api/service")
app.register_blueprint(provider_bp, url_prefix="/api/provider")

# ----------------------------------
# API Health Check (moved)
# ----------------------------------
@app.route("/api/health")
def api_health():
    return {
        "status": "running",
        "env": "aws",
        "region": AWS_REGION
    }

# ----------------------------------
# Serve React (SPA)
# ----------------------------------
@app.route("/")
def serve_react():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def serve_static_or_react(path):
    file_path = os.path.join(app.static_folder, path)
    if os.path.exists(file_path):
        return send_from_directory(app.static_folder, path)
    # React Router fallback
    return send_from_directory(app.static_folder, "index.html")

# ----------------------------------
# Entry point (DEMO MODE)
# ----------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
