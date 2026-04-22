from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import database, crud, schemas, models
from auth import get_current_user, check_admin_or_owner

router = APIRouter(prefix="/sales", tags=["Sales"])

@router.post("/record-sale", response_model=schemas.SaleResponse)
def record_sale(sale: schemas.SaleCreate, db: Session = Depends(database.get_db)):
    try:
        return crud.process_bake_and_calculate_margins(db, sale.product_id, sale.tenant_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get("/margins/{product_id}")
def get_product_margins(
    product_id: int, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Security Check
    check_admin_or_owner(current_user)
    
    # Financial Query
    stats = db.query(models.TransactionLog).filter(
        models.TransactionLog.product_id == product_id,
        models.TransactionLog.tenant_id == current_user.tenant_id
    ).order_by(models.TransactionLog.timestamp.desc()).first()
    
    if not stats:
        raise HTTPException(status_code=404, detail="No sales data found")
        
    return {
        "fifo_margin": stats.margin_fifo,
        "newest_margin": stats.margin_newest,
        "status": utils.get_margin_status(stats.margin_fifo, stats.margin_newest)
    }