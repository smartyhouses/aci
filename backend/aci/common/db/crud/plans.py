from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from aci.common.db.custom_sql_types import PlanFeatures
from aci.common.db.sql_models import Plan
from aci.common.enums import PlanName
from aci.common.schemas.plans import PlanUpdate


def get_by_name(db: Session, name: PlanName) -> Plan | None:
    """
    Retrieves a Plan from the database by its name.
    
    Args:
        name: The unique name of the plan to retrieve.
    
    Returns:
        The matching Plan instance if found, otherwise None.
    """
    stmt = select(Plan).where(Plan.name == name)
    return db.execute(stmt).scalar_one_or_none()


def get_by_id(db: Session, id: UUID) -> Plan | None:
    """
    Retrieves a Plan by its unique identifier.
    
    Args:
    	id: The UUID of the plan to retrieve.
    
    Returns:
    	The matching Plan instance if found, otherwise None.
    """
    stmt = select(Plan).where(Plan.id == id)
    return db.execute(stmt).scalar_one_or_none()


def get_by_stripe_price_id(db: Session, stripe_price_id: str) -> Plan | None:
    """
    Retrieves a plan with a matching Stripe monthly or yearly price ID.
    
    Args:
        stripe_price_id: The Stripe price ID to search for.
    
    Returns:
        The matching Plan instance if found, otherwise None.
    """
    stmt = select(Plan).where(
        (Plan.stripe_monthly_price_id == stripe_price_id)
        | (Plan.stripe_yearly_price_id == stripe_price_id)
    )
    return db.execute(stmt).scalar_one_or_none()


def create(
    db: Session,
    name: PlanName,
    stripe_product_id: str,
    stripe_monthly_price_id: str,
    stripe_yearly_price_id: str,
    features: PlanFeatures,
    is_public: bool,
) -> Plan:
    """
    Creates and persists a new Plan record with the specified attributes.
    
    Args:
        name: The unique name of the plan.
        stripe_product_id: Stripe product identifier for the plan.
        stripe_monthly_price_id: Stripe price ID for the monthly billing option.
        stripe_yearly_price_id: Stripe price ID for the yearly billing option.
        features: Features associated with the plan.
        is_public: Whether the plan is publicly visible.
    
    Returns:
        The newly created Plan instance reflecting the current database state.
    """
    plan = Plan(
        name=name,
        stripe_product_id=stripe_product_id,
        stripe_monthly_price_id=stripe_monthly_price_id,
        stripe_yearly_price_id=stripe_yearly_price_id,
        features=features,
        is_public=is_public,
    )
    db.add(plan)
    db.flush()
    db.refresh(plan)
    return plan


def update_plan(db: Session, plan: Plan, plan_update: PlanUpdate) -> Plan:
    """
    Updates a Plan instance with fields provided in a PlanUpdate model.
    
    Only fields explicitly set in the PlanUpdate model are applied to the Plan object. The updated Plan is flushed and refreshed in the database session before being returned.
    
    Args:
        plan: The Plan ORM object to update.
        plan_update: The PlanUpdate Pydantic model with fields to modify.
    
    Returns:
        The updated Plan ORM object.
    """
    update_data = plan_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(plan, field, value)

    db.flush()
    db.refresh(plan)
    return plan
