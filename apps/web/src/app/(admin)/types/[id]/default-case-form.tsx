"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { defaultTestCaseSchema, type DefaultTestCaseInput } from "@/lib/schemas/admin";
import type { DefaultTestCase } from "@/lib/types/admin";

export interface DefaultCasePayload {
  feature: string;
  scenario: string;
  steps: string[];
  expected_result: string;
  evidence_group: string;
}

function toPayload(values: DefaultTestCaseInput): DefaultCasePayload {
  return {
    feature: values.feature,
    scenario: values.scenario,
    expected_result: values.expected_result,
    evidence_group: values.evidence_group,
    steps: values.steps
      .split("\n")
      .map((s) => s.replace(/^\s*\d+[.)]\s*/, "").trim())
      .filter(Boolean),
  };
}

export function DefaultCaseForm({
  initial,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  initial?: DefaultTestCase;
  submitLabel: string;
  onSubmit: (payload: DefaultCasePayload) => Promise<unknown> | void;
  onCancel?: () => void;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<DefaultTestCaseInput>({
    resolver: zodResolver(defaultTestCaseSchema),
    defaultValues: initial
      ? {
          feature: initial.feature,
          scenario: initial.scenario,
          steps: initial.steps.map((s, i) => `${i + 1}. ${s}`).join("\n"),
          expected_result: initial.expected_result,
          evidence_group: initial.evidence_group,
        }
      : { evidence_group: "Default Scenarios" },
  });

  return (
    <form
      onSubmit={handleSubmit(async (values) => onSubmit(toPayload(values)))}
      className="grid grid-cols-1 gap-4 md:grid-cols-2"
    >
      <div className="flex flex-col gap-2">
        <Label htmlFor="feature">Feature</Label>
        <Input id="feature" {...register("feature")} aria-invalid={!!errors.feature} />
        {errors.feature && <p className="text-destructive text-sm">{errors.feature.message}</p>}
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="evidence_group">Evidence group</Label>
        <Input id="evidence_group" {...register("evidence_group")} />
      </div>
      <div className="flex flex-col gap-2 md:col-span-2">
        <Label htmlFor="scenario">Scenario</Label>
        <Textarea id="scenario" {...register("scenario")} aria-invalid={!!errors.scenario} />
        {errors.scenario && <p className="text-destructive text-sm">{errors.scenario.message}</p>}
      </div>
      <div className="flex flex-col gap-2 md:col-span-2">
        <Label htmlFor="steps">Steps to execute (one per line)</Label>
        <Textarea id="steps" rows={4} {...register("steps")} aria-invalid={!!errors.steps} />
        {errors.steps && <p className="text-destructive text-sm">{errors.steps.message}</p>}
      </div>
      <div className="flex flex-col gap-2 md:col-span-2">
        <Label htmlFor="expected_result">Expected result</Label>
        <Textarea
          id="expected_result"
          {...register("expected_result")}
          aria-invalid={!!errors.expected_result}
        />
        {errors.expected_result && (
          <p className="text-destructive text-sm">{errors.expected_result.message}</p>
        )}
      </div>
      <div className="flex gap-2 md:col-span-2">
        <Button type="submit" loading={isSubmitting}>
          {isSubmitting ? "Saving…" : submitLabel}
        </Button>
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}
