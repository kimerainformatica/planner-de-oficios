import { useQuery } from "@tanstack/react-query";
import {
  BellRing, Building2, CalendarCheck, Columns3, LayoutDashboard, LayoutGrid, ListChecks, LogOut, Menu, PlusCircle, ShieldCheck,
  Users, X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { painelManutencao } from "../api/endpoints";
import logo from "../assets/acqua-logo.svg";
import { useAuth } from "../auth/AuthContext";
import { useAvisos } from "../pages/manutencao/Avisos";
import { ROTULO_PAPEL_MANUTENCAO } from "../utils/manutencao";
import { SeletorTema } from "./SeletorTema";
import { NomeUnidade } from "./Unidade";

type Link = { para: string; rotulo: string; icone: ReactNode; ativo: boolean; contador?: number; aviso?: string };

/**
 * Estrutura do módulo Manutenção Clínica (helpdesk). Para criar uma tela nova do módulo:
 * 1) acrescente a rota em App.tsx, dentro de `/manutencao`; 2) acrescente o link em `links` abaixo.
 */
export function LayoutManutencao() {
  const { usuario, ehMaster, ehGestor, modulos, papelNo, ehAdminNo, sair } = useAuth();
  const { pathname } = useLocation();
  const [menuAberto, setMenuAberto] = useState(false);
  const papel = papelNo("MANUTENCAO");
  const admin = ehAdminNo("MANUTENCAO");
  const podeAbrir = papel === "CLIENTE" || admin;

  // Contador no menu: chamados aguardando diagnóstico (para técnicos e administradores), a cada minuto
  const painel = useQuery({
    queryKey: ["manutencao-painel"], queryFn: painelManutencao, refetchInterval: 60_000,
    enabled: papel === "TECNICO" || admin,
  });
  const aguardando = painel.data?.aguardando_diagnostico ?? 0;
  // Avisos internos (o sistema não envia e-mail): pendências críticas e de atenção de quem está logado
  const pendencias = useAvisos().data?.total ?? 0;

  const emChamados = pathname.startsWith("/manutencao/chamados") && pathname !== "/manutencao/chamados/novo";
  const links: Link[] = [
    // Para o técnico, o painel já é o quadro de acompanhamento
    { para: "/manutencao", rotulo: papel === "TECNICO" ? "Meu painel" : "Painel", icone: <LayoutDashboard size={19} />,
      ativo: pathname === "/manutencao" },
    ...(papel !== "TECNICO"
      ? [{ para: "/manutencao/quadro", rotulo: "Quadro de acompanhamento", icone: <Columns3 size={19} />,
          ativo: pathname === "/manutencao/quadro" }]
      : []),
    { para: "/manutencao/chamados", rotulo: "Chamados", icone: <ListChecks size={19} />, ativo: emChamados,
      contador: aguardando, aviso: "chamado(s) aguardando diagnóstico" },
    ...(podeAbrir
      ? [{ para: "/manutencao/chamados/novo", rotulo: "Abrir chamado", icone: <PlusCircle size={19} />,
          ativo: pathname === "/manutencao/chamados/novo" }]
      : []),
    { para: "/manutencao/preventivas", rotulo: "Preventivas", icone: <CalendarCheck size={19} />,
      ativo: pathname === "/manutencao/preventivas" },
    { para: "/manutencao/avisos", rotulo: "Avisos", icone: <BellRing size={19} />, ativo: pathname === "/manutencao/avisos",
      contador: pendencias, aviso: "pendência(s) para você" },
  ];
  const administracao: Link[] = admin
    ? [{ para: "/manutencao/empresas", rotulo: "Empresas técnicas", icone: <Building2 size={19} />,
        ativo: pathname === "/manutencao/empresas" }]
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
          <NavLink to="/manutencao" className="marca-link" onClick={() => setMenuAberto(false)}
            aria-label="Manutenção Clínica · Instituto ACQUA, ir para o painel">
            <img src={logo} alt="Instituto ACQUA" className="marca-logo" />
            <span className="marca-sistema">Manutenção Clínica</span>
            <NomeUnidade className="marca-unidade" />
          </NavLink>
          <button className="btn-icone so-mobile" onClick={() => setMenuAberto((v) => !v)} aria-label="Menu">
            {menuAberto ? <X size={22} /> : <Menu size={22} />}
            {!menuAberto && aguardando + pendencias > 0 && <span className="ponto-aviso" aria-hidden />}
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
                {papel ? ROTULO_PAPEL_MANUTENCAO[papel] : ""}
                {usuario?.modulos.find((a) => a.modulo === "MANUTENCAO")?.empresa_nome &&
                  ` · ${usuario.modulos.find((a) => a.modulo === "MANUTENCAO")!.empresa_nome}`}
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
