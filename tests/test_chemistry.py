import pytest
from custom_components.flipr_pool.chemistry import (
    compute_isl,
    compute_ph_equilibrium,
    estimate_free_chlorine
)
from custom_components.flipr_pool.__init__ import _compute_pool_data

def test_lsi_calculation():
    # Temp 25, pH 7.2, TAC 100, TH 200, TDS 1000
    lsi = compute_isl(25, 7.2, 100, 200, 1000)
    assert lsi is not None
    assert round(lsi, 2) == -0.32

def test_doses_calculation(mock_config_entry):
    m = {
        "PH": {"Value": 7.6}, # Cible est 7.4, difference de +0.2
        "Desinfectant": {"Value": 1.0}, # Cible 2.0, diff 1.0
        "Temperature": 28.0
    }
    
    # 8 * 4 * 1.5 = 48 m3
    # dose_ph_minus = 0.2 * 48 * 100 = 960g
    # dose_cl_maint = 1.0 * 48 * 1.5 (si c'est 1.5g par m3 pour 1 ppm)
    
    data = _compute_pool_data(m, {}, mock_config_entry)
    
    assert data["pool_volume"] == 48000
    assert data["dose_ph_minus"] == 960
    assert data["dose_ph_plus"] == 0
    assert data["dose_cl_maint"] == 72 # 1.0 * 48 * 1.5 = 72
