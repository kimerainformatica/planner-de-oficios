import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, PackageCheck, Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { atualizarTipo, criarTipo, excluirTipo, listarTipos } from "../api/endpoints";
import { useToast } from "../components/Toast";
import { Botao, Campo, Carregando, ErroBox, Modal } from "../components/ui";
import type { TipoInfo } from "../types";

/** Cadastro dos tipos de ofício (admin/master): nome, nome curto, se exige entrega, ativo e ordem. */
export function TiposOficio() {
  const avisar = useToast();
  const queryClient = useQueryClient();
  const consulta = useQuery({ queryKey: ["tipos"], queryFn: listarTipos });
  const [editando, setEditando] = useState<TipoInfo | null>(null);

  // A regra do tipo muda status e prazos dos ofícios: recarrega listas, detalhe e painel
  const aposMudanca = () => {
    for (const chave of ["tipos", "oficios", "oficio", "analise", "resumo", "atividades"]) {
      queryClient.invalidateQueries({ queryKey: [chave] });
    }
  };

  const alterar = useMutation({
    mutationFn: ({ tipo, dados }: { tipo: TipoInfo; dados: Parameters<typeof atualizarTipo>[1] }) =>
      atualizarTipo(tipo.codigo, dados),
    onSuccess: (t) => {
      aposMudanca();
      avisar(`Tipo ${t.nome} atualizado.`);
    },
    onError: (e) => avisar(e.message, "erro"),
  });
  const mover = useMutation({
    mutationFn: async ({ a, b }: { a: TipoInfo; b: TipoInfo }) => {
      await atualizarTipo(a.codigo, { ordem: b.ordem });
      await atualizarTipo(b.codigo, { ordem: a.ordem });
    },
    onSuccess: aposMudanca,
    onError: (e) => avisar(e.message, "erro"),
  });
  const apagar = useMutation({
    mutationFn: (t: TipoInfo) => excluirTipo(t.codigo),
    onSuccess: () => {
      aposMudanca();
      avisar("Tipo apagado.");
    },
    onError: (e) => avisar(e.message, "erro"),
  });

  function trocarEntrega(t: TipoInfo) {
    const passa = !t.exige_entrega;
    const aviso = t.em_uso
      ? passa
        ? `\n\nOs ofícios deste tipo com resposta confirmada passam a aguardar a confirmação da entrega.`
        : `\n\nOs ofícios deste tipo aguardando entrega ou recebidos passam a Confirmado (o histórico é mantido).`
      : "";
    if (confirm(`${passa ? "Exigir" : "Deixar de exigir"} a confirmação da entrega em "${t.nome}"?${aviso}`)) {
      alterar.mutate({ tipo: t, dados: { exige_entrega: passa } });
    }
  }

  const tipos = consulta.data ?? [];
  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Tipos de ofício</h1>
          <p className="texto-suave">
            Os tipos que aparecem no cadastro dos ofícios, nos filtros e no painel. Desativar tira o tipo do
            cadastro de ofícios novos sem mexer nos que já existem.
          </p>
        </div>
      </header>

      <div className="duas-colunas colunas-tipos">
        <section className="painel-bloco">
          <h2>Tipos cadastrados</h2>
          {consulta.isPending ? (
            <Carregando />
          ) : consulta.isError ? (
            <ErroBox erro={consulta.error} />
          ) : (
            <div className="tabela-mini-box">
              <table className="tabela tabela-tipos">
                <thead>
                  <tr>
                    <th>Ordem</th>
                    <th>Nome</th>
                    <th>Exige entrega</th>
                    <th>Situação</th>
                    <th className="num">Ofícios</th>
                    <th aria-label="Ações" />
                  </tr>
                </thead>
                <tbody>
                  {tipos.map((t, i) => (
                    <tr key={t.codigo} className={t.ativo ? "" : "linha-inativa"}>
                      <td>
                        <span className="grupo grupo-justo">
                          <button className="btn-icone" aria-label={`Subir ${t.nome}`} disabled={i === 0 || mover.isPending}
                            onClick={() => mover.mutate({ a: t, b: tipos[i - 1] })}>
                            <ArrowUp size={15} />
                          </button>
                          <button className="btn-icone" aria-label={`Descer ${t.nome}`}
                            disabled={i === tipos.length - 1 || mover.isPending}
                            onClick={() => mover.mutate({ a: t, b: tipos[i + 1] })}>
                            <ArrowDown size={15} />
                          </button>
                        </span>
                      </td>
                      <td>
                        <strong>{t.nome}</strong>
                        {t.nome_curto && <small className="celula-sub">Curto: {t.nome_curto}</small>}
                      </td>
                      <td>
                        <label className="checkbox">
                          <input type="checkbox" checked={t.exige_entrega} disabled={alterar.isPending}
                            onChange={() => trocarEntrega(t)} />
                          {t.exige_entrega ? "Sim" : "Não"}
                        </label>
                      </td>
                      <td>
                        <label className="checkbox">
                          <input type="checkbox" checked={t.ativo} disabled={alterar.isPending}
                            onChange={() => alterar.mutate({ tipo: t, dados: { ativo: !t.ativo } })} />
                          {t.ativo ? "Ativo" : "Desativado"}
                        </label>
                      </td>
                      <td className="num">{t.em_uso}</td>
                      <td>
                        <span className="grupo grupo-justo">
                          <button className="btn-icone" aria-label={`Editar ${t.nome}`} onClick={() => setEditando(t)}>
                            <Pencil size={15} />
                          </button>
                          {t.em_uso === 0 && (
                            <button className="btn-icone texto-perigo" aria-label={`Apagar ${t.nome}`}
                              onClick={() => confirm(`Apagar o tipo "${t.nome}"?`) && apagar.mutate(t)}>
                              <Trash2 size={15} />
                            </button>
                          )}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="texto-suave nota">
            <PackageCheck size={14} /> <strong>Exige entrega:</strong> depois da resposta confirmada, o ofício fica
            "Pendente de recebimento" até a entrega (dos itens ou do serviço) ser confirmada. Tipos em uso não podem
            ser apagados, só desativados.
          </p>
        </section>

        <NovoTipo aoCriar={aposMudanca} />
      </div>

      {editando && <ModalEditarTipo tipo={editando} aoFechar={() => setEditando(null)} aoSalvar={aposMudanca} />}
    </>
  );
}

function NovoTipo({ aoCriar }: { aoCriar: () => void }) {
  const avisar = useToast();
  const [nome, setNome] = useState("");
  const [curto, setCurto] = useState("");
  const [entrega, setEntrega] = useState(true);
  const criar = useMutation({
    mutationFn: () => criarTipo({ nome: nome.trim(), nome_curto: curto.trim() || null, exige_entrega: entrega }),
    onSuccess: (t) => {
      aoCriar();
      setNome("");
      setCurto("");
      setEntrega(true);
      avisar(`Tipo ${t.nome} criado.`);
    },
    onError: (e) => avisar(e.message, "erro"),
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    criar.mutate();
  }

  return (
    <section className="painel-bloco">
      <h2>Novo tipo</h2>
      <form className="formulario" onSubmit={enviar}>
        <Campo rotulo="Nome *">
          {(id) => <input id={id} className="input" required minLength={2} maxLength={80} value={nome}
            placeholder="Ex.: Medicamentos" onChange={(e) => setNome(e.target.value)} />}
        </Campo>
        <Campo rotulo="Nome curto" dica="Opcional: usado na lista e nos gráficos quando o nome é longo">
          {(id) => <input id={id} className="input" maxLength={40} value={curto}
            onChange={(e) => setCurto(e.target.value)} />}
        </Campo>
        <label className="checkbox">
          <input type="checkbox" checked={entrega} onChange={(e) => setEntrega(e.target.checked)} />
          Exige confirmação da entrega depois da resposta
        </label>
        <Botao type="submit" carregando={criar.isPending}>
          <Plus size={16} /> Criar tipo
        </Botao>
      </form>
    </section>
  );
}

function ModalEditarTipo({ tipo, aoFechar, aoSalvar }: { tipo: TipoInfo; aoFechar: () => void; aoSalvar: () => void }) {
  const avisar = useToast();
  const [nome, setNome] = useState(tipo.nome);
  const [curto, setCurto] = useState(tipo.nome_curto ?? "");
  const salvar = useMutation({
    mutationFn: () => atualizarTipo(tipo.codigo, { nome: nome.trim(), nome_curto: curto.trim() || null }),
    onSuccess: () => {
      aoSalvar();
      avisar("Tipo atualizado.");
      aoFechar();
    },
    onError: (e) => avisar(e.message, "erro"),
  });
  return (
    <Modal titulo={`Editar tipo ${tipo.nome}`} aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e) => { e.preventDefault(); salvar.mutate(); }}>
        <Campo rotulo="Nome *" dica="Mudar o nome não altera os ofícios: eles passam a mostrar o nome novo">
          {(id) => <input id={id} className="input" required minLength={2} maxLength={80} value={nome}
            onChange={(e) => setNome(e.target.value)} />}
        </Campo>
        <Campo rotulo="Nome curto" dica="Opcional: usado na lista e nos gráficos">
          {(id) => <input id={id} className="input" maxLength={40} value={curto}
            onChange={(e) => setCurto(e.target.value)} />}
        </Campo>
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" carregando={salvar.isPending}>Salvar</Botao>
        </div>
      </form>
    </Modal>
  );
}
