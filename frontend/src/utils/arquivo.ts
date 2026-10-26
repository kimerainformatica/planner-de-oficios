/** Oferece um blob para o usuário salvar com o nome indicado. */
export function salvarArquivo(blob: Blob, nome: string) {
  const url = URL.createObjectURL(blob);
  Object.assign(document.createElement("a"), { href: url, download: nome }).click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
