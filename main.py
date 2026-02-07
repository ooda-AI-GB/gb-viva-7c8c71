import uvicorn
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from typing import Optional
import bcrypt

from database import SessionLocal, engine, Employee, init_db

# Initialize Database
init_db()

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Session Middleware (Secret key should be env var in prod)
app.add_middleware(SessionMiddleware, secret_key="super-secret-key-change-me")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Hardcoded Users (using bcrypt to hash passwords for demo consistency, 
# though we are just comparing against hardcoded strings in this simple example,
# the requirement asked to use bcrypt. 
# Since users are hardcoded, I will pre-calculate the hash for "password123" 
# to demonstrate verification or just do it on the fly for simplicity since it's hardcoded.)
# Actually, the requirement says "Login page — simple username/password with 2 hardcoded users".
# It also says "Use bcrypt directly". I will simulate a proper check.

# Generating a hash for "password"
# hashed = bcrypt.hashpw("password".encode('utf-8'), bcrypt.gensalt())
# For simplicity in this demo, I'll just store the plain text in the hardcoded dict
# and hash the input to verify against a stored hash, OR better yet, store the hash.

ADMIN_HASH = bcrypt.hashpw("adminpass".encode('utf-8'), bcrypt.gensalt())
USER_HASH = bcrypt.hashpw("userpass".encode('utf-8'), bcrypt.gensalt())

USERS = {
    "admin": {"password_hash": ADMIN_HASH, "role": "admin", "name": "System Administrator"},
    "employee": {"password_hash": USER_HASH, "role": "employee", "name": "John Doe"},
}

# Seeding
def seed_data(db: Session):
    if db.query(Employee).count() == 0:
        employees = [
            Employee(name="Alice Smith", department="Engineering", email="alice@company.com", phone="555-0101", job_title="Senior Engineer"),
            Employee(name="Bob Jones", department="Engineering", email="bob@company.com", phone="555-0102", job_title="Software Developer"),
            Employee(name="Charlie Brown", department="HR", email="charlie@company.com", phone="555-0103", job_title="HR Manager"),
            Employee(name="David Wilson", department="Sales", email="david@company.com", phone="555-0104", job_title="Sales Director"),
            Employee(name="Eve Davis", department="Engineering", email="eve@company.com", phone="555-0105", job_title="DevOps Engineer"),
            Employee(name="Frank Miller", department="Sales", email="frank@company.com", phone="555-0106", job_title="Account Executive"),
            Employee(name="Grace Lee", department="HR", email="grace@company.com", phone="555-0107", job_title="Recruiter"),
            Employee(name="Hank Green", department="Engineering", email="hank@company.com", phone="555-0108", job_title="QA Engineer"),
            Employee(name="Ivy White", department="Marketing", email="ivy@company.com", phone="555-0109", job_title="Marketing Lead"),
            Employee(name="Jack Black", department="Marketing", email="jack@company.com", phone="555-0110", job_title="Content Creator"),
        ]
        db.add_all(employees)
        db.commit()

# Run seed on startup
@app.on_event("startup")
def on_startup():
    with SessionLocal() as db:
        seed_data(db)

# Helper to get current user from session
def get_current_user(request: Request):
    user_id = request.session.get("user")
    if user_id and user_id in USERS:
        return USERS[user_id]
    return None

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/directory", status_code=303)
    return RedirectResponse(url="/login", status_code=303)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = USERS.get(username)
    if not user:
         return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})
    
    # Verify password
    if bcrypt.checkpw(password.encode('utf-8'), user["password_hash"]):
        request.session["user"] = username
        return RedirectResponse(url="/directory", status_code=303)
    else:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

@app.get("/directory", response_class=HTMLResponse)
async def directory(request: Request, q: Optional[str] = None, db: Session = Depends(get_db)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    
    query = db.query(Employee)
    if q:
        search = f"%{q}%"
        query = query.filter(
            (Employee.name.ilike(search)) |
            (Employee.department.ilike(search)) |
            (Employee.job_title.ilike(search))
        )
    
    employees = query.all()
    return templates.TemplateResponse("directory.html", {
        "request": request, 
        "employees": employees, 
        "user": user, 
        "q": q
    })

@app.get("/add-employee", response_class=HTMLResponse)
async def add_employee_page(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/directory", status_code=303)
    
    return templates.TemplateResponse("add_employee.html", {"request": request, "user": user})

@app.post("/add-employee", response_class=HTMLResponse)
async def add_employee(
    request: Request,
    name: str = Form(...),
    department: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    job_title: str = Form(...),
    db: Session = Depends(get_db)
):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/directory", status_code=303)
    
    new_employee = Employee(
        name=name,
        department=department,
        email=email,
        phone=phone,
        job_title=job_title
    )
    db.add(new_employee)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse("add_employee.html", {
            "request": request, 
            "user": user, 
            "error": "Error adding employee. Email might already exist."
        })
        
    return RedirectResponse(url="/directory", status_code=303)

@app.get("/health")
async def health():
    return JSONResponse(content={"status": "ok"})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
