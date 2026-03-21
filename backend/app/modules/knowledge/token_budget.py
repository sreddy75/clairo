"""Token budget management for AI context building.

Manages token allocation across context tiers to ensure
prompts stay within model limits.
"""

from dataclasses import dataclass


@dataclass
class TokenBudget:
    """Token budget allocations for context tiers.

    Tier 1: Client profile - always included
    Tier 2: Financial summaries - intent-specific
    Tier 3: Raw transaction details - on-demand
    RAG: Knowledge base context
    """

    tier1_profile: int = 500
    tier2_summaries: int = 4000
    tier3_details: int = 2000
    rag_context: int = 2000
    total_max: int = 12500

    @property
    def total_allocated(self) -> int:
        """Total tokens allocated across all tiers."""
        return self.tier1_profile + self.tier2_summaries + self.tier3_details + self.rag_context


class TokenBudgetManager:
    """Manages token budget allocation and tracking.

    Uses a chars/4 approximation for token estimation,
    which is roughly accurate for English text with Claude.
    """

    CHARS_PER_TOKEN = 4  # Approximate ratio for Claude

    def __init__(self, budget: TokenBudget | None = None) -> None:
        """Initialize with optional custom budget.

        Args:
            budget: Custom token budget. Uses defaults if not provided.
        """
        self.budget = budget or TokenBudget()
        self._used: dict[str, int] = {
            "tier1": 0,
            "tier2": 0,
            "tier3": 0,
            "rag": 0,
        }

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Text to estimate tokens for.

        Returns:
            Estimated token count.
        """
        if not text:
            return 0
        return len(text) // self.CHARS_PER_TOKEN + 1

    def get_tier_budget(self, tier: str) -> int:
        """Get the budget for a specific tier.

        Args:
            tier: Tier name ('tier1', 'tier2', 'tier3', 'rag').

        Returns:
            Budget for the tier in tokens.
        """
        tier_budgets = {
            "tier1": self.budget.tier1_profile,
            "tier2": self.budget.tier2_summaries,
            "tier3": self.budget.tier3_details,
            "rag": self.budget.rag_context,
        }
        return tier_budgets.get(tier, 0)

    def fits_budget(self, text: str, tier: str) -> bool:
        """Check if text fits within the tier's remaining budget.

        Args:
            text: Text to check.
            tier: Tier name.

        Returns:
            True if text fits within remaining budget.
        """
        tokens = self.estimate_tokens(text)
        budget = self.get_tier_budget(tier)
        used = self._used.get(tier, 0)
        return tokens <= (budget - used)

    def remaining_budget(self, tier: str) -> int:
        """Get remaining budget for a tier.

        Args:
            tier: Tier name.

        Returns:
            Remaining tokens available.
        """
        budget = self.get_tier_budget(tier)
        used = self._used.get(tier, 0)
        return max(0, budget - used)

    def total_remaining(self) -> int:
        """Get total remaining budget across all tiers."""
        total_used = sum(self._used.values())
        return max(0, self.budget.total_max - total_used)

    def record_usage(self, text: str, tier: str) -> int:
        """Record token usage for a tier.

        Args:
            text: Text that was added to context.
            tier: Tier the text belongs to.

        Returns:
            Number of tokens recorded.
        """
        tokens = self.estimate_tokens(text)
        self._used[tier] = self._used.get(tier, 0) + tokens
        return tokens

    def truncate_to_budget(self, text: str, tier: str) -> str:
        """Truncate text to fit within tier's remaining budget.

        Args:
            text: Text to potentially truncate.
            tier: Tier to check budget against.

        Returns:
            Original text if it fits, truncated text otherwise.
        """
        remaining = self.remaining_budget(tier)
        remaining_chars = remaining * self.CHARS_PER_TOKEN

        if len(text) <= remaining_chars:
            return text

        # Truncate at word boundary
        truncated = text[:remaining_chars]
        last_space = truncated.rfind(" ")
        if last_space > remaining_chars * 0.8:  # Keep at least 80%
            truncated = truncated[:last_space]

        return truncated.rstrip() + "..."

    def allocate_remaining(self, used_tiers: list[str]) -> dict[str, int]:
        """Reallocate unused budget from specified tiers.

        If some tiers use less than their budget, the remainder
        can be allocated to other tiers (typically tier2 or rag).

        Args:
            used_tiers: List of tiers that have been filled.

        Returns:
            Dict of tier names to reallocated budget amounts.
        """
        unused = 0
        for tier in used_tiers:
            budget = self.get_tier_budget(tier)
            used = self._used.get(tier, 0)
            unused += max(0, budget - used)

        # Reallocate unused to remaining tiers proportionally
        remaining_tiers = [t for t in ["tier2", "tier3", "rag"] if t not in used_tiers]

        if not remaining_tiers or unused == 0:
            return {}

        per_tier = unused // len(remaining_tiers)
        return dict.fromkeys(remaining_tiers, per_tier)

    def get_usage_summary(self) -> dict[str, dict[str, int]]:
        """Get a summary of token usage across all tiers.

        Returns:
            Dict with budget, used, and remaining for each tier.
        """
        summary = {}
        for tier in ["tier1", "tier2", "tier3", "rag"]:
            budget = self.get_tier_budget(tier)
            used = self._used.get(tier, 0)
            summary[tier] = {
                "budget": budget,
                "used": used,
                "remaining": max(0, budget - used),
            }

        summary["total"] = {
            "budget": self.budget.total_max,
            "used": sum(self._used.values()),
            "remaining": self.total_remaining(),
        }

        return summary
