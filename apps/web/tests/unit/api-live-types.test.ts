/**
 * The test that the types of the frontend agree with the published contracts.
 *
 * Why this file exists: the three contracts of `specs/003-r3-bring-your-own-key/contracts/` are
 * read by the Python core, and the frontend has its own transcription of them. The two can drift
 * apart silently, and a drift shows up as a field the browser reads and the server never sends.
 * This test reads the JSON Schema files of the repository and checks, field by field, that every
 * required field of the contract is present in the TypeScript type.
 *
 * The path of the contracts is resolved from the location of this file and never from the current
 * working directory, so the test answers the same thing from the root of the repository and from
 * the folder of the application.
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  DEFAULT_RUN_LIMITS,
  type CostReportBody,
  type CredentialHandle,
  type LiveRunRequest,
  type ModelProfile,
} from "@/lib/api/live";

/** The folder of the contracts, resolved from the location of this file. */
const contractsDirectory = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../../specs/003-r3-bring-your-own-key/contracts",
);

/** One property of a JSON Schema, as much of it as this test reads. */
interface SchemaProperty {
  type?: string | string[];
  enum?: string[];
  required?: string[];
  minimum?: number;
  maximum?: number;
  properties?: Record<string, SchemaProperty>;
}

/** One contract of the repository, as much of it as this test reads. */
interface ContractSchema {
  title: string;
  required: string[];
  properties: Record<string, SchemaProperty>;
}

/** Reads one contract of the repository. */
function readContract(fileName: string): ContractSchema {
  const content = readFileSync(path.join(contractsDirectory, fileName), "utf8");
  return JSON.parse(content) as ContractSchema;
}

/**
 * Checks that a value has the shape the schema asks for.
 *
 * The check is about the value of the fixture, which is typed with the TypeScript type of the
 * frontend, so the two answers have to agree: the type says what the field is, and the schema
 * says what the server sends.
 */
function expectTheValueToMatch(property: SchemaProperty, field: string, value: unknown): void {
  const types = Array.isArray(property.type) ? property.type : property.type ? [property.type] : [];
  if (types.length > 0) {
    const matches = types.some((type) => {
      if (type === "string") {
        return typeof value === "string";
      }
      if (type === "integer") {
        return typeof value === "number" && Number.isInteger(value);
      }
      if (type === "number") {
        return typeof value === "number";
      }
      if (type === "boolean") {
        return typeof value === "boolean";
      }
      if (type === "null") {
        return value === null;
      }
      if (type === "object") {
        return typeof value === "object" && value !== null;
      }
      if (type === "array") {
        return Array.isArray(value);
      }
      return false;
    });
    expect(matches, `the field ${field} does not have the type of the contract`).toBe(true);
  }
  if (property.enum) {
    expect(property.enum, `the field ${field} is not one of the values of the contract`).toContain(
      value as string,
    );
  }
}

/**
 * Checks that every required field of a contract is present in the fixture, field by field.
 *
 * The fixture is typed with the TypeScript type of the frontend, so the compiler already refuses
 * a field the type does not have and a field the type requires and the fixture misses. The
 * assertions of the runtime are the other half: they refuse a required field of the contract
 * that the type does not carry at all.
 */
function expectEveryRequiredField(schema: ContractSchema, fixture: Record<string, unknown>): void {
  for (const field of schema.required) {
    expect(Object.keys(fixture), `the type does not carry the field ${field}`).toContain(field);
    const property = schema.properties[field];
    if (property) {
      expectTheValueToMatch(property, field, fixture[field]);
    }
  }
}

/** The credential of the contract, with every required field. */
const aCredential: CredentialHandle = {
  handle: "cred_0123456789abcdef0123456789abcdef",
  provider: "openai",
  created_at: "2026-11-21T10:00:00+00:00",
  expires_at: "2026-11-21T18:00:00+00:00",
};

/** The request of a live run, with every required field of the contract. */
const aRunRequest: LiveRunRequest = {
  mode: "live_agent",
  scenario_id: "S01",
  sandbox_id: "branch_0123456789abcdef",
  expected_revision: 0,
  account_id: "C-0001",
  question: "Why was the BRL refund for TX-2048 lower than the EUR payment?",
  variant: "A",
  model_profile_id: "profile_1",
  credential_handle: "cred_0123456789abcdef0123456789abcdef",
  limits: DEFAULT_RUN_LIMITS,
};

/** The profile of a model, with every required field of the contract. */
const aModelProfile: ModelProfile = {
  profile_id: "profile_1",
  provider: "openai",
  model_id: "gpt-4o-mini",
  display_name: "A small tested model",
  capabilities: ["chat", "tool_calling"],
  status: "tested",
  enabled_in_public_demo: true,
  pricing: {
    source: "provider",
    last_verified: "2026-11-01",
    input_per_1m_usd: "0.15",
    output_per_1m_usd: "0.60",
  },
};

describe("the types of the published contracts", () => {
  it("carries every required field of the credential handle", () => {
    const schema = readContract("credential-handle.schema.json");
    expectEveryRequiredField(schema, aCredential as unknown as Record<string, unknown>);
  });

  it("carries every required field of the request of a live run", () => {
    const schema = readContract("live-run-request.schema.json");
    expectEveryRequiredField(schema, aRunRequest as unknown as Record<string, unknown>);
  });

  it("carries every required field of the limits of the request", () => {
    const schema = readContract("live-run-request.schema.json");
    const limits = schema.properties["limits"];
    expect(limits).toBeDefined();
    expectEveryRequiredField(
      { title: "RunLimits", required: limits?.required ?? [], properties: limits?.properties ?? {} },
      aRunRequest.limits as unknown as Record<string, unknown>,
    );
  });

  it("carries every required field of the profile of a model", () => {
    const schema = readContract("model-profile.schema.json");
    expectEveryRequiredField(schema, aModelProfile as unknown as Record<string, unknown>);
  });

  it("carries every required field of the price of a model", () => {
    const schema = readContract("model-profile.schema.json");
    const pricing = schema.properties["pricing"];
    expect(pricing).toBeDefined();
    expectEveryRequiredField(
      { title: "Pricing", required: pricing?.required ?? [], properties: pricing?.properties ?? {} },
      aModelProfile.pricing as unknown as Record<string, unknown>,
    );
  });

  it("keeps the default limits inside the bounds of the contract", () => {
    const schema = readContract("live-run-request.schema.json");
    const limits = schema.properties["limits"];
    const fields = ["max_model_calls", "max_tool_calls", "max_wall_seconds", "max_output_tokens"];

    for (const field of fields) {
      const property = limits?.properties?.[field];
      const value = DEFAULT_RUN_LIMITS[field as keyof typeof DEFAULT_RUN_LIMITS];
      expect(typeof value, `the default of ${field} is not a number`).toBe("number");
      if (typeof value === "number") {
        expect(value).toBeGreaterThanOrEqual(property?.minimum ?? Number.NEGATIVE_INFINITY);
        expect(value).toBeLessThanOrEqual(property?.maximum ?? Number.POSITIVE_INFINITY);
      }
    }
  });

  it("keeps the money of the cost report as a text and never as a number", () => {
    const money: CostReportBody["observed_cost_usd"] = "0.0123";
    expect(money).toBe("0.0123");

    // @ts-expect-error the frontend never turns money into a number.
    const moneyAsNumber: CostReportBody["observed_cost_usd"] = 0.0123;
    expect(moneyAsNumber).toBe(0.0123);
  });
});
