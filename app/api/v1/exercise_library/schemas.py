from uuid import UUID
from typing import Optional, List
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field, ConfigDict
from app.models.exercise_library import MuscleGroup

class ExerciseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    muscle_group: MuscleGroup
    equipment: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    default_sets: Optional[int] = Field(None, ge=1)
    default_reps: Optional[int] = Field(None, ge=1)
    default_rest_seconds: Optional[int] = Field(None, ge=0)

class ExerciseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    muscle_group: Optional[MuscleGroup] = None
    equipment: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    default_sets: Optional[int] = Field(None, ge=1)
    default_reps: Optional[int] = Field(None, ge=1)
    default_rest_seconds: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None

class ExerciseResponse(BaseModel):
    id: UUID
    name: str
    muscle_group: MuscleGroup
    equipment: Optional[str] = None
    description: Optional[str] = None
    default_sets: Optional[int] = None
    default_reps: Optional[int] = None
    default_rest_seconds: Optional[int] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class ExerciseListResponse(BaseModel):
    exercises: List[ExerciseResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
