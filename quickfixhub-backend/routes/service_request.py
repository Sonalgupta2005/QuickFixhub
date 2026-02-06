from flask import Blueprint, request
from flask_login import login_required, current_user
from boto3.dynamodb.conditions import Attr
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
# CREATE SERVICE REQUEST
# ==========================================================
@service_bp.route("/requests", methods=["POST"])
@login_required
def create_service_request():
    data = request.get_json()

    required = ["serviceType", "description", "address", "preferredDate"]
    for field in required:
        if not data.get(field):
            return {"success": False, "message": f"{field} is required"}, 400

    now = now_iso()
    request_id = str(uuid.uuid4())

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

    ranked = get_ranked_providers(
        service_type=request_item["service_type"],
        address=request_item["address"]
    )

    provider_ids = [pid for pid, _ in ranked[:3]]

    if provider_ids:
        offer_request_to_providers(request_item, provider_ids)
    else:
        service_requests_table.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET #s=:s",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "expired"}
        )

    res = service_requests_table.get_item(Key={"request_id": request_id})

    return {"success": True, "request": res["Item"]}, 201


# ==========================================================
# GET MY REQUESTS
# ==========================================================
@service_bp.route("/my-requests", methods=["GET"])
@login_required
def get_my_requests():
    handle_expired_offers()

    res = service_requests_table.scan(
        FilterExpression=Attr("user_id").eq(current_user.id)
    )

    return {"success": True, "requests": res.get("Items", [])}


# ==========================================================
# GET ALL REQUESTS
# ==========================================================
@service_bp.route("/all", methods=["GET"])
@login_required
def get_all_requests():
    res = service_requests_table.scan()
    return {"success": True, "requests": res.get("Items", [])}


# ==========================================================
# CANCEL REQUEST
# ==========================================================
@service_bp.route("/requests/<request_id>/cancel", methods=["POST"])
@login_required
def cancel_service_request(request_id):

    res = service_requests_table.get_item(
        Key={"request_id": request_id}
    )

    req = res.get("Item")
    if not req:
        return {"success": False}, 404

    if req["user_id"] != current_user.id:
        return {"success": False}, 403

    if req["status"] in ["in_progress", "completed", "expired", "cancelled"]:
        return {"success": False}, 400

    # Cancel request
    service_requests_table.update_item(
        Key={"request_id": request_id},
        UpdateExpression="SET #s=:s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "cancelled"}
    )

    # Expire offers (NO offer_id used)
    offers = service_offers_table.scan(
        FilterExpression=Attr("request_id").eq(request_id)
    ).get("Items", [])

    for offer in offers:
        if offer["status"] == "offered":
            service_offers_table.update_item(
                Key={
                    "request_id": request_id,
                    "provider_id": offer["provider_id"]
                },
                UpdateExpression="SET #s=:s",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": "expired"}
            )

    updated = service_requests_table.get_item(
        Key={"request_id": request_id}
    )

    return {
        "success": True,
        "request": updated["Item"]
    }
