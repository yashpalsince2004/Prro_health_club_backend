from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.auth.endpoints import router as auth_router
from app.api.v1.members.endpoints import router as members_router
from app.api.v1.trainers.endpoints import router as trainers_router
from app.api.v1.memberships.endpoints import router as memberships_router
from app.api.v1.payments.endpoints import router as payments_router
from app.api.v1.attendance.endpoints import router as attendance_router
from app.api.v1.attendance.biometric_push import router as biometric_router
from app.api.v1.plans.endpoints import router as plans_router
from app.api.v1.workout_plans.endpoints import router as workout_plans_router
from app.api.v1.diet_plans.endpoints import router as diet_plans_router
from app.api.v1.analytics.endpoints import router as analytics_router
from app.api.v1.notifications.endpoints import router as notifications_router
from app.api.v1.admin.cron import router as admin_cron_router

from app.api.v1.receptionists.endpoints import router as receptionists_router
from app.api.v1.leads.endpoints import router as leads_router
from app.api.v1.exercise_library.endpoints import router as exercise_library_router
from app.api.v1.admin.reports import router as reports_router
from app.api.v1.admin.settings import router as settings_router
from app.api.v1.pt_plans.endpoints import router as pt_plans_router
from app.api.v1.locker_plans.endpoints import router as locker_plans_router
from app.api.v1.additional_services.endpoints import router as additional_services_router

api_router = APIRouter()

# Register all v1 sub-routers
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(members_router, prefix="/members", tags=["Members"])
api_router.include_router(trainers_router, prefix="/trainers", tags=["Trainers"])
api_router.include_router(receptionists_router, prefix="/receptionists", tags=["Receptionists"])
api_router.include_router(leads_router, prefix="/leads", tags=["Leads"])
api_router.include_router(exercise_library_router, prefix="/exercise-library", tags=["Exercise Library"])
api_router.include_router(reports_router, prefix="/admin/reports", tags=["Reports"])
api_router.include_router(settings_router, prefix="/admin/settings", tags=["Settings"])
api_router.include_router(memberships_router, prefix="/memberships", tags=["Memberships"])
api_router.include_router(payments_router, prefix="/payments", tags=["Payments"])
api_router.include_router(attendance_router, prefix="/attendance", tags=["Attendance"])
api_router.include_router(biometric_router, prefix="/attendance", tags=["Biometric"])
api_router.include_router(plans_router, prefix="/plans", tags=["Membership Plans"])
api_router.include_router(workout_plans_router, prefix="/workout-plans", tags=["Workout Plans"])
api_router.include_router(diet_plans_router, prefix="/diet-plans", tags=["Diet Plans"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(admin_cron_router, prefix="/admin", tags=["Admin Cron"])
api_router.include_router(pt_plans_router, prefix="/pt-plans", tags=["PT Packages"])
api_router.include_router(locker_plans_router, prefix="/locker-plans", tags=["Locker Plans"])
api_router.include_router(additional_services_router, prefix="/additional-services", tags=["Additional Services"])
