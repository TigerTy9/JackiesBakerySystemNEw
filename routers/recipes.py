from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import database, models, schemas

router = APIRouter(prefix="/products", tags=["Products & Recipes"])

@router.post("/", response_model=schemas.ProductCreate)
def create_product_with_recipe(product_in: schemas.ProductCreate, tenant_id: int, db: Session = Depends(database.get_db)):
    # 1. Create the Product master record
    new_product = models.Product(
        tenant_id=tenant_id,
        name=product_in.name,
        retail_price=product_in.retail_price
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    # 2. Add each Ingredient to the Recipe
    for item in product_in.recipe:
        recipe_entry = models.RecipeItem(
            product_id=new_product.id,
            ingredient_id=item.ingredient_id,
            quantity_required=item.quantity_required
        )
        db.add(recipe_entry)
    
    db.commit()
    return new_product