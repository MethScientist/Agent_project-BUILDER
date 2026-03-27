from fastapi import APIRouter, Depends
from account.models import User
from auth.auth import get_current_user




router = APIRouter(prefix="/api")  # ✅ sets base path to /api

@router.get("/user")
def get_user_profile(user: User = Depends(get_current_user)):
    return {
        "name": user.pseudo,  # ✅ if you use "pseudo" instead of "username"
        "profileImage": f"/static/{user.profile_image}" if user.profile_image else "/static/default-profile.png",
    }
