from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models.service_request import ServiceRequest
import uuid
from services.timeout_service import handle_expired_offers
from utils.time_utils import now_iso
from store import SERVICE_REQUESTS, SERVICE_OFFERS
from services.provider_matcher import get_ranked_providers
from services.offer_service import offer_request_to_providers

service_bp = Blueprint("service", __name__)


# ==========================================================
# CREATE SERVICE REQUEST (WLA-CORRECT FLOW)
# ==========================================================
@service_bp.route("/requests", methods=["POST"])
@login_required
def create_service_request():
    """
    Workflow:
    1. Create request as PENDING
    2. Match providers
    3. If providers found -> OFFERED
    4. If no providers -> EXPIRED
    """

    data = request.get_json()

    # -------------------------
    # REQUIRED FIELD VALIDATION
    # -------------------------
    required_fields = [
        "serviceType",
        "description",
        "address",
        "preferredDate"
    ]

    for field in required_fields:
        if not data.get(field):
            return jsonify({
                "success": False,
                "message": f"{field} is required"
            }), 400

    now = now_iso()

    # -------------------------
    # CREATE REQUEST (PENDING)
    # -------------------------
    request_obj = ServiceRequest(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        user_name=current_user.name,
        user_email=current_user.email,
        user_phone=current_user.phone,
        service_type=data["serviceType"],
        description=data["description"],
        address=data["address"],
        preferred_date=data["preferredDate"],
        preferred_time=data.get("preferredTime"),
        status="pending",
        assigned_provider_id=None,
        offer_round=0,
        offer_expires_at=None,
        created_at=now,
        updated_at=now
    )

    SERVICE_REQUESTS[request_obj.id] = request_obj

    # -------------------------
    # MATCH PROVIDERS
    # -------------------------
    ranked_providers = get_ranked_providers(
        service_type=request_obj.service_type,
        address=request_obj.address
    )

    provider_ids = [pid for pid, _ in ranked_providers[:3]]
    # -------------------------
    # OFFER OR EXPIRE
    # -------------------------
    if provider_ids:
        offer_request_to_providers(request_obj, provider_ids)
    else:
        # No providers available
        request_obj.status = "expired"
        request_obj.updated_at = now

    return jsonify({
        "success": True,
        "request": request_obj.to_dict()
    }), 201


# ==========================================================
# HOMEOWNER: GET MY REQUESTS
# ==========================================================
@service_bp.route("/my-requests", methods=["GET"])
@login_required
def get_my_requests():
    """
    Returns all requests created by the logged-in homeowner.
    """
    handle_expired_offers()

    requests = [
        req.to_dict()
        for req in SERVICE_REQUESTS.values()
        if req.user_id == current_user.id
    ]

    return jsonify({
        "success": True,
        "requests": requests
    })


# ==========================================================
# ADMIN / PROVIDER: GET ALL REQUESTS (TEMP)
# ==========================================================
@service_bp.route("/all", methods=["GET"])
@login_required
def get_all_requests():
    """
    Returns all requests.
    Role enforcement will be added later.
    """

    return jsonify({
        "success": True,
        "requests": [req.to_dict() for req in SERVICE_REQUESTS.values()]
    })

@service_bp.route("/requests/<request_id>/cancel", methods=["POST"])
@login_required
def cancel_service_request(request_id):
    """
    Homeowner cancels a service request.
    Allowed only before work starts.
    """

    req = SERVICE_REQUESTS.get(request_id)

    if not req:
        return jsonify({
            "success": False,
            "message": "Service request not found"
        }), 404

    if req.user_id != current_user.id:
        return jsonify({
            "success": False,
            "message": "You are not allowed to cancel this request"
        }), 403

    if req.status in ["in_progress", "completed", "expired", "cancelled"]:
        return jsonify({
            "success": False,
            "message": f"Cannot cancel a request that is '{req.status}'"
        }), 400

    req.status = "cancelled"
    req.updated_at = now_iso()
    req.offer_expires_at = None

    # ---------------------------------
    # ✅ EXPIRE ALL OFFERS
    # ---------------------------------
    for offer in SERVICE_OFFERS:
        if offer.request_id == request_id and offer.status == "offered":
            offer.status = "expired"

    return jsonify({
        "success": True,
        "message": "Service request cancelled successfully",
        "request": req.to_dict()
    })