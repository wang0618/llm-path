"""Dependency analysis for request sequences."""

from .models import CookedRequest


class DependencyAnalyzer:
    """Analyzes request dependencies using Levenshtein distance and tool matching.

    Builds a dependency forest (not linear chain) by:
    - Using Levenshtein distance for parent detection
    - Filtering by model (no cross-model dependencies)
    - Applying tool difference penalties to match scores
    - Creating new roots when match score is below threshold
    """

    # Dependency analysis parameters
    TOOL_DIFF_PENALTY = 0.5  # Penalty per different tool
    RELATIVE_THRESHOLD = 0.5  # Edit distance threshold as ratio of message count

    def analyze(self, requests: list[CookedRequest]) -> None:
        """Analyze dependencies and set parent_id for each request (in-place modification).

        Args:
            requests: List of CookedRequest sorted by timestamp ascending
        """
        for idx, req in enumerate(requests):
            if idx == 0:
                req.parent_id = None
            else:
                req.parent_id = self._find_parent(req, requests[:idx])

    def _find_parent(self, curr: CookedRequest, candidates: list[CookedRequest]) -> str | None:
        """Find the best parent for current request.

        Args:
            curr: Current request
            candidates: Requests earlier than curr (sorted by timestamp ascending)

        Returns:
            parent_id or None (becomes new root if no good match)
        """
        # Filter: only consider candidates with same model
        same_model_candidates = [c for c in candidates if c.model == curr.model]

        if not same_model_candidates:
            return None  # No same-model candidate, become new root

        # Use combined score to find most similar parent
        best_score = float("-inf")
        best_parent_id = None

        for c in reversed(same_model_candidates):  # From most recent, same score picks latest
            score = self._match_score(curr, c)
            if score > best_score:
                best_score = score
                best_parent_id = c.id

        # Forest support: become new root if score is too low
        threshold = -len(curr.request_messages) * self.RELATIVE_THRESHOLD
        if best_score < threshold:
            return None

        return best_parent_id

    def _build_expected_prefix(self, candidate: CookedRequest) -> list[str]:
        """Build expected message prefix.

        If candidate has response_messages, prefix = request_messages + response_messages
        Otherwise just request_messages
        """
        prefix = list(candidate.request_messages)
        if candidate.response_messages:
            prefix.extend(candidate.response_messages)
        return prefix

    def _match_score(self, curr: CookedRequest, candidate: CookedRequest) -> float:
        """Compute combined match score (higher is more similar).

        Score = message_score + tool_score
        - message_score: negative edit distance
        - tool_score: penalty for tool differences
        """
        # Message score: negative edit distance
        a = self._build_expected_prefix(candidate)
        b = curr.request_messages
        message_score = -self._levenshtein(a, b)

        # Tool score: penalty for different tools
        curr_tools = set(curr.tools)
        candidate_tools = set(candidate.tools)
        tool_diff = len(curr_tools.symmetric_difference(candidate_tools))
        tool_score = -self.TOOL_DIFF_PENALTY * tool_diff

        return message_score + tool_score

    def _levenshtein(self, a: list[str], b: list[str]) -> int:
        """Compute Levenshtein distance between two lists.

        Operations: add, delete, replace
        """
        m, n = len(a), len(b)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if a[i - 1] == b[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = 1 + min(
                        dp[i - 1][j],  # delete
                        dp[i][j - 1],  # add
                        dp[i - 1][j - 1],  # replace
                    )

        return dp[m][n]
