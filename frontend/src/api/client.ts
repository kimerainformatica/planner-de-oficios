const CHAVE_TOKEN = "planner.token";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export function lerToken(): string | null {
  try {
    return localStorage.getItem(CHAVE_TOKEN);
  } catch {
    return null;
  }
}

export function salvarToken(token: string | null) {
  try {
    if (token) localStorage.setItem(CHAVE_TOKEN, token);
    else localStorage.removeItem(CHAVE_TOKEN);
  } catch {
    /* navegador sem armazenamento: a sessão dura só enquanto a aba estiver aberta */
  }
}

/** Chamado quando a API responde 401 (sessão expirada) — o AuthProvider registra o logout. */
let aoExpirar: () => void = () => {};
export function definirAoExpirar(fn: () => void) {
  aoExpirar = fn;
}

function mensagemDeErro(corpo: unknown, status: number): string {
  const detalhe = (corpo as { detail?: unknown })?.detail;
  if (typeof detalhe === "string") return detalhe;
  if (Array.isArray(detalhe) && detalhe.length) {
    // Erros de validação do FastAPI: [{loc, msg}]
    return detalhe
      .map((e: { msg?: string }) => (e.msg ?? "").replace(/^Value error, /, ""))
      .join("; ");
  }
  return status >= 500 ? "Erro no servidor. Tente novamente." : `Erro ${status}`;
}

type Params = Record<string, string | number | boolean | undefined | null>;

export function montarQuery(params?: Params): string {
  if (!params) return "";
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export async function requisicao(
  caminho: string,
  opcoes: RequestInit & { params?: Params } = {},
): Promise<Response> {
  const { params, headers, ...resto } = opcoes;
  const token = lerToken();
  const resposta = await fetch(`/api${caminho}${montarQuery(params)}`, {
    ...resto,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(resto.body && !(resto.body instanceof FormData) && !(resto.body instanceof URLSearchParams)
        ? { "Content-Type": "application/json" }
        : {}),
      ...headers,
    },
  });

  if (!resposta.ok) {
    const corpo = await resposta.json().catch(() => null);
    if (resposta.status === 401 && token) aoExpirar();
    throw new ApiError(resposta.status, mensagemDeErro(corpo, resposta.status));
  }
  return resposta;
}

export async function api<T>(caminho: string, opcoes: RequestInit & { params?: Params } = {}): Promise<T> {
  const resposta = await requisicao(caminho, opcoes);
  if (resposta.status === 204) return undefined as T;
  return resposta.json() as Promise<T>;
}
