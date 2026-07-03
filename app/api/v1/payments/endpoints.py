"""
FastAPI route handlers for Payment invoice transactions.
"""

import math
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
from decimal import Decimal
from loguru import logger
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from app.database.session import get_db
from app.core.exceptions import NotFoundException, AuthorizationException, ConflictException
from app.core.constants import UserRole
from app.dependencies.auth import get_current_user_context, RoleChecker, UserContext
from app.utils.response import success_response, paginated_response
from app.models.member import Member
from app.models.membership import Membership
from app.models.payment import Payment, PaymentStatusEnum, PaymentMethodEnum
from app.models.profile import Profile
from app.models.user import User
from app.api.v1.payments.schemas import (
    PaymentCreate,
    PaymentResponse,
    PaymentSummary,
    PaymentListResponse
)

router = APIRouter()


def _map_payment_to_response(p: Payment) -> PaymentResponse:
    """Helper to map a Payment db model to PaymentResponse schema."""
    member_profile = p.member.profile if p.member else None
    member_name = member_profile.full_name if member_profile else "Unknown Member"
    
    collector_profile = p.collector.profile if p.collector else None
    collected_by_name = collector_profile.full_name if collector_profile else None

    return PaymentResponse(
        id=p.id,
        membership_id=p.membership_id,
        member_id=p.member_id,
        member_name=member_name,
        amount_paid=Decimal(str(p.amount_paid)),
        currency=p.currency,
        payment_method=p.payment_method,
        payment_status=p.payment_status,
        transaction_reference=p.transaction_reference,
        payment_date=p.payment_date,
        notes=p.notes,
        collected_by_name=collected_by_name
    )


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=None)
def record_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Record an invoice payment (receptionist/admin only)."""
    logger.info(f"[record_payment] user={current_user.user_id} member={payload.member_id} amount={payload.amount_paid}")

    # Validate that membership exists
    membership = db.query(Membership).filter(Membership.id == payload.membership_id, Membership.is_deleted == False).first()
    if not membership:
        raise NotFoundException(message="Membership subscription not found")

    # Validate that member exists
    member = db.query(Member).filter(Member.id == payload.member_id, Member.is_deleted == False).first()
    if not member:
        raise NotFoundException(message="Member not found")

    # Prevent mismatched recording: Ensure membership is linked to the requested member
    if membership.member_id != payload.member_id:
        raise ConflictException(message="Membership subscription does not belong to the specified member")

    try:
        new_payment = Payment(
            membership_id=payload.membership_id,
            member_id=payload.member_id,
            amount_paid=float(payload.amount_paid),
            payment_method=payload.payment_method,
            payment_status=PaymentStatusEnum.COMPLETED,
            transaction_reference=payload.transaction_reference,
            payment_date=payload.payment_date or datetime.now(timezone.utc),
            notes=payload.notes,
            collected_by=current_user.user_id
        )
        db.add(new_payment)
        db.commit()

        # Fire notification side-effect
        try:
            from app.api.v1.notifications.service import notify_payment_received
            member_user_id = db.query(Profile.user_id).filter(Profile.id == member.profile_id).scalar()
            if member_user_id:
                notify_payment_received(db, member_user_id=member_user_id, payment_id=new_payment.id, amount=Decimal(str(new_payment.amount_paid)))
        except Exception as notify_err:
            logger.error(f"Failed to trigger payment notification (non-critical): {str(notify_err)}")

        # Reload for mapping
        p_with_relations = db.query(Payment).options(
            joinedload(Payment.member).joinedload(Member.profile),
            joinedload(Payment.collector).joinedload(User.profile)
        ).filter(Payment.id == new_payment.id).first()

        res_data = _map_payment_to_response(p_with_relations)
        return success_response(message="Payment recorded successfully", data=res_data.model_dump(), status_code=201)

    except Exception as e:
        db.rollback()
        logger.error(f"[record_payment] error recording transaction: {str(e)}")
        raise e


@router.get("/summary", response_model=None)
def get_revenue_summary(
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Retrieve consolidated revenue summary statistics for dashboard charts."""
    logger.info(f"[get_revenue_summary] user={current_user.user_id}")

    query = db.query(Payment)
    if from_date:
        query = query.filter(Payment.payment_date >= from_date)
    if to_date:
        query = query.filter(Payment.payment_date <= to_date)

    payments = query.all()

    total_payments = len(payments)
    total_amount = Decimal(str(sum(p.amount_paid for p in payments)))

    # Breakdown by method
    by_method = {}
    for method in PaymentMethodEnum:
        by_method[method.value] = Decimal("0.00")
    for p in payments:
        by_method[p.payment_method.value] += Decimal(str(p.amount_paid))

    # Breakdown by status
    by_status = {}
    for status_val in PaymentStatusEnum:
        by_status[status_val.value] = 0
    for p in payments:
        by_status[p.payment_status.value] += 1

    summary = PaymentSummary(
        total_payments=total_payments,
        total_amount=total_amount,
        by_method=by_method,
        by_status=by_status,
        period=f"From {from_date or 'beginning'} to {to_date or 'now'}"
    )
    return success_response(message="Revenue summary retrieved", data=summary.model_dump())


@router.get("/", response_model=None)
def list_payments(
    member_id: Optional[UUID] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    method: Optional[PaymentMethodEnum] = Query(None),
    status: Optional[PaymentStatusEnum] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """List and filter payment invoices with pagination."""
    logger.info(f"[list_payments] user={current_user.user_id} page={page} per_page={per_page}")

    query = db.query(Payment)

    if member_id:
        query = query.filter(Payment.member_id == member_id)
    if from_date:
        query = query.filter(Payment.payment_date >= from_date)
    if to_date:
        query = query.filter(Payment.payment_date <= to_date)
    if method:
        query = query.filter(Payment.payment_method == method)
    if status:
        query = query.filter(Payment.payment_status == status)

    total = query.count()
    payments = query.options(
        joinedload(Payment.member).joinedload(Member.profile),
        joinedload(Payment.collector).joinedload(User.profile)
    ).order_by(Payment.payment_date.desc()).offset((page - 1) * per_page).limit(per_page).all()

    mapped_list = [_map_payment_to_response(p).model_dump() for p in payments]
    return paginated_response(
        message="Payments retrieved",
        data=mapped_list,
        page=page,
        limit=per_page,
        total=total
    )


@router.get("/member/{member_id}", response_model=None)
def get_member_payments(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Retrieve billing/payment history for a specific member."""
    logger.info(f"[get_member_payments] user={current_user.user_id} target_member={member_id}")

    member = db.query(Member).options(joinedload(Member.profile)).filter(
        Member.id == member_id,
        Member.is_deleted == False
    ).first()

    if not member:
        raise NotFoundException(message="Member not found")

    # Ownership check: Member can only view their own payment history
    if current_user.role == UserRole.MEMBER:
        if member.profile.user_id != current_user.user_id:
            raise AuthorizationException(message="You are not authorized to view this billing history")

    payments = db.query(Payment).options(
        joinedload(Payment.member).joinedload(Member.profile),
        joinedload(Payment.collector).joinedload(User.profile)
    ).filter(Payment.member_id == member_id).order_by(Payment.payment_date.desc()).all()

    mapped_list = [_map_payment_to_response(p).model_dump() for p in payments]
    return success_response(message="Member payments history retrieved", data=mapped_list)


@router.get("/{payment_id}", response_model=None)
def get_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(get_current_user_context)
):
    """Retrieve details for a single payment invoice."""
    logger.info(f"[get_payment] user={current_user.user_id} target={payment_id}")

    payment = db.query(Payment).options(
        joinedload(Payment.member).joinedload(Member.profile),
        joinedload(Payment.collector).joinedload(User.profile)
    ).filter(Payment.id == payment_id).first()

    if not payment:
        raise NotFoundException(message="Payment transaction not found")

    # Ownership check: Member can only view their own payment transaction
    if current_user.role == UserRole.MEMBER:
        if payment.member.profile.user_id != current_user.user_id:
            raise AuthorizationException(message="You are not authorized to view this transaction")

    res_data = _map_payment_to_response(payment)
    return success_response(message="Payment transaction retrieved", data=res_data.model_dump())


@router.patch("/{payment_id}/status", response_model=None)
def update_payment_status(
    payment_id: UUID,
    payment_status: PaymentStatusEnum = Query(...),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Alter payment status, such as marking refunds or failures (Admin only)."""
    logger.info(f"[update_payment_status] user={current_user.user_id} target={payment_id} status={payment_status}")

    payment = db.query(Payment).options(
        joinedload(Payment.member).joinedload(Member.profile),
        joinedload(Payment.collector).joinedload(User.profile)
    ).filter(Payment.id == payment_id).first()

    if not payment:
        raise NotFoundException(message="Payment transaction not found")

    try:
        payment.payment_status = payment_status
        db.commit()
        res_data = _map_payment_to_response(payment)
        return success_response(message="Payment status updated successfully", data=res_data.model_dump())

    except Exception as e:
        db.rollback()
        logger.error(f"[update_payment_status] error modifying status: {str(e)}")
        raise e
