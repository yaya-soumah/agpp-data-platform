from src.shared.currency import Currency

def test_supported_currencies_have_expected_iso_codes():
    assert Currency.USD.value == "USD"
    assert Currency.EUR.value == "EUR"
    assert Currency.GBP.value == "GBP"
    assert Currency.CNY.value == "CNY"

def test_currency_is_string_compatible():
    assert str(Currency.USD) == "USD"
    assert str(Currency.EUR) == "EUR"
    assert str(Currency.GBP) == "GBP"
    assert str(Currency.CNY) == "CNY"
    