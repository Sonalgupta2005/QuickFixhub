from models.service_request import ServiceRequest
from models.service_offer import ServiceOffer

SERVICE_REQUESTS = {}     # request_id -> ServiceRequest
SERVICE_OFFERS = []       # list[ServiceOffer]
PROVIDER_PROFILES = {}    # provider_id -> ProviderProfile
