import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { definirAoExpirar, lerToken, salvarToken } from "../api/client";
import * as endpoints from "../api/endpoints";
import type { Usuario } from "../types";

interface Auth {
  usuario: Usuario | null;
  carregando: boolean;
  ehAdmin: boolean; // ADMIN ou MASTER
  ehMaster: boolean;
  entrar: (login: string, senha: string) => Promise<void>;
  sair: () => void;
}

const AuthContext = createContext<Auth | null>(null);

export const CHAVE_SESSAO_ENCERRADA = "planner-sessao-encerrada";

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [carregando, setCarregando] = useState(() => Boolean(lerToken()));

  const sair = useCallback(() => {
    salvarToken(null);
    setUsuario(null);
    queryClient.clear(); // não deixa dados de um usuário aparecerem para o próximo
  }, [queryClient]);

  useEffect(() => {
    // Sessão recusada pela API (tempo esgotado ou senha trocada): a tela de login explica o motivo
    definirAoExpirar(() => {
      try {
        sessionStorage.setItem(CHAVE_SESSAO_ENCERRADA, "1");
      } catch {
        /* sem armazenamento: só não mostra o aviso */
      }
      sair();
    });
    if (!lerToken()) return;
    endpoints
      .eu()
      .then(setUsuario)
      .catch(() => sair())
      .finally(() => setCarregando(false));
  }, [sair]);

  const entrar = useCallback(
    async (login: string, senha: string) => {
      const token = await endpoints.login(login, senha);
      queryClient.clear();
      salvarToken(token.access_token);
      setUsuario(token.usuario);
    },
    [queryClient],
  );

  const valor = useMemo(
    () => ({
      usuario,
      carregando,
      ehAdmin: usuario?.perfil === "ADMIN" || usuario?.perfil === "MASTER",
      ehMaster: usuario?.perfil === "MASTER",
      entrar,
      sair,
    }),
    [usuario, carregando, entrar, sair],
  );
  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>;
}

export function useAuth(): Auth {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth fora do AuthProvider");
  return ctx;
}
