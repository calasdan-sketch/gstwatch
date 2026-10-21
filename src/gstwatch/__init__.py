"""gstwatch — GST/HST small-supplier threshold companion.

Rules verified against Canada.ca in October 2026 (see README). Not tax advice:
it applies the published rules to the numbers you give it and shows its work.
"""

from .evaluate import Status, evaluate, filing_frequency, retention_deadline, quarter_end

__version__ = "0.1.0"
__all__ = ["Status", "evaluate", "filing_frequency", "retention_deadline", "quarter_end",
           "__version__"]
