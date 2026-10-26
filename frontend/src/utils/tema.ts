import { useEffect, useState } from "react";

/** Escolha do usuário. "auto" segue o tema do sistema operacional. Fica guardada neste navegador. */
export type Tema = "auto" | "claro" | "escuro";

const CHAVE = "planner-tema"; // a mesma do script em index.html
const sistemaEscuro = () => matchMedia("(prefers-color-scheme: dark)");

function lerTema(): Tema {
  try {
    const t = localStorage.getItem(CHAVE);
    return t === "claro" || t === "escuro" ? t : "auto";
  } catch {
    return "auto"; // navegação privada ou armazenamento bloqueado
  }
}

function aplicar(tema: Tema) {
  const escuro = tema === "escuro" || (tema === "auto" && sistemaEscuro().matches);
  document.documentElement.dataset.theme = escuro ? "dark" : "light";
}

export function useTema(): [Tema, (t: Tema) => void] {
  const [tema, setTema] = useState<Tema>(lerTema);

  useEffect(() => {
    aplicar(tema);
    try {
      if (tema === "auto") localStorage.removeItem(CHAVE);
      else localStorage.setItem(CHAVE, tema);
    } catch {
      // sem armazenamento a escolha vale só até fechar a página
    }
    if (tema !== "auto") return;
    // No automático, acompanha a troca de tema do sistema sem recarregar
    const mq = sistemaEscuro();
    const mudou = () => aplicar("auto");
    mq.addEventListener("change", mudou);
    return () => mq.removeEventListener("change", mudou);
  }, [tema]);

  // Outra aba deste navegador trocou o tema
  useEffect(() => {
    const outraAba = (e: StorageEvent) => e.key === CHAVE && setTema(lerTema());
    window.addEventListener("storage", outraAba);
    return () => window.removeEventListener("storage", outraAba);
  }, []);

  return [tema, setTema];
}
