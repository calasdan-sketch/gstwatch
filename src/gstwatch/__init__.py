"""gstwatch — GST/HST small-supplier threshold companion.

Rules verified against Canada.ca, last re-verified 2026-11-07 (see README). Not tax advice:
it applies the published rules to the numbers you give it and shows its work.
"""

from .evaluate import Status, evaluate, filing_frequency, retention_deadline, quarter_end

__version__ = "0.2.0"
__all__ = ["Status", "evaluate", "filing_frequency", "retention_deadline", "quarter_end",
           "__version__"]
