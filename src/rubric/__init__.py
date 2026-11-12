"""EntryLib's scoring rubric (RUBRIC.md): reliability scores of a claimset's claims and of the paper, computed by rules
from the published claimset file, and the novelty close-match check.

    score(doc, warnings=None)     -> the scores of a claimset: claims, paper, problems (see score.py); warnings
                                     are the claimset validator's for the file (its validation report)
    assess(doc, find=None, warnings=None)
                                  -> score() with novelty, comparing principal claims with what find() returns
    novelty(claim, matches, ...)  -> a claim's novelty label and close-match result (see novelty.py)
    report(scores, biggest_n=0)   -> the scores as a plain-text report (see report.py)
    similarity(a, b)              -> how closely two claim statements match, 0 to 1
    stems(statement)              -> the stems similarity compares
    VERSION                       -> the rubric version every score records

Standard library only, Python 3.10+.
"""

from .novelty import assess, novelty, similarity, stems
from .report import report
from .score import RUBRIC, VERSION, band, score

__all__ = ["RUBRIC", "assess", "VERSION", "band", "novelty", "report", "score", "similarity", "stems"]
