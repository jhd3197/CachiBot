import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  css: {
    preprocessorOptions: {
      less: {
        additionalData: `
          @import "${path.resolve(__dirname, 'src/styles/variables.less')}";
          @import "${path.resolve(__dirname, 'src/styles/mixins.less')}";
        `,
        javascriptEnabled: true,
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5870',
        changeOrigin: true,
      },
      '/ws': {
        target: 'http://127.0.0.1:5870',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
