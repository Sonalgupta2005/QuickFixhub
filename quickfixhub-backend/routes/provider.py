from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from boto3.dynamodb.conditions import Attr
import uuid

from db.dynamodb import (
    service_requests_table,
    service_offers_table,
)

from services.provider_matcher import get_ranked_providers
from services.offer_service import MAX_OFFER_ROUNDS
from utils.time_utils import now_iso


provider_bp = Blueprint("provider", __name__)


# =========================================================
# DASHBOARD SUMMARY
# =========================================================
@provider_bp.route("/dashboard/summary", methods=["GET"])
@login_required
def dashboard_summary():
    if current_user.role != "provider":
        return {"success": False}, 403

    res = service_requests_table.scan(
        FilterExpression=Attr("assigned_provider_id").eq(current_user.id)
    )

    completed = 0
    active = 0
    earnings = 0

    for req in res.get("Items", []):
        if req["status"] == "completed":
            completed += 1
            earnings += 50
        elif req["status"] in ["accepted", "in_progress"]:
            active += 1

    return {
        "success": True,
        "stats": {
            "jobsCompleted": completed,
            "activeJobs": active,
            "rating": 4.9,
            "earnings": earnings,
        },
    }


# =========================================================
# AVAILABLE JOBS
# =========================================================
@provider_bp.route("/jobs/available", methods=["GET"])
@login_required
def available_jobs():
    if current_user.role != "provider":
        return {"success": False}, 403

    offers = service_offers_table.scan(
        FilterExpression=(
            Attr("provider_id").eq(current_user.id)
            & Attr("status").eq("offered")
        )
    ).get("Items", [])

    jobs = []

    for offer in offers:
        req = service_requests_table.get_item(
            Key={"request_id": offer["request_id"]}
        ).get("Item")

        if req:
            jobs.append(req)

    return {"success": True, "jobs": jobs}


# =========================================================
# MY JOBS
# =========================================================
@provider_bp.route("/jobs/my", methods=["GET"])
@login_required
def my_jobs():
    if current_user.role != "provider":
        return {"success": False}, 403

    res = service_requests_table.scan(
        FilterExpression=(
            Attr("assigned_provider_id").eq(current_user.id)
            & Attr("status").is_in(
                ["accepted", "in_progress", "completed"]
            )
        )
    )

    return {"success": True, "jobs": res.get("Items", [])}


# =========================================================
# ACCEPT OFFER
# =========================================================
@provider_bp.route("/offers/<request_id>/accept", methods=["POST"])
@login_required
def accept_offer(request_id):
    if current_user.role != "provider":
        return {"success": False}, 403

    # Fetch offer using composite key
    res = service_offers_table.get_item(
        Key={
            "request_id": request_id,
            "provider_id": current_user.id
        }
    )

    offer = res.get("Item")

    if not offer or offer["status"] != "offered":
        return {"success": False, "message": "No active offer"}, 400

    # Mark offer accepted
    service_offers_table.update_item(
        Key={
            "request_id": request_id,
            "provider_id": current_user.id
        },
        UpdateExpression="SET #s=:s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "accepted"},
    )

    # Update service request
    service_requests_table.update_item(
        Key={"request_id": request_id},
        UpdateExpression="""
            SET #s=:s,
                assigned_provider_id=:pid,
                provider_name=:pn,
                provider_phone=:pp,
                provider_email=:pe,
                offer_expires_at=:null,
                updated_at=:u
        """,
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "accepted",
            ":pid": current_user.id,
            ":pn": current_user.name,
            ":pp": current_user.phone,
            ":pe": current_user.email,
            ":null": None,
            ":u": now_iso(),
        },
    )

    # Expire other offers for same request
    other_offers = service_offers_table.scan(
        FilterExpression=Attr("request_id").eq(request_id)
    ).get("Items", [])

    for o in other_offers:
        if o["provider_id"] != current_user.id and o["status"] == "offered":
            service_offers_table.update_item(
                Key={
                    "request_id": request_id,
                    "provider_id": o["provider_id"]
                },
                UpdateExpression="SET #s=:s",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": "expired"},
            )

    return {"success": True}


# =========================================================
# REJECT OFFER
# =========================================================
@provider_bp.route("/offers/<request_id>/reject", methods=["POST"])
@login_required
def reject_offer(request_id):
    if current_user.role != "provider":
        return {"success": False}, 403

    res = service_offers_table.get_item(
        Key={
            "request_id": request_id,
            "provider_id": current_user.id
        }
    )

    offer = res.get("Item")

    if not offer or offer["status"] != "offered":
        return {"success": False}, 400

    # Mark rejected
    service_offers_table.update_item(
        Key={
            "request_id": request_id,
            "provider_id": current_user.id
        },
        UpdateExpression="SET #s=:s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "rejected"},
    )

    req = service_requests_table.get_item(
        Key={"request_id": request_id}
    ).get("Item")

    if not req:
        return {"success": False}, 404

    # Check if other offers still active
    active_offers = service_offers_table.scan(
        FilterExpression=(
            Attr("request_id").eq(request_id)
            & Attr("status").eq("offered")
        )
    ).get("Items", [])

    if active_offers:
        return {"success": True}

    # Max rounds?
    if req["offer_round"] >= MAX_OFFER_ROUNDS:
        service_requests_table.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET #s=:s, updated_at=:u",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "expired",
                ":u": now_iso(),
            },
        )
        return {"success": True}

    # Re-offer logic
    ranked = get_ranked_providers(
        req["service_type"],
        req["address"],
    )

    contacted = {
        o["provider_id"]
        for o in service_offers_table.scan(
            FilterExpression=Attr("request_id").eq(request_id)
        ).get("Items", [])
    }

    fresh = [pid for pid, _ in ranked if pid not in contacted]

    if not fresh:
        service_requests_table.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET #s=:s, updated_at=:u",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "expired",
                ":u": now_iso(),
            },
        )
        return {"success": True}

    # Offer next batch
    for pid in fresh[:3]:
        service_offers_table.put_item(
            Item={
                "request_id": request_id,
                "provider_id": pid,
                "status": "offered",
                "created_at": now_iso(),
            }
        )

    service_requests_table.update_item(
        Key={"request_id": request_id},
        UpdateExpression="""
            SET #s=:s,
                offer_round=:r,
                offer_expires_at=:e,
                updated_at=:u
        """,
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "offered",
            ":r": req["offer_round"] + 1,
            ":e": now_iso(),
            ":u": now_iso(),
        },
    )

    return {"success": True}
