from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.entities import User
from app.schemas.auth import LoginRequest, OkResponse, RegisterRequest, TokenResponse, UserSummary
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    return auth_service.register_user(db, payload)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.login_user(db, payload)


@router.post("/logout", response_model=OkResponse)
def logout():
    return OkResponse(ok=True)


@router.get("/me", response_model=UserSummary)
def me(user: User = Depends(get_current_user)):
    return UserSummary.model_validate(user)
