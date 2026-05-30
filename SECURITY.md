# Política de Segurança

## Reportando uma vulnerabilidade

Se você encontrar uma vulnerabilidade de segurança, **não abra uma issue pública**.
Em vez disso, use o canal privado de
[Security Advisories do GitHub](https://github.com/danzeroum/Central_Inteligencia_Juridica/security/advisories/new)
para relatá-la de forma responsável.

Inclua, se possível: descrição, passos de reprodução, impacto potencial e versão
afetada. O objetivo é uma primeira resposta em até 5 dias úteis.

## Escopo e considerações

Esta plataforma lida com **dados jurídicos sensíveis** e decisões assistidas por
IA sujeitas a auditoria (LGPD). Atenção especial a:

- **Trilha de auditoria** (`DecisionLedger`): integridade dos registros de decisão.
- **Human-in-the-Loop**: o fluxo de aprovação não deve poder ser contornado.
- **Sanitização de entrada** (`InputSanitizer`): XSS, SQL injection, path traversal.
- **Segredos**: nunca commitar `.env`, tokens de tribunais ou `JWT_SECRET`.

A CI executa varredura com **Bandit** (falhas de severidade alta bloqueiam o build).
