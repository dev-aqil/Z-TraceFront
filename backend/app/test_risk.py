from datetime import datetime, timedelta

from app.risk import rule_based_risk_score


class FakeReading:
    def __init__(self, temperature):
        self.shipment_id = 1
        self.timestamp = datetime.now()
        self.temperature = temperature


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_):
        return self

    def order_by(self, *_):
        return self

    def all(self):
        return self.rows


class FakeDB:
    def __init__(self, rows):
        self.rows = rows

    def query(self, *_):
        return FakeQuery(self.rows)


def test_no_data_is_unknown():
    out = rule_based_risk_score(FakeDB([]), shipment_id=1)
    assert out["level"] == "UNKNOWN"


def test_temperature_excursion_raises_risk():
    out = rule_based_risk_score(FakeDB([FakeReading(3), FakeReading(12), FakeReading(13)]), shipment_id=1)
    assert out["score"] > 0
    assert out["level"] in {"MEDIUM", "HIGH"}


if __name__ == "__main__":
    test_no_data_is_unknown()
    test_temperature_excursion_raises_risk()
    print("ok")
