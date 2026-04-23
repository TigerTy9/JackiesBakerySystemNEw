from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import database, models, schemas, utils
from auth import get_current_user
from typing import List
from auth import get_tenant_db
from sqlalchemy import func
from datetime import datetime

# This is what main.py is looking for
router = APIRouter(
    prefix="/inventory",
    tags=["inventory"]
)

@router.get("/")
def get_inventory():
    return {"message": "Inventory system active"}

@router.post("/receive-lot")
def receive_inventory(
    ingredient_id: int, 
    qty: float, 
    unit: str, 
    cost: float, 
    current_user: models.User = Depends(get_current_user), # Secure identity
    db: Session = Depends(get_tenant_db) # Secure RLS database
):
    # RLS ensures this only finds the ingredient if it belongs to the bakery
    ingredient = db.query(models.Ingredient).get(ingredient_id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    if unit == ingredient.base_unit:
        multiplier = 1.0
    else:
        # Use the secure tenant_id
        multiplier = utils.get_conversion_multiplier(db, current_user.tenant_id, unit, ingredient.base_unit)
        
    if multiplier is None:
        raise HTTPException(
            status_code=400, 
            detail=f"No conversion found for {unit} to {ingredient.base_unit}"
        )

    base_qty = qty * multiplier
    
    new_lot = models.IngredientLot(
        ingredient_id=ingredient_id,
        cost_total=cost,
        quantity_purchased=base_qty,
        quantity_remaining=base_qty
    )
    db.add(new_lot)
    db.commit()
    return {"message": f"Received {base_qty} {ingredient.base_unit} of inventory."}

@router.post("/log-waste")
def log_waste(
    ingredient_id: int, 
    qty: float, 
    reason: str, 
    current_user: models.User = Depends(get_current_user), # Secure identity
    db: Session = Depends(get_tenant_db) # Secure RLS database
):
    # RLS protects this query automatically
    oldest_lot = db.query(models.IngredientLot).filter(
        models.IngredientLot.ingredient_id == ingredient_id,
        models.IngredientLot.is_depleted == False
    ).order_by(models.IngredientLot.purchase_date).first()
    
    if not oldest_lot or oldest_lot.quantity_remaining < qty:
        raise HTTPException(status_code=400, detail="Not enough inventory to waste.")

    oldest_lot.quantity_remaining -= qty
    if oldest_lot.quantity_remaining <= 0:
        oldest_lot.is_depleted = True
        
    new_waste = models.WasteLog(
        tenant_id=current_user.tenant_id, # Safely applied from the token
        ingredient_id=ingredient_id, 
        lot_id=oldest_lot.id, 
        quantity_wasted=qty, 
        reason=reason
    )
    db.add(new_waste)
    db.commit()
    return {"message": "Waste logged successfully."}

@router.post("/add-ingredient", response_model=schemas.IngredientResponse)
def add_ingredient(
    ingredient: schemas.IngredientCreate, 
    current_user: models.User = Depends(get_current_user), # Secure identity
    db: Session = Depends(get_tenant_db) # Secure RLS database
):
    # 2. Check for existing ingredients (case-insensitive) to prevent duplicates
    # No manual tenant_id filter needed here thanks to RLS!
    existing_ingredient = db.query(models.Ingredient).filter(
        func.lower(models.Ingredient.name) == func.lower(ingredient.name)
    ).first()
    
    if existing_ingredient:
        raise HTTPException(
            status_code=400, 
            detail=f"An ingredient named '{ingredient.name}' already exists in your inventory."
        )

    # 3. Create the record using the secure tenant_id
    new_ingredient = models.Ingredient(
        tenant_id=current_user.tenant_id, # Overrides whatever the user typed
        name=ingredient.name,
        base_unit=ingredient.base_unit,
        is_non_food=ingredient.is_non_food
    )
    
    db.add(new_ingredient)
    db.commit()
    db.refresh(new_ingredient)
    return new_ingredient

@router.put("/edit-ingredient/{ingredient_id}")
def edit_ingredient(
    ingredient_id: int, 
    updated_data: schemas.IngredientCreate, 
    db: Session = Depends(get_tenant_db)
):
    # Only allow edits if the ingredient belongs to the user's bakery
    db_ingredient = db.query(models.Ingredient).filter(
        models.Ingredient.id == ingredient_id,
    ).first()
    
    if not db_ingredient:
        raise HTTPException(status_code=404, detail="Not authorized or not found")
    
    db_ingredient.name = updated_data.name
    db_ingredient.base_unit = updated_data.base_unit
    db.commit()
    return db_ingredient

@router.delete("/remove-ingredient/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_ingredient(
    ingredient_id: int, 
    db: Session = Depends(get_tenant_db),
):
    # 1. Search for the ingredient restricted to the User's Tenant ID
    db_ingredient = db.query(models.Ingredient).filter(
        models.Ingredient.id == ingredient_id,
    ).first()
    
    # 2. If not found or belongs to another bakery, 404 is returned to mask data existence
    if not db_ingredient:
        raise HTTPException(
            status_code=404, 
            detail="Ingredient not found in your bakery inventory"
        )

    # 3. Integrity Check: Ensure no active Lots or Recipes depend on this
    has_lots = db.query(models.IngredientLot).filter(
        models.IngredientLot.ingredient_id == ingredient_id
    ).first()
    
    has_recipes = db.query(models.RecipeItem).filter(
        models.RecipeItem.ingredient_id == ingredient_id
    ).first()

    if has_lots or has_recipes:
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete ingredient with active purchase lots or recipes. Archive it instead."
        )

    # 4. Final Deletion
    db.delete(db_ingredient)
    db.commit()
    return None

@router.get("/list", response_model=List[schemas.IngredientResponse])
def list_ingredients(
    db: Session = Depends(get_tenant_db) # <-- Use the new dependency here
):
    # LOOK MA, NO FILTERS! 
    # Because of RLS, Postgres will ONLY return ingredients for this specific tenant.
    # If a developer forgets the filter, the data is still perfectly safe.
    ingredients = db.query(models.Ingredient).all()
    
    return ingredients

@router.get("/stock-levels", response_model=List[schemas.IngredientStockResponse])
def get_stock_levels(db: Session = Depends(get_tenant_db)):
    """
    Calculates the total quantity on hand for every ingredient 
    by summing up all non-depleted lots.
    """
    # We join Ingredients and IngredientLots to get names and quantities together
    stock = db.query(
        models.Ingredient.id.label("ingredient_id"),
        models.Ingredient.name,
        func.sum(models.IngredientLot.quantity_remaining).label("total_quantity"),
        models.Ingredient.base_unit
    ).join(models.IngredientLot).filter(
        models.IngredientLot.is_depleted == False
    ).group_by(models.Ingredient.id).all()
    
    return stock