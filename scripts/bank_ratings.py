"""Bank name -> ethical rating (1 worst ... 5 ethical), from bank-ratings.md (bank.green). One copy - import it.

Matching is by keyword, longest first ("royal bank of scotland" before "bank of scotland").
RBS is not in bank-ratings.md, so it is "not rated" (never folded into Bank of Scotland).
"""
RATINGS = {
    "barclays": 1, "hsbc": 1, "natwest": 1, "nat west": 1, "national westminster": 1, "santander": 1,
    "standard chartered": 1, "tsb": 1,
    "bank of scotland": 3, "halifax": 3, "lloyds": 3,
    "tide": 4,
    "caf": 5, "charities aid": 5, "charities' aid": 5, "co-operative": 5, "cooperative": 5, "co-op": 5,
    "charity bank": 5, "clydesdale": 5, "handelsbanken": 5, "nationwide": 5, "metro bank": 5, "unity trust": 5,
    "triodos": 5, "virgin money": 5, "yorkshire bank": 5,
}
NOT_RATED = ("royal bank of scotland",)


def rate(bank, ratings=RATINGS):
    """Rating 1-5, or None when the bank is unknown / not in bank-ratings.md."""
    s = (bank or "").lower()
    if not s or any(k in s for k in NOT_RATED):
        return None
    for k in sorted(ratings, key=len, reverse=True):
        if k in s:
            return ratings[k]
    return None
