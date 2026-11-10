"""EntryLib's scoring rubric (RUBRIC.md): reliability scores of a claimset's claims and of the paper, computed by rules
from the published claimset file, and the novelty close-match check.

    score(doc)                    -> the scores of a claimset: claims, paper, problems (see score.py)
    novelty(claim, matches, ...)  -> a claim's novelty label and close-match result (see novelty.py)
    similarity(a, b)              -> how closely two claim statements match, 0 to 1
    stems(statement)              -> the stems similarity compares
    VERSION                       -> the rubric version every score records

Standard library only, Python 3.10+.
"""

from .novelty import novelty, similarity, stems
from .score import RUBRIC, VERSION, band, score

__all__ = ["RUBRIC", "VERSION", "band", "novelty", "score", "similarity", "stems"]
