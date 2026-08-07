"use client";

import { LogOut } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/providers/auth-provider";
import { useUsage } from "@/hooks/use-data";
import { displayName, formatDate } from "@/lib/utils";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const { data: usage } = useUsage();

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title="Settings" subtitle="Manage your account and plan." />

      <Card className="p-6">
        <CardTitle>Account</CardTitle>
        <CardContent className="mt-5 space-y-5">
          <div className="space-y-2">
            <Label htmlFor="account-name">Name</Label>
            <Input id="account-name" value={displayName(user?.name, user?.email)} readOnly />
          </div>
          <div className="space-y-2">
            <Label htmlFor="account-email">Email</Label>
            <Input id="account-email" value={user?.email ?? ""} readOnly />
          </div>
          {/* These look like inputs because they are; editing them isn't
              supported yet, so say so rather than silently swallowing keystrokes. */}
          <p className="text-[13px] text-text-muted">
            Account details can&apos;t be changed yet.
          </p>
          <div className="flex items-center gap-2">
            <span className="text-[14px] text-text-secondary">Plan:</span>
            <Badge variant="wine">{user?.subscription_tier ?? "free"}</Badge>
          </div>
        </CardContent>
      </Card>

      <Card className="p-6">
        <CardTitle>Usage</CardTitle>
        <CardContent className="mt-5 space-y-2 text-[15px] text-text-secondary">
          {usage ? (
            <>
              <p>
                Resume matches:{" "}
                <span className="font-medium text-text-primary">
                  {usage.monthly_match_count} / {usage.monthly_match_limit}
                </span>
              </p>
              <p>
                Mock interviews:{" "}
                <span className="font-medium text-text-primary">
                  {usage.monthly_interview_count} / {usage.monthly_interview_limit}
                </span>
              </p>
              {usage.usage_reset_at && <p>Resets on {formatDate(usage.usage_reset_at)}</p>}
            </>
          ) : (
            <div className="space-y-2.5" aria-busy="true" aria-label="Loading usage">
              <Skeleton className="h-5 w-52" />
              <Skeleton className="h-5 w-48" />
              <Skeleton className="h-5 w-40" />
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="p-6">
        <CardTitle>Session</CardTitle>
        <CardContent className="mt-4">
          <Button variant="danger" onClick={logout}>
            <LogOut size={18} /> Log out
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
