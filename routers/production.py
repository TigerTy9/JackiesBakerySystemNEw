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

@router.post("/log-waste")
def log_finished_goods_waste(
    lot_id: int, 
    qty: int, 
    reason: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    # Find the specific batch
    lot = db.query(models.FinishedGoodsLot).filter(
        models.FinishedGoodsLot.id == lot_id,
        models.FinishedGoodsLot.tenant_id == current_user.tenant_id
    ).first()

    if not lot or lot.quantity_remaining < qty:
        raise HTTPException(status_code=400, detail="Insufficient stock in this lot to waste.")

    # Deduct from physical inventory
    lot.quantity_remaining -= qty
    if lot.quantity_remaining <= 0:
        lot.is_depleted = True

    new_waste = models.FinishedGoodsWasteLog(
        tenant_id=current_user.tenant_id,
        product_id=lot.product_id,
        lot_id=lot.id,
        quantity_wasted=qty,
        reason=reason
    )
    db.add(new_waste)
    db.commit()
    return {"message": "Finished goods waste logged. Margins updated."}

@router.post("/log-waste", response_model=schemas.FinishedGoodsResponse)
def log_production_waste(
    lot_id: int, 
    qty: int, 
    reason: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    try:
        # Call the function we just defined in crud.py
        waste_record = crud.record_finished_goods_waste(
            db=db,
            lot_id=lot_id,
            tenant_id=current_user.tenant_id,
            quantity_wasted=qty,
            reason=reason
        )
        return waste_record
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))