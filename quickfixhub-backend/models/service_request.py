class ServiceRequest:
    def __init__(
        self,
        id,
        user_id,
        user_name,
        user_email,
        user_phone,
        service_type,
        description,
        address,
        preferred_date,
        preferred_time,
        status,                     # pending | offered | accepted | in_progress | completed | cancelled | expired
        assigned_provider_id,       # provider user_id | None
        created_at,                 # ISO UTC
        updated_at,                 # ISO UTC
        provider_name=None,         # provider name | None
        provider_phone=None,        # provider phone | None
        provider_email=None,        # provider email | None
        offer_round=0,              # int
        offer_expires_at=None,      # ISO UTC | None
    ):
        self.id = id
        self.user_id = user_id
        self.user_name = user_name
        self.user_email = user_email
        self.user_phone = user_phone
        self.service_type = service_type
        self.description = description
        self.address = address
        self.preferred_date = preferred_date
        self.preferred_time = preferred_time
        self.status = status
        self.assigned_provider_id = assigned_provider_id 
        self.provider_name = provider_name
        self.provider_phone = provider_phone
        self.provider_email = provider_email
        self.offer_round = offer_round
        self.offer_expires_at = offer_expires_at
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "userName": self.user_name,
            "userEmail": self.user_email,
            "userPhone": self.user_phone,
            "serviceType": self.service_type,
            "description": self.description,
            "address": self.address,
            "preferredDate": self.preferred_date,
            "preferredTime": self.preferred_time,
            "status": self.status,
            "assignedProviderId": self.assigned_provider_id,
            "providerName": self.provider_name,
            "providerPhone": self.provider_phone,
            "providerEmail": self.provider_email,
            "offerRound": self.offer_round,
            "offerExpiresAt": self.offer_expires_at,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at
        }
