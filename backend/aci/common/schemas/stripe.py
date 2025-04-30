from pydantic import BaseModel

from aci.common.enums import PlanName, StripeSubscriptionInterval


class StripeCheckoutSessionCreate(BaseModel):
    plan_name: PlanName
    interval: StripeSubscriptionInterval
