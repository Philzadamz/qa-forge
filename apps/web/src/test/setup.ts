import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// vitest.config.mts doesn't set `test.globals`, so @testing-library/react's
// auto-cleanup (which only registers when `afterEach` is already a global at
// import time) never fires — do it explicitly or DOM leaks across tests.
afterEach(cleanup);
