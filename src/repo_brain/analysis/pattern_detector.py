"""Pattern detection for identifying similar code patterns in the codebase."""

from collections import defaultdict
from dataclasses import dataclass

from repo_brain.config import RepoConfig
from repo_brain.storage.vector_store import VectorStore


@dataclass
class CodePattern:
    """Detected code pattern in the codebase."""

    pattern_type: str  # "library", "inline", "utility", "service"
    locations: list[str]  # File paths where pattern exists
    count: int  # How many times this pattern appears
    recommendation: str  # What to do based on this pattern


class PatternDetector:
    """Detects existing code patterns to inform implementation decisions."""

    def __init__(self, config: RepoConfig):
        """Initialize pattern detector.

        Args:
            config: Repository configuration
        """
        self.config = config
        self.vector_store = VectorStore(config)

    def detect_similar_patterns(self, task_description: str, top_k: int = 20) -> CodePattern | None:
        """Detect if similar patterns exist in the codebase.

        Args:
            task_description: Description of what needs to be implemented
            top_k: Number of code chunks to analyze

        Returns:
            Detected pattern or None
        """
        # Search for similar code
        results = self.vector_store.search_by_text(task_description, limit=top_k)

        if not results:
            return None

        # Extract keywords from task
        keywords = self._extract_pattern_keywords(task_description)

        # Analyze results for patterns
        pattern_locations = defaultdict(list)

        for result in results:
            metadata = result.get("metadata", {})
            file_path = metadata.get("file_path", "")
            symbol_name = metadata.get("symbol_name", "")

            # Check if this looks like a library, utility, or inline implementation
            pattern_type = self._classify_code_location(file_path, symbol_name)

            # Check if keywords match
            content = result.get("document", "").lower()
            if any(kw in content for kw in keywords):
                pattern_locations[pattern_type].append(file_path)

        if not pattern_locations:
            return CodePattern(
                pattern_type="none",
                locations=[],
                count=0,
                recommendation="No similar patterns found. Start with inline solution.",
            )

        # Determine dominant pattern
        most_common_type = max(pattern_locations.keys(), key=lambda k: len(pattern_locations[k]))
        count = len(pattern_locations[most_common_type])
        locations = list(set(pattern_locations[most_common_type]))

        recommendation = self._generate_pattern_recommendation(most_common_type, count, locations)

        return CodePattern(
            pattern_type=most_common_type,
            locations=locations[:5],  # Limit to top 5
            count=count,
            recommendation=recommendation,
        )

    def _extract_pattern_keywords(self, task_description: str) -> list[str]:
        """Extract pattern-relevant keywords from task description.

        Args:
            task_description: Task description

        Returns:
            List of keywords
        """
        # Focus on technical keywords that indicate functionality
        stop_words = {"add", "create", "implement", "build", "make", "the", "a", "an"}
        words = task_description.lower().split()
        keywords = [w for w in words if len(w) > 3 and w not in stop_words]
        return keywords[:3]

    def _classify_code_location(self, file_path: str, symbol_name: str) -> str:
        """Classify where code is located (library, utility, inline, etc.).

        Args:
            file_path: Path to the file
            symbol_name: Name of the symbol

        Returns:
            Classification string
        """
        path_lower = file_path.lower()

        # Check for library patterns
        if any(
            marker in path_lower
            for marker in ["lib/", "library/", "libraries/", "packages/", "pkg/"]
        ):
            return "library"

        # Check for utility patterns
        if any(marker in path_lower for marker in ["util", "helper", "common", "shared", "core"]):
            return "utility"

        # Check for service patterns
        if any(marker in path_lower for marker in ["service", "services/", "srv/"]):
            return "service"

        # Default to inline
        return "inline"

    def _generate_pattern_recommendation(
        self, pattern_type: str, count: int, locations: list[str]
    ) -> str:
        """Generate recommendation based on detected patterns.

        Args:
            pattern_type: Type of pattern detected
            count: How many occurrences
            locations: Where the pattern exists

        Returns:
            Recommendation string
        """
        if pattern_type == "library" and count >= 3:
            return (
                f"Library pattern detected ({count} occurrences). "
                f"Consider using existing library: {locations[0]}"
            )
        elif pattern_type == "utility" and count >= 2:
            return (
                f"Utility pattern detected ({count} occurrences). "
                f"Consider adding to existing utility: {locations[0]}"
            )
        elif pattern_type == "service" and count >= 2:
            return (
                f"Service pattern detected ({count} occurrences). Follow existing service pattern"
            )
        elif count == 1:
            return "Single occurrence found. Inline solution likely sufficient."
        else:
            return "No established pattern. Start with inline solution, refactor if needed."

    def detect_code_duplication(
        self, task_description: str, similarity_threshold: float = 0.8
    ) -> dict:
        """Detect if similar code already exists (potential duplication).

        Args:
            task_description: What needs to be implemented
            similarity_threshold: Threshold for similarity (0-1)

        Returns:
            Dictionary with duplication analysis
        """
        results = self.vector_store.search_by_text(task_description, limit=10)

        if not results:
            return {"has_duplication": False, "similar_code": []}

        # Check distances to determine similarity
        similar_code = []
        for result in results:
            distance = result.get("distance", 1.0)
            similarity = 1.0 - distance

            if similarity >= similarity_threshold:
                metadata = result.get("metadata", {})
                similar_code.append(
                    {
                        "file": metadata.get("file_path"),
                        "symbol": metadata.get("symbol_name"),
                        "similarity": round(similarity, 2),
                    }
                )

        return {
            "has_duplication": len(similar_code) > 0,
            "similar_code": similar_code[:3],  # Top 3
            "recommendation": (
                "Very similar code exists. Consider refactoring to avoid duplication."
                if similar_code
                else "No duplication detected."
            ),
        }
