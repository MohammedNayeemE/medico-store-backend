import io
from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from fastapi import HTTPException, UploadFile
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket

from app.core.database import bucket


class ContentService:
    def __init__(self, db: AsyncIOMotorClient):
        self.db = db
        self.fs = bucket

        # Collections
        self.hero_collection = db["hero_section"]
        self.banner_collection = db["banners"]
        self.feature_collection = db["best_features"]
        self.category_collection = db["categories"]
        self.promise_collection = db["promises"]
        self.policy_collection = db["policies"]

    # GridFS Helper Methods
    async def upload_image(self, file: UploadFile) -> str:
        """Upload image to GridFS and return file ID"""
        contents = await file.read()
        file_id = await self.fs.upload_from_stream(
            file.filename,
            io.BytesIO(contents),
            metadata={
                "content_type": file.content_type,
                "uploaded_at": datetime.utcnow(),
            },
        )
        return str(file_id)

    async def get_image_url(self, file_id: str) -> Optional[str]:
        """Generate URL for GridFS image"""
        if not file_id:
            return None
        return f"/api/content/images/{file_id}"

    async def delete_image(self, file_id: str):
        """Delete image from GridFS"""
        try:
            await self.fs.delete(ObjectId(file_id))
        except Exception as e:
            print(f"Error deleting image: {e}")

    async def get_image_stream(self, file_id: str):
        """Get image stream from GridFS"""
        try:
            grid_out = await self.fs.open_download_stream(ObjectId(file_id))
            return grid_out
        except Exception:
            raise HTTPException(status_code=404, detail="Image not found")

    # Hero Section Methods
    async def create_hero_section(self, data: dict) -> dict:
        result = await self.hero_collection.insert_one(data)
        data["_id"] = result.inserted_id
        return data

    async def get_hero_section(self) -> Optional[dict]:
        hero = await self.hero_collection.find_one({"is_active": True})
        if hero:
            hero["id"] = str(hero["_id"])
            hero["image_1_url"] = await self.get_image_url(hero.get("image_1_id"))
            hero["image_2_url"] = await self.get_image_url(hero.get("image_2_id"))
        return hero

    async def update_hero_section(self, hero_id: str, data: dict) -> dict:
        data["updated_at"] = datetime.utcnow()
        await self.hero_collection.update_one(
            {"_id": ObjectId(hero_id)}, {"$set": data}
        )
        return await self.hero_collection.find_one({"_id": ObjectId(hero_id)})

    async def upload_hero_image(
        self, hero_id: str, image_num: int, file: UploadFile
    ) -> dict:
        """Upload image for hero section"""
        hero = await self.hero_collection.find_one({"_id": ObjectId(hero_id)})
        if not hero:
            raise HTTPException(status_code=404, detail="Hero section not found")

        # Delete old image if exists
        old_image_key = f"image_{image_num}_id"
        if hero.get(old_image_key):
            await self.delete_image(hero[old_image_key])

        # Upload new image
        file_id = await self.upload_image(file)

        # Update hero section
        await self.hero_collection.update_one(
            {"_id": ObjectId(hero_id)},
            {"$set": {old_image_key: file_id, "updated_at": datetime.utcnow()}},
        )

        return await self.get_hero_section()

    # Banner Methods
    async def create_banner(self, file: UploadFile, data: dict) -> dict:
        # Check banner limit
        count = await self.banner_collection.count_documents({"is_active": True})
        if count >= 5:
            raise HTTPException(
                status_code=400, detail="Maximum 5 active banners allowed"
            )

        file_id = await self.upload_image(file)
        data["image_id"] = file_id
        data["created_at"] = datetime.utcnow()
        data["updated_at"] = datetime.utcnow()

        result = await self.banner_collection.insert_one(data)
        data["_id"] = result.inserted_id
        data["id"] = str(result.inserted_id)
        data["image_url"] = await self.get_image_url(file_id)
        return data

    async def get_banners(self, active_only: bool = False) -> List[dict]:
        query = {"is_active": True} if active_only else {}
        banners = (
            await self.banner_collection.find(query).sort("order", 1).to_list(None)
        )
        for banner in banners:
            banner["id"] = str(banner["_id"])
            banner["image_url"] = await self.get_image_url(banner["image_id"])
        return banners

    async def update_banner(self, banner_id: str, data: dict) -> dict:
        data["updated_at"] = datetime.utcnow()
        await self.banner_collection.update_one(
            {"_id": ObjectId(banner_id)}, {"$set": data}
        )
        banner = await self.banner_collection.find_one({"_id": ObjectId(banner_id)})
        if banner:
            banner["id"] = str(banner["_id"])
            banner["image_url"] = await self.get_image_url(banner["image_id"])
        return banner

    async def delete_banner(self, banner_id: str):
        banner = await self.banner_collection.find_one({"_id": ObjectId(banner_id)})
        if not banner:
            raise HTTPException(status_code=404, detail="Banner not found")

        await self.delete_image(banner["image_id"])
        await self.banner_collection.delete_one({"_id": ObjectId(banner_id)})

    # Best Features Methods
    async def create_feature(self, data: dict) -> dict:
        data["created_at"] = datetime.utcnow()
        data["updated_at"] = datetime.utcnow()
        result = await self.feature_collection.insert_one(data)
        data["_id"] = result.inserted_id
        data["id"] = str(result.inserted_id)
        return data

    async def get_features(self, active_only: bool = False) -> List[dict]:
        query = {"is_active": True} if active_only else {}
        features = (
            await self.feature_collection.find(query).sort("order", 1).to_list(None)
        )
        for feature in features:
            feature["id"] = str(feature["_id"])
        return features

    async def update_feature(self, feature_id: str, data: dict) -> dict:
        data["updated_at"] = datetime.utcnow()
        await self.feature_collection.update_one(
            {"_id": ObjectId(feature_id)}, {"$set": data}
        )
        feature = await self.feature_collection.find_one({"_id": ObjectId(feature_id)})
        if feature:
            feature["id"] = str(feature["_id"])
        return feature

    async def delete_feature(self, feature_id: str):
        await self.feature_collection.delete_one({"_id": ObjectId(feature_id)})

    # Category Methods
    async def create_category(
        self, data: dict, file: Optional[UploadFile] = None
    ) -> dict:
        if file:
            data["image_id"] = await self.upload_image(file)

        data["created_at"] = datetime.utcnow()
        data["updated_at"] = datetime.utcnow()
        result = await self.category_collection.insert_one(data)
        data["_id"] = result.inserted_id
        data["id"] = str(result.inserted_id)
        data["image_url"] = await self.get_image_url(data.get("image_id"))
        return data

    async def get_categories(self, active_only: bool = False) -> List[dict]:
        query = {"is_active": True} if active_only else {}
        categories = (
            await self.category_collection.find(query).sort("order", 1).to_list(None)
        )
        for category in categories:
            category["id"] = str(category["_id"])
            category["image_url"] = await self.get_image_url(category.get("image_id"))
        return categories

    async def update_category(
        self, category_id: str, data: dict, file: Optional[UploadFile] = None
    ) -> dict:
        if file:
            # Delete old image
            category = await self.category_collection.find_one(
                {"_id": ObjectId(category_id)}
            )
            if category and category.get("image_id"):
                await self.delete_image(category["image_id"])

            data["image_id"] = await self.upload_image(file)

        data["updated_at"] = datetime.utcnow()
        await self.category_collection.update_one(
            {"_id": ObjectId(category_id)}, {"$set": data}
        )
        category = await self.category_collection.find_one(
            {"_id": ObjectId(category_id)}
        )
        if category:
            category["id"] = str(category["_id"])
            category["image_url"] = await self.get_image_url(category.get("image_id"))
        return category

    async def delete_category(self, category_id: str):
        category = await self.category_collection.find_one(
            {"_id": ObjectId(category_id)}
        )
        if category and category.get("image_id"):
            await self.delete_image(category["image_id"])
        await self.category_collection.delete_one({"_id": ObjectId(category_id)})

    # Promise Methods
    async def create_promise(self, data: dict) -> dict:
        data["created_at"] = datetime.utcnow()
        data["updated_at"] = datetime.utcnow()
        result = await self.promise_collection.insert_one(data)
        data["_id"] = result.inserted_id
        data["id"] = str(result.inserted_id)
        return data

    async def get_promises(self, active_only: bool = False) -> List[dict]:
        query = {"is_active": True} if active_only else {}
        promises = (
            await self.promise_collection.find(query).sort("order", 1).to_list(None)
        )
        for promise in promises:
            promise["id"] = str(promise["_id"])
        return promises

    async def update_promise(self, promise_id: str, data: dict) -> dict:
        data["updated_at"] = datetime.utcnow()
        await self.promise_collection.update_one(
            {"_id": ObjectId(promise_id)}, {"$set": data}
        )
        promise = await self.promise_collection.find_one({"_id": ObjectId(promise_id)})
        if promise:
            promise["id"] = str(promise["_id"])
        return promise

    async def delete_promise(self, promise_id: str):
        await self.promise_collection.delete_one({"_id": ObjectId(promise_id)})

    # Policy Methods
    async def create_policy(self, data: dict) -> dict:
        data["created_at"] = datetime.utcnow()
        data["updated_at"] = datetime.utcnow()
        result = await self.policy_collection.insert_one(data)
        data["_id"] = result.inserted_id
        data["id"] = str(result.inserted_id)
        return data

    async def get_policy_by_type(self, policy_type: str) -> Optional[dict]:
        policy = await self.policy_collection.find_one(
            {"type": policy_type, "is_active": True}
        )
        if policy:
            policy["id"] = str(policy["_id"])
        return policy

    async def get_policies(self) -> List[dict]:
        policies = await self.policy_collection.find({"is_active": True}).to_list(None)
        for policy in policies:
            policy["id"] = str(policy["_id"])
        return policies

    async def update_policy(self, policy_id: str, data: dict) -> dict:
        data["updated_at"] = datetime.utcnow()
        await self.policy_collection.update_one(
            {"_id": ObjectId(policy_id)}, {"$set": data}
        )
        policy = await self.policy_collection.find_one({"_id": ObjectId(policy_id)})
        if policy:
            policy["id"] = str(policy["_id"])
        return policy

    async def delete_policy(self, policy_id: str):
        await self.policy_collection.delete_one({"_id": ObjectId(policy_id)})

