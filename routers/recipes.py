from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import database, models, schemas
from auth import get_current_user, get_tenant_db

router = APIRouter(prefix="/products", tags=["Products & Recipes"])

@router.post("/", response_model=schemas.ProductResponse)
def create_product_with_recipe(
    product_in: schemas.ProductCreate, 
    current_user: models.User = Depends(get_current_user), # Secure identity
    db: Session = Depends(get_tenant_db)                   # Secure RLS database
):
    # 1. Create the Product master record securely
    new_product = models.Product(
        tenant_id=current_user.tenant_id, # Safely applied from the token
        name=product_in.name,
        retail_price=product_in.retail_price
    )
    db.add(new_product)
    db.flush() # Get the new product ID before committing

    # 2. Add each Ingredient to the Recipe
    for item in product_in.recipe:
        recipe_entry = models.RecipeItem(
            product_id=new_product.id,
            ingredient_id=item.ingredient_id,
            quantity_required=item.quantity_required
        )
        db.add(recipe_entry)
    
    db.commit()
    db.refresh(new_product)
    return new_product


@router.get("/list", response_model=List[schemas.ProductResponse])
def list_products_and_recipes(db: Session = Depends(get_tenant_db)):
    """
    Returns all baked goods and their associated recipes.
    RLS ensures only this bakery's products are returned.
    """
    products = db.query(models.Product).all()
    return products