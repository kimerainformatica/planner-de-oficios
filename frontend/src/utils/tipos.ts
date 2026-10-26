import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { listarTipos } from "../api/endpoints";
import type { TipoInfo, TipoOficio } from "../types";

export const SEM_TIPO = "Não classificado";

export interface Tipos {
  todos: TipoInfo[]; // inclusive desativados: filtros e ofícios antigos ainda usam
  ativos: TipoInfo[]; // os que podem ser escolhidos num ofício novo
  /** Nome do tipo; curto = nome curto quando houver (lista e gráficos). */
  rotulo: (codigo: TipoOficio | null | undefined, curto?: boolean) => string;
  /** Depois da resposta confirmada, a entrega também precisa ser confirmada? */
  exigeEntrega: (codigo: TipoOficio | null | undefined) => boolean;
}

/** Tipos de ofício cadastrados pelos administradores (carregados uma vez e guardados por 5 minutos). */
export function useTipos(): Tipos {
  const { data = [] } = useQuery({ queryKey: ["tipos"], queryFn: listarTipos, staleTime: 5 * 60_000 });
  return useMemo(() => {
    const porCodigo = new Map(data.map((t) => [t.codigo, t]));
    return {
      todos: data,
      ativos: data.filter((t) => t.ativo),
      rotulo: (codigo, curto = false) => {
        if (!codigo) return SEM_TIPO;
        const t = porCodigo.get(codigo);
        return t ? (curto && t.nome_curto) || t.nome : codigo;
      },
      exigeEntrega: (codigo) => !!codigo && !!porCodigo.get(codigo)?.exige_entrega,
    };
  }, [data]);
}
