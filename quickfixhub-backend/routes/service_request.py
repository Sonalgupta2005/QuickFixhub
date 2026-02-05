from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from boto3.dynamodb.conditions import Key
import uuid

from db.dynamodb import (
    service_requests_table,
    service_offers_table
)

from services.provider_matcher import get_ranked_providers
from services.offer_service import offer_request_to_providers
from services.timeout_service import handle_expired_offers
from utils.time_utils import now_iso


service_bp = Blueprint("service", __name__)


# ==========================================================
# CREATE SERVICE REQUEST (DYNAMODB FLOW)
# ==========================================================
@service_bp.route("/requests", methods=["POST"])
@login_required
def create_service_request():
    data = request.get_json()

    required_fields = ["serviceType", "description", "address", "preferredDate"]
    for field in required_fields:
        if not data.get(field):
            return {"success": False, "message": f"{field} is required"}, 400

    now = now_iso()
    request_id = str(uuid.uuid4())

    # -------------------------
    # CREATE REQUEST (PENDING)
    # -------------------------
    request_item = {
        "request_id": request_id,
        "user_id": current_user.id,
        "user_name": current_user.name,
        "user_email": current_user.email,
        "user_phone": current_user.phone,
        "service_type": data["serviceType"],
        "description": data["description"],
        "address": data["address"],
        "preferred_date": data["preferredDate"],
        "preferred_time": data.get("preferredTime"),
        "status": "pending",
        "assigned_provider_id": None,
        "offer_round": 0,
        "offer_expires_at": None,
        "created_at": now,
        "updated_at": now,
    }

    service_requests_table.put_item(Item=request_item)

    # -------------------------
    # MATCH PROVIDERS
    # -------------------------
    ranked = get_ranked_providers(
        service_type=request_item["service_type"],
        address=request_item["address"]
    )

    provider_ids = [pid for pid, _ in ranked[:3]]

    # -------------------------
    # OFFER OR EXPIRE
    # -------------------------
    if provider_ids:
        offer_request_to_providers(request_item, provider_ids)
    else:
        service_requests_table.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET #s=:s, updated_at=:u",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "expired",
                ":u": now_iso()
            }
        )

    # Return fresh copy
    res = service_requests_table.get_item(
        Key={"request_id": request_id}
    )

    return {
        "success": True,
        "request": res["Item"]
    }, 201


# ==========================================================
# HOMEOWNER: GET MY REQUESTS
# ==========================================================
@service_bp.route("/my-requests", methods=["GET"])
@login_required
def get_my_requests():
    # Ensure expired offers are processed
    handle_expired_offers()

    res = service_requests_table.query(
        IndexName="user_id-index",
        KeyConditionExpression=Key("user_id").eq(current_user.id)
    )

    return {
        "success": True,
        "requests": res.get("Items", [])
    }


# ==========================================================
# ADMIN / PROVIDER: GET ALL REQUESTS (TEMP)
# ==========================================================
@service_bp.route("/all", methods=["GET"])
@login_required
def get_all_requests():
    res = service_requests_table.scan()
    return {"success": True, "requests": res.get("Items", [])}


# ==========================================================
# HOMEOWNER: CANCEL SERVICE REQUEST
# ==========================================================
@service_bp.route("/requests/<request_id>/cancel", methods=["POST"])
@login_required
def cancel_service_request(request_id):
    res = service_requests_table.get_item(
        Key={"request_id": request_id}
    )
    req = res.get("Item")

    if not req:
        return {"success": False, "message": "Request not found"}, 404

    if req["user_id"] != current_user.id:
        return {"success": False, "message": "Forbidden"}, 403

    if req["status"] in ["in_progress", "completed", "expired", "cancelled"]:
        return {
            "success": False,
            "message": f"Cannot cancel request in '{req['status']}' state"
        }, 400

    # Cancel request
    service_requests_table.update_item(
        Key={"request_id": request_id},
        UpdateExpression="SET #s=:s, offer_expires_at=:n, updated_at=:u",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "cancelled",
            ":n": None,
            ":u": now_iso()
        }
    )

    # Expire all active offers
    offers = service_offers_table.query(
        IndexName="request_id-index",
        KeyConditionExpression=Key("request_id").eq(request_id)
    ).get("Items", [])

    for offer in offers:
        if offer["status"] == "offered":
            service_offers_table.update_item(
                Key={"offer_id": offer["offer_id"]},
                UpdateExpression="SET #s=:s",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": "expired"}
            )

    updated = service_requests_table.get_item(
        Key={"request_id": request_id}
    )

    return {
        "success": True,
        "message": "Service request cancelled",
        "request": updated["Item"]
    }
