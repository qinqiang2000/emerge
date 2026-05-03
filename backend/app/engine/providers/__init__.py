from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engine.provider import Provider


def get_provider(name: str | None = None) -> "Provider":
    from app.engine.providers.gemini_provider import GeminiProvider
    from app.engine.providers.openai_provider import OpenAIProvider
    from app.settings import settings

    name = name or settings.default_provider
    if name == "openai":
        return OpenAIProvider()
    if name == "gemini":
        return GeminiProvider()
    raise ValueError(f"unknown provider {name!r}")
