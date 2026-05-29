#!/usr/bin/env bash
# =============================================================================
#  FASE 1 - Correcao Completa da Central de Inteligencia Juridica
#  Aplicar via Git Bash no raiz do repositorio clonado
# =============================================================================

set -euo pipefail

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
#  PASSO 0: Validacoes Iniciais
# =============================================================================
log_info "Validando ambiente..."

# Verificar se estamos no repositorio
if [ ! -d ".git" ]; then
    log_error "Nao esta no raiz do repositorio Git. Execute: cd Central_Inteligencia_Juridica"
    exit 1
fi

# Verificar se ha conflitos de merge
CONFLICT_FILES=$(git diff --name-only --diff-filter=U 2>/dev/null || true)
if [ -z "$CONFLICT_FILES" ]; then
    # Verificar marcadores de conflito nos arquivos
    CONFLICT_MARKERS=$(grep -rl "<<<<<<< HEAD" --include="*.py" --include="*.txt" --include="*.md" . 2>/dev/null || true)
    if [ -n "$CONFLICT_MARKERS" ]; then
        log_warn "Arquivos com marcadores de conflito encontrados (sem estado de merge ativo)"
        log_warn "Arquivos: $(echo $CONFLICT_MARKERS | tr '\n' ' ')"
    fi
fi

log_ok "Ambiente validado"

# =============================================================================
#  PASSO 1: Corrigir .gitignore
# =============================================================================
log_info "PASSO 1/10: Corrigindo .gitignore..."

cat > .gitignore << 'GITIGNORE_EOF'
docs/UX/mockups.zip

# -- Python --
__pycache__/
*.py[cod]
*$py.class
*.so

# -- Environment & Secrets --
.env
.env.*
!.env.example
!.env.template

# -- Build artifacts --
build/
dist/
*.egg-info/
*.egg

# -- IDE & Editor --
.idea/
.vscode/
*.swp
*.swo
*~

# -- OS files --
.DS_Store
Thumbs.db

# -- BuildToFlip internal --
.buildtoflip/ledger/

# -- Logs --
logs/
*.log

# -- Testing / Coverage --
htmlcov/
.coverage
.coverage.*
coverage.xml
*.cover
.pytest_cache/

# -- Java (secondary stack) --
target/
.m2/
*.jar
*.war
*.class

# -- Terraform --
.terraform/
*.tfstate
*.tfstate.*
*.tfplan

# -- Node (if any) --
node_modules/

# -- Docker volumes (local) --
docker/data/
GITIGNORE_EOF

log_ok ".gitignore corrigido"

# =============================================================================
#  PASSO 2: Remover secrets do Git (git rm --cached)
# =============================================================================
log_info "PASSO 2/10: Removendo secrets do controle de versao..."

# Remover .env.prod e .env.dev do index (mantem localmente)
git rm --cached .env.prod 2>/dev/null || log_warn ".env.prod ja nao estava no index"
git rm --cached .env.dev 2>/dev/null || log_warn ".env.dev ja nao estava no index"

# Verificar outros .env files acidentalmente commitados
for ENV_FILE in $(git ls-files | grep "^\.env" || true); do
    case "$ENV_FILE" in
        .env.example|.env.template) 
            log_info "Mantendo $ENV_FILE (template)"
            ;;
        *) 
            log_warn "Removendo $ENV_FILE do index"
            git rm --cached "$ENV_FILE" 2>/dev/null || true
            ;;
    esac
done

log_ok "Secrets removidos do Git index"

# =============================================================================
#  PASSO 3: Corrigir requirements.txt (resolver conflito)
# =============================================================================
log_info "PASSO 3/10: Corrigindo requirements.txt..."

cat > requirements.txt << 'REQ_EOF'
# Production dependencies - Central de Inteligencia Juridica
fastapi==0.111.0
uvicorn[standard]==0.29.0
httpx==0.27.2
redis==4.6.0
prometheus-client==0.17.1
PyJWT==2.8.0
pydantic==2.6.0
pydantic-settings==2.1.0
python-dotenv==1.0.1
tenacity==8.2.3
numpy>=1.22.0,<2.0.0
chromadb==0.4.22
sentence-transformers==2.2.2
langchain>=0.1.0
langchain-openai>=0.0.5
openai>=1.0.0
REQ_EOF

log_ok "requirements.txt corrigido (httpx upgradado para 0.27.2 - CVE fix)"

# =============================================================================
#  PASSO 4: Corrigir requirements-dev.txt (resolver conflito)
# =============================================================================
log_info "PASSO 4/10: Corrigindo requirements-dev.txt..."

cat > requirements-dev.txt << 'REQDEV_EOF'
# Development dependencies
-r requirements.txt

pytest==8.0.0
pytest-asyncio==0.23.3
pytest-cov==4.1.0
respx==0.20.2
black==24.2.0
flake8==7.0.0
bandit==1.7.7
mypy==1.8.0
REQDEV_EOF

log_ok "requirements-dev.txt corrigido"

# =============================================================================
#  PASSO 5: Corrigir src/api/auth.py (JWT + REQUIRED=True)
# =============================================================================
log_info "PASSO 5/10: Corrigindo auth.py (JWT secret + REQUIRED=True)..."

cat > src/api/auth.py << 'AUTH_EOF'
"""JWT-based authentication helpers for the public API.

SECURITY: JWT_SECRET environment variable is REQUIRED (min 32 chars).
The application will raise RuntimeError if JWT_SECRET is not set.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


class AuthManager:
    """Utility class to create and validate JWT tokens.

    IMPORTANT: ``SECRET_KEY`` is loaded from the ``JWT_SECRET``
    environment variable. If not set (and not in test env), RuntimeError
    is raised to prevent accidental insecure deployment.
    """

    ALGORITHM: str = "HS256"
    REQUIRED: bool = True  # SECURITY: Changed from False to True

    # Load secret from environment (no fallback default)
    _raw_secret: str = os.environ.get("JWT_SECRET", "")
    if len(_raw_secret) < 32 and os.environ.get("ENVIRONMENT", "") != "test":
        raise RuntimeError(
            "JWT_SECRET environment variable must be set (min 32 characters). "
            "Generate: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    SECRET_KEY: str = _raw_secret

    @classmethod
    def configure(
        cls,
        secret_key: Optional[str] = None,
        algorithm: Optional[str] = None,
        required: Optional[bool] = None,
    ) -> None:
        """Override class-level settings. Primarily used for testing."""
        if secret_key is not None:
            cls.SECRET_KEY = secret_key
        if algorithm is not None:
            cls.ALGORITHM = algorithm
        if required is not None:
            cls.REQUIRED = required

    @classmethod
    def create_token(cls, user_id: str, expires_in_hours: int = 24) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "exp": now + timedelta(hours=expires_in_hours),
            "iat": now,
        }
        return jwt.encode(payload, cls.SECRET_KEY, algorithm=cls.ALGORITHM)

    @classmethod
    async def verify_token(
        cls, credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> str:
        if credentials is None:
            if cls.REQUIRED:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication credentials were not provided",
                )
            return "anonymous"

        token = credentials.credentials
        try:
            payload = jwt.decode(token, cls.SECRET_KEY, algorithms=[cls.ALGORITHM])
            return str(payload["sub"])
        except jwt.ExpiredSignatureError as exc:  # pragma: no cover
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expirado",
            ) from exc
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            ) from exc


__all__ = ["AuthManager", "security"]
AUTH_EOF

log_ok "auth.py corrigido (REQUIRED=True, JWT_SECRET required from env)"

# =============================================================================
#  PASSO 6: Corrigir src/utils/input_sanitizer.py (manter versao segura)
# =============================================================================
log_info "PASSO 6/10: Corrigindo input_sanitizer.py (versao com seguranca real)..."

cat > src/utils/input_sanitizer.py << 'SANITIZER_EOF'
"""Basic Input Sanitizer for security purposes.

Phase 1 Fix: Keeps full security sanitization with corrected ordering
(strip chars BEFORE html.escape to prevent &amp; from being stripped).
"""

from __future__ import annotations

import html
import re
from typing import Dict


class InputSanitizer:
    """Provide protection against malicious input patterns.

    Sanitisation pipeline (order matters):
        1. Length truncation (prevent resource exhaustion)
        2. Strip disallowed characters
        3. Remove suspicious regex patterns
        4. HTML-escape remaining content
        5. Collapse whitespace
    """

    def __init__(self, max_length: int = 1000) -> None:
        self.max_length = max_length
        self.suspicious_patterns = [
            r"<script.*?>.*?</script>",
            r"javascript:",
            r"on\w+=",
            r"union.*select",
            r"drop\s+table",
            r"insert\s+into",
            r"delete\s+from",
            r"<\?php",
            r"\.\./",
            r"\.\.\\",
            r"(\\x[0-9a-fA-F]{2})+",
        ]
        self.allowed_chars = (
            r"a-zA-Z0-9"
            r"áéíóúâêîôûãõàèìòùç"
            r"ÁÉÍÓÚÂÊÎÔÛÃÕÀÈÌÒÙÇ"
            r"\s\.,\-_:;?!@#\$%&\*\(\)\[\]\{\}\&;"
        )

    def sanitize_text(self, text: str) -> str:
        """Sanitize a text input removing suspicious patterns and limiting size."""

        if not text or not isinstance(text, str):
            return ""

        # 1. Truncate first to prevent DoS on regex
        sanitized = text[:self.max_length]

        # 2. Remove suspicious patterns FIRST (before char stripping)
        for pattern in self.suspicious_patterns:
            sanitized = re.sub(
                pattern, "[REMOVED]", sanitized, flags=re.IGNORECASE | re.DOTALL
            )

        # 3. Strip disallowed characters
        sanitized = re.sub(f"[^{self.allowed_chars}]", "", sanitized)

        # 4. HTML-escape remaining content
        sanitized = html.escape(sanitized)

        # 5. Collapse whitespace and trim
        sanitized = re.sub(r"\s+", " ", sanitized).strip()
        return sanitized

    def is_safe_input(self, text: str) -> bool:
        """Check if input contains potentially dangerous patterns."""

        if not text or not isinstance(text, str):
            return True

        lowered = text.lower()
        for pattern in self.suspicious_patterns:
            if re.search(pattern, lowered, flags=re.IGNORECASE | re.DOTALL):
                return False

        if re.search(f"[^{self.allowed_chars}]", text):
            return False
        return True

    def validate_and_sanitize(self, text: str) -> Dict[str, str | bool]:
        """Validate input and return sanitized version with validation result."""

        sanitized = self.sanitize_text(text)
        is_safe = self.is_safe_input(text)
        return {
            "original": text,
            "sanitized": sanitized,
            "is_safe": is_safe,
            "was_modified": text != sanitized if text else False,
        }


__all__ = ["InputSanitizer"]
SANITIZER_EOF

log_ok "input_sanitizer.py corrigido (sanitizacao real, ordering fix)"

# =============================================================================
#  PASSO 7: Corrigir src/core/safe_agent_base.py (merge com guardrails reais)
# =============================================================================
log_info "PASSO 7/10: Corrigindo safe_agent_base.py (guardrails reais)..."

cat > src/core/safe_agent_base.py << 'SAFEAGENT_EOF'
"""Safety-focused base agent with guardrails used across the platform.

Phase 1 Fix: Merged HEAD structure with codex guardrails.
Real guardrails: loop protection, capability whitelisting, decision ledger.
"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, Iterable, Optional, Protocol
import re

logger = logging.getLogger(__name__)

CapabilityHandler = Callable[[str, Optional[str]], Dict[str, Any]]


class Guardrail(Protocol):
    """Protocol that all guardrails must implement."""

    name: str

    def validate(self, pattern: str) -> bool:
        """Return True if the pattern passes guardrail checks."""


@dataclass
class RegisteredCapability:
    """Metadata describing a capability available to the agent."""

    name: str
    handler: CapabilityHandler
    description: str = ""
    allowed_tools: Iterable[str] = field(default_factory=tuple)


@dataclass
class GuardrailSuite:
    """Container responsible for evaluating guardrail compliance."""

    guardrails: Iterable[Guardrail]

    def validate_pattern_safety(self, pattern: str) -> bool:
        return all(guardrail.validate(pattern) for guardrail in self.guardrails)


class InputSanitizerGuard:
    """Real input sanitization guardrail."""

    name = "input_sanitizer_guard"

    def __init__(self) -> None:
        self._suspicious_patterns = [
            (r"<script.*?>.*?</script>", re.IGNORECASE | re.DOTALL),
            (r"javascript:", re.IGNORECASE),
            (r"on\w+\s*=", re.IGNORECASE),
            (r"union\s+.*select", re.IGNORECASE | re.DOTALL),
            (r"drop\s+table", re.IGNORECASE),
            (r"insert\s+into", re.IGNORECASE),
            (r"delete\s+from", re.IGNORECASE),
            (r"<\?php", re.IGNORECASE),
            (r"\.\./", 0),
            (r"\.\.\\\\", 0),
        ]

    def validate(self, pattern: str) -> bool:
        for pat, flags in self._suspicious_patterns:
            if re.search(pat, pattern, flags):
                logger.warning("InputSanitizerGuard: blocked suspicious pattern '%s'", pat)
                return False
        return True


class OutputValidatorGuard:
    """Validates output for ethical and safety boundaries."""

    name = "output_validator_guard"

    def validate(self, pattern: str) -> bool:
        if not pattern or len(pattern.strip()) < 1:
            return False
        return True


class EthicalBoundaryGuard:
    """Checks for ethically sensitive content."""

    name = "ethical_boundary_guard"

    def validate(self, pattern: str) -> bool:
        lower = pattern.lower()
        blocked_terms = ["senha", "password", "credencial", "private_key"]
        for term in blocked_terms:
            if term in lower:
                logger.warning("EthicalBoundaryGuard: flagged sensitive content")
                return False
        return True


class ResourceLimitGuard:
    """Enforces resource usage limits."""

    name = "resource_limit_guard"
    MAX_TASK_LENGTH = 5000

    def validate(self, pattern: str) -> bool:
        if len(pattern) > self.MAX_TASK_LENGTH:
            logger.warning("ResourceLimitGuard: task exceeds max length")
            return False
        return True


class SafeAgentBase:
    """Base class embedding mandatory guardrails for all agents.

    Guardrails enforced:
        1. **Input sanitisation**  - Suspicious patterns are blocked.
        2. **Loop protection**      - SHA-256 fingerprinting prevents repetition.
        3. **Capability whitelisting** - Only registered capabilities execute.
        4. **Resource limits**       - Task length enforcement.
    """

    def __init__(self, *, max_repeated_tasks: int = 3) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.guardrails = GuardrailSuite(self._initialize_guardrails())
        self.max_repeated_tasks = max(1, max_repeated_tasks)
        self._recent_tasks: Deque[str] = deque(
            maxlen=self.max_repeated_tasks * 2
        )
        self._capabilities: Dict[str, RegisteredCapability] = {}
        self._tools_in_use: Counter[str] = Counter()

    def _initialize_guardrails(self) -> list[Guardrail]:
        return [
            InputSanitizerGuard(),
            OutputValidatorGuard(),
            EthicalBoundaryGuard(),
            ResourceLimitGuard(),
        ]

    def add_capability(
        self,
        name: str,
        handler: CapabilityHandler | None = None,
        *,
        description: str = "",
        allowed_tools: Iterable[str] | None = None,
    ) -> None:
        """Register a new capability guarded by the whitelist."""
        if not name:
            raise ValueError("Capability name cannot be empty")
        if name in self._capabilities:
            raise ValueError(f"Capability '{name}' already registered")

        capability = RegisteredCapability(
            name=name,
            handler=handler or (lambda task, ctx: {"result": task}),
            description=description,
            allowed_tools=tuple(allowed_tools or ()),
        )
        self._capabilities[name] = capability
        self.logger.info("Capability registered: %s", name)

    def list_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """Return metadata about registered capabilities."""
        return {
            name: {
                "description": cap.description,
                "allowed_tools": list(cap.allowed_tools),
            }
            for name, cap in self._capabilities.items()
        }

    def execute(
        self,
        task: str,
        context: str | None = None,
        **_kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute a task applying guardrails and loop protection."""
        if not self.guardrails.validate_pattern_safety(task):
            raise ValueError(f"Task failed guardrail validation: {task[:100]}")

        task_fingerprint = self._fingerprint_task(task)
        self._enforce_loop_protection(task_fingerprint)

        capability_name = _kwargs.get("capability", next(iter(self._capabilities), None))
        if capability_name and capability_name in self._capabilities:
            cap = self._capabilities[capability_name]
            result = cap.handler(task, context)
            payload = dict(result)
            payload["capability"] = capability_name
            payload["task"] = task
            return payload

        return {
            "task": task,
            "context": context,
            "completed": True,
            "output": f"executed::{task}",
            "guardrail_violations": 0,
        }

    def execute_tool(self, tool_name: str, **kwargs: Any) -> Dict[str, Any]:
        """Record tool usage ensuring it is approved by an active capability."""
        if tool_name not in self._tools_in_use:
            if not any(
                tool_name in cap.allowed_tools for cap in self._capabilities.values()
            ):
                raise PermissionError(f"Tool '{tool_name}' is not authorised")
        self._tools_in_use[tool_name] += 1
        self.logger.info("Tool executed: %s", tool_name)
        return {"tool": tool_name, "executions": self._tools_in_use[tool_name]}

    def _fingerprint_task(self, task: str) -> str:
        data = task.encode("utf-8", "ignore")
        return hashlib.sha256(data).hexdigest()

    def _enforce_loop_protection(self, fingerprint: str) -> None:
        if fingerprint in self._recent_tasks:
            occurrences = sum(1 for item in self._recent_tasks if item == fingerprint)
            if occurrences >= self.max_repeated_tasks:
                raise RuntimeError(
                    "Loop protection triggered: task repeated excessively"
                )
        self._recent_tasks.append(fingerprint)


@dataclass
class PlanCreation:
    task: str
    memory_context: Optional[str] = None
    memory_accessed: bool = False


@dataclass
class Plan:
    task: str
    creation: PlanCreation


@dataclass
class AgentExecution:
    """Telemetry emitted after executing a task."""

    task: str
    context: Optional[str]
    completed: bool
    resource_usage: float
    guardrail_violations: int
    output: str

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "context": self.context,
            "completed": self.completed,
            "resource_usage": self.resource_usage,
            "guardrail_violations": self.guardrail_violations,
            "output": self.output,
        }


class MemoryManager:
    """Simple memory facade used by emergent behavior tests."""

    def __init__(self) -> None:
        self._last_task: Optional[str] = None
        self._last_context: Optional[str] = None

    def recall(self, task: str) -> str:
        self._last_task = task
        self._last_context = f"contexto recuperado para {task}"
        return self._last_context

    def was_accessed_during(self, creation: PlanCreation) -> bool:
        return (
            creation.memory_accessed
            and creation.memory_context is not None
            and creation.memory_context == self._last_context
        )


__all__ = [
    "SafeAgentBase",
    "Guardrail",
    "GuardrailSuite",
    "RegisteredCapability",
    "Plan",
    "PlanCreation",
    "AgentExecution",
    "MemoryManager",
]
SAFEAGENT_EOF

log_ok "safe_agent_base.py corrigido (guardrails reais implementados)"

# =============================================================================
#  PASSO 8: Corrigir .env.prod (remover credenciais hardcoded)
# =============================================================================
log_info "PASSO 8/10: Limpando .env.prod (remover credenciais hardcoded)..."

cat > .env.prod << 'ENVPROD_EOF'
APP_PORT=8080
DB_HOST=prod-postgres
DB_PORT=5432
DB_NAME=buildtoflip_prod
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
REDIS_HOST=prod-redis
ENVIRONMENT=prod
FEATURE_MOCK_DATA=false
FEATURE_RATE_LIMIT=true
FEATURE_CACHE=true
JWT_SECRET=${JWT_SECRET}

# Grafana (use Docker secrets or vault)
GF_SECURITY_ADMIN_USER=${GF_ADMIN_USER}
GF_SECURITY_ADMIN_PASSWORD=${GF_ADMIN_PASSWORD}
ENVPROD_EOF

log_ok ".env.prod limpo (variaveis de ambiente ao inves de credenciais)"

# =============================================================================
#  PASSO 9: Corrigir docker-compose.yml (remover ports expostos + credenciais)
# =============================================================================
log_info "PASSO 9/10: Corrigindo docker-compose.yml..."

# Corrigir ports expostos do PostgreSQL e Redis
if [ -f "docker-compose.yml" ]; then
    # Remover ports expostos de postgres e redis
    sed -i 's/      - "5432:5432"/      - "127.0.0.1:5432:5432"/' docker-compose.yml 2>/dev/null || true
    sed -i 's/      - "6379:6379"/      - "127.0.0.1:6379:6379"/' docker-compose.yml 2>/dev/null || true

    # Corrigir Grafana credentials
    sed -i 's/GF_SECURITY_ADMIN_PASSWORD: admin/GF_SECURITY_ADMIN_PASSWORD: ${GF_ADMIN_PASSWORD}/' docker-compose.yml 2>/dev/null || true

    log_ok "docker-compose.yml: ports ligados ao localhost, Grafana sem senha padrao"
fi

if [ -f "docker/docker-compose.yml" ]; then
    sed -i 's/      - "5432:5432"/      - "127.0.0.1:5432:5432"/' docker/docker-compose.yml 2>/dev/null || true
    sed -i 's/      - "6379:6379"/      - "127.0.0.1:6379:6379"/' docker/docker-compose.yml 2>/dev/null || true
    sed -i 's/GF_SECURITY_ADMIN_PASSWORD: admin/GF_SECURITY_ADMIN_PASSWORD: ${GF_ADMIN_PASSWORD}/' docker/docker-compose.yml 2>/dev/null || true
    log_ok "docker/docker-compose.yml corrigido"
fi

if [ -f "docker/docker-compose-prod.yml" ]; then
    sed -i 's/POSTGRES_PASSWORD: \${DB_PASSWORD:-nfe123}/POSTGRES_PASSWORD: ${DB_PASSWORD}/' docker/docker-compose-prod.yml 2>/dev/null || true
    sed -i 's/      - "5432:5432"/      - "127.0.0.1:5432:5432"/' docker/docker-compose-prod.yml 2>/dev/null || true
    sed -i 's/      - "6379:6379"/      - "127.0.0.1:6379:6379"/' docker/docker-compose-prod.yml 2>/dev/null || true
    sed -i 's/GF_SECURITY_ADMIN_PASSWORD: admin/GF_SECURITY_ADMIN_PASSWORD: ${GF_ADMIN_PASSWORD}/' docker/docker-compose-prod.yml 2>/dev/null || true
    log_ok "docker/docker-compose-prod.yml corrigido"
fi

# =============================================================================
#  PASSO 10: Corrigir docker/Dockerfile (adicionar non-root user)
# =============================================================================
log_info "PASSO 10/10: Corrigindo Dockerfiles..."

if [ -f "docker/Dockerfile" ]; then
    # Verificar se ja tem USER
    if ! grep -q "^USER " docker/Dockerfile 2>/dev/null; then
        # Adicionar non-root user antes do ENTRYPOINT
        sed -i '/^ENTRYPOINT/i RUN groupadd -r appuser \&\& useradd -r -g appuser appuser\nUSER appuser\n' docker/Dockerfile 2>/dev/null || true
        log_ok "docker/Dockerfile: non-root user adicionado"
    else
        log_ok "docker/Dockerfile: ja possui non-root user"
    fi
fi

if [ -f "Dockerfile" ]; then
    # Verificar se esta instalando requirements-dev.txt
    if grep -q "requirements-dev" Dockerfile 2>/dev/null; then
        sed -i '/requirements-dev/d' Dockerfile 2>/dev/null || true
        log_warn "Dockerfile: removida instalacao de requirements-dev.txt em producao"
    fi
fi

# =============================================================================
#  RESUMO E VALIDACAO FINAL
# =============================================================================
echo ""
echo "=========================================================================="
echo -e "${GREEN}  FASE 1 CONCLUIDA - Resumo das correcoes aplicadas${NC}"
echo "=========================================================================="
echo ""
echo "  [1] .gitignore              - Completo (Python, Java, Terraform, IDE, secrets)"
echo "  [2] Secrets removidos       - .env.prod e .env.dev removidos do Git index"
echo "  [3] requirements.txt         - httpx 0.27.2 (CVE fix), deps consolidadas"
echo "  [4] requirements-dev.txt     - pytest-cov, bandit, black adicionados"
echo "  [5] src/api/auth.py          - REQUIRED=True, JWT_SECRET required from env"
echo "  [6] src/utils/input_sanitizer - Sanitizacao real com ordering corrigido"
echo "  [7] src/core/safe_agent_base - Guardrails reais (loop, whitelist, limits)"
echo "  [8] .env.prod               - Sem credenciais hardcoded"
echo "  [9] docker-compose.yml      - Ports localhost, Grafana sem default"
echo " [10] Dockerfiles              - Non-root user, sem dev-deps em prod"
echo ""
echo "=========================================================================="
echo -e "${YELLOW}  ACOES MANUAIS AINDA NECESSARIAS:${NC}"
echo "=========================================================================="
echo ""
echo "  1. ROTACIONAR CREDENCIAIS IMEDIATAMENTE:"
echo "     - Gerar novo JWT_SECRET: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
echo "     - Rotacionar DB password (produser/prodpass esta comprometida)"
echo "     - Rotacionar Grafana password (admin/admin esta comprometida)"
echo ""
echo "  2. CONFIGURAR .env.prod COM VALORES REAIS:"
echo "     - Copiar .env.prod e preencher com credenciais novas"
echo "     - NUNCA commitar .env.prod novamente"
echo ""
echo "  3. RESOLVER CONFLITOS DE MERGE RESTANTES:"
echo "     - Os arquivos com conflitos maiores (supervisor_agent.py,"
echo "       tribunal_agent.py, architect_agent.py, api/main.py)"
echo "       precisam ser resolvidos manualmente ou via git mergetool"
echo "     - Execute: git mergetool"
echo ""
echo "  4. COMMITAR CORRECOES:"
echo "     git add -A"
echo "     git commit -m \"fix(phase1): security hardening - JWT, auth, sanitizer, gitignore\""
echo ""
echo "=========================================================================="
echo -e "${RED}  ATENCAO: Os 10+ arquivos com conflitos de merge maiores${NC}"
echo -e "${RED}  (supervisor, tribunal, architect, api/main, etc.) PRECISAM${NC}"
echo -e "${RED}  ser resolvidos separadamente. Veja o script fase1-merge.sh${NC}"
echo "=========================================================================="
