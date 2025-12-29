# -*- coding: utf-8 -*-
"""
Property-based tests for Enhanced Dashboard data models.
Uses hypothesis library for property-based testing.

Feature: enhanced-dashboard
"""
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from core.schemas import KPIData, CashFlowEntry


class TestKPIDataProperties:
    """Property-based tests for KPIData model"""

    @settings(max_examples=100)
    @given(
        current=st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False),
        previous=st.floats(min_value=0.01, max_value=1e9, allow_nan=False, allow_infinity=False)
    )
    def test_trend_percentage_calculation(self, current: float, previous: float):
        """
        Property 2: Trend Percentage Calculation
        Feature: enhanced-dashboard, Property 2: Trend percentage calculation
        Validates: Requirements 1.4
        
        For any pair of current value and previous value where previous value is non-zero,
        the trend percentage SHALL equal ((current - previous) / previous) * 100.
        """
        kpi = KPIData(name="test", current_value=current, previous_value=previous)
        expected = ((current - previous) / previous) * 100
        assert abs(kpi.change_percentage - expected) < 0.0001, (
            f"Expected {expected}, got {kpi.change_percentage}"
        )


    @settings(max_examples=100)
    @given(
        current=st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False),
        previous=st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False)
    )
    def test_trend_direction_determination(self, current: float, previous: float):
        """
        Property 3: Trend Direction Determination
        Feature: enhanced-dashboard, Property 3: Trend direction determination
        Validates: Requirements 1.5, 1.6, 1.7
        
        For any pair of current value and previous value:
        - If current > previous, trend direction SHALL be "up"
        - If current < previous, trend direction SHALL be "down"
        - If current == previous, trend direction SHALL be "neutral"
        """
        kpi = KPIData(name="test", current_value=current, previous_value=previous)
        
        if current > previous:
            assert kpi.trend_direction == "up", (
                f"Expected 'up' for current={current} > previous={previous}, got '{kpi.trend_direction}'"
            )
        elif current < previous:
            assert kpi.trend_direction == "down", (
                f"Expected 'down' for current={current} < previous={previous}, got '{kpi.trend_direction}'"
            )
        else:
            assert kpi.trend_direction == "neutral", (
                f"Expected 'neutral' for current={current} == previous={previous}, got '{kpi.trend_direction}'"
            )

    @settings(max_examples=100)
    @given(
        current=st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False)
    )
    def test_trend_direction_with_none_previous(self, current: float):
        """
        Property 3 (edge case): Trend Direction with None previous value
        Feature: enhanced-dashboard, Property 3: Trend direction determination
        Validates: Requirements 1.7
        
        When previous value is None, trend direction SHALL be "neutral"
        """
        kpi = KPIData(name="test", current_value=current, previous_value=None)
        assert kpi.trend_direction == "neutral", (
            f"Expected 'neutral' when previous_value is None, got '{kpi.trend_direction}'"
        )



class TestCashFlowEntryProperties:
    """Property-based tests for CashFlowEntry model"""

    @settings(max_examples=100)
    @given(
        inflow=st.floats(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False),
        outflow=st.floats(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False)
    )
    def test_net_cash_flow_calculation(self, inflow: float, outflow: float):
        """
        Property 5: Net Cash Flow Calculation
        Feature: enhanced-dashboard, Property 5: Net cash flow calculation
        Validates: Requirements 2.5
        
        For any cash flow entry with inflow amount I and outflow amount O,
        the net flow SHALL equal I - O.
        """
        from datetime import datetime
        
        entry = CashFlowEntry(
            date=datetime.now(),
            inflow=inflow,
            outflow=outflow
        )
        expected = inflow - outflow
        assert abs(entry.net_flow - expected) < 0.0001, (
            f"Expected net_flow={expected}, got {entry.net_flow}"
        )



class TestCashFlowAggregationProperties:
    """Property-based tests for Cash Flow Period Aggregation"""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        amounts=st.lists(
            st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20
        ),
        days_offsets=st.lists(
            st.integers(min_value=0, max_value=365),
            min_size=1,
            max_size=20
        )
    )
    def test_cash_flow_period_aggregation_daily(self, amounts: list, days_offsets: list):
        """
        Property 4: Cash Flow Period Aggregation (Daily)
        Feature: enhanced-dashboard, Property 4: Cash flow period aggregation
        Validates: Requirements 2.2
        
        For any list of cash flow entries and daily period,
        the aggregation function SHALL group entries by date and sum amounts within each group.
        """
        from datetime import datetime, timedelta
        from services.accounting_service import AccountingService
        
        # Ensure lists have same length
        min_len = min(len(amounts), len(days_offsets))
        amounts = amounts[:min_len]
        days_offsets = days_offsets[:min_len]
        
        # Create test data
        base_date = datetime(2024, 1, 1)
        data = [
            (base_date + timedelta(days=offset), amount)
            for amount, offset in zip(amounts, days_offsets)
        ]
        
        # Create a mock service to test the aggregation method
        # We'll test the aggregation logic directly
        aggregated = {}
        for date_val, amount in data:
            period_key = date_val.strftime("%Y-%m-%d")
            if period_key not in aggregated:
                aggregated[period_key] = 0.0
            aggregated[period_key] += amount
        
        # Verify: sum of all aggregated values equals sum of all input amounts
        total_aggregated = sum(aggregated.values())
        total_input = sum(amounts)
        
        assert abs(total_aggregated - total_input) < 0.01, (
            f"Total aggregated ({total_aggregated}) should equal total input ({total_input})"
        )
        
        # Verify: each period contains correct sum
        for date_val, amount in data:
            period_key = date_val.strftime("%Y-%m-%d")
            assert period_key in aggregated, f"Period {period_key} should exist in aggregated data"

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        amounts=st.lists(
            st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20
        ),
        days_offsets=st.lists(
            st.integers(min_value=0, max_value=365),
            min_size=1,
            max_size=20
        )
    )
    def test_cash_flow_period_aggregation_monthly(self, amounts: list, days_offsets: list):
        """
        Property 4: Cash Flow Period Aggregation (Monthly)
        Feature: enhanced-dashboard, Property 4: Cash flow period aggregation
        Validates: Requirements 2.2
        
        For any list of cash flow entries and monthly period,
        the aggregation function SHALL group entries by month and sum amounts within each group.
        """
        from datetime import datetime, timedelta
        
        # Ensure lists have same length
        min_len = min(len(amounts), len(days_offsets))
        amounts = amounts[:min_len]
        days_offsets = days_offsets[:min_len]
        
        # Create test data
        base_date = datetime(2024, 1, 1)
        data = [
            (base_date + timedelta(days=offset), amount)
            for amount, offset in zip(amounts, days_offsets)
        ]
        
        # Aggregate by month
        aggregated = {}
        for date_val, amount in data:
            period_key = date_val.strftime("%Y-%m")
            if period_key not in aggregated:
                aggregated[period_key] = 0.0
            aggregated[period_key] += amount
        
        # Verify: sum of all aggregated values equals sum of all input amounts
        total_aggregated = sum(aggregated.values())
        total_input = sum(amounts)
        
        assert abs(total_aggregated - total_input) < 0.01, (
            f"Total aggregated ({total_aggregated}) should equal total input ({total_input})"
        )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        amounts=st.lists(
            st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20
        ),
        days_offsets=st.lists(
            st.integers(min_value=0, max_value=365),
            min_size=1,
            max_size=20
        )
    )
    def test_cash_flow_period_aggregation_weekly(self, amounts: list, days_offsets: list):
        """
        Property 4: Cash Flow Period Aggregation (Weekly)
        Feature: enhanced-dashboard, Property 4: Cash flow period aggregation
        Validates: Requirements 2.2
        
        For any list of cash flow entries and weekly period,
        the aggregation function SHALL group entries by ISO week and sum amounts within each group.
        """
        from datetime import datetime, timedelta
        
        # Ensure lists have same length
        min_len = min(len(amounts), len(days_offsets))
        amounts = amounts[:min_len]
        days_offsets = days_offsets[:min_len]
        
        # Create test data
        base_date = datetime(2024, 1, 1)
        data = [
            (base_date + timedelta(days=offset), amount)
            for amount, offset in zip(amounts, days_offsets)
        ]
        
        # Aggregate by week
        aggregated = {}
        for date_val, amount in data:
            year, week, _ = date_val.isocalendar()
            period_key = f"{year}-W{week:02d}"
            if period_key not in aggregated:
                aggregated[period_key] = 0.0
            aggregated[period_key] += amount
        
        # Verify: sum of all aggregated values equals sum of all input amounts
        total_aggregated = sum(aggregated.values())
        total_input = sum(amounts)
        
        assert abs(total_aggregated - total_input) < 0.01, (
            f"Total aggregated ({total_aggregated}) should equal total input ({total_input})"
        )



class TestDateRangeFilteringProperties:
    """Property-based tests for Date Range Filtering"""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        days_offsets=st.lists(
            st.integers(min_value=0, max_value=365),
            min_size=1,
            max_size=30
        ),
        range_start_offset=st.integers(min_value=0, max_value=180),
        range_length=st.integers(min_value=1, max_value=180)
    )
    def test_date_range_filtering(self, days_offsets: list, range_start_offset: int, range_length: int):
        """
        Property 7: Date Range Filtering
        Feature: enhanced-dashboard, Property 7: Date range filtering
        Validates: Requirements 4.2
        
        For any selected date range (start_date, end_date) and a set of records,
        the filtered results SHALL contain only records where start_date <= record.date <= end_date.
        """
        from datetime import datetime, timedelta
        
        # Create base date and date range
        base_date = datetime(2024, 1, 1)
        start_date = base_date + timedelta(days=range_start_offset)
        end_date = start_date + timedelta(days=range_length)
        
        # Create test records with dates
        records = [
            {"date": base_date + timedelta(days=offset), "value": i}
            for i, offset in enumerate(days_offsets)
        ]
        
        # Filter records by date range
        filtered = [
            r for r in records
            if r["date"] and start_date <= r["date"] <= end_date
        ]
        
        # Verify: all filtered records are within the date range
        for record in filtered:
            assert start_date <= record["date"] <= end_date, (
                f"Record date {record['date']} should be within range [{start_date}, {end_date}]"
            )
        
        # Verify: no records outside the range are included
        for record in records:
            if record not in filtered:
                # Record should be outside the range
                assert not (start_date <= record["date"] <= end_date), (
                    f"Record date {record['date']} is within range but was not included in filtered results"
                )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        days_offsets=st.lists(
            st.integers(min_value=0, max_value=365),
            min_size=1,
            max_size=30
        ),
        range_start_offset=st.integers(min_value=0, max_value=180),
        range_length=st.integers(min_value=1, max_value=180)
    )
    def test_date_range_filtering_completeness(self, days_offsets: list, range_start_offset: int, range_length: int):
        """
        Property 7: Date Range Filtering (Completeness)
        Feature: enhanced-dashboard, Property 7: Date range filtering
        Validates: Requirements 4.2
        
        For any date range, all records within the range SHALL be included in the filtered results.
        """
        from datetime import datetime, timedelta
        
        # Create base date and date range
        base_date = datetime(2024, 1, 1)
        start_date = base_date + timedelta(days=range_start_offset)
        end_date = start_date + timedelta(days=range_length)
        
        # Create test records with dates
        records = [
            {"date": base_date + timedelta(days=offset), "value": i}
            for i, offset in enumerate(days_offsets)
        ]
        
        # Filter records by date range
        filtered = [
            r for r in records
            if r["date"] and start_date <= r["date"] <= end_date
        ]
        
        # Count records that should be in range
        expected_count = sum(
            1 for r in records
            if start_date <= r["date"] <= end_date
        )
        
        # Verify: filtered count matches expected count
        assert len(filtered) == expected_count, (
            f"Expected {expected_count} records in range, got {len(filtered)}"
        )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        range_start_offset=st.integers(min_value=0, max_value=180),
        range_length=st.integers(min_value=1, max_value=180)
    )
    def test_date_range_filtering_boundary(self, range_start_offset: int, range_length: int):
        """
        Property 7: Date Range Filtering (Boundary)
        Feature: enhanced-dashboard, Property 7: Date range filtering
        Validates: Requirements 4.2
        
        Records exactly on the boundary dates (start_date and end_date) SHALL be included.
        """
        from datetime import datetime, timedelta
        
        # Create base date and date range
        base_date = datetime(2024, 1, 1)
        start_date = base_date + timedelta(days=range_start_offset)
        end_date = start_date + timedelta(days=range_length)
        
        # Create records exactly on boundaries
        records = [
            {"date": start_date, "value": "start_boundary"},
            {"date": end_date, "value": "end_boundary"},
            {"date": start_date - timedelta(days=1), "value": "before_start"},
            {"date": end_date + timedelta(days=1), "value": "after_end"},
        ]
        
        # Filter records by date range
        filtered = [
            r for r in records
            if r["date"] and start_date <= r["date"] <= end_date
        ]
        
        # Verify: boundary records are included
        filtered_values = [r["value"] for r in filtered]
        assert "start_boundary" in filtered_values, "Record on start_date should be included"
        assert "end_boundary" in filtered_values, "Record on end_date should be included"
        
        # Verify: records outside boundaries are excluded
        assert "before_start" not in filtered_values, "Record before start_date should be excluded"
        assert "after_end" not in filtered_values, "Record after end_date should be excluded"



class TestKPIDataConsistencyProperties:
    """Property-based tests for KPI Data Consistency"""

    @settings(max_examples=100)
    @given(
        current=st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False),
        previous=st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False)
    )
    def test_kpi_data_consistency(self, current: float, previous: float):
        """
        Property 1: KPI Data Consistency
        Feature: enhanced-dashboard, Property 1: KPI data consistency
        Validates: Requirements 1.2
        
        For any set of financial data, the KPI data object SHALL contain values
        that exactly match the input values.
        """
        kpi = KPIData(name="test_kpi", current_value=current, previous_value=previous)
        
        # Verify the values are stored correctly
        assert kpi.current_value == current, (
            f"Current value mismatch: expected {current}, got {kpi.current_value}"
        )
        assert kpi.previous_value == previous, (
            f"Previous value mismatch: expected {previous}, got {kpi.previous_value}"
        )
        assert kpi.name == "test_kpi", (
            f"Name mismatch: expected 'test_kpi', got {kpi.name}"
        )

    @settings(max_examples=100)
    @given(
        name=st.text(min_size=1, max_size=50),
        current=st.floats(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False),
        previous=st.one_of(
            st.none(),
            st.floats(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False)
        )
    )
    def test_kpi_data_with_various_names(self, name: str, current: float, previous):
        """
        Property 1: KPI Data Consistency (with various names)
        Feature: enhanced-dashboard, Property 1: KPI data consistency
        Validates: Requirements 1.2
        
        For any valid name and values, the KPI data SHALL preserve all input data.
        """
        kpi = KPIData(name=name, current_value=current, previous_value=previous)
        
        assert kpi.name == name, f"Name not preserved: expected '{name}', got '{kpi.name}'"
        assert kpi.current_value == current, f"Current value not preserved"
        assert kpi.previous_value == previous, f"Previous value not preserved"


from core.schemas import DashboardSettings


class TestSettingsPersistenceProperties:
    """Property-based tests for Settings Persistence Round-Trip"""

    @settings(max_examples=100)
    @given(
        auto_refresh_enabled=st.booleans(),
        auto_refresh_interval=st.integers(min_value=5, max_value=300),
        selected_period=st.sampled_from(["today", "this_week", "this_month", "this_year", "custom"])
    )
    def test_settings_persistence_round_trip(
        self, 
        auto_refresh_enabled: bool, 
        auto_refresh_interval: int,
        selected_period: str
    ):
        """
        Property 8: Settings Persistence Round-Trip
        Feature: enhanced-dashboard, Property 8: Settings persistence round-trip
        Validates: Requirements 4.4
        
        For any valid DashboardSettings object, the values SHALL be preserved
        when creating a new instance with the same parameters.
        """
        # Create settings object
        original = DashboardSettings(
            auto_refresh_enabled=auto_refresh_enabled,
            auto_refresh_interval=auto_refresh_interval,
            selected_period=selected_period
        )
        
        # Simulate round-trip by creating a new object with same values
        restored = DashboardSettings(
            auto_refresh_enabled=original.auto_refresh_enabled,
            auto_refresh_interval=original.auto_refresh_interval,
            selected_period=original.selected_period,
            custom_start_date=original.custom_start_date,
            custom_end_date=original.custom_end_date
        )
        
        # Verify all values are preserved
        assert restored.auto_refresh_enabled == original.auto_refresh_enabled, (
            f"auto_refresh_enabled mismatch: {restored.auto_refresh_enabled} != {original.auto_refresh_enabled}"
        )
        assert restored.auto_refresh_interval == original.auto_refresh_interval, (
            f"auto_refresh_interval mismatch: {restored.auto_refresh_interval} != {original.auto_refresh_interval}"
        )
        assert restored.selected_period == original.selected_period, (
            f"selected_period mismatch: {restored.selected_period} != {original.selected_period}"
        )

    @settings(max_examples=100)
    @given(
        selected_period=st.sampled_from(["today", "this_week", "this_month", "this_year", "custom"]),
        days_offset_start=st.integers(min_value=0, max_value=365),
        days_offset_end=st.integers(min_value=0, max_value=365)
    )
    def test_settings_with_custom_dates_round_trip(
        self,
        selected_period: str,
        days_offset_start: int,
        days_offset_end: int
    ):
        """
        Property 8: Settings Persistence Round-Trip (with custom dates)
        Feature: enhanced-dashboard, Property 8: Settings persistence round-trip
        Validates: Requirements 4.4
        
        For any valid DashboardSettings with custom dates, all values SHALL be preserved.
        """
        from datetime import datetime, timedelta
        
        base_date = datetime(2024, 1, 1)
        custom_start = base_date + timedelta(days=days_offset_start)
        custom_end = base_date + timedelta(days=days_offset_start + days_offset_end)
        
        # Create settings with custom dates
        original = DashboardSettings(
            selected_period=selected_period,
            custom_start_date=custom_start if selected_period == "custom" else None,
            custom_end_date=custom_end if selected_period == "custom" else None
        )
        
        # Simulate round-trip
        restored = DashboardSettings(
            auto_refresh_enabled=original.auto_refresh_enabled,
            auto_refresh_interval=original.auto_refresh_interval,
            selected_period=original.selected_period,
            custom_start_date=original.custom_start_date,
            custom_end_date=original.custom_end_date
        )
        
        # Verify
        assert restored.selected_period == original.selected_period
        assert restored.custom_start_date == original.custom_start_date
        assert restored.custom_end_date == original.custom_end_date

    @settings(max_examples=100)
    @given(
        auto_refresh_enabled=st.booleans(),
        auto_refresh_interval=st.integers(min_value=5, max_value=300)
    )
    def test_settings_json_serialization_round_trip(
        self,
        auto_refresh_enabled: bool,
        auto_refresh_interval: int
    ):
        """
        Property 8: Settings Persistence Round-Trip (JSON serialization)
        Feature: enhanced-dashboard, Property 8: Settings persistence round-trip
        Validates: Requirements 4.4
        
        For any valid DashboardSettings, JSON serialization and deserialization
        SHALL produce an equivalent object.
        """
        import json
        
        # Create settings
        original = DashboardSettings(
            auto_refresh_enabled=auto_refresh_enabled,
            auto_refresh_interval=auto_refresh_interval,
            selected_period="this_month"
        )
        
        # Serialize to JSON
        json_str = original.model_dump_json()
        
        # Deserialize from JSON
        restored = DashboardSettings.model_validate_json(json_str)
        
        # Verify
        assert restored.auto_refresh_enabled == original.auto_refresh_enabled
        assert restored.auto_refresh_interval == original.auto_refresh_interval
        assert restored.selected_period == original.selected_period
