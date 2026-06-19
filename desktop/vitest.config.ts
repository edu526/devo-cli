import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vitest/config";

export default defineConfig({
  // Tests use the Svelte client runtime (mount, unmount). Forcing
  // resolveExportConditions makes Node load `svelte/index.js` (the
  // client entry) instead of the server entry, which would otherwise
  // throw "mount() is not available on the server" inside jsdom.
  resolve: {
    conditions: ["browser"],
    alias: {
      $lib: "/src/lib",
    },
  },
  plugins: [
    svelte({
      hot: false,
      // Skip vitePreprocess in tests so we sidestep a known incompatibility
      // between vite-plugin-svelte 5 and Vitest's CSS preprocessing proxy
      // (manifests as "Cannot create proxy with a non-object as target or
      // handler"). The Svelte compiler still handles <script lang="ts">.
      preprocess: [],
    }),
  ],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,svelte}"],
    server: {
      deps: {
        inline: [/\.svelte\.js$/, /\.svelte\.ts$/],
      },
    },
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      include: ["src/lib/**/*.ts"],
      exclude: ["src/lib/**/*.test.ts", "src/lib/__tests__/**"],
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 75,
        statements: 80,
      },
    },
  },
});
