import { Monitor, Moon, Sun } from "lucide-react";
import { useTema, type Tema } from "../utils/tema";

const OPCOES: { valor: Tema; rotulo: string; dica: string; Icone: typeof Sun }[] = [
  { valor: "claro", rotulo: "Claro", dica: "Tema claro", Icone: Sun },
  { valor: "escuro", rotulo: "Escuro", dica: "Tema escuro", Icone: Moon },
  { valor: "auto", rotulo: "Auto", dica: "Automático: segue o tema do computador", Icone: Monitor },
];

/** Claro / Escuro / Automático. Compacto (só ícones) na tela de login. */
export function SeletorTema({ compacto = false }: { compacto?: boolean }) {
  const [tema, setTema] = useTema();
  return (
    <div className={`seletor-tema ${compacto ? "compacto" : ""}`} role="radiogroup" aria-label="Tema da interface">
      {OPCOES.map(({ valor, rotulo, dica, Icone }) => (
        <button key={valor} type="button" role="radio" aria-checked={tema === valor} title={dica}
          aria-label={compacto ? dica : undefined} className={tema === valor ? "ativo" : ""}
          onClick={() => setTema(valor)}>
          <Icone size={15} aria-hidden />
          {!compacto && rotulo}
        </button>
      ))}
    </div>
  );
}
