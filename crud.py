from sqlalchemy.orm import Session
from sqlalchemy import desc
import models, schemas

def execute_production_run(
    db: Session, 
    product_id: int, 
    tenant_id: int, 
    quantity_produced: int, 
    labor_hours: float = 0.0, 
    hourly_rate: float = 0.0
):
    """
    1. THE BAKE: Deducts raw ingredients and creates a batch of Finished Goods.
    Now includes Labor and Overhead apportionment for true Net Margin analysis. 
    """
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise Exception("Product not found")
    
    total_cost_fifo = 0.0
    total_cost_newest = 0.0
    
    # --- STEP 1: DEDUCT RAW INGREDIENTS (FIFO) ---
    for item in product.recipe_items:
        total_qty_needed = item.quantity_required * quantity_produced 
        
        # Calculate newest replacement cost for secondary margin view 
        newest_lot = db.query(models.IngredientLot)\
            .filter(models.IngredientLot.ingredient_id == item.ingredient_id)\
            .order_by(desc(models.IngredientLot.purchase_date)).first()
         
        if newest_lot:
            cost_per_unit_newest = newest_lot.cost_total / newest_lot.quantity_purchased 
            total_cost_newest += (cost_per_unit_newest * total_qty_needed) 

        # Deduct from oldest physical inventory lots
        remaining_to_deduct = total_qty_needed
        while remaining_to_deduct > 0:
            oldest_lot = db.query(models.IngredientLot)\
                .filter(models.IngredientLot.ingredient_id == item.ingredient_id, 
                        models.IngredientLot.is_depleted == False)\
                .order_by(models.IngredientLot.purchase_date).first() 
            
            if not oldest_lot:
                raise Exception(f"Out of stock: {item.ingredient.name}")

            cost_per_unit_fifo = oldest_lot.cost_total / oldest_lot.quantity_purchased
             
            if oldest_lot.quantity_remaining >= remaining_to_deduct:
                oldest_lot.quantity_remaining -= remaining_to_deduct 
                total_cost_fifo += (cost_per_unit_fifo * remaining_to_deduct)
                remaining_to_deduct = 0 
            else:
                total_cost_fifo += (cost_per_unit_fifo * oldest_lot.quantity_remaining)
                remaining_to_deduct -= oldest_lot.quantity_remaining
                oldest_lot.quantity_remaining = 0 
                oldest_lot.is_depleted = True
            
            db.flush()

    # --- STEP 2: CALCULATE LABOR & OVERHEAD --- 
    
    # Calculate variable labor for this specific batch
    batch_labor_total = labor_hours * hourly_rate
    
    # Apportion Fixed Overhead (e.g., Rent, Utilities)
    # Strategy: Sum all monthly overhead and divide by a standard monthly volume (e.g., 2000 units)
    # In a production system, this ensures every pastry "carries" its share of the rent.
    monthly_overhead = db.query(func.sum(models.OverheadExpense.monthly_amount))\
                         .filter(models.OverheadExpense.tenant_id == tenant_id).scalar() or 0.0
    
    # Assuming a standard denominator for apportionment; 
    # alternatively, this can be dynamic based on previous month's total quantity_produced.
    standard_monthly_volume = 2000 
    overhead_per_unit = monthly_overhead / standard_monthly_volume

    # --- STEP 3: CREATE THE FINISHED GOODS BATCH ---
    
    # Final unit cost = (Ingredient Cost + Labor Cost) / Total Quantity + Overhead Share
    ingredient_cost_per_unit = total_cost_fifo / quantity_produced if quantity_produced > 0 else 0
    labor_cost_per_unit = batch_labor_total / quantity_produced if quantity_produced > 0 else 0
    
    final_net_cost_per_unit = ingredient_cost_per_unit + labor_cost_per_unit + overhead_per_unit

    new_batch = models.FinishedGoodsLot(
        tenant_id=tenant_id,
        product_id=product_id,
        quantity_produced=quantity_produced,
        quantity_remaining=quantity_produced,
        # We store the final Net Cost as the cost_per_unit_fifo for margin accuracy
        cost_per_unit_fifo=final_net_cost_per_unit,
        cost_per_unit_newest=total_cost_newest / quantity_produced if quantity_produced > 0 else 0
    )
    
    db.add(new_batch)
    
    # Log labor record for auditing
    if labor_hours > 0:
        db.add(models.LaborLog(
            tenant_id=tenant_id,
            lot_id=new_batch.id,
            hours_spent=labor_hours,
            hourly_rate=hourly_rate,
            total_labor_cost=batch_labor_total
        ))

    db.commit()
    return new_batch


def record_finished_goods_sale(db: Session, product_id: int, tenant_id: int, quantity_sold: int):
    """
    2. THE SALE: Deducts from baked inventory and logs the final financial transaction.
    """
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    
    remaining_to_sell = quantity_sold
    total_fifo_cost = 0.0
    total_newest_cost = 0.0
    
    while remaining_to_sell > 0:
        # Find the oldest batch of baked goods sitting on the counter
        oldest_batch = db.query(models.FinishedGoodsLot)\
            .filter(models.FinishedGoodsLot.product_id == product_id,
                    models.FinishedGoodsLot.is_depleted == False)\
            .order_by(models.FinishedGoodsLot.production_date).first()
            
        if not oldest_batch:
            raise Exception(f"Not enough baked {product.name} in stock! You must run a production bake first.")
            
        if oldest_batch.quantity_remaining >= remaining_to_sell:
            oldest_batch.quantity_remaining -= remaining_to_sell
            total_fifo_cost += (oldest_batch.cost_per_unit_fifo * remaining_to_sell)
            total_newest_cost += (oldest_batch.cost_per_unit_newest * remaining_to_sell)
            remaining_to_sell = 0
        else:
            total_fifo_cost += (oldest_batch.cost_per_unit_fifo * oldest_batch.quantity_remaining)
            total_newest_cost += (oldest_batch.cost_per_unit_newest * oldest_batch.quantity_remaining)
            remaining_to_sell -= oldest_batch.quantity_remaining
            oldest_batch.quantity_remaining = 0
            oldest_batch.is_depleted = True
            
        db.flush()

    # Calculate final margins and log the sale 
    total_revenue = product.retail_price * quantity_sold
    margin_fifo = total_revenue - total_fifo_cost
    margin_newest = total_revenue - total_newest_cost
    
    new_log = models.TransactionLog(
        tenant_id=tenant_id,
        product_id=product_id,
        sale_price=total_revenue, 
        margin_fifo=margin_fifo,
        margin_newest=margin_newest
    )
    
    db.add(new_log)
    db.commit()
    return new_log

def log_finished_goods_waste(db: Session, lot_id: int, tenant_id: int, qty: int, reason: str):
    lot = db.query(models.FinishedGoodsLot).filter(
        models.FinishedGoodsLot.id == lot_id,
        models.FinishedGoodsLot.tenant_id == tenant_id
    ).first()

    if not lot or lot.quantity_remaining < qty:
        raise Exception("Not enough baked stock in this lot to waste.")

    # Deduct from the specific batch
    lot.quantity_remaining -= qty
    if lot.quantity_remaining <= 0:
        lot.is_depleted = True

    new_waste = models.FinishedGoodsWasteLog(
        tenant_id=tenant_id,
        product_id=lot.product_id,
        lot_id=lot.id,
        quantity_wasted=qty,
        reason=reason
    )
    db.add(new_waste)
    db.commit()
    return new_waste

def record_finished_goods_waste(db: Session, lot_id: int, tenant_id: int, quantity_wasted: int, reason: str):
    """
    Deducts unsold baked goods from a specific batch and logs the loss.
    """
    # 1. Locate the specific batch
    lot = db.query(models.FinishedGoodsLot).filter(
        models.FinishedGoodsLot.id == lot_id,
        models.FinishedGoodsLot.tenant_id == tenant_id
    ).first()

    if not lot:
        raise Exception("Finished goods batch not found.")
    
    if lot.quantity_remaining < quantity_wasted:
        raise Exception(f"Not enough stock in batch #{lot_id} to waste that amount.")

    # 2. Deduct from the counter/inventory
    lot.quantity_remaining -= quantity_wasted
    if lot.quantity_remaining <= 0:
        lot.is_depleted = True

    # 3. Create the waste record
    waste_entry = models.FinishedGoodsWasteLog(
        tenant_id=tenant_id,
        product_id=lot.product_id,
        lot_id=lot.id,
        quantity_wasted=quantity_wasted,
        reason=reason
    )
    
    db.add(waste_entry)
    db.commit()
    return waste_entry