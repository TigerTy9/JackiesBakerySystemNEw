# main.py
from fastapi import FastAPI, Depends, HTTPException, status
from database import engine, get_db
import models
from routers import inventory, sales, tenants
from fastapi.security import OAuth2PasswordRequestForm
import auth
from sqlalchemy.orm import Session

# This line creates the actual PostgreSQL tables if they don't exist
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="BakeryOS SaaS")

app.include_router(tenants.router)   # For you to add new clients
app.include_router(inventory.router) # For the baker to add flour/sugar
app.include_router(sales.router)     # For the POS/Auto-subtract logic

@app.get("/")
def health_check():
    return {"status": "active", "system": "BakeryOS"}

@app.post("/login")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    # 1. Look up the user
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    
    # 2. Verify password against the hash 
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Incorrect username or password"
        )
    
    # 3. Create the token [cite: 54]
    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}