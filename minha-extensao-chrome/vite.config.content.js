import { defineConfig } from 'vite'
import path from 'path'

export default defineConfig({
  build: {
    outDir: 'dist/content',
    target: 'es2017',
    emptyOutDir: false,
    rollupOptions: {
      input: path.resolve(__dirname, 'src/content/index.js'),
      output: {
        inlineDynamicImports: true,
        preserveEntrySignatures: false,
        entryFileNames: 'content.js'
      }
    }
  }
})
