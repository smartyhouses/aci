import { Check, X } from "lucide-react";
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from "@/components/ui/table";

type PlanFeature = {
  feature: string;
  free: boolean | string;
  starter: boolean | string;
  team: boolean | string;
  enterprise: boolean | string;
};

const tableData: PlanFeature[] = [
  {
    feature: "Unique End Users",
    free: "10",
    starter: "250",
    team: "1000",
    enterprise: "Custom",
  },
  {
    feature: "API Calls",
    free: "1K/month",
    starter: "100K/month",
    team: "300K/month",
    enterprise: "Custom",
  },
  {
    feature: "Agent Credentials",
    free: "5",
    starter: "2500",
    team: "10000",
    enterprise: "Unlimited",
  },
  {
    feature: "Developer Seats",
    free: "1",
    starter: "5",
    team: "10",
    enterprise: "Custom",
  },
  {
    feature: "Custom OAuth2 Client",
    free: false,
    starter: true,
    team: true,
    enterprise: true,
  },
  {
    feature: "Log Retention",
    free: "3 days",
    starter: "1 week",
    team: "1 month",
    enterprise: "Custom",
  },
  {
    feature: "Support",
    free: "Discord",
    starter: "Discord + Email",
    team: "Discord + Email",
    enterprise: "Dedicated Rep",
  },
];

function renderIcon(value: boolean | string) {
  if (typeof value === "boolean") {
    return value ? (
      <div className="flex items-center justify-center">
        <Check className="w-4 h-4 text-green-500" aria-label="Yes" />
      </div>
    ) : (
      <div className="flex items-center justify-center">
        <X className="w-4 h-4 text-red-500" aria-label="No" />
      </div>
    );
  }
  return value;
}

export default function CompareTable() {
  const planKeys = ["free", "starter", "team", "enterprise"] as const;

  return (
    <div className="mt-16">
      <h2 className="text-3xl font-bold text-center mb-6">Compare Plans</h2>
      <div className="overflow-x-auto">
        <Table className="min-w-[600px] bg-background rounded-lg shadow ring-1 ring-border">
          <TableHeader className="bg-muted">
            <TableRow>
              <TableHead className="px-4 py-3 text-left text-sm font-semibold uppercase">
                Feature
              </TableHead>
              <TableHead className="px-4 py-3 text-center text-sm font-semibold uppercase">
                Free Tier
              </TableHead>
              <TableHead className="px-4 py-3 text-center text-sm font-semibold uppercase">
                Starter
              </TableHead>
              <TableHead className="px-4 py-3 text-center text-sm font-semibold uppercase">
                Team
              </TableHead>
              <TableHead className="px-4 py-3 text-center text-sm font-semibold uppercase">
                Enterprise
              </TableHead>
            </TableRow>
          </TableHeader>

          <TableBody>
            {tableData.map((row, idx) => (
              <TableRow
                key={row.feature}
                className={`border-b last:border-0 ${idx % 2 === 0 ? "bg-muted/10" : ""}`}
              >
                <TableCell className="px-4 py-3 font-medium text-sm">
                  {row.feature}
                </TableCell>
                {planKeys.map((key) => (
                  <TableCell
                    key={key}
                    className="px-4 py-3 text-center text-sm align-middle"
                  >
                    {renderIcon(row[key])}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
