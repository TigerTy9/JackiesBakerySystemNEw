from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import database, crud, schemas, models, utils
from auth import get_current_user, get_tenant_db, check_admin_or_owner

router = APIRouter(prefix="/sales", tags=["Sales"])

@router.post("/record-sale", response_model=schemas.SaleResponse)
def record_sale(
    sale: schemas.SaleCreate, 
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db) 
):
    try:
        # This now subtracts from Finished Goods instead of raw ingredients
        result = crud.record_finished_goods_sale(
            db=db, 
            product_id=sale.item_id, 
            tenant_id=current_user.tenant_id,
            quantity_sold=sale.quantity 
        )
        return result
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