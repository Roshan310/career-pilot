"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { register } from "@/lib/api/auth";
import { useAuth } from "@/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/client";

export default function RegisterPage() {
  const router = useRouter();
  const { setUser } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  // Field-level problems belong next to the field. Toasts stay for server errors.
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  // Don't scold someone mid-typing — validate live only after a failed submit.
  const [submitted, setSubmitted] = useState(false);

  function validate(): { email?: string; password?: string } {
    const next: { email?: string; password?: string } = {};
    if (!email.trim()) next.email = "Enter your email address.";
    else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim()))
      next.email = "That doesn't look like a valid email address.";
    if (!password) next.password = "Choose a password.";
    else if (password.length < 8) next.password = "Use at least 8 characters.";
    return next;
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitted(true);
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    setLoading(true);
    try {
      const user = await register(email, password, name);
      setUser(user);
      toast.success("Account created. Welcome to CareerPilot!");
      router.replace("/dashboard");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="text-h3 text-text-primary">Create your account</h1>
      <p className="mt-1.5 text-[15px] text-text-secondary">Start matching resumes in minutes.</p>

      <form onSubmit={onSubmit} className="mt-8 space-y-5">
        <div className="space-y-2">
          <Label htmlFor="name">Full name</Label>
          <Input
            id="name"
            type="text"
            autoComplete="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Roshan Aryal"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              if (submitted) setErrors(validate());
            }}
            error={errors.email}
            placeholder="you@example.com"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              if (submitted) setErrors(validate());
            }}
            error={errors.password}
            placeholder="At least 8 characters"
            aria-describedby="password-hint"
          />
          <p id="password-hint" className="text-[13px] text-text-muted">
            At least 8 characters.
          </p>
        </div>
        <Button type="submit" size="lg" className="w-full" disabled={loading}>
          {loading && <Loader2 size={18} className="animate-spin" />}
          Create account
        </Button>
      </form>

      <p className="mt-6 text-center text-[15px] text-text-secondary">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-wine-fg hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}
