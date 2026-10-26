import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Em desenvolvimento o Vite repassa /api para a API (porta 3112).
// Em produção, `npm run build` gera dist/, que a própria API serve na porta 3112.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // acessível na rede também em desenvolvimento
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:3112" },
  },
});
