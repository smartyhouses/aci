export enum PlanName {
  Free = "free",
  Starter = "starter",
  Team = "team",
  Growth = "growth",
  Enterprise = "enterprise",
}

export enum Interval {
  Month = "month",
  Year = "year",
}

export enum SubscriptionStatus {
  Incomplete = "incomplete",
  IncompleteExpired = "incomplete_expired",
  Trialing = "trialing",
  Active = "active",
  PastDue = "past_due",
  Canceled = "canceled",
  Unpaid = "unpaid",
  Paused = "paused",
}

export interface Subscription {
  plan: PlanName;
  status: SubscriptionStatus;
}
