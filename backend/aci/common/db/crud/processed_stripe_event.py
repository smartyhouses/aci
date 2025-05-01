from sqlalchemy import select
from sqlalchemy.orm import Session

from aci.common.db.sql_models import ProcessedStripeEvent
from aci.common.logging_setup import get_logger

logger = get_logger(__name__)


def record_processed_event(db_session: Session, event_id: str) -> ProcessedStripeEvent:
    """
    Creates and persists a new ProcessedStripeEvent record for the given Stripe event ID.
    
    Args:
        event_id: The Stripe event ID to record as processed.
    
    Returns:
        The newly created ProcessedStripeEvent instance.
    """
    processed_event = ProcessedStripeEvent(event_id=event_id)
    db_session.add(processed_event)
    db_session.flush()
    db_session.refresh(processed_event)
    return processed_event


def is_event_processed(db_session: Session, event_id: str) -> bool:
    """
    Determines whether a Stripe event with the given ID has already been processed.
    
    Args:
        event_id: The Stripe event ID to check.
    
    Returns:
        True if a processed event with the specified ID exists, otherwise False.
    """
    statement = select(ProcessedStripeEvent).filter_by(event_id=event_id)
    result = db_session.execute(statement).scalar_one_or_none()
    return result is not None
