import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_api_client():
    with patch("custom_components.flipr_pool.api.FliprApiClient") as mock_client:
        instance = mock_client.return_value
        instance.get_pool_data.return_value = {
            "place_id": "P123",
            "hub_id": "H123",
            "module_last_measure": {
                "PH": {"Value": 7.2, "DeviationSector": "OK"},
                "OxydoReductionPotentiel": {"Value": 650},
                "Battery": {"Deviation": 0.8},
                "Conductivity": {"Value": 1200},
                "Desinfectant": {"Value": 1.5, "DeviationSector": "OK"},
                "Temperature": 28.0,
                "DateTime": "2026-06-28T12:00:00Z"
            },
            "module_shortterm": {
                "AirTemperature": 32.0,
                "WaterState": "Baignade"
            },
            "alerts": [],
            "thresholds": {},
            "hub_state": {"Mode": "auto", "Status": "on"}
        }
        yield instance

@pytest.fixture
def mock_config_entry():
    return MagicMock(
        data={"email": "test@flipr.fr", "password": "pass", "flipr_id": "G123"},
        options={"pool_length": 8.0, "pool_width": 4.0, "pool_depth": 1.5},
        entry_id="flipr_test_123"
    )
