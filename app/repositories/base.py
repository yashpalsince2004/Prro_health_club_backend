import uuid
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Base repository pattern implementation using SQLAlchemy 2.0 semantics.
    All resource-specific repositories must inherit from this class.
    """
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        """Fetch a single record by primary key, honoring soft delete status if present."""
        query = select(self.model).where(self.model.id == id)
        if hasattr(self.model, "is_deleted"):
            # Clean filtering of soft-deleted records
            query = query.where(self.model.is_deleted == False)
        return db.scalars(query).first()

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """Fetch multiple records with offset and limit pagination."""
        query = select(self.model)
        if hasattr(self.model, "is_deleted"):
            query = query.where(self.model.is_deleted == False)
        query = query.offset(skip).limit(limit)
        return list(db.scalars(query).all())

    def create(self, db: Session, *, obj_in: Dict[str, Any]) -> ModelType:
        """Persist a new database entity."""
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: Union[Dict[str, Any], Any]
    ) -> ModelType:
        """Update an existing database entity using dict or Pydantic schema input."""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
            
        for field in update_data:
            if hasattr(db_obj, field):
                setattr(db_obj, field, update_data[field])
                
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: Any) -> bool:
        """Permanently delete a database record (hard delete)."""
        query = select(self.model).where(self.model.id == id)
        db_obj = db.scalars(query).first()
        if not db_obj:
            return False
        db.delete(db_obj)
        db.commit()
        return True

    def soft_delete(self, db: Session, *, id: Any, updater_id: Optional[uuid.UUID] = None) -> bool:
        """Flag a record as deleted without dropping it from the database."""
        query = select(self.model).where(self.model.id == id)
        db_obj = db.scalars(query).first()
        if not db_obj:
            return False
            
        if hasattr(db_obj, "soft_delete"):
            db_obj.soft_delete(updater_id=updater_id)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return True
            
        # Fallback to hard delete if soft delete mixin is not implemented
        db.delete(db_obj)
        db.commit()
        return True
