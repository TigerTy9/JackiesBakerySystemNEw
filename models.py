from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import enum
from sqlalchemy import Enum as SQLEnum

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(Integer, primary_key=True, index=True)
    business_name = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True) # Added to match your request
    domain = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    users = relationship("User", back_populates="tenant")
    ingredients = relationship("Ingredient", back_populates="tenant")
    products = relationship("Product", back_populates="tenant")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String) # Replaces passwords.txt
    role = Column(String) # "owner", "baker", "cashier"
    
    tenant = relationship("Tenant", back_populates="users")

class WasteLog(Base):
    """Tracks spoilage and dropped items to prevent inventory drift.""" 
    __tablename__ = "waste_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"))
    lot_id = Column(Integer, ForeignKey("ingredient_lots.id"))
    quantity_wasted = Column(Float) # In base_unit
    reason = Column(String) # "Expired", "Dropped", "Spilled" 
    timestamp = Column(DateTime, default=datetime.utcnow)

class Ingredient(Base):
    """The master record for raw materials."""
    __tablename__ = "ingredients"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    name = Column(String) 
    base_unit = Column(String) # Always standard: "grams", "milliliters", or "units"
    is_non_food = Column(Boolean, default=False)

    tenant = relationship("Tenant", back_populates="ingredients")
    lots = relationship("IngredientLot", back_populates="ingredient")

class IngredientLot(Base):
    """Tracks individual purchases for accurate FIFO margin calculation."""
    __tablename__ = "ingredient_lots"
    
    id = Column(Integer, primary_key=True, index=True)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"))
    purchase_date = Column(DateTime, default=datetime.utcnow)
    
    # Financial and Inventory Tracking
    cost_total = Column(Float) # Total price paid for this lot
    quantity_purchased = Column(Float) # Converted to base_unit
    quantity_remaining = Column(Float) # Deducted automatically upon baking
    
    is_depleted = Column(Boolean, default=False)
    
    ingredient = relationship("Ingredient", back_populates="lots")

class Product(Base):
    """The finished baked good ready for sale."""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    name = Column(String)
    retail_price = Column(Float)
    
    lead_time_days = Column(Integer, default=0) 
    
    tenant = relationship("Tenant", back_populates="products")
    recipe_items = relationship("RecipeItem", back_populates="product")

class RecipeItem(Base):
    """The Bill of Materials connecting Products to Ingredients."""
    __tablename__ = "recipe_items"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"))
    quantity_required = Column(Float) # Amount of base_unit needed
    
    product = relationship("Product", back_populates="recipe_items")
    ingredient = relationship("Ingredient")

class TransactionLog(Base):
    """Immutable ledger of all sales and calculated margins."""
    __tablename__ = "transaction_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    customer_name = Column(String, nullable=True) # NEW FIELD
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    sale_price = Column(Float)
    margin_fifo = Column(Float)
    margin_newest = Column(Float)
    
class UnitConversion(Base):
    __tablename__ = "unit_conversions"
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    from_unit = Column(String) # e.g., "50lb Bag"
    to_unit = Column(String)   # e.g., "grams"
    multiplier = Column(Float)  # e.g., 22679.6

class OrderStatus(str, enum.Enum):
    PENDING_QUOTE = "Quote Pending"
    DEPOSIT_PAID = "Deposit Paid"
    BAKING_SCHEDULED = "Baking Scheduled"
    READY = "Ready for Pickup"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"

class CustomOrderItem(Base):
    """Links multiple products to a single custom order."""
    __tablename__ = "custom_order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    custom_order_id = Column(Integer, ForeignKey("custom_orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    
    quantity = Column(Integer, default=1)
    
    # Custom orders often have negotiated prices that differ from retail
    price_override = Column(Float, nullable=True) 

    custom_order = relationship("CustomOrder", back_populates="items")
    product = relationship("Product")

class CustomOrder(Base):
    """Pipeline for complex, non-standard baked goods like wedding cakes."""
    __tablename__ = "custom_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    
    customer_name = Column(String)
    customer_email = Column(String, nullable=True)
    description = Column(String) # e.g., "3-Tier Vanilla Cake with Floral Piping"
    items = relationship("CustomOrderItem", back_populates="custom_order")

    # Financials
    total_price = Column(Float, nullable=True) # Starts null until quote is given
    deposit_amount = Column(Float, default=0.0)
    
    # Workflow State
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING_QUOTE)
    
    delivery_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant")

class FinishedGoodsLot(Base):
    """Tracks daily batches of baked items ready for sale."""
    __tablename__ = "finished_goods_lots"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    
    quantity_produced = Column(Integer)
    quantity_remaining = Column(Integer) # Deducted when sold
    
    # We lock in the calculated ingredient cost at the exact moment of baking
    cost_per_unit_fifo = Column(Float) 
    cost_per_unit_newest = Column(Float)
    
    production_date = Column(DateTime, default=datetime.utcnow)
    is_depleted = Column(Boolean, default=False)
    
    tenant = relationship("Tenant")
    product = relationship("Product")

class FinishedGoodsWasteLog(Base):
    """Tracks unsold or damaged baked items (e.g., end-of-day bread waste)."""
    __tablename__ = "finished_goods_waste_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    lot_id = Column(Integer, ForeignKey("finished_goods_lots.id"))
    
    quantity_wasted = Column(Integer)
    reason = Column(String) # e.g., "Expired", "Dropped", "Donated" 
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Link back to the specific production run to retrieve costs 
    finished_goods_lot = relationship("FinishedGoodsLot")

class OverheadExpense(Base):
    """Fixed monthly costs like rent, hosting, and utilities."""
    __tablename__ = "overhead_expenses"
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    name = Column(String) # e.g., "Kitchen Rent", "BakeryOS Subscription"
    monthly_amount = Column(Float)
    category = Column(String) # "Fixed", "Utility", "Subscription"

class LaborLog(Base):
    """Tracks labor time spent on specific production batches."""
    __tablename__ = "labor_logs"
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    lot_id = Column(Integer, ForeignKey("finished_goods_lots.id"))
    
    hours_spent = Column(Float)
    hourly_rate = Column(Float) # The wage of the baker for this specific batch
    total_labor_cost = Column(Float) # Calculated as hours * rate

class ProductParLevel(Base):
    """Target daily stock levels for standard retail items."""
    __tablename__ = "product_par_levels"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    product_id = Column(Integer, ForeignKey("products.id"), unique=True)
    
    target_quantity = Column(Integer, default=0) # Amount needed at start of day
    
    tenant = relationship("Tenant")
    product = relationship("Product")

class PlannedBatch(Base):
    """Allows bakers to manually schedule one-off production runs for specific dates."""
    __tablename__ = "planned_batches"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    
    planned_quantity = Column(Integer)
    scheduled_date = Column(DateTime) # The day this needs to show up on the Prep List
    is_completed = Column(Boolean, default=False)
    
    tenant = relationship("Tenant")
    product = relationship("Product")