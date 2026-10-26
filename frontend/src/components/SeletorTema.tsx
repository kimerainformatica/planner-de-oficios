import { Monitor, Moon, Sun } from "lucide-react";
import type { CSSProperties } from "react";
import { useTema, type Tema } from "../utils/tema";

const OPCOES: { valor: Tema; rotulo: string; dica: string; Icone: typeof Sun }[] = [
  { valor: "claro", rotulo: "Claro", dica: "Tema claro", Icone: Sun },
  { valor: "escuro", rotulo: "Escuro", dica: "Tema escuro", Icone: Moon },
  { valor: "auto", rotulo: "Auto", dica: "Automático: segue o tema do computador", Icone: Monitor },
];

/** Claro / Escuro / Automático, com uma pílula que desliza até a escolha. "claro" é a versão sobre fundo
 *  claro (tela de login); a do menu lateral fica sobre o verde-petróleo. */
export function SeletorTema({ claro = false }: { claro?: boolean }) {
  const [tema, setTema] = useTema();
  const indice = OPCOES.findIndex((o) => o.valor === tema);
  return (
    <div className={`seletor-tema ${claro ? "seletor-tema-claro" : ""}`} role="radiogroup" aria-label="Tema da interface"
      style={{ "--i": indice } as CSSProperties}>
      {OPCOES.map(({ valor, rotulo, dica, Icone }) => (
        <button key={valor} type="button" role="radio" aria-checked={tema === valor} title={dica}
          aria-label={claro ? dica : undefined} className={tema === valor ? "ativo" : ""}
          onClick={() => setTema(valor)}>
          <Icone size={15} aria-hidden />
          {rotulo}
        </button>
      ))}
    </div>
  );
}
