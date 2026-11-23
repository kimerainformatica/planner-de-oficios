import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, UserPlus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { atualizarUsuario, criarUsuario, listarEmpresas, listarUsuarios } from "../api/endpoints";
import { ROTULO_PAPEL_MANUTENCAO } from "../utils/manutencao";
import { ROTULO_PAPEL_DOCUMENTOS } from "./documentos/comum";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { Botao, Campo, Carregando, ErroBox, Modal } from "../components/ui";
import type { AcessoModulo, Modulo, Perfil, Usuario } from "../types";
import { ROTULO_PERFIL } from "../utils/formato";
import { modulosQueAdministra, MODULOS, podeEditar, podeEditarAcesso, podeGerirConta } from "../utils/modulos";

const CLASSE_PERFIL: Record<Perfil, string> = {
  MASTER: "badge-master", ADMIN: "badge-admin", CLIENTE: "badge-neutro", TECNICO: "badge-tecnico",
};

type Escolha = "NENHUM" | "CLIENTE" | "ADMIN" | "TECNICO";

/** Nome do papel no módulo: na Manutenção Clínica o cliente é o "operacional". */
function rotuloPapel(modulo: Modulo, perfil: Perfil): string {
  if (modulo === "MANUTENCAO") return ROTULO_PAPEL_MANUTENCAO[perfil];
  if (modulo === "DOCUMENTOS") return ROTULO_PAPEL_DOCUMENTOS[perfil];
  return ROTULO_PERFIL[perfil];
}

export function Usuarios() {
  const { usuario: eu, ehMaster } = useAuth();
  const consulta = useQuery({ queryKey: ["usuarios"], queryFn: () => listarUsuarios() });
  const [editando, setEditando] = useState<Usuario | "novo" | null>(null);

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Usuários</h1>
          <p className="texto-suave">
            {ehMaster
              ? "Como MASTER, você gerencia todas as contas e o acesso aos dois módulos, inclusive o dos administradores."
              : "Você habilita pessoas nos módulos que administra. Administradores e masters são geridos pelo MASTER."}
          </p>
        </div>
        <button className="btn btn-primario" onClick={() => setEditando("novo")}>
          <UserPlus size={18} /> Novo usuário
        </button>
      </header>

      {consulta.isPending ? (
        <Carregando />
      ) : consulta.isError ? (
        <ErroBox erro={consulta.error} />
      ) : (
        <div className="tabela-box">
          <table className="tabela">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Login</th>
                <th>Acesso aos módulos</th>
                <th>Situação</th>
                <th aria-label="Ações" />
              </tr>
            </thead>
            <tbody>
              {consulta.data.map((u) => (
                <tr key={u.id} className={u.ativo ? "" : "linha-inativa"}>
                  <td>
                    {u.nome}
                    {u.id === eu?.id && <small className="texto-suave"> (você)</small>}
                  </td>
                  <td>{u.login}</td>
                  <td>
                    <div className="acessos">
                      {u.perfil === "MASTER" ? (
                        <span className="badge badge-master">Master · todos os módulos</span>
                      ) : u.modulos.length === 0 ? (
                        <span className="texto-suave">Sem acesso</span>
                      ) : (
                        MODULOS.filter((m) => u.modulos.some((a) => a.modulo === m.modulo)).map((m) => {
                          const a = u.modulos.find((x) => x.modulo === m.modulo)!;
                          return (
                            <span key={m.modulo} className={`badge ${CLASSE_PERFIL[a.perfil]}`}>
                              {m.nome} · {rotuloPapel(m.modulo, a.perfil)}
                              {a.empresa_nome && ` · ${a.empresa_nome}`}
                            </span>
                          );
                        })
                      )}
                    </div>
                  </td>
                  <td>{u.ativo ? "Ativo" : "Inativo"}</td>
                  <td className="num">
                    <button className="btn btn-fantasma btn-pequeno" onClick={() => setEditando(u)}
                      disabled={!podeEditar(eu, u)}
                      title={podeEditar(eu, u) ? undefined : "Só o MASTER altera esta conta"}>
                      <Pencil size={15} /> Editar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editando && (
        <ModalUsuario usuario={editando === "novo" ? null : editando} aoFechar={() => setEditando(null)} />
      )}
    </>
  );
}

function escolhaAtual(u: Usuario | null, modulo: Modulo): Escolha {
  return (u?.modulos.find((a) => a.modulo === modulo)?.perfil as Escolha | undefined) ?? "NENHUM";
}

function ModalUsuario({ usuario, aoFechar }: { usuario: Usuario | null; aoFechar: () => void }) {
  const { usuario: eu, ehMaster } = useAuth();
  const avisar = useToast();
  const queryClient = useQueryClient();
  const ehEu = usuario !== null && usuario.id === eu?.id;
  const meus = modulosQueAdministra(eu);
  // Sem permissão para mexer na conta (nome, login, senha, situação): só o acesso aos módulos
  const contaLiberada = usuario === null || podeGerirConta(eu, usuario);
  const acessoLiberado = usuario === null ? true : podeEditarAcesso(eu, usuario);

  const [nome, setNome] = useState(usuario?.nome ?? "");
  const [login, setLogin] = useState(usuario?.login ?? "");
  const [cargo, setCargo] = useState(usuario?.cargo ?? "");
  const [matricula, setMatricula] = useState(usuario?.matricula ?? "");
  const [senha, setSenha] = useState("");
  const [ativo, setAtivo] = useState(usuario?.ativo ?? true);
  const [master, setMaster] = useState(usuario?.perfil === "MASTER");
  const [acesso, setAcesso] = useState<Record<Modulo, Escolha>>(() => {
    const base = Object.fromEntries(MODULOS.map((m) => [m.modulo, escolhaAtual(usuario, m.modulo)])) as Record<Modulo, Escolha>;
    // Novo usuário criado por um administrador já começa habilitado no primeiro módulo dele
    if (!usuario && !ehMaster && meus.length) base[meus[0]] = "CLIENTE";
    return base;
  });
  // Regra: todo operacional (cliente ou admin) da Manutenção também usa o Planner de Ofícios
  const operacional = acesso.MANUTENCAO === "CLIENTE" || acesso.MANUTENCAO === "ADMIN";
  function mudarAcesso(modulo: Modulo, valor: Escolha) {
    setAcesso((a) => {
      const novo = { ...a, [modulo]: valor };
      const virouOperacional = modulo === "MANUTENCAO" && (valor === "CLIENTE" || valor === "ADMIN");
      if (virouOperacional && novo.OFICIOS === "NENHUM" && meus.includes("OFICIOS")) novo.OFICIOS = "CLIENTE";
      return novo;
    });
  }
  // Empresa do técnico (só na Manutenção Clínica)
  const [empresaTecnico, setEmpresaTecnico] = useState<number | "">(
    usuario?.modulos.find((a) => a.modulo === "MANUTENCAO")?.empresa_id ?? "",
  );
  const empresas = useQuery({
    queryKey: ["empresas-manutencao"],
    queryFn: () => listarEmpresas(),
    enabled: meus.includes("MANUTENCAO"),
  });

  // Só os módulos que o editor administra podem ser alterados; o administrador de um módulo só o MASTER troca
  const editavel = (m: Modulo) => acessoLiberado && !ehEu && !master && meus.includes(m) && (ehMaster || escolhaAtual(usuario, m) !== "ADMIN");

  const salvar = useMutation({
    mutationFn: () => {
      const modulos: AcessoModulo[] = MODULOS.filter((m) => meus.includes(m.modulo) && acesso[m.modulo] !== "NENHUM").map(
        (m) => ({
          modulo: m.modulo,
          perfil: acesso[m.modulo] as Perfil,
          ...(acesso[m.modulo] === "TECNICO" ? { empresa_id: empresaTecnico === "" ? null : empresaTecnico } : {}),
        }),
      );
      if (!usuario) {
        return criarUsuario({ nome: nome.trim(), login: login.trim(), senha, master, modulos,
          cargo: cargo.trim(), matricula: matricula.trim() });
      }
      return atualizarUsuario(usuario.id, {
        ...(contaLiberada
          ? {
              nome: nome.trim(),
              ...(cargo.trim() !== (usuario.cargo ?? "") ? { cargo: cargo.trim() } : {}),
              ...(matricula.trim() !== (usuario.matricula ?? "") ? { matricula: matricula.trim() } : {}),
              ...(login.trim() !== usuario.login ? { login: login.trim() } : {}),
              ...(senha ? { senha } : {}),
              ...(ehEu ? {} : { ativo }),
            }
          : {}),
        ...(ehMaster && !ehEu && master !== (usuario.perfil === "MASTER") ? { master } : {}),
        ...(acessoLiberado && !ehEu && !master ? { modulos } : {}),
      });
    },
    onSuccess: (u) => {
      queryClient.invalidateQueries({ queryKey: ["usuarios"] });
      avisar(usuario ? `Usuário ${u.nome} atualizado.` : `Usuário ${u.nome} criado.`);
      aoFechar();
    },
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    if (!usuario && !ehMaster && !MODULOS.some((m) => meus.includes(m.modulo) && acesso[m.modulo] !== "NENHUM")) {
      salvar.reset();
      avisar("Habilite o usuário em pelo menos um módulo.");
      return;
    }
    salvar.mutate();
  }

  return (
    <Modal titulo={usuario ? `Editar ${usuario.nome}` : "Novo usuário"} aoFechar={aoFechar}>
      <form className="formulario" onSubmit={enviar}>
        {!contaLiberada && (
          <div className="alerta-info" role="note">
            <span>
              Esta conta também usa módulos que você não administra (ou é de um administrador): você altera só o acesso aos
              seus módulos.
            </span>
          </div>
        )}
        <Campo rotulo="Nome *">
          {(id) => <input id={id} className="input" required maxLength={120} value={nome} autoFocus disabled={!contaLiberada}
            onChange={(e) => setNome(e.target.value)} />}
        </Campo>
        <div className="grade-2">
          <Campo rotulo="Cargo" dica="Sai no bloco de assinatura dos ofícios e memorandos.">
            {(id) => <input id={id} className="input" maxLength={120} value={cargo} disabled={!contaLiberada}
              onChange={(e) => setCargo(e.target.value)} />}
          </Campo>
          <Campo rotulo="Matrícula / ID">
            {(id) => <input id={id} className="input" maxLength={30} value={matricula} disabled={!contaLiberada}
              onChange={(e) => setMatricula(e.target.value)} />}
          </Campo>
        </div>
        <Campo rotulo="Login *"
          dica={usuario ? "Usado para entrar no sistema. Se mudar, avise o usuário (a senha continua a mesma)." : "Letras, números, ponto, hífen ou _"}>
          {(id) => <input id={id} className="input" required minLength={3} maxLength={60} pattern="[A-Za-z0-9._\-]+"
            value={login} disabled={!contaLiberada} onChange={(e) => setLogin(e.target.value)} />}
        </Campo>
        <Campo rotulo={usuario ? "Nova senha" : "Senha *"} dica={usuario ? "Deixe em branco para manter a atual." : "Mínimo de 8 caracteres."}>
          {(id) => <input id={id} className="input" type="password" autoComplete="new-password" minLength={8}
            required={!usuario} value={senha} disabled={!contaLiberada} onChange={(e) => setSenha(e.target.value)} />}
        </Campo>

        <fieldset className="acesso-modulos">
          <legend>Acesso aos módulos</legend>
          {ehMaster && (
            <label className="checkbox">
              <input type="checkbox" checked={master} disabled={ehEu} onChange={(e) => setMaster(e.target.checked)} />
              Master: acesso total a todos os módulos e gestão de administradores
            </label>
          )}
          {master ? (
            <p className="texto-suave">O master entra em todos os módulos como administrador geral.</p>
          ) : (
            MODULOS.map((m) => (
              <Campo key={m.modulo} rotulo={m.nome}
                dica={
                  ehEu ? "Você não pode mudar o próprio acesso."
                    : m.modulo === "OFICIOS" && operacional && acesso.OFICIOS === "NENHUM"
                      ? "O operacional da Manutenção recebe acesso de cliente ao Planner automaticamente."
                    : m.modulo === "OFICIOS" && operacional
                      ? "Todo operacional da Manutenção usa o Planner (cliente ou administrador)."
                    : !meus.includes(m.modulo) ? "Você não administra este módulo."
                    : !editavel(m.modulo) ? "Só o MASTER altera o acesso de administradores."
                    : undefined
                }>
                {(id) => (
                  <>
                    <select id={id} className="input" value={acesso[m.modulo]} disabled={!editavel(m.modulo)}
                      onChange={(e) => mudarAcesso(m.modulo, e.target.value as Escolha)}>
                      {/* operacional da Manutenção não fica sem o Planner */}
                      {!(m.modulo === "OFICIOS" && operacional && acesso.OFICIOS !== "NENHUM") && (
                        <option value="NENHUM">Sem acesso</option>
                      )}
                      {m.modulo === "MANUTENCAO" ? (
                        <>
                          <option value="CLIENTE">Operacional (abre e acompanha os chamados)</option>
                          <option value="TECNICO">Técnico (atende os chamados de uma empresa)</option>
                        </>
                      ) : m.modulo === "DOCUMENTOS" ? (
                        <option value="CLIENTE">Redator (redige e assina ofícios e memorandos)</option>
                      ) : (
                        <option value="CLIENTE">Cliente</option>
                      )}
                      {(ehMaster || acesso[m.modulo] === "ADMIN") && <option value="ADMIN">Administrador</option>}
                    </select>
                    {m.modulo === "MANUTENCAO" && acesso.MANUTENCAO === "TECNICO" && (
                      <select className="input" aria-label="Empresa do técnico" required disabled={!editavel(m.modulo)}
                        value={empresaTecnico} onChange={(e) => setEmpresaTecnico(e.target.value ? Number(e.target.value) : "")}>
                        <option value="">Empresa do técnico…</option>
                        {(empresas.data ?? [])
                          .filter((x) => x.ativo || x.id === empresaTecnico)
                          .map((x) => <option key={x.id} value={x.id}>{x.nome}</option>)}
                        {!empresas.data && empresaTecnico !== "" && (
                          <option value={empresaTecnico}>
                            {usuario?.modulos.find((a) => a.modulo === "MANUTENCAO")?.empresa_nome ?? "Empresa atual"}
                          </option>
                        )}
                      </select>
                    )}
                  </>
                )}
              </Campo>
            ))
          )}
        </fieldset>

        {usuario && !ehEu && contaLiberada && (
          <label className="checkbox">
            <input type="checkbox" checked={ativo} onChange={(e) => setAtivo(e.target.checked)} />
            Usuário ativo (desmarque para bloquear o acesso)
          </label>
        )}
        {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" carregando={salvar.isPending}>{usuario ? "Salvar" : "Criar usuário"}</Botao>
        </div>
      </form>
    </Modal>
  );
}
