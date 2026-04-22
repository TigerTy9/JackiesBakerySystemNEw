from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas, crud
from auth import get_current_user, get_tenant_db
from typing import List

router = APIRouter(prefix="/production", tags=["Production Runs"])

@router.post("/run", response_model=schemas.FinishedGoodsResponse)
def log_production_run(
    run: schemas.ProductionRunCreate, 
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    try:
        # Executes the bake, subtracts raw ingredients, yields finished pastries
        batch = crud.execute_production_run(
            db=db, 
            product_id=run.product_id, 
            tenant_id=current_user.tenant_id, 
            quantity_produced=run.quantity_produced
        )
        return batch
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/finished-inventory", response_model=List[schemas.FinishedGoodsResponse])
def get_ready_to_sell_inventory(db: Session = Depends(get_tenant_db)):
    # RLS ensures they only see their own baked goods
    return db.query(models.FinishedGoodsLot).filter(models.FinishedGoodsLot.is_depleted == False).all()