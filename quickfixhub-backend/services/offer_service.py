from datetime import datetime, timedelta,timezone
from models.service_offer import ServiceOffer
from utils.time_utils import now_iso
from store import SERVICE_OFFERS

OFFER_TIMEOUT_MINUTES = 15
MAX_OFFER_ROUNDS = 3


def create_offer(request_id, provider_id):
    
    offer = ServiceOffer(
        request_id=request_id,
        provider_id=provider_id,
        status="offered",
        created_at=now_iso()
    )
    SERVICE_OFFERS.append(offer)
    return offer


def get_active_offer(request_id, provider_id):
    for offer in SERVICE_OFFERS:
        if (
            offer.request_id == request_id
            and offer.provider_id == provider_id
            and offer.status == "offered"
        ):
            return offer
    return None


def expire_other_offers(request_id, accepted_provider_id):
    for offer in SERVICE_OFFERS:
        if offer.request_id == request_id and offer.provider_id != accepted_provider_id:
            if offer.status == "offered":
                offer.status = "expired"


def offer_request_to_providers(service_request, provider_ids):
    expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=OFFER_TIMEOUT_MINUTES)
    ).isoformat()
    
    for provider_id in provider_ids:
        create_offer(service_request.id, provider_id)
        # 🔔 SNS notification hook (later)

    service_request.status = "offered"
    service_request.offer_round += 1
    service_request.offer_expires_at = expires_at
    service_request.updated_at = now_iso()
