import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { definirAoExpirar, lerToken, salvarToken } from "../api/client";
import * as endpoints from "../api/endpoints";
import type { Modulo, Perfil, Usuario } from "../types";
import { ehAdminNo, ehGestor, MODULOS, papelNo, temAcesso } from "../utils/modulos";

interface Auth {
  usuario: Usuario | null;
  carregando: boolean;
  /** Administrador do **Planner de Ofícios** (ADMIN do módulo ou MASTER). Para os outros módulos: `ehAdminNo`. */
  ehAdmin: boolean;
  ehMaster: boolean;
  /** MASTER ou administrador de algum módulo: acessa a gestão de usuários. */
  ehGestor: boolean;
  /** Módulos que o usuário pode abrir. */
  modulos: Modulo[];
  papelNo: (modulo: Modulo) => Perfil | null;
  ehAdminNo: (modulo: Modulo) => boolean;
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
      ehAdmin: ehAdminNo(usuario, "OFICIOS"),
      ehMaster: usuario?.perfil === "MASTER",
      ehGestor: ehGestor(usuario),
      modulos: usuario ? MODULOS.filter((m) => temAcesso(usuario, m.modulo)).map((m) => m.modulo) : [],
      papelNo: (m: Modulo) => papelNo(usuario, m),
      ehAdminNo: (m: Modulo) => ehAdminNo(usuario, m),
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
