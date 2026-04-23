from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas, crud
from auth import get_current_user, get_tenant_db
from typing import List
from sqlalchemy import func, cast, Date
from datetime import datetime

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

@router.post("/schedule-batch")
def schedule_planned_batch(
    batch: schemas.PlannedBatchCreate,
    db: Session = Depends(get_tenant_db),
    current_user: models.User = Depends(get_current_user)
):
    """Allows a manager to manually inject a production run for a specific date."""
    new_batch = models.PlannedBatch(
        tenant_id=current_user.tenant_id,
        product_id=batch.product_id,
        planned_quantity=batch.planned_quantity,
        scheduled_date=batch.scheduled_date
    )
    db.add(new_batch)
    db.commit()
    db.refresh(new_batch)
    return new_batch

@router.get("/prep-list", response_model=List[schemas.PrepListItem])
def get_daily_prep_list(
    db: Session = Depends(get_tenant_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Generates the morning prep list by calculating:
    (Retail Par - Current Stock) + Custom Orders + Today's Planned Batches
    """
    products = db.query(models.Product).all()
    today = datetime.utcnow().date()
    
    # 1. Sum up existing baked stock sitting on the counter
    current_stock = db.query(
        models.FinishedGoodsLot.product_id,
        func.sum(models.FinishedGoodsLot.quantity_remaining).label("qty")
    ).filter(
        models.FinishedGoodsLot.is_depleted == False
    ).group_by(models.FinishedGoodsLot.product_id).all()
    stock_map = {item.product_id: item.qty for item in current_stock}

    # 2. Sum up Custom Orders marked as "Baking Scheduled"
    custom_orders = db.query(
        models.CustomOrderItem.product_id,
        func.sum(models.CustomOrderItem.quantity).label("qty")
    ).join(models.CustomOrder).filter(
        models.CustomOrder.status == models.OrderStatus.BAKING_SCHEDULED
    ).group_by(models.CustomOrderItem.product_id).all()
    custom_map = {item.product_id: item.qty for item in custom_orders}

    # 3. Sum up Today's Planned Batches (NEW)
    planned_batches = db.query(
        models.PlannedBatch.product_id,
        func.sum(models.PlannedBatch.planned_quantity).label("qty")
    ).filter(
        cast(models.PlannedBatch.scheduled_date, Date) == today,
        models.PlannedBatch.is_completed == False
    ).group_by(models.PlannedBatch.product_id).all()
    planned_map = {item.product_id: item.qty for item in planned_batches}

    # 4. Get Retail Par Levels
    par_levels = db.query(models.ProductParLevel).all()
    par_map = {par.product_id: par.target_quantity for par in par_levels}

    # 5. Calculate the Prep List
    prep_list = []
    for product in products:
        target_par = par_map.get(product.id, 0)
        current_inventory = stock_map.get(product.id, 0)
        
        # Retail deficit
        retail_deficit = target_par - current_inventory
        retail_needed = retail_deficit if retail_deficit > 0 else 0
        
        # Add custom orders & planned batches
        custom_needed = custom_map.get(product.id, 0)
        planned_needed = planned_map.get(product.id, 0)
        
        # THE NEW MATH
        total_to_bake = retail_needed + custom_needed + planned_needed
        
        if total_to_bake > 0:
            prep_list.append(
                schemas.PrepListItem(
                    product_id=product.id,
                    product_name=product.name,
                    retail_par_needed=retail_needed,
                    custom_order_needed=custom_needed,
                    planned_batch_needed=planned_needed, # Added to response
                    total_to_bake=total_to_bake
                )
            )
            
    return prep_list