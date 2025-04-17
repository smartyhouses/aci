import time
import httpx
from typing import Any, cast

from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App
from fastapi import Request
from starlette.responses import RedirectResponse

from aipolabs.common.exceptions import LinkedAccountOAuth2Error
from aipolabs.common.logging_setup import get_logger
from aipolabs.common.schemas.security_scheme import OAuth2SchemeCredentials

logger = get_logger(__name__)

"""
Mostly a wrapper around authlib oauth2 features.
Having a wrapper because for some function we need do some special overrides.
And potentially easier for testing and refactoring if later we want to switch to a different oauth2 library.
"""

# TODO: oauth2 related code smells bad

def create_oauth2_client(
    name: str,
    client_id: str,
    client_secret: str,
    scope: str,
    prompt: str = "consent",
    code_challenge_method: str = "S256",
    access_type: str = "offline",
    token_endpoint_auth_method: str | None = None,
    authorize_url: str | None = None,
    access_token_url: str | None = None,
    refresh_token_url: str | None = None,
    server_metadata_url: str | None = None,
) -> StarletteOAuth2App:
    """
    Create an OAuth2 client for the given app.
    """
    client_kwargs = {
        "scope": scope,
        "prompt": prompt,
        "code_challenge_method": code_challenge_method,
    }

    # Only add token_endpoint_auth_method if provided
    if token_endpoint_auth_method:
        client_kwargs["token_endpoint_auth_method"] = token_endpoint_auth_method

    # Special handling for LinkedIn
    if name == "LINKEDIN":
        # LinkedIn requires these specific settings
        client_kwargs["token_endpoint_auth_method"] = "client_secret_post"

    oauth_client = OAuth().register(
        name=name,
        client_id=client_id,
        client_secret=client_secret,
        client_kwargs=client_kwargs,
        # Note: usually if server_metadata_url (e.g., google's discovery doc https://accounts.google.com/.well-known/openid-configuration)
        # is provided, the other endpoints are not needed.
        authorize_url=authorize_url,
        authorize_params={"access_type": access_type},
        access_token_url=access_token_url,
        refresh_token_url=refresh_token_url,
        server_metadata_url=server_metadata_url,
    )
    return cast(StarletteOAuth2App, oauth_client)

async def authorize_redirect(
    oauth2_client: StarletteOAuth2App, request: Request, redirect_uri: str
) -> RedirectResponse:
    return cast(RedirectResponse, await oauth2_client.authorize_redirect(request, redirect_uri))

async def create_authorization_url(oauth2_client: StarletteOAuth2App, redirect_uri: str) -> dict:
    return cast(dict, await oauth2_client.create_authorization_url(redirect_uri))

async def authorize_access_token(
    oauth2_client: StarletteOAuth2App,
    request: Request,
    **kwargs: Any,
) -> dict:
    return cast(dict, await oauth2_client.authorize_access_token(request, **kwargs))

async def refresh_access_token(oauth2_client: StarletteOAuth2App, refresh_token: str) -> dict:
    return cast(
        dict,
        await oauth2_client.fetch_access_token(
            grant_type="refresh_token", refresh_token=refresh_token
        ),
    )

async def authorize_access_token_without_browser_session(
    oauth2_client: StarletteOAuth2App,
    request: Request,
    redirect_uri: str,
    code_verifier: str,
    nonce: str | None = None,
    **kwargs: Any,
) -> dict:
    """
    This is a modified version of the authorize_access_token method in authlib/integrations/starlette_client/apps.py
    This is to bypass a need of browser session for oauth2 flow
    """
    logger.debug(
        "authorizing access token without browser session",
        extra={"redirect_uri": redirect_uri, "code_verifier": code_verifier},
    )
    error = request.query_params.get("error")
    if error:
        description = request.query_params.get("error_description")
        error_msg = f"account linking failed due to OAuth2 error from provider. error={error}"
        if description:
            error_msg += f", error_description={description}"
        logger.error(error_msg)
        raise LinkedAccountOAuth2Error(error_msg)

    code = request.query_params.get("code")

    # Special handling for LinkedIn - directly handle token exchange without using the OAuth client
    if oauth2_client.name == "LINKEDIN":
        logger.debug("Using LinkedIn specific token exchange method")
        return await linkedin_exchange_code_for_token(
            oauth2_client.client_id,
            oauth2_client.client_secret,
            code,
            redirect_uri,
            code_verifier
        )

    # Standard flow for other providers
    params = {
        "code": code,
        "state": request.query_params.get("state"),
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
        "grant_type": "authorization_code",
    }

    claims_options = kwargs.pop("claims_options", None)
    logger.debug(
        "fetching access token",
        extra=params,
    )
    token = cast(dict, await oauth2_client.fetch_access_token(**params, **kwargs))

    if "id_token" in token and nonce:
        userinfo = await oauth2_client.parse_id_token(
            token, nonce=nonce, claims_options=claims_options
        )
        token["userinfo"] = userinfo
    return token

async def linkedin_exchange_code_for_token(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> dict:
    """
    LinkedIn-specific function to exchange the authorization code for an access token.
    This uses direct HTTP requests following LinkedIn's documentation exactly.

    According to LinkedIn docs: https://learn.microsoft.com/zh-cn/linkedin/shared/authentication/authorization-code-flow
    """
    logger.debug("Performing LinkedIn token exchange")

    # LinkedIn requires these exact parameters for token exchange
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }

    # LinkedIn docs specify Content-Type: x-www-form-urlencoded
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }

    logger.debug(f"LinkedIn token exchange request data: {payload}")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data=payload,  # httpx will handle form encoding automatically
            headers=headers
        )

        if response.status_code != 200:
            logger.error(f"LinkedIn token exchange failed: {response.status_code}, {response.text}")
            raise LinkedAccountOAuth2Error(f"Failed to retrieve OAuth token from LinkedIn: {response.text}")

        token_data = response.json()
        logger.debug(f"LinkedIn token exchange successful: {token_data}")
        return token_data

def parse_oauth2_security_credentials(
    app_name: str, token_response: dict
) -> OAuth2SchemeCredentials:
    """
    Parse OAuth2SchemeCredentials from token response with app-specific handling.

    Args:
        app_name: Name of the app/provider (e.g., "SLACK", "GOOGLE")
        token_response: OAuth2 token response from provider

    Returns:
        OAuth2SchemeCredentials with appropriate fields set
    """
    if app_name == "SLACK":
        authed_user = token_response.get("authed_user", {})
        if not authed_user or "access_token" not in authed_user:
            logger.error(f"Invalid Slack OAuth response: {token_response}")
            raise LinkedAccountOAuth2Error("Invalid Slack OAuth response")

        return OAuth2SchemeCredentials(
            access_token=authed_user["access_token"],
            token_type=authed_user.get("token_type"),
            refresh_token=authed_user.get("refresh_token"),
            expires_at=int(time.time()) + authed_user.get("expires_in")
            if authed_user.get("expires_in")
            else None,
            raw_token_response=token_response,
        )

    # LinkedIn 特定处理
    if app_name == "LINKEDIN":
        if "access_token" not in token_response:
            logger.error(f"Invalid LinkedIn OAuth response: {token_response}")
            raise LinkedAccountOAuth2Error("Invalid LinkedIn OAuth response")

        return OAuth2SchemeCredentials(
            access_token=token_response["access_token"],
            token_type=token_response.get("token_type", "Bearer"),
            refresh_token=token_response.get("refresh_token"),
            expires_at=int(time.time()) + token_response.get("expires_in", 3600)
            if token_response.get("expires_in")
            else None,
            raw_token_response=token_response,
        )

    if "access_token" not in token_response:
        logger.error(f"Missing access token in OAuth response: {token_response}")
        raise LinkedAccountOAuth2Error("Missing access token in OAuth response")

    return OAuth2SchemeCredentials(
        access_token=token_response["access_token"],
        token_type=token_response.get("token_type"),
        expires_at=int(time.time()) + token_response["expires_in"]
        if "expires_in" in token_response
        else None,
        refresh_token=token_response.get("refresh_token"),
        raw_token_response=token_response,
    )

def rewrite_oauth2_authorization_url(app_name: str, authorization_url: str) -> str:
    """
    Rewrite OAuth2 authorization URL for specific apps that need special handling.
    Currently handles Slack's special case where user scopes and scopes need to be replaced.
    TODO: this approach is hacky and need to refactor this in the future

    Args:
        app_name: Name of the OAuth2 app (e.g., 'slack')
        authorization_url: The original authorization URL

    Returns:
        The rewritten authorization URL if needed, otherwise the original URL
    """
    if app_name == "SLACK":
        # Slack requires user scopes to be prefixed with 'user_'
        # Replace 'scope=' with 'user_scope=' and add 'scope=' with the null value
        if "scope=" in authorization_url:
            # Extract the original scope value
            scope_start = authorization_url.find("scope=") + 6
            scope_end = authorization_url.find("&", scope_start)
            if scope_end == -1:
                scope_end = len(authorization_url)
            original_scope = authorization_url[scope_start:scope_end]

            # Replace the original scope with user_scope and add scope
            new_url = authorization_url.replace(
                f"scope={original_scope}", f"user_scope={original_scope}&scope="
            )
            return new_url

    # LinkedIn 特定的 URL 处理
    if app_name == "LINKEDIN":
        # Ensure response_type=code is in the URL
        if "&response_type=code" not in authorization_url and "?response_type=code" not in authorization_url:
            separator = "&" if "?" in authorization_url else "?"
            new_url = f"{authorization_url}{separator}response_type=code"
            logger.debug(f"Added response_type to LinkedIn authorization URL: {new_url}")
            return new_url

        # 确保 scope 参数格式正确
        expected_scope = "openid profile email w_member_social"  # 与 app.json 中的 scope 保持一致
        if "scope=" not in authorization_url:
            # 如果 scope 参数缺失，手动添加
            separator = "&" if "?" in authorization_url else "?"
            new_url = f"{authorization_url}{separator}scope={expected_scope.replace(' ', '%20')}"
            logger.debug(f"Added missing scope to LinkedIn authorization URL: {new_url}")
            return new_url
        else:
            # Update the scope to match what's in app.json
            scope_start = authorization_url.find("scope=") + 6
            scope_end = authorization_url.find("&", scope_start)
            if scope_end == -1:
                scope_end = len(authorization_url)

            # Replace with the current expected scope
            new_url = authorization_url[:scope_start] + expected_scope.replace(" ", "%20") + authorization_url[scope_end:]
            logger.debug(f"Updated scope in LinkedIn authorization URL: {new_url}")
            return new_url

    return authorization_url
