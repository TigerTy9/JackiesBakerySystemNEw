from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import database, models, schemas
from auth import hash_password

router = APIRouter(prefix="/tenants", tags=["tenants"])

@router.post("/", response_model=schemas.TenantResponse)
def create_tenant(tenant: schemas.TenantCreate, db: Session = Depends(database.get_db)):
    # 1. Map Schema 'name' to Model 'business_name'
    # 2. Generate a basic domain from the name
    generated_domain = f"{tenant.name.lower().replace(' ', '-')}.bakeryos.com"
    
    db_tenant = models.Tenant(
        business_name=tenant.name,
        email=tenant.email,
        domain=generated_domain
    )
    
    try:
        db.add(db_tenant)
        db.commit()
        db.refresh(db_tenant)
        return db_tenant
    except Exception as e:
        db.rollback()
        # This catches things like duplicate names/emails
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")

@router.post("/register-user", response_model=schemas.UserResponse)
def register_user(user_in: schemas.UserCreate, db: Session = Depends(database.get_db)):
    # 1. Check if user already exists
    existing_user = db.query(models.User).filter(models.User.username == user_in.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # 2. Hash the password before saving 
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