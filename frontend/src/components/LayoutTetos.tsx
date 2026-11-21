import { useQuery } from "@tanstack/react-query";
import {
  Building, Gauge, LayoutGrid, ListPlus, LogOut, Menu, ReceiptText, ShieldCheck, Tags, Users, X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { painelTetos } from "../api/endpoints";
import logo from "../assets/acqua-logo.svg";
import { useAuth } from "../auth/AuthContext";
import { ROTULO_PAPEL_TETOS } from "../utils/tetos";
import { SeletorTema } from "./SeletorTema";
import { NomeUnidade } from "./Unidade";

type Link = { para: string; rotulo: string; icone: ReactNode; ativo: boolean; contador?: number; aviso?: string };

/**
 * Estrutura do módulo Controle de Tetos. Para criar uma tela nova do módulo:
 * 1) acrescente a rota em App.tsx, dentro de `/tetos`; 2) acrescente o link em `links` abaixo.
 */
export function LayoutTetos() {
  const { usuario, ehMaster, ehGestor, modulos, papelNo, ehAdminNo, sair } = useAuth();
  const { pathname } = useLocation();
  const [menuAberto, setMenuAberto] = useState(false);
  const papel = papelNo("TETOS");
  const admin = ehAdminNo("TETOS");
  const setor = usuario?.modulos.find((a) => a.modulo === "TETOS")?.setor_nome;

  // Contador no menu: tipos com o mês acima do teto (atualiza a cada 5 minutos)
  const painel = useQuery({ queryKey: ["tetos-painel", "menu"], queryFn: () => painelTetos(), refetchInterval: 300_000,
    enabled: admin || !!setor });
  const estourados = painel.data?.estourados ?? 0;

  const links: Link[] = [
    { para: "/tetos", rotulo: "Painel", icone: <Gauge size={19} />, ativo: pathname === "/tetos" || pathname.startsWith("/tetos/tipo/"),
      contador: estourados, aviso: "teto(s) estourado(s) no mês" },
    { para: "/tetos/lancamentos", rotulo: "Lançamentos", icone: <ReceiptText size={19} />,
      ativo: pathname === "/tetos/lancamentos" },
    { para: "/tetos/lancamentos?novo=1", rotulo: "Lançar gasto", icone: <ListPlus size={19} />, ativo: false },
  ];
  const administracao: Link[] = admin
    ? [
        { para: "/tetos/tipos", rotulo: "Tipos de teto", icone: <Tags size={19} />, ativo: pathname === "/tetos/tipos" },
        { para: "/tetos/setores", rotulo: "Setores", icone: <Building size={19} />, ativo: pathname === "/tetos/setores" },
      ]
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
          <NavLink to="/tetos" className="marca-link" onClick={() => setMenuAberto(false)}
            aria-label="Controle de Tetos · Instituto ACQUA, ir para o painel">
            <img src={logo} alt="Instituto ACQUA" className="marca-logo" />
            <span className="marca-sistema">Controle de Tetos</span>
            <NomeUnidade className="marca-unidade" />
          </NavLink>
          <button className="btn-icone so-mobile" onClick={() => setMenuAberto((v) => !v)} aria-label="Menu">
            {menuAberto ? <X size={22} /> : <Menu size={22} />}
            {!menuAberto && estourados > 0 && <span className="ponto-aviso" aria-hidden />}
          </button>
        </div>

        <nav className="nav" onClick={() => setMenuAberto(false)} aria-label="Menu principal">
          {links.map(item)}
          {administracao.length > 0 && <span className="nav-grupo">Administração</span>}
          {administracao.map(item)}
          {(modulos.length > 1 || ehGestor) && <span className="nav-grupo">Plataforma</span>}
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
                {papel ? ROTULO_PAPEL_TETOS[papel] : ""}
                {setor && ` · ${setor}`}
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
