from datetime import date, datetime, timezone, timedelta
from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from app.database.session import get_db
from app.core.exceptions import NotFoundException, ConflictException
from app.core.constants import UserRole, SubscriptionStatus
from app.core.security import get_password_hash
from app.dependencies.auth import get_current_user_context, RoleChecker, UserContext
from app.utils.response import success_response, paginated_response
from app.models.lead import Lead, LeadStatus, LeadSource
from app.models.user import User
from app.models.profile import Profile
from app.models.member import Member
from app.models.membership import Membership
from app.models.plan import MembershipPlan
from app.api.v1.leads.schemas import (
    LeadCreate,
    LeadUpdate,
    ConvertLeadRequest,
    LeadResponse
)
from app.api.v1.members.schemas import MemberResponse, ProfileResponse, ActiveMembershipSummary
from app.api.v1.members.endpoints import _map_member_to_response

router = APIRouter()

def _map_lead_to_response(lead: Lead) -> LeadResponse:
    return LeadResponse(
        id=lead.id,
        full_name=lead.full_name,
        phone=lead.phone,
        email=lead.email,
        age=lead.age,
        gender=lead.gender,
        interest=lead.interest,
        source=lead.source.value if hasattr(lead.source, "value") else lead.source,
        status=lead.status.value if hasattr(lead.status, "value") else lead.status,
        notes=lead.notes,
        follow_up_date=lead.follow_up_date,
        trial_start=lead.trial_start,
        trial_end=lead.trial_end,
        assigned_to=lead.assigned_to,
        converted_member_id=lead.converted_member_id,
        created_at=lead.created_at
    )

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_lead(
    payload: LeadCreate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Create a new lead (Admin + Receptionist)."""
    new_lead = Lead(
        full_name=payload.full_name,
        phone=payload.phone,
        email=payload.email,
        age=payload.age,
        gender=payload.gender,
        interest=payload.interest,
        source=payload.source,
        status=LeadStatus.NEW,
        notes=payload.notes,
        follow_up_date=payload.follow_up_date,
        assigned_to=payload.assigned_to
    )
    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)

    return success_response(
        message="Lead created successfully",
        data=_map_lead_to_response(new_lead),
        status_code=status.HTTP_201_CREATED
    )

@router.get("/")
def list_leads(
    status: Optional[LeadStatus] = Query(None),
    source: Optional[LeadSource] = Query(None),
    follow_up_today: bool = Query(False),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """List prospective members / leads (Admin + Receptionist)."""
    query = db.query(Lead).filter(Lead.is_deleted == False)

    if status:
        query = query.filter(Lead.status == status)
    if source:
        query = query.filter(Lead.source == source)
    if follow_up_today:
        query = query.filter(Lead.follow_up_date == date.today())

    total = query.count()
    offset = (page - 1) * per_page
    leads = query.order_by(Lead.created_at.desc()).offset(offset).limit(per_page).all()

    mapped_leads = [_map_lead_to_response(l) for l in leads]

    return paginated_response(
        message="Leads retrieved successfully",
        data=mapped_leads,
        page=page,
        limit=per_page,
        total=total
    )

@router.get("/{lead_id}")
def get_lead(
    lead_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Retrieve details for a single lead."""
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.is_deleted == False).first()
    if not lead:
        raise NotFoundException(message="Lead not found")

    return success_response(
        message="Lead retrieved successfully",
        data=_map_lead_to_response(lead)
    )

@router.patch("/{lead_id}")
def update_lead(
    lead_id: UUID,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Update lead status, assignment, or scheduling (Admin + Receptionist)."""
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.is_deleted == False).first()
    if not lead:
        raise NotFoundException(message="Lead not found")

    if payload.full_name is not None:
        lead.full_name = payload.full_name
    if payload.phone is not None:
        lead.phone = payload.phone
    if payload.email is not None:
        lead.email = payload.email
    if payload.age is not None:
        lead.age = payload.age
    if payload.gender is not None:
        lead.gender = payload.gender
    if payload.interest is not None:
        lead.interest = payload.interest
    if payload.source is not None:
        lead.source = payload.source
    if payload.status is not None:
        lead.status = payload.status
    if payload.notes is not None:
        lead.notes = f"{lead.notes or ''}\nUpdated: {payload.notes}".strip()
    if payload.follow_up_date is not None:
        lead.follow_up_date = payload.follow_up_date
    if payload.trial_start is not None:
        lead.trial_start = payload.trial_start
    if payload.trial_end is not None:
        lead.trial_end = payload.trial_end
    if payload.assigned_to is not None:
        lead.assigned_to = payload.assigned_to

    db.commit()
    db.refresh(lead)

    return success_response(
        message="Lead updated successfully",
        data=_map_lead_to_response(lead)
    )

@router.post("/{lead_id}/convert")
def convert_lead_to_member(
    lead_id: UUID,
    payload: ConvertLeadRequest,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN, UserRole.RECEPTIONIST]))
):
    """Convert a lead to a registered member, subscribing them to a plan (Admin + Receptionist)."""
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.is_deleted == False).first()
    if not lead:
        raise NotFoundException(message="Lead not found")

    if lead.status == LeadStatus.CONVERTED:
        raise ConflictException(message="Lead is already converted to a member")

    # Check email uniqueness if email exists
    email_to_use = lead.email or f"{lead.phone}@prrohealthclub.com"
    existing_user = db.query(User).filter(User.email == email_to_use.lower()).first()
    if existing_user:
        raise ConflictException(message=f"Email or Phone identifier '{email_to_use}' is already registered as a user")

    try:
        # 1. Create User
        new_user = User(
            email=email_to_use.lower(),
            hashed_password=get_password_hash(payload.password),
            role=UserRole.MEMBER,
            is_active=True
        )
        db.add(new_user)
        db.flush()

        # 2. Create Profile
        new_profile = Profile(
            user_id=new_user.id,
            full_name=lead.full_name,
            phone=lead.phone,
            gender=lead.gender,
            address=None,
            date_of_birth=None
        )
        db.add(new_profile)
        db.flush()

        # 3. Create Member
        new_member = Member(
            profile_id=new_profile.id,
            joining_date=payload.joining_date,
            notes=f"Converted from lead. Original notes: {lead.notes or ''}"
        )
        db.add(new_member)
        db.flush()

        # 4. Create Membership if plan_id provided
        if payload.plan_id:
            plan = db.query(MembershipPlan).filter(MembershipPlan.id == payload.plan_id, MembershipPlan.is_active == True).first()
            if not plan:
                raise NotFoundException(message="Membership plan not found or inactive")
            
            end_date = payload.joining_date + timedelta(days=plan.duration_days)
            new_membership = Membership(
                member_id=new_member.id,
                plan_id=plan.id,
                start_date=payload.joining_date,
                end_date=end_date,
                status=SubscriptionStatus.ACTIVE,
                discount_percent=0.0,
                notes="Created during lead conversion"
            )
            db.add(new_membership)

        # 5. Link Lead
        lead.status = LeadStatus.CONVERTED
        lead.converted_member_id = new_member.id
        lead.notes = f"{lead.notes or ''}\nConverted to member {new_member.id} on {date.today()}".strip()

        db.commit()

        # Load relations for mapping
        member_with_relations = db.query(Member).options(
            joinedload(Member.profile).joinedload(Profile.user),
            joinedload(Member.memberships).joinedload(Membership.plan)
        ).filter(Member.id == new_member.id).first()

        return success_response(
            message="Lead converted successfully to member",
            data=_map_member_to_response(member_with_relations).model_dump()
        )
    except Exception as e:
        db.rollback()
        raise e

@router.delete("/{lead_id}")
def delete_lead(
    lead_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserContext = Depends(RoleChecker(allowed_roles=[UserRole.ADMIN]))
):
    """Soft delete lead (Admin only)."""
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.is_deleted == False).first()
    if not lead:
        raise NotFoundException(message="Lead not found")

    lead.is_deleted = True
    db.commit()

    return success_response(message="Lead soft deleted successfully")
