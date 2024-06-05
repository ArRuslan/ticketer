import asyncio
import sys

from bcrypt import hashpw, gensalt
from tortoise import Tortoise

from ticketer import config
from ticketer.models import User, UserRole


async def main():
    email = input("Email: ")
    password = input("Password: ")

    await Tortoise.init(
        config=None, config_file=None, db_url=config.DB_CONNECTION_STRING, modules={"models": ["ticketer.models"]}
    )

    if await User.filter(email=email).exists():
        print("User already exists!")
        return sys.exit()

    await User.create(
        email=email,
        password=hashpw(password.encode("utf8"), gensalt()).decode("utf8"),
        first_name="Admin",
        last_name="Admin",
        role=UserRole.ADMIN,
    )
    print("User created successfully!")

    await Tortoise.close_connections()
    sys.exit()


if __name__ == "__main__":
    asyncio.run(main())
