from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.models.api_key import ApiKey


def create_api_key(db: Session, name: str, user_id: str) -> ApiKey:
    key = ApiKey.generate_key()
    api_key = ApiKey(
        name=name,
        key=key,
        key_prefix=key[:12],
        user_id=user_id,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key


def get_api_keys_by_user(db: Session, user_id: str, skip: int = 0, limit: int = 10) -> list[ApiKey]:
    return db.query(ApiKey).filter(ApiKey.user_id == user_id).order_by(ApiKey.created_at.desc()).offset(skip).limit(limit).all()


def get_api_key_by_id(db: Session, key_id: str, user_id: str) -> ApiKey | None:
    return db.query(ApiKey).filter(
        ApiKey.id == key_id, ApiKey.user_id == user_id
    ).first()


def update_api_key(db: Session, api_key: ApiKey, name: str) -> ApiKey:
    api_key.name = name
    db.commit()
    db.refresh(api_key)
    return api_key


def get_api_key_by_key(db: Session, key: str) -> ApiKey | None:
    api_key = db.query(ApiKey).filter(ApiKey.key == key, ApiKey.is_active == True).first()
    if api_key:
        # Update last used timestamp
        api_key.last_used_at = datetime.now(timezone.utc)
        db.commit()
    return api_key


def revoke_api_key(db: Session, api_key: ApiKey) -> ApiKey:
    api_key.is_active = False
    db.commit()
    db.refresh(api_key)
    return api_key


def delete_api_key(db: Session, api_key: ApiKey) -> None:
    db.delete(api_key)
    db.commit()


def count_api_keys_by_user(db: Session, user_id: str) -> int:
    return db.query(ApiKey).filter(ApiKey.user_id == user_id).count()
