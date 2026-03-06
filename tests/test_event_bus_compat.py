from core.event_bus import EventBus


def test_payment_event_aliases_share_the_same_subscribers():
    bus = EventBus()
    seen: list[tuple[str, str]] = []

    bus.subscribe("PAYMENT_RECEIVED", lambda data: seen.append(("legacy", data["id"])))
    bus.subscribe("PAYMENT_RECORDED", lambda data: seen.append(("canonical", data["id"])))

    assert bus.get_subscriber_count("PAYMENT_RECEIVED") == 2
    assert bus.get_subscriber_count("PAYMENT_RECORDED") == 2

    assert bus.publish("PAYMENT_RECORDED", {"id": "PAY-1"}) == 2
    assert seen == [("legacy", "PAY-1"), ("canonical", "PAY-1")]

    seen.clear()
    assert bus.publish("PAYMENT_RECEIVED", {"id": "PAY-2"}) == 2
    assert seen == [("legacy", "PAY-2"), ("canonical", "PAY-2")]


def test_project_edited_alias_reaches_project_updated_subscribers():
    bus = EventBus()
    seen: list[str] = []

    bus.subscribe("PROJECT_UPDATED", lambda data: seen.append(data["id"]))

    assert bus.publish("PROJECT_EDITED", {"id": "PROJ-1"}) == 1
    assert seen == ["PROJ-1"]


def test_invoice_edited_alias_reaches_invoice_updated_subscribers():
    bus = EventBus()
    seen: list[str] = []

    bus.subscribe("INVOICE_UPDATED", lambda data: seen.append(data["id"]))

    assert bus.publish("INVOICE_EDITED", {"id": "INV-1"}) == 1
    assert seen == ["INV-1"]
