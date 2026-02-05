from boto3.dynamodb.conditions import Key
from db.dynamodb import provider_profiles_table, service_requests_table

MAX_ACTIVE_JOBS = 3


# -------------------------------------------------
# COUNT ACTIVE JOBS (DynamoDB)
# -------------------------------------------------
def count_active_jobs(provider_id):
    """
    Counts accepted + in_progress jobs for a provider
    """

    # ⚠️ Requires GSI: assigned_provider_id-index
    res = service_requests_table.query(
        IndexName="assigned_provider_id-index",
        KeyConditionExpression=Key("assigned_provider_id").eq(provider_id)
    )

    count = 0
    for item in res.get("Items", []):
        if item["status"] in ["accepted", "in_progress"]:
            count += 1

    return count


# -------------------------------------------------
# ELIGIBLE PROVIDERS
# -------------------------------------------------
def get_eligible_providers(service_type, address):
    """
    Filters providers based on:
    - service type
    - active job load
    """

    eligible = []

    res = provider_profiles_table.scan()

    for profile in res.get("Items", []):

        provider_id = profile["provider_id"]

        # if not profile.get("is_verified", False):
        #     continue

        if service_type not in profile.get("service_types", []):
            continue

        if count_active_jobs(provider_id) >= MAX_ACTIVE_JOBS:
            continue

        eligible.append(provider_id)

    return eligible


# -------------------------------------------------
# RANK PROVIDERS
# -------------------------------------------------
def rank_providers(provider_ids):
    ranked = []

    for pid in provider_ids:
        active_jobs = count_active_jobs(pid)
        score = (MAX_ACTIVE_JOBS - active_jobs) * 10
        ranked.append((pid, score))

    return sorted(ranked, key=lambda x: x[1], reverse=True)


# -------------------------------------------------
# FINAL ENTRY POINT
# -------------------------------------------------
def get_ranked_providers(service_type, address):
    eligible = get_eligible_providers(service_type, address)
    return rank_providers(eligible)
