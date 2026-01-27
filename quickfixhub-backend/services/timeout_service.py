from store import SERVICE_REQUESTS, SERVICE_OFFERS
from utils.time_utils import now_iso
from services.offer_service import offer_request_to_providers, MAX_OFFER_ROUNDS
from services.provider_matcher import get_ranked_providers


def handle_expired_offers():
    for request in SERVICE_REQUESTS.values():

        # Only process requests currently in offered state
        if request.status != "offered":
            continue

        # Only act if offer has actually expired
        if not request.offer_expires_at or request.offer_expires_at >= now_iso():
            continue

        # ------------------------------------
        # Expire all currently open offers
        # ------------------------------------

        for offer in SERVICE_OFFERS:
            if offer.request_id == request.id and offer.status == "offered":
                offer.status = "expired"
        # ------------------------------------
        # Stop if max rounds already reached
        # ------------------------------------
        if request.offer_round >= MAX_OFFER_ROUNDS:
            request.status = "expired"
            request.updated_at = now_iso()
            continue

        # ------------------------------------
        # Collect previously contacted providers
        # (accepted / rejected / ignored / expired)
        # ------------------------------------
        previously_contacted = {
            offer.provider_id
            for offer in SERVICE_OFFERS
            if offer.request_id == request.id
        }

        # ------------------------------------
        # Find eligible providers
        # ------------------------------------
        ranked = get_ranked_providers(
            request.service_type,
            request.address
        )

        # Exclude already contacted providers
        fresh_providers = [
            pid for pid, _ in ranked
            if pid not in previously_contacted
        ]

        # ------------------------------------
        # No providers left → EXPIRE REQUEST
        # ------------------------------------
        if not fresh_providers:
            request.status = "expired"
            request.updated_at = now_iso()
            continue

        # ------------------------------------
        # Offer to next batch (max 3)
        # ------------------------------------
        offer_request_to_providers(
            request,
            fresh_providers[:3]
        )
