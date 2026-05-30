# Como adicionar um novo domínio (área jurídica)

A Central de Inteligência Jurídica é **orientada a dados**: adicionar uma nova área do direito
(ex.: Direito Trabalhista, Consumidor, Tributário) é, na maioria dos casos, **inserir dados** —
não escrever código. Este guia descreve o processo.

## Modelo de dados envolvido

| Tabela | Papel |
|---|---|
| `areas_juridicas` | Cadastro da área (nome, descrição, ativo) |
| `prompts` | Prompt da área, com versão (`versao`) e flag `ativo`. Usa variáveis `{{campo}}` |
| `prompt_versions` | Histórico de versões do prompt |
| `configuracoes` | Parâmetros chave/valor (config flexível, inclusive por domínio) |
| `peticoes` | Documentos gerados (entrada em `dados_entrada` JSONB, vínculo `area_id`) |

## Passo a passo

1. **Criar a área** em `areas_juridicas` (via tela *Áreas* — `src/components/AreasManager.tsx`):
   - `nome`, `descricao`, `ativo = true`.

2. **Criar o prompt** da área em `prompts` (tela *Prompts* — `src/components/PromptManager.tsx`):
   - `area_id` apontando para a nova área, `versao = 1`, `ativo = true`.
   - No corpo (`conteudo`), use **variáveis** no formato `{{nome_do_campo}}`. Ex.:
     ```
     Elabore uma petição de {{tipo_acao}} para o reclamante {{nome_reclamante}},
     em face de {{nome_reclamada}}, com os seguintes fatos: {{fatos}}.
     ```
   - O frontend detecta automaticamente esses campos (`extractedFields` em
     `src/components/PetitionGenerator.tsx`) e gera os inputs do formulário.

3. **(Opcional) Parâmetros específicos** da área em `configuracoes` (chave/valor),
   lidos pelo app conforme necessário.

4. **Gerar e validar**: na tela de geração, selecione a área, preencha os campos e gere.
   A Edge Function `supabase/functions/generate-peticao/index.ts`:
   - carrega o prompt **ativo de maior versão** da área,
   - substitui as variáveis `{{campo}}` com os dados de entrada,
   - consulta o **cache** (`ai_response_cache`) antes de chamar o LLM,
   - registra **uso/tokens** em `ai_usage_log` (custo por área no dashboard).

5. **Versionar o prompt**: ao ajustar, crie uma nova `versao` e marque-a `ativo`; a versão
   anterior fica no histórico (`prompt_versions`). Não é preciso alterar código.

## Quando *é* necessário código

Apenas se a nova área exigir:
- um tipo de campo de entrada que o formulário dinâmico ainda não suporta, ou
- uma regra de validação específica que não dê para expressar via dados/config.

Nesses casos, prefira **parametrizar** (via `configuracoes`) em vez de embutir a regra no código,
mantendo o sistema genérico para os próximos domínios.

## Observabilidade de custo

- `ai_usage_log` registra tokens e se a resposta veio do cache.
- A view `ai_usage_por_area` agrega geração, cache e tokens faturáveis por área — base para um
  painel de custo por domínio.
