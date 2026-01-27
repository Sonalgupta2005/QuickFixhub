class ServiceOffer:
    def __init__(
        self,
        request_id,
        provider_id,
        status,         # offered | accepted | rejected | expired
        created_at
    ):
        self.request_id = request_id
        self.provider_id = provider_id
        self.status = status
        self.created_at = created_at

    def to_dict(self):
        return {
            "requestId": self.request_id,
            "providerId": self.provider_id,
            "status": self.status,
            "createdAt": self.created_at
        }
