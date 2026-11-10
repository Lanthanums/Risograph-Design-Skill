"""Measured, copy-preserving title line selection for the deck renderer.

The helper is deliberately isolated from the rendering pipeline.  A caller
passes the real advance-width function for the face and size it will draw::

    import textmetrics as tm
    lines = choose_title_lines(
        title,
        max_lines=2,
        measure=lambda value: tm.advance(value, "Georgia", 76, True),
        max_width=864,
    )
    if lines is None:
        # No measured, copy-preserving wrap exists.  Widen the type region,
        # reduce the requested size, or return the title as one line only if
        # the caller can prove it fits.
        ...
    fitted = "\\n".join(lines)

Rules implemented here:

* an unchanged single line is returned whenever it measures within the width;
* explicit newlines are hard boundaries and are never merged or reflowed
  across paragraphs;
* words are never changed, reordered, truncated, or dropped;
* explicit ``keep_phrases`` are never split across lines;
* candidates are ranked for balance, with dangling function words and a
  one-word final line penalised.  A one-word final line is only accepted when
  it is unavoidable or is a strong standalone word (``Why?``, ``Now``, ...);
* ``None`` is returned when no measured candidate satisfies the width, line
  budget, and phrase constraints.
"""

from __future__ import annotations

import math
import re
from typing import Callable, Iterable, List, NamedTuple, Optional, Sequence, Tuple

__all__ = ["choose_title_lines"]


_WORD_RE = re.compile(r"\S+", re.UNICODE)
_EDGE_PUNCT_RE = re.compile(r"^[^\w]+|[^\w]+$", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)
_NUMBER = re.compile(r"^[+−-]?\d+(?:[.,:]\d+)*(?:[–-]\d+)?$")
_UNIT = re.compile(r"^(?:%|°[CF]|kWh|Hz|kg|mg|km|cm|mm|mL|GB|MB|ms|pt|min|hrs?|USD|EUR|GBP|a\.m\.|p\.m\.)$")
_WEEKDAYS = {'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'}
_DAY_PARTS = {'morning', 'afternoon', 'evening', 'night'}

# A non-final line should not end on a word that needs what follows.  The set
# stays to closed-class words: articles, prepositions, conjunctions,
# auxiliaries, determiners and auxiliary contractions.  Adverbs such as
# "just" or "only" are intentionally absent because they can be a deliberate
# one-word display line.
_ARTICLES = frozenset({"a", "an", "the"})
_PREPOSITIONS = frozenset({
    "about", "above", "across", "after", "against", "along", "amid", "among",
    "around", "as", "at", "before", "behind", "below", "beneath", "beside",
    "besides", "between", "beyond", "by", "despite", "down", "during",
    "except", "for", "from", "in", "inside", "into", "like", "near", "of",
    "off", "on", "onto", "out", "outside", "over", "past", "per", "since",
    "than", "through", "throughout", "to", "toward", "towards", "under",
    "underneath", "until", "unto", "up", "upon", "via", "with", "within",
    "without", "vs", "versus",
})
_CONJUNCTIONS = frozenset({
    "and", "or", "but", "nor", "so", "yet", "because", "although", "though",
    "while", "whereas", "if", "when", "whenever", "where", "wherever",
    "whether", "that", "which", "who", "whom", "whose",
})
_AUXILIARIES = frozenset({
    "am", "is", "are", "was", "were", "be", "been", "being",
    "has", "have", "had", "do", "does", "did",
    "can", "could", "will", "would", "shall", "should", "may", "might",
    "must",
})
_DETERMINERS = frozenset({
    "this", "these", "those", "my", "your", "his", "her", "its", "our",
    "their", "some", "any", "each", "every", "either", "neither", "such",
    "all", "both", "many", "much", "more", "most", "few", "little", "less",
    "least", "another", "other", "same", "own",
})
_CONTRACTIONS = frozenset({
    "i'm", "i've", "i'd", "i'll", "you're", "you've", "you'd", "you'll",
    "he's", "he'd", "he'll", "she's", "she'd", "she'll", "it's", "it'd",
    "it'll", "we're", "we've", "we'd", "we'll", "they're", "they've",
    "they'd", "they'll", "that's", "there's", "here's", "what's", "who's",
    "where's", "when's", "why's", "how's", "don't", "doesn't", "didn't",
    "isn't", "aren't", "wasn't", "weren't", "hasn't", "haven't", "hadn't",
    "can't", "couldn't", "won't", "wouldn't", "shouldn't", "mustn't",
})
_DANGLING = frozenset(
    _ARTICLES | _PREPOSITIONS | _CONJUNCTIONS | _AUXILIARIES | _DETERMINERS
    | _CONTRACTIONS | {"not", "no"}
)

# A one-word final line is normally a widow/orphan.  These words can stand as
# a complete display line; punctuation such as "Why?" also qualifies.
_STRONG_STANDALONE = frozenset({
    "all", "again", "alone", "always", "anything", "ask", "back", "begin",
    "both", "build", "change", "check", "choose", "compare", "consider",
    "continue", "decide", "done", "draw", "enough", "everything", "finally",
    "first", "forward", "go", "goodbye", "grow", "hello", "here", "hold",
    "how", "imagine", "instead", "keep", "last", "learn", "less", "listen",
    "look", "make", "maybe", "measure", "more", "move", "never", "next",
    "no", "none", "nothing", "notice", "now", "perhaps", "please", "read",
    "ready", "remember", "run", "see", "share", "show", "something", "start",
    "stop", "tell", "test", "thank", "thanks", "then", "there", "think",
    "today", "together", "tomorrow", "try", "wait", "welcome", "what",
    "when", "where", "who", "whom", "why", "write", "yes", "yesterday",
})

# Bound the exact search for pathological titles.  A greedy measured wrap is
# always evaluated first, so hitting the cap cannot turn a legal wrap into
# ``None``; it only stops the search for a better ranked one.
_MAX_EXPLORED_STATES = 300_000


class _Candidate(NamedTuple):
    tier: int
    score: float
    lines: Tuple[str, ...]


class _SearchLimit(Exception):
    """Internal signal: the bounded candidate search is large enough."""


def _norm_token(value: str) -> str:
    """Lowercase a token and strip edge punctuation for matching only."""
    return _EDGE_PUNCT_RE.sub("", value).casefold()


def _phrase_norm_token(value: str) -> str:
    """Phrase matching also treats a possessive as its base noun."""
    token = _norm_token(value)
    for suffix in ("'s", "’s"):
        if token.endswith(suffix):
            return token[:-2]
    return token


def _tokens(value: str) -> List[str]:
    return _WORD_RE.findall(value)


def _last_token(value: str) -> Optional[str]:
    found = _WORD_RE.findall(value)
    return found[-1] if found else None


def _is_dangling(value: str) -> bool:
    token = _last_token(value)
    return bool(token) and _norm_token(token) in _DANGLING


def _is_strong_standalone(value: str) -> bool:
    token = value.strip()
    if not token:
        return False
    if token.endswith(("!", "?")):
        return True
    return _norm_token(token) in _STRONG_STANDALONE


def _clean_phrases(keep_phrases: Iterable[str]) -> Tuple[Tuple[str, ...], ...]:
    if keep_phrases is None:  # type: ignore[comparison-overlap]
        return ()
    if isinstance(keep_phrases, str):
        keep_phrases = (keep_phrases,)
    cleaned: List[Tuple[str, ...]] = []
    for phrase in keep_phrases:
        if not isinstance(phrase, str):
            raise TypeError("keep_phrases must contain only str values")
        tokens = tuple(
            token
            for token in (_phrase_norm_token(part) for part in phrase.split())
            if token
        )
        if tokens:
            cleaned.append(tokens)
    return tuple(cleaned)


def _make_atoms(
    tokens: Sequence[Tuple[str, int, int]],
    phrases: Sequence[Sequence[str]],
) -> List[Tuple[int, int]]:
    """Return token ranges that must not be split by a line break."""
    count = len(tokens)
    if not count:
        return []
    norms = [_phrase_norm_token(token[0]) for token in tokens]
    forced = [False] * (count - 1)
    for k in range(count - 1):
        following = tokens[k + 1][0]
        if ((_NUMBER.fullmatch(tokens[k][0]) and _UNIT.fullmatch(following.rstrip(',;:!?')))
                or (norms[k] in _WEEKDAYS and norms[k + 1] in _DAY_PARTS)
                or re.fullmatch(r'[,.;:!?%’”\)\]]+', following)):
            forced[k] = True
    for phrase in phrases:
        width = len(phrase)
        if not width or width > count:
            continue
        for start in range(count - width + 1):
            if all(norms[start + offset] == phrase[offset]
                   for offset in range(width)):
                for boundary in range(start, start + width - 1):
                    forced[boundary] = True
    atoms: List[Tuple[int, int]] = []
    start = 0
    for boundary, must_join in enumerate(forced):
        if not must_join:
            atoms.append((start, boundary + 1))
            start = boundary + 1
    atoms.append((start, count))
    return atoms


def _line_text(
    paragraph: str,
    tokens: Sequence[Tuple[str, int, int]],
    start: int,
    end: int,
) -> str:
    """Original source slice, so copy and internal spacing are not rewritten."""
    return paragraph[tokens[start][1]:tokens[end - 1][2]]


def _candidate(lines: Sequence[str], widths: Sequence[float],
               width_limit: float) -> _Candidate:
    """Rank one measured wrap.  Lower tier and lower score are better."""
    body = [(line, width) for line, width in zip(lines, widths) if line]
    body_count = len(body)
    mean = sum(width for _, width in body) / body_count if body_count else 0.0

    if body_count > 1:
        variance = sum((width - mean) ** 2 for _, width in body) / body_count
        balance = math.sqrt(variance) / width_limit
    else:
        balance = 0.0
    fill = max(0.0, (width_limit - mean) / width_limit)

    # A mild line-count term precedes balance rather than dominating it: a
    # genuinely balanced three-line title can beat a two-line one that leaves
    # a stub, while ordinary titles still use as few lines as possible.
    score = 0.12 * (len(lines) - 1) + balance + 0.05 * fill

    if body_count > 1:
        longest = max(width for _, width in body)
        if longest > 0:
            last_ratio = body[-1][1] / longest
            if last_ratio < 0.62:
                score += 0.18 * (0.62 - last_ratio)

    # A one-word non-final line is legal but usually a weak display break.
    for line, _ in body[:-1]:
        line_tokens = _tokens(line)
        if len(line_tokens) == 1 and not _is_strong_standalone(line_tokens[0]):
            score += 0.06

    score += 0.5 * sum(1 for line in lines if not line)

    final_tokens = _tokens(lines[-1]) if lines and lines[-1] else []
    strong_final = (
        len(final_tokens) == 1 and _is_strong_standalone(final_tokens[0])
    )
    orphan = len(final_tokens) == 1 and not strong_final
    dangling = sum(1 for line in lines[:-1] if line and _is_dangling(line))

    # Tier order follows the explicit orphan rule: a one-word final line is
    # only allowed when every legal wrap has one (or the word is a strong
    # standalone).  A dangling non-final close is still demoted, but it cannot
    # force a widow when a multi-word final line is available.
    #   0  no orphan, no dangling close
    #   1  no orphan, dangling close unavoidable
    #   2  orphan unavoidable, no dangling close
    #   3  orphan unavoidable and a dangling close
    tier = (2 if orphan else 0) + (1 if dangling else 0)
    score += 1.5 * dangling + (1.0 if orphan else 0.0)
    if strong_final:
        score += 0.02
    return _Candidate(tier, score, tuple(lines))


def has_weak_break(lines):
    """Allow the font-size search to prefer a clean wrap to a larger runt."""
    body = [line for line in lines if line.strip()]
    if len(body) < 2:
        return False
    last = _tokens(body[-1])
    return any(_is_dangling(line) for line in body[:-1]) or (
        len(last) == 1 and not _is_strong_standalone(last[0]))


def _better(candidate: _Candidate, current: _Candidate) -> bool:
    if candidate.tier != current.tier:
        return candidate.tier < current.tier
    if abs(candidate.score - current.score) > 1e-9:
        return candidate.score < current.score
    if len(candidate.lines) != len(current.lines):
        return len(candidate.lines) < len(current.lines)
    return candidate.lines < current.lines


def _greedy_lines(paragraphs, measured, width_limit: float,
                  line_limit: int) -> Optional[Tuple[List[str], List[float]]]:
    """A measured longest-line wrap; used as a safety fallback for big searches."""
    lines: List[str] = []
    widths: List[float] = []
    for paragraph, tokens, atoms, _fits_one_line in paragraphs:
        if not tokens:
            lines.append("")
            widths.append(0.0)
            if len(lines) > line_limit:
                return None
            continue
        position = 0
        while position < len(atoms):
            chosen = None
            for end in range(position + 1, len(atoms) + 1):
                line = _line_text(
                    paragraph, tokens,
                    atoms[position][0], atoms[end - 1][1],
                )
                width = measured(line)
                if width is None:
                    continue
                if width > width_limit:
                    # Keep scanning: measure is caller-supplied and need not
                    # be strictly monotone for every candidate string.
                    continue
                chosen = (end, line, width)
            if chosen is None:
                return None
            end, line, width = chosen
            lines.append(line)
            widths.append(width)
            if len(lines) > line_limit:
                return None
            position = end
    return lines, widths


def choose_title_lines(
    text: str,
    max_lines: int,
    measure: Callable[[str], float],
    max_width: float,
    keep_phrases: Iterable[str] = (),
) -> list[str] | None:
    """Choose measured title lines without changing the copy.

    Parameters
    ----------
    text:
        The exact title.  Explicit newlines are preserved as hard line
        boundaries; blank paragraphs become empty strings in the result.
    max_lines:
        Maximum number of output lines, including explicit blank lines.
    measure:
        ``measure(value) -> number`` in the same unit as ``max_width``.  It
        must include the real face, size, tracking, and any fitted offset the
        renderer will use.
    max_width:
        Maximum measured width of any output line.
    keep_phrases:
        Strings that must stay on one line.  Matching is whitespace- and
        case-insensitive and ignores edge punctuation.  Phrases that do not
        occur are ignored; a phrase wider than ``max_width`` makes the wrap
        impossible.

    Returns
    -------
    list[str] or None
        The selected lines, or ``None`` when no measured candidate satisfies
        the width, line budget, and phrase constraints.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a str")
    if not callable(measure):
        raise TypeError("measure must be callable")
    try:
        width_limit = float(max_width)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(width_limit) or width_limit <= 0:
        return None
    try:
        line_limit = int(max_lines)
    except (TypeError, ValueError, OverflowError):
        return None
    if line_limit < 1 or line_limit != max_lines:
        return None

    phrases = _clean_phrases(keep_phrases)
    normalized = (
        text.replace("\r\n", "\n").replace("\r", "\n")
        .replace("\u2028", "\n").replace("\u2029", "\n")
        .strip()
    )
    if not normalized:
        return None

    measurement_cache: dict[str, Optional[float]] = {}

    def measured(value: str) -> Optional[float]:
        if value in measurement_cache:
            return measurement_cache[value]
        try:
            result = float(measure(value))
        except Exception:
            # A glyph/measurement failure means this candidate cannot be
            # proven legal.  It must not abort the whole wrap.
            measurement_cache[value] = None
            return None
        if not math.isfinite(result) or result < 0:
            measurement_cache[value] = None
            return None
        measurement_cache[value] = result
        return result

    # Preserve an already-working single line exactly.  This is the strongest
    # preference in the contract.
    if "\n" not in normalized:
        whole_width = measured(normalized)
        if whole_width is not None and whole_width <= width_limit:
            return [normalized]

    paragraphs = []
    for paragraph in normalized.split("\n"):
        tokens = [
            (match.group(0), match.start(), match.end())
            for match in _WORD_RE.finditer(paragraph)
        ]
        atoms = _make_atoms(tokens, phrases)
        if tokens:
            whole = _line_text(
                paragraph, tokens, atoms[0][0], atoms[-1][1]
            )
            whole_width = measured(whole)
            # An explicit paragraph that already fits is an author-chosen
            # line.  Do not add a second break merely to improve balance.
            fits_one_line = (
                whole_width is not None and whole_width <= width_limit
            )
        else:
            fits_one_line = True
        paragraphs.append((paragraph, tokens, atoms, fits_one_line))

    source_compact = _WHITESPACE_RE.sub("", normalized)
    best: Optional[_Candidate] = None

    def consider(lines: List[str], widths: List[float]) -> None:
        nonlocal best
        if not lines or len(lines) > line_limit:
            return
        if _WHITESPACE_RE.sub("", "".join(lines)) != source_compact:
            return
        candidate = _candidate(lines, widths, width_limit)
        if best is None or _better(candidate, best):
            best = candidate

    # The greedy pass guarantees a valid fallback before the bounded search.
    fallback = _greedy_lines(paragraphs, measured, width_limit, line_limit)
    if fallback is not None:
        consider(*fallback)

    explored = 0

    def walk(paragraph_index: int, atom_index: int,
             lines: List[str], widths: List[float]) -> None:
        nonlocal explored
        explored += 1
        if explored > _MAX_EXPLORED_STATES:
            raise _SearchLimit

        if len(lines) > line_limit:
            return
        if paragraph_index == len(paragraphs):
            consider(lines, widths)
            return

        paragraph, tokens, atoms, fits_one_line = paragraphs[paragraph_index]
        if not tokens:
            if len(lines) < line_limit:
                walk(paragraph_index + 1, 0, lines + [""], widths + [0.0])
            return
        if atom_index == len(atoms):
            # A paragraph boundary is a hard break, never a merge point.
            walk(paragraph_index + 1, 0, lines, widths)
            return

        first_token = atoms[atom_index][0]
        ends = (len(atoms),) if fits_one_line else range(
            atom_index + 1, len(atoms) + 1
        )
        for end in ends:
            line = _line_text(paragraph, tokens, first_token, atoms[end - 1][1])
            width = measured(line)
            if width is None:
                continue
            if width > width_limit:
                # Keep scanning: the caller's measure is authoritative, and a
                # non-monotone fake or a kerning quirk must not hide a candidate.
                continue
            if len(lines) + 1 > line_limit:
                break
            walk(paragraph_index, end, lines + [line], widths + [width])

    try:
        walk(0, 0, [], [])
    except _SearchLimit:
        pass

    return list(best.lines) if best is not None else None
