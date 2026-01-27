from store import PROVIDER_PROFILES, SERVICE_REQUESTS

MAX_ACTIVE_JOBS = 3


def count_active_jobs(provider_id):
    count = 0
    for req in SERVICE_REQUESTS.values():
        if (
            req.assigned_provider_id == provider_id
            and req.status in ["accepted", "in_progress"]
        ):
            count += 1
    return count


def get_eligible_providers(service_type, address):
    eligible = []

    for provider_id, profile in PROVIDER_PROFILES.items():
        # if not profile.is_verified:
        #     continue
        if service_type not in profile.service_types:
            continue
        if count_active_jobs(provider_id) >= MAX_ACTIVE_JOBS:
            continue

        eligible.append(provider_id)

    return eligible


def rank_providers(provider_ids):
    
    ranked = []

    for pid in provider_ids:
        score = 0
        score += (MAX_ACTIVE_JOBS - count_active_jobs(pid)) * 10
        ranked.append((pid, score))

    return sorted(ranked, key=lambda x: x[1], reverse=True)


def get_ranked_providers(service_type, address):
    eligible = get_eligible_providers(service_type, address)

    return rank_providers(eligible)
