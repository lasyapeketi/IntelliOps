
from modules.complaint_sentiment.service import analyze_complaint


def test_payment_complaint():
    result = analyze_complaint(
        "My payment was deducted but the merchant did not receive it."
    )

    assert result["complaint_category"] == "Payment Issue"
    assert result["sentiment"] in {"Positive", "Negative", "Neutral"}
    assert 0 <= result["category_confidence"] <= 1


def test_empty_complaint_is_rejected():
    try:
        analyze_complaint("   ")
    except ValueError:
        return

    raise AssertionError("Expected empty complaint to raise ValueError")

