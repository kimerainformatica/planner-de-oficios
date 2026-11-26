import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderPlus, Pencil, Power, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { atualizarPasta, criarPasta, excluirPasta, listarPastas } from "../../api/endpoints";
import { useToast } from "../../components/Toast";
import { Botao, Campo, Carregando, ErroBox, Modal } from "../../components/ui";
import type { PastaDocumento } from "../../types";

/** Pastas para organizar os documentos (só o administrador do módulo Documentos cria e muda). */
export function Pastas() {
  const qc = useQueryClient();
  const avisar = useToast();
  const consulta = useQuery({ queryKey: ["pastas-documento"], queryFn: listarPastas });
  const [nome, setNome] = useState("");
  const [descricao, setDescricao] = useState("");
  const [editando, setEditando] = useState<PastaDocumento | null>(null);
  const depois = () => {
    qc.invalidateQueries({ queryKey: ["pastas-documento"] });
    qc.invalidateQueries({ queryKey: ["documentos"] });
    qc.invalidateQueries({ queryKey: ["documento"] });
  };
  const criar = useMutation({
    mutationFn: () => criarPasta({ nome: nome.trim(), descricao: descricao.trim() || null }),
    onSuccess: (p) => { depois(); setNome(""); setDescricao(""); avisar(`Pasta ${p.nome} criada.`); },
  });
  const alternar = useMutation({
    mutationFn: (p: PastaDocumento) => atualizarPasta(p.id, { ativo: !p.ativo }),
    onSuccess: (p) => { depois(); avisar(`Pasta ${p.nome} ${p.ativo ? "reativada" : "desativada"}.`); },
    onError: (e) => avisar(e.message, "erro"),
  });
  const apagar = useMutation({
    mutationFn: (p: PastaDocumento) => excluirPasta(p.id),
    onSuccess: () => { depois(); avisar("Pasta apagada."); },
    onError: (e) => avisar(e.message, "erro"),
  });

  function confirmarApagar(p: PastaDocumento) {
    const aviso = p.documentos ? ` Os ${p.documentos} documento(s) dela ficam sem pasta (nenhum é apagado).` : "";
    if (confirm(`Apagar a pasta ${p.nome}?${aviso}`)) apagar.mutate(p);
  }

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Pastas</h1>
          <p className="texto-suave">
            Para organizar os documentos por setor, assunto ou projeto. Cada documento fica em uma pasta ou em nenhuma; a
            pasta não muda quem pode ver o documento. Desativar tira a pasta da escolha sem mexer nos documentos dela.
          </p>
        </div>
      </header>

      <div className="duas-colunas colunas-pastas">
        <section className="painel-bloco">
          <h2>Nova pasta</h2>
          <form className="formulario" onSubmit={(e: FormEvent) => { e.preventDefault(); criar.mutate(); }}>
            <Campo rotulo="Nome *">
              {(i) => <input id={i} className="input" required minLength={2} maxLength={80} value={nome}
                placeholder="Ex.: Recursos Humanos" onChange={(e) => setNome(e.target.value)} />}
            </Campo>
            <Campo rotulo="Descrição">
              {(i) => <input id={i} className="input" maxLength={200} value={descricao} onChange={(e) => setDescricao(e.target.value)} />}
            </Campo>
            {criar.isError && <div className="alerta-erro" role="alert">{criar.error.message}</div>}
            <div className="acoes-form">
              <Botao type="submit" carregando={criar.isPending} disabled={nome.trim().length < 2}>
                <FolderPlus size={16} /> Criar pasta
              </Botao>
            </div>
          </form>
        </section>

        <section className="painel-bloco">
          <h2>Pastas cadastradas</h2>
          {consulta.isPending ? <Carregando /> : consulta.isError ? <ErroBox erro={consulta.error} /> : consulta.data.length === 0 ? (
            <p className="texto-suave">Nenhuma pasta ainda.</p>
          ) : (
            <div className="tabela-mini-box">
              <table className="tabela tabela-pastas">
                <thead>
                  <tr>
                    <th>Pasta</th>
                    <th className="num">Documentos</th>
                    <th>Situação</th>
                    <th aria-label="Ações" />
                  </tr>
                </thead>
                <tbody>
                  {consulta.data.map((p) => (
                    <tr key={p.id} className={p.ativo ? "" : "linha-inativa"}>
                      <td>
                        <strong>{p.nome}</strong>
                        {p.descricao && <small className="celula-sub">{p.descricao}</small>}
                      </td>
                      <td className="num">
                        {p.documentos ? <Link className="link" to={`/documentos?pasta=${p.id}`}>{p.documentos}</Link> : 0}
                      </td>
                      <td>{p.ativo ? "Ativa" : "Desativada"}</td>
                      <td>
                        <span className="grupo grupo-justo">
                          <button className="btn-icone" aria-label={`Renomear ${p.nome}`} title="Renomear" onClick={() => setEditando(p)}>
                            <Pencil size={15} />
                          </button>
                          <button className="btn-icone" aria-label={`${p.ativo ? "Desativar" : "Reativar"} ${p.nome}`}
                            title={p.ativo ? "Desativar" : "Reativar"} disabled={alternar.isPending} onClick={() => alternar.mutate(p)}>
                            <Power size={15} />
                          </button>
                          <button className="btn-icone btn-perigo" aria-label={`Apagar ${p.nome}`} title="Apagar"
                            disabled={apagar.isPending} onClick={() => confirmarApagar(p)}>
                            <Trash2 size={15} />
                          </button>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {editando && (
        <ModalPasta pasta={editando} aoFechar={() => setEditando(null)}
          aoSalvar={(p) => { depois(); setEditando(null); avisar(`Pasta ${p.nome} salva.`); }} />
      )}
    </>
  );
}

function ModalPasta({ pasta, aoFechar, aoSalvar }: {
  pasta: PastaDocumento; aoFechar: () => void; aoSalvar: (p: PastaDocumento) => void;
}) {
  const [nome, setNome] = useState(pasta.nome);
  const [descricao, setDescricao] = useState(pasta.descricao ?? "");
  const salvar = useMutation({
    mutationFn: () => atualizarPasta(pasta.id, { nome: nome.trim(), descricao: descricao.trim() || null }),
    onSuccess: aoSalvar,
  });
  return (
    <Modal titulo={`Pasta ${pasta.nome}`} aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e) => { e.preventDefault(); salvar.mutate(); }}>
        <Campo rotulo="Nome *">
          {(i) => <input id={i} className="input" required minLength={2} maxLength={80} autoFocus value={nome}
            onChange={(e) => setNome(e.target.value)} />}
        </Campo>
        <Campo rotulo="Descrição">
          {(i) => <input id={i} className="input" maxLength={200} value={descricao} onChange={(e) => setDescricao(e.target.value)} />}
        </Campo>
        {salvar.isError && <div className="alerta-erro" role="alert">{salvar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Voltar</button>
          <Botao type="submit" carregando={salvar.isPending} disabled={nome.trim().length < 2}>Salvar</Botao>
        </div>
      </form>
    </Modal>
  );
}
