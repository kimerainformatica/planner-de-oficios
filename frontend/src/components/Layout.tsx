import { useQuery } from "@tanstack/react-query";
import { FileSignature, LayoutGrid, Menu, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { exclusoesPendentes, resumoDocumentos } from "../api/endpoints";
import { useVerificacao } from "../pages/Arquivos";
import logo from "../assets/acqua-logo.svg";
import {
  IconeArquivos,
  IconeAtividades,
  IconeExclusao,
  IconeNovoOficio,
  IconeOficios,
  IconePainel,
  IconeSair,
  IconeTipos,
  IconeUsuarios,
  type PropsIcone,
} from "./Icones";
import { SeletorTema } from "./SeletorTema";
import { NomeUnidade } from "./Unidade";
import { useAuth } from "../auth/AuthContext";
import { ROTULO_PERFIL } from "../utils/formato";

type LinkMenu = {
  para: string;
  rotulo: string;
  icone: (p: PropsIcone) => React.ReactNode;
  ativo: boolean;
  contador?: number;
  avisoContador?: string;
};

const IconeDocumentos = ({ tamanho = 20, className }: PropsIcone) => (
  <FileSignature size={tamanho} className={className} aria-hidden />
);

/** "Ana Lima" → "AL" */
function iniciais(nome = ""): string {
  const partes = nome.trim().split(/\s+/).filter(Boolean);
  return ((partes[0]?.[0] ?? "") + (partes.length > 1 ? partes[partes.length - 1][0] : "")).toUpperCase();
}

export function Layout() {
  const { usuario, ehAdmin, ehMaster, modulos, papelNo, sair } = useAuth();
  const [menuAberto, setMenuAberto] = useState(false);
  const { pathname } = useLocation();

  // Aviso de pedidos de exclusão aguardando decisão (só admin/master), atualizado a cada minuto
  const pendentes = useQuery({
    queryKey: ["exclusoes-pendentes"],
    queryFn: exclusoesPendentes,
    enabled: ehAdmin,
    refetchInterval: 60_000,
  });
  const totalPendentes = pendentes.data?.total ?? 0;
  // Integração com o módulo Documentos: atalho para redigir, com os documentos esperando a assinatura de quem está no app
  const usaDocumentos = modulos.includes("DOCUMENTOS");
  const paraAssinar = useQuery({ queryKey: ["documentos-resumo"], queryFn: resumoDocumentos, refetchInterval: 60_000,
    enabled: usaDocumentos }).data?.para_assinar ?? 0;
  // Arquivos que sumiram ou foram alterados (verificação diária): aviso no menu para admin/master
  const problemasArquivos = useVerificacao(ehAdmin).data?.problemas.length ?? 0;

  // "Ofícios" fica ativo na lista e no detalhe, mas não em "Novo ofício".
  const emOficios = pathname.startsWith("/oficios") && pathname !== "/oficios/novo";
  const principais: LinkMenu[] = [
    { para: "/", rotulo: "Painel", icone: IconePainel, ativo: pathname === "/" },
    { para: "/oficios", rotulo: "Ofícios", icone: IconeOficios, ativo: emOficios },
    { para: "/oficios/novo", rotulo: "Novo ofício", icone: IconeNovoOficio, ativo: pathname === "/oficios/novo" },
    ...(usaDocumentos
      ? [{
          para: "/documentos?novo=OFICIO",
          rotulo: "Redigir ofício",
          icone: IconeDocumentos,
          ativo: false,
          contador: paraAssinar,
          avisoContador: "documento(s) aguardando a sua assinatura no módulo Documentos",
        }]
      : []),
    {
      para: "/exclusoes",
      rotulo: ehAdmin ? "Pedidos de exclusão" : "Meus pedidos de exclusão",
      icone: IconeExclusao,
      ativo: pathname === "/exclusoes",
      contador: ehAdmin ? totalPendentes : 0,
    },
    { para: "/atividades", rotulo: "Atividades", icone: IconeAtividades, ativo: pathname === "/atividades" },
  ];
  const administracao: LinkMenu[] = ehAdmin
    ? [
        { para: "/usuarios", rotulo: "Usuários", icone: IconeUsuarios, ativo: pathname === "/usuarios" },
        { para: "/tipos", rotulo: "Tipos de ofício", icone: IconeTipos, ativo: pathname === "/tipos" },
        {
          para: "/arquivos",
          rotulo: "Arquivos",
          icone: IconeArquivos,
          ativo: pathname === "/arquivos",
          contador: problemasArquivos,
          avisoContador: "arquivo(s) com problema",
        },
      ]
    : [];

  const item = ({ para, rotulo, icone: Icone, ativo, contador, avisoContador }: LinkMenu) => (
    <NavLink key={para} to={para} className={`nav-link ${ativo ? "ativo" : ""}`} aria-current={ativo ? "page" : undefined}>
      <span className="nav-ic">
        <Icone />
      </span>
      <span className="nav-rotulo">{rotulo}</span>
      {contador ? (
        <span className="contador" aria-label={`${contador} ${avisoContador ?? "aguardando decisão"}`}>
          {contador}
        </span>
      ) : null}
    </NavLink>
  );

  return (
    <div className="app">
      <aside className={`lateral ${menuAberto ? "aberta" : ""}`}>
        <div className="marca">
          <NavLink to="/" className="marca-link" onClick={() => setMenuAberto(false)}
            aria-label="Planner de Ofícios · Instituto ACQUA, ir para o Painel">
            <img src={logo} alt="Instituto ACQUA" className="marca-logo" />
            <span className="marca-sistema">Planner de Ofícios</span>
            <NomeUnidade className="marca-unidade" />
          </NavLink>
          <button className="btn-icone so-mobile" onClick={() => setMenuAberto((v) => !v)} aria-label="Menu">
            {menuAberto ? <X size={22} /> : <Menu size={22} />}
            {!menuAberto && totalPendentes + problemasArquivos > 0 && <span className="ponto-aviso" aria-hidden />}
          </button>
        </div>

        <nav className="nav" onClick={() => setMenuAberto(false)} aria-label="Menu principal">
          {principais.map(item)}
          {administracao.length > 0 && <span className="nav-grupo">Administração</span>}
          {administracao.map(item)}
          {modulos.length > 1 && (
            <>
              <span className="nav-grupo">Plataforma</span>
              <NavLink to="/modulos" className="nav-link">
                <span className="nav-ic">
                  <LayoutGrid size={19} aria-hidden />
                </span>
                <span className="nav-rotulo">Módulos</span>
              </NavLink>
            </>
          )}
        </nav>

        <div className="lateral-rodape">
          <SeletorTema />
          <div className="usuario-box">
            <span className="avatar" aria-hidden>{iniciais(usuario?.nome)}</span>
            <div>
              <strong>{usuario?.nome}</strong>
              <small className="perfil-linha">
                {ehMaster && <ShieldCheck size={13} />}
                {papelNo("OFICIOS") ? ROTULO_PERFIL[papelNo("OFICIOS")!] : ""}
              </small>
            </div>
            <button className="btn-sair" onClick={sair} title="Sair" aria-label="Sair">
              <IconeSair />
            </button>
          </div>
        </div>
        <svg className="onda-lateral" viewBox="0 0 2880 120" preserveAspectRatio="none" aria-hidden="true">
          <path d="M0 60 C240 20 480 20 720 60 S1200 100 1440 60 S1920 20 2160 60 S2640 100 2880 60 V120 H0Z" />
        </svg>
      </aside>

      <main className="conteudo">
        <Outlet />
      </main>
    </div>
  );
}
