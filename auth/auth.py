import os
from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from werkzeug.utils import secure_filename
import shutil

from account.database import SessionLocal
from account.models import User

# --- Router and Templates Setup ---
router = APIRouter()
templates = Jinja2Templates(directory="web/templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Database Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Helper Functions ---
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# --- Registration Routes ---
@router.get("/register", response_class=HTMLResponse)
def show_register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
def register_user(
    request: Request,
    pseudo: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    profile_image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    # Vérifie si l'utilisateur existe déjà
    user = db.query(User).filter(User.email == email).first()
    if user:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "message": "Email already registered"
        })

    # Hash du mot de passe
    hashed_pw = hash_password(password)

    # Traitement de l'image de profil
    if profile_image and profile_image.filename:
        filename = secure_filename(profile_image.filename)
        image_filename = f"profile_{email}_{filename}"
        image_path = f"static/uploads/{image_filename}"

        os.makedirs("static/uploads", exist_ok=True)

        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(profile_image.file, buffer)

        profile_path = f"/static/uploads/{image_filename}"
    else:
        profile_path = "/static/default-profile.png"

    # Création de l'utilisateur
    new_user = User(
        email=email,
        pseudo=pseudo,
        hashed_password=hashed_pw,
        profile_image=profile_path
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return RedirectResponse("/login", status_code=303)

# --- Login Routes ---
@router.get("/login", response_class=HTMLResponse)
def show_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
def submit_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html", {"request": request, "message": "Invalid credentials"}
        )

    request.session["user"] = user.email
    return RedirectResponse("/", status_code=302)

# --- Get Current User Helper ---
def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_email = request.session.get("user")
    if not user_email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return user

# --- API Endpoint to get user ---
@router.get("/api/user")
def get_user_api(request: Request, db: Session = Depends(get_db)):
    user_email = request.session.get("user")
    if not user_email:
        raise HTTPException(status_code=401, detail="Not logged in")

    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile_path = user.profile_image or "/static/default-profile.png"

    return {
        "name": user.pseudo,
        "profileImage": profile_path,
    }

