import logging
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import Role, User
from .observability import TraceMiddleware, setup_logging
from .schemas import LoginIn, RegisterIn, RoleOut, TokenOut, UserListOut, UserOut
from .security import create_token, decode_token, hash_password, verify_password

setup_logging("auth")
logger = logging.getLogger("auth")

app = FastAPI(title="auth-service", version="1.0.0")
app.add_middleware(TraceMiddleware)


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    try:
        payload = decode_token(authorization[len("Bearer "):])
    except Exception:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role.name != "admin":
        raise HTTPException(status_code=403, detail="admin role required")
    return user


def require_staff(user: User = Depends(get_current_user)) -> User:
    if user.role.name not in ("admin", "agent"):
        raise HTTPException(status_code=403, detail="admin or agent role required")
    return user


def to_user_out(user: User) -> UserOut:
    return UserOut(id=user.id, username=user.username, role=user.role.name)


@app.get("/health")
def health():
    return {"status": "ok", "service": "auth"}


@app.post("/auth/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    role = db.query(Role).filter(Role.name == body.role).first()
    if role is None:
        raise HTTPException(status_code=400, detail="unknown role: " + body.role)
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=409, detail="username already taken")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role_id=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("user registered id=%s username=%s role=%s", user.id, user.username, role.name)
    return to_user_out(user)


@app.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        logger.info("login failed username=%s", body.username)
        raise HTTPException(status_code=401, detail="invalid credentials")
    logger.info("login ok user_id=%s", user.id)
    return TokenOut(access_token=create_token(user.id, user.username, user.role.name))


@app.get("/auth/verify", response_model=UserOut)
def verify(user: User = Depends(get_current_user)):
    return to_user_out(user)


@app.get("/auth/roles", response_model=list)
def list_roles(db: Session = Depends(get_db)):
    return [RoleOut(id=r.id, name=r.name) for r in db.query(Role).all()]


@app.get("/auth/users", response_model=UserListOut)
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return UserListOut(users=[to_user_out(u) for u in db.query(User).all()])


@app.get("/auth/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return to_user_out(user)
