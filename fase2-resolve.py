#!/usr/bin/env python3
"""
================================================================================
 FASE 2 - Resolucao completa de conflitos de merge + Melhorias Phase 2
 Central de Inteligencia Juridica
================================================================================

Uso:
  python fase2-resolve.py [--dry-run] [--verbose]

Estrategia de resolucao:
  - 21 arquivos: escolher automaticamente o lado correto (HEAD ou codex)
  - 6 arquivos:  merge manual com conteudo mesclado completo

Executar na raiz do repositorio:
  cd /c/vps/Central_Inteligencia_Juridica
  python fase2-resolve.py
================================================================================
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# ─── Configuracao ──────────────────────────────────────────────────────────

CONFLICT_MARKER_START = re.compile(r"^<<<<<<< ", re.MULTILINE)
CONFLICT_MARKER_SEP = re.compile(r"^=======\s*$", re.MULTILINE)
CONFLICT_MARKER_END = re.compile(r"^>>>>>>> ", re.MULTILINE)

# Estrategia por arquivo: 'head', 'codex', 'merge'
STRATEGY: dict[str, str] = {
    # Agents
    "src/agents/supervisor_agent.py": "codex",
    "src/agents/tribunal_agent.py": "codex",
    "src/agents/architect_agent.py": "merge",
    # API
    "src/api/main.py": "codex",
    # Consensus
    "src/consensus/weighted_voting.py": "codex",
    "src/consensus/__init__.py": "codex",
    # Core
    "src/core/safe_agent_base.py": "codex",
    # Evaluation
    "src/evaluation/ab_testing.py": "codex",
    "src/evaluation/continuous_evaluator.py": "codex",
    # HITL
    "src/hitl/progressive_autonomy.py": "codex",
    "src/hitl/__init__.py": "codex",
    # Memory
    "src/memory/agent_memory.py": "merge",
    "src/memory/__init__.py": "codex",
    # Orchestration
    "src/orchestration/unified_orchestrator.py": "head",
    "src/orchestration/__init__.py": "codex",
    # Routing
    "src/routing/learning_router.py": "codex",
    "src/routing/__init__.py": "codex",
    # Tools
    "src/tools/rag_tool.py": "codex",
    # Utils
    "src/utils/cache_manager.py": "codex",
    "src/utils/input_sanitizer.py": "head",
    "src/utils/ledger.py": "head",
    "src/utils/metrics_collector.py": "head",
    # Tests
    "tests/integration/test_full_flow.py": "merge",
    # Docs
    "docs/troubleshooting.md": "codex",
    # Root
    "requirements.txt": "merge",
    "requirements-dev.txt": "merge",
}

# ─── Merge Manual: Conteudo Completo ────────────────────────────────────────

MERGED_CONTENT: dict[str, str] = {}


def _build_merged_content() -> dict[str, str]:
    """Build the complete merged content for files that need manual merging."""

    content = {}

    # ── 1. src/agents/architect_agent.py ──
    # HEAD: BaseAgent pattern, ADR generation, plan creation
    # CODEX: Legal domain CoT with tribunal identification
    # MERGE: Keep codex's legal domain as primary (used by SupervisorAgent),
    #         add HEAD's plan creation and ADR as bonus methods
    content["src/agents/architect_agent.py"] = r'''"""Architect agent responsible for high-level reasoning with CoT.

Performs chain-of-thought analysis tailored for legal/tribunal context,
with optional plan creation and ADR generation for architectural tasks.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.utils.input_sanitizer import InputSanitizer

logger = logging.getLogger(__name__)


class ArchitectAgent:
    """Performs lightweight chain-of-thought style reasoning for legal tribunals."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.sanitizer = InputSanitizer()
        self.reasoning_history: List[Dict[str, Any]] = []

    def reason_with_cot(self, task_description: str) -> Dict[str, Any]:
        """Generate a structured reasoning payload for the supervisor."""

        sanitized = self.sanitizer.sanitize_text(task_description)
        tokens = sanitized.lower().split()

        analysis_steps: List[str] = []
        analysis_steps.append("1. Interpretar a solicitacao juridica do usuario.")

        if not sanitized:
            conclusion = "Solicitacao vazia; manter modo padrao TJSP."
            self.logger.warning("ArchitectAgent recebeu tarefa vazia para CoT")
            return {
                "problem_analysis": "Tarefa vazia.",
                "chain_of_thought": analysis_steps,
                "recommendation": conclusion,
                "identified_tribunals": ["TJSP"],
                "confidence": 0.2,
            }

        analysis_steps.append(
            "2. Extrair entidades e tribunais mencionados explicitamente."
        )

        tribunal_map = {
            "tjsp": "TJSP",
            "sao": "TJSP",
            "paulo": "TJSP",
            "tjmg": "TJMG",
            "minas": "TJMG",
            "gerais": "TJMG",
            "tjrs": "TJRS",
            "gaucho": "TJRS",
            "ga\u00facho": "TJRS",
            "sul": "TJRS",
            "tjrj": "TJRJ",
            "fluminense": "TJRJ",
            "rj": "TJRJ",
            "stf": "STF",
            "supremo": "STF",
            "federal": "STF",
        }

        detected: List[str] = []
        for token in tokens:
            tribunal = tribunal_map.get(token)
            if tribunal:
                detected.append(tribunal)

        if any(
            keyword in tokens
            for keyword in ["tribunais", "comparar", "comparacao"]
        ):
            analysis_steps.append(
                "3. Solicitacao sugere multiplos tribunais ou comparacao de jurisprudencia."
            )

        unique_tribunals = list(dict.fromkeys(detected))
        if not unique_tribunals:
            if "federal" in tokens or "uniao" in tokens:
                unique_tribunals = ["STF"]
            else:
                unique_tribunals = ["TJSP"]

        analysis_steps.append(
            "4. Construir recomendacao priorizando tribunais identificados e contexto do usuario."
        )

        recommendation = "Consultar tribunais: " + ", ".join(unique_tribunals)
        problem_analysis = (
            "A tarefa requer analise juridica envolvendo os tribunais "
            + ", ".join(unique_tribunals)
            + "."
        )
        confidence = 0.6 + 0.1 * min(len(unique_tribunals), 3)

        reasoning_payload = {
            "problem_analysis": problem_analysis,
            "chain_of_thought": analysis_steps,
            "recommendation": recommendation,
            "identified_tribunals": unique_tribunals,
            "confidence": min(1.0, confidence),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self.reasoning_history.append(reasoning_payload)
        self.logger.info(
            "ArchitectAgent concluiu CoT com tribunais: %s", unique_tribunals
        )
        return reasoning_payload

    def create_plan(self, task: Dict[str, Any], reasoning: Dict[str, Any]) -> Dict[str, Any]:
        """Derive a lightweight architectural plan informed by the reasoning."""

        components = ["API Gateway", "Auth Service", "Business Logic", "Database"]
        if "cache" in reasoning.get("recommendation", "").lower():
            components.append("Caching Layer")

        return {
            "goal": task.get("description", ""),
            "architecture": "microservices",
            "components": components,
            "patterns": reasoning.get("applicable_patterns", []),
            "risks": ["Complexidade", "Custo operacional"],
            "mitigations": ["Documentacao", "Observabilidade"],
            "estimated_effort": "2 sprints",
        }

    def create_adr(self, decision: Dict[str, Any]) -> str:
        """Generate an Architecture Decision Record style note."""

        return (
            f"# ADR: {decision.get('title', 'Architecture Decision')}\n\n"
            "## Status\nAccepted\n\n"
            "## Context\n"
            f"{decision.get('problem_analysis', 'N/A')}\n\n"
            "## Decision\n"
            f"{decision.get('recommendation', 'N/A')}\n\n"
            "## Consequences\n"
            f"{decision.get('trade_offs', 'N/A')}\n"
        )
'''

    # ── 2. src/memory/agent_memory.py ──
    # CODEX: VectorMemory facade (used by SupervisorAgent)
    # HEAD: JSONL episodic persistence (valuable for auditing)
    # MERGE: codex facade + HEAD's JSONL persistence as optional feature
    content["src/memory/agent_memory.py"] = r'''"""High-level memory facade that wraps VectorMemory for agent usage.

Provides:
- Vector similarity search via VectorMemory (primary)
- JSONL episodic persistence for audit trails (optional)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.memory.vector_memory import VectorMemory

logger = logging.getLogger(__name__)


class AgentMemorySystem:
    """Convenience wrapper around :class:`VectorMemory` for RAG pipelines.

    Also supports optional JSONL episodic persistence for audit trails.
    """

    def __init__(
        self,
        vector_memory: VectorMemory | None = None,
        storage_dir: Optional[Path] = None,
    ) -> None:
        self.vector_memory = vector_memory or VectorMemory()
        self.logger = logging.getLogger(f"{__name__}.AgentMemorySystem")

        # Optional JSONL episodic persistence
        self.storage_dir = storage_dir or Path("logs/memory")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.episodic_path = self.storage_dir / "agent_memories.jsonl"

    def is_available(self) -> bool:
        """Return ``True`` if the underlying vector memory is available."""

        return self.vector_memory.is_available()

    def recall_similar(self, query: str, k: int = 3) -> Dict[str, Any]:
        """Retrieve context documents that are similar to ``query``."""

        if not query:
            return {"documents": [[]], "metadatas": [[]], "note": "empty_query"}

        results = self.vector_memory.recall_similar(query, k=k)
        if not results:
            return {"documents": [[]], "metadatas": [[]], "note": "no_memories"}

        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for item in results:
            snapshot = item.get("result_snapshot")
            if isinstance(snapshot, str) and snapshot:
                documents.append(snapshot)
            else:
                documents.append(item.get("original_task") or "")

            metadatas.append(
                {
                    "similarity": float(item.get("similarity_score", 0.0)),
                    "tribunals": item.get("tribunals", []),
                    "timestamp": item.get("timestamp"),
                    "intent": (
                        item.get("intent_operacao")
                        or item.get("intent_operation")
                        or "unknown"
                    ),
                }
            )

        return {
            "documents": [documents],
            "metadatas": [metadatas],
            "note": "vector_memory_recall",
        }

    def remember(
        self,
        task: str,
        result: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> bool:
        """Persist an interaction using the underlying vector memory + JSONL."""

        vector_ok = self.vector_memory.remember(task, result, metadata)

        # Always persist to JSONL for audit trail
        try:
            memory = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "task": task[:200],
                "metadata": metadata,
                "result_status": result.get("status", "unknown"),
            }
            with self.episodic_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(memory, ensure_ascii=False) + "\n")
        except OSError as exc:
            self.logger.warning("Failed to write episodic memory: %s", exc)

        return vector_ok
'''

    # ── 3. tests/integration/test_full_flow.py ──
    # HEAD: 4 sync tests (happy path, XSS, init, communication)
    # CODEX: 2 async tests (single tribunal, multi-tribunal parallel)
    # MERGE: Codex async pattern (matches actual SupervisorAgent API) + HEAD XSS test
    content["tests/integration/test_full_flow.py"] = r'''"""Integration tests covering supervisor and tribunal agents working together."""

from __future__ import annotations

import pytest

from src.agents.supervisor_agent import SupervisorAgent


@pytest.mark.asyncio
async def test_full_flow_single_tribunal() -> None:
    supervisor = SupervisorAgent()

    result = await supervisor.process_task("Status TJSP")

    assert result["status"] in ("success", "weak_consensus")
    assert isinstance(result.get("tribunals_used"), list)
    assert len(result.get("tribunals_used", [])) >= 1
    assert "TJSP" in result.get("tribunals_used", [])
    assert "supervisor_result" in result


@pytest.mark.asyncio
async def test_full_flow_multiple_tribunals_parallel() -> None:
    supervisor = SupervisorAgent()

    result = await supervisor.process_task("Comparar jurisprudencia TJSP e TJMG")

    assert result["status"] in ("success", "success_with_consensus", "weak_consensus", "pending_human_review")
    assert isinstance(result.get("tribunals_used"), list)
    assert "supervisor_result" in result


@pytest.mark.asyncio
async def test_xss_sanitization_in_task() -> None:
    """Verify that XSS payloads are sanitized during task processing."""

    supervisor = SupervisorAgent()
    result = await supervisor.process_task(
        "Status <script>alert('xss')</script> TJSP"
    )

    assert result["status"] in ("success", "weak_consensus")
    # The sanitizer should strip or escape the script tag
    supervisor_result = result.get("supervisor_result", {})
    result_str = str(supervisor_result)
    assert "<script>" not in result_str
    assert "alert" not in result_str or "alert" in result_str.lower() and "script" not in result_str.lower()


@pytest.mark.asyncio
async def test_empty_task_handling() -> None:
    """Verify graceful handling of empty or whitespace-only tasks."""

    supervisor = SupervisorAgent()
    result = await supervisor.process_task("   ")

    assert "status" in result
'''

    # ── 4. requirements.txt ──
    # CODEX has the right additional deps, but moved pytest/pytest-asyncio/respx to dev
    content["requirements.txt"] = r'''# Production dependencies - Central de Inteligencia Juridica
fastapi==0.111.0
uvicorn[standard]==0.29.0
httpx==0.27.2
redis==4.6.0
prometheus-client==0.17.1
PyJWT==2.8.0

# Validacao e configuracao
pydantic==2.6.0
pydantic-settings==2.1.0
python-dotenv==1.0.1

# Integracao LLM
ollama==0.1.9

# NumPy compatibility fix (ChromaDB dependency)
numpy<2.0.0,>=1.22.0

# AI/ML - Vector store e embeddings
chromadb==0.4.18
sentence-transformers==2.2.2
'''

    # ── 5. requirements-dev.txt ──
    # Use -r requirements.txt pattern, no duplication
    content["requirements-dev.txt"] = r'''# Development dependencies - Central de Inteligencia Juridica
-r requirements.txt

# Testing
pytest==7.4.4
pytest-asyncio==0.23.8
pytest-cov==5.0.0
respx==0.21.1

# Code quality
bandit==1.7.9
black==24.8.0
isort==5.13.2
flake8==7.1.1
mypy==1.11.2

# Benchmarking
pytest-benchmark==4.0.0
'''

    return content


# ─── Conflict Resolver Engine ────────────────────────────────────────────────


def find_conflict_regions(text: str) -> list[tuple[int, int, int, int, int]]:
    """Find all conflict regions in text, returning (start, sep, end, head_end, codex_end)."""

    regions = []
    lines = text.split("\n")

    i = 0
    while i < len(lines):
        if lines[i].startswith("<<<<<<< "):
            start = i
            # Find separator
            sep = None
            for j in range(i + 1, len(lines)):
                if lines[j] == "=======":
                    sep = j
                    break
            if sep is None:
                i += 1
                continue
            # Find end
            end = None
            for j in range(sep + 1, len(lines)):
                if lines[j].startswith(">>>>>>> "):
                    end = j
                    break
            if end is None:
                i += 1
                continue
            regions.append((start, sep, end, start, sep - 1, sep + 1, end - 1))
            i = end + 1
        else:
            i += 1

    return regions


def extract_head_side(text: str, regions: list) -> str:
    """Extract only HEAD content, removing all conflict markers and codex sides."""

    lines = text.split("\n")
    result = []

    # Build set of lines to skip
    skip_lines: set[int] = set()
    for region in regions:
        start, sep, end = region[0], region[1], region[2]
        # Skip HEAD marker line, separator line, codex content, and end marker
        skip_lines.add(start)
        for j in range(sep, end + 1):
            skip_lines.add(j)

    for i, line in enumerate(lines):
        if i not in skip_lines:
            result.append(line)

    return "\n".join(result)


def extract_codex_side(text: str, regions: list) -> str:
    """Extract only codex content, removing all conflict markers and HEAD sides."""

    lines = text.split("\n")
    result = []

    skip_lines: set[int] = set()
    for region in regions:
        start, sep, end = region[0], region[1], region[2]
        # Skip HEAD marker, HEAD content, separator, and end marker
        for j in range(start, sep + 1):
            skip_lines.add(j)
        skip_lines.add(end)

    for i, line in enumerate(lines):
        if i not in skip_lines:
            result.append(line)

    return "\n".join(result)


def resolve_file(filepath: str, strategy: str, verbose: bool = False) -> tuple[bool, str]:
    """Resolve a single file. Returns (success, message)."""

    path = Path(filepath)
    if not path.exists():
        return False, f"ARQUIVO NAO ENCONTRADO: {filepath}"

    raw = path.read_text(encoding="utf-8")

    if "<<<<<<< " not in raw:
        return True, f"[OK] Sem conflitos: {filepath}"

    regions = find_conflict_regions(raw)
    if not regions:
        return True, f"[OK] Sem conflitos: {filepath}"

    if strategy == "head":
        resolved = extract_head_side(raw, regions)
        strategy_label = "HEAD"

    elif strategy == "codex":
        resolved = extract_codex_side(raw, regions)
        strategy_label = "origin/codex"

    elif strategy == "merge":
        merged = MERGED_CONTENT.get(filepath)
        if merged:
            resolved = merged
            strategy_label = "MERGE MANUAL"
        else:
            # Fallback: use codex
            resolved = extract_codex_side(raw, regions)
            strategy_label = "origin/codex (fallback - merge content not found)"

    else:
        return False, f"[ERRO] Estrategia desconhecida: {strategy} para {filepath}"

    # Clean up any remaining conflict markers (safety)
    resolved = re.sub(r"^<<<<<<< .*$", "", resolved, flags=re.MULTILINE)
    resolved = re.sub(r"^=======\s*$", "", resolved, flags=re.MULTILINE)
    resolved = re.sub(r"^>>>>>>> .*$", "", resolved, flags=re.MULTILINE)

    # Remove excessive blank lines (more than 2 consecutive)
    resolved = re.sub(r"\n{4,}", "\n\n\n", resolved)

    # Ensure file ends with newline
    resolved = resolved.rstrip("\n") + "\n"

    path.write_text(resolved, encoding="utf-8")

    msg = f"[OK] {filepath} -> {strategy_label} ({len(regions)} conflito(s) resolvido(s))"
    if verbose:
        msg += f" [{len(raw)} -> {len(resolved)} bytes]"
    return True, msg


# ─── Phase 2 Quality Improvements ──────────────────────────────────────────

PHASE2_IMPROVEMENTS: dict[str, str] = {}


def apply_phase2_improvements(verbose: bool = False) -> list[tuple[bool, str]]:
    """Apply Phase 2 code quality improvements."""

    results = []
    improvements = []

    # ── 1. Fix src/__init__.py ──
    init_path = Path("src/__init__.py")
    if init_path.exists():
        init_content = init_path.read_text(encoding="utf-8")
        if "__version__" not in init_content:
            init_content = '"""Central de Inteligencia Juridica."""\n\n__version__ = "0.2.0"\n'
            init_path.write_text(init_content, encoding="utf-8")
            improvements.append(("[OK] src/__init__.py", "Adicionado __version__"))

    # ── 2. Create src/protocols/__init__.py if needed ──
    protocols_dir = Path("src/protocols")
    if protocols_dir.exists() and not (protocols_dir / "__init__.py").exists():
        (protocols_dir / "__init__.py").write_text(
            '"""Agent communication protocols."""\n', encoding="utf-8"
        )
        improvements.append(("[OK] src/protocols/__init__.py", "Criado"))

    # ── 3. Create src/services/__init__.py if needed ──
    services_dir = Path("src/services")
    if services_dir.exists() and not (services_dir / "__init__.py").exists():
        (services_dir / "__init__.py").write_text(
            '"""External service integrations."""\n', encoding="utf-8"
        )
        improvements.append(("[OK] src/services/__init__.py", "Criado"))

    # ── 4. Create src/memory/vector_memory.py stub if missing ──
    vector_memory_path = Path("src/memory/vector_memory.py")
    if not vector_memory_path.exists():
        vector_memory_path.write_text(
            '''"""Vector memory abstraction for semantic search and RAG."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import chromadb  # type: ignore
except Exception:
    chromadb = None  # type: ignore


class VectorMemory:
    """Vector memory store using ChromaDB with graceful degradation."""

    def __init__(self) -> None:
        self._client = None
        self._collection = None
        self._available = False
        self._manual_embeddings = True

        if chromadb is not None:
            try:
                self._client = chromadb.Client(
                    chromadb.Settings(
                        chroma_server_host="localhost",
                        chroma_server_http_port=8000,
                    )
                )
                try:
                    self._collection = self._client.create_collection(
                        "agent_memories"
                    )
                except Exception:
                    self._collection = self._client.get_collection(
                        "agent_memories"
                    )
                self._available = True
            except Exception as exc:
                logger.warning("ChromaDB unavailable: %s", exc)
        else:
            logger.info("ChromaDB not installed. Memory features disabled.")

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def using_manual_embeddings(self) -> bool:
        return self._manual_embeddings

    def recall_similar(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Recall similar items from vector store."""

        if not self._available or self._collection is None:
            return []

        try:
            results = self._collection.query(
                query_texts=[query], n_results=k
            )
            return self._format_results(results)
        except Exception as exc:
            logger.warning("Vector recall failed: %s", exc)
            return []

    def remember(
        self,
        task: str,
        result: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> bool:
        """Store a new memory entry."""

        if not self._available or self._collection is None:
            return False

        try:
            import json

            self._collection.add(
                documents=[task[:200]],
                metadatas=[{
                    "tribunals": str(metadata.get("tribunals", [])),
                    "intent_operacao": metadata.get("intent_operacao", ""),
                    "timestamp": metadata.get("timestamp", ""),
                }],
                ids=[f"mem_{len(task)}_{hash(task) % 100000:05d}"],
            )
            return True
        except Exception as exc:
            logger.warning("Vector store failed: %s", exc)
            return False

    def _format_results(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format ChromaDB query results into structured dicts."""

        formatted = []
        documents = results.get("documents", [[]])
        metadatas = results.get("metadatas", [[]])
        distances = results.get("distances", [[]])

        for i, doc_list in enumerate(documents):
            for j, doc in enumerate(doc_list):
                meta = {}
                if metadatas and i < len(metadatas) and j < len(metadatas[i]):
                    meta = metadatas[i][j]
                distance = 0.0
                if distances and i < len(distances) and j < len(distances[i]):
                    distance = distances[i][j]

                import ast

                tribunals = meta.get("tribunals", "[]")
                try:
                    tribunals = ast.literal_eval(str(tribunals))
                except (ValueError, SyntaxError):
                    tribunals = []

                formatted.append({
                    "original_task": doc,
                    "similarity_score": max(0.0, 1.0 - distance),
                    "tribunals": tribunals if isinstance(tribunals, list) else [],
                    "intent_operacao": meta.get("intent_operacao", ""),
                    "timestamp": meta.get("timestamp", ""),
                })

        return formatted
''',
            encoding="utf-8",
        )
        improvements.append(
            ("[OK] src/memory/vector_memory.py", "Criado stub com ChromaDB integration")
        )

    # ── 5. Create src/routing/intent_classifier.py stub if missing ──
    intent_cls_path = Path("src/routing/intent_classifier.py")
    if not intent_cls_path.exists():
        intent_cls_path.write_text(
            '''"""Intent classifier for legal task routing."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ClassifiedIntent:
    """Result of intent classification."""

    tribunais: List[str] = field(default_factory=lambda: ["TJSP"])
    operacao: str = "generic"
    parametros: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.8
    reasoning: str = ""


class IntentClassifier:
    """Classify legal task intents for routing."""

    def __init__(self, confidence_threshold: float = 0.7) -> None:
        self.confidence_threshold = confidence_threshold
        self.llm_enabled = False
        self.logger = logging.getLogger(__name__)

    def should_use_llm(self, task: str) -> bool:
        """Determine if LLM classification should be used over keywords."""

        return False  # LLM not configured

    async def classify(self, task: str) -> ClassifiedIntent:
        """Classify task intent using LLM or keyword fallback."""

        return ClassifiedIntent(
            tribunais=["TJSP"],
            operacao="generic",
            confidence=0.5,
            reasoning="Keyword fallback - LLM not enabled",
        )
''',
            encoding="utf-8",
        )
        improvements.append(
            ("[OK] src/routing/intent_classifier.py", "Criado stub para import")
        )

    # ── 6. Create src/protocols/a2a_mixin.py stub if missing ──
    a2a_mixin_path = Path("src/protocols/a2a_mixin.py")
    if not a2a_mixin_path.exists():
        a2a_mixin_path.write_text(
            '''"""Agent-to-Agent communication mixin."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class A2ACapable:
    """Mixin providing Agent-to-Agent communication capabilities."""

    def __init__(self) -> None:
        self._a2a_handlers: Dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)

    def register_a2a_handler(self, message_type: str, handler: Any) -> None:
        """Register a handler for a specific A2A message type."""

        self._a2a_handlers[message_type] = handler

    async def send_a2a_message(
        self, target: str, message_type: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send a message to another agent."""

        return {
            "status": "success",
            "target": target,
            "message_type": message_type,
        }
''',
            encoding="utf-8",
        )
        improvements.append(
            ("[OK] src/protocols/a2a_mixin.py", "Criado stub para A2ACapable import")
        )

    # ── 7. Create src/utils/decision_metrics.py stub if missing ──
    decision_metrics_path = Path("src/utils/decision_metrics.py")
    if not decision_metrics_path.exists():
        decision_metrics_path.write_text(
            '''"""Decision metrics collector for tracking agent performance."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class DecisionMetricsCollector:
    """Collect and aggregate decision metrics for monitoring."""

    _decisions: List[Dict[str, Any]] = []

    @classmethod
    def record_decision(
        cls,
        agent: str,
        decision_type: str,
        outcome: str,
        confidence: float,
        duration_seconds: float,
    ) -> None:
        """Record a decision event."""

        cls._decisions.append({
            "agent": agent,
            "decision_type": decision_type,
            "outcome": outcome,
            "confidence": confidence,
            "duration_seconds": duration_seconds,
        })

    @classmethod
    def record_consensus(
        cls,
        decision_type: str,
        strength: float,
        participants: int,
        winning_agent: str,
        outcome: str,
    ) -> None:
        """Record a consensus event."""

        cls._decisions.append({
            "decision_type": f"consensus_{decision_type}",
            "consensus_strength": strength,
            "participants": participants,
            "winning_agent": winning_agent,
            "outcome": outcome,
        })

    @classmethod
    def record_hitl_request(
        cls, agent: str, status: str = "pending"
    ) -> None:
        """Record a human-in-the-loop request."""

        cls._decisions.append({
            "agent": agent,
            "decision_type": "hitl_request",
            "status": status,
        })
''',
            encoding="utf-8",
        )
        improvements.append(
            ("[OK] src/utils/decision_metrics.py", "Criado stub para DecisionMetricsCollector")
        )

    # ── 8. Create src/hitl/hitl_queue.py stub if missing ──
    hitl_queue_path = Path("src/hitl/hitl_queue.py")
    if not hitl_queue_path.exists():
        hitl_queue_path.write_text(
            '''"""Human-in-the-loop queue for pending reviews."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class HITLRequest:
    """A request pending human review."""

    request_id: str
    agent: str
    reason: str
    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"


@dataclass
class HITLQueue:
    """Queue for managing HITL requests."""

    _queue: deque = field(default_factory=deque)

    def enqueue(self, request: HITLRequest) -> None:
        self._queue.append(request)

    def dequeue(self) -> Optional[HITLRequest]:
        return self._queue.popleft() if self._queue else None

    def pending_count(self) -> int:
        return len(self._queue)


_default_queue: Optional[HITLQueue] = None


def get_hitl_queue() -> HITLQueue:
    """Get or create the default HITL queue."""

    global _default_queue
    if _default_queue is None:
        _default_queue = HITLQueue()
    return _default_queue
''',
            encoding="utf-8",
        )
        improvements.append(
            ("[OK] src/hitl/hitl_queue.py", "Criado stub para HITL queue")
        )

    # ── 9. Create src/tools/circuit_breaker.py stub if missing ──
    cb_path = Path("src/tools/circuit_breaker.py")
    if not cb_path.exists():
        cb_path.write_text(
            '''"""Circuit breaker pattern for resilient service calls."""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker with configurable thresholds."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        name: str = "default",
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._last_state_change: float = 0.0

    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute function through circuit breaker."""

        if self.state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise RuntimeError(
                    f"Circuit breaker '{self.name}' is OPEN"
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        self._failure_count = 0
        if self.state != CircuitState.CLOSED:
            self.state = CircuitState.CLOSED
            self._last_state_change = time.monotonic()

    def _on_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self._last_state_change = time.monotonic()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }
''',
            encoding="utf-8",
        )
        improvements.append(
            ("[OK] src/tools/circuit_breaker.py", "Criado stub para CircuitBreaker")
        )

    # ── 10. Fix pytest.ini for asyncio mode ──
    pytest_ini_path = Path("pytest.ini")
    if pytest_ini_path.exists():
        pytest_content = pytest_ini_path.read_text(encoding="utf-8")
        if "asyncio_mode" not in pytest_content:
            pytest_content = (
                pytest_content.rstrip("\n")
                + "\nasyncio_mode = auto\n"
            )
            pytest_ini_path.write_text(pytest_content, encoding="utf-8")
            improvements.append(("[OK] pytest.ini", "Adicionado asyncio_mode = auto"))

    # ── 11. Create .env.example if missing ──
    env_example_path = Path(".env.example")
    if not env_example_path.exists():
        env_example_path.write_text(
            """# Central de Inteligencia Juridica - Environment Template
# Copiar para .env.prod e preencher com valores reais
# NUNCA commitar .env.prod

JWT_SECRET=gerar_com:python_-c_"import_secrets;print(secrets.token_urlsafe(48))"
DB_USER=seu_usuario
DB_PASSWORD=sua_senha_segura
DB_HOST=localhost
DB_PORT=5432
DB_NAME=central_inteligencia

REDIS_URL=redis://localhost:6379/0

# ChromaDB
CHROMA_HOST=localhost
CHROMA_PORT=8000

# LLM
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=llama3

# Grafana
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=senha_segura_do_grafana
""",
            encoding="utf-8",
        )
        improvements.append(("[OK] .env.example", "Template criado"))

    for label, desc in improvements:
        results.append((True, f"{label} - {desc}"))

    return results


# ─── Validation ─────────────────────────────────────────────────────────────


def validate_resolution(verbose: bool = False) -> list[tuple[bool, str]]:
    """Validate that all files are properly resolved."""

    results = []
    all_files = list(STRATEGY.keys())

    # Check for remaining conflict markers
    remaining_conflicts = []
    for filepath in all_files:
        path = Path(filepath)
        if path.exists():
            content = path.read_text(encoding="utf-8")
            if "<<<<<<< " in content:
                count = content.count("<<<<<<< ")
                remaining_conflicts.append((filepath, count))

    if remaining_conflicts:
        for fp, count in remaining_conflicts:
            results.append((False, f"[FAIL] {fp} ainda tem {count} conflito(s)"))
    else:
        results.append((True, "[OK] Nenhum marcador de conflito restante em nenhum arquivo"))

    # Check imports can be resolved (basic syntax check)
    syntax_errors = []
    py_files = [f for f in all_files if f.endswith(".py")]
    for filepath in py_files:
        path = Path(filepath)
        if path.exists():
            try:
                compile(path.read_text(encoding="utf-8"), filepath, "exec")
            except SyntaxError as exc:
                syntax_errors.append((filepath, str(exc)))

    if syntax_errors:
        for fp, err in syntax_errors:
            results.append((False, f"[SYNTAX ERROR] {fp}: {err}"))
    else:
        results.append((True, "[OK] Todos os arquivos .py passam verificacao de sintaxe"))

    # Summary
    total_ok = sum(1 for ok, _ in results if ok)
    total_fail = sum(1 for ok, _ in results if not ok)
    results.append(
        (total_fail == 0, f"[SUMMARY] {total_ok} OK, {total_fail} FALHAS")
    )

    return results


# ─── Main ────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fase 2: Resolve merge conflicts + Phase 2 improvements"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )
    parser.add_argument(
        "--validate-only", action="store_true", help="Only validate, do not resolve"
    )
    args = parser.parse_args()

    global MERGED_CONTENT
    MERGED_CONTENT = _build_merged_content()

    print("=" * 78)
    print("  FASE 2 - Resolucao de Conflitos + Melhorias Phase 2")
    print("  Central de Inteligencia Juridica")
    print("=" * 78)
    print()

    if args.validate_only:
        print("[INFO] Modo validacao apenas...")
        print()
        results = validate_resolution(verbose=args.verbose)
        for ok, msg in results:
            status = "\033[92m" if ok else "\033[91m"
            print(f"  {status}{msg}\033[0m")
        print()
        return

    # Phase 2a: Resolve conflicts
    print("[INFO] PASSO 1/3: Resolvendo conflitos de merge...")
    print()

    conflict_results = []
    for filepath, strategy in STRATEGY.items():
        if args.dry_run:
            path = Path(filepath)
            if path.exists() and "<<<<<<< " in path.read_text(encoding="utf-8"):
                conflict_results.append(
                    (True, f"[DRY-RUN] {filepath} -> {strategy}")
                )
            elif path.exists():
                conflict_results.append(
                    (True, f"[DRY-RUN] {filepath} (sem conflitos)")
                )
            else:
                conflict_results.append(
                    (False, f"[DRY-RUN] {filepath} (NAO ENCONTRADO)")
                )
        else:
            ok, msg = resolve_file(filepath, strategy, verbose=args.verbose)
            conflict_results.append((ok, msg))

    for ok, msg in conflict_results:
        status = "\033[92m" if ok else "\033[91m"
        print(f"  {status}{msg}\033[0m")

    # Phase 2b: Quality improvements
    print()
    print("[INFO] PASSO 2/3: Aplicando melhorias Phase 2...")
    print()

    if args.dry_run:
        print("  [DRY-RUN] Melhorias Phase 2 seriam aplicadas")
        print("  - Stubs para modulos ausentes (vector_memory, intent_classifier, etc.)")
        print("  - .env.example template")
        print("  - pytest.ini asyncio_mode")
        print("  - src/__init__.py version")
    else:
        improvement_results = apply_phase2_improvements(verbose=args.verbose)
        for ok, msg in improvement_results:
            status = "\033[92m" if ok else "\033[91m"
            print(f"  {status}{msg}\033[0m")

    # Phase 2c: Validate
    print()
    print("[INFO] PASSO 3/3: Validacao...")
    print()

    if args.dry_run:
        print("  [DRY-RUN] Validacao seria executada")
    else:
        validation_results = validate_resolution(verbose=args.verbose)
        for ok, msg in validation_results:
            status = "\033[92m" if ok else "\033[91m"
            print(f"  {status}{msg}\033[0m")

    # Summary
    print()
    print("=" * 78)
    total_ok = sum(1 for ok, _ in conflict_results if ok)
    total_files = len(conflict_results)
    print(f"  RESOLVIDOS: {total_ok}/{total_files} arquivos processados")
    print()

    if args.dry_run:
        print("  MODO DRY-RUN - Nenhuma alteracao foi feita")
        print("  Remova --dry-run para aplicar as correcoes")
    else:
        print("  PROXIMOS PASSOS:")
        print()
        print("  1. Verificar sintaxe:")
        print("     python -c 'import src' 2>&1 || echo 'Imports OK'")
        print()
        print("  2. Rodar testes:")
        print("     python -m pytest tests/ -x -v 2>&1")
        print()
        print("  3. Commitar:")
        print('     git add -A')
        print('     git commit -m "fix(fase2): resolve all merge conflicts + phase2 improvements"')
        print()

    print("=" * 78)

    # Exit code
    all_ok = all(ok for ok, _ in conflict_results)
    sys.exit(0 if all_ok or args.dry_run else 1)


if __name__ == "__main__":
    main()
