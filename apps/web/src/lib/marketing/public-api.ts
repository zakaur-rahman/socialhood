/**
 * The public API's reference (GR-25), from the API's own OpenAPI document for /public/v1
 * (GET /v1 is the app's; /public/v1/openapi.json is only the public API). Read on the server and
 * revalidated hourly; the page renders it minimally, with no OpenAPI viewer library. When the API
 * can't be reached the page says so instead of showing a stale or invented reference.
 */
import { z } from "zod";

export const PUBLIC_API_REVALIDATE_SECONDS = 3600;
const TIMEOUT_MS = 5000;
export const PUBLIC_API_DOCUMENT_PATH = "/public/v1/openapi.json";

type Schema = {
  $ref?: string;
  type?: string;
  format?: string;
  enum?: unknown[];
  const?: unknown;
  items?: Schema;
  anyOf?: Schema[];
  oneOf?: Schema[];
  allOf?: Schema[];
  properties?: Record<string, Schema & { description?: string }>;
  required?: string[];
  description?: string;
  additionalProperties?: Schema | boolean;
};

// A schema is read as it comes (the API's OpenAPI is generated, not user input); the page only
// reads the fields in `Schema`, so an object is all that is checked.
const SchemaShape = z.custom<Schema>((value) => typeof value === "object" && value !== null);

const OperationShape = z
  .object({
    operationId: z.string(),
    summary: z.string().optional(),
    description: z.string().optional(),
    tags: z.array(z.string()).optional(),
    "x-required-scope": z.string().optional(),
    parameters: z
      .array(
        z
          .object({
            name: z.string(),
            in: z.string(),
            required: z.boolean().optional(),
            description: z.string().optional(),
            schema: SchemaShape.optional(),
          })
          .loose(),
      )
      .optional(),
    requestBody: z
      .object({
        content: z.record(z.string(), z.object({ schema: SchemaShape.optional() }).loose()).optional(),
      })
      .loose()
      .optional(),
    responses: z.record(z.string(), z.object({ description: z.string().optional() }).loose()).optional(),
  })
  .loose();

const DocumentShape = z
  .object({
    info: z.object({ title: z.string(), version: z.string(), description: z.string().optional() }).loose(),
    paths: z.record(z.string(), z.record(z.string(), OperationShape)),
    components: z.object({ schemas: z.record(z.string(), SchemaShape).optional() }).loose().optional(),
    "x-scopes": z.record(z.string(), z.string()).optional(),
  })
  .loose();

export type PublicApiDocument = z.infer<typeof DocumentShape>;

/** GET /public/v1/openapi.json on the server. Null when the API is unset, down, slow or answers badly. */
export async function fetchPublicApiDocument(
  baseUrl: string | undefined = process.env.NEXT_PUBLIC_API_BASE_URL,
  fetcher: typeof fetch = fetch,
): Promise<PublicApiDocument | null> {
  if (!baseUrl) return null;
  try {
    const response = await fetcher(`${baseUrl.replace(/\/+$/, "")}${PUBLIC_API_DOCUMENT_PATH}`, {
      headers: { accept: "application/json" },
      next: { revalidate: PUBLIC_API_REVALIDATE_SECONDS },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!response.ok) return null;
    const parsed = DocumentShape.safeParse(await response.json());
    return parsed.success ? parsed.data : null;
  } catch {
    return null;
  }
}

// ---- what the page shows

export type ReferenceField = { name: string; type: string; required: boolean; description: string | null };
export type ReferenceOperation = {
  id: string;
  method: string;
  path: string;
  summary: string;
  paragraphs: string[];
  scope: string | null;
  parameters: ReferenceField[];
  body: ReferenceField[] | null;
  responses: { status: string; description: string }[];
};
export type ReferenceGroup = { tag: string; operations: ReferenceOperation[] };
export type Reference = {
  title: string;
  version: string;
  paragraphs: string[];
  scopes: { scope: string; description: string }[];
  groups: ReferenceGroup[];
};

const METHOD_ORDER = ["get", "post", "put", "patch", "delete"];

function refName(ref: string): string {
  return ref.slice(ref.lastIndexOf("/") + 1);
}

/** "string", "uuid", "Tag[]", "integer or null", "one of a, b". */
export function describeType(schema: Schema | undefined): string {
  if (!schema) return "any";
  if (schema.$ref) return refName(schema.$ref);
  const options = schema.anyOf ?? schema.oneOf;
  if (options) {
    const parts = options.map(describeType);
    return [...new Set(parts)].join(" or ");
  }
  if (schema.allOf?.length) return schema.allOf.map(describeType).join(" and ");
  if (schema.enum) return `one of ${schema.enum.map(String).join(", ")}`;
  if (schema.type === "array") return `${describeType(schema.items)}[]`;
  if (schema.type === "string" && schema.format) return schema.format;
  if (schema.type === "object" && schema.additionalProperties) return "object";
  return schema.type ?? "any";
}

function resolve(schema: Schema | undefined, schemas: Record<string, Schema>): Schema | undefined {
  if (!schema) return undefined;
  if (schema.$ref) return schemas[refName(schema.$ref)];
  return schema;
}

function bodyFields(schema: Schema | undefined, schemas: Record<string, Schema>): ReferenceField[] | null {
  const resolved = resolve(schema, schemas);
  if (!resolved?.properties) return null;
  const required = new Set(resolved.required ?? []);
  return Object.entries(resolved.properties).map(([name, property]) => ({
    name,
    type: describeType(property),
    required: required.has(name),
    description: property.description ?? null,
  }));
}

function paragraphs(text: string | undefined): string[] {
  return (text ?? "")
    .split(/\n{2,}/)
    .map((p) => p.replace(/\s*\n\s*/g, " ").trim())
    .filter(Boolean);
}

/** The document as groups of operations by tag, in the order the API lists them. */
export function buildReference(document: PublicApiDocument): Reference {
  const schemas = (document.components?.schemas ?? {}) as Record<string, Schema>;
  const groups = new Map<string, ReferenceOperation[]>();
  for (const [path, operations] of Object.entries(document.paths)) {
    const methods = Object.keys(operations).sort((a, b) => METHOD_ORDER.indexOf(a) - METHOD_ORDER.indexOf(b));
    for (const method of methods) {
      const operation = operations[method];
      const content = operation.requestBody?.content?.["application/json"];
      const tag = operation.tags?.[0] ?? "Other";
      const entry: ReferenceOperation = {
        id: operation.operationId,
        method: method.toUpperCase(),
        path,
        summary: operation.summary ?? operation.operationId.replaceAll("_", " "),
        paragraphs: paragraphs(operation.description),
        scope: operation["x-required-scope"] ?? null,
        parameters: (operation.parameters ?? []).map((p) => ({
          name: p.name,
          type: describeType(p.schema),
          required: p.required === true,
          description: p.description ?? null,
        })),
        body: bodyFields(content?.schema, schemas),
        responses: Object.entries(operation.responses ?? {})
          .filter(([status]) => status !== "default" && status !== "422")
          .map(([status, response]) => ({ status, description: response.description ?? "" })),
      };
      groups.set(tag, [...(groups.get(tag) ?? []), entry]);
    }
  }
  return {
    title: document.info.title,
    version: document.info.version,
    paragraphs: paragraphs(document.info.description),
    scopes: Object.entries(document["x-scopes"] ?? {}).map(([scope, description]) => ({ scope, description })),
    groups: [...groups.entries()].map(([tag, operations]) => ({ tag, operations })),
  };
}

/** A curl line for an operation, with the key in an environment variable. */
export function curlExample(operation: ReferenceOperation, baseUrl: string): string {
  const url = `${baseUrl.replace(/\/+$/, "")}${operation.path.replace(/{(\w+)}/g, "<$1>")}`;
  const lines = [`curl ${operation.method === "GET" ? "" : `-X ${operation.method} `}"${url}"`];
  lines.push(`  -H "Authorization: Bearer $SOCIALHOOD_API_KEY"`);
  if (operation.body) {
    lines.push(`  -H "Content-Type: application/json"`);
    const sample = Object.fromEntries(operation.body.filter((f) => f.required).map((f) => [f.name, `<${f.name}>`]));
    lines.push(`  -d '${JSON.stringify(sample)}'`);
  }
  return lines.join(" \\\n");
}
