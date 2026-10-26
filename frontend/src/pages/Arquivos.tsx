import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { ultimaVerificacao, verificarArquivos } from "../api/endpoints";
import { ListaLixeira } from "../components/Lixeira";
import { useToast } from "../components/Toast";
import { Botao, Carregando, ErroBox } from "../components/ui";
import type { VerificacaoArquivos } from "../types";
import { dataHora } from "../utils/formato";

export const CHAVE_VERIFICACAO = ["verificacao"];

export function useVerificacao(ativo = true) {
  return useQuery({ queryKey: CHAVE_VERIFICACAO, queryFn: ultimaVerificacao, enabled: ativo, refetchInterval: 5 * 60_000 });
}

/** Admin/master: conferência dos arquivos guardados e a lixeira de todos os ofícios. */
export function Arquivos() {
  const avisar = useToast();
  const queryClient = useQueryClient();
  const verificacao = useVerificacao();
  const verificar = useMutation({
    mutationFn: (_: { avisar: boolean }) => verificarArquivos(),
    onSuccess: (r, { avisar: comAviso }) => {
      queryClient.setQueryData(CHAVE_VERIFICACAO, r);
      if (!comAviso) return;
      avisar(r.problemas.length ? `${r.problemas.length} arquivo(s) com problema.` : "Todos os arquivos estão íntegros.",
        r.problemas.length ? "erro" : "sucesso");
    },
    onError: (e) => avisar(e.message, "erro"),
  });
  // Ao abrir a página, confere de novo (a automática roda uma vez por dia)
  const { mutate } = verificar;
  useEffect(() => mutate({ avisar: false }), [mutate]);

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Arquivos</h1>
          <p className="texto-suave">
            Conferência dos documentos guardados e lixeira das versões substituídas ou removidas.
          </p>
        </div>
      </header>

      <section className="painel-bloco">
        <div className="bloco-topo">
          <div>
            <h2>Verificação dos arquivos</h2>
            <small className="texto-suave">
              Confere se cada documento ainda existe e não foi alterado fora do sistema (pelo hash SHA-256 gravado no
              envio). Roda sozinha uma vez por dia.
            </small>
          </div>
          <Botao className="btn btn-secundario" carregando={verificar.isPending} onClick={() => verificar.mutate({ avisar: true })}>
            <RefreshCw size={16} /> Verificar agora
          </Botao>
        </div>
        {verificacao.isPending ? (
          <Carregando texto="Verificando…" />
        ) : verificacao.isError ? (
          <ErroBox erro={verificacao.error} />
        ) : (
          <ResultadoVerificacao r={verificacao.data} />
        )}
      </section>

      <section className="painel-bloco">
        <div>
          <h2>Lixeira</h2>
          <small className="texto-suave">
            Quando um documento é substituído ou removido, a versão anterior fica aqui. Restaurar devolve ao ofício;
            apagar de vez tira o arquivo do servidor. Ao excluir um ofício, as versões dele também são apagadas.
          </small>
        </div>
        <ListaLixeira />
      </section>
    </>
  );
}

function ResultadoVerificacao({ r }: { r: VerificacaoArquivos }) {
  const ok = r.problemas.length === 0;
  return (
    <div className="verificacao">
      <div className={`verificacao-status ${ok ? "ok" : "falha"}`} role="status">
        {ok ? <CheckCircle2 size={20} /> : <AlertTriangle size={20} />}
        <div>
          <strong>
            {!ok
              ? `${r.problemas.length} de ${r.arquivos} arquivo(s) com problema`
              : r.arquivos === 0
                ? "Nenhum documento guardado ainda"
                : `${r.arquivos} ${r.arquivos === 1 ? "arquivo conferido, íntegro" : "arquivos conferidos, todos íntegros"}`}
          </strong>
          <small className="texto-suave">
            Última verificação em {dataHora(r.verificado_em)}
            {r.sem_registro > 0 &&
              ` · ${r.sem_registro} arquivo(s) na pasta sem ofício ligado (sobras antigas; não atrapalham)`}
          </small>
        </div>
      </div>
      {!ok && (
        <ul className="verificacao-problemas">
          {r.problemas.map((p) => (
            <li key={`${p.origem}-${p.id}`}>
              <span className={`badge ${p.problema === "AUSENTE" ? "badge-alerta-CRITICO" : "badge-alerta-ATENCAO"}`}>
                {p.problema === "AUSENTE" ? "Sumiu" : "Alterado"}
              </span>
              <span className="arquivo-nome" title={p.nome_original}>{p.nome_original}</span>
              <Link to={`/oficios/${p.oficio_id}`} className="link">Ofício nº {p.oficio_numero}</Link>
              {p.origem === "lixeira" && <small className="texto-suave">(na lixeira)</small>}
            </li>
          ))}
        </ul>
      )}
      {!ok && (
        <p className="texto-suave">
          Arquivo que sumiu ou foi alterado precisa ser recuperado do backup da pasta <code>backend/storage</code> ou
          enviado de novo no ofício.
        </p>
      )}
    </div>
  );
}
