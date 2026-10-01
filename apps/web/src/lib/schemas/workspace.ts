import { z } from "zod";

export const projectSchema = z.object({
  name: z.string().trim().min(1, "Enter a name"),
  app_code: z.string().trim().min(1, "Enter an app code"),
  id_prefix: z.string().trim().min(1, "Enter a test case ID prefix"),
  user_group_dept: z.string().trim().optional(),
  solution_provider: z.string().trim().optional(),
  default_test_url: z.string().trim().optional(),
});
export type ProjectInput = z.infer<typeof projectSchema>;

export const suiteSetupSchema = z.object({
  name: z.string().trim().min(1, "Enter a suite name"),
  type_id: z.string().trim().min(1, "Select a test case type"),
  user_group_dept: z.string().trim().optional(),
  solution_provider: z.string().trim().optional(),
  developers: z.string().trim().optional(),
  test_done_by: z.string().trim().optional(),
  test_reviewed_by: z.string().trim().optional(),
  start_date: z.string().trim().optional(),
  end_date: z.string().trim().optional(),
  test_description: z.string().trim().optional(),
  endpoint_url: z.string().trim().optional(),
});
export type SuiteSetupInput = z.infer<typeof suiteSetupSchema>;

export const pasteStorySchema = z.object({
  title: z.string().trim().min(1, "Enter a title"),
  text: z.string().trim().min(1, "Paste the story text"),
});
export type PasteStoryInput = z.infer<typeof pasteStorySchema>;
