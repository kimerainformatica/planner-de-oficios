# Certificados de confiança

`govbr/` tem a cadeia pública das assinaturas GOV.BR (ITI): AC Raiz, AC Intermediária e AC Final do Governo Federal do
Brasil v1. Só documentos assinados por certificados desta cadeia são aceitos (`app/services/assinatura_govbr.py`).

Obtida em 24/11/2026 de <http://repo.iti.br/docs/Cadeia_GovBr-der.p7b> e, por HTTPS, do endereço indicado na página do
governo [Saiba como importar os certificados do gov.br](https://www.gov.br/governodigital/pt-br/identidade/assinatura-eletronica/saiba-como-importar-os-certificados-do-gov-br-no-adobe-acrobat-reader).
As duas cópias são idênticas. Impressões digitais (SHA-256):

| Arquivo | SHA-256 |
|---|---|
| `1-raiz.pem` | `163bd003bc0df2beab88174b6d5b450b6e1dc973a64b2dc2a33218544f49ef4e` |
| `2-intermediaria.pem` | `c96f8b6de022119717dfd2aeb6334e98036aaeb5c3818b4d84be1d267926d2e7` |
| `3-final.pem` | `96bb5c41859fc51d88f305517be641d9ef4a5d601b1bb2352e7161e97ff8b852` |

Válida até junho de 2033. Se o governo publicar outra cadeia, confira a origem antes de acrescentar os arquivos aqui.
