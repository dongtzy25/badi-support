import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dev server forwards API calls to FastAPI, so the browser only ever talks
// to one origin (no CORS problems, and the WebSocket URL is simply /ws/...).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
