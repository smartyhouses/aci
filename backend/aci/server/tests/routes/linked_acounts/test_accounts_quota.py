from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from aci.common.db.sql_models import Plan
from aci.common.schemas.app_configurations import AppConfigurationPublic
from aci.common.schemas.linked_accounts import LinkedAccountNoAuthCreate
from aci.common.schemas.plans import PlanFeatures
from aci.server import config


def test_linked_accounts_quota(
    test_client: TestClient,
    dummy_api_key_1: str,
    dummy_app_configuration_no_auth_mock_app_connector_project_1: AppConfigurationPublic,
    db_session: Session,
) -> None:
    plan = Plan(
        name="free",
        stripe_product_id="prod_FREE_placeholder",
        stripe_monthly_price_id="price_FREE_monthly_placeholder",
        stripe_yearly_price_id="price_FREE_yearly_placeholder",
        features=PlanFeatures(
            linked_accounts=2,
            api_calls_monthly=1000,
            agent_credentials=5,
            developer_seats=1,
            custom_oauth=False,
            log_retention_days=7,
        ).model_dump(),
        is_public=True,
    )
    db_session.add(plan)
    db_session.commit()

    # Create first linked account (should succeed)
    body1 = LinkedAccountNoAuthCreate(
        app_name=dummy_app_configuration_no_auth_mock_app_connector_project_1.app_name,
        linked_account_owner_id="test_linked_accounts_quota_1",
    )
    response = test_client.post(
        f"{config.ROUTER_PREFIX_LINKED_ACCOUNTS}/no-auth",
        json=body1.model_dump(mode="json", exclude_none=True),
        headers={"x-api-key": dummy_api_key_1},
    )
    assert response.status_code == status.HTTP_200_OK

    # Create second linked account (should also succeed)
    body2 = LinkedAccountNoAuthCreate(
        app_name=dummy_app_configuration_no_auth_mock_app_connector_project_1.app_name,
        linked_account_owner_id="test_linked_accounts_quota_2",
    )
    response = test_client.post(
        f"{config.ROUTER_PREFIX_LINKED_ACCOUNTS}/no-auth",
        json=body2.model_dump(mode="json", exclude_none=True),
        headers={"x-api-key": dummy_api_key_1},
    )
    assert response.status_code == status.HTTP_200_OK

    # Try to create third linked account (should fail due to quota)
    body3 = LinkedAccountNoAuthCreate(
        app_name=dummy_app_configuration_no_auth_mock_app_connector_project_1.app_name,
        linked_account_owner_id="test_linked_accounts_quota_3",
    )
    response = test_client.post(
        f"{config.ROUTER_PREFIX_LINKED_ACCOUNTS}/no-auth",
        json=body3.model_dump(mode="json", exclude_none=True),
        headers={"x-api-key": dummy_api_key_1},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Max linked accounts reached" in str(response.json()["error"])
