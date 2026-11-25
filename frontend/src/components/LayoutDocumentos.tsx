import { useQuery } from "@tanstack/react-query";
import {
  FilePen, FileSignature, FileText, LayoutGrid, LogOut, Menu, ShieldCheck, Signature, Stamp, Users, X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { resumoDocumentos } from "../api/endpoints";
import logo from "../assets/acqua-logo.svg";
import { useAuth } from "../auth/AuthContext";
import { ROTULO_PAPEL_DOCUMENTOS } from "../pages/documentos/comum";
import { SeletorTema } from "./SeletorTema";
import { NomeUnidade } from "./Unidade";

type Link = { para: string; rotulo: string; icone: ReactNode; ativo: boolean; contador?: number; aviso?: string };

/**
 * Estrutura do módulo Documentos (ofícios e memorandos no modelo da unidade). Para criar uma tela nova:
 * 1) acrescente a rota em App.tsx, dentro de `/documentos`; 2) acrescente o link em `links` abaixo.
 */
export function LayoutDocumentos() {
  const { usuario, ehMaster, ehGestor, modulos, papelNo, ehAdminNo, sair } = useAuth();
  const { pathname, search } = useLocation();
  const [menuAberto, setMenuAberto] = useState(false);
  const papel = papelNo("DOCUMENTOS");
  const admin = ehAdminNo("DOCUMENTOS");
  const usaPlanner = modulos.includes("OFICIOS");

  // Documentos emitidos esperando a assinatura de quem está no app (atualiza a cada minuto)
  const paraAssinar = useQuery({ queryKey: ["documentos-resumo"], queryFn: resumoDocumentos, refetchInterval: 60_000 })
    .data?.para_assinar ?? 0;
  const naLista = pathname === "/documentos";
  const escopo = new URLSearchParams(search).get("escopo");

  const links: Link[] = [
    { para: "/documentos", rotulo: "Documentos", icone: <FileSignature size={19} />,
      ativo: (naLista && escopo !== "assinar") || /^\/documentos\/\d+/.test(pathname) },
    { para: "/documentos?escopo=assinar", rotulo: "Para assinar", icone: <Signature size={19} />,
      ativo: naLista && escopo === "assinar", contador: paraAssinar, aviso: "documento(s) aguardando a sua assinatura" },
    { para: "/documentos?novo=OFICIO", rotulo: "Novo ofício", icone: <FilePen size={19} />, ativo: false },
    { para: "/documentos?novo=MEMORANDO", rotulo: "Novo memorando", icone: <FileText size={19} />, ativo: false },
  ];
  const administracao: Link[] = admin
    ? [{ para: "/documentos/timbrado", rotulo: "Timbrado", icone: <Stamp size={19} />, ativo: pathname === "/documentos/timbrado" }]
    : [];

  const item = (l: Link) => (
    <NavLink key={l.para} to={l.para} end className={`nav-link ${l.ativo ? "ativo" : ""}`} aria-current={l.ativo ? "page" : undefined}>
      <span className="nav-ic" aria-hidden>{l.icone}</span>
      <span className="nav-rotulo">{l.rotulo}</span>
      {l.contador ? <span className="contador" aria-label={`${l.contador} ${l.aviso ?? ""}`}>{l.contador}</span> : null}
    </NavLink>
  );

  return (
    <div className="app">
      <aside className={`lateral ${menuAberto ? "aberta" : ""}`}>
        <div className="marca">
          <NavLink to="/documentos" className="marca-link" onClick={() => setMenuAberto(false)}
            aria-label="Documentos · Instituto ACQUA, ir para a lista">
            <img src={logo} alt="Instituto ACQUA" className="marca-logo" />
            <span className="marca-sistema">Documentos</span>
            <NomeUnidade className="marca-unidade" />
          </NavLink>
          <button className="btn-icone so-mobile" onClick={() => setMenuAberto((v) => !v)} aria-label="Menu">
            {menuAberto ? <X size={22} /> : <Menu size={22} />}
            {!menuAberto && paraAssinar > 0 && <span className="ponto-aviso" aria-hidden />}
          </button>
        </div>

        <nav className="nav" onClick={() => setMenuAberto(false)} aria-label="Menu principal">
          {links.map(item)}
          {administracao.length > 0 && <span className="nav-grupo">Administração</span>}
          {administracao.map(item)}
          {(modulos.length > 1 || ehGestor) && <span className="nav-grupo">Plataforma</span>}
          {usaPlanner && (
            <NavLink to="/oficios" className="nav-link">
              <span className="nav-ic"><FileText size={19} aria-hidden /></span>
              <span className="nav-rotulo">Planner de Ofícios</span>
            </NavLink>
          )}
          {modulos.length > 1 && (
            <NavLink to="/modulos" className="nav-link">
              <span className="nav-ic"><LayoutGrid size={19} aria-hidden /></span>
              <span className="nav-rotulo">Módulos</span>
            </NavLink>
          )}
          {ehGestor && (
            <NavLink to="/usuarios" className="nav-link">
              <span className="nav-ic"><Users size={19} aria-hidden /></span>
              <span className="nav-rotulo">Usuários</span>
            </NavLink>
          )}
        </nav>

        <div className="lateral-rodape">
          <SeletorTema />
          <div className="usuario-box">
            <span className="avatar" aria-hidden>
              {(usuario?.nome ?? "").trim().slice(0, 2).toUpperCase()}
            </span>
            <div>
              <strong>{usuario?.nome}</strong>
              <small className="perfil-linha">
                {ehMaster && <ShieldCheck size={13} aria-hidden />}
                {papel ? ROTULO_PAPEL_DOCUMENTOS[papel] : ""}
                {usuario?.cargo && ` · ${usuario.cargo}`}
              </small>
            </div>
            <button className="btn-sair" onClick={sair} title="Sair" aria-label="Sair">
              <LogOut size={18} aria-hidden />
            </button>
          </div>
        </div>
      </aside>

      <main className="conteudo">
        <Outlet />
      </main>
    </div>
  );
}
