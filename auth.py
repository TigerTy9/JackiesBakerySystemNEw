import os
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import text

# Internal imports from your project structure [cite: 1, 9, 75]
import database, models

# Configuration [cite: 28, 84]
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY", "SUPER_SECRET_BAKERY_KEY") 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# --- Utility Functions ---

def hash_password(password: str):
    """Encodes plain text password into a secure hash."""
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    """Checks if the provided password matches the stored hash."""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    """Generates a JWT token for a validated user[cite: 89]."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# --- Dependency Injection ---

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    """
    The security 'guard'. Extract this into your routes to identify 
    which bakery (tenant) is making the request[cite: 36, 66].
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

def check_admin_or_owner(current_user: models.User):
    if current_user.role not in ["admin", "owner"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation restricted to Owners/Admins"
        )
    return True

def get_tenant_db(
    current_user: models.User = Depends(get_current_user), 
    db: Session = Depends(database.get_db)
):
    """
    SaaS Security Layer: Injects the tenant_id into the PostgreSQL session.
    RLS will automatically filter all subsequent queries in this transaction.
    """
    # SET LOCAL only lasts for the duration of this specific database transaction
    db.execute(text(f"SET LOCAL app.tenant_id = '{current_user.tenant_id}'"))
    
    return db