class ProviderProfile:
    def __init__(
        self,
        provider_id,
        service_types,
        address,
        is_verified,
        created_at
    ):
        self.provider_id = provider_id        # FK → User.id
        self.service_types = service_types    # list[str]
        self.address = address                # REQUIRED
        self.is_verified = is_verified        # False initially
        self.created_at = created_at

    def to_dict(self):
        return {
            "providerId": self.provider_id,
            "serviceTypes": self.service_types,
            "address": self.address,
            "isVerified": self.is_verified,
            "createdAt": self.created_at
        }
