from fastapi import APIRouter, HTTPException
from schemas import UserCreate, UserResponse
from database import db

router = APIRouter()

@router.post("/user", response_model=UserResponse)
async def createUser(data: UserCreate):
    existing_user = await db.users.find_one({"email": data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Use model_dump() to convert Pydantic model to dict for MongoDB
    user_data = data.model_dump(mode="json")



    result = await db.users.insert_one(user_data)

    # Set _id for response
    user_data["id"] = str(result.inserted_id)
    
    return UserResponse(**user_data)

@router.get("/user/{user_email}", response_model=UserResponse)
async def get_user(user_email: str):
    user = await db.users.find_one({"email": user_email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user["id"] = str(user["_id"])  # Convert _id to string
    del user["_id"]                # Remove original Mongo _id
    return UserResponse(**user)
