from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import database, crud, schemas, models, utils
from auth import get_current_user, get_tenant_db, check_admin_or_owner
from sqlalchemy import func
from typing import List

router = APIRouter(prefix="/sales", tags=["Sales"])

@router.post("/record-sale", response_model=schemas.SaleResponse)
def record_sale(
    sale: schemas.SaleCreate, 
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db) 
):
    try:
        result = crud.record_finished_goods_sale(
            db=db, 
            product_id=sale.item_id, 
            tenant_id=current_user.tenant_id,
            quantity_sold=sale.quantity,
            custom_revenue=(sale.price * sale.quantity) # Now respects the price sent from the frontend!
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
    
    # 1. Get Total Revenue and Ingredient Costs from Sales 
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
    check_admin_or_owner(current_user)

    # 1. Calculate Gross Revenue and Ingredient/Labor Costs (COGS)
    sales_query = db.query(
        func.sum(models.TransactionLog.sale_price).label("revenue"),
        func.sum(models.TransactionLog.sale_price - models.TransactionLog.margin_fifo).label("cogs")
    ).filter(models.TransactionLog.tenant_id == current_user.tenant_id).first()

    revenue = sales_query.revenue or 0.0
    cogs = sales_query.cogs or 0.0

    # 2. Total Waste Loss (Baked goods thrown away)
    waste_loss = db.query(
        func.sum(models.FinishedGoodsWasteLog.quantity_wasted * models.FinishedGoodsLot.cost_per_unit_fifo)
    ).join(models.FinishedGoodsLot).filter(
        models.FinishedGoodsWasteLog.tenant_id == current_user.tenant_id
    ).scalar() or 0.0

    # 3. Total Monthly Overhead (The "Lump Sum" you want to see deducted)
    total_overhead = db.query(
        func.sum(models.OverheadExpense.monthly_amount)
    ).filter(models.OverheadExpense.tenant_id == current_user.tenant_id).scalar() or 0.0

    # NEW FORMULA: Profit = Revenue - COGS - Waste - Total Overhead
    net_profit = revenue - cogs - waste_loss - total_overhead

    return {
        "total_revenue": round(revenue, 2),
        "total_waste_loss": round(waste_loss, 2),
        "total_overhead": round(total_overhead, 2),
        "net_profit": round(net_profit, 2)
    }

@router.get("/history")
def get_transaction_history(
    db: Session = Depends(get_tenant_db), 
    current_user: models.User = Depends(get_current_user)
):
    # Join with Product table to get the name [cite: 200, 201]
    transactions = db.query(
        models.TransactionLog, 
        models.Product.name
    ).join(
        models.Product, 
        models.TransactionLog.product_id == models.Product.id
    ).filter(
        models.TransactionLog.tenant_id == current_user.tenant_id
    ).order_by(models.TransactionLog.timestamp.desc()).all()

    # Format the data for the frontend, now including customer_name [cite: 201]
    return [{
        "timestamp": t[0].timestamp,
        "customer_name": t[0].customer_name or "Retail", # NEW FIELD
        "product_name": t[1],
        "sale_price": t[0].sale_price,
        "margin_fifo": t[0].margin_fifo
    } for t in transactions]

@router.get("/overhead", response_model=List[schemas.OverheadResponse])
def list_overhead(db: Session = Depends(get_tenant_db)):
    return db.query(models.OverheadExpense).all()

@router.post("/overhead", response_model=schemas.OverheadResponse)
def add_overhead(
    expense: schemas.OverheadCreate, 
    db: Session = Depends(get_tenant_db),
    current_user: models.User = Depends(get_current_user)
):
    new_exp = models.OverheadExpense(
        tenant_id=current_user.tenant_id,
        **expense.dict()
    )
    db.add(new_exp)
    db.commit()
    return new_exp

@router.delete("/overhead/{expense_id}")
def delete_overhead(expense_id: int, db: Session = Depends(get_tenant_db)):
    exp = db.query(models.OverheadExpense).filter(models.OverheadExpense.id == expense_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(exp)
    db.commit()
    return {"message": "Deleted"}