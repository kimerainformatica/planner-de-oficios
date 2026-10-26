import { useEffect, useState } from "react";

const semMovimento = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Mostra "18,4" ou "89%" contando do zero até o valor quando ele aparece ou muda. Texto que não começa
 *  por número ("—") aparece como está. */
export function NumeroAnimado({ valor, duracao = 900 }: { valor: string; duracao?: number }) {
  const m = /^(\d+)(?:,(\d+))?(.*)$/.exec(valor);
  const alvo = m ? Number(`${m[1]}.${m[2] ?? 0}`) : 0;
  const casas = m?.[2]?.length ?? 0;
  const [p, setP] = useState(1);

  useEffect(() => {
    if (!m || alvo === 0 || semMovimento()) return;
    let quadro = 0;
    const inicio = performance.now();
    const passo = (agora: number) => {
      const t = Math.min(1, (agora - inicio) / duracao);
      setP(1 - Math.pow(1 - t, 3));
      if (t < 1) quadro = requestAnimationFrame(passo);
    };
    setP(0);
    quadro = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(quadro);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [alvo, duracao]);

  if (!m) return <>{valor}</>;
  const atual = (alvo * p).toFixed(casas).replace(".", ",");
  return (
    <>
      {atual}
      {m[3]}
    </>
  );
}
