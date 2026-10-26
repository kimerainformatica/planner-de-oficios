import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { IconeBaixar, IconeLixo, IconeRestaurar, IconeVer } from "./Icones";
import { Link } from "react-router-dom";
import { apagarDaLixeira, baixarDaLixeira, listarLixeira, restaurarDaLixeira } from "../api/endpoints";
import type { AnexoLixeira, TipoAnexo } from "../types";
import { salvarArquivo } from "../utils/arquivo";
import { dataHora, tamanho } from "../utils/formato";
import { useToast } from "./Toast";
import { Botao, Carregando, ErroBox } from "./ui";

const NOME_TIPO: Record<TipoAnexo, string> = {
  OFICIO: "Documento do ofício",
  REFERENCIA: "Documento de referência",
  RESPOSTA: "Evidência da resposta",
  RECEBIMENTO: "Evidência da entrega",
};

export function useLixeira(oficioId?: number) {
  return useQuery({ queryKey: ["lixeira", oficioId ?? "todas"], queryFn: () => listarLixeira(oficioId) });
}

/** Versões anteriores de anexos (admin/master): visualizar, baixar, restaurar ou apagar de vez. */
export function ListaLixeira({ oficioId }: { oficioId?: number }) {
  const avisar = useToast();
  const queryClient = useQueryClient();
  const consulta = useLixeira(oficioId);

  const aposMudanca = () => {
    for (const chave of ["lixeira", "oficio", "oficios", "atividades", "verificacao"]) {
      queryClient.invalidateQueries({ queryKey: [chave] });
    }
  };
  const restaurar = useMutation({
    mutationFn: (i: AnexoLixeira) => restaurarDaLixeira(i.id),
    onSuccess: () => {
      aposMudanca();
      avisar("Documento restaurado. Se havia outro no lugar, ele foi para a lixeira.");
    },
    onError: (e) => avisar(e.message, "erro"),
  });
  const apagar = useMutation({
    mutationFn: (i: AnexoLixeira) => apagarDaLixeira(i.id),
    onSuccess: () => {
      aposMudanca();
      avisar("Apagado de vez.");
    },
    onError: (e) => avisar(e.message, "erro"),
  });

  async function abrir(i: AnexoLixeira, baixar: boolean) {
    const janela = baixar ? null : window.open("", "_blank"); // abre já no clique para o navegador não bloquear
    try {
      const blob = await baixarDaLixeira(i);
      if (baixar) return salvarArquivo(blob, i.nome_original);
      const url = URL.createObjectURL(blob);
      if (janela) janela.location.href = url;
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      janela?.close();
      avisar(e instanceof Error ? e.message : "Não foi possível abrir", "erro");
    }
  }

  if (consulta.isPending) return <Carregando />;
  if (consulta.isError) return <ErroBox erro={consulta.error} />;
  if (consulta.data.length === 0) {
    return <p className="texto-suave">A lixeira está vazia{oficioId ? " para este ofício" : ""}.</p>;
  }
  return (
    <ul className="lixeira">
      {consulta.data.map((i) => (
        <li key={i.id}>
          <FileText size={22} className="texto-suave" aria-hidden />
          <div className="lixeira-info">
            <strong className="arquivo-nome" title={i.nome_original}>{i.nome_original}</strong>
            <small className="texto-suave">
              {NOME_TIPO[i.tipo]}
              {!oficioId && (
                <>
                  {" · "}
                  <Link to={`/oficios/${i.oficio_id}`} className="link">Ofício nº {i.oficio_numero}</Link>
                </>
              )}
              {" · "}
              {tamanho(i.tamanho_bytes)}
            </small>
            <small className="texto-suave">
              {i.motivo === "SUBSTITUIDO" ? "Substituído" : "Removido"} em {dataHora(i.descartado_em)}
              {i.descartado_por_nome && ` por ${i.descartado_por_nome}`}
            </small>
          </div>
          <div className="grupo">
            <button className="btn btn-secundario btn-pequeno" onClick={() => abrir(i, false)}>
              <IconeVer tamanho={16} /> Visualizar
            </button>
            <button className="btn btn-secundario btn-pequeno" onClick={() => abrir(i, true)}>
              <IconeBaixar tamanho={16} /> Baixar
            </button>
            <Botao className="btn btn-secundario btn-pequeno" carregando={restaurar.isPending && restaurar.variables?.id === i.id}
              onClick={() => restaurar.mutate(i)}>
              <IconeRestaurar tamanho={16} /> Restaurar
            </Botao>
            <Botao className="btn btn-fantasma btn-pequeno texto-perigo"
              carregando={apagar.isPending && apagar.variables?.id === i.id}
              onClick={() => confirm(`Apagar "${i.nome_original}" de vez? Não dá para desfazer.`) && apagar.mutate(i)}>
              <IconeLixo tamanho={16} /> Apagar de vez
            </Botao>
          </div>
        </li>
      ))}
    </ul>
  );
}
