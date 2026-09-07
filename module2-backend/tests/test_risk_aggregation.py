import pytest

from app.services.checkin import OVERALL_RISK_WEIGHTS, aggregate_risk_score


def test_m2_risk_weights_match_the_module_boundary():
    assert OVERALL_RISK_WEIGHTS == {
        "biometric": 0.50,
        "device_attestation": 0.20,
        "geolocation": 0.15,
        "network": 0.15,
    }
    assert sum(OVERALL_RISK_WEIGHTS.values()) == 1.0


def test_m2_aggregates_biometric_device_location_and_network_risk():
    assert aggregate_risk_score(
        biometric_risk=0.4,
        device_attestation_risk=0.5,
        geolocation_risk=0.2,
        network_risk=0.6,
    ) == 0.42


@pytest.mark.parametrize("invalid_risk", [-0.01, 1.01])
def test_m2_rejects_invalid_component_risk(invalid_risk):
    with pytest.raises(ValueError):
        aggregate_risk_score(
            biometric_risk=invalid_risk,
            device_attestation_risk=0.0,
            geolocation_risk=0.0,
            network_risk=0.0,
        )
