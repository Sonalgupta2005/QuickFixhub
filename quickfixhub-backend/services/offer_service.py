from datetime import datetime, timedelta, timezone
from utils.time_utils import now_iso
from db.dynamodb import service_offers_table

OFFER_TIMEOUT_MINUTES = 15
MAX_OFFER_ROUNDS = 3


def create_offer(request_id, provider_id):
    item = {
        "request_id": request_id,
        "provider_id": provider_id,
        "status": "offered",
        "created_at": now_iso(),
    }

    service_offers_table.put_item(Item=item)
    return item


def get_active_offer(request_id, provider_id):
    res = service_offers_table.get_item(
        Key={
            "request_id": request_id,
            "provider_id": provider_id
        }
    )

    item = res.get("Item")
    if item and item["status"] == "offered":
        return item
    return None


def expire_other_offers(request_id, accepted_provider_id):
    res = service_offers_table.query(
        KeyConditionExpression="request_id = :rid",
        ExpressionAttributeValues={":rid": request_id}
    )

    for offer in res.get("Items", []):
        if (
            offer["provider_id"] != accepted_provider_id
            and offer["status"] == "offered"
        ):
            service_offers_table.update_item(
                Key={
                    "request_id": request_id,
                    "provider_id": offer["provider_id"]
                },
                UpdateExpression="SET #s = :expired",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":expired": "expired"}
            )


def offer_request_to_providers(service_request, provider_ids):
    expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=OFFER_TIMEOUT_MINUTES)
    ).isoformat()

    for provider_id in provider_ids:
        create_offer(service_request.id, provider_id)

    # Update request state
    service_request.status = "offered"
    service_request.offer_round += 1
    service_request.offer_expires_at = expires_at
    service_request.updated_at = now_iso()
