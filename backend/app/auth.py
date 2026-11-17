"""Accounts, sign-in sessions and the access rules.

A regulator (a Ministry of Health officer) reads and writes everything. A company user acts for one organization and
sees one step back and one step forward: the lots that organization made, used or moved, and the shipments it sent or
received. Lab results are shown to a company only for lots it made.

Accounts are created on the server by an administrator; there is no public sign-up:

    python -m app.auth add-user --email officer@example.gov.my --name "Aisyah Rahman" --role regulator
    python -m app.auth add-user --email qa@farm.example --name "Lim Wei" --role company --organization "Greenfield Farm"

The password is asked for without echo, or read from standard input when piped.
"""

import argparse
import getpass
import hashlib
import hmac
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine, get_db
from app.models import Batch, BatchRelationship, Entry, Organization, Shipment, User, UserSession

router = APIRouter(prefix="/api/auth")

COOKIE = "tracefront_session"
# Chrome, Edge and Firefox accept Secure cookies from http://localhost, so this stays on behind the SSH tunnel too.
# Set TRACEFRONT_COOKIE_SECURE=0 only for a local browser that refuses them.
COOKIE_SECURE = os.environ.get("TRACEFRONT_COOKIE_SECURE", "1") != "0"
SESSION_LENGTH = timedelta(hours=12)
MAX_FAILED_LOGINS, LOCK_FOR = 5, timedelta(minutes=15)
MIN_PASSWORD_LENGTH = 12
SCRYPT = {"n": 2**14, "r": 8, "p": 5}  # an OWASP-listed setting; kept in each hash so it can be raised later
ROLES = ("regulator", "company")
# One message for a wrong email, a wrong password and a locked account, so none can be told from the others.
BAD_LOGIN = (f"The email or password is not correct. After {MAX_FAILED_LOGINS} failed attempts an account is locked "
             f"for {LOCK_FOR.seconds // 60} minutes.")


def utc(at: datetime) -> datetime:
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)  # SQLite drops the zone


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **SCRYPT)
    return f"scrypt${SCRYPT['n']}${SCRYPT['r']}${SCRYPT['p']}${salt.hex()}${digest.hex()}"


def password_matches(password: str, stored: str) -> bool:
    _, n, r, p, salt, digest = stored.split("$")
    actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), dklen=32, n=int(n), r=int(r), p=int(p))
    return hmac.compare_digest(actual, bytes.fromhex(digest))


UNKNOWN_USER_HASH = hash_password(secrets.token_urlsafe())  # checked for unknown emails, so they take as long as known ones


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_user(db: Session, email: str, name: str, password: str, role: str, organization_id: int | None = None) -> User:
    email, name = email.strip().lower(), name.strip()
    if role not in ROLES:
        raise ValueError(f"role must be one of {', '.join(ROLES)}")
    if (role == "company") != (organization_id is not None):
        raise ValueError("a company user needs an organization, and a regulator has none")
    if "@" not in email or not name:
        raise ValueError("give an email address and a name")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"the password needs at least {MIN_PASSWORD_LENGTH} characters")
    if db.query(User).filter(User.email == email).first():
        raise ValueError("that email already has an account")
    if organization_id is not None and db.get(Organization, organization_id) is None:
        raise ValueError(f"organization {organization_id} is not stored")
    user = User(email=email, name=name, password_hash=hash_password(password), role=role,
                organization_id=organization_id, failed_logins=0)
    db.add(user)
    db.commit()
    return user


def user_document(db: Session, user: User) -> dict:
    org = db.get(Organization, user.organization_id) if user.organization_id is not None else None
    return {"user_id": user.user_id, "email": user.email, "name": user.name, "role": user.role,
            "organization_id": user.organization_id, "organization_name": org.name if org else None}


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE)
    session = db.get(UserSession, token_hash(token)) if token else None
    live = session is not None and utc(session.expires_at) > datetime.now(timezone.utc)
    user = db.get(User, session.user_id) if live else None
    if user is None:
        raise HTTPException(401, "sign in to continue")
    return user


def regulator(user: User = Depends(current_user)) -> User:
    if user.role != "regulator":
        raise HTTPException(403, "only a Ministry of Health officer can do this")
    return user


def party(organization_id: int):
    """Filter: shipments an organization sent or received."""
    return or_(Shipment.from_org_id == organization_id, Shipment.to_org_id == organization_id)


def scope(db: Session, user: User) -> set[int] | None:
    """The batch IDs a user may see. None means every batch, and only a regulator gets that. A company gets the lots it
    made, the lots in shipments it sent or received, and the ingredient lots of its own products."""
    if user.role == "regulator":
        return None
    # ponytail: the scope is rebuilt as an ID set on every request; use subqueries once a company passes ~30k lots
    org = user.organization_id
    made = db.query(Batch.batch_id).filter(Batch.organization_id == org)
    moved = db.query(Shipment.batch_id).filter(party(org))
    used = (db.query(BatchRelationship.parent_batch_id)
            .join(Batch, Batch.batch_id == BatchRelationship.child_batch_id).filter(Batch.organization_id == org))
    return {id_ for query in (made, moved, used) for (id_,) in query}


def log_entry(db: Session, user: User, record) -> None:
    """Note who stored a record. The record must already have its primary key."""
    key = record.__mapper__.primary_key_from_instance(record)[0]
    db.add(Entry(user_id=user.user_id, organization_id=user.organization_id, kind=record.__tablename__,
                 record_id=str(key), entered_at=datetime.now(timezone.utc)))


class Login(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=1024)  # bounded, so a huge value cannot tie up the password hash


@router.post("/login")
def login(data: Login, response: Response, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    user = db.query(User).filter(User.email == data.email.strip().lower()).first()
    locked = user is not None and user.locked_until is not None and utc(user.locked_until) > now
    matches = password_matches(data.password, user.password_hash if user else UNKNOWN_USER_HASH)
    if user is None or locked or not matches:
        if user is not None and not locked:
            user.failed_logins += 1
            if user.failed_logins >= MAX_FAILED_LOGINS:
                user.failed_logins, user.locked_until = 0, now + LOCK_FOR
            db.commit()
        raise HTTPException(401, BAD_LOGIN)
    user.failed_logins, user.locked_until = 0, None
    db.query(UserSession).filter(UserSession.expires_at < now).delete()
    token = secrets.token_urlsafe(32)
    db.add(UserSession(token_hash=token_hash(token), user_id=user.user_id, expires_at=now + SESSION_LENGTH))
    db.commit()
    response.set_cookie(COOKIE, token, max_age=int(SESSION_LENGTH.total_seconds()), httponly=True, samesite="lax",
                        secure=COOKIE_SECURE, path="/")
    return user_document(db, user)


@router.post("/logout")
def logout(request: Request, response: Response, _: User = Depends(current_user), db: Session = Depends(get_db)):
    db.query(UserSession).filter(UserSession.token_hash == token_hash(request.cookies[COOKIE])).delete()
    db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"signed_out": True}


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return user_document(db, user)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage Tracefront accounts.")
    add = parser.add_subparsers(dest="command", required=True).add_parser("add-user")
    add.add_argument("--email", required=True)
    add.add_argument("--name", required=True)
    add.add_argument("--role", required=True, choices=ROLES)
    add.add_argument("--organization", help="the stored organization's name; required for a company user")
    args = parser.parse_args()
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        organization_id = None
        if args.organization:
            matches = [o for o in session.query(Organization) if o.name.casefold() == args.organization.strip().casefold()]
            if len(matches) != 1:
                sys.exit(f"{len(matches)} stored organizations are named {args.organization!r}; one is needed")
            organization_id = matches[0].organization_id
        # PowerShell pipes text with a byte-order mark first; kept, it would make the password impossible to type.
        password = (getpass.getpass("Password: ") if sys.stdin.isatty()
                    else sys.stdin.readline().rstrip("\r\n").removeprefix("﻿"))
        try:
            made = create_user(session, args.email, args.name, password, args.role, organization_id)
        except ValueError as error:
            sys.exit(str(error))
        print(f"created {made.role} account {made.email}")
