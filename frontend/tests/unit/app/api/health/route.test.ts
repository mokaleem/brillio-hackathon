import { describe, expect, test } from "@rstest/core";

import { GET } from "@/app/api/health/route";

describe("GET /api/health", () => {
  test("returns frontend health metadata", async () => {
    const response = GET();

    await expect(response.json()).resolves.toEqual({
      status: "healthy",
      service: "deer-flow-frontend",
    });
  });
});
