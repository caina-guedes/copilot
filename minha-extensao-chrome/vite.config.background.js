import { defineConfig } from 'vite'
import path from 'path'

export default defineConfig({
  build: {
    outDir: 'dist/background',
    target: 'es2017',
    emptyOutDir: false,
    rollupOptions: {
      input: path.resolve(__dirname, 'src/background/index.js'),
      output: {
        entryFileNames: 'background.js',
        chunkFileNames: 'chunks/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
        preserveEntrySignatures: false
      }
    }
  }
})
