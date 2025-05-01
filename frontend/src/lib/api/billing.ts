import { Interval, PlanName, Subscription } from "@/lib/types/billing";

/**
 * Retrieves the current subscription details for a specified organization.
 *
 * @param accessToken - Bearer token used for API authentication.
 * @param orgId - Identifier of the organization whose subscription is being fetched.
 * @returns The organization's subscription information.
 *
 * @throws {Error} If the API request fails or returns a non-OK HTTP status.
 */
export async function getSubscription(
  accessToken: string,
  orgId: string,
): Promise<Subscription> {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/v1/billing/get-subscription`,
    {
      method: "GET",
      headers: {
        "X-ACI-ORG-ID": orgId,
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
    },
  );

  if (!response.ok) {
    throw new Error(`Failed to get subscription. Status: ${response.status}`);
  }
  return response.json();
}

/**
 * Initiates a checkout session for a specified billing plan and interval.
 *
 * @param planName - The name of the billing plan to purchase.
 * @param interval - The billing interval for the selected plan.
 * @returns A string representing the checkout session identifier or URL.
 *
 * @throws {Error} If the checkout session could not be created, including the HTTP status code.
 */
export async function createCheckoutSession(
  accessToken: string,
  orgId: string,
  planName: PlanName,
  interval: Interval,
): Promise<string> {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/v1/billing/create-checkout-session`,
    {
      method: "POST",
      headers: {
        "X-ACI-ORG-ID": orgId,
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({
        plan_name: planName,
        interval,
      }),
    },
  );

  if (!response.ok) {
    throw new Error(
      `Failed to create checkout session. Status: ${response.status}`,
    );
  }
  return response.json();
}

/**
 * Creates a customer portal session for the specified organization.
 *
 * Sends a POST request to the billing API to generate a session for managing customer billing information.
 *
 * @param accessToken - Bearer token used for API authorization.
 * @param orgId - Identifier of the organization for which the portal session is created.
 * @returns A string representing the customer portal session identifier or URL.
 *
 * @throws {Error} If the API request fails or returns a non-OK HTTP status.
 */
export async function createCustomerPortalSession(
  accessToken: string,
  orgId: string,
): Promise<string> {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/v1/billing/create-customer-portal-session`,
    {
      method: "POST",
      headers: {
        "X-ACI-ORG-ID": orgId,
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
    },
  );

  if (!response.ok) {
    throw new Error(
      `Failed to create customer portal session. Status: ${response.status}`,
    );
  }
  return response.json();
}
