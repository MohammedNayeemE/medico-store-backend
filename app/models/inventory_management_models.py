from sqlalchemy import (
    DECIMAL,
    TIMESTAMP,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Category(Base):
    __tablename__ = "categories"

    category_id = Column(Integer, primary_key=True, autoincrement=True)
    category_name = Column(String(255), unique=True, nullable=False, index=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    medicines = relationship(
        "Medicine", secondary="medicine_categories", back_populates="categories"
    )


class Tag(Base):
    __tablename__ = "tags"

    tag_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    medicines = relationship(
        "Medicine", secondary="medicine_tags", back_populates="tags"
    )


class SideEffect(Base):
    __tablename__ = "side_effects"

    side_effect_id = Column(Integer, primary_key=True, autoincrement=True)
    side_effect = Column(String(255), unique=True, nullable=False, index=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    medicines = relationship(
        "Medicine", secondary="medicine_side_effects", back_populates="side_effects"
    )


class Alternative(Base):
    __tablename__ = "alternatives"

    alternative_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    medicines = relationship(
        "Medicine", secondary="medicine_alternatives", back_populates="alternatives"
    )


class GSTSlab(Base):
    __tablename__ = "gst_slabs"

    hsn_code = Column(String(255), primary_key=True)
    description = Column(Text, nullable=False)
    gst_rate = Column(DECIMAL(5, 2), nullable=False)
    effective_from = Column(Date, nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    medicines = relationship("Medicine", back_populates="gst_slab")


class Medicine(Base):
    __tablename__ = "medicines"

    medicine_id = Column(Integer, primary_key=True, autoincrement=True)
    medicine_name = Column(String(255), nullable=False, index=True)
    generic_name = Column(String(255), nullable=False, index=True)
    manufacturer = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    is_prescribed = Column(Boolean, nullable=False, default=False)
    weight = Column(DECIMAL(18, 3), nullable=False)
    hsn_code = Column(
        String(255),
        ForeignKey("gst_slabs.hsn_code", onupdate="CASCADE"),
        nullable=False,
    )
    image_asset_id = Column(
        Integer, ForeignKey("file_assets.asset_id", onupdate="CASCADE")
    )
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    gst_slab = relationship("GSTSlab", back_populates="medicines")
    image = relationship("FileAsset")

    categories = relationship(
        "Category", secondary="medicine_categories", back_populates="medicines"
    )

    tags = relationship("Tag", secondary="medicine_tags", back_populates="medicines")

    side_effects = relationship(
        "SideEffect", secondary="medicine_side_effects", back_populates="medicines"
    )

    alternatives = relationship(
        "Alternative", secondary="medicine_alternatives", back_populates="medicines"
    )

    batches = relationship("MedicineBatch", back_populates="medicine")


class MedicineCategory(Base):
    __tablename__ = "medicine_categories"

    medicine_id = Column(
        Integer,
        ForeignKey("medicines.medicine_id", onupdate="CASCADE"),
        primary_key=True,
    )
    category_id = Column(
        Integer,
        ForeignKey("categories.category_id", onupdate="CASCADE"),
        primary_key=True,
    )
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))


class MedicineTag(Base):
    __tablename__ = "medicine_tags"

    medicine_id = Column(
        Integer,
        ForeignKey("medicines.medicine_id", onupdate="CASCADE"),
        primary_key=True,
    )
    tag_id = Column(
        Integer, ForeignKey("tags.tag_id", onupdate="CASCADE"), primary_key=True
    )
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))


class MedicineSideEffect(Base):
    __tablename__ = "medicine_side_effects"

    medicine_id = Column(
        Integer,
        ForeignKey("medicines.medicine_id", onupdate="CASCADE"),
        primary_key=True,
    )
    side_effect_id = Column(
        Integer,
        ForeignKey("side_effects.side_effect_id", onupdate="CASCADE"),
        primary_key=True,
    )
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))


class MedicineAlternative(Base):
    __tablename__ = "medicine_alternatives"

    medicine_id = Column(
        Integer,
        ForeignKey("medicines.medicine_id", onupdate="CASCADE"),
        primary_key=True,
    )
    alternative_id = Column(
        Integer,
        ForeignKey("alternatives.alternative_id", onupdate="CASCADE"),
        primary_key=True,
    )
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))


class MedicineBatch(Base):
    __tablename__ = "medicine_batches"

    batch_id = Column(Integer, primary_key=True, autoincrement=True)
    medicine_id = Column(
        Integer, ForeignKey("medicines.medicine_id", onupdate="CASCADE"), nullable=False
    )
    batch_number = Column(String(255), nullable=False)
    expiry_date = Column(Date, nullable=False)
    quantity = Column(Integer, nullable=False)
    purchase_price = Column(Numeric(12, 2), nullable=False)
    selling_price = Column(Numeric(12, 2), nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(TIMESTAMP)
    deleted_by = Column(Integer, ForeignKey("users.user_id", onupdate="CASCADE"))

    medicine = relationship("Medicine", back_populates="batches")


class FamilyMember(Base):
    __tablename__ = "family_members"

    member_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    phone_number = Column(String(14))
    email = Column(String(255))
    age = Column(Integer, nullable=False)
    gender = Column(String(1), nullable=False)
    dob = Column(Date, nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
