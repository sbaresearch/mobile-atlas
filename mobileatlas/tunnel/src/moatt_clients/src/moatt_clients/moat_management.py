import logging

import requests
from moatt_types.connect import Token
from pydantic import ValidationError

from . import types

LOGGER = logging.getLogger(__name__)


def register_probe(api_url: str, mam_token: Token, tunnel_token: Token) -> Token:
    """Register a client using valid management server and SIM tunnel tokens.

    Parameters
    ----------
    api_url
        API base URL (e.g., 'https://example.com/api/v1')
    mam_token
        MobileAtlas probe API access token (the token used to register the probe)
    tunnel_token
        MobileAtlas SIM tunnel token

    Returns
    -------
    The session token returned by the server
    """
    url = f"{api_url}/tunnel/probe"

    headers = {"Authorization": f"Bearer {mam_token.as_base64()}"}
    r = requests.post(url, headers=headers, json={"token": tunnel_token.as_base64()})

    try:
        r.raise_for_status()
    except requests.HTTPError:
        LOGGER.error(
            f"Registration failed. Received {r.status_code} status from server."
        )
        raise

    try:
        resp = types.RegistrationResponse.model_validate_json(r.text)
        return Token(resp.session_token)
    except (ValidationError, ValueError):
        LOGGER.exception("Received a malformed session_token")
        raise


def deregister_probe(api_url: str, session_token: Token) -> bool:
    """Deregister a probe session token.

    Parameters
    ----------
    api_url
        API base URL (e.g., 'https://example.com/api/v1')
    session_token
        Session token to deregister.

    Returns
    -------
    Whether deregistration was successful.
    """
    return _deregister(f"{api_url}/tunnel/probe", session_token)


def register_provider(api_url: str, tunnel_token: Token) -> Token:
    """Register a SIM provider using a valid SIM tunnel token.

    Parameters
    ----------
    api_url
        API base URL (e.g., 'https://example.com/api/v1')
    tunnel_token
        MobileAtlas SIM tunnel token

    Returns
    -------
    The session token returned by the server
    """
    url = f"{api_url}/tunnel/provider"

    headers = {"Authorization": f"Bearer {tunnel_token.as_base64()}"}
    r = requests.post(url, headers=headers)

    try:
        r.raise_for_status()
    except requests.HTTPError:
        LOGGER.error(
            f"Registration failed. Received {r.status_code} status from server."
        )
        raise

    try:
        resp = types.RegistrationResponse.model_validate_json(r.text)
        return Token(resp.session_token)
    except (ValidationError, ValueError):
        LOGGER.exception("Received a malformed session_token")
        raise


def deregister_provider(api_url: str, session_token: Token) -> bool:
    """Deregister a provider session token.

    Parameters
    ----------
    api_url
        API base URL (e.g., 'https://example.com/api/v1')
    session_token
        Session token to deregister.

    Returns
    -------
    Whether deregistration was successful.
    """

    return _deregister(f"{api_url}/tunnel/provider", session_token)


def _deregister(url: str, session_token: Token) -> bool:
    r = requests.delete(url, json=session_token.as_base64())

    if r.status_code != requests.codes.ok:
        return False
    else:
        return True
