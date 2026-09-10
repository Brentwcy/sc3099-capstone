"""
Biometric Risk Assessment Engine for Module 3.
Evaluates biometric signals (liveness score and face matching).
Environmental and device signals are handled in Module 2.
"""
from typing import Dict, List
from .models import RiskAssessRequest, RiskAssessResponse


class RiskEngine:
    """Biometric risk evaluation engine focusing on liveness and face matching."""

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
        """
        Assess risk based solely on biometric signals (liveness score and face matching).
        Contextual, environmental, and device signals are handled in Module 2.
        """
        liveness_val = request.liveness_score
        face_match_val = request.face_match_score

        has_liveness = liveness_val is not None
        has_match = face_match_val is not None

        # 1. Biometric Signals (inverted: low score -> high risk)
        if has_liveness and has_match:
            liveness_score = max(0.0, min(1.0, float(liveness_val)))
            face_match_score = max(0.0, min(1.0, float(face_match_val)))
            liveness_risk = 1.0 - liveness_score
            match_risk = 1.0 - face_match_score
            c_liveness = 0.5 * liveness_risk
            c_match = 0.5 * match_risk
            total_risk = c_liveness + c_match
        elif has_liveness:
            liveness_score = max(0.0, min(1.0, float(liveness_val)))
            liveness_risk = 1.0 - liveness_score
            match_risk = 0.0
            c_liveness = liveness_risk
            c_match = 0.0
            total_risk = liveness_risk
        elif has_match:
            face_match_score = max(0.0, min(1.0, float(face_match_val)))
            liveness_risk = 0.0
            match_risk = 1.0 - face_match_score
            c_liveness = 0.0
            c_match = match_risk
            total_risk = match_risk
        else:
            # Default low baseline when neither score is provided
            liveness_risk = 0.20
            match_risk = 0.15
            c_liveness = 0.5 * liveness_risk
            c_match = 0.5 * match_risk
            total_risk = c_liveness + c_match

        total_risk = float(round(max(0.0, min(1.0, total_risk)), 4))

        # 2. Risk Level Mapping
        if total_risk < 0.30:
            risk_level = "LOW"
        elif total_risk < 0.50:
            risk_level = "MEDIUM"
        elif total_risk < 0.70:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"

        pass_threshold = total_risk < self.risk_threshold

        # 3. Biometric signal breakdown
        signal_breakdown = {
            "liveness": round(c_liveness, 4),
            "face_match": round(c_match, 4),
        }

        # 4. Actionable recommendations strictly for biometric signals
        recommendations: List[str] = []
        if liveness_risk > 0.40:
            recommendations.append("Improve lighting and face visibility for liveness verification")
        if match_risk > 0.40:
            recommendations.append("Re-enroll face or improve image capture angle")

        return RiskAssessResponse(
            risk_score=total_risk,
            risk_level=risk_level,
            pass_threshold=pass_threshold,
            risk_threshold=self.risk_threshold,
            signal_breakdown=signal_breakdown,
            signals=signal_breakdown,
            recommendations=recommendations
        )
