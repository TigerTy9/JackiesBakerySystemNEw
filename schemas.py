from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import List, Optional

class IngredientBase(BaseModel):
    name: str
    base_unit: str # e.g., "g", "ml", "unit"

class RecipeItemCreate(BaseModel):
    ingredient_id: int
    quantity_required: float
    is_non_food: bool = False

class ProductCreate(BaseModel):
    name: str
    retail_price: float
    recipe: List[RecipeItemCreate]

class SaleCreate(BaseModel):
    item_id: int
    quantity: int
    price: float
    class Config:
        from_attributes = True

class SaleResponse(BaseModel):
    id: int
    tenant_id: int
    total_amount: float
    created_at: datetime

    class Config:
        from_attributes = True  # This allows Pydantic to read data from SQLAlchemy models

class TenantBase(BaseModel):
    name: str  # We'll map this to business_name
    email: EmailStr

class TenantCreate(TenantBase):
    pass

class TenantResponse(BaseModel):
    id: int
    business_name: str
    email: str
    domain: str
    created_at: datetime

    class Config:
        from_attributes = True # Allows Pydantic to read SQLAlchemy models

class IngredientCreate(BaseModel):
    name: str
    base_unit: str
    is_non_food: bool = False

class IngredientResponse(BaseModel):
    id: int
    tenant_id: int
    name: str
    base_unit: str
    is_non_food: bool

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    tenant_id: int
    username: str
    password: str
    role: str # "owner", "baker", "cashier" 

class UserResponse(BaseModel):
    id: int
    tenant_id: int
    username: str
    role: str

    class Config:
        from_attributes = True