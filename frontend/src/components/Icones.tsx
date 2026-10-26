// Ícones próprios do Planner (família "Correnteza"): traço 1,75 e um detalhe na cor da marca (.ac / .acf)
// que se mexe quando o mouse passa sobre o link ou botão onde o ícone está (animações em styles/icones.css).
import type { ReactNode } from "react";

export type PropsIcone = { tamanho?: number; className?: string };

function Svg({ nome, tamanho = 20, className = "", children }: PropsIcone & { nome: string; children: ReactNode }) {
  return (
    <svg className={`ic i-${nome} ${className}`} width={tamanho} height={tamanho} viewBox="0 0 24 24" aria-hidden="true"
      focusable="false">
      {children}
    </svg>
  );
}

const FOLHA = "M7 3.5h7l4.5 4.5v11A1.5 1.5 0 0 1 17 20.5H7A1.5 1.5 0 0 1 5.5 19V5A1.5 1.5 0 0 1 7 3.5z";
const FOLHA_RECORTADA = "M12.5 20.5H7A1.5 1.5 0 0 1 5.5 19V5A1.5 1.5 0 0 1 7 3.5h7l4.5 4.5v3.5";

export const IconePainel = (p: PropsIcone) => (
  <Svg nome="painel" {...p}>
    <rect className="mv" x="3.5" y="3.5" width="7" height="9" rx="2" />
    <rect className="mv" x="13.5" y="3.5" width="7" height="5" rx="2" />
    <rect className="mv ac" x="13.5" y="11.5" width="7" height="9" rx="2" />
    <rect className="mv" x="3.5" y="15.5" width="7" height="5" rx="2" />
  </Svg>
);

export const IconeOficios = (p: PropsIcone) => (
  <Svg nome="doc" {...p}>
    <path d={FOLHA} />
    <path d="M14 3.5V8h4.5" />
    <path className="linha ac" d="M8.5 12.5h7" />
    <path className="linha ac" d="M8.5 16h4.5" />
  </Svg>
);

export const IconeNovoOficio = (p: PropsIcone) => (
  <Svg nome="novo" {...p}>
    <path d={FOLHA_RECORTADA} />
    <path d="M14 3.5V8h4.5" />
    <g className="mais mv">
      <circle className="acf" cx="17.5" cy="17.5" r="4.5" />
      <path className="contra" d="M17.5 15.5v4M15.5 17.5h4" />
    </g>
  </Svg>
);

export const IconeExclusao = (p: PropsIcone) => (
  <Svg nome="excluir" {...p}>
    <path d={FOLHA_RECORTADA} />
    <path d="M14 3.5V8h4.5" />
    <g className="mv">
      <circle className="perigo-f" cx="17.5" cy="17.5" r="4.5" />
      <path className="perigo-x" d="M16 16l3 3M19 16l-3 3" />
    </g>
  </Svg>
);

export const IconeAtividades = (p: PropsIcone) => (
  <Svg nome="hist" {...p}>
    <g className="volta">
      <path d="M4.2 13.5A8 8 0 1 0 6 6.6" />
      <path d="M3.8 4v3.6h3.6" />
    </g>
    <path className="ponteiro ac" d="M12 8v4.2l2.8 1.8" />
  </Svg>
);

export const IconeUsuarios = (p: PropsIcone) => (
  <Svg nome="users" {...p}>
    <circle cx="9" cy="8.5" r="3.3" />
    <path d="M3 19.5a6 6 0 0 1 12 0" />
    <g className="p2">
      <circle className="ac" cx="16.8" cy="9.5" r="2.6" />
      <path className="ac" d="M16 14.3a4.8 4.8 0 0 1 5 5.2" />
    </g>
  </Svg>
);

export const IconeFeriados = (p: PropsIcone) => (
  <Svg nome="feriado" {...p}>
    <rect x="3.5" y="5.5" width="17" height="15" rx="2.5" />
    <path d="M3.5 10h17" />
    <path className="argola mv" d="M8 3.5v3.5" />
    <path className="argola mv" d="M16 3.5v3.5" />
    <g className="sol mv">
      <circle className="acf" cx="12" cy="15.2" r="2" />
      <path className="ac" d="M12 11.9v.6M12 17.9v.6M8.7 15.2h.6M14.7 15.2h.6" />
    </g>
  </Svg>
);

export const IconeTipos = (p: PropsIcone) => (
  <Svg nome="tag" {...p}>
    <g className="etiqueta">
      <path d="M3.5 11.4V5A1.5 1.5 0 0 1 5 3.5h6.4a1.5 1.5 0 0 1 1.06.44l7.6 7.6a1.5 1.5 0 0 1 0 2.12l-6.4 6.4a1.5 1.5 0 0 1-2.12 0l-7.6-7.6A1.5 1.5 0 0 1 3.5 11.4z" />
      <circle className="acf" cx="8" cy="8" r="1.7" />
    </g>
  </Svg>
);

export const IconeArquivos = (p: PropsIcone) => (
  <Svg nome="arq" {...p}>
    <rect className="tampa" x="3" y="4" width="18" height="4.5" rx="1.5" />
    <path d="M5 8.5v10A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5v-10" />
    <path className="ac" d="M10 12.5h4" />
  </Svg>
);

export const IconeSair = (p: PropsIcone) => (
  <Svg nome="sair" {...p}>
    <path d="M10 4H6.5A1.5 1.5 0 0 0 5 5.5v13A1.5 1.5 0 0 0 6.5 20H10" />
    <g className="seta">
      <path className="perigo" d="M14.5 8l4 4-4 4" />
      <path className="perigo" d="M18.5 12H9.5" />
    </g>
  </Svg>
);

export const IconeResposta = (p: PropsIcone) => (
  <Svg nome="check" {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path className="traco" d="M8 12.3l2.7 2.7L16.2 9.5" />
  </Svg>
);

export const IconeRecebimento = (p: PropsIcone) => (
  <Svg nome="pacote" {...p}>
    <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" />
    <path d="M4 7.5l8 4.5 8-4.5M12 12v9" />
    <path className="fita mv" d="M8 5.3l8 4.5" />
  </Svg>
);

export const IconeRestaurar = (p: PropsIcone) => (
  <Svg nome="restaurar" {...p}>
    <g className="volta">
      <path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3" />
      <path d="M4.5 4v4h4" />
    </g>
  </Svg>
);

export const IconeEditar = (p: PropsIcone) => (
  <Svg nome="editar" {...p}>
    <g className="lapis">
      <path d="M4.5 19.5l1-4.2L15.8 5a2 2 0 0 1 2.9 0l.3.3a2 2 0 0 1 0 2.9L8.7 18.5z" />
      <path className="ac" d="M13.5 7.3l3.2 3.2" />
    </g>
  </Svg>
);

export const IconeLixo = (p: PropsIcone) => (
  <Svg nome="lixo" {...p}>
    <g className="tampa-lixo">
      <path d="M4.5 6.5h15" />
      <path d="M9.5 6.5V4.5h5v2" />
    </g>
    <path d="M6.5 6.5l.9 12.2a1.5 1.5 0 0 0 1.5 1.3h6.2a1.5 1.5 0 0 0 1.5-1.3l.9-12.2" />
    <path d="M10.2 10.5v6M13.8 10.5v6" />
  </Svg>
);

export const IconeVer = (p: PropsIcone) => (
  <Svg nome="olho" {...p}>
    <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />
    <circle className="pupila ac" cx="12" cy="12" r="2.8" />
  </Svg>
);

export const IconeBaixar = (p: PropsIcone) => (
  <Svg nome="baixar" {...p}>
    <path d="M4.5 15.5v3a1.5 1.5 0 0 0 1.5 1.5h12a1.5 1.5 0 0 0 1.5-1.5v-3" />
    <g className="flecha">
      <path className="ac" d="M12 4v11M7.5 10.5 12 15l4.5-4.5" />
    </g>
  </Svg>
);

export const IconeSubstituir = (p: PropsIcone) => (
  <Svg nome="trocar" {...p}>
    <g className="giro">
      <path d="M4.5 9.5A7.5 7.5 0 0 1 18 6.5l1.5 1.5" />
      <path d="M19.5 4v4h-4" />
      <path className="ac" d="M19.5 14.5A7.5 7.5 0 0 1 6 17.5L4.5 16" />
      <path className="ac" d="M4.5 20v-4h4" />
    </g>
  </Svg>
);

/** Ampulheta: aguardando resposta */
export const IconeAguardando = (p: PropsIcone) => (
  <Svg nome="ampulheta" {...p}>
    <path d="M7 3.5h10M7 20.5h10" />
    <path d="M8 3.5c0 4 4 5 4 8.5s-4 4.5-4 8.5M16 3.5c0 4-4 5-4 8.5s4 4.5 4 8.5" />
    <path className="areia ac" d="M10 18h4" />
  </Svg>
);
