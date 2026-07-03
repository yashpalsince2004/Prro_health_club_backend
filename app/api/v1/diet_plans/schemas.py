"""
Pydantic schemas for Diet Plan nutrition management.
"""

from datetime import date
from uuid import UUID
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict
from app.models.diet import MealType


class DietItemCreate(BaseModel):
    """Schema to add a diet item detail to a plan."""
    meal_type: MealType = Field(..., description="Meal type category (breakfast, lunch, etc.)")
    food_name: str = Field(..., description="Food item name")
    quantity: str = Field(..., description="Portion quantity (e.g. 100, 2, 1.5)")
    unit: str = Field(..., description="Portion unit (e.g. grams, ml, pieces)")
    calories: Optional[int] = Field(None, ge=0, description="Optional calorie count")
    notes: Optional[str] = Field(None, description="Eating recommendations")
    order_index: int = Field(0, description="Sorting sequence order in the meal")


class DietItemUpdate(BaseModel):
    """Schema to update a diet item in a plan."""
    meal_type: Optional[MealType] = Field(None)
    food_name: Optional[str] = Field(None)
    quantity: Optional[str] = Field(None)
    unit: Optional[str] = Field(None)
    calories: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = Field(None)
    order_index: Optional[int] = Field(None)


class DietItemResponse(BaseModel):
    """Schema exposing nutritional diet item details."""
    id: UUID
    meal_type: MealType
    meal_type_label: str
    food_name: str
    quantity: str
    unit: str
    calories: Optional[int] = None
    notes: Optional[str] = None
    order_index: int

    model_config = ConfigDict(from_attributes=True)


class DietPlanCreate(BaseModel):
    """Schema to prescribe a nutrition plan to a member."""
    member_id: UUID = Field(..., description="Member target ID")
    title: str = Field(..., description="Diet plan title")
    description: Optional[str] = Field(None, description="General nutritional targets")
    daily_calories: Optional[int] = Field(None, ge=0, description="Overall daily calories goal")
    protein_grams: Optional[int] = Field(None, ge=0, description="Daily protein intake grams")
    carbs_grams: Optional[int] = Field(None, ge=0, description="Daily carbohydrate intake grams")
    fat_grams: Optional[int] = Field(None, ge=0, description="Daily fat intake grams")
    start_date: date = Field(default_factory=date.today, description="Plan start date")
    end_date: Optional[date] = Field(None, description="Optional plan expiration date")
    items: List[DietItemCreate] = Field(default_factory=list, description="Array of diet items")


class DietPlanUpdate(BaseModel):
    """Schema to update diet plan metadata."""
    title: Optional[str] = Field(None)
    description: Optional[str] = Field(None)
    daily_calories: Optional[int] = Field(None, ge=0)
    protein_grams: Optional[int] = Field(None, ge=0)
    carbs_grams: Optional[int] = Field(None, ge=0)
    fat_grams: Optional[int] = Field(None, ge=0)
    start_date: Optional[date] = Field(None)
    end_date: Optional[date] = Field(None)
    is_active: Optional[bool] = Field(None)


class DietPlanResponse(BaseModel):
    """Schema exposing complete diet plan details with items grouped by meal."""
    id: UUID
    member_id: UUID
    member_name: str
    trainer_id: Optional[UUID] = None
    trainer_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    daily_calories: Optional[int] = None
    protein_grams: Optional[int] = None
    carbs_grams: Optional[int] = None
    fat_grams: Optional[int] = None
    start_date: date
    end_date: Optional[date] = None
    is_active: bool
    items_by_meal: Dict[str, List[DietItemResponse]]
    total_tracked_calories: int

    model_config = ConfigDict(from_attributes=True)
