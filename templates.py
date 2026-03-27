from fastapi import APIRouter, Request, FastAPI, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from account.database import get_db

import tkinter as tk


root = tk.Tk()

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="SUPER_SECRET_KEY")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("web/static/favicon.ico")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    session_user = request.session.get("user")
    if not session_user:
        # Create a guest user in DB
        guest_user = {"email": "guest@example.com", "name": "Guest"}
        request.session["user"] = guest_user
        session_user = guest_user
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": session_user})


# Helper to serve both "/page" and "/page.html"
def add_html_routes(path: str, template_name: str):
    @router.get(path, response_class=HTMLResponse)
    @router.get(f"{path}.html", response_class=HTMLResponse)
    async def serve_page(request: Request):
        return templates.TemplateResponse(template_name, {"request": request})

# --- HTML GET routes ---
add_html_routes("/register", "register.html")
add_html_routes("/login", "login.html")
add_html_routes("/ai-agent", "ai-agent.html")
add_html_routes("/billing", "billing.html")
add_html_routes("/plugins", "plugins.html")
add_html_routes("/profile", "profile.html")
add_html_routes("/project-viewer", "project-viewer.html")
add_html_routes("/settings", "profile.html")
add_html_routes("/history", "history.html")



# --- POST handlers for forms ---
@router.post("/register")
async def register_post(request: Request):
    form_data = await request.form()
    email = form_data.get("email")
    password = form_data.get("password")
    
    # TODO: Save new user in database here
    request.session["user"] = email

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="user_email",
        value=email,
        httponly=True,
        max_age=60*60*24*30
    )
    return response

@router.post("/login")
async def login_post(request: Request):
    form_data = await request.form()
    email = form_data.get("email")
    password = form_data.get("password")
    # TODO: validate credentials
    request.session["user"] = email

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="user_email",
        value=email,
        httponly=True,
        max_age=60*60*24*30  # 30 days
    )
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("user_email")
    return response
