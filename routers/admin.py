from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, database, auth

router = APIRouter(prefix="/admin", tags=["Super Admin"])

@router.post("/create-tenant")
def create_new_bakery(name: str, domain: str, db: Session = Depends(database.get_db)):
    new_bakery = models.Tenant(business_name=name, domain=domain)
    db.add(new_bakery)
    db.commit()
    return {"message": f"Bakery {name} is now live on the platform."}

@router.get("/global-stats")
def get_platform_metrics(db: Session = Depends(database.get_db)):
    total_sales = db.query(models.TransactionLog).count()
    return {"total_transactions_managed": total_sales}

@router.get("/list-tenants")
def get_all_tenants(db: Session = Depends(database.get_db)):
    tenants = db.query(models.Tenant).order_by(models.Tenant.created_at.desc()).all()
    return tenants

@router.get("/list-users")
def get_all_users(db: Session = Depends(database.get_db)):
    users = db.query(models.User).all()
    result = []
    for u in users:
        result.append({
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "tenant_id": u.tenant_id,
            "business_name": u.tenant.business_name if u.tenant else "Orphaned"
        })
    return result

@router.delete("/delete-user/{user_id}")
def delete_user(user_id: int, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}

@router.get("/recent-activity")
def get_recent_activity(db: Session = Depends(database.get_db)):
    # Grab the 15 most recent sales across the entire SaaS platform
    logs = db.query(models.TransactionLog).order_by(models.TransactionLog.timestamp.desc()).limit(15).all()
    
    activity = []
    for log in logs:
        tenant = db.query(models.Tenant).filter(models.Tenant.id == log.tenant_id).first()
        product = db.query(models.Product).filter(models.Product.id == log.product_id).first()
        
        activity.append({
            "id": log.id,
            "tenant_name": tenant.business_name if tenant else f"Tenant #{log.tenant_id}",
            "product_name": product.name if product else f"Product #{log.product_id}",
            "amount": log.sale_price,
            "time": log.timestamp
        })
    return activity

@router.post("/impersonate/{user_id}")
def impersonate_user(user_id: int, db: Session = Depends(database.get_db)):
    # Find the user
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Generate a valid JWT token just like the normal login route does [cite: 89, 90]
    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}