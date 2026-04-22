from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import database, models, schemas
from auth import get_current_user, get_tenant_db

router = APIRouter(prefix="/orders", tags=["Custom Orders"])

@router.post("/request-quote", response_model=schemas.CustomOrderResponse)
def create_custom_order(
    order: schemas.CustomOrderCreate, 
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    # 1. Create the parent order record
    new_order = models.CustomOrder(
        tenant_id=current_user.tenant_id,
        customer_name=order.customer_name,
        customer_email=order.customer_email,
        description=order.description,
        delivery_date=order.delivery_date
    )
    db.add(new_order)
    db.flush() # Flushes to DB to get the new_order.id without committing yet

    # 2. Add all associated products to the order
    for item in order.items:
        new_item = models.CustomOrderItem(
            custom_order_id=new_order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            price_override=item.price_override
        )
        db.add(new_item)

    # 3. Commit the entire transaction safely
    db.commit()
    db.refresh(new_order)
    return new_order

@router.put("/{order_id}/update-pipeline", response_model=schemas.CustomOrderResponse)
def update_order_pipeline(
    order_id: int, 
    update_data: schemas.CustomOrderUpdate,
    db: Session = Depends(get_tenant_db)
):
    # RLS ensures they can only update their own bakery's orders
    order = db.query(models.CustomOrder).filter(models.CustomOrder.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    if update_data.total_price is not None:
        order.total_price = update_data.total_price
    if update_data.deposit_amount is not None:
        order.deposit_amount = update_data.deposit_amount
    if update_data.status is not None:
        order.status = update_data.status
        
    db.commit()
    db.refresh(order)
    return order

@router.get("/pipeline", response_model=List[schemas.CustomOrderResponse])
def get_active_orders(db: Session = Depends(get_tenant_db)):
    # Returns all orders not yet completed or cancelled
    orders = db.query(models.CustomOrder).filter(
        models.CustomOrder.status.notin_([models.OrderStatus.COMPLETED, models.OrderStatus.CANCELLED])
    ).order_by(models.CustomOrder.delivery_date).all()
    return orders