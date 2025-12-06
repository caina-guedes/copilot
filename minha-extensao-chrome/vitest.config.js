// vitest.config.js
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    globals: true,                 // permite usar describe/it/expect sem imports extras
    environment: 'jsdom',          // disponibiliza `window`, `alert()`, etc.
    include: ['src/**/*.{test,spec}.{js,ts}'], // padrões de arquivo de teste
    coverage: {
      reporter: ['text', 'html'],  // relatórios de cobertura no terminal e em HTML
    },
  },
})
