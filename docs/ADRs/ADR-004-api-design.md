# ADR-004: API RESTful para o Serviço do SupervisorAgent

## Status
Aceito

## Contexto
O backend do `SupervisorAgent` foi implementado e containerizado. O IA-Designer produziu um UI Kit e um mockup que define a interação do usuário: submeter uma tarefa de texto e receber um resultado estruturado. É necessário projetar a interface de programação de aplicações (API) que servirá de ponte entre o frontend (a ser desenvolvido) e o backend, expondo a funcionalidade do agente de forma robusta, escalável e alinhada aos princípios do projeto.

## Decisão
Adotaremos uma API RESTful utilizando JSON como formato de serialização de dados.

*   A API será versionada através do path (ex.: `/api/v1/`).
*   O método HTTP `POST` será utilizado para a criação de novas tarefas de processamento.
*   As respostas de sucesso seguirão um schema JSON consistente, incluindo o resultado completo do `SupervisorAgent`.
*   As respostas de erro serão formatadas de acordo com o padrão **RFC 7807 (Problem Details for HTTP APIs)**.

## Consequências
### Positivas
*   **Simplicidade e Familiaridade:** REST/JSON é um padrão amplamente conhecido, facilitando o consumo por parte de desenvolvedores de frontend e a integração com futuros serviços.
*   **Semântica Clara:** O uso correto de métodos HTTP (`POST` para criação) torna a API intuitiva.
*   **Desacoplamento:** A separação clara entre frontend e backend permite que ambas as partes evoluam independentemente, desde que o contrato da API (definido pela especificação OpenAPI) seja mantido.
*   **Capacidade de Evolução:** O versionamento explícito da API protege os clientes existentes de mudanças que possam quebrar compatibilidade.

### Negativas
*   **Overhead de Comunicação:** Comparado a alternativas como gRPC, o JSON sobre HTTP pode ter um overhead ligeiramente maior em tamanho de mensagem e tempo de parsing.
*   **Definição de Contrato:** É necessário criar e manter uma especificação OpenAPI para documentar o contrato formalmente.

### Neutras
*   A decisão está em total conformidade com os princípios "Crisp Pragmatist" estabelecidos no projeto, particularmente "Explícito > Mágico" e a diretriz para uso de RFC 7807.
