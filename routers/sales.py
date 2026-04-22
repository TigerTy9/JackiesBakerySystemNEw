from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import database, crud, schemas, models, utils
from auth import get_current_user, get_tenant_db, check_admin_or_owner
from sqlalchemy import func

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
    check_admin_or_owner(current_user)
    
    # 1. Get Total Revenue and Ingredient Costs from Sales [cite: 116, 140]
    sales_data = db.query(
        func.sum(models.TransactionLog.sale_price).label("revenue"),
        func.sum(models.TransactionLog.sale_price - models.TransactionLog.margin_fifo).label("cogs")
    ).filter(
        models.TransactionLog.product_id == product_id,
        models.TransactionLog.tenant_id == current_user.tenant_id
    ).first()

    # 2. Get Total Cost of Wasted Finished Goods
    # We join with the Lot to get the cost_per_unit fixed at the time of baking 
    waste_cost = db.query(
        func.sum(models.FinishedGoodsWasteLog.quantity_wasted * models.FinishedGoodsLot.cost_per_unit_fifo)
    ).join(models.FinishedGoodsLot).filter(
        models.FinishedGoodsWasteLog.product_id == product_id,
        models.FinishedGoodsWasteLog.tenant_id == current_user.tenant_id
    ).scalar() or 0.0

    if not sales_data.revenue:
        raise HTTPException(status_code=404, detail="No sales data found")

    net_margin = sales_data.revenue - sales_data.cogs - waste_cost
        
    return {
        "gross_revenue": sales_data.revenue,
        "net_margin": net_margin,
        "waste_loss": waste_cost,
        "status": "Warning: High Waste" if waste_cost > (sales_data.revenue * 0.1) else "Healthy"
    }

@router.get("/financial-summary")
def get_bakery_finances(
    db: Session = Depends(get_tenant_db), 
    current_user: models.User = Depends(get_current_user)
):
    # Ensure only owners can see the money
    check_admin_or_owner(current_user)

    # Use COALESCE/scalar logic to prevent NoneType errors in Python
    # 1. Total Revenue and COGS
    sales_query = db.query(
        func.sum(models.TransactionLog.sale_price).label("revenue"),
        func.sum(models.TransactionLog.sale_price - models.TransactionLog.margin_fifo).label("cogs")
    ).filter(models.TransactionLog.tenant_id == current_user.tenant_id).first()

    revenue = sales_query.revenue if sales_query.revenue is not None else 0.0
    cogs = sales_query.cogs if sales_query.cogs is not None else 0.0

    # 2. Total Financial Loss from Waste [cite: 36, 38]
    # We join FinishedGoodsWasteLog to the Lot to find the original cost
    waste_loss = db.query(
        func.sum(models.FinishedGoodsWasteLog.quantity_wasted * models.FinishedGoodsLot.cost_per_unit_fifo)
    ).join(models.FinishedGoodsLot).filter(
        models.FinishedGoodsWasteLog.tenant_id == current_user.tenant_id
    ).scalar() or 0.0

    net_profit = revenue - cogs - waste_loss

    return {
        "total_revenue": revenue,
        "total_waste_loss": waste_loss,
        "net_profit": net_profit
    }