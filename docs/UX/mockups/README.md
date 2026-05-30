# Mockup - Tela Principal (Wireframe de Baixa Fidelidade)

## Descrição Textual do Wireframe

**Justificativa Geral:** O layout é centrado e simples, priorizando a única tarefa do usuário no MVP: inserir uma consulta e visualizar o resultado. A hierarquia visual clara (Header > Input > Action > Output) guia o usuário de forma intuitiva, minimizando a carga cognitiva — um aspecto crucial para profissionais que necessitam de eficiência.

A tela é organizada em uma única coluna, com os seguintes elementos, de cima para baixo:

1.  **Cabeçalho (Header):**
    -   **Justificativa:** Estabelece a identidade do produto de forma imediata.
    -   **Elemento:** Uma barra horizontal no topo da página, com fundo branco e uma sombra sutil para criar profundidade.
    -   **Conteúdo:** Centralizado verticalmente nesta barra, está o título **"Central de Inteligência Jurídica"** estilizado como `H1` usando a tipografia definida no UI Kit.

2.  **Área de Entrada (Input Area):**
    -   **Justificativa:** A área de entrada é o elemento mais importante da tela. Seu tamanho generoso comunica que o sistema espera entradas textuais substanciais e incentiva o usuário a ser detalhado em sua solicitação.
    -   **Elemento:** Localizada no centro superior da área de conteúdo principal, abaixo do cabeçalho.
    -   **Componente:** Um grande componente `Input de Texto` (como definido no UI Kit), ocupando a largura total do container principal.
    -   **Atributos:** O campo possui um `placeholder` com o texto: *"Exemplo: Verificar o status do tribunal TJSP ou Consultar as últimas decisões do STF sobre..."*.

3.  **Botão de Ação (Call-to-Action):**
    -   **Justificativa:** Posicionado logo abaixo do input, forma um grupo visual claro com a área de entrada, indicando a sequência natural de ação: "digitar > processar".
    -   **Elemento:** Um único `Botão Primário`, centralizado horizontalmente na tela.
    -   **Rótulo:** O botão exibe o texto **"Processar"**.

4.  **Área de Resultados (Output Area):**
    -   **Justificativa:** Esta área é inicialmente vazia, ganhando conteúdo apenas após a ação do usuário. Seu design prevê a exibição de informações complexas (o JSON) de forma estruturada e fácil de digerir.
    -   **Elemento:** Uma seção expansível localizada abaixo do botão. Quando ativa, contém um `Card de Resultado`.
    -   **Estado com Dados:** Ao receber uma resposta de sucesso da API, o card é preenchido da seguinte forma:
        -   **Cabeçalho do Card:** Exibe o valor de `"tribunal_used"` (ex: `TJSP`) em destaque.
        -   **Corpo do Card:** Os dados dentro de `"supervisor_result"` são formatados como uma lista de pares chave-valor legíveis:
            -   **Operação:** [Valor de `operation`]
            -   **Status do Sistema:** [Valor de `data.status`] (com um indicador visual de cor, e.g., verde para "operacional")
            -   **Última Atualização:** [Valor formatado de `data.ultima_atualizacao`]
            -   **Mensagem:** [Valor de `data.mensagem`]
            -   **Timestamp da Consulta:** [Valor formatado de `timestamp`]

5.  **Estado de Carregamento (Loading State):**
    -   **Justificativa:** Fornece feedback crucial durante o tempo de espera, evitando que o usuário pense que a interface travou.
    -   **Gatilho:** Imediatamente após o clique no botão "Processar".
    -   **Comportamento:** O texto do botão é substituído pelo `Spinner de Carregamento`. A `Área de Resultados` é limpa (se houver conteúdo anterior) e uma mensagem sutil como "Consultando o tribunal..." pode ser exibida.

## Fluxo de Interação
1.  O usuário digita sua tarefa no campo de entrada.
2.  O usuário clica em "Processar".
3.  O sistema entra no *Estado de Carregamento*.
4.  Upon API response, o sistema preenche a `Área de Resultados` com o `Card de Resultado` formatado.
5.  Se ocorrer um erro, a `Área de Resultados` exibe uma mensagem de erro dentro do card, utilizando a cor de feedback definida para erro.
