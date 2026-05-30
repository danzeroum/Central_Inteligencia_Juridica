# UI Kit - Central de Inteligência Jurídica

## Visão Geral
Este UI Kit estabelece a base visual para a plataforma "Central de Inteligência Jurídica", focada em profissionais do direito. O design prioriza sobriedade, clareza e eficiência, refletindo a seriedade do domínio jurídico.

## Paleta de Cores
**Justificativa:** Uma paleta de azuis transmite confiança e estabilidade, enquanto tons de cinza oferecem neutralidade e profissionalismo, evitando distrações.

-   **Primária:** `#2C5AA0` (Azul Profundo) - Para botões primários e elementos de destaque.
-   **Secundária:** `#4A6585` (Azul Médio) - Para cabeçalhos e bordas.
-   **Neutra (Fundo):** `#F8F9FA` (Cinza Muito Claro) - Para o fundo da página.
-   **Neutra (Superfície):** `#FFFFFF` (Branco) - Para cards e superfícies de conteúdo.
-   **Neutra (Texto):** `#333333` (Cinza Escuro) - Para texto principal.
-   **Neutra (Texto Secundário):** `#666666` (Cinza Médio) - Para rótulos e texto de suporte.
-   **Feedback (Sucesso):** `#28A745` (Verde) - Para indicar conclusão bem-sucedida.
-   **Feedback (Atenção):** ` #FFC107` (Âmbar) - Para estados de carregamento.
-   **Feedback (Erro):** `#DC3545` (Vermelho) - Para mensagens de erro.

## Tipografia
**Justificativa:** A fonte `Inter` foi escolhida por sua excelente legibilidade em telas, ampla disponibilidade e aparência moderna e limpa, adequada para longos períodos de leitura.

-   **Família Primária:** `Inter, sans-serif`
-   **Escalas:**
    -   `H1 (Título da Página):` 2rem (32px) / Weight: 600
    -   `H2 (Cabeçalhos de Seção):` 1.5rem (24px) / Weight: 600
    -   `Corpo (Texto Principal):` 1rem (16px) / Weight: 400
    -   `Rótulo/Input:` 0.875rem (14px) / Weight: 500
    -   `Texto de Suporte:` 0.875rem (14px) / Weight: 400

## Componentes Essenciais

### Botão Primário
**Justificativa:** Proeminente e de alta contraste para a ação principal da tela, guiando o usuário de forma clara.

-   **Estilo Base:** Cor de fundo `#2C5AA0` (Primária), cor do texto `#FFFFFF`, preenchimento (`padding`) `12px 24px`, sem borda, raio da borda (`border-radius`) `6px`.
-   **Estado `:hover`:** Cor de fundo `#1E3F73` (um tom mais escuro do primário).
-   **Estado `:disabled`:** Cor de fundo `#CCCCCC`, cor do texto `#666666`.

### Input de Texto
**Justificativa:** Campo amplo e claro para acomodar consultas textuais complexas típicas do domínio jurídico.

-   **Estilo Base:** Cor de fundo `#FFFFFF`, cor da borda `#DDDDDD`, raio da borda `4px`, preenchimento `12px`.
-   **Estado `:focus`:** Cor da borda `#2C5AA0` (Primária), sombra sutil (`box-shadow`).

### Card de Resultado
**Justificativa:** Cria uma área visualmente distinta para os resultados, organizando as informações de forma hierárquica e escaneável.

-   **Estilo Base:** Cor de fundo `#FFFFFF`, sombra sutil (`box-shadow`), raio da borda `8px`, preenchimento interno (`padding`) `24px`.
-   **Estrutura Interna:** Cabeçalho com o nome do tribunal em `H2`, lista de pares chave-valor para os dados.

### Spinner de Carregamento
**Justificativa:** Fornece feedback visual imediato de que o sistema está processando a requisição, melhorando a percepção de desempenho.

-   **Estilo:** Indicador circular (`border-radius: 50%`) com bordas tracejadas animadas, usando a cor `#FFC107` (Atenção).

## Checklist de Acessibilidade (WCAG)
-   [ ] **Contraste de Texto:** O contraste entre o texto e o fundo deve ser de pelo menos 4.5:1 (verificado nas cores de texto `#333333` sobre `#FFFFFF` e `#F8F9FA`).
-   [ ] **Foco do Teclado:** Todos os componentes interativos (botão, input) devem ter um indicador de foco visível (usando `outline` ou `box-shadow`).
-   [ ] **Árvore de DOM:** A estrutura HTML deve ser lógica e semântica, compatível com leitores de tela.
-   [ ] **Labels:** Todos os campos de entrada devem ter labels associados corretamente (atributo `for` e `id`).
-   [ ] **Status de Carregamento:** O spinner de carregamento deve ser anunciado por tecnologias assistivas (usando `aria-live="polite"` e `aria-busy="true"`).
