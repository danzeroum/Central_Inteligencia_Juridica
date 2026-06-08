"""Designer agent responsible for UX and UI considerations."""

from __future__ import annotations

from typing import Any, Dict, List

from src.agents.base_agent import BaseAgent


class DesignerAgent(BaseAgent):
    """Produces pragmatic design artefacts for the platform."""

    def __init__(self) -> None:
        super().__init__("designer")
        self.name = "Designer Agent"
        self.description = (
            "Produz artefatos de design UX/UI pragmáticos para a plataforma."
        )
        self.capabilities = [
            "ui_design",
            "ux_review",
            "accessibility_review",
            "design_mock",
        ]
        self.specialization = "design"
        self.design_patterns: List[str] = ["material", "fluent", "carbon"]
        self.tools = ["design_mock", "accessibility_review"]
        self.metadata = {
            "supported_patterns": ["material", "fluent", "carbon"],
            "default_pattern": "material",
            "supported_themes": ["light", "dark"],
            "default_components": ["header", "navigation", "content", "footer"],
            "optional_components": {"landing_page": "hero"},
            "default_palette": {
                "primary": "#1976d2",
                "secondary": "#dc004e",
                "background_light": "#ffffff",
                "background_dark": "#121212",
            },
            "typography": {
                "font": "Roboto",
                "scale": {"h1": "2rem", "body": "1rem"},
            },
            "accessibility_standard": "WCAG 2.1 AA",
            "responsive_default": True,
            "confidence_design": 0.85,
        }

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate_input(task):
            raise ValueError("Invalid design task payload")

        design = await self.create_design(task)
        decision = {
            "task": task,
            "design": design,
            "confidence": design.get("confidence", 0.0),
        }
        self.log_decision(decision)
        return {"success": True, "agent": self.agent_type, **design}

    async def create_design(self, task: Dict[str, Any]) -> Dict[str, Any]:
        requested_pattern = task.get("pattern")
        pattern = (
            requested_pattern
            if requested_pattern in self.design_patterns
            else "material"
        )
        theme = task.get("theme", "light")
        components = ["header", "navigation", "content", "footer"]
        if task.get("landing_page"):
            components.append("hero")
        return {
            "pattern": pattern,
            "theme": theme,
            "components": components,
            "colors": {
                "primary": "#1976d2",
                "secondary": "#dc004e",
                "background": "#ffffff" if theme == "light" else "#121212",
            },
            "typography": {
                "font": "Roboto",
                "sizes": {"h1": "2rem", "body": "1rem"},
            },
            "responsive": True,
            "accessibility": "WCAG 2.1 AA",
            "confidence": 0.85,
        }
