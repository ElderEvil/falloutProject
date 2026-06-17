#!/usr/bin/env python3
"""CLI to create a superuser (admin) account for testing.

Usage:
  uv run python scripts/create_admin.py --email admin@test.com --username admin --password test1234
"""

import argparse
import asyncio
import uuid
from datetime import datetime

import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed.decode()


async def create_admin(
    db_url: str,
    email: str,
    username: str,
    password: str,
    is_superuser: bool = True,
    is_active: bool = True,
    email_verified: bool = True,
):
    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(
            text('SELECT id FROM "user" WHERE email = :email'),
            {"email": email},
        )
        existing = result.scalar_one_or_none()
        if existing:
            print(f"User {email} already exists. Upgrading to superuser...")
            await session.execute(
                text('UPDATE "user" SET is_superuser = true, is_active = true WHERE id = :id'),
                {"id": existing},
            )
            await session.commit()
            print(f"Updated {email} to superuser.")
            return

        hashed = hash_password(password)
        user_id = str(uuid.uuid4())
        now = datetime.utcnow()

        await session.execute(
            text("""
                INSERT INTO "user"
                    (id, username, email, hashed_password, is_superuser,
                     is_active, email_verified, created_at, updated_at)
                VALUES (:id, :username, :email, :password, :is_superuser,
                        :is_active, :email_verified, :now, :now)
            """),
            {
                "id": user_id,
                "username": username,
                "email": email,
                "password": hashed,
                "is_superuser": is_superuser,
                "is_active": is_active,
                "email_verified": email_verified,
                "now": now,
            },
        )
        await session.commit()
        print(f"Superuser created:\n  Email: {email}\n  Username: {username}\n  Password: {password}")


def main():
    parser = argparse.ArgumentParser(description="Create a superuser for testing")
    parser.add_argument("--email", default="admin@test.com")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    parser.add_argument(
        "--db-url",
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/fallout_db",
    )
    args = parser.parse_args()
    asyncio.run(
        create_admin(
            db_url=args.db_url,
            email=args.email,
            username=args.username,
            password=args.password,
        )
    )


if __name__ == "__main__":
    main()
