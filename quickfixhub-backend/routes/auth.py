from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from extensions import bcrypt
from models.user import User
from models.provider_profile import ProviderProfile
from datetime import datetime
import uuid
from utils.time_utils import now_iso
from aws_app import send_sns


from db.dynamodb import users_table, provider_profiles_table
from boto3.dynamodb.conditions import Key

auth_bp = Blueprint("auth", __name__)


# ===============================
# SIGNUP (ROLE-AWARE, DYNAMODB)
# ===============================
@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    phone = data.get("phone")
    role = data.get("role")

    if not all([name, email, password, phone, role]):
        return {"success": False, "message": "Missing required fields"}, 400

    if role not in ["homeowner", "provider"]:
        return {"success": False, "message": "Invalid role"}, 400

    # ----------------------------------
    # CHECK EMAIL UNIQUENESS (GSI)
    # ----------------------------------
    existing = users_table.query(
        IndexName="email-index",
        KeyConditionExpression=Key("email").eq(email)
    )

    if existing.get("Items"):
        return {"success": False, "message": "User already exists"}, 400

    user_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()

    # ----------------------------------
    # CREATE USER
    # ----------------------------------
    user_item = {
        "user_id": user_id,
        "name": name,
        "email": email,
        "password_hash": bcrypt.generate_password_hash(password).decode(),
        "role": role,
        "phone": phone,
        "created_at": created_at,
    }

    users_table.put_item(Item=user_item)

    # ----------------------------------
    # PROVIDER PROFILE (IF NEEDED)
    # ----------------------------------
    provider_profile = None

    if role == "provider":
        service_types = data.get("serviceTypes")
        address = data.get("address")

        if not service_types or not isinstance(service_types, list) or not address:
            users_table.delete_item(Key={"user_id": user_id})
            return {
                "success": False,
                "message": "Providers must specify serviceTypes and address"
            }, 400

        provider_profile = {
            "provider_id": user_id,
            "service_types": service_types,
            "address": address,
            "is_verified": False,
            "created_at": created_at,
        }

        provider_profiles_table.put_item(Item=provider_profile)

    # ----------------------------------
    # AUTO LOGIN
    # ----------------------------------
    user = User(
        id=user_id,
        name=name,
        email=email,
        role=role,
        phone=phone,
        created_at=created_at
    )

    login_user(user)
    session["role"] = role

    response = {
        "success": True,
        "user": user.to_dict()
    }

    if provider_profile:
        response["providerProfile"] = provider_profile

    return jsonify(response), 201


# ===============================
# LOGIN
# ===============================
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return {
            "success": False,
            "message": "Email and password are required"
        }, 400

    # ----------------------------------
    # QUERY USER BY EMAIL (GSI)
    # ----------------------------------
    res = users_table.query(
        IndexName="email-index",
        KeyConditionExpression=Key("email").eq(email)
    )

    items = res.get("Items", [])
    if not items:
        return {"success": False, "message": "Invalid credentials"}, 401

    user_item = items[0]

    # ----------------------------------
    # PASSWORD CHECK
    # ----------------------------------
    if not bcrypt.check_password_hash(
        user_item["password_hash"], password
    ):
        return {"success": False, "message": "Invalid credentials"}, 401

    # ----------------------------------
    # LOGIN USER
    # ----------------------------------
    user = User(
        id=user_item["user_id"],
        name=user_item["name"],
        email=user_item["email"],
        role=user_item["role"],
        phone=user_item["phone"],
        created_at=user_item["created_at"]
    )

    login_user(user)
    session["role"] = user.role
    session["user_id"] = user.id

    # ----------------------------------
    # 🔔 SNS LOGIN NOTIFICATION
    # ----------------------------------
    send_sns(
        subject="User Login Event",
        message=(
            f"User logged in successfully\n\n"
            f"User ID: {user.id}\n"
            f"Name: {user.name}\n"
            f"Email: {user.email}\n"
            f"Role: {user.role}\n"
            f"Login Time (UTC): {now_iso()}"
        )
    )

    # ----------------------------------
    # RESPONSE
    # ----------------------------------
    response = {
        "success": True,
        "user": user.to_dict()
    }

    if user.role == "provider":
        profile = provider_profiles_table.get_item(
            Key={"provider_id": user.id}
        ).get("Item")
        response["providerProfile"] = profile

    return jsonify(response), 200

def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    res = users_table.query(
        IndexName="email-index",
        KeyConditionExpression=Key("email").eq(email)
    )

    items = res.get("Items", [])
    if not items:
        return {"success": False, "message": "Invalid credentials"}, 401

    user_item = items[0]

    if not bcrypt.check_password_hash(
        user_item["password_hash"], password
    ):
        return {"success": False, "message": "Invalid credentials"}, 401

    user = User(
        id=user_item["user_id"],
        name=user_item["name"],
        email=user_item["email"],
        role=user_item["role"],
        phone=user_item["phone"],
        created_at=user_item["created_at"]
    )

    login_user(user)
    session["role"] = user.role

    response = {
        "success": True,
        "user": user.to_dict()
    }

    if user.role == "provider":
        profile = provider_profiles_table.get_item(
            Key={"provider_id": user.id}
        ).get("Item")
        response["providerProfile"] = profile

    return jsonify(response)


# ===============================
# SESSION RESTORE
# ===============================
@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    response = {
        "success": True,
        "user": current_user.to_dict()
    }

    if current_user.role == "provider":
        profile = provider_profiles_table.get_item(
            Key={"provider_id": current_user.id}
        ).get("Item")
        response["providerProfile"] = profile

    return jsonify(response)


# ===============================
# LOGOUT
# ===============================
@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    return {"success": True}
