import { useQuery } from "@tanstack/react-query";
import { unidadeDoServidor } from "../api/endpoints";

/** Unidade atendida por este servidor (cada unidade tem o seu). Vem do .env do back-end e não muda na sessão. */
export function useUnidade() {
  return useQuery({ queryKey: ["unidade"], queryFn: unidadeDoServidor, staleTime: Infinity, retry: false }).data;
}

/** Nome da unidade, quando configurado (sem ele, não aparece nada). */
export function NomeUnidade({ className }: { className?: string }) {
  const unidade = useUnidade();
  if (!unidade?.nome) return null;
  return <span className={className} title={unidade.descricao ?? undefined}>{unidade.nome}</span>;
}
