import { describe, expect, it } from "vitest";

import { featureOn, type FeatureFlag } from "./features";

const flags: FeatureFlag[] = [
  { key: "test_lab_android", label: "Android", description: "", enabled: false },
  { key: "bug_tracking", label: "Bugs", description: "", enabled: true },
];

describe("featureOn", () => {
  it("reports a flag as off when the server says so", () => {
    expect(featureOn(flags, "test_lab_android")).toBe(false);
  });

  it("treats features as on while the list is loading", () => {
    expect(featureOn(undefined, "test_lab_android")).toBe(true);
  });

  it("treats an unknown key as on rather than hiding unrelated UI", () => {
    expect(featureOn(flags, "something_else")).toBe(true);
  });
});
