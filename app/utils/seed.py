from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_management_models import (  # adjust import paths as needed
    Permission,
    Role,
    RolePermission,
)

# =========================================================
# 🚀 SEED DATA
# =========================================================

ALL_PERMISSIONS = [
    # --- Address Type ---
    ("address_type:delete", "Permission to delete address types"),
    ("address_type:read", "Permission to read address types"),
    ("address_type:write", "Permission to write address types"),
    # --- Admin ---
    ("admin:read", "Permission to read admin data"),
    ("admin:write", "Permission to write admin data"),
    # --- Alternate ---
    ("alternate:update", "Permission to update alternate records"),
    ("alternate:write", "Permission to write alternate records"),
    # --- Auth ---
    ("auth:write", "Permission to write authentication data"),
    # --- Backup ---
    ("backup:read", "Permission to read backups"),
    ("backup:write", "Permission to write backups"),
    # --- Batch ---
    ("batch:delete", "Permission to delete batches"),
    ("batch:read", "Permission to read batches"),
    ("batch:write", "Permission to write batches"),
    # --- Cart ---
    ("cart:delete", "Permission to delete carts"),
    ("cart:read", "Permission to read carts"),
    ("cart:write", "Permission to write carts"),
    # --- Category ---
    ("category:read", "Permission to read categories"),
    ("category:write", "Permission to write categories"),
    # --- Content ---
    ("content:write", "Permission to write content"),
    # --- Coupon ---
    ("coupon:read", "Permission to read coupons"),
    ("coupon:write", "Permission to write coupons"),
    # --- Dashboard ---
    ("dashboard:read", "Permission to read dashboard data"),
    # --- Discount ---
    ("discount:delete", "Permission to delete discounts"),
    ("discount:read", "Permission to read discounts"),
    ("discount:write", "Permission to write discounts"),
    # --- GST ---
    ("gst:read", "Permission to read GST data"),
    ("gst:write", "Permission to write GST data"),
    # --- Issues ---
    ("issue:read", "Permission to read issues"),
    ("issue:write", "Permission to write issues"),
    # --- Medicine ---
    ("medicine:read", "Permission to read medicines"),
    ("medicine:delete", "Permission to delete medicines"),
    ("medicine:write", "Permission to write medicines"),
    # --- Members ---
    ("members:read", "Permission to read members"),
    ("members:write", "Permission to write members"),
    # --- Notification ---
    ("notification:read", "Permission to read notifications"),
    # --- Orders ---
    ("order:delete", "Permission to delete orders"),
    ("order:read", "Permission to read orders"),
    ("order:write", "Permission to write orders"),
    # --- Payments ---
    ("payment:read", "Permission to read payments"),
    ("payment:update", "Permission to update payments"),
    ("payment:write", "Permission to write payments"),
    # --- Prescription ---
    ("prescription:read", "Permission to read prescriptions"),
    ("prescription:write", "Permission to write prescriptions"),
    # --- Profile ---
    ("profile:read", "Permission to read profiles"),
    ("profile:update", "Permission to update profiles"),
    ("profile:write", "Permission to write profiles"),
    # --- Requests ---
    ("request_medicine:read", "Permission to read requested medicines"),
    ("request_medicine:write", "Permission to write requested medicines"),
    ("request_order_admin:read", "Permission to read admin request orders"),
    ("request_order_admin:update", "Permission to update admin request orders"),
    ("request_order:read", "Permission to read request orders"),
    ("request_order:write", "Permission to write request orders"),
    # --- Reviews ---
    ("review:delete", "Permission to delete reviews"),
    ("review:read", "Permission to read reviews"),
    ("review:write", "Permission to write reviews"),
    # --- Roles ---
    ("role:read", "Permission to read roles"),
    ("role:update", "Permission to update roles"),
    ("role:write", "Permission to write roles"),
    # --- Side Effects ---
    ("side_effect:read", "Permission to read side effects"),
    ("side_effect:write", "Permission to write side effects"),
    # --- Tags ---
    ("tag:read", "Permission to read tags"),
    ("tag:write", "Permission to write tags"),
    # --- Reports ---
    ("reports:read", "Permission to read reports"),
]


CUSTOMER_PERMISSIONS = {
    "address_type:read",
    "auth:write",
    "cart:delete",
    "cart:read",
    "cart:write",
    "coupon:read",
    "category:read",
    "discount:read",
    "members:read",
    "members:write",
    "notification:read",
    "order:read",
    "payment:read",
    "payment:write",
    "prescription:read",
    "prescription:write",
    "profile:read",
    "profile:update",
    "profile:write",
    "request_medicine:read",
    "request_medicine:write",
    "request_order:read",
    "request_order:write",
    "review:read",
    "review:write",
    "medicine:read",
}


ADMIN_PERMISSIONS = {name for name, _ in ALL_PERMISSIONS}  # all permissions


# =========================================================
# 🌱 SEED FUNCTION
# =========================================================
async def seed_roles_and_permissions(db: AsyncSession):
    # 1️⃣ Create roles if not exists
    result = await db.execute(select(Role).where(Role.name.in_(["customer", "admin"])))
    existing_roles = {r.name: r for r in result.scalars().all()}

    if "customer" not in existing_roles:
        customer = Role(name="customer", description="Customer role", is_deleted=False)
        db.add(customer)
        await db.flush()  # ensures role_id is generated
    else:
        customer = existing_roles["customer"]

    if "admin" not in existing_roles:
        admin = Role(name="admin", description="Admin role", is_deleted=False)
        db.add(admin)
        await db.flush()
    else:
        admin = existing_roles["admin"]

    # 2️⃣ Insert permissions if missing
    result = await db.execute(select(Permission))
    existing_perms = {p.name: p for p in result.scalars().all()}

    for name, desc in ALL_PERMISSIONS:
        if name not in existing_perms:
            perm = Permission(name=name, description=desc, is_deleted=False)
            db.add(perm)
            await db.flush()
            existing_perms[name] = perm

    # 3️⃣ Assign permissions to roles (avoid duplicates)
    result = await db.execute(select(RolePermission))
    existing_links = {(rp.role_id, rp.permission_id) for rp in result.scalars().all()}

    def add_mapping(role, perm_names):
        for name in perm_names:
            perm = existing_perms.get(name)
            if perm and (role.role_id, perm.permission_id) not in existing_links:
                db.add(
                    RolePermission(
                        role_id=role.role_id,
                        permission_id=perm.permission_id,
                        granted_at=datetime.utcnow(),
                        is_deleted=False,
                    )
                )

    # Customer → limited permissions
    add_mapping(customer, CUSTOMER_PERMISSIONS)
    # Admin → all permissions
    add_mapping(admin, ADMIN_PERMISSIONS)

    # 4️⃣ Commit all changes
    await db.commit()
    print("✅ Roles and Permissions seeded successfully!")


# =========================================================
# 🧠 Usage Example
# =========================================================
"""
from app.db.session import async_session_maker
import asyncio

async def main():
    async with async_session_maker() as session:
        await seed_roles_and_permissions(session)

asyncio.run(main())
"""
