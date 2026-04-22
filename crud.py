from sqlalchemy.orm import Session
from sqlalchemy import desc
import models, schemas

def process_bake_and_calculate_margins(db: Session, product_id: int, tenant_id: int, quantity_sold: int = 1):
    """
    Processes a bake/sale by deducting raw ingredients from lots using FIFO logic.
    Calculates margins based on both the oldest and newest purchase costs.
    """
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise Exception("Product not found")
    
    total_cost_fifo = 0.0
    total_cost_newest = 0.0
    
    # 1. Loop through every ingredient in the recipe 
    for item in product.recipe_items:
        # --- BULK CALCULATION ---
        # Multiply the single recipe requirement by the number of items actually baked
        total_qty_needed = item.quantity_required * quantity_sold
        
        # --- NEWEST PURCHASE PRICE CALCULATION ---
        # We look up the most recent lot to see what it would cost to replace these ingredients today
        newest_lot = db.query(models.IngredientLot)\
            .filter(models.IngredientLot.ingredient_id == item.ingredient_id)\
            .order_by(desc(models.IngredientLot.purchase_date)).first()
        
        if newest_lot:
            cost_per_unit_newest = newest_lot.cost_total / newest_lot.quantity_purchased
            total_cost_newest += (cost_per_unit_newest * total_qty_needed)

        # --- FIFO DEDUCTION & OLDEST PRICE CALCULATION --- 
        # We deduct from the oldest available lots first until the requirement is met
        remaining_to_deduct = total_qty_needed
        
        while remaining_to_deduct > 0:
            print(f"DEBUG: Ingredient ID {item.ingredient_id} - Need: {remaining_to_deduct}")
            
            oldest_lot = db.query(models.IngredientLot)\
                .filter(models.IngredientLot.ingredient_id == item.ingredient_id, 
                        models.IngredientLot.is_depleted == False)\
                .order_by(models.IngredientLot.purchase_date).first()
            
            if not oldest_lot:
                print("DEBUG: Out of stock, breaking loop")
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
            
            # FOR TESTING: This prevents the 'hang'
            db.flush()
        
    # 2. Record the transaction with the margins 
    # Note: retail_price is multiplied by quantity_sold for accurate totals
    total_revenue = product.retail_price * quantity_sold
    margin_fifo = total_revenue - total_cost_fifo
    margin_newest = total_revenue - total_cost_newest
    
    new_log = models.TransactionLog(
        tenant_id=tenant_id,
        product_id=product_id,
        sale_price=total_revenue, # Total for the whole batch
        margin_fifo=margin_fifo,
        margin_newest=margin_newest
    )
    
    db.add(new_log)
    db.commit()
    return new_log