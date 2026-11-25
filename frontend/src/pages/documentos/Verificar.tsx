import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Ban, BadgeCheck, Search } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { verificarDocumento } from "../../api/endpoints";
import logo from "../../assets/acqua-logo.svg";
import { Carregando } from "../../components/ui";
import { data, dataHora } from "../../utils/formato";
import { URL_VALIDADOR } from "./comum";

/** Página pública (sem login): confere um documento pelo código de verificação impresso no rodapé ou no QR code. */
export function Verificar() {
  const { codigo } = useParams();
  const navegar = useNavigate();
  const [digitado, setDigitado] = useState(codigo ?? "");
  const consulta = useQuery({
    queryKey: ["verificar", codigo],
    queryFn: () => verificarDocumento(codigo!),
    enabled: !!codigo,
    retry: false,
  });

  function procurar(e: FormEvent) {
    e.preventDefault();
    if (digitado.trim()) navegar(`/verificar/${digitado.trim().toUpperCase()}`);
  }

  const v = consulta.data;
  return (
    <main className="verificar-pagina">
      <div className="verificar-caixa">
        <header className="verificar-topo">
          <img src={logo} alt="Instituto ACQUA" />
          <div>
            <h1>Verificação de documento</h1>
            <p className="texto-suave">Confira se um ofício ou memorando foi emitido pelo Planner de Ofícios e se continua válido.</p>
          </div>
        </header>

        <form className="grupo verificar-form" onSubmit={procurar}>
          <input className="input" value={digitado} onChange={(e) => setDigitado(e.target.value)} placeholder="Código, ex.: 7Q4K-2M9X"
            aria-label="Código de verificação" maxLength={12} autoFocus={!codigo} />
          <button className="btn btn-primario" type="submit"><Search size={16} /> Verificar</button>
        </form>

        {codigo && consulta.isPending && <Carregando texto="Conferindo…" />}
        {consulta.isError && (
          <div className="verificar-resultado ruim" role="alert">
            <AlertTriangle size={26} aria-hidden />
            <div><strong>Nenhum documento com o código {codigo}.</strong><p>Confira se o código foi digitado como está no rodapé do documento.</p></div>
          </div>
        )}
        {v && (
          <>
            {v.status === "CANCELADO" ? (
              <div className="verificar-resultado ruim" role="status">
                <Ban size={26} aria-hidden />
                <div><strong>Documento cancelado, sem validade.</strong>
                  <p>Cancelado em {v.cancelado_em ? dataHora(v.cancelado_em) : "—"}. Motivo: {v.motivo_cancelamento}</p></div>
              </div>
            ) : !v.integro ? (
              <div className="verificar-resultado ruim" role="status">
                <AlertTriangle size={26} aria-hidden />
                <div><strong>O registro deste documento foi alterado depois da emissão.</strong>
                  <p>Não confie no conteúdo sem falar com quem o emitiu.</p></div>
              </div>
            ) : (
              <div className="verificar-resultado bom" role="status">
                <BadgeCheck size={26} aria-hidden />
                <div><strong>Documento autêntico.</strong><p>Emitido pelo Planner de Ofícios{v.unidade ? ` (${v.unidade})` : ""} e válido.</p></div>
              </div>
            )}
            <dl className="dados-documento verificar-dados">
              <dt>Documento</dt><dd>{v.titulo}</dd>
              <dt>Data</dt><dd>{v.data_documento ? data(v.data_documento) : "—"}</dd>
              <dt>Assunto</dt><dd>{v.assunto}</dd>
              <dt>Elaborado por</dt><dd>{v.elaborador_nome}</dd>
              {v.validador_nome && (<><dt>De acordo</dt><dd>{v.validador_nome}</dd></>)}
              <dt>Emitido em</dt><dd>{v.emitido_em ? dataHora(v.emitido_em) : "—"}</dd>
              <dt>Assinaturas eletrônicas</dt>
              <dd>{v.assinaturas.length === 0 ? "Nenhuma (assinado à mão, se for o caso)" : v.assinaturas.map((a) => (
                <span key={a.papel} className="bloco">
                  {a.nome}{a.cargo ? `, ${a.cargo}` : ""}, {a.forma === "GOVBR" ? "pelo GOV.BR" : "no app"} em {dataHora(a.assinado_em)}
                </span>
              ))}
                {v.assinaturas.some((a) => a.forma === "GOVBR") && (
                  <span className="bloco texto-suave">Confira o arquivo PDF assinado em{" "}
                    <a className="link" href={URL_VALIDADOR} target="_blank" rel="noreferrer">validar.iti.gov.br</a>.</span>
                )}</dd>
              <dt>Código</dt><dd><strong className="codigo-verificacao">{v.codigo}</strong></dd>
              {v.hash_conteudo && (<><dt>Impressão digital</dt><dd className="hash">{v.hash_conteudo}</dd></>)}
            </dl>
          </>
        )}
      </div>
    </main>
  );
}
