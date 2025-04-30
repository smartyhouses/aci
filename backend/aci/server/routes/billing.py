import time
from datetime import datetime
from typing import Annotated
from uuid import UUID

import stripe
from fastapi import APIRouter, Body, Depends, Header, Request, status
from propelauth_fastapi import User
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aci.common.db import crud
from aci.common.db.sql_models import Subscription
from aci.common.enums import (
    OrganizationRole,
    PlanName,
    StripeSubscriptionInterval,
    StripeSubscriptionStatus,
)
from aci.common.exceptions import BillingError, SubscriptionPlanNotFound
from aci.common.logging_setup import get_logger
from aci.common.schemas.stripe import StripeCheckoutSessionCreate
from aci.common.schemas.subscription import (
    StripeSubscriptionDetails,
    SubscriptionPublic,
    SubscriptionUpdate,
)
from aci.server import acl, config
from aci.server import dependencies as deps

router = APIRouter()
logger = get_logger(__name__)

auth = acl.get_propelauth()


@router.get("/get-subscription", response_model=SubscriptionPublic)
async def get_subscription(
    db_session: Annotated[Session, Depends(deps.yield_db_session)],
    org_id: Annotated[UUID, Header(alias="X-ACI-ORG-ID")],
    user: Annotated[User, Depends(auth.require_user)],
) -> SubscriptionPublic:
    acl.require_org_member(user, org_id)

    active_subscription = crud.subscriptions.get_subscription_by_org_id(db_session, org_id)
    if not active_subscription:
        logger.info(
            "no active subscription found, the org is on the free plan",
            extra={"org_id": org_id},
        )
        return SubscriptionPublic(
            plan=PlanName.FREE,
            status=StripeSubscriptionStatus.ACTIVE,
        )

    plan = crud.plans.get_by_id(db_session, active_subscription.plan_id)
    if not plan:
        logger.error(
            "plan not found",
            extra={"plan_id": active_subscription.plan_id},
        )
        raise SubscriptionPlanNotFound(f"plan={active_subscription.plan_id} not found")
    return SubscriptionPublic(
        plan=plan.name,
        status=active_subscription.status,
    )


@router.post("/create-checkout-session")
async def create_checkout_session(
    user: Annotated[User, Depends(auth.require_user)],
    db_session: Annotated[Session, Depends(deps.yield_db_session)],
    org_id: Annotated[UUID, Header(alias="X-ACI-ORG-ID")],
    body: Annotated[StripeCheckoutSessionCreate, Body()],
) -> str:
    acl.require_org_member_with_minimum_role(user, org_id, OrganizationRole.ADMIN)

    plan = crud.plans.get_by_name(db_session, body.plan_name)
    if not plan:
        logger.error(
            "plan not found",
            extra={"plan_name": body.plan_name},
        )
        raise SubscriptionPlanNotFound(f"plan={body.plan_name} not found")

    price_id = (
        plan.stripe_monthly_price_id
        if body.interval == StripeSubscriptionInterval.MONTH
        else plan.stripe_yearly_price_id
    )

    try:
        session = stripe.checkout.Session.create(
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            success_url=f"{config.DEV_PORTAL_URL}/account",
            cancel_url=f"{config.DEV_PORTAL_URL}/pricing",
            mode="subscription",
            client_reference_id=str(org_id),
            ui_mode="hosted",
        )
    except stripe.StripeError as e:
        logger.error(
            "error creating checkout session",
            extra={"error": e},
        )
        raise BillingError() from e

    if not session.url:
        logger.error(
            "checkout session url not found",
            extra={"session": session},
        )
        raise BillingError(
            "checkout session url not found", error_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return session.url


@router.post("/create-customer-portal-session")
async def create_customer_portal_session(
    user: Annotated[User, Depends(auth.require_user)],
    db_session: Annotated[Session, Depends(deps.yield_db_session)],
    org_id: Annotated[UUID, Header(alias="X-ACI-ORG-ID")],
) -> str:
    acl.require_org_member_with_minimum_role(user, org_id, OrganizationRole.ADMIN)

    active_subscription = crud.subscriptions.get_subscription_by_org_id(db_session, org_id)
    if not active_subscription:
        logger.error(
            "subscription not found, the org is on the free plan",
            extra={"org_id": org_id},
        )
        raise BillingError(
            "subscription not found, the org is on the free plan",
            error_code=status.HTTP_404_NOT_FOUND,
        )

    try:
        session = stripe.billing_portal.Session.create(
            customer=active_subscription.stripe_customer_id,
            return_url=f"{config.DEV_PORTAL_URL}/account",
        )
    except stripe.StripeError as e:
        logger.error(
            "error creating customer portal session",
            extra={"error": e},
        )
        raise BillingError() from e

    return session.url


@router.post("/webhook")
async def handle_stripe_webhook(
    request: Request,
    db_session: Annotated[Session, Depends(deps.yield_db_session)],
    stripe_signature: str = Header(None),
) -> None:
    payload = await request.body()
    event = None

    # 1. Verify Signature
    try:
        event = stripe.Webhook.construct_event(  # type: ignore
            payload, stripe_signature, config.STRIPE_WEBHOOK_SIGNING_SECRET
        )
        logger.info(
            "Received valid Stripe event",
            extra={"event_id": event.id, "event_type": event.type},
        )
    except stripe.InvalidRequestError as e:
        logger.error(
            "Webhook error: Invalid payload",
            extra={"error": e},
        )
        raise BillingError(
            error_code=status.HTTP_400_BAD_REQUEST,
        ) from e
    except stripe.SignatureVerificationError as e:
        logger.error(
            "Webhook error: Invalid signature",
            extra={"error": e},
        )
        raise BillingError(
            error_code=status.HTTP_400_BAD_REQUEST,
        ) from e
    except stripe.StripeError as e:
        logger.error(
            "Webhook error: Unexpected error during event construction",
            extra={"error": e},
        )
        raise BillingError() from e

    # 2. Idempotency Check: if event has already been processed, return directly
    # Don't need to worry about race condition or locking here because our event
    # handlers are idempotent. The worst case is just the event is processed twice,
    # but only one of the two inserted into the processed_stripe_event table.
    if crud.processed_stripe_event.is_event_processed(db_session, event.id):
        logger.info(
            "Event already processed. Skipping.",
            extra={"event_id": event.id},
        )
        return

    # 3. Handle the event
    start_time = time.time()
    logger.info(
        "Processing event",
        extra={"event_id": event.id, "event_type": event.type},
    )

    match event.type:
        case "checkout.session.completed":
            await handle_checkout_session_completed(event.data.object, db_session)
        case "customer.subscription.updated":
            await handle_customer_subscription_updated(event.data.object, db_session)
        case "customer.subscription.deleted":
            await handle_customer_subscription_deleted(event.data.object, db_session)
        case _:
            logger.warning(
                "Unhandled event",
                extra={"event_id": event.id, "event_type": event.type},
            )
            return

    # 4. Record Processed Event
    try:
        crud.processed_stripe_event.record_processed_event(db_session, event.id)
        db_session.commit()
    except IntegrityError as e:
        logger.warn(
            "The event has already been processed and inserted into the processed_stripe_event table",
            extra={"event_id": event.id, "error": e},
        )
        return

    processing_time = time.time() - start_time
    logger.info(
        "Successfully processed and recorded event",
        extra={
            "event_id": event.id,
            "event_type": event.type,
            "processing_time": processing_time,
        },
    )


async def handle_checkout_session_completed(session_data: dict, db_session: Session) -> None:
    """
    Handles the checkout.session.completed event.
    1. Retrieve the client_reference_id and subscription details from the session data
    2. Retrieve the subscription details from Stripe
    3. Find the plan corresponding to the subscription price id
    4. Check if a subscription record already exists for this org (idempotency for this specific step)
    5. Create the new Subscription record
    """
    logger.info(f"Handling checkout.session.completed event: {session_data}")
    # TODO: find out how to use the construct_from method
    # session = stripe.checkout.Session.construct_from(session_data, None)

    # 1. Retrieve the client_reference_id and subscription details from the session data
    client_reference_id = session_data.get("client_reference_id")
    stripe_customer_id = session_data.get("customer")
    stripe_subscription_id = session_data.get("subscription")

    if not client_reference_id or not stripe_customer_id or not stripe_subscription_id:
        raise BillingError(
            "Missing critical data in checkout.session.completed event payload.",
            error_code=status.HTTP_400_BAD_REQUEST,
        )

    # 2. Retrieve the subscription details from Stripe
    try:
        stripe_subscription = stripe.Subscription.retrieve(stripe_subscription_id)
        logger.info(f"Retrieved subscription {stripe_subscription_id} for checkout session.")
    except stripe.StripeError as e:
        logger.error(f"Failed to retrieve subscription {stripe_subscription_id}: {e}")
        raise BillingError() from e

    subscription_details = _parse_stripe_subscription_details(stripe_subscription)

    # 3. Find the plan corresponding to the subscription price id
    plan = crud.plans.get_by_stripe_price_id(db_session, subscription_details.stripe_price_id)
    if not plan:
        logger.error(
            f"Could not find internal Plan matching Stripe Price ID: {subscription_details.stripe_price_id}"
        )
        raise ValueError(
            f"Could not find internal Plan matching Stripe Price ID: {subscription_details.stripe_price_id}"
        )

    # 4. Check if a subscription record already exists for this org (idempotency for this specific step)
    existing_sub = crud.subscriptions.get_subscription_by_org_id(db_session, client_reference_id)
    if existing_sub:
        subscription_update = SubscriptionUpdate(
            plan_id=plan.id,
            stripe_customer_id=stripe_customer_id,
            status=StripeSubscriptionStatus(subscription_details.status),
            interval=subscription_details.interval,
            current_period_end=subscription_details.current_period_end,
            cancel_at_period_end=subscription_details.cancel_at_period_end,
        )
        existing_sub = crud.subscriptions.update_subscription_by_stripe_id(
            db_session,
            stripe_subscription_id,
            subscription_update,
        )
        db_session.add(existing_sub)
        db_session.flush()
        db_session.refresh(existing_sub)
    else:
        # 5. Create the new Subscription record
        new_subscription = Subscription(
            org_id=client_reference_id,
            plan_id=plan.id,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            status=StripeSubscriptionStatus(subscription_details.status),
            interval=subscription_details.interval,
            current_period_end=subscription_details.current_period_end,
            cancel_at_period_end=subscription_details.cancel_at_period_end,
        )
        db_session.add(new_subscription)

    db_session.commit()
    logger.info(
        f"Successfully created/updated subscription record for Org ID: {client_reference_id}"
    )


async def handle_customer_subscription_updated(
    subscription_data: dict, db_session: Session
) -> None:
    """
    Handles the customer.subscription.updated event.
    1. Find the existing subscription record by stripe_subscription_id
    2. Update the subscription record with the new details
    """
    logger.info(
        "Handling customer.subscription.updated event",
        extra={"subscription_data": subscription_data},
    )

    subscription_details = _parse_stripe_subscription_details(subscription_data)

    # 1. Find your internal Plan record based on the stripe_price_id
    plan = crud.plans.get_by_stripe_price_id(db_session, subscription_details.stripe_price_id)
    if not plan:
        logger.error(
            "Could not find internal Plan matching Stripe Price ID",
            extra={"stripe_price_id": subscription_details.stripe_price_id},
        )
        raise BillingError(
            f"Could not find internal Plan matching Stripe Price ID: {subscription_details.stripe_price_id}",
            error_code=status.HTTP_400_BAD_REQUEST,
        )

    # 2. Update the subscription record with the new details
    update_data = SubscriptionUpdate(
        status=StripeSubscriptionStatus(subscription_details.status),
        plan_id=plan.id,
        interval=subscription_details.interval,
        current_period_end=subscription_details.current_period_end,
        cancel_at_period_end=subscription_details.cancel_at_period_end,
        stripe_customer_id=subscription_details.stripe_customer_id,
    )

    subscription = crud.subscriptions.update_subscription_by_stripe_id(
        db_session,
        subscription_details.stripe_subscription_id,
        update_data,
    )
    if not subscription:
        logger.error(
            "Could not find existing Subscription record to update",
            extra={"stripe_subscription_id": subscription_details.stripe_subscription_id},
        )
        raise BillingError(
            "Could not find existing Subscription record to update",
            error_code=status.HTTP_400_BAD_REQUEST,
        )

    db_session.commit()

    logger.info(
        "Successfully updated subscription record",
        extra={"stripe_subscription_id": subscription_details.stripe_subscription_id},
    )


async def handle_customer_subscription_deleted(
    subscription_data: dict, db_session: Session
) -> None:
    """
    Handles the customer.subscription.deleted event.
    1. Find the existing subscription record by stripe_subscription_id
    2. Delete the subscription record
    """
    logger.info(
        "Handling customer.subscription.deleted event",
        extra={"subscription_data": subscription_data},
    )
    stripe_subscription_id = subscription_data.get("id")

    if not stripe_subscription_id:
        logger.error(f"Subscription deleted event missing ID. Payload: {subscription_data}")
        raise BillingError(
            "Subscription deleted event missing ID",
            error_code=status.HTTP_400_BAD_REQUEST,
        )

    # 1. Find the existing subscription record by stripe_subscription_id
    subscription = crud.subscriptions.get_subscription_by_stripe_id(
        db_session, stripe_subscription_id
    )

    if subscription:
        # 2. Delete the subscription record
        logger.info(
            "Deleting subscription record",
            extra={
                "stripe_subscription_id": stripe_subscription_id,
                "org_id": subscription.org_id,
                "plan_id": subscription.plan_id,
            },
        )
        crud.subscriptions.delete_subscription_by_stripe_id(db_session, stripe_subscription_id)
        db_session.commit()
    else:
        logger.warning(
            "Subscription record not found",
            extra={"stripe_subscription_id": stripe_subscription_id},
        )
        raise BillingError(
            "Subscription record not found",
            error_code=status.HTTP_404_NOT_FOUND,
        )


def _parse_stripe_subscription_details(
    subscription_data: dict,
) -> StripeSubscriptionDetails:
    """
    Parse the Stripe subscription details from a Stripe subscription dict based on the
    schema: https://docs.stripe.com/api/subscriptions/retrieve?lang=python
    """
    stripe_subscription_id = subscription_data.get("id")
    stripe_customer_id = subscription_data.get("customer")
    status = subscription_data.get("status")
    cancel_at_period_end = subscription_data.get("cancel_at_period_end", False)

    items_data = subscription_data.get("items", {}).get("data", [])
    price = items_data[0].get("price", {})
    current_period_end_ts = items_data[0].get("current_period_end")
    current_period_end_dt = datetime.fromtimestamp(current_period_end_ts)
    interval = price.get("recurring", {}).get("interval")
    stripe_price_id = price.get("id")
    subscription_interval = (
        StripeSubscriptionInterval.MONTH if interval == "month" else StripeSubscriptionInterval.YEAR
    )

    print("stripe_subscription_id", stripe_subscription_id)
    print("stripe_customer_id", stripe_customer_id)
    print("status", status)
    print("cancel_at_period_end", cancel_at_period_end)
    print("current_period_end_dt", current_period_end_dt)
    print("stripe_price_id", stripe_price_id)
    print("subscription_interval", subscription_interval)

    # TODO: add stripe event generation timestamp

    return StripeSubscriptionDetails(
        stripe_subscription_id=stripe_subscription_id,  # type: ignore
        stripe_customer_id=stripe_customer_id,  # type: ignore
        status=StripeSubscriptionStatus(status),  # type: ignore
        current_period_end=current_period_end_dt,
        cancel_at_period_end=cancel_at_period_end,
        stripe_price_id=stripe_price_id,
        interval=subscription_interval,
    )
