import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["node_modules/**", "dist/**", "test-results/**", "playwright-report/**", "public/models/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: { globals: { ...globals.browser } },
    plugins: { "react-hooks": reactHooks },
    rules: { ...reactHooks.configs.recommended.rules },
  },
  {
    // One clock (docs/CONTRACT.md section 1): client times are performance.now() ms since t0, never Date.now().
    files: ["src/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-properties": ["error", {
        object: "Date", property: "now", message: "Use performance.now() (ms since t0), never Date.now().",
      }],
    },
  },
  { files: ["*.config.{js,ts}", "e2e/**"], languageOptions: { globals: { ...globals.node } } },
);
