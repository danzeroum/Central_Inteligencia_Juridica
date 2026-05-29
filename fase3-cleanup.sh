#!/usr/bin/env bash
# ================================================================================
#  FASE 3 - LIMPEZA PROFUNDA DO REPOSITORIO
#  Central de Inteligencia Juridica
# ================================================================================
#
#  REMOVE tudo que NAO esta relacionado ao sistema juridico/Docker:
#    - Pasta .buildtoflip (artefatos do projeto anterior BuildToFlip)
#    - Java/Spring Boot (pom.xml, src/main/java/*, application.yml)
#    - k6 scripts (load/stress testing)
#    - Terraform (infra as code - usando Docker)
#    - Ansible (provisioning - usando Docker)
#    - Scripts de setup/validacao do BuildToFlip v6
#    - Certificados e artefatos do projeto antigo
#    - Experimental/sandbox
#    - GitHub Actions workflow do BuildToFlip
#    - IDE configs (.idea)
#    - Arquivos JSON de discovery/consensus antigos
#    - Documentacao obsoleta do BuildToFlip
#
#  MANTENHO:
#    - src/ (Python/FastAPI - sistema juridico)
#    - docker/ (Dockerfiles e compose)
#    - docker-compose.yml (raiz)
#    - Dockerfile (raiz)
#    - monitoring/ (Prometheus + Grafana dashboards para Docker)
#    - tests/ (pytest)
#    - docs/ (documentacao)
#    - requirements*.txt
#    - pytest.ini, .gitignore, .env.example, .env.template
#    - README.md, CHANGELOG.md
#    - config/ (constituicao agentes + prompts)
#    - despachar_tarefa.py (script util do dominio juridico)
#    - examples/ (demos do sistema)
#
#  Uso:
#    cd /c/vps/Central_Inteligencia_Juridica
#    bash fase3-cleanup.sh [--dry-run]
# ================================================================================

set -euo pipefail

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "======================================================================="
    echo "  MODO DRY-RUN - Nenhuma alteracao sera feita"
    echo "======================================================================="
    echo ""
fi

# Cores
RED='\033[91m'
GREEN='\033[92m'
YELLOW='\033[93m'
CYAN='\033[96m'
RESET='\033[0m'

removed_count=0
removed_bytes=0

log_remove() {
    local path="$1"
    local reason="$2"
    if [ -e "$path" ]; then
        local size
        size=$(du -sb "$path" 2>/dev/null | cut -f1 || echo "0")
        if $DRY_RUN; then
            echo -e "  ${YELLOW}[DRY-RUN]${RESET} REMOVER: $path"
            echo -e "           Motivo: $reason"
        else
            rm -rf "$path"
            echo -e "  ${RED}[REMOVED]${RESET} $path"
            echo -e "           Motivo: $reason"
        fi
        removed_count=$((removed_count + 1))
        removed_bytes=$((removed_bytes + size))
    else
        echo -e "  ${CYAN}[SKIP]${RESET} $path (ja nao existe)"
    fi
}

log_keep() {
    local path="$1"
    local reason="$2"
    echo -e "  ${GREEN}[KEEP]${RESET} $path"
    echo -e "         Motivo: $reason"
}

echo "==========================================================================="
echo "  FASE 3 - LIMPEZA PROFUNDA DO REPOSITORIO"
echo "  Central de Inteligencia Juridica"
echo "==========================================================================="
echo ""

# ── 1. Pasta .buildtoflip (artefatos do BuildToFlip v6) ──────────────────────
echo -e "${CYAN}[GRUPO 1] Arquivos do projeto anterior BuildToFlip${RESET}"
echo ""

log_remove ".buildtoflip" \
    "Artefatos do BuildToFlip v6 (checklists, ledger, consensus, prompts, responses)"

log_remove "buildtoflip-v6-certificate.md" \
    "Certificacao do BuildToFlip v6 - nao relacionado ao sistema juridico"

log_remove "buildtoflip-v6.1-certificate.md" \
    "Certificacao do BuildToFlip v6.1 - nao relacionado ao sistema juridico"

log_remove "discovery-consensus.v6.json" \
    "Arquivo de discovery do BuildToFlip v6 - obsoleto"

log_remove "handoff-codex.md" \
    "Handoff document do BuildToFlip - obsoleto"

log_remove "fallback-strategy.md" \
    "Estrategia de fallback do BuildToFlip - obsoleto"

log_remove "orchestration-matrix.md" \
    "Matriz de orquestracao do BuildToFlip - obsoleto"

log_remove "certificates" \
    "Certificados do BuildToFlip (prompt chaining) - nao relacionado ao sistema juridico"

echo ""

# ── 2. Java/Spring Boot ────────────────────────────────────────────────────
echo -e "${CYAN}[GRUPO 2] Java/Spring Boot (projeto usa Python/FastAPI)${RESET}"
echo ""

log_remove "pom.xml" \
    "Maven POM do Java/Spring Boot - projeto usa Python/FastAPI"

log_remove "src/main" \
    "Codigo Java (exceptions Spring Boot) - projeto usa Python/FastAPI"

echo ""

# ── 3. k6 (load testing) ───────────────────────────────────────────────────
echo -e "${CYAN}[GRUPO 3] k6 load testing scripts${RESET}"
echo ""

log_remove "k6" \
    "Scripts k6 de load/stress testing - removido por solicitacao do usuario"

echo ""

# ── 4. Terraform ───────────────────────────────────────────────────────────
echo -e "${CYAN}[GRUPO 4] Terraform IaC${RESET}"
echo ""

log_remove "terraform" \
    "Infraestrutura Terraform - usando Docker Compose"

echo ""

# ── 5. Ansible ─────────────────────────────────────────────────────────────
echo -e "${CYAN}[GRUPO 5] Ansible provisioning${RESET}"
echo ""

log_remove "ansible" \
    "Playbook Ansible - usando Docker Compose"

echo ""

# ── 6. Scripts de setup/validacao do BuildToFlip ─────────────────────────────
echo -e "${CYAN}[GRUPO 6] Scripts de setup BuildToFlip v6${RESET}"
echo ""

log_remove "scripts" \
    "Scripts de setup/validacao/buildtoflip v6 - maioria obsoleta"

log_remove "setup-project.sh" \
    "Setup script do BuildToFlip v6 - obsoleto"

echo ""

# ── 7. Experimental ────────────────────────────────────────────────────────
echo -e "${CYAN}[GRUPO 7] Codigo experimental${RESET}"
echo ""

log_remove "experimental" \
    "Sandbox experimental - nao estavel/producao"

echo ""

# ── 8. GitHub Actions do BuildToFlip ────────────────────────────────────────
echo -e "${CYAN}[GRUPO 8] CI/CD do BuildToFlip${RESET}"
echo ""

log_remove ".github/workflows/buildtoflip-v6.yml" \
    "Workflow CI/CD do BuildToFlip v6 - nao relacionado ao sistema juridico"

# Remove .github se ficou vazio
if [ -d ".github" ] && [ -z "$(ls -A .github 2>/dev/null)" ]; then
    log_remove ".github" "Diretorio vazio apos remocao do workflow"
fi

echo ""

# ── 9. IDE configs ──────────────────────────────────────────────────────────
echo -e "${CYAN}[GRUPO 9] Configuracoes de IDE${RESET}"
echo ""

log_remove ".idea" \
    "Configuracoes IntelliJ IDEA - nao deve estar no git"

echo ""

# ── 10. Arquivos temporarios/backup da Fase 1 ─────────────────────────────
echo -e "${CYAN}[GRUPO 10] Arquivos temporarios e backup${RESET}"
echo ""

log_remove "src-api-auth.py" \
    "Backup temporario do fase1-security.sh - nao necessario"

log_remove "src-core-safe_agent_base.py" \
    "Backup temporario do fase1-security.sh - nao necessario"

log_remove "src-utils-input_sanitizer.py" \
    "Backup temporario do fase1-security.sh - nao necessario"

log_remove "gitignore" \
    "Arquivo gitignore duplicado (o correto e .gitignore com ponto)"

echo ""

# ── 11. Documentacao obsoleta ──────────────────────────────────────────────
echo -e "${CYAN}[GRUPO 11] Documentacao obsoleta${RESET}"
echo ""

log_remove "TESTING.md" \
    "Guia de testes referenciando scripts BuildToFlip obsoletos"

echo ""

# ── 12. Metrics YAMLs antigos (raiz) ────────────────────────────────────────
echo -e "${CYAN}[GRUPO 12] Arquivos de configuracao obsoletos${RESET}"
echo ""

log_remove "metrics.yaml" \
    "Configuracao de metrics antiga - Prometheus config esta em monitoring/"

log_remove "metrics-advanced.yaml" \
    "Configuracao de metrics avancada antiga - Prometheus config esta em monitoring/"

log_remove "requirements-core.txt" \
    "Arquivo de requirements redundante (requirements.txt ja existe)"

echo ""

# ── 13. CHANGELOG.md (manter, apenas informativo) ─────────────────────────
echo -e "${CYAN}[GRUPO 13] Arquivos mantidos${RESET}"
echo ""

log_keep "src/" "Codigo-fonte Python/FastAPI do sistema juridico"
log_keep "docker/" "Dockerfiles e compose files para producao"
log_keep "docker-compose.yml" "Docker Compose principal (raiz)"
log_keep "Dockerfile" "Dockerfile principal (raiz)"
log_keep "monitoring/" "Prometheus + Grafana para Docker (dashboards e config)"
log_keep "tests/" "Testes pytest"
log_keep "docs/" "Documentacao do sistema"
log_keep "config/" "Configuracao de agentes e prompts"
log_keep "examples/" "Demos do sistema juridico"
log_keep ".gitignore" "Git ignore rules"
log_keep ".env.example" "Template de variaveis de ambiente"
log_keep ".env.template" "Template de variaveis de ambiente"
log_keep ".env.prod" "Variaveis de producao (com secrets removidos)"
log_keep "requirements.txt" "Dependencias Python"
log_keep "requirements-dev.txt" "Dependencias de desenvolvimento"
log_keep "pytest.ini" "Configuracao pytest"
log_keep "README.md" "Documentacao principal"
log_keep "CHANGELOG.md" "Historico de mudancas"
log_keep "despachar_tarefa.py" "Script utilitario do dominio juridico"

echo ""

# ── 14. Limpar diretorio vazio ─────────────────────────────────────────────
echo -e "${CYAN}[GRUPO 14] Diretorios vazios${RESET}"
echo ""

if ! $DRY_RUN; then
    find . -type d -empty -not -path "./.git/*" -delete 2>/dev/null || true
    echo -e "  ${GREEN}[OK]${RESET} Diretorios vazios removidos"
else
    echo -e "  ${YELLOW}[DRY-RUN]${RESET} Diretorios vazios seriam removidos"
fi

echo ""

# ── 15. Atualizar .gitignore ────────────────────────────────────────────────
echo -e "${CYAN}[GRUPO 15] Atualizar .gitignore${RESET}"
echo ""

if [ -f ".gitignore" ] && ! $DRY_RUN; then
    # Garantir que estas entradas estao no .gitignore
    grep -q "^\.idea/$" .gitignore 2>/dev/null || echo ".idea/" >> .gitignore
    grep -q "^\.buildtoflip/$" .gitignore 2>/dev/null || echo ".buildtoflip/" >> .gitignore
    grep -q "^*.class$" .gitignore 2>/dev/null || echo "*.class" >> .gitignore
    grep -q "^target/$" .gitignore 2>/dev/null || echo "target/" >> .gitignore
    grep -q "^pom.xml$" .gitignore 2>/dev/null || true  # pom.xml sera removido, nao preciso ignorar
    grep -q "^src/main/$" .gitignore 2>/dev/null || echo "src/main/" >> .gitignore
    grep -q "^k6/$" .gitignore 2>/dev/null || echo "k6/" >> .gitignore
    grep -q "^terraform/$" .gitignore 2>/dev/null || echo "terraform/" >> .gitignore
    grep -q "^ansible/$" .gitignore 2>/dev/null || echo "ansible/" >> .gitignore
    grep -q "^experimental/$" .gitignore 2>/dev/null || echo "experimental/" >> .gitignore
    grep -q "^certificates/$" .gitignore 2>/dev/null || echo "certificates/" >> .gitignore
    grep -q "^.github/" .gitignore 2>/dev/null || true  # Manter .github se tiver workflows uteis
    echo -e "  ${GREEN}[OK]${RESET} .gitignore atualizado com regras anti-retorno"
elif $DRY_RUN; then
    echo -e "  ${YELLOW}[DRY-RUN]${RESET} .gitignore seria atualizado"
fi

echo ""

# ── RESUMO ────────────────────────────────────────────────────────────────
echo "==========================================================================="
echo -e "  RESUMO DA LIMPEZA"
echo "==========================================================================="
echo ""
echo -e "  ${RED}Removidos:${RESET} ${removed_count} itens"
echo -e "  ${RED}Espaco liberado:${RESET} ~$((removed_bytes / 1024)) KB"
echo ""

if $DRY_RUN; then
    echo -e "  ${YELLOW}MODO DRY-RUN${RESET} - Nenhuma alteracao foi feita"
    echo ""
    echo "  Para aplicar, execute:"
    echo "    bash fase3-cleanup.sh"
    echo ""
else
    echo "  ESTRUTURA FINAL DO REPOSITORIO:"
    echo ""
    echo "  Central_Inteligencia_Juridica/"
    echo "  ├── src/                    # Codigo Python/FastAPI"
    echo "  ├── tests/                  # Testes pytest"
    echo "  ├── docker/                  # Dockerfiles + compose prod"
    echo "  ├── monitoring/              # Prometheus + Grafana"
    echo "  ├── docs/                    # Documentacao"
    echo "  ├── config/                  # Agentes + prompts"
    echo "  ├── examples/                # Demos"
    echo "  ├── docker-compose.yml       # Compose principal"
    echo "  ├── Dockerfile               # Dockerfile principal"
    echo "  ├── requirements.txt         # Deps producao"
    echo "  ├── requirements-dev.txt    # Deps dev"
    echo "  ├── pytest.ini               # Config pytest"
    echo "  ├── .gitignore               # Git rules"
    echo "  ├── .env.example             # Template env"
    echo "  ├── README.md                # Doc principal"
    echo "  ├── CHANGELOG.md             # Changelog"
    echo "  └── despachar_tarefa.py      # Script utilitario"
    echo ""
    echo "  PROXIMOS PASSOS:"
    echo ""
    echo "  1. Verificar estado:"
    echo "     git status"
    echo ""
    echo "  2. Validar imports:"
    echo "     python -c 'import compileall; compileall.compile_dir(\"src\", quiet=True)'"
    echo ""
    echo "  3. Rodar testes:"
    echo "     python -m pytest tests/unit/ -v --tb=short 2>&1 | head -40"
    echo ""
    echo "  4. Commitar:"
    echo "     git add -A"
    echo '     git commit -m "chore(fase3): deep cleanup - remove BuildToFlip, Java, k6, Terraform, Ansible"'
    echo ""
fi

echo "==========================================================================="
