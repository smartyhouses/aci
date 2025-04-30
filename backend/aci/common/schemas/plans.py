from pydantic import BaseModel, Field

from aci.common.db.custom_sql_types import PlanFeatures


class PlanUpdate(BaseModel):
    stripe_product_id: str | None = Field(None)
    stripe_monthly_price_id: str | None = Field(None)
    stripe_yearly_price_id: str | None = Field(None)
    features: PlanFeatures | None = Field(None)
    is_public: bool | None = Field(None)
    model_config = {"extra": "forbid"}
