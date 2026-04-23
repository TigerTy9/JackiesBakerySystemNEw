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

class PlannedBatchCreate(BaseModel):
    product_id: int
    planned_quantity: int
    scheduled_date: datetime
    
class ProductCreate(BaseModel):
    name: str
    retail_price: float
    lead_time_days: int = 0
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
    sale_price: float  # Changed from total_amount to sale_price
    margin_fifo: float # Add these to see your margins in the response
    margin_newest: float
    timestamp: datetime # Changed from created_at to timestamp to match models.py

    class Config:
        from_attributes = True
        
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

class CustomOrderItemCreate(BaseModel):
    product_id: int
    quantity: int
    price_override: Optional[float] = None

class CustomOrderItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    price_override: Optional[float]
    
    class Config:
        from_attributes = True

class CustomOrderCreate(BaseModel):
    customer_name: str
    customer_email: Optional[str] = None
    description: str
    delivery_date: datetime
    items: List[CustomOrderItemCreate] = []

class CustomOrderUpdate(BaseModel):
    total_price: Optional[float] = None
    deposit_amount: Optional[float] = None
    status: Optional[str] = None

class CustomOrderResponse(BaseModel):
    id: int
    tenant_id: int
    customer_name: str
    customer_email: Optional[str]
    description: str
    total_price: Optional[float]
    deposit_amount: float
    status: str
    delivery_date: datetime
    created_at: datetime
    items: List[CustomOrderItemResponse] = []

    class Config:
        from_attributes = True

class RecipeItemResponse(BaseModel):
    id: int
    ingredient_id: int
    quantity_required: float

    class Config:
        from_attributes = True

class ProductResponse(BaseModel):
    id: int
    tenant_id: int
    name: str
    retail_price: float
    lead_time_days: int  # Added field
    recipe_items: List[RecipeItemResponse] = [] 

    class Config:
        from_attributes = True
        
class IngredientStockResponse(BaseModel):
    ingredient_id: int
    name: str
    total_quantity: float
    base_unit: str

    class Config:
        from_attributes = True

class ProductionRunCreate(BaseModel):
    product_id: int
    quantity_produced: int

class FinishedGoodsResponse(BaseModel):
    id: int
    product_id: int
    quantity_produced: int
    quantity_remaining: int
    production_date: datetime
    is_depleted: bool

    class Config:
        from_attributes = True

class OverheadBase(BaseModel):
    name: str
    monthly_amount: float
    category: str # e.g., "Fixed", "Subscription", "Utility"

class OverheadCreate(OverheadBase):
    pass

class OverheadResponse(OverheadBase):
    id: int
    tenant_id: int

    class Config:
        from_attributes = True

class PlannedBatchCreate(BaseModel):
    product_id: int
    planned_quantity: int
    scheduled_date: datetime

class PrepListItem(BaseModel):
    product_id: int
    product_name: str
    current_inventory: int
    retail_par_needed: int
    custom_order_needed: int
    planned_batch_needed: int 
    total_to_bake: int

    class Config:
        from_attributes = True