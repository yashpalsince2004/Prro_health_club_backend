"""
Pydantic schemas for Workout Plan management.
"""

from datetime import date
from uuid import UUID
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict


class ExerciseCreate(BaseModel):
    """Schema to add an exercise detail to a plan."""
    day_of_week: int = Field(..., ge=1, le=7, description="ISO day index (1 = Monday, 7 = Sunday)")
    exercise_name: str = Field(..., description="Name of the exercise")
    sets: Optional[int] = Field(None, ge=1, description="Sets count")
    reps: Optional[int] = Field(None, ge=1, description="Reps count per set")
    duration_minutes: Optional[int] = Field(None, ge=1, description="Duration in minutes (for cardio)")
    rest_seconds: Optional[int] = Field(None, ge=0, description="Rest period in seconds between sets")
    notes: Optional[str] = Field(None, description="Coaching recommendations")
    order_index: int = Field(0, description="Sorting order of this exercise in the day's routine")


class ExerciseUpdate(BaseModel):
    """Schema to update an exercise in a plan."""
    day_of_week: Optional[int] = Field(None, ge=1, le=7)
    exercise_name: Optional[str] = Field(None)
    sets: Optional[int] = Field(None, ge=1)
    reps: Optional[int] = Field(None, ge=1)
    duration_minutes: Optional[int] = Field(None, ge=1)
    rest_seconds: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = Field(None)
    order_index: Optional[int] = Field(None)


class ExerciseResponse(BaseModel):
    """Schema exposing workout exercise details."""
    id: UUID
    day_of_week: int
    day_name: str
    exercise_name: str
    sets: Optional[int] = None
    reps: Optional[int] = None
    duration_minutes: Optional[int] = None
    rest_seconds: Optional[int] = None
    notes: Optional[str] = None
    order_index: int

    model_config = ConfigDict(from_attributes=True)


class WorkoutPlanCreate(BaseModel):
    """Schema to create a member's training prescription program."""
    member_id: UUID = Field(..., description="Member target ID")
    title: str = Field(..., description="Workout plan title (e.g. Hypertrophy Split)")
    description: Optional[str] = Field(None, description="Core target of the plan")
    start_date: date = Field(default_factory=date.today, description="Plan start date")
    end_date: Optional[date] = Field(None, description="Optional plan end date")
    exercises: List[ExerciseCreate] = Field(default_factory=list, description="Array of exercises to add")


class WorkoutPlanUpdate(BaseModel):
    """Schema to update workout plan metadata."""
    title: Optional[str] = Field(None)
    description: Optional[str] = Field(None)
    start_date: Optional[date] = Field(None)
    end_date: Optional[date] = Field(None)
    is_active: Optional[bool] = Field(None)


class WorkoutPlanResponse(BaseModel):
    """Schema exposing complete workout plan details with daily nested groups."""
    id: UUID
    member_id: UUID
    member_name: str
    trainer_id: Optional[UUID] = None
    trainer_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    is_active: bool
    exercises_by_day: Dict[str, List[ExerciseResponse]]
    total_exercises: int

    model_config = ConfigDict(from_attributes=True)
