# ADR-017 — FTP Plaintext para acesso ao servidor público DATASUS

**Status:** Aceito  
**Data:** 2026-06-11  
**Sprint:** SAUDE-01  
**Relacionado a:** `src/datasus/fetcher.py`, `config/governance/data_sources.yaml`

## Contexto

O indicador `saude.resp.internacoes_j` (Sentinela Respiratória) consome dados do
SIH-RD (Sistema de Informações Hospitalares — Registro de Dados) disponibilizados
pelo Ministério da Saúde via DATASUS.

O servidor público é `ftp.datasus.gov.br`.  O acesso é realizado com `ftplib` da
biblioteca padrão Python.  O Bandit (SAST) levanta dois findings de severidade alta:

| ID   | Descrição                              | Arquivo / Linha              |
|------|----------------------------------------|------------------------------|
| B402 | `import ftplib` — FTP is considered insecure | `fetcher.py:20` |
| B321 | `ftplib.FTP(...)` — FTP function called       | `fetcher.py:107` |

## Análise de Risco

| Fator | Avaliação |
|-------|-----------|
| Confidencialidade dos dados em trânsito | **Nenhuma.** Os arquivos DBC do SIH-RD são dados abertos de acesso público, baixáveis sem qualquer autenticação. O Ministério da Saúde publica os mesmos arquivos no portal DATASUS para qualquer cidadão. |
| Credenciais transmitidas | **Nenhuma.** O login é anônimo (`ftp.login()` sem argumentos = `user=anonymous, passwd=''`). |
| Disponibilidade de alternativa segura | **Não existe.** O servidor `ftp.datasus.gov.br` oferece exclusivamente FTP plaintext. Não há mirror SFTP, FTPS nem HTTPS para os arquivos binários `.dbc`. Bibliotecas de terceiros (PySUS, read.dbc) usam o mesmo protocolo. |
| Integridade dos arquivos | Os arquivos são verificados por tamanho e estrutura interna (cabeçalho DBF) após o download; a ausência de TLS não impede detecção de corrupção. |
| Risco de Man-in-The-Middle | Baixo contextualmente: rede pública governamental, dados públicos, sem impacto de confidencialidade mesmo em cenário adversarial. O risco real é de corrupção silenciosa do arquivo, mitigado pela verificação estrutural no decompressor (`expand_dbc_to_dbf`). |

## Decisão

Aceitar o uso de `ftplib` com login anônimo para acesso ao `ftp.datasus.gov.br`,
suprimindo os findings B402 e B321 via `# nosec` com justificativa inline.

As supressões seguem o padrão do projeto (não são supressões em branco — cada
`# nosec` inclui o código do finding e referência a este ADR).

## Consequências

- CI não quebra por estes findings de SAST.
- Se o DATASUS disponibilizar mirror HTTPS/SFTP no futuro, migrar e remover os
  `# nosec` (rastreado como issue SAUDE-02).
- A coluna `protocolo` em `data_sources.yaml` documenta `ftp-anonimo` para
  rastreabilidade de governança.

## Alternativas Rejeitadas

| Alternativa | Motivo da rejeição |
|-------------|-------------------|
| Usar biblioteca `ftps` / `paramiko` | O servidor não suporta FTPS nem SSH. |
| Usar PySUS (wrapper DATASUS) | Adiciona dependência pesada; usa o mesmo protocolo internamente. Não resolve o finding. |
| Download manual / pré-cache no CI | Não escala para 27 UFs × 12 meses; quebra o modelo de pull-on-demand. |
| Desabilitar Bandit para o módulo inteiro | Muito amplo; `# nosec` por linha é mais cirúrgico e auditável. |
