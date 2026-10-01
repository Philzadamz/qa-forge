import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ResetPasswordForm } from "./reset-password-form";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

describe("ResetPasswordForm", () => {
  it("shows an invalid-link message when there's no token", () => {
    render(<ResetPasswordForm token={null} />);
    expect(screen.getByText("Invalid link")).toBeInTheDocument();
  });

  it("validates that the passwords match before submitting", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(<ResetPasswordForm token="abc123" />);

    await userEvent.type(screen.getByLabelText("New password"), "new-password-1");
    await userEvent.type(screen.getByLabelText("Confirm new password"), "different-password");
    await userEvent.click(screen.getByRole("button", { name: "Save new password" }));

    expect(await screen.findByText("Passwords don't match")).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("submits the token and redirects to sign in on success", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    render(<ResetPasswordForm token="abc123" />);

    await userEvent.type(screen.getByLabelText("New password"), "new-password-1");
    await userEvent.type(screen.getByLabelText("Confirm new password"), "new-password-1");
    await userEvent.click(screen.getByRole("button", { name: "Save new password" }));

    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/login"));
  });

  it("shows a friendly message on an expired or invalid token", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ title: "Bad Request", status: 400 }), {
        status: 400,
        headers: { "content-type": "application/problem+json" },
      }),
    );
    render(<ResetPasswordForm token="abc123" />);

    await userEvent.type(screen.getByLabelText("New password"), "new-password-1");
    await userEvent.type(screen.getByLabelText("Confirm new password"), "new-password-1");
    await userEvent.click(screen.getByRole("button", { name: "Save new password" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This reset link is invalid or has expired.",
    );
  });
});
