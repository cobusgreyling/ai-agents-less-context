from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict

app = FastAPI()

class UserCreate(BaseModel):
    name: str
    email: str

class User(UserCreate):
    id: int

# In-memory storage
users: Dict[int, User] = {}
next_id = 1

@app.post("/register", response_model=User)
def register(user_create: UserCreate):
    global next_id
    user = User(id=next_id, **user_create.dict())
    users[next_id] = user
    next_id += 1
    return user

@app.get("/user/{user_id}", response_model=User)
def get_user(user_id: int):
    user = users.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.delete("/user/{user_id}", status_code=204)
def delete_user(user_id: int):
    if user_id not in users:
        raise HTTPException(status_code=404, detail="User not found")
    del users[user_id]
    return None