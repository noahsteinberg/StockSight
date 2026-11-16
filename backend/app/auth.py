"""Auth0 access-token validation; identity never comes from request bodies."""

from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyCookie, HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientConnectionError, PyJWKClientError

from app.config import Settings
from app.sessions import COOKIE

bearer = HTTPBearer(auto_error=False, scheme_name="Auth0AccessToken")
session_cookie = APIKeyCookie(
    name=COOKIE, auto_error=False, scheme_name="StockSightSession"
)


def unauthorized():
    return HTTPException(
        401,
        detail={"code": "UNAUTHENTICATED", "message": "Sign in again to continue."},
        headers={"WWW-Authenticate": "Bearer"},
    )


@dataclass(frozen=True)
class Principal:
    issuer: str
    subject: str


class TokenVerifier:
    def __init__(self, settings: Settings):
        self.issuer = f"https://{settings.auth0_domain}/"
        self.audience = settings.auth0_audience
        self.jwks = PyJWKClient(
            self.issuer + ".well-known/jwks.json", lifespan=300, timeout=5
        )

    def verify(self, token: str) -> Principal:
        try:
            if len(token) > 16384:
                raise unauthorized()
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not header.get("kid"):
                raise unauthorized()
            key = self.jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                leeway=10,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
            subject = claims["sub"]
            if (
                not isinstance(subject, str)
                or not subject.strip()
                or len(subject) > 255
                or subject.endswith("@clients")
                or claims.get("gty") == "client-credentials"
            ):
                raise unauthorized()
            return Principal(issuer=self.issuer, subject=subject)
        except (PyJWKClientConnectionError, jwt.PyJWKError, jwt.PyJWKSetError):
            raise HTTPException(
                503,
                detail={
                    "code": "AUTH_UNAVAILABLE",
                    "message": "Sign-in verification is temporarily unavailable.",
                },
            ) from None
        except (jwt.InvalidTokenError, PyJWKClientError):
            raise unauthorized() from None


def bearer_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    verifier = request.app.state.token_verifier
    if verifier is None:
        raise HTTPException(
            503,
            detail={
                "code": "AUTH_NOT_CONFIGURED",
                "message": "Account sign-in is not configured yet.",
            },
        )
    return verifier.verify(credentials.credentials)


def current_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    cookie: Annotated[str | None, Depends(session_cookie)],
) -> Principal:
    if request.headers.get("authorization") is not None:
        # An explicitly invalid bearer token must never fall back to a cookie.
        return bearer_principal(request, credentials)
    from app.sessions import read_session, require_session_request

    if not cookie:
        raise unauthorized()
    session = read_session(request)
    if session is None:
        raise unauthorized()
    require_session_request(request, session)
    return Principal(issuer=session["issuer"], subject=session["subject"])
