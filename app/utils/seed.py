from datetime import datetime, timedelta
from decimal import Decimal

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backup_models import Backup
from app.models.enums import (
    InvoicePaymentStatusEnum,
    IssueStatusEnum,
    OrderStatusEnum,
    PaymentStatusEnum,
    PrescriptionStatusEnum,
    ReportFormatEnum,
    ReportStatusEnum,
    ReportTypeEnum,
    RequestOrderStatusEnum,
    RequestStatusEnum,
    ReviewStatusEnum,
)
from app.models.inventory_management_models import (
    Alternative,
    Category,
    FamilyMember,
    GSTSlab,
    Medicine,
    MedicineAlternative,
    MedicineBatch,
    MedicineCategory,
    MedicineImage,
    MedicineSideEffect,
    MedicineTag,
    SideEffect,
    Tag,
    Cart,
    CartItem,
    MedicineRequest,

)
from app.models.notification_management_models import Notification
from app.models.order_management_models import (
    
    Coupon,
    Discount,
    DiscountCategory,
    DiscountMedicine,
    DiscountParameter,
    DiscountType,
    Invoice,
    InvoiceItem,
    Issue,
    IssueAttachment,
    IssueCategory,
    IssueMessage,
    Order,
    OrderItem,
    Payment,
    RequestOrder,
    RequestOrderItem,
)
from app.models.report_management_models import (
    GeneratedReport,
    ReportEmailDelivery,
    ReportSchedule,
    ReportTemplate,
)
from app.models.user_management_models import (
    Address,
    AddressType,
    CustomerProfile,
    FileAsset,
    ManagementProfile,
    PasswordReset,
    Permission,
    Review,
    Role,
    RolePermission,
    User,
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

# Password hasher
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


# =========================================================
# 🌱 SEED FUNCTIONS
# =========================================================


async def seed_roles_and_permissions(db: AsyncSession):
    """
    Seed the database with default roles and permissions.
    
    This function initializes the database with essential role-based access control
    (RBAC) data. It creates two default roles (customer and admin) if they don't
    exist, creates all permissions defined in ALL_PERMISSIONS, and assigns the
    appropriate permissions to each role.
    """
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


async def seed_address_types(db: AsyncSession):
    """Seed address types (home, work, etc.)"""
    address_types = ["home", "work", "other"]
    
    result = await db.execute(select(AddressType))
    existing = {at.name for at in result.scalars().all()}
    
    for name in address_types:
        if name not in existing:
            db.add(AddressType(name=name, is_deleted=False))
    
    await db.commit()
    print("✅ Address Types seeded successfully!")


async def seed_categories(db: AsyncSession):
    """Seed medicine categories"""
    categories = [
        "Antibiotics",
        "Pain Relief",
        "Vitamins & Supplements",
        "Cardiac",
        "Diabetes",
        "Respiratory",
        "Digestive",
        "Skin Care",
        "Eye Care",
        "General",
    ]
    
    result = await db.execute(select(Category))
    existing = {c.category_name for c in result.scalars().all()}
    
    for name in categories:
        if name not in existing:
            db.add(Category(category_name=name, is_deleted=False))
    
    await db.commit()
    print("✅ Categories seeded successfully!")


async def seed_tags(db: AsyncSession):
    """Seed medicine tags"""
    tags = [
        "prescription",
        "over-the-counter",
        "generic",
        "branded",
        "fast-acting",
        "long-lasting",
        "pediatric",
        "adult",
        "senior",
    ]
    
    result = await db.execute(select(Tag))
    existing = {t.name for t in result.scalars().all()}
    
    for name in tags:
        if name not in existing:
            db.add(Tag(name=name, is_deleted=False))
    
    await db.commit()
    print("✅ Tags seeded successfully!")


async def seed_side_effects(db: AsyncSession):
    """Seed common side effects"""
    side_effects = [
        "Drowsiness",
        "Nausea",
        "Headache",
        "Dizziness",
        "Dry Mouth",
        "Diarrhea",
        "Constipation",
        "Rash",
        "Allergic Reaction",
    ]
    
    result = await db.execute(select(SideEffect))
    existing = {se.side_effect for se in result.scalars().all()}
    
    for name in side_effects:
        if name not in existing:
            db.add(SideEffect(side_effect=name, is_deleted=False))
    
    await db.commit()
    print("✅ Side Effects seeded successfully!")


async def seed_alternatives(db: AsyncSession):
    """Seed alternative medicine names"""
    alternatives = [
        "Paracetamol",
        "Ibuprofen",
        "Aspirin",
        "Amoxicillin",
        "Metformin",
    ]
    
    result = await db.execute(select(Alternative))
    existing = {alt.name for alt in result.scalars().all()}
    
    for name in alternatives:
        if name not in existing:
            db.add(Alternative(name=name, is_deleted=False))
    
    await db.commit()
    print("✅ Alternatives seeded successfully!")


async def seed_gst_slabs(db: AsyncSession):
    """Seed GST slabs"""
    gst_slabs = [
        {"hsn_code": "3004", "description": "Medicines", "gst_rate": Decimal("5.00"), "effective_from": datetime.now().date()},
        {"hsn_code": "3003", "description": "Pharmaceutical Products", "gst_rate": Decimal("12.00"), "effective_from": datetime.now().date()},
        {"hsn_code": "3002", "description": "Human Blood", "gst_rate": Decimal("0.00"), "effective_from": datetime.now().date()},
    ]
    
    result = await db.execute(select(GSTSlab))
    existing = {gst.hsn_code for gst in result.scalars().all()}
    
    for gst_data in gst_slabs:
        if gst_data["hsn_code"] not in existing:
            db.add(GSTSlab(**gst_data, is_deleted=False))
    
    await db.commit()
    print("✅ GST Slabs seeded successfully!")


async def seed_discount_types(db: AsyncSession):
    """Seed discount types"""
    discount_types = [
        {"type_name": "percentage", "description": "Percentage-based discount"},
        {"type_name": "fixed", "description": "Fixed amount discount"},
        {"type_name": "buy_one_get_one", "description": "Buy one get one free"},
    ]
    
    result = await db.execute(select(DiscountType))
    existing = {dt.type_name for dt in result.scalars().all()}
    
    for dt_data in discount_types:
        if dt_data["type_name"] not in existing:
            db.add(DiscountType(**dt_data, is_deleted=False))
    
    await db.commit()
    print("✅ Discount Types seeded successfully!")


async def seed_issue_categories(db: AsyncSession):
    """Seed issue categories"""
    issue_categories = [
        {"name": "delivery", "description": "Delivery related issues"},
        {"name": "product", "description": "Product quality issues"},
        {"name": "payment", "description": "Payment related issues"},
        {"name": "order", "description": "Order processing issues"},
        {"name": "other", "description": "Other issues"},
    ]
    
    result = await db.execute(select(IssueCategory))
    existing = {ic.name for ic in result.scalars().all()}
    
    for ic_data in issue_categories:
        if ic_data["name"] not in existing:
            db.add(IssueCategory(**ic_data, is_deleted=False))
    
    await db.commit()
    print("✅ Issue Categories seeded successfully!")


async def seed_users(db: AsyncSession):
    """Seed default users (admin and customer)"""
    # Get roles
    result = await db.execute(select(Role).where(Role.name.in_(["admin", "customer"])))
    roles = {r.name: r for r in result.scalars().all()}
    
    admin_role = roles.get("admin")
    customer_role = roles.get("customer")
    
    if not admin_role or not customer_role:
        print("⚠️  Roles not found. Please seed roles first.")
        return
    
    # Check if admin user exists
    result = await db.execute(select(User).where(User.email == "admin@epms.com"))
    admin_user = result.scalar_one_or_none()
    
    if not admin_user:
        hashed_password = pwd_context.hash("admin123")
        admin_user = User(
            email="admin@epms.com",
            password_hash=hashed_password,
            role_id=admin_role.role_id,
            is_active=True,
            is_deleted=False,
        )
        db.add(admin_user)
        await db.flush()
        
        # Create management profile
        management_profile = ManagementProfile(
            user_id=admin_user.user_id,
            name="System Administrator",
            phone_number="+1234567890",
            is_deleted=False,
        )
        db.add(management_profile)
        print("✅ Admin user created successfully!")
    else:
        print("ℹ️  Admin user already exists")
    
    # Check if customer user exists
    result = await db.execute(select(User).where(User.phone_number == "+917598982124"))
    customer_user = result.scalar_one_or_none()
    
    if not customer_user:
        hashed_password = pwd_context.hash("customer123")
        customer_user = User(
            phone_number="+917598982124",
            email="",
            password_hash=hashed_password,
            role_id=customer_role.role_id,
            is_active=True,
            is_deleted=False,
        )
        db.add(customer_user)
        await db.flush()
        
        # Create customer profile
        customer_profile = CustomerProfile(
            user_id=customer_user.user_id,
            name="Mohammed Nayeem",
            email="mohammednayeeme.cse2022@citchennai.net",
            blood_group="B+",
            gender="M",
            dob=datetime(1990, 1, 1).date(),
            is_deleted=False,
        )
        db.add(customer_profile)
        print("✅ Customer user created successfully!")
    else:
        print("ℹ️  Customer user already exists")
    
    await db.commit()
    print("✅ Users seeded successfully!")


async def seed_all(db: AsyncSession):
    """
    Main seed function that seeds all data in the correct order.
    
    This function ensures that all dependencies are created in the proper sequence
    to avoid foreign key constraint violations.
    """
    print("🌱 Starting database seeding...")
    print("=" * 50)
    
    try:
        # 1. Base models (no dependencies)
        await seed_roles_and_permissions(db)
        await seed_address_types(db)
        await seed_categories(db)
        await seed_tags(db)
        await seed_side_effects(db)
        await seed_alternatives(db)
        await seed_gst_slabs(db)
        await seed_discount_types(db)
        await seed_issue_categories(db)
        
        # 2. Users (depends on Roles)
        await seed_users(db)
        
        print("=" * 50)
        print("✅ Database seeding completed successfully!")
        print("\nDefault credentials:")
        print("  Admin: admin@epms.com / admin123")
        print("  Customer: +1987654321 / customer123")
        
    except Exception as e:
        await db.rollback()
        print(f"❌ Error during seeding: {e}")
        raise


# =========================================================
# 🧠 Usage Example
# =========================================================
"""
from app.core.database import async_session
import asyncio

async def main():
    async with async_session() as session:
        await seed_all(session)

if __name__ == "__main__":
    asyncio.run(main())
"""
