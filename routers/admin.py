from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import models, database

router = APIRouter(prefix="/admin", tags=["Super Admin"])

@router.post("/create-tenant")
def create_new_bakery(name: str, domain: str, db: Session = Depends(database.get_db)):
    new_bakery = models.Tenant(business_name=name, domain=domain)
    db.add(new_bakery)
    db.commit()
    return {"message": f"Bakery {name} is now live on the platform."}

@router.get("/global-stats")
def get_platform_metrics(db: Session = Depends(database.get_db)):
    # Total revenue processed across all bakeries (for your marketing)
    total_sales = db.query(models.TransactionLog).count()
    return {"total_transactions_managed": total_sales}