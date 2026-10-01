import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Playwright's reports and traces from local e2e and screenshot runs.
    "playwright-report/**",
    "test-results/**",
  ]),
  {
    // cn is configured for the design system's utilities in lib/utils (C-070); import it from there.
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/lib/utils.ts"],
    rules: {
      "no-restricted-imports": [
        "error",
        { paths: [{ name: "cn", message: "Import cn from @/lib/utils: it knows the design system's utilities." }] },
      ],
    },
  },
]);

export default eslintConfig;
