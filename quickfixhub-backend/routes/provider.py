from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from boto3.dynamodb.conditions import Key

from db.dynamodb import (
    service_requests_table,
    service_offers_table,
    providers_table,
)

from services.offer_service import (
    get_active_offer,
    expire_other_offers,
    offer_request_to_providers,
    MAX_OFFER_ROUNDS,
)

from services.provider_matcher import get_ranked_providers
from utils.time_utils import now_iso


provider_bp = Blueprint("provider", __name__)


# =========================================================
# PROVIDER DASHBOARD SUMMARY
# =========================================================
@provider_bp.route("/dashboard/summary", methods=["GET"])
@login_required
def dashboard_summary():
    if current_user.role != "provider":
        return {"success": False}, 403

    res = service_requests_table.scan(
        FilterExpression=Key("assigned_provider_id").eq(current_user.id)
    )

    completed = 0
    active = 0
    earnings = 0

    for req in res.get("Items", []):
        if req["status"] == "completed":
            completed += 1
            earnings += 50  # demo payout
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
# AVAILABLE JOBS (OFFERS TO THIS PROVIDER)
# =========================================================
@provider_bp.route("/jobs/available", methods=["GET"])
@login_required
def available_jobs():
    if current_user.role != "provider":
        return {"success": False}, 403

    offers = service_offers_table.query(
        IndexName="provider_id-index",
        KeyConditionExpression=Key("provider_id").eq(current_user.id),
    ).get("Items", [])

    jobs = []

    for offer in offers:
        if offer["status"] != "offered":
            continue

        req = service_requests_table.get_item(
            Key={"request_id": offer["request_id"]}
        ).get("Item")

        if req:
            jobs.append(req)

    return {"success": True, "jobs": jobs}


# =========================================================
# MY JOBS (ACCEPTED / IN PROGRESS / COMPLETED)
# =========================================================
@provider_bp.route("/jobs/my", methods=["GET"])
@login_required
def my_jobs():
    if current_user.role != "provider":
        return {"success": False}, 403

    res = service_requests_table.scan(
        FilterExpression=Key("assigned_provider_id").eq(current_user.id)
    )

    jobs = [
        r for r in res.get("Items", [])
        if r["status"] in ["accepted", "in_progress", "completed"]
    ]

    return {"success": True, "jobs": jobs}


# =========================================================
# ACCEPT OFFER
# =========================================================
@provider_bp.route("/offers/<request_id>/accept", methods=["POST"])
@login_required
def accept_offer(request_id):
    if current_user.role != "provider":
        return {"success": False}, 403

    offer = get_active_offer(request_id, current_user.id)
    if not offer:
        return {"success": False, "message": "No active offer"}, 400

    # Mark offer accepted
    service_offers_table.update_item(
        Key={"offer_id": offer.offer_id},
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
                offer_expires_at=:n,
                updated_at=:u
        """,
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "accepted",
            ":pid": current_user.id,
            ":pn": current_user.name,
            ":pp": current_user.phone,
            ":pe": current_user.email,
            ":n": None,
            ":u": now_iso(),
        },
    )

    # Expire all other offers
    expire_other_offers(request_id, current_user.id)

    return {"success": True}


# =========================================================
# REJECT OFFER
# =========================================================
@provider_bp.route("/offers/<request_id>/reject", methods=["POST"])
@login_required
def reject_offer(request_id):
    if current_user.role != "provider":
        return {"success": False}, 403

    offer = get_active_offer(request_id, current_user.id)
    if not offer:
        return {"success": False, "message": "No active offer"}, 400

    # Mark offer rejected
    service_offers_table.update_item(
        Key={"offer_id": offer.offer_id},
        UpdateExpression="SET #s=:s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "rejected"},
    )

    # Fetch all offers for this request
    offers = service_offers_table.query(
        IndexName="request_id-index",
        KeyConditionExpression=Key("request_id").eq(request_id),
    ).get("Items", [])

    # If other providers are still deciding, stop here
    if any(o["status"] == "offered" for o in offers):
        return {"success": True, "message": "Offer rejected"}

    req = service_requests_table.get_item(
        Key={"request_id": request_id}
    ).get("Item")

    if not req:
        return {"success": False}, 404

    # Max rounds reached → expire
    if req["offer_round"] >= MAX_OFFER_ROUNDS:
        service_requests_table.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET #s=:s, updated_at=:u",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "expired", ":u": now_iso()},
        )
        return {"success": True, "message": "Request expired"}

    # Exclude already-contacted providers
    contacted = {o["provider_id"] for o in offers}

    ranked = get_ranked_providers(
        req["service_type"],
        req["address"],
    )

    fresh_providers = [
        pid for pid, _ in ranked if pid not in contacted
    ]

    # No providers left → expire
    if not fresh_providers:
        service_requests_table.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET #s=:s, updated_at=:u",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "expired", ":u": now_iso()},
        )
        return {"success": True, "message": "Request expired"}

    # Offer next batch
    offer_request_to_providers(req, fresh_providers[:3])

    return {
        "success": True,
        "message": "Offer rejected, re-offered to next providers",
    }


# =========================================================
# START JOB
# =========================================================
@provider_bp.route("/jobs/<request_id>/start", methods=["POST"])
@login_required
def start_job(request_id):
    service_requests_table.update_item(
        Key={"request_id": request_id},
        UpdateExpression="SET #s=:s, updated_at=:u",
        ConditionExpression="assigned_provider_id=:pid AND #s=:prev",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "in_progress",
            ":prev": "accepted",
            ":pid": current_user.id,
            ":u": now_iso(),
        },
    )
    return {"success": True}


# =========================================================
# COMPLETE JOB
# =========================================================
@provider_bp.route("/jobs/<request_id>/complete", methods=["POST"])
@login_required
def complete_job(request_id):
    service_requests_table.update_item(
        Key={"request_id": request_id},
        UpdateExpression="SET #s=:s, updated_at=:u",
        ConditionExpression="assigned_provider_id=:pid AND #s=:prev",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "completed",
            ":prev": "in_progress",
            ":pid": current_user.id,
            ":u": now_iso(),
        },
    )
    return {"success": True}
