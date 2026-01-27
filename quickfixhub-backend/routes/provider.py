from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from store import SERVICE_REQUESTS, SERVICE_OFFERS
from services.offer_service import get_active_offer, expire_other_offers
from utils.time_utils import now_iso

provider_bp = Blueprint("provider", __name__)

# ================================
# DASHBOARD SUMMARY
# ================================
@provider_bp.route("/dashboard/summary", methods=["GET"])
@login_required
def dashboard_summary():
    if current_user.role != "provider":
        return {"success": False}, 403

    completed = 0
    active = 0
    earnings = 0

    for req in SERVICE_REQUESTS.values():
        if req.assigned_provider_id == current_user.id:
            if req.status == "completed":
                completed += 1
                earnings += 50   # placeholder payout
            if req.status in ["accepted", "in_progress"]:
                active += 1

    return {
        "success": True,
        "stats": {
            "jobsCompleted": completed,
            "activeJobs": active,
            "rating": 4.9,     # future ratings table
            "earnings": earnings
        }
    }


# ================================
# AVAILABLE JOBS (OFFERS)
# ================================
@provider_bp.route("/jobs/available", methods=["GET"])
@login_required
def available_jobs():
    if current_user.role != "provider":
        return {"success": False}, 403

    jobs = []

    for offer in SERVICE_OFFERS:
        if offer.provider_id == current_user.id and offer.status == "offered":
            req = SERVICE_REQUESTS.get(offer.request_id)
            if req:
                jobs.append(req.to_dict())

    return {"success": True, "jobs": jobs}


# ================================
# MY JOBS (ACCEPTED / IN PROGRESS)
# ================================
@provider_bp.route("/jobs/my", methods=["GET"])
@login_required
def my_jobs():
    if current_user.role != "provider":
        return {"success": False}, 403

    jobs = []

    for req in SERVICE_REQUESTS.values():
        if (
            req.assigned_provider_id == current_user.id
            and req.status in ["accepted", "in_progress"]
        ):
            jobs.append(req.to_dict())

    return {"success": True, "jobs": jobs}


# ================================
# ACCEPT OFFER
# ================================
@provider_bp.route("/offers/<request_id>/accept", methods=["POST"])
@login_required
def accept_offer(request_id):
    offer = get_active_offer(request_id, current_user.id)
    if not offer:
        return {"success": False}, 400

    req = SERVICE_REQUESTS.get(request_id)
    if not req:
        return {"success": False}, 404

    offer.status = "accepted"
    req.status = "accepted"
    req.assigned_provider_id = current_user.id
    req.offer_expires_at = None
    req.updated_at = now_iso()

    req.provider_name = current_user.name
    req.provider_phone = current_user.phone
    req.provider_email = current_user.email

    expire_other_offers(request_id, current_user.id)

    return {"success": True}


# ================================
# REJECT OFFER
# ================================
@provider_bp.route("/offers/<request_id>/reject", methods=["POST"])
@login_required
def reject_offer(request_id):
    offer = get_active_offer(request_id, current_user.id)
    if not offer:
        return {"success": False}, 400

    offer.status = "rejected"
    return {"success": True}


# ================================
# START JOB
# ================================
@provider_bp.route("/jobs/<request_id>/start", methods=["POST"])
@login_required
def start_job(request_id):
    req = SERVICE_REQUESTS.get(request_id)

    if not req or req.assigned_provider_id != current_user.id:
        return {"success": False}, 404

    if req.status != "accepted":
        return {"success": False, "message": "Invalid state"}, 400

    req.status = "in_progress"
    req.updated_at = now_iso()

    return {"success": True}


# ================================
# COMPLETE JOB
# ================================
@provider_bp.route("/jobs/<request_id>/complete", methods=["POST"])
@login_required
def complete_job(request_id):
    req = SERVICE_REQUESTS.get(request_id)

    if not req or req.assigned_provider_id != current_user.id:
        return {"success": False}, 404

    if req.status != "in_progress":
        return {"success": False, "message": "Invalid state"}, 400

    req.status = "completed"
    req.updated_at = now_iso()

    return {"success": True}
