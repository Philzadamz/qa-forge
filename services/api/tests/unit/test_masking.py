from app.services.ai.masking import mask_secrets, mask_text


def test_masks_nuban_account_number() -> None:
    result = mask_text("Please debit account 0123456789 for the transfer.")
    assert "0123456789" not in result.text
    assert "[MASKED_ACCOUNT_1]" in result.text
    assert result.counts["ACCOUNT"] == 1


def test_masks_bvn() -> None:
    result = mask_text("BVN on file is 12345678901.")
    assert "12345678901" not in result.text
    assert result.counts["BVN_NIN"] == 1


def test_masks_valid_card_pan_but_not_random_long_number() -> None:
    # 4111111111111111 is a well-known Luhn-valid test PAN.
    result = mask_text("Card used: 4111111111111111")
    assert "4111111111111111" not in result.text
    assert result.counts["CARD"] == 1


def test_masks_email() -> None:
    result = mask_text("Contact jane.doe@example.com for details.")
    assert "jane.doe@example.com" not in result.text
    assert result.counts["EMAIL"] == 1


def test_masks_nigerian_phone_number() -> None:
    result = mask_text("Call 08012345678 to confirm.")
    assert "08012345678" not in result.text
    assert result.counts["PHONE"] == 1


def test_email_masking_can_be_disabled() -> None:
    result = mask_text("Contact jane.doe@example.com", mask_email=False)
    assert "jane.doe@example.com" in result.text
    assert "EMAIL" not in result.counts


def test_leaves_ordinary_text_untouched() -> None:
    result = mask_text("Check that the login page renders correctly.")
    assert result.text == "Check that the login page renders correctly."
    assert result.total_masked == 0


def test_mask_secrets_replaces_known_values() -> None:
    result = mask_secrets("The password is hunter2, confirm it.", ["hunter2"])
    assert "hunter2" not in result.text
    assert result.counts["SECRET"] == 1


def test_mask_secrets_ignores_empty_values() -> None:
    result = mask_secrets("Nothing to hide here.", ["", None])  # type: ignore[list-item]
    assert result.text == "Nothing to hide here."
    assert result.total_masked == 0
