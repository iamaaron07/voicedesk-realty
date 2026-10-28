import { describe, expect, it } from "vitest";
import { registrationError, safeInternalPath } from "./auth-utils";

describe("safeInternalPath", () => {
  it("preserves internal destinations", () => expect(safeInternalPath("/voice?property=12")).toBe("/voice?property=12"));
  it.each([null, "", "https://evil.example", "//evil.example", "/\\evil.example"]) (
    "rejects unsafe destination %s",
    (value) => expect(safeInternalPath(value)).toBe("/"),
  );
});

describe("registrationError", () => {
  it("rejects mismatched passwords", () => expect(registrationError("safePassword123", "differentPass123")).toBe("Passwords do not match."));
  it("enforces the password policy", () => expect(registrationError("short", "short")).toContain("10 characters"));
  it("accepts a matching password that satisfies policy", () => expect(registrationError("safePassword123", "safePassword123")).toBeNull());
});
