import { useQuery } from "@tanstack/react-query";
import { ArrowRight, FileSignature, FileText, Users, Wrench } from "lucide-react";
import type { ReactNode } from "react";
import { Link, Navigate } from "react-router-dom";
import { listarModulos } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { Carregando, ErroBox } from "../components/ui";
import type { Modulo } from "../types";
import { ROTULO_PERFIL } from "../utils/formato";
import { ROTULO_PAPEL_MANUTENCAO } from "../utils/manutencao";
import { ROTULO_PAPEL_DOCUMENTOS } from "./documentos/comum";

const ICONE: Record<Modulo, ReactNode> = {
  OFICIOS: <FileText size={30} aria-hidden />,
  MANUTENCAO: <Wrench size={30} aria-hidden />,
  DOCUMENTOS: <FileSignature size={30} aria-hidden />,
};

/** Tela inicial depois do login: os módulos que o usuário pode abrir. Com um só módulo, entra direto nele. */
export function Modulos() {
  const { usuario, ehGestor } = useAuth();
  const consulta = useQuery({ queryKey: ["modulos"], queryFn: listarModulos });

  if (consulta.isPending) return <Carregando />;
  if (consulta.isError) return <ErroBox erro={consulta.error} />;

  const modulos = consulta.data;
  if (modulos.length === 1) return <Navigate to={modulos[0].rota} replace />;

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Olá, {usuario?.nome.split(" ")[0]}</h1>
          <p className="texto-suave">
            {modulos.length ? "Escolha o módulo que deseja abrir." : "Você ainda não foi habilitado em nenhum módulo."}
          </p>
        </div>
      </header>

      {modulos.length === 0 ? (
        <div className="aviso-vazio" role="status">
          Peça a um administrador para habilitar o seu acesso a um módulo e entre novamente.
        </div>
      ) : (
        <div className="modulos-grade">
          {modulos.map((m) => (
            <Link key={m.modulo} to={m.rota} className="modulo-cartao">
              <span className="modulo-icone">{ICONE[m.modulo]}</span>
              <span className="modulo-texto">
                <strong>{m.nome}</strong>
                <span className="texto-suave">{m.descricao}</span>
              </span>
              <span className="modulo-rodape">
                <span className={`badge ${m.perfil === "MASTER" ? "badge-master" : m.perfil === "ADMIN" ? "badge-admin" : m.perfil === "TECNICO" ? "badge-tecnico" : "badge-neutro"}`}>
                  {m.modulo === "MANUTENCAO" ? ROTULO_PAPEL_MANUTENCAO[m.perfil]
                    : m.modulo === "DOCUMENTOS" ? ROTULO_PAPEL_DOCUMENTOS[m.perfil] : ROTULO_PERFIL[m.perfil]}
                </span>
                <ArrowRight size={20} className="modulo-seta" aria-hidden />
              </span>
            </Link>
          ))}
          {ehGestor && (
            <Link to="/usuarios" className="modulo-cartao modulo-cartao-secundario">
              <span className="modulo-icone">
                <Users size={30} aria-hidden />
              </span>
              <span className="modulo-texto">
                <strong>Usuários</strong>
                <span className="texto-suave">Cadastro e acesso de cada pessoa aos módulos.</span>
              </span>
              <span className="modulo-rodape">
                <ArrowRight size={20} className="modulo-seta" aria-hidden />
              </span>
            </Link>
          )}
        </div>
      )}
    </>
  );
}
