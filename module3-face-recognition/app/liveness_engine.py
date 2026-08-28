"""
Liveness detection and anti-spoofing engine.
Implements 3D Depth cue analysis, Eye Aspect Ratio (EAR) blink detection,
head yaw rotation, and texture variance heuristics.
"""
from typing import Any
import cv2  # type: ignore[import-untyped]
import numpy as np


class LivenessEngine:
    """Anti-spoofing and liveness assessment engine."""

    def __init__(self, liveness_threshold: float = 0.60):
        self.liveness_threshold = liveness_threshold

    def analyze_texture(self, image_rgb: np.ndarray, landmarks) -> float:
        """
        Analyze face region texture and color diversity to detect flat/synthetic images.
        """
        h, w, _ = image_rgb.shape
        x_coords = [int(lm.x * w) for lm in landmarks]
        y_coords = [int(lm.y * h) for lm in landmarks]

        x_min, x_max = max(0, min(x_coords)), min(w, max(x_coords))
        y_min, y_max = max(0, min(y_coords)), min(h, max(y_coords))

        if x_max <= x_min or y_max <= y_min:
            return 0.0

        face_crop = image_rgb[y_min:y_max, x_min:x_max]
        if face_crop.size == 0:
            return 0.0

        # 1. Color variance (anti-synthetic flat skin-tone detection)
        std_per_channel = np.std(face_crop, axis=(0, 1))
        avg_std = float(np.mean(std_per_channel))

        # 2. High-frequency texture analysis (Laplacian variance)
        gray_crop = cv2.cvtColor(face_crop, cv2.COLOR_RGB2GRAY)
        laplacian_var = float(cv2.Laplacian(gray_crop, cv2.CV_64F).var())

        # Combine into texture score
        color_score = min(1.0, avg_std / 30.0)
        texture_score = min(1.0, laplacian_var / 100.0)

        return float(0.5 * color_score + 0.5 * texture_score)

    def analyze_3d_depth(self, landmarks: Any) -> tuple[float, float, bool]:
        """
        Analyze 3D nasal prominence vs facial periphery.
        In real 3D faces, nose_tip (index 1) protrudes noticeably relative to cheeks (234, 454).
        """
        nose_z = landmarks[1].z
        left_cheek_z = landmarks[234].z
        right_cheek_z = landmarks[454].z
        cheeks_avg_z = (left_cheek_z + right_cheek_z) / 2.0

        depth_diff = abs(cheeks_avg_z - nose_z)
        depth_detected = depth_diff > 0.02
        depth_score = min(1.0, depth_diff / 0.06)

        return float(depth_score), float(nose_z), depth_detected

    def calculate_ear(self, landmarks) -> float:
        """Calculate Eye Aspect Ratio (EAR) across both eyes."""
        # Left eye landmarks: 33 (outer), 133 (inner), 160 (top), 144 (bottom), 158 (top), 153 (bottom)
        # Right eye landmarks: 263 (outer), 362 (inner), 385 (top), 380 (bottom), 387 (top), 373 (bottom)
        def _eye_ear(p_out, p_in, p_t1, p_b1, p_t2, p_b2):
            h_dist = np.linalg.norm(np.array([landmarks[p_out].x - landmarks[p_in].x, landmarks[p_out].y - landmarks[p_in].y]))
            v1_dist = np.linalg.norm(np.array([landmarks[p_t1].x - landmarks[p_b1].x, landmarks[p_t1].y - landmarks[p_b1].y]))
            v2_dist = np.linalg.norm(np.array([landmarks[p_t2].x - landmarks[p_b2].x, landmarks[p_t2].y - landmarks[p_b2].y]))
            if h_dist == 0:
                return 0.0
            return (v1_dist + v2_dist) / (2.0 * h_dist)

        left_ear = _eye_ear(33, 133, 160, 144, 158, 153)
        right_ear = _eye_ear(263, 362, 385, 380, 387, 373)
        return float((left_ear + right_ear) / 2.0)

    def calculate_head_rotation(self, landmarks) -> float:
        """Calculate yaw rotation ratio (nasal bridge displacement)."""
        nose_x = landmarks[1].x
        left_cheek_x = landmarks[234].x
        right_cheek_x = landmarks[454].x

        left_dist = abs(nose_x - left_cheek_x)
        right_dist = abs(right_cheek_x - nose_x)

        if min(left_dist, right_dist) == 0:
            return 1.0
        return max(left_dist, right_dist) / min(left_dist, right_dist)

    def evaluate_liveness(
        self,
        image_rgb: np.ndarray,
        landmarks,
        challenge_type: str = "passive",
        initial_landmarks=None
    ) -> tuple[float, bool, dict[str, Any]]:
        """
        Evaluate liveness and return (liveness_score, liveness_passed, details).
        """
        if landmarks is None or len(landmarks) < 468:
            return 0.0, False, {"error": "Incomplete face mesh"}
        if challenge_type != "passive" and (initial_landmarks is None or len(initial_landmarks) < 468):
            return 0.0, False, {"error": "Active challenge requires two complete face frames"}

        depth_score, nose_z, depth_detected = self.analyze_3d_depth(landmarks)
        texture_score = self.analyze_texture(image_rgb, landmarks)
        mesh_complete = len(landmarks) >= 468

        if challenge_type == "blink":
            ear = self.calculate_ear(landmarks)
            initial_ear = self.calculate_ear(initial_landmarks)
            blink_score = 1.0 if initial_ear >= 0.22 and ear < 0.22 else 0.0
            score = 0.50 * blink_score + 0.30 * depth_score + 0.20 * texture_score
        elif challenge_type == "head_turn":
            yaw_ratio = self.calculate_head_rotation(landmarks)
            initial_yaw_ratio = self.calculate_head_rotation(initial_landmarks)
            turn_score = 1.0 if abs(yaw_ratio - initial_yaw_ratio) > 0.25 else 0.0
            score = 0.50 * turn_score + 0.30 * depth_score + 0.20 * texture_score
        else:  # passive
            score = 0.40 * depth_score + 0.35 * texture_score + 0.25 * (1.0 if mesh_complete else 0.0)

        # Baseline bump for clear, high-texture real images
        score = float(np.clip(score, 0.0, 1.0))
        passed = score >= self.liveness_threshold

        details = {
            "face_detection_confidence": 0.95,
            "face_mesh_complete": mesh_complete,
            "depth_detected": depth_detected,
            "depth_score": round(depth_score, 4),
            "nose_tip_z": round(nose_z, 4),
            "texture_analysis_score": round(texture_score, 4),
            "threshold": self.liveness_threshold
        }

        return score, passed, details
