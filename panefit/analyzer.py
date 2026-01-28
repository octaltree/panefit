"""
Panefit content analyzer.

Analyzes pane content using entropy, surprisal, and activity detection
to calculate importance and interestingness scores.
"""

import math
import re
import hashlib
from collections import Counter
from typing import Optional

from .types import PaneData, AnalysisResult, RelevanceResult, AnalysisBatch


class Analyzer:
    """Content analyzer for pane content."""

    # Programming keywords (indicate code/development activity)
    CODE_KEYWORDS = {
        "function", "def", "class", "import", "from", "return", "if", "else",
        "for", "while", "try", "except", "catch", "throw", "async", "await",
        "const", "let", "var", "public", "private", "static", "void", "int",
        "string", "bool", "true", "false", "null", "none", "self", "this",
        "error", "warning", "debug", "info", "log", "test", "spec", "describe"
    }

    # Shell activity patterns
    ACTIVITY_PATTERNS = [
        r"^\$\s",           # Shell prompt
        r"^>\s",            # Continuation prompt
        r"^\[\d+\]",        # Job control
        r"^npm\s", r"^yarn\s", r"^pnpm\s",    # Package managers
        r"^git\s",          # Version control
        r"^docker\s", r"^kubectl\s",          # Containers
        r"^python\s", r"^node\s", r"^ruby\s", # Interpreters
        r"^make\s", r"^cargo\s", r"^go\s",    # Build tools
    ]

    # Stop words for keyword extraction
    STOP_WORDS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "can", "to", "of",
        "in", "for", "on", "with", "at", "by", "from", "as", "or",
        "and", "but", "not", "no", "so", "if", "it", "its", "this",
        "that", "these", "those", "then", "than", "when", "where"
    }

    def __init__(self, ngram_size: int = 3):
        """
        Initialize analyzer.

        Args:
            ngram_size: Size of n-grams for surprisal calculation.
        """
        self.ngram_size = ngram_size
        self._content_history: dict[str, list[str]] = {}

    def _calculate_entropy(self, items: list) -> float:
        """Calculate Shannon entropy for a list of items."""
        if not items:
            return 0.0

        counts = Counter(items)
        total = len(items)
        entropy = 0.0

        for count in counts.values():
            if count > 0:
                prob = count / total
                entropy -= prob * math.log2(prob)

        return entropy

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into words."""
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        return [w for w in text.split() if w and len(w) > 1]

    def _extract_keywords(self, text: str, top_n: int = 20) -> list[str]:
        """Extract important keywords from text."""
        words = self._tokenize(text)
        word_freq = Counter(words)

        keywords = [
            word for word, _ in word_freq.most_common(top_n * 2)
            if word not in self.STOP_WORDS
        ][:top_n]

        return keywords

    def _calculate_surprisal(self, text: str) -> float:
        """Calculate surprisal score using n-gram model."""
        words = self._tokenize(text)
        if len(words) < self.ngram_size + 1:
            return 0.5

        # Build context -> next word frequency
        context_counts: dict[tuple, Counter] = {}
        for i in range(len(words) - self.ngram_size):
            context = tuple(words[i:i + self.ngram_size])
            next_word = words[i + self.ngram_size]
            if context not in context_counts:
                context_counts[context] = Counter()
            context_counts[context][next_word] += 1

        # Calculate average surprisal
        total_surprisal = 0.0
        count = 0

        for i in range(len(words) - self.ngram_size):
            context = tuple(words[i:i + self.ngram_size])
            actual_word = words[i + self.ngram_size]

            if context in context_counts:
                total = sum(context_counts[context].values())
                word_count = context_counts[context].get(actual_word, 1)
                prob = word_count / total
                total_surprisal += -math.log2(prob) if prob > 0 else 10.0
                count += 1

        if count == 0:
            return 0.5

        avg_surprisal = total_surprisal / count
        return min(1.0, avg_surprisal / 10.0)

    def _detect_activity(self, text: str) -> float:
        """Detect recent activity level in content."""
        lines = text.strip().split('\n')
        if not lines:
            return 0.0

        recent_lines = lines[-20:]
        activity_score = 0.0

        for line in recent_lines:
            for pattern in self.ACTIVITY_PATTERNS:
                if re.search(pattern, line):
                    activity_score += 0.1
                    break

        non_empty_recent = sum(1 for line in recent_lines if line.strip())
        activity_score += non_empty_recent * 0.02

        return min(1.0, activity_score)

    def _content_hash(self, text: str) -> str:
        """Calculate hash for change detection."""
        return hashlib.md5(text.encode()).hexdigest()[:16]

    def analyze(self, content: str, pane_id: str = "") -> AnalysisResult:
        """
        Analyze pane content.

        Args:
            content: Pane content to analyze.
            pane_id: Optional pane ID for tracking history.

        Returns:
            AnalysisResult with all metrics.
        """
        chars = list(content)
        words = self._tokenize(content)
        lines = content.strip().split('\n')

        # Handle empty content
        if not words:
            return AnalysisResult(
                pane_id=pane_id,
                char_count=len(content),
                content_hash=self._content_hash(content)
            )

        # Calculate entropies
        char_entropy = self._calculate_entropy(chars)
        word_entropy = self._calculate_entropy(words)

        # Basic statistics
        line_count = len(lines)
        word_count = len(words)
        char_count = len(content)
        unique_words = set(words)
        unique_word_ratio = len(unique_words) / word_count

        # Complexity metrics
        avg_word_length = sum(len(w) for w in words) / word_count
        vocabulary_richness = len(unique_words) / math.sqrt(word_count)

        # Activity and surprisal
        activity_score = self._detect_activity(content)
        surprisal_score = self._calculate_surprisal(content)

        # Code keyword ratio
        code_keyword_ratio = sum(
            1 for w in unique_words if w in self.CODE_KEYWORDS
        ) / max(len(unique_words), 1)

        # Track content changes
        content_hash = self._content_hash(content)
        change_score = 0.0
        if pane_id and pane_id in self._content_history:
            if self._content_history[pane_id][-1] != content_hash:
                change_score = 0.3

        if pane_id:
            if pane_id not in self._content_history:
                self._content_history[pane_id] = []
            self._content_history[pane_id].append(content_hash)
            self._content_history[pane_id] = self._content_history[pane_id][-10:]

        # Calculate importance score
        importance_score = min(1.0, (
            0.2 * min(1.0, word_count / 500) +
            0.2 * activity_score +
            0.15 * unique_word_ratio +
            0.15 * code_keyword_ratio +
            0.15 * change_score +
            0.15 * min(1.0, char_entropy / 5.0)
        ))

        # Calculate interestingness score
        entropy_interestingness = max(0.0, 1.0 - abs(char_entropy - 4.0) / 4.0)

        interestingness_score = min(1.0, (
            0.25 * surprisal_score +
            0.25 * entropy_interestingness +
            0.25 * vocabulary_richness / 10.0 +
            0.25 * activity_score
        ))

        return AnalysisResult(
            pane_id=pane_id,
            char_entropy=char_entropy,
            word_entropy=word_entropy,
            word_count=word_count,
            line_count=line_count,
            char_count=char_count,
            unique_word_ratio=unique_word_ratio,
            vocabulary_richness=vocabulary_richness,
            avg_word_length=avg_word_length,
            surprisal_score=surprisal_score,
            recent_activity_score=activity_score,
            importance_score=importance_score,
            interestingness_score=interestingness_score,
            content_hash=content_hash
        )

    def analyze_pane(self, pane: PaneData) -> AnalysisResult:
        """Analyze a PaneData object."""
        return self.analyze(pane.content, pane.id)

    def analyze_panes(self, panes: list[PaneData]) -> dict[str, AnalysisResult]:
        """
        Analyze multiple panes.

        Args:
            panes: List of PaneData objects.

        Returns:
            Dictionary mapping pane_id to AnalysisResult.
        """
        return {pane.id: self.analyze_pane(pane) for pane in panes}

    def calculate_relevance(self, content1: str, content2: str, id1: str = "", id2: str = "") -> RelevanceResult:
        """
        Calculate relevance between two pane contents.

        Args:
            content1: First pane content.
            content2: Second pane content.
            id1: First pane ID.
            id2: Second pane ID.

        Returns:
            RelevanceResult with similarity metrics.
        """
        keywords1 = set(self._extract_keywords(content1))
        keywords2 = set(self._extract_keywords(content2))

        shared = keywords1 & keywords2
        union = keywords1 | keywords2
        jaccard = len(shared) / len(union) if union else 0.0

        words1 = set(self._tokenize(content1))
        words2 = set(self._tokenize(content2))
        word_jaccard = len(words1 & words2) / len(words1 | words2) if (words1 | words2) else 0.0

        code_words1 = words1 & self.CODE_KEYWORDS
        code_words2 = words2 & self.CODE_KEYWORDS
        topic_similarity = 0.0
        if code_words1 and code_words2:
            topic_similarity = len(code_words1 & code_words2) / len(code_words1 | code_words2)
        elif not code_words1 and not code_words2:
            topic_similarity = 0.5

        combined = 0.4 * jaccard + 0.3 * word_jaccard + 0.3 * topic_similarity

        return RelevanceResult(
            pane_id_1=id1,
            pane_id_2=id2,
            shared_keywords=list(shared),
            jaccard_similarity=jaccard,
            topic_similarity=topic_similarity,
            combined_score=combined
        )

    def build_relevance_matrix(
        self,
        panes: list[PaneData]
    ) -> dict[tuple[str, str], RelevanceResult]:
        """Build relevance matrix for all pane pairs."""
        matrix = {}
        for i, p1 in enumerate(panes):
            for j, p2 in enumerate(panes):
                if i < j:
                    result = self.calculate_relevance(p1.content, p2.content, p1.id, p2.id)
                    matrix[(p1.id, p2.id)] = result
                    matrix[(p2.id, p1.id)] = result
        return matrix

    def analyze_batch(self, panes: list[PaneData], compute_relevance: bool = True) -> AnalysisBatch:
        """
        Perform complete analysis on multiple panes.

        Args:
            panes: List of PaneData objects.
            compute_relevance: Whether to compute pairwise relevance.

        Returns:
            AnalysisBatch with all results.
        """
        results = self.analyze_panes(panes)
        relevance = self.build_relevance_matrix(panes) if compute_relevance else {}

        return AnalysisBatch(results=results, relevance_matrix=relevance)
