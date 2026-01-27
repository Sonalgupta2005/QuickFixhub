from flask_login import UserMixin

class User(UserMixin):
    def __init__(self,name, id, email, role, phone, created_at):
        self.id = id
        self.name = name
        self.email = email
        self.role = role
        self.phone = phone
        self.created_at = created_at

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "phone": self.phone,
            "createdAt": self.created_at
        }
