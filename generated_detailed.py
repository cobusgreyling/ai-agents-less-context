from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, EmailStr
from uuid import uuid4

app = FastAPI()
users_db: dict[str, dict] = {}

class UserCreate(BaseModel):
    name: str = Field(..., min_length=1)
    email: EmailStr

class UserResponse(BaseModel):
    id: str
    name: str
    email: str

class ErrorResponse(BaseModel):
    detail: str

@app.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(user: UserCreate):
    """
    Register a new user.
    """
    user_id = str(uuid4())
    user_dict = {"id": user_id, "name": user.name, "email": user.email}
    users_db[user_id] = user_dict
    return user_dict

@app.get(
    "/user/{user_id}",
    response_model=UserResponse,
)
def get_user(user_id: str):
    """
    Retrieve a user by ID.
    """
    if user_id not in users_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return users_db[user_id]

@app.delete("/user/{user_id}")
def delete_user(user_id: str):
    """
    Delete a user by ID.
    """
    if user_id not in users_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    del users_db[user_id]
    return {"message": "User deleted"}