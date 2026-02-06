from datetime import datetime, timedelta, timezone
from boto3.dynamodb.conditions import Key

from utils.time_utils import now_iso
from db.dynamodb import service_offers_table, service_requests_table


OFFER_TIMEOUT_MINUTES = 15
MAX_OFFER_ROUNDS = 3


# ==========================================================
# CREATE OFFER (PK: request_id, SK: provider_id)
# ==========================================================
def create_offer(request_id, provider_id):
    item = {
        "request_id": request_id,
        "provider_id": provider_id,
        "status": "offered",
        "created_at": now_iso(),
    }

    service_offers_table.put_item(Item=item)
    return item


# ==========================================================
# GET ACTIVE OFFER
# ==========================================================
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


# ==========================================================
# EXPIRE OTHER OFFERS (when one provider accepts)
# ==========================================================
def expire_other_offers(request_id, accepted_provider_id):
    res = service_offers_table.query(
        KeyConditionExpression=Key("request_id").eq(request_id)
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


# ==========================================================
# OFFER REQUEST TO PROVIDERS
# ==========================================================
def offer_request_to_providers(service_request_item, provider_ids):
    """
    service_request_item must be DynamoDB dict item,
    not local object.
    """

    expires_at = (
        datetime.now(timezone.utc) +
        timedelta(minutes=OFFER_TIMEOUT_MINUTES)
    ).isoformat()

    # Create offers
    for provider_id in provider_ids:
        create_offer(service_request_item["request_id"], provider_id)

    # Update request state in DynamoDB
    service_requests_table.update_item(
        Key={"request_id": service_request_item["request_id"]},
        UpdateExpression="""
            SET #s = :s,
                offer_round = offer_round + :inc,
                offer_expires_at = :exp,
                updated_at = :u
        """,
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":s": "offered",
            ":inc": 1,
            ":exp": expires_at,
            ":u": now_iso()
        }
    )
