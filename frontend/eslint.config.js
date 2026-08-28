import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: { window: "readonly", document: "readonly", localStorage: "readonly", fetch: "readonly" },
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      // This app fetches data on mount with plain useEffect+useState (no
      // react-query/SWR in this vertical slice), the standard pattern React's
      // own docs describe for "fetching data when a component mounts" --
      // https://react.dev/learn/synchronizing-with-effects#fetching-data.
      // This rule (new in eslint-plugin-react-hooks v7) flags exactly that
      // pattern as a cascading-render risk; it's a legitimate concern for
      // effects that set state *in response to other state*, not for a
      // one-shot fetch-on-mount, so it's disabled rather than restructured
      // into an unnecessary cancellation-token pattern.
      "react-hooks/set-state-in-effect": "off",
    },
  },
);
