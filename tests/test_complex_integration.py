import json
import pytest
from src.manager import Manager
from src.models import Bill, Parameters
from src.models import ApartmentSettlement
from src.models import Tenant, TenantSettlement

def test_apartment_costs_with_optional_parameters():
    manager = Manager(Parameters())
    manager.bills.append(Bill(
        apartment='apart-polanka',
        date_due='2025-03-15',
        settlement_year=2025,
        settlement_month=2,
        amount_pln=1250.0,
        type='rent'
    ))

    manager.bills.append(Bill(
        apartment='apart-polanka',
        date_due='2024-03-15',
        settlement_year=2024,
        settlement_month=2,
        amount_pln=1150.0,
        type='rent'
    ))

    manager.bills.append(Bill(
        apartment='apart-polanka',
        date_due='2024-02-02',
        settlement_year=2024,
        settlement_month=1,
        amount_pln=222.0,
        type='electricity'
    ))

    costs = manager.get_apartment_costs('apartment-1', 2024, 1)
    assert costs is None

    costs = manager.get_apartment_costs('apart-polanka', 2024, 3)
    assert costs == 0.0

    costs = manager.get_apartment_costs('apart-polanka', 2024, 1)
    assert costs == 222.0

    costs = manager.get_apartment_costs('apart-polanka', 2025, 1)
    assert costs == 910.0

    costs = manager.get_apartment_costs('apart-polanka', 2024)
    assert costs == 1372.0

    costs = manager.get_apartment_costs('apart-polanka')
    assert costs == 3532.0


@pytest.fixture
def setup_manager(tmp_path):
    apartments_data = {
        "apart-polanka": {
            "key": "apart-polanka",
            "name": "Mieszkanie Polanka",
            "location": "Poznań, ul. Polanka 1",
            "area_m2": 45.0,
            "rooms": {}
        },
        "apart-centrum": {
            "key": "apart-centrum",
            "name": "Apartament Centrum",
            "location": "Poznań, ul. Święty Marcin 10",
            "area_m2": 60.0,
            "rooms": {}
        }
    }
    tenants_data = {}
    transfers_data = []
    bills_data = [
        {
            "amount_pln": 760.00,
            "date_due": "2025-02-15",
            "settlement_year": 2025,
            "settlement_month": 1,
            "apartment": "apart-polanka",
            "type": "rent"
        },
        {
            "amount_pln": 150.00,
            "date_due": "2025-02-12",
            "settlement_year": 2025,
            "settlement_month": 1,
            "apartment": "apart-polanka",
            "type": "electricity"
        },
        {
            "amount_pln": 800.00,
            "date_due": "2025-03-15",
            "settlement_year": 2025,
            "settlement_month": 2,
            "apartment": "apart-polanka",
            "type": "rent"
        },
        {
            "amount_pln": 1200.00,
            "date_due": "2025-02-15",
            "settlement_year": 2025,
            "settlement_month": 1,
            "apartment": "apart-centrum",
            "type": "rent"
        }
    ]

    apt_file = tmp_path / "apartments.json"
    ten_file = tmp_path / "tenants.json"
    tra_file = tmp_path / "transfers.json"
    bil_file = tmp_path / "bills.json"

    apt_file.write_text(json.dumps(apartments_data), encoding="utf-8")
    ten_file.write_text(json.dumps(tenants_data), encoding="utf-8")
    tra_file.write_text(json.dumps(transfers_data), encoding="utf-8")
    bil_file.write_text(json.dumps(bills_data), encoding="utf-8")

    params = Parameters(
        apartments_json_path=str(apt_file),
        tenants_json_path=str(ten_file),
        transfers_json_path=str(tra_file),
        bills_json_path=str(bil_file)
    )
    return Manager(params)


def test_get_apartment_costs(setup_manager):
    manager = setup_manager

    # 1. Mieszkanie istnieje i ma 2 rachunki w styczniu 2025
    assert manager.get_apartment_costs("apart-polanka", 2025, 1) == pytest.approx(910.00)

    # 2. Mieszkanie nie ma rachunków w grudniu 2025
    assert manager.get_apartment_costs("apart-polanka", 2025, 12) == 0.0

    # 3. Mieszkanie nie istnieje w bazie
    assert manager.get_apartment_costs("nieistniejace-mieszkanie", 2025, 1) is None

    # 4. Suma dla całego roku (bez podania miesiąca)
    assert manager.get_apartment_costs("apart-polanka", 2025) == pytest.approx(1710.00)

    # 5. Suma dla całej historii (bez podania roku i miesiąca)
    assert manager.get_apartment_costs("apart-polanka") == pytest.approx(1710.00)


def test_get_apartment_costs_invalid_month(setup_manager):
    manager = setup_manager

    with pytest.raises(ValueError):
        manager.get_apartment_costs("apart-polanka", 2025, 13)

    with pytest.raises(ValueError):
        manager.get_apartment_costs("apart-polanka", 2025, 0)


def test_create_apartment_settlement(setup_manager):
    manager = setup_manager
    # Scenariusz 1: Mieszkanie ma rachunki w styczniu 2025 (760.00 rent + 150.00 electricity = 910.00)
    settlement = manager.create_apartment_settlement("apart-polanka", 2025, 1)
    assert settlement is not None
    assert isinstance(settlement, ApartmentSettlement)
    assert settlement.apartment == "apart-polanka"
    assert settlement.year == 2025
    assert settlement.month == 1
    assert settlement.total_bills_pln == pytest.approx(910.00)
    # Bilans (przelewy 0.0 - rachunki 910.00 = -910.00)
    assert settlement.total_due_pln == pytest.approx(-910.00)
    # Scenariusz 2: Mieszkanie istnieje, ale nie ma rachunków w grudniu 2025
    empty_settlement = manager.create_apartment_settlement("apart-polanka", 2025, 12)
    assert empty_settlement is not None
    assert empty_settlement.apartment == "apart-polanka"
    assert empty_settlement.total_bills_pln == 0.0
    assert empty_settlement.total_due_pln == 0.0
    # Scenariusz 3: Mieszkanie nie istnieje
    assert manager.create_apartment_settlement("nieistniejace", 2025, 1) is None
    # Scenariusz 4: Nieprawidłowy miesiąc
    with pytest.raises(ValueError):
        manager.create_apartment_settlement("apart-polanka", 2025, 13)

def test_create_tenant_settlements(setup_manager):
    manager = setup_manager

    manager.tenants["jan-kowalski"] = Tenant(
        name="Jan Kowalski",
        apartment="apart-polanka",
        room="room-1",
        rent_pln=1000.0,
        deposit_pln=1000.0,
        date_agreement_from="2024-01-01",
        date_agreement_to="2025-12-31",
    )
    manager.tenants["anna-nowak"] = Tenant(
        name="Anna Nowak",
        apartment="apart-polanka",
        room="room-2",
        rent_pln=1200.0,
        deposit_pln=1200.0,
        date_agreement_from="2025-01-01",
        date_agreement_to="2025-06-30",
    )
    manager.tenants["byly-najemca"] = Tenant(
        name="Piotr Stary",
        apartment="apart-polanka",
        room="room-1",
        rent_pln=900.0,
        deposit_pln=900.0,
        date_agreement_from="2024-01-01",
        date_agreement_to="2024-12-31",
    )

    manager.tenants["marek-solo"] = Tenant(
        name="Marek Solo",
        apartment="apart-centrum",
        room="room-1",
        rent_pln=2500.0,
        deposit_pln=2500.0,
        date_agreement_from="2025-01-01",
        date_agreement_to="2025-12-31",
    )

    # Scenariusz 1: Mieszkanie ma 2 aktualnych najemców (rachunki 910.00 / 2 = 455.00 na osobę)
    apt_settlement_polanka = manager.create_apartment_settlement("apart-polanka", 2025, 1)
    polanka_tenants = manager.create_tenant_settlements(apt_settlement_polanka)

    assert len(polanka_tenants) == 2
    assert all(isinstance(ts, TenantSettlement) for ts in polanka_tenants)

    settlements_by_tenant = {ts.tenant: ts for ts in polanka_tenants}
    assert "byly-najemca" not in settlements_by_tenant

    ts_jan = settlements_by_tenant["jan-kowalski"]
    assert ts_jan.month == 1
    assert ts_jan.year == 2025
    assert ts_jan.rent_pln == pytest.approx(1000.0)
    assert ts_jan.bills_pln == pytest.approx(455.0)
    assert ts_jan.total_due_pln == pytest.approx(1455.0)
    assert ts_jan.balance_pln == pytest.approx(-1455.0)

    ts_anna = settlements_by_tenant["anna-nowak"]
    assert ts_anna.bills_pln == pytest.approx(455.0)
    assert ts_anna.total_due_pln == pytest.approx(1655.0)
    assert ts_anna.balance_pln == pytest.approx(-1655.0)

    # Scenariusz 2: Mieszkanie ma 1 najemcę (rachunki 1200.00 / 1 = 1200.00)
    apt_settlement_centrum = manager.create_apartment_settlement("apart-centrum", 2025, 1)
    centrum_tenants = manager.create_tenant_settlements(apt_settlement_centrum)

    assert len(centrum_tenants) == 1
    assert centrum_tenants[0].tenant == "marek-solo"
    assert centrum_tenants[0].bills_pln == pytest.approx(1200.0)
    assert centrum_tenants[0].total_due_pln == pytest.approx(3700.0)

    # Scenariusz 3: Mieszkanie nie ma żadnych najemców (brak rozliczeń)
    manager.tenants.clear()
    empty_tenants = manager.create_tenant_settlements(apt_settlement_polanka)
    assert empty_tenants == []
