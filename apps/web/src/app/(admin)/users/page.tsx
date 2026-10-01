"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { ApiError, apiFetch } from "@/lib/api";
import { createUserSchema, type CreateUserInput } from "@/lib/schemas/admin";
import type { AdminUser, Role } from "@/lib/types/admin";

function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.problem.detail ?? err.message;
  return fallback;
}

export default function UsersPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resettingId, setResettingId] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState("");

  const { data: users, isLoading } = useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => apiFetch<AdminUser[]>("/admin/users"),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreateUserInput>({
    resolver: zodResolver(createUserSchema),
    defaultValues: { role: "user" },
  });

  const createUser = useMutation({
    mutationFn: (values: CreateUserInput) =>
      apiFetch<AdminUser>("/admin/users", { method: "POST", body: JSON.stringify(values) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      reset();
      setShowForm(false);
      setError(null);
    },
    onError: (err: unknown) => setError(describeError(err, "Could not create the user.")),
  });

  const patchUser = useMutation({
    mutationFn: ({ id, ...body }: { id: string; role?: Role; is_active?: boolean }) =>
      apiFetch<AdminUser>(`/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
    onError: (err: unknown) => setError(describeError(err, "Could not update the user.")),
  });

  const resetPassword = useMutation({
    mutationFn: ({ id, password }: { id: string; password: string }) =>
      apiFetch<void>(`/admin/users/${id}/reset-password`, {
        method: "POST",
        body: JSON.stringify({ new_password: password }),
      }),
    onSuccess: () => {
      setResettingId(null);
      setNewPassword("");
    },
    onError: (err: unknown) => setError(describeError(err, "Could not reset the password.")),
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
          <p className="text-muted-foreground text-sm">
            ADM-UP-1: invite, role, deactivate, reset.
          </p>
        </div>
        <Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New user"}</Button>
      </div>

      {error && <p className="text-destructive text-sm">{error}</p>}

      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle>New user</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={handleSubmit((values) => createUser.mutate(values))}
              className="grid grid-cols-1 gap-4 md:grid-cols-2"
            >
              <div className="flex flex-col gap-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  {...register("email")}
                  aria-invalid={!!errors.email}
                />
                {errors.email && <p className="text-destructive text-sm">{errors.email.message}</p>}
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="full_name">Full name</Label>
                <Input
                  id="full_name"
                  {...register("full_name")}
                  aria-invalid={!!errors.full_name}
                />
                {errors.full_name && (
                  <p className="text-destructive text-sm">{errors.full_name.message}</p>
                )}
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="staff_id">Staff ID</Label>
                <Input id="staff_id" {...register("staff_id")} />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="role">Role</Label>
                <Select id="role" {...register("role")}>
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                  <option value="viewer">Viewer</option>
                </Select>
              </div>
              <div className="flex flex-col gap-2 md:col-span-2">
                <Label htmlFor="password">Initial password</Label>
                <Input
                  id="password"
                  type="password"
                  {...register("password")}
                  aria-invalid={!!errors.password}
                />
                {errors.password && (
                  <p className="text-destructive text-sm">{errors.password.message}</p>
                )}
              </div>
              <Button type="submit" disabled={isSubmitting} className="self-start md:col-span-2">
                {isSubmitting ? "Creating…" : "Create user"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {isLoading && <p className="text-muted-foreground text-sm">Loading…</p>}

      <div className="flex flex-col gap-2">
        {users?.map((u) => (
          <Card key={u.id}>
            <CardContent className="flex flex-wrap items-center justify-between gap-4 py-4">
              <div>
                <div className="flex items-center gap-2 font-medium">
                  {u.full_name}
                  {!u.is_active && <Badge variant="destructive">Deactivated</Badge>}
                </div>
                <div className="text-muted-foreground text-sm">
                  {u.email} {u.staff_id ? `· ${u.staff_id}` : ""}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Select
                  value={u.role}
                  onChange={(e) => patchUser.mutate({ id: u.id, role: e.target.value as Role })}
                  className="h-9 w-32"
                >
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                  <option value="viewer">Viewer</option>
                </Select>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => patchUser.mutate({ id: u.id, is_active: !u.is_active })}
                >
                  {u.is_active ? "Deactivate" : "Activate"}
                </Button>
                {resettingId === u.id ? (
                  <div className="flex items-center gap-2">
                    <Input
                      type="password"
                      placeholder="New password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      className="h-9 w-40"
                    />
                    <Button
                      size="sm"
                      disabled={newPassword.length < 8}
                      onClick={() => resetPassword.mutate({ id: u.id, password: newPassword })}
                    >
                      Save
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setResettingId(null)}>
                      Cancel
                    </Button>
                  </div>
                ) : (
                  <Button variant="outline" size="sm" onClick={() => setResettingId(u.id)}>
                    Reset password
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
