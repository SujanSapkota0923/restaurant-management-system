import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist/", "dev-dist/", "coverage/", "node_modules/"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.strictTypeChecked,
      reactHooks.configs.flat.recommended,
    ],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      // Never render untrusted HTML (.claude/rules/security.md).
      "no-restricted-syntax": [
        "error",
        {
          selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
          message: "Rendering raw HTML is forbidden. See docs/conventions/frontend.md.",
        },
      ],
      // No tokens or personal data in web storage (frontend conventions).
      "no-restricted-globals": [
        "error",
        { name: "localStorage", message: "Web storage is restricted; see frontend conventions." },
        { name: "sessionStorage", message: "Web storage is restricted; see frontend conventions." },
      ],
      "no-restricted-properties": [
        "error",
        { object: "window", property: "localStorage", message: "Web storage is restricted." },
        { object: "window", property: "sessionStorage", message: "Web storage is restricted." },
        { object: "globalThis", property: "localStorage", message: "Web storage is restricted." },
        { object: "globalThis", property: "sessionStorage", message: "Web storage is restricted." },
      ],
    },
  },
  {
    files: ["vite.config.ts", "config/**/*.ts"],
    languageOptions: { globals: globals.node },
  },
  {
    files: ["eslint.config.js"],
    extends: [js.configs.recommended],
    languageOptions: { globals: globals.node },
  },
);
