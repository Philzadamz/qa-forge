import { z } from "zod";

export const testCaseTypeSchema = z.object({
  name: z.string().trim().min(1, "Enter a name"),
  description: z.string().trim().optional(),
  id_prefix_hint: z.string().trim().optional(),
});
export type TestCaseTypeInput = z.infer<typeof testCaseTypeSchema>;

export const defaultTestCaseSchema = z.object({
  feature: z.string().trim().min(1, "Enter a feature"),
  scenario: z.string().trim().min(1, "Enter a scenario"),
  steps: z.string().trim().min(1, "Enter at least one step"),
  expected_result: z.string().trim().min(1, "Enter the expected result"),
  evidence_group: z.string().trim().min(1, "Enter an evidence group"),
});
export type DefaultTestCaseInput = z.infer<typeof defaultTestCaseSchema>;

export const createUserSchema = z.object({
  email: z.string().trim().min(1, "Enter an email").email("Enter a valid email address"),
  full_name: z.string().trim().min(1, "Enter a name"),
  staff_id: z.string().trim().optional(),
  role: z.enum(["admin", "user", "viewer"]),
  password: z.string().min(8, "Use at least 8 characters"),
});
export type CreateUserInput = z.infer<typeof createUserSchema>;
