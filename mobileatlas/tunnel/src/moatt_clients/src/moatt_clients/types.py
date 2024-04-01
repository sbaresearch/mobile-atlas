from pydantic import Base64Bytes, BaseModel


class RegistrationResponse(BaseModel):
    session_token: Base64Bytes
