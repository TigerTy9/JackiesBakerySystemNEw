import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import database, models, schemas
from auth import hash_password

router = APIRouter(prefix="/tenants", tags=["tenants"])

def slugify_domain(name: str) -> str:
    """
    Converts a business name into a DNS-safe subdomain.
    Example: "Jackie's Bakery!" -> "jackies-bakery"
    """
    # 1. Lowercase and strip whitespace
    name = name.lower().strip()
    # 2. Replace spaces with hyphens
    name = name.replace(' ', '-')
    # 3. Remove any character that isn't a-z, 0-9, or a hyphen
    name = re.sub(r'[^a-z0-9-]', '', name)
    # 4. Remove duplicate hyphens (e.g. "Bakery -- Shop" -> "bakery-shop")
    name = re.sub(r'-+', '-', name)
    # 5. Trim hyphens from the start/end
    return name.strip('-')

@router.post("/", response_model=schemas.TenantResponse)
def create_tenant(tenant: schemas.TenantCreate, db: Session = Depends(database.get_db)):
    # Generate the clean, safe subdomain
    subdomain = slugify_domain(tenant.name)
    
    if not subdomain:
        raise HTTPException(status_code=400, detail="Business name must contain alphanumeric characters.")

    full_domain = f"{subdomain}.flourish.name"

    # Check for domain collisions (uniqueness check)
    existing_domain = db.query(models.Tenant).filter(models.Tenant.domain == full_domain).first()
    if existing_domain:
        raise HTTPException(
            status_code=400, 
            detail=f"The domain '{full_domain}' is already taken. Please try a different business name."
        )

    db_tenant = models.Tenant(
        business_name=tenant.name,
        email=tenant.email,
        domain=full_domain
    )
    
    try:
        db.add(db_tenant)
        db.commit()
        db.refresh(db_tenant)
        return db_tenant
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Could not create tenant. Name or Email may already exist.")

@router.post("/register-user", response_model=schemas.UserResponse)
def register_user(user_in: schemas.UserCreate, db: Session = Depends(database.get_db)):
    existing_user = db.query(models.User).filter(models.User.username == user_in.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_pwd = hash_password(user_in.password)
    
    new_user = models.User(
        tenant_id=user_in.tenant_id,
        username=user_in.username,
        hashed_password=hashed_pwd,
        role=user_in.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

