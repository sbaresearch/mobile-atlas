import json
import logging

from typing import Optional
from tunnelTypes.connect import Imsi, Iccid, Token, IdentifierType

logger = logging.getLogger(__name__)

def read_tokens(filename="tokens.json"):
    with open(filename, "r") as f:
        return list(map(lambda x: Token(bytes.fromhex(x)), json.load(f)))

def read_provider_mapping(filename="prov_map.json"):
    with open(filename, "r") as f:
        res = json.load(f)
    return res

valid_tokens = read_tokens()
sim_provider_mapping = read_provider_mapping()

class AuthError(Exception):
    def __init__(self):
        super().__init__("Authorisation failure.")

def valid(token: Token) -> bool:
    return token in valid_tokens

def allowed_sim_request(token: Token, identifier: Imsi | Iccid) -> bool:
    if not valid(token):
        raise AuthError

    id(identifier)
    return valid(token)

def find_provider(token: Token, identifier: Imsi | Iccid) -> Optional[int]:
    if not valid(token) or not allowed_sim_request(token, identifier):
        raise AuthError

    if identifier.identifier_type() == IdentifierType.Imsi:
        return sim_provider_mapping["imsi"].get(identifier.imsi)
    else:
        return sim_provider_mapping["iccid"].get(identifier.iccid)
