/** A small public API document for the reference tests (the shape api/public_openapi.py serves). */
import type { PublicApiDocument } from "@/lib/marketing/public-api";

export const SAMPLE = {
  info: { title: "Social Hood public API", version: "1.0.0", description: "Read contacts.\n\nErrors are problem+json." },
  "x-scopes": { "contacts:read": "Read contacts.", "contacts:write": "Create contacts." },
  paths: {
    "/public/v1/contacts": {
      post: {
        operationId: "create_contact",
        summary: "Create Contact",
        description: "Add a customer by phone number.\n\nRequires the `contacts:write` scope.",
        tags: ["Contacts"],
        "x-required-scope": "contacts:write",
        requestBody: {
          content: { "application/json": { schema: { $ref: "#/components/schemas/ContactCreate" } } },
        },
        responses: { "201": { description: "Successful Response" }, "422": { description: "Validation error" }, default: { description: "Problem" } },
      },
      get: {
        operationId: "list_contacts",
        summary: "List Contacts",
        description: "Latest activity first.",
        tags: ["Contacts"],
        "x-required-scope": "contacts:read",
        parameters: [
          { name: "q", in: "query", required: false, schema: { anyOf: [{ type: "string", maxLength: 100 }, { type: "null" }] } },
          { name: "limit", in: "query", schema: { type: "integer" }, description: "Up to 100." },
          { name: "sort", in: "query", schema: { enum: ["activity", "created"] } },
        ],
        responses: { "200": { description: "Successful Response" } },
      },
    },
    "/public/v1/contacts/{contact_id}": {
      get: {
        operationId: "get_contact",
        tags: ["Contacts"],
        "x-required-scope": "contacts:read",
        parameters: [{ name: "contact_id", in: "path", required: true, schema: { type: "string", format: "uuid" } }],
        responses: { "200": { description: "Successful Response" } },
      },
    },
    "/public/v1/hooks": {
      post: { operationId: "subscribe_hook", tags: ["REST hooks"], "x-required-scope": "webhooks:subscribe", responses: { "201": { description: "Created" } } },
    },
  },
  components: {
    schemas: {
      ContactCreate: {
        type: "object",
        required: ["account_id", "phone"],
        properties: {
          account_id: { type: "string", format: "uuid" },
          phone: { type: "string", description: "With its country code." },
          tags: { type: "array", items: { $ref: "#/components/schemas/Tag" } },
        },
      },
    },
  },
} as unknown as PublicApiDocument;
