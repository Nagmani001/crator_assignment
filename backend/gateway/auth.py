import datetime as dt

import jwt
from django.conf import settings
from rest_framework import authentication, exceptions
from rest_framework.request import Request

from .models import Agent


def current_agent(request: Request) -> Agent:
    agent = getattr(request, "agent", None)
    if agent is None:
        raise exceptions.NotAuthenticated("no authenticated agent on request")
    return agent


def issue_token(agent: Agent) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    exp = now + dt.timedelta(minutes=settings.JWT_TTL_MINUTES)
    payload = {
        "kind": "agent",
        "agent_id": str(agent.id),
        "agent_name": agent.name,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    return {"token": token, "expires_in": settings.JWT_TTL_MINUTES * 60}


def issue_admin_token(user) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    exp = now + dt.timedelta(minutes=settings.JWT_TTL_MINUTES)
    payload = {
        "kind": "admin",
        "admin_id": user.id,
        "admin_username": user.username,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    return {"token": token, "expires_in": settings.JWT_TTL_MINUTES * 60}


def _decode(token):
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise exceptions.AuthenticationFailed("token expired")
    except jwt.InvalidTokenError:
        raise exceptions.AuthenticationFailed("invalid token")


class JWTAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith(self.keyword + " "):
            return None
        token = header.split(" ", 1)[1].strip()
        payload = _decode(token)

        if payload.get("kind") == "admin":
            raise exceptions.AuthenticationFailed("agent token required")

        agent_id = payload.get("agent_id")
        try:
            agent = Agent.objects.get(id=agent_id, is_active=True)
        except Agent.DoesNotExist:
            raise exceptions.AuthenticationFailed("agent unknown or inactive")

        request.agent = agent
        return (agent, token)

    def authenticate_header(self, request):
        return self.keyword


class AdminJWTAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith(self.keyword + " "):
            return None
        token = header.split(" ", 1)[1].strip()
        payload = _decode(token)

        if payload.get("kind") != "admin":
            raise exceptions.AuthenticationFailed("admin token required")

        from django.contrib.auth.models import User
        try:
            user = User.objects.get(
                id=payload["admin_id"], is_staff=True, is_active=True
            )
        except (User.DoesNotExist, KeyError):
            raise exceptions.AuthenticationFailed("admin unknown or inactive")
        return (user, token)

    def authenticate_header(self, request):
        return self.keyword
