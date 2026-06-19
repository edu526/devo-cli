import js from "@eslint/js";
import tseslint from "typescript-eslint";
import svelte from "eslint-plugin-svelte";
import prettier from "eslint-config-prettier";
import globals from "globals";

export default [
  {
    ignores: [
      "node_modules/**",
      "dist/**",
      "src-tauri/**",
      "src/**/*.svelte-kit/**",
      "coverage/**",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...svelte.configs["flat/recommended"],
  prettier,
  ...svelte.configs["flat/prettier"],
  {
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
  },
  {
    files: ["**/*.svelte", "**/*.svelte.ts"],
    languageOptions: {
      parserOptions: {
        parser: tseslint.parser,
        extraFileExtensions: [".svelte"],
      },
    },
  },
  {
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/no-explicit-any": "warn",
      "no-console": ["warn", { allow: ["warn", "error"] }],
    },
  },
  {
    files: ["**/*.test.ts", "src/**/__tests__/**", "src/**/*.spec.ts"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "no-console": "off",
    },
  },
];
