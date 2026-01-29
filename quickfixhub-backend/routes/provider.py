from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from store import SERVICE_REQUESTS, SERVICE_OFFERS
from services.offer_service import get_active_offer, expire_other_offers,offer_request_to_providers, MAX_OFFER_ROUNDS
from services.provider_matcher import get_ranked_providers
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
            and req.status in ["accepted", "in_progress", "completed"]
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
    """
    Provider rejects an offered service request.
    Immediately re-evaluates request state.
    """

    # 🔒 Only providers can reject
    if current_user.role != "provider":
        return {"success": False, "message": "Forbidden"}, 403

    # 🔍 Find active offer
    offer = next(
        (
            o for o in SERVICE_OFFERS
            if o.request_id == request_id
            and o.provider_id == current_user.id
            and o.status == "offered"
        ),
        None
    )

    if not offer:
        return {"success": False, "message": "No active offer"}, 400

    req = SERVICE_REQUESTS.get(request_id)
    if not req:
        return {"success": False, "message": "Request not found"}, 404

    # ---------------------------------
    # ✅ MARK OFFER AS REJECTED
    # ---------------------------------
    offer.status = "rejected"

    # ---------------------------------
    # 🔎 CHECK FOR OTHER ACTIVE OFFERS
    # ---------------------------------
    active_offers = [
        o for o in SERVICE_OFFERS
        if o.request_id == request_id and o.status == "offered"
    ]

    if active_offers:
        # Still waiting on other providers
        return {"success": True, "message": "Offer rejected"}

    # ---------------------------------
    # 🔁 NO ACTIVE OFFERS LEFT → TRY RE-OFFER
    # ---------------------------------
    previously_contacted = {
        o.provider_id
        for o in SERVICE_OFFERS
        if o.request_id == request_id
    }

    if req.offer_round >= MAX_OFFER_ROUNDS:
        req.status = "expired"
        req.updated_at = now_iso()
        return {
            "success": True,
            "message": "Request expired (max rounds reached)"
        }

    ranked = get_ranked_providers(
        req.service_type,
        req.address,
    )
    fresh_providers = [
            pid for pid, _ in ranked
            if pid not in previously_contacted
        ]

    if not fresh_providers:
        # 🚨 NO PROVIDERS LEFT — THIS WAS YOUR BUG
        req.status = "expired"
        req.updated_at = now_iso()
        return {
            "success": True,
            "message": "Request expired (no providers available)"
        }

    # ---------------------------------
    # ✅ OFFER NEXT BATCH
    # ---------------------------------
    next_batch = [pid for pid, _ in ranked[:3]]
    offer_request_to_providers(req, next_batch)

    return {
        "success": True,
        "message": "Offer rejected, next providers notified"
    }



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
