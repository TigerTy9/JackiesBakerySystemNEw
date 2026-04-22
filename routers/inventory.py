from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import database, models, schemas, utils
from auth import get_current_user
from typing import List

# This is what main.py is looking for
router = APIRouter(
    prefix="/inventory",
    tags=["inventory"]
)

@router.get("/")
def get_inventory():
    return {"message": "Inventory system active"}

@router.post("/receive-lot")
def receive_inventory(ingredient_id: int, qty: float, unit: str, cost: float, tenant_id: int, db: Session = Depends(database.get_db)):
    ingredient = db.query(models.Ingredient).get(ingredient_id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient not found")

    # If the units match exactly, multiplier is 1.0
    if unit == ingredient.base_unit:
        multiplier = 1.0
    else:
        multiplier = utils.get_conversion_multiplier(db, tenant_id, unit, ingredient.base_unit)
        
    # Check if a multiplier was actually found
    if multiplier is None:
        raise HTTPException(
            status_code=400, 
            detail=f"No conversion found for {unit} to {ingredient.base_unit}"
        )

    base_qty = qty * multiplier
    
    # 2. Create the Lot [cite: 39]
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
def log_waste(ingredient_id: int, qty: float, reason: str, tenant_id: int, db: Session = Depends(database.get_db)):
    # Logic to find oldest non-depleted lot and deduct waste
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
        tenant_id=tenant_id, 
        ingredient_id=ingredient_id, 
        lot_id=oldest_lot.id, 
        quantity_wasted=qty, 
        reason=reason
    )
    db.add(new_waste)
    db.commit()
    return {"message": "Waste logged successfully."}

@router.post("/add-ingredient", response_model=schemas.IngredientResponse)
def add_ingredient(ingredient: schemas.IngredientCreate, db: Session = Depends(database.get_db)):
    # Create the master record for a raw material
    new_ingredient = models.Ingredient(
        tenant_id=ingredient.tenant_id,
        name=ingredient.name,
        base_unit=ingredient.base_unit,  # Should be 'grams', 'ml', or 'units'
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
    current_user: models.User = Depends(get_current_user), # New Dependency
    db: Session = Depends(database.get_db)
):
    # Only allow edits if the ingredient belongs to the user's bakery
    db_ingredient = db.query(models.Ingredient).filter(
        models.Ingredient.id == ingredient_id,
        models.Ingredient.tenant_id == current_user.tenant_id
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
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user) # Securely identifies the bakery
):
    # 1. Search for the ingredient restricted to the User's Tenant ID
    db_ingredient = db.query(models.Ingredient).filter(
        models.Ingredient.id == ingredient_id,
        models.Ingredient.tenant_id == current_user.tenant_id
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
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user)
):
    # Retrieve only the ingredients belonging to this specific tenant
    ingredients = db.query(models.Ingredient).filter(
        models.Ingredient.tenant_id == current_user.tenant_id
    ).all()
    return ingredients