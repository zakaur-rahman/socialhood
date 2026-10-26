import { describe, expect, it, vi } from "vitest";

import { SAMPLE } from "@/test/publicApiSample";

import { buildReference, curlExample, describeType, fetchPublicApiDocument } from "./public-api";

describe("describeType", () => {
  it("names a schema the way a reader would", () => {
    expect(describeType({ type: "string", format: "uuid" })).toBe("uuid");
    expect(describeType({ anyOf: [{ type: "string" }, { type: "null" }] })).toBe("string or null");
    expect(describeType({ type: "array", items: { $ref: "#/components/schemas/Tag" } })).toBe("Tag[]");
    expect(describeType({ enum: ["a", "b"] })).toBe("one of a, b");
    expect(describeType(undefined)).toBe("any");
  });
});

describe("buildReference", () => {
  const reference = buildReference(SAMPLE);

  it("groups operations by tag in the API's order, methods in reading order", () => {
    expect(reference.groups.map((g) => g.tag)).toEqual(["Contacts", "REST hooks"]);
    expect(reference.groups[0].operations.map((o) => `${o.method} ${o.path}`)).toEqual([
      "GET /public/v1/contacts",
      "POST /public/v1/contacts",
      "GET /public/v1/contacts/{contact_id}",
    ]);
  });

  it("carries the scope, the parameters and the request body fields", () => {
    const create = reference.groups[0].operations[1];
    expect(create.scope).toBe("contacts:write");
    expect(create.body).toEqual([
      { name: "account_id", type: "uuid", required: true, description: null },
      { name: "phone", type: "string", required: true, description: "With its country code." },
      { name: "tags", type: "Tag[]", required: false, description: null },
    ]);
    const list = reference.groups[0].operations[0];
    expect(list.parameters.map((p) => [p.name, p.type, p.required])).toEqual([
      ["q", "string or null", false],
      ["limit", "integer", false],
      ["sort", "one of activity, created", false],
    ]);
    expect(reference.groups[0].operations[2].parameters[0]).toMatchObject({ name: "contact_id", required: true, type: "uuid" });
  });

  it("lists the responses without the generic ones, and the scopes the document names", () => {
    expect(reference.groups[0].operations[1].responses).toEqual([{ status: "201", description: "Successful Response" }]);
    expect(reference.scopes).toEqual([
      { scope: "contacts:read", description: "Read contacts." },
      { scope: "contacts:write", description: "Create contacts." },
    ]);
    expect(reference.paragraphs).toEqual(["Read contacts.", "Errors are problem+json."]);
  });

  it("falls back to the operation id for a missing summary", () => {
    expect(reference.groups[0].operations[2].summary).toBe("get contact");
  });
});

describe("curlExample", () => {
  it("sends the key from an environment variable and the required body fields", () => {
    const [, create, one] = buildReference(SAMPLE).groups[0].operations;
    expect(curlExample(create, "https://api.example.test/")).toBe(
      [
        'curl -X POST "https://api.example.test/public/v1/contacts" \\',
        '  -H "Authorization: Bearer $SOCIALHOOD_API_KEY" \\',
        '  -H "Content-Type: application/json" \\',
        `  -d '{"account_id":"<account_id>","phone":"<phone>"}'`,
      ].join("\n"),
    );
    expect(curlExample(one, "https://api.example.test")).toContain("/public/v1/contacts/<contact_id>");
  });
});

describe("fetchPublicApiDocument", () => {
  const ok = (body: unknown) => vi.fn(async () => new Response(JSON.stringify(body), { status: 200 })) as unknown as typeof fetch;

  it("reads the document from the API's public path", async () => {
    const fetcher = ok(SAMPLE);
    const document = await fetchPublicApiDocument("https://api.example.test/", fetcher);
    expect(document?.info.title).toBe("Amplychat public API");
    expect(vi.mocked(fetcher).mock.calls[0][0]).toBe("https://api.example.test/public/v1/openapi.json");
  });

  it("is null when the API is unset, down, answers an error or sends something else", async () => {
    expect(await fetchPublicApiDocument(undefined, ok(SAMPLE))).toBeNull();
    const down = vi.fn(async () => {
      throw new Error("offline");
    }) as unknown as typeof fetch;
    expect(await fetchPublicApiDocument("https://api.example.test", down)).toBeNull();
    const failing = vi.fn(async () => new Response("no", { status: 503 })) as unknown as typeof fetch;
    expect(await fetchPublicApiDocument("https://api.example.test", failing)).toBeNull();
    expect(await fetchPublicApiDocument("https://api.example.test", ok({ hello: "world" }))).toBeNull();
  });
});
