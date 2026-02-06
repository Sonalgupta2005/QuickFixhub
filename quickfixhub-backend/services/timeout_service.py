from boto3.dynamodb.conditions import Key
from db.dynamodb import service_requests_table, service_offers_table
from utils.time_utils import now_iso
from services.offer_service import offer_request_to_providers, MAX_OFFER_ROUNDS
from services.provider_matcher import get_ranked_providers


def handle_expired_offers():

    res = service_requests_table.scan()

    for request in res.get("Items", []):

        if request["status"] != "offered":
            continue

        if (
            not request.get("offer_expires_at")
            or request["offer_expires_at"] >= now_iso()
        ):
            continue

        request_id = request["request_id"]

        # -------------------------------------------------
        # 1️⃣ Expire all open offers
        # -------------------------------------------------
        offers = service_offers_table.query(
            KeyConditionExpression=Key("request_id").eq(request_id)
        ).get("Items", [])

        for offer in offers:
            if offer["status"] == "offered":
                service_offers_table.update_item(
                    Key={
                        "request_id": request_id,
                        "provider_id": offer["provider_id"]
                    },
                    UpdateExpression="SET #s = :expired",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={":expired": "expired"}
                )

        # -------------------------------------------------
        # 2️⃣ Max rounds check
        # -------------------------------------------------
        if request["offer_round"] >= MAX_OFFER_ROUNDS:
            service_requests_table.update_item(
                Key={"request_id": request_id},
                UpdateExpression="SET #s = :expired, updated_at = :now",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":expired": "expired",
                    ":now": now_iso()
                }
            )
            continue

        # -------------------------------------------------
        # 3️⃣ Exclude previously contacted providers
        # -------------------------------------------------
        previously_contacted = {
            o["provider_id"] for o in offers
        }

        ranked = get_ranked_providers(
            request["service_type"],
            request["address"]
        )

        fresh_providers = [
            pid for pid, _ in ranked
            if pid not in previously_contacted
        ]

        # -------------------------------------------------
        # 4️⃣ No providers left → expire
        # -------------------------------------------------
        if not fresh_providers:
            service_requests_table.update_item(
                Key={"request_id": request_id},
                UpdateExpression="SET #s = :expired, updated_at = :now",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":expired": "expired",
                    ":now": now_iso()
                }
            )
            continue

        # -------------------------------------------------
        # 5️⃣ Re-offer next batch
        # -------------------------------------------------
        offer_request_to_providers(
            request,
            fresh_providers[:3]
        )
