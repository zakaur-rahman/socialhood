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
  {
    // The toast rules (UI-024, DESIGN_SYSTEM §8.2, §10.12). toastError is where the first one is kept.
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/lib/toast-error.ts"],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          // toast.error(errorMessage(e)), also inside a template or a condition.
          selector:
            "CallExpression:matches([callee.name='toast'], [callee.object.name='toast']) CallExpression[callee.name='errorMessage']",
          message:
            "Show a failed request with toastError(error) or toastError(error, message) from @/lib/toast-error: a plan limit (402) is the upgrade dialog's to say, once (C-051).",
        },
        {
          selector:
            "CallExpression:matches([callee.name='toast'], [callee.object.name='toast']) ObjectExpression:has(> Property[key.name='action']):not(:has(> Property[key.name='duration']))",
          message:
            "A toast with an action stays 10 s or more (WCAG 2.2.1): add `duration: TOAST_ACTION_DURATION` from @/components/ui/sonner.",
        },
      ],
    },
  },
]);

export default eslintConfig;
