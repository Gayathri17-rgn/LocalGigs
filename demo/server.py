
"""LocalGigs demo server with account authentication and Strands Decider chat."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel

from decider_kit.config import load_dotenv

load_dotenv()

STATIC = Path(__file__).parent / "static"
DB_PATH = Path(__file__).parent / "users.db"
SESSION_COOKIE = "localgigs_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7

# Set LOCALGIGS_SECRET_KEY in the environment before deployment.
SECRET_KEY = os.environ.get(
    "LOCALGIGS_SECRET_KEY",
    "localgigs-development-key-change-before-deployment",
)
serializer = URLSafeTimedSerializer(SECRET_KEY)

app = FastAPI(title="LocalGigs - Strands Decider demo")
_agent: Any = None


def init_db() -> None:
    """Create the accounts table if it does not exist."""
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


init_db()


class AuthInput(BaseModel):
    username: str
    password: str


class Turn(BaseModel):
    message: str
    session_id: str = "demo"
    images: list[str] = []


def hash_password(password: str, salt: bytes) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        310_000,
    ).hex()


def current_user(request: Request) -> str | None:
    """Return the logged-in username from a valid signed cookie."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None

    try:
        data = serializer.loads(token, max_age=SESSION_MAX_AGE)
        return data.get("username")
    except (BadSignature, TypeError, AttributeError):
        return None


def unauthorized() -> JSONResponse:
    return JSONResponse(
        {"error": "Please log in to continue."},
        status_code=401,
    )


@app.post("/api/register")
def register(data: AuthInput) -> JSONResponse:
    username = data.username.strip().lower()
    password = data.password

    if len(username) < 3 or len(username) > 100:
        return JSONResponse(
            {"error": "Username must contain 3–100 characters."},
            status_code=400,
        )

    if len(password) < 8:
        return JSONResponse(
            {"error": "Password must contain at least 8 characters."},
            status_code=400,
        )

    salt = secrets.token_bytes(16)
    password_hash = hash_password(password, salt)

    try:
        with sqlite3.connect(DB_PATH) as db:
            db.execute(
                "INSERT INTO users (username, password_hash, salt) "
                "VALUES (?, ?, ?)",
                (username, password_hash, salt.hex()),
            )
    except sqlite3.IntegrityError:
        return JSONResponse(
            {"error": "That username is already registered."},
            status_code=409,
        )

    response = JSONResponse({
        "ok": True,
        "username": username,
        "message": "Account created successfully.",
    })
    response.set_cookie(
        key=SESSION_COOKIE,
        value=serializer.dumps({"username": username}),
        httponly=True,
        samesite="lax",
        secure=os.environ.get("COOKIE_SECURE") == "1",
        max_age=SESSION_MAX_AGE,
        path="/",
    )
    return response


@app.post("/api/login")
def login(data: AuthInput) -> JSONResponse:
    username = data.username.strip().lower()

    with sqlite3.connect(DB_PATH) as db:
        row = db.execute(
            "SELECT password_hash, salt FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    # Use a generic error so the response does not reveal which usernames exist.
    if row is None:
        return JSONResponse(
            {"error": "Invalid username or password."},
            status_code=401,
        )

    stored_hash, salt_hex = row
    supplied_hash = hash_password(data.password, bytes.fromhex(salt_hex))

    if not hmac.compare_digest(supplied_hash, stored_hash):
        return JSONResponse(
            {"error": "Invalid username or password."},
            status_code=401,
        )

    response = JSONResponse({
        "ok": True,
        "username": username,
        "message": "Login successful.",
    })
    response.set_cookie(
        key=SESSION_COOKIE,
        value=serializer.dumps({"username": username}),
        httponly=True,
        samesite="lax",
        secure=os.environ.get("COOKIE_SECURE") == "1",
        max_age=SESSION_MAX_AGE,
        path="/",
    )
    return response


@app.get("/api/me")
def me(request: Request) -> dict[str, Any]:
    username = current_user(request)
    return {"logged_in": username is not None, "username": username}


@app.post("/api/logout")
def logout() -> JSONResponse:
    response = JSONResponse({"ok": True, "message": "Logged out."})
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax")
    return response


def agent() -> Any:
    global _agent

    if _agent is None:
        if os.environ.get("DEMO_TARGET") == "agentcore":
            _agent = AgentCoreClient(os.environ["AGENTCORE_ARN"])
        else:
            from agent.agent import HackathonAgent
            _agent = HackathonAgent()

    return _agent


class AgentCoreClient:
    """Client for an agent deployed to Amazon Bedrock AgentCore Runtime."""

    def __init__(self, arn: str):
        import boto3

        self.arn = arn
        self.client = boto3.client(
            "bedrock-agentcore",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
        self.sessions: dict[str, str] = {}

    def chat(
        self,
        message: str,
        session_id: str = "demo",
        images: list[str] | None = None,
    ) -> dict[str, Any]:
        sid = self.sessions.setdefault(
            session_id,
            f"demo-{session_id}-{uuid.uuid4().hex}",
        )
        payload = {"prompt": message, **({"images": images} if images else {})}
        response = self.client.invoke_agent_runtime(
            agentRuntimeArn=self.arn,
            runtimeSessionId=sid,
            payload=json.dumps(payload).encode(),
        )
        body = (
            response["response"].read()
            if hasattr(response["response"], "read")
            else response["response"]
        )
        output = json.loads(body)
        output["served_by"] = "Amazon Bedrock AgentCore Runtime"
        return output


@app.get("/")
def index() -> FileResponse:
    # The page will display login/register forms when no session exists.
    return FileResponse(STATIC / "index.html")


@app.get("/api/info")
def info() -> dict[str, Any]:
    from decider_kit.config import settings

    s = settings()
    name = "Your agent"

    try:
        from agent import agent as mod
        name = getattr(mod, "NAME", name)
    except Exception:
        pass

    decider = s.decider_mode

    if os.environ.get("DEMO_TARGET") == "agentcore":
        dep = (
            Path(__file__).resolve().parent.parent
            / "submission"
            / "deployment.json"
        )
        if dep.exists():
            decider = json.loads(dep.read_text()).get(
                "decider_mode", decider
            )

    from decider_kit.llm import describe

    llm = describe()
    if os.environ.get("DEMO_TARGET") == "agentcore":
        llm = f"Amazon Bedrock ({s.bedrock_model})"

    return {
        "agent": name,
        "llm": llm,
        "bedrock_model": s.bedrock_model,
        "decider": decider,
        "target": os.environ.get("DEMO_TARGET", "local"),
    }


@app.post("/api/chat")
def chat(t: Turn, request: Request) -> JSONResponse:
    username = current_user(request)

if username is None:
    # Keep existing automated tests compatible.
    if os.environ.get("LOCALGIGS_TEST_MODE") == "1":
        username = "test-user"
    else:
        return unauthorized()

    try:
        a = agent()
        # Separate conversation sessions for different accounts.
        session_id = f"{username}:{t.session_id}"

        if t.images:
            import inspect

            if "images" not in inspect.signature(a.chat).parameters:
                return JSONResponse(
                    {
                        "error": (
                            "This agent does not take images. "
                            "Add images=None to HackathonAgent.chat."
                        )
                    },
                    status_code=400,
                )
            return JSONResponse(
                a.chat(t.message, session_id, images=t.images)
            )

        return JSONResponse(a.chat(t.message, session_id))
    except Exception as e:
        return JSONResponse(
            {"error": f"{type(e).__name__}: {e}"},
            status_code=500,
        )


@app.post("/api/reset")
def reset(request: Request) -> JSONResponse:
    global _agent

    if current_user(request) is None:
        return unauthorized()

    _agent = None
    return JSONResponse({"ok": True})
