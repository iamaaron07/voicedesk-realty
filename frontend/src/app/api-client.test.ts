import { describe, expect, it } from "vitest";
import { resolveApiOrigin } from "./api-client";

describe("resolveApiOrigin", () => {
  it("uses localhost only for local development when unset", () => {
    expect(resolveApiOrigin(undefined, "development")).toBe("http://localhost:8000");
    expect(resolveApiOrigin(undefined, "production")).toBe("");
  });

  it("normalizes a configured origin", () => {
    expect(resolveApiOrigin(" https://api.example.test/ ", "production")).toBe("https://api.example.test");
  });
});
