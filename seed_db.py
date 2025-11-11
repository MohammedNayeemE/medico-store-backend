"""
Database seeding script.

Run this script to populate the database with initial data:
- Roles and Permissions
- Address Types
- Categories, Tags, Side Effects, Alternatives
- GST Slabs
- Discount Types
- Issue Categories
- Default Users (Admin and Customer)

Usage:
    python seed_db.py
"""

import asyncio
from app.core.database import async_session
from app.utils.seed import seed_all


async def main():
    """Main function to run database seeding."""
    async with async_session() as session:
        await seed_all(session)


if __name__ == "__main__":
    print("Starting database seeding...")
    asyncio.run(main())

