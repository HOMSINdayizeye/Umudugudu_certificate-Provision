import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.PORT) || 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        // When the Django server is not running, answer with a JSON error the app can show instead of an empty 500
        configure: (proxy) => {
          proxy.on('error', (err, req, res) => {
            console.error(`[api proxy] ${req.method} ${req.url} -> backend unreachable: ${err.message}`)
            if (res.writeHead && !res.headersSent) {
              res.writeHead(503, { 'Content-Type': 'application/json' })
              res.end(JSON.stringify({
                detail: 'The backend is not running on http://127.0.0.1:8000. Start it with "npm run dev:api" (or "npm run dev" for both servers).',
                code: 'backend_unreachable', error: err.message,
              }))
            }
          })
        },
      },
    },
  },
})
