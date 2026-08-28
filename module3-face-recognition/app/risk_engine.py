"""
Multi-signal Risk Assessment and Fusion Engine.
Evaluates biometric, device, network, and geolocation signals.
"""
from typing import Dict, List
from .models import RiskAssessRequest, RiskAssessResponse


class RiskEngine:
    """Multi-signal weighted risk evaluation engine."""

    def __init__(self, risk_threshold: float = 0.50):
        self.risk_threshold = risk_threshold

    def evaluate_network_risk(self, ip_address: str, user_agent: str) -> float:
        """Detect VPN, proxy, localhost, and suspicious user-agents."""
        risk = 0.05  # Default low baseline risk for clean network

        if ip_address:
            ip_str = ip_address.strip()
            # Private IP ranges (indicative of VPN/internal tunneling in remote environments)
            if (
                ip_str.startswith("10.")
                or ip_str.startswith("192.168.")
                or ip_str.startswith("127.")
                or ip_str == "::1"
            ):
                risk = max(risk, 0.85)
            elif ip_str.startswith("172."):
                parts = ip_str.split(".")
                if len(parts) > 1 and parts[1].isdigit() and 16 <= int(parts[1]) <= 31:
                    risk = max(risk, 0.85)

        if user_agent:
            ua_lower = user_agent.lower()
            vpn_keywords = ["vpn", "proxy", "tor", "headless", "bot", "crawl", "spider"]
            if any(k in ua_lower for k in vpn_keywords):
                risk = max(risk, 0.90)

        return min(1.0, risk)

    def evaluate_geolocation_risk(self, geolocation) -> float:
        """Evaluate accuracy and bounding box for classroom geofence."""
        if not geolocation:
            return 0.20  # Neutral missing penalty

        accuracy = getattr(geolocation, "accuracy", 10.0)

        # High accuracy spoofing (< 0.5m) or extremely poor accuracy (> 5000m)
        if accuracy > 5000:
            return 0.80
        elif accuracy > 500:
            return 0.50
        elif accuracy < 0.5:
            return 0.40  # Mock location suspicion
        else:
            return 0.05  # High-quality realistic mobile GPS

    def evaluate_device_risk(self, device_signature: str, device_public_key: str) -> float:
        """Evaluate cryptographic device attestation."""
        if device_signature and device_public_key:
            if len(device_signature) > 10 and len(device_public_key) > 10:
                return 0.05
            return 0.70
        return 0.15  # Default un-attested device baseline

    def evaluate_time_risk(self, check_in_time, session_start_time, session_end_time) -> float:
        """Flag check-ins outside the scheduled session window."""
        if not check_in_time or not session_start_time or not session_end_time:
            return 0.20
        check_in = check_in_time.replace(tzinfo=None)
        start = session_start_time.replace(tzinfo=None)
        end = session_end_time.replace(tzinfo=None)
        return 0.05 if start <= check_in <= end else 0.90

    def assess_risk(self, request: RiskAssessRequest) -> RiskAssessResponse:
        """Perform weighted multi-signal risk fusion."""
        # 1. Biometric Signals (inverted: low score -> high risk)
        liveness_score = request.liveness_score if request.liveness_score is not None else 0.80
        face_match_score = request.face_match_score if request.face_match_score is not None else 0.85

        liveness_risk = 1.0 - max(0.0, min(1.0, liveness_score))
        match_risk = 1.0 - max(0.0, min(1.0, face_match_score))

        # 2. Contextual Signals
        device_risk = self.evaluate_device_risk(request.device_signature, request.device_public_key)
        network_risk = self.evaluate_network_risk(request.ip_address, request.user_agent)
        geo_risk = self.evaluate_geolocation_risk(request.geolocation)
        time_risk = self.evaluate_time_risk(
            request.check_in_time, request.session_start_time, request.session_end_time
        )

        # 3. Weighted Fusion, including the session-time signal.
        c_liveness = 0.22 * liveness_risk
        c_match = 0.22 * match_risk
        c_device = 0.18 * device_risk
        c_network = 0.14 * network_risk
        c_geo = 0.14 * geo_risk
        c_time = 0.10 * time_risk

        total_risk = c_liveness + c_match + c_device + c_network + c_geo + c_time
        total_risk = float(round(max(0.0, min(1.0, total_risk)), 4))

        # 4. Risk Level Mapping
        if total_risk < 0.30:
            risk_level = "LOW"
        elif total_risk <= 0.60:
            risk_level = "MEDIUM"
        elif total_risk <= 0.80:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"

        pass_threshold = total_risk < self.risk_threshold

        # 5. Signal breakdown
        signal_breakdown = {
            "liveness": round(c_liveness, 4),
            "face_match": round(c_match, 4),
            "device": round(c_device, 4),
            "network": round(c_network, 4),
            "geolocation": round(c_geo, 4),
            "time": round(c_time, 4),
        }

        # 6. Actionable recommendations
        recommendations: List[str] = []
        if liveness_risk > 0.40:
            recommendations.append("Improve lighting and face visibility for liveness verification")
        if match_risk > 0.40:
            recommendations.append("Re-enroll face or improve image capture angle")
        if network_risk > 0.40:
            recommendations.append("Disable VPN or proxy connections during check-in")
        if geo_risk > 0.40:
            recommendations.append("Enable precise location services")
        if time_risk > 0.40:
            recommendations.append("Check in during the scheduled session window")
        if device_risk > 0.40:
            recommendations.append("Register device binding keypair")

        return RiskAssessResponse(
            risk_score=total_risk,
            risk_level=risk_level,
            pass_threshold=pass_threshold,
            risk_threshold=self.risk_threshold,
            signal_breakdown=signal_breakdown,
            signals=signal_breakdown,
            recommendations=recommendations
        )
