from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from extensions import bcrypt
from models.user import User
from store import  PROVIDER_PROFILES
from models.provider_profile import ProviderProfile
from datetime import datetime
import uuid

auth_bp = Blueprint("auth", __name__)

# ===============================
# TEMP IN-MEMORY STORES
# (Replace with DynamoDB later)
# ===============================

USERS = {}               # key: email -> { password, user }


# ===============================
# SIGNUP (ROLE-AWARE)
# ===============================
@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    name= data.get("name")
    email = data.get("email")
    password = data.get("password")
    phone = data.get("phone")
    role = data.get("role")

    # ---- BASIC VALIDATION ----
    if not email or not password or not phone or not role:
        return jsonify({
            "success": False,
            "message": "Email, password, phone, and role are required"
        }), 400

    if role not in ["homeowner", "provider"]:
        return jsonify({
            "success": False,
            "message": "Invalid role"
        }), 400

    if email in USERS:
        return jsonify({
            "success": False,
            "message": "User already exists"
        }), 400

    # ---- CREATE USER (IDENTITY) ----
    user_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()

    USERS[email] = {
        "password": bcrypt.generate_password_hash(password).decode(),
        "user": {
            "id": user_id,
            "name": name,
            "email": email,
            "role": role,
            "phone": phone,
            "created_at": created_at
        }
    }

    # ---- PROVIDER-SPECIFIC ENFORCEMENT ----
    if role == "provider":
        service_types = data.get("serviceTypes")
        address = data.get("address")

        if (
            not service_types
            or not isinstance(service_types, list)
            or len(service_types) == 0
            or not address
        ):
            # Rollback user creation
            USERS.pop(email, None)
            return jsonify({
                "success": False,
                "message": "Providers must specify serviceTypes (array) and address"
            }), 400

        PROVIDER_PROFILES[user_id] = ProviderProfile(
            provider_id=user_id,
            service_types=service_types,
            address=address,
            is_verified=False,
            created_at=created_at
        )

    # ---- AUTO LOGIN AFTER SIGNUP ----
    user = User(**USERS[email]["user"])
    login_user(user)
    session["role"] = role

    response = {
        "success": True,
        "user": user.to_dict()
    }

    if role == "provider":
        response["providerProfile"] = PROVIDER_PROFILES[user_id].to_dict()

    return jsonify(response), 201


# ===============================
# LOGIN
# ===============================
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    email = data.get("email")
    password = data.get("password")

    record = USERS.get(email)

    if not record or not bcrypt.check_password_hash(
        record["password"], password
    ):
        return jsonify({
            "success": False,
            "message": "Invalid credentials"
        }), 401

    user = User(**record["user"])
    login_user(user)
    session["role"] = user.role

    response = {
        "success": True,
        "user": user.to_dict()
    }

    if user.role == "provider":
        response["providerProfile"] = PROVIDER_PROFILES.get(user.id).to_dict()

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
        response["providerProfile"] = PROVIDER_PROFILES.get(current_user.id).to_dict()

    return jsonify(response)


# ===============================
# LOGOUT
# ===============================
@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    return jsonify({"success": True})
