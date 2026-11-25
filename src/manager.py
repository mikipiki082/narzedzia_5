import calendar
from datetime import date
from src.models import (
    Apartment,
    ApartmentSettlement,
    Bill,
    Parameters,
    Tenant,
    TenantSettlement,
    Transfer,
)



class Manager:
    def __init__(self, parameters: Parameters):
        self.parameters = parameters

        self.apartments = {}
        self.tenants = {}
        self.transfers = []
        self.bills = []

        self.load_data()

    def load_data(self):
        self.apartments = Apartment.from_json_file(self.parameters.apartments_json_path)
        self.tenants = Tenant.from_json_file(self.parameters.tenants_json_path)
        self.transfers = Transfer.from_json_file(self.parameters.transfers_json_path)
        self.bills = Bill.from_json_file(self.parameters.bills_json_path)

    def check_tenants_apartment_keys(self) -> bool:
        for tenant in self.tenants.values():
            if tenant.apartment not in self.apartments:
                return False
        return True

    def get_apartment_costs(
        self,
        apartment_key: str,
        year: int | None = None,
        month: int | None = None,
    ) -> float | None:
        if month is not None and not (1 <= month <= 12):
            raise ValueError(f"Invalid month: {month}. Month must be between 1 and 12.")

        if apartment_key not in self.apartments:
            return None

        total_cost = 0.0
        for bill in self.bills:
            if bill.apartment != apartment_key:
                continue
            if year is not None and bill.settlement_year != year:
                continue
            if month is not None and bill.settlement_month != month:
                continue

            total_cost += bill.amount_pln

        return total_cost

    def create_apartment_settlement(
        self, apartment_key: str, year: int, month: int
    ) -> ApartmentSettlement | None:
        total_bills = self.get_apartment_costs(apartment_key, year, month)
        if total_bills is None:
            return None

        # Przelewy będą uwzględnione w kolejnym kroku (obecnie 0.0)
        total_transfers = 0.0
        balance = total_transfers - total_bills

        return ApartmentSettlement(
            apartment=apartment_key,
            month=month,
            year=year,
            total_rent_pln=0.0,
            total_bills_pln=total_bills,
            total_due_pln=balance,
        )
    def create_tenant_settlements(
        self, apartment_settlement: ApartmentSettlement
    ) -> list[TenantSettlement]:
        last_day = calendar.monthrange(
            apartment_settlement.year, apartment_settlement.month
        )[1]
        period_start = date(apartment_settlement.year, apartment_settlement.month, 1)
        period_end = date(apartment_settlement.year, apartment_settlement.month, last_day)

        active_tenants: list[tuple[str, Tenant]] = []
        for tenant_key, tenant in self.tenants.items():
            if tenant.apartment != apartment_settlement.apartment:
                continue

            agreement_from = date.fromisoformat(tenant.date_agreement_from)
            agreement_to = date.fromisoformat(tenant.date_agreement_to)

            if agreement_from <= period_end and agreement_to >= period_start:
                active_tenants.append((tenant_key, tenant))

        if not active_tenants:
            return []

        bills_share = apartment_settlement.total_bills_pln / len(active_tenants)
        settlement_id = (
            f"{apartment_settlement.apartment}-"
            f"{apartment_settlement.year}-"
            f"{apartment_settlement.month:02d}"
        )

        settlements: list[TenantSettlement] = []
        for tenant_key, tenant in active_tenants:
            total_due = tenant.rent_pln + bills_share
            # Przelewy będą uwzględnione w kolejnym kroku (obecnie 0.0)
            balance = 0.0 - total_due

            settlements.append(
                TenantSettlement(
                    tenant=tenant_key,
                    apartment_settlement=settlement_id,
                    month=apartment_settlement.month,
                    year=apartment_settlement.year,
                    rent_pln=tenant.rent_pln,
                    bills_pln=bills_share,
                    total_due_pln=total_due,
                    balance_pln=balance,
                )
            )

        return settlements
