from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


class MongoBaseModel(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class HeroSection(MongoBaseModel):
    title: str
    description: str
    image_1_id: Optional[str] = None  # GridFS file ID
    image_2_id: Optional[str] = None  # GridFS file ID
    is_active: bool = True


class Banner(MongoBaseModel):
    image_id: str  # GridFS file ID
    alt_text: Optional[str] = None
    link: Optional[str] = None
    order: int = 0
    is_active: bool = True


class BestFeature(MongoBaseModel):
    title: str
    description: str
    tags: List[str] = []
    icon: Optional[str] = None
    order: int = 0
    is_active: bool = True


class Category(MongoBaseModel):
    name: str
    image_id: Optional[str] = None  # GridFS file ID
    slug: str
    description: Optional[str] = None
    order: int = 0
    is_active: bool = True


class Promise(MongoBaseModel):
    title: str
    description: str
    icon: Optional[str] = None
    order: int = 0
    is_active: bool = True


class Policy(MongoBaseModel):
    type: str  # terms_and_conditions, privacy_policy, cancellation_policy, refund_policy, etc.
    title: str
    content: str  # HTML or Markdown content
    version: str = "1.0"
    is_active: bool = True