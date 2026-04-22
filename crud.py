from sqlalchemy.orm import Session
from sqlalchemy import desc
import models, schemas

def process_bake_and_calculate_margins(db: Session, product_id: int, tenant_id: int):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    
    total_cost_fifo = 0.0
    total_cost_newest = 0.0
    
    # 1. Loop through every ingredient in the recipe
    for item in product.recipe_items:
        qty_needed = item.quantity_required
        
        # --- NEWEST PURCHASE PRICE CALCULATION ---
        newest_lot = db.query(models.IngredientLot)\
            .filter(models.IngredientLot.ingredient_id == item.ingredient_id)\
            .order_by(desc(models.IngredientLot.purchase_date)).first()
        
        if newest_lot:
            cost_per_unit_newest = newest_lot.cost_total / newest_lot.quantity_purchased
            total_cost_newest += (cost_per_unit_newest * qty_needed)

        # --- FIFO DEDUCTION & OLDEST PRICE CALCULATION ---
        remaining_to_deduct = qty_needed
        
        while remaining_to_deduct > 0:
            # Find the oldest lot that isn't empty
            oldest_lot = db.query(models.IngredientLot)\
                .filter(models.IngredientLot.ingredient_id == item.ingredient_id, 
                        models.IngredientLot.is_depleted == False)\
                .order_by(models.IngredientLot.purchase_date).first()
            
            if not oldest_lot:
                raise Exception(f"Out of stock: {item.ingredient.name}")

            cost_per_unit_fifo = oldest_lot.cost_total / oldest_lot.quantity_purchased
            
            if oldest_lot.quantity_remaining >= remaining_to_deduct:
                # This lot has enough to cover the rest of the recipe
                total_cost_fifo += (cost_per_unit_fifo * remaining_to_deduct)
                oldest_lot.quantity_remaining -= remaining_to_deduct
                remaining_to_deduct = 0
            else:
                # Use what's left in this lot and move to the next
                total_cost_fifo += (cost_per_unit_fifo * oldest_lot.quantity_remaining)
                remaining_to_deduct -= oldest_lot.quantity_remaining
                oldest_lot.quantity_remaining = 0
                oldest_lot.is_depleted = True
    
    # 2. Record the transaction with the margins
    margin_fifo = product.retail_price - total_cost_fifo
    margin_newest = product.retail_price - total_cost_newest
    
    new_log = models.TransactionLog(
        tenant_id=tenant_id,
        product_id=product_id,
        sale_price=product.retail_price,
        margin_fifo=margin_fifo,
        margin_newest=margin_newest
    )
    
    db.add(new_log)
    db.commit()
    return new_log
    