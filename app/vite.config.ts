import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
import { inspectAttr } from 'kimi-plugin-inspect-react'

export default defineConfig({
  base: './',   // must stay './' — kimi plugin requires it
  plugins: [inspectAttr(), react()],
  server: {
    port: 3000,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        manualChunks: {
          vendor:   ['react', 'react-dom', 'react-router'],
          ui:       ['@radix-ui/react-select', '@radix-ui/react-dialog', '@radix-ui/react-tabs'],
          charts:   ['recharts'],
          markdown: ['react-markdown'],
        },
      },
    },
  },
})
