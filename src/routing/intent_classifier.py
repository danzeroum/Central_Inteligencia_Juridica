"""LLM-based Intent Classifier for intelligent routing.

Esta implementação segue a especificação da Onda 2.1. Sempre que um
modelo de linguagem estiver disponível o classificador utiliza LangChain para
obter uma saída estruturada. Caso contrário – ou se ocorrer algum erro – a
solução realiza um fallback determinístico baseado em heurísticas, garantindo
que os testes possam ser executados offline.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - dependência opcional
    from langchain.chains import LLMChain
    from langchain.prompts import PromptTemplate
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover - ambiente sem LangChain
    LLMChain = None  # type: ignore[assignment]
    PromptTemplate = None  # type: ignore[assignment]
    ChatOpenAI = None  # type: ignore[assignment]

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


_PROCESS_PATTERN = re.compile(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}")


class ClassifiedIntent(BaseModel):
    """Structured output from intent classification."""

    tribunais: List[str] = Field(
        ...,
        description="Lista de tribunais identificados (TJSP, TJMG, STF, etc.)",
    )
    operacao: str = Field(
        ...,
        description="Tipo de operação solicitada",
    )
    parametros: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parâmetros adicionais extraídos",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confiança na classificação",
    )
    reasoning: str = Field(
        default="",
        description="Chain-of-thought do LLM ou do fallback heurístico",
    )

    @field_validator("tribunais")
    @classmethod
    def validate_tribunais(cls, v: List[str]) -> List[str]:
        valid_codes = {"TJSP", "TJMG", "TJRS", "TJRJ", "STF", "STJ", "TST"}
        return [t.upper() for t in v if t.upper() in valid_codes]


class IntentClassifier:
    """LLM-powered intent classifier with structured output."""

    CLASSIFICATION_PROMPT = """Você é um assistente especializado em análise de consultas jurídicas.

Analise a solicitação do usuário e extraia as seguintes informações em formato JSON estruturado:

1. **tribunais**: Lista de códigos de tribunais mencionados (TJSP, TJMG, TJRS, TJRJ, STF, STJ, TST)
2. **operacao**: Tipo de operação solicitada. Opções válidas:
   - "status_check": Verificar status/disponibilidade do sistema
   - "process_query": Consultar processo específico
   - "process_movements": Verificar movimentações processuais
   - "jurisprudence_search": Buscar jurisprudência/decisões
   - "jurisprudence_comparison": Comparar jurisprudência entre tribunais
   - "generic": Consulta genérica/outros
3. **parametros**: Dicionário com informações extras:
   - "numero_processo": se mencionado
   - "tema": assunto jurídico principal
   - "periodo": intervalo temporal se especificado
4. **confidence**: Sua confiança na classificação (0.0 a 1.0)
5. **reasoning**: Breve explicação do seu raciocínio

**IMPORTANTE:**
- Se nenhum tribunal for mencionado explicitamente, deixe "tribunais" vazio []
- Se mencionar "São Paulo" ou "SP", considere TJSP
- Se mencionar "Minas" ou "MG", considere TJMG
- Priorize precisão sobre recall - seja conservador

**Exemplos:**

Input: "Verificar status do TJSP"
Output: {{"tribunais": ["TJSP"], "operacao": "status_check", "parametros": {{}}, "confidence": 0.95, "reasoning": "Menção explícita a TJSP e palavra-chave 'status'"}}

Input: "Comparar jurisprudência sobre LGPD no STF e TJSP"
Output: {{"tribunais": ["STF", "TJSP"], "operacao": "jurisprudence_comparison", "parametros": {{"tema": "LGPD"}}, "confidence": 0.90, "reasoning": "Dois tribunais mencionados, operação de comparação explícita, tema LGPD identificado"}}

Input: "Qual o andamento do processo 1234567-89.2024.8.26.1234?"
Output: {{"tribunais": ["TJSP"], "operacao": "process_movements", "parametros": {{"numero_processo": "1234567-89.2024.8.26.1234"}}, "confidence": 0.85, "reasoning": "Número de processo do formato TJSP identificado, pergunta sobre andamento"}}

Agora analise a seguinte solicitação:

**Input do Usuário:** {user_input}

**Output (JSON válido apenas, sem markdown):**"""

    def __init__(
        self,
        model_name: str = "gpt-4",
        temperature: float = 0.1,
        confidence_threshold: float = 0.7,
        llm_enabled: Optional[bool] = None,
    ) -> None:
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold

        inferred_enabled = bool(os.getenv("OPENAI_API_KEY"))
        if llm_enabled is not None:
            inferred_enabled = llm_enabled

        self.llm_enabled = bool(LLMChain and PromptTemplate and ChatOpenAI) and inferred_enabled
        self.chain: Optional[LLMChain] = None

        if self.llm_enabled:
            try:
                llm = ChatOpenAI(  # type: ignore[operator]
                    model=model_name,
                    temperature=temperature,
                    request_timeout=30,
                )
                prompt = PromptTemplate(  # type: ignore[operator]
                    input_variables=["user_input"],
                    template=self.CLASSIFICATION_PROMPT,
                )
                self.chain = LLMChain(  # type: ignore[operator]
                    llm=llm,
                    prompt=prompt,
                    verbose=False,
                )
            except Exception as exc:  # pragma: no cover - inicialização defensiva
                logger.warning("Failed to initialize LLM chain: %s", exc)
                self.llm_enabled = False
                self.chain = None

        logger.info(
            "IntentClassifier initialized (model=%s, threshold=%.2f, llm_enabled=%s)",
            model_name,
            confidence_threshold,
            self.llm_enabled,
        )

    async def classify(self, user_input: str) -> ClassifiedIntent:
        """Classifica a intenção do usuário usando LLM ou heurísticas."""

        start_time = time.perf_counter()

        if not self.llm_enabled or self.chain is None:
            return self._keyword_classify(user_input, fallback_reason="LLM indisponível")

        try:
            raw_output = await self.chain.arun(user_input=user_input)
            parsed = self._parse_llm_output(raw_output)
            intent = ClassifiedIntent.model_validate(parsed)
        except Exception as exc:
            logger.error("Intent classification failed: %s", exc, exc_info=True)
            return self._keyword_classify(
                user_input,
                fallback_reason=f"Classification failed: {exc}",
            )

        elapsed = time.perf_counter() - start_time
        estimated_cost = self._estimate_cost(user_input)
        logger.info(
            "Intent classified via LLM: tribunais=%s, op=%s, confidence=%.2f, time=%.3fs, estimated_cost=$%.4f",
            intent.tribunais,
            intent.operacao,
            intent.confidence,
            elapsed,
            estimated_cost,
        )
        return intent

    def should_use_llm(self, user_input: str) -> bool:
        """Decide se vale a pena usar LLM (mais caro) ou fallback keyword-based."""

        keywords_complexos = [
            "comparar",
            "analisar",
            "jurisprudência",
            "jurisprudencia",
            "decisões",
            "decisoes",
            "tendência",
            "tendencia",
            "evolução",
            "evolucao",
        ]

        if len(user_input) > 50:
            return True

        lowered = user_input.lower()
        if any(kw in lowered for kw in keywords_complexos):
            return True

        tribunals_mentioned = sum(
            1 for t in ["TJSP", "TJMG", "TJRS", "TJRJ", "STF", "STJ", "TST"]
            if t in user_input.upper()
        )
        if tribunals_mentioned >= 2:
            return True

        return False

    # ------------------------------------------------------------------
    # Métodos auxiliares
    # ------------------------------------------------------------------
    def _parse_llm_output(self, raw_output: str) -> Dict[str, Any]:
        """Parse JSON da resposta do LLM, removendo markdown se presente."""

        cleaned = raw_output.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM output as JSON", exc_info=True)
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise

    def _keyword_classify(
        self,
        user_input: str,
        fallback_reason: Optional[str] = None,
    ) -> ClassifiedIntent:
        """Fallback heurístico utilizado quando o LLM não está disponível."""

        lowered = user_input.lower()
        tribunais = self._extract_tribunals(user_input)

        operation = "generic"
        confidence = 0.6
        reasoning_parts: List[str] = []
        if fallback_reason:
            reasoning_parts.append(fallback_reason)

        comparison_keywords = ["comparar", "comparação", "comparacao"]
        status_keywords = [
            "status",
            "disponibilidade",
            "disponivel",
            "funcionamento",
            "indisponível",
            "indisponivel",
        ]
        movement_keywords = ["movimentações", "movimentacoes", "andamento", "últimas movimentações", "ultimas movimentacoes"]
        jurisprudence_keywords = ["jurisprudência", "jurisprudencia", "decisões", "decisoes", "precedentes"]
        process_keywords = ["processo", "processar"]

        if any(kw in lowered for kw in comparison_keywords):
            operation = "jurisprudence_comparison"
            confidence = 0.85
            reasoning_parts.append("Palavra-chave de comparação identificada")
        elif any(kw in lowered for kw in status_keywords):
            operation = "status_check"
            confidence = 0.8
            reasoning_parts.append("Palavra-chave de status identificada")
        elif any(kw in lowered for kw in movement_keywords):
            operation = "process_movements"
            confidence = 0.8
            reasoning_parts.append("Referência a movimentações processuais")
        elif any(kw in lowered for kw in process_keywords):
            operation = "process_query"
            confidence = 0.75
            reasoning_parts.append("Solicitação envolvendo processo específico")
        elif any(kw in lowered for kw in jurisprudence_keywords):
            operation = "jurisprudence_search"
            confidence = 0.75
            reasoning_parts.append("Solicitação por jurisprudência/decisões")
        else:
            reasoning_parts.append("Nenhuma palavra-chave forte encontrada; marcado como genérico")

        parametros = self._extract_parameters(user_input, lowered)
        if "numero_processo" in parametros and not tribunais:
            inferred = self._infer_tribunal_from_process(parametros["numero_processo"])
            if inferred:
                tribunais = [inferred]
                reasoning_parts.append(
                    "Tribunal inferido a partir do número do processo"
                )
        if parametros:
            reasoning_parts.append("Parâmetros extras identificados")

        # Ajusta confiança para casos muito vagos
        if not tribunais and operation == "generic":
            confidence = min(confidence, 0.5)

        reasoning = "; ".join(reasoning_parts)

        return ClassifiedIntent(
            tribunais=tribunais,
            operacao=operation,
            parametros=parametros,
            confidence=confidence,
            reasoning=reasoning,
        )

    def _estimate_cost(self, user_input: str) -> float:
        """Estimate API cost based on a naive token approximation."""

        approx_tokens = max(len(user_input.split()), 1)
        # Aproximação grosseira: ~$0.02 por 1K tokens => 0.00002 por token
        return approx_tokens * 0.00002

    def _extract_tribunals(self, user_input: str) -> List[str]:
        lowered = user_input.lower()
        tribunal_keywords: Dict[str, List[str]] = {
            "TJSP": ["tjsp", "são paulo", "sao paulo", "sp"],
            "TJMG": ["tjmg", "minas gerais", "minas", "mg"],
            "TJRS": ["tjrs", "rio grande do sul", "gaúcho", "gaucho", "rs"],
            "TJRJ": ["tjrj", "rio de janeiro", "fluminense", "rj"],
            "STF": ["stf", "supremo", "supremo tribunal federal"],
            "STJ": ["stj", "superior tribunal de justiça"],
            "TST": ["tst", "tribunal superior do trabalho"],
        }

        found: List[str] = []
        for tribunal, keywords in tribunal_keywords.items():
            for keyword in keywords:
                if self._keyword_matches(lowered, keyword):
                    found.append(tribunal)
                    break

        return list(dict.fromkeys(found))

    def _keyword_matches(self, text: str, keyword: str) -> bool:
        if " " in keyword:
            return keyword in text
        return re.search(rf"\b{re.escape(keyword)}\b", text) is not None

    def _extract_parameters(self, original: str, lowered: str) -> Dict[str, Any]:
        parametros: Dict[str, Any] = {}

        match = _PROCESS_PATTERN.search(original)
        if match:
            parametros["numero_processo"] = match.group(0)

        if "sobre" in lowered:
            idx = lowered.find("sobre") + len("sobre")
            fragment = original[idx:].strip()
            delimiters = [" no ", " na ", " em ", "?", ".", ","]
            for delimiter in delimiters:
                if delimiter in fragment:
                    fragment = fragment.split(delimiter)[0]
                    break
            fragment = fragment.strip()
            if fragment:
                parametros["tema"] = fragment

        periodo_match = re.search(r"(últimos|ultimos|últimas|ultimas) (\d+) anos", lowered)
        if periodo_match:
            parametros["periodo"] = periodo_match.group(0)

        return parametros

    def _infer_tribunal_from_process(self, numero: str) -> Optional[str]:
        if ".8.26." in numero:
            return "TJSP"
        if ".8.13." in numero:
            return "TJMG"
        if ".8.21." in numero:
            return "TJRS"
        return None


__all__ = ["ClassifiedIntent", "IntentClassifier"]


if __name__ == "__main__":  # pragma: no cover - demonstração manual
    import asyncio

    async def demo() -> None:
        classifier = IntentClassifier(llm_enabled=False)
        examples = [
            "Status do TJSP",
            "Comparar jurisprudência sobre LGPD no STF e TJSP",
            "Processo 1234567-89.2024.8.26.1234 no TJMG",
            "Últimas decisões do STF sobre direito digital",
        ]
        for example in examples:
            intent = await classifier.classify(example)
            print(example)
            print(intent.model_dump())

    asyncio.run(demo())

