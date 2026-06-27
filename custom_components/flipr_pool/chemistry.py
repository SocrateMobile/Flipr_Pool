import math
import logging

_LOGGER = logging.getLogger(__name__)

_CYA_HOCl_MAX_FACTOR = 50.0

def _compute_ph_s(temp_c: float, tac_c: float, th_c: float, tds_c: float) -> float:
    # Formule standard LSI simplifiée (Kelvin)
    a = (math.log10(max(1.0, tds_c)) - 1) / 10
    b = -13.12 * math.log10(temp_c + 273.15) + 34.55
    c = math.log10(max(1.0, th_c)) - 0.4
    d = math.log10(max(1.0, tac_c))
    return (9.3 + a + b) - (c + d)


def compute_isl(
    temp: float, ph: float, tac: float, th: float, tds: float
) -> float | None:
    if any(v is None for v in [temp, ph, tac, th, tds]):
        return None
    if tac <= 0 or th <= 0 or tds <= 0:
        return None
    try:
        ph_s = _compute_ph_s(float(temp), float(tac), float(th), float(tds))
        return round(ph - ph_s, 2)
    except Exception as e:
        _LOGGER.debug("Error computing LSI: %s", e)
        return None


def compute_ph_equilibrium(
    temp: float, tac: float, th: float, tds: float
) -> float | None:
    if any(v is None for v in [temp, tac, th, tds]):
        return None
    if tac <= 0 or th <= 0 or tds <= 0:
        return None
    try:
        return round(_compute_ph_s(float(temp), float(tac), float(th), float(tds)), 2)
    except Exception as e:
        _LOGGER.debug("Error computing equilibrium pH: %s", e)
        return None


def estimate_free_chlorine(orp: float, ph: float, cya: float = 40.0) -> float | None:
    try:
        if orp < 415.0:
            _LOGGER.debug(
                "ORP=%.1f mV is below 415 mV — free chlorine estimation unreliable",
                orp,
            )
        effective_orp = max(415.0, orp)
        amplifier = 657 - (51 * ph)
        if amplifier < 0.1:
            amplifier = 0.1

        exponent = (effective_orp - 1065 + (50 * ph)) / amplifier
        fc_theoretical = math.pow(10, exponent)

        cya_factor = max(1.0, float(cya) / 40.0)
        fc_estimated = fc_theoretical * cya_factor

        return round(max(0.0, min(fc_estimated, 15.0)), 2)

    except (ValueError, OverflowError, ZeroDivisionError) as e:
        _LOGGER.error("Mathematical error in estimate_free_chlorine: %s", e)
        return None


def compute_active_chlorine_from_fc(
    fc_estimated: float | None, ph: float, temp_c: float, cya: float
) -> float | None:
    try:
        if fc_estimated is None:
            return None
        if fc_estimated <= 0:
            return 0.0

        temp_c_clamped = max(0.0, min(float(temp_c), 60.0))
        temp_k = temp_c_clamped + 273.15
        pka = (3000.0 / temp_k) - 10.0686 + (0.0253 * temp_k)
        hocl_fraction = 1.0 / (1.0 + math.pow(10, ph - pka))

        cya_penalty_factor = min(
            1.0 + (max(0.0, cya) * 0.8),
            _CYA_HOCl_MAX_FACTOR,
        )
        active_chlorine = (fc_estimated * hocl_fraction) / cya_penalty_factor

        return round(max(0.0, active_chlorine), 4)
    except Exception as e:
        _LOGGER.error("Error in compute_active_chlorine_from_fc: %s", e)
        return None
