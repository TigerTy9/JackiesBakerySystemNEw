from sqlalchemy.orm import Session
from sqlalchemy import desc
import models, schemas

def execute_production_run(db: Session, product_id: int, tenant_id: int, quantity_produced: int):
    """
    1. THE BAKE: Deducts raw ingredients and creates a batch of Finished Goods.
    """
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise Exception("Product not found")
    
    total_cost_fifo = 0.0
    total_cost_newest = 0.0
    
    # Deduct raw ingredients based on the recipe [cite: 93, 94]
    for item in product.recipe_items:
        total_qty_needed = item.quantity_required * quantity_produced
        
        # Calculate newest replacement cost [cite: 94, 95]
        newest_lot = db.query(models.IngredientLot)\
            .filter(models.IngredientLot.ingredient_id == item.ingredient_id)\
            .order_by(desc(models.IngredientLot.purchase_date)).first()
         
        if newest_lot:
            cost_per_unit_newest = newest_lot.cost_total / newest_lot.quantity_purchased
            total_cost_newest += (cost_per_unit_newest * total_qty_needed)

        # Deduct from oldest physical inventory (FIFO) [cite: 95, 96, 97]
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
            
    # Create the Finished Goods batch with the locked-in costs per individual pastry
    new_batch = models.FinishedGoodsLot(
        tenant_id=tenant_id,
        product_id=product_id,
        quantity_produced=quantity_produced,
        quantity_remaining=quantity_produced,
        cost_per_unit_fifo=total_cost_fifo / quantity_produced if quantity_produced > 0 else 0,
        cost_per_unit_newest=total_cost_newest / quantity_produced if quantity_produced > 0 else 0
    )
    
    db.add(new_batch)
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

    # Calculate final margins and log the sale [cite: 100, 101]
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