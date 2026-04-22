from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import database, crud, schemas

router = APIRouter(prefix="/sales", tags=["Sales"])

@router.post("/record-sale", response_model=schemas.SaleResponse)
def record_sale(sale: schemas.SaleCreate, db: Session = Depends(database.get_db)):
    try:
        return crud.process_bake_and_calculate_margins(db, sale.product_id, sale.tenant_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))