from sqlalchemy.orm import Session
from . import models, schemas

def create_photo(db: Session, photo: schemas.PhotoCreate):
    db_photo = models.Photo(filename=photo.filename, url=f"/uploads/{photo.filename}")
    db.add(db_photo)
    db.commit()
    db.refresh(db_photo)
    return db_photo

def get_photos(db: Session, skip: int = 0, limit: int = 10):
    return db.query(models.Photo).offset(skip).limit(limit).all()

from sqlalchemy.orm import Session
