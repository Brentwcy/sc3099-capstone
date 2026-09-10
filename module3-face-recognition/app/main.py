"""
SAIV Face Recognition & Risk Service - Module 3.

Production implementation providing:
- Face enrollment & verification
- MediaPipe 468 3D landmark Face Mesh processing
- Liveness detection & anti-spoofing heuristics
- Multi-signal weighted risk assessment
- Privacy-first hash-only storage & in-memory image lifecycle
"""
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .logging_config import logger
from .telemetry import setup_telemetry
from .models import (
    FaceEnrollRequest,
    FaceEnrollResponse,
    FaceVerifyRequest,
    FaceVerifyResponse,
    LivenessRequest,
    LivenessResponse,
    RiskAssessRequest,
    RiskAssessResponse,
)
from .image_utils import decode_base64_image
from .face_engine import FaceEngine
from .liveness_engine import LivenessEngine
from .risk_engine import RiskEngine
from .redis_client import EmbeddingCache

# Initialize FastAPI application
app = FastAPI(
    title=settings.SERVICE_NAME,
    description="Face enrollment, verification, liveness detection, and risk scoring service",
    version=settings.VERSION,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize engines and services
face_engine = FaceEngine(min_detection_confidence=settings.MIN_DETECTION_CONFIDENCE)
liveness_engine = LivenessEngine(liveness_threshold=settings.LIVENESS_THRESHOLD)
risk_engine = RiskEngine(risk_threshold=settings.RISK_THRESHOLD)
cache = EmbeddingCache(
    redis_url=settings.REDIS_URL,
    encryption_key=settings.TEMPLATE_ENCRYPTION_KEY,
)

# Setup OpenTelemetry instrumentation if configured
setup_telemetry(app, settings.OTEL_EXPORTER_OTLP_ENDPOINT)


# =============================================================================
# ROOT & HEALTH ENDPOINTS
# =============================================================================

@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION
    }


@app.get("/", status_code=status.HTTP_200_OK)
async def root():
    """List available endpoints."""
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
        "endpoints": [
            "/health",
            "/face/enroll",
            "/face/verify",
            "/face/match",
            "/liveness/check",
            "/risk/assess"
        ]
    }


# =============================================================================
# FACE ENROLLMENT ENDPOINT
# =============================================================================

@app.post("/face/enroll", response_model=FaceEnrollResponse, status_code=status.HTTP_201_CREATED)
async def enroll_face(request: FaceEnrollRequest):
    """
    Enroll a user's face for future verification.
    Requires camera consent and a valid frontal face image.
    """
    if not request.camera_consent:
        logger.warning("Enrollment rejected: camera_consent is False", user_id=request.user_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera consent is required for biometric enrollment"
        )

    image_rgb = decode_base64_image(request.image)
    if image_rgb is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or unreadable image data"
        )

    landmarks = face_engine.extract_landmarks(image_rgb)
    if landmarks is None:
        logger.warning("Enrollment failed: No face detected", user_id=request.user_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No face detected in submitted image"
        )

    quality_score, details = face_engine.calculate_quality_score(image_rgb, landmarks)
    embedding = face_engine.extract_embedding(landmarks)
    face_template_hash = face_engine.generate_face_hash(embedding)
    simhash = face_engine.generate_simhash(embedding)

    cache.set_template(face_template_hash, simhash)

    logger.info(
        "Face enrolled successfully",
        user_id=request.user_id,
        hash=face_template_hash[:8] + "...",
        quality_score=quality_score
    )

    return FaceEnrollResponse(
        enrollment_successful=True,
        face_template_hash=face_template_hash,
        quality_score=quality_score,
        details=details
    )


# =============================================================================
# FACE VERIFICATION ENDPOINTS
# =============================================================================

@app.post("/face/verify", response_model=FaceVerifyResponse, status_code=status.HTTP_200_OK)
async def verify_face(request: FaceVerifyRequest):
    """
    Verify a face against a previously enrolled reference template hash.
    """
    ref_hash = request.reference_template_hash or request.reference_hash

    image_rgb = decode_base64_image(request.image)
    if image_rgb is None:
        return FaceVerifyResponse(
            match_passed=False,
            match_score=0.0,
            match_threshold=settings.FACE_MATCH_THRESHOLD,
            face_detected=False,
            current_template_hash="",
            face_embedding_hash=""
        )

    landmarks = face_engine.extract_landmarks(image_rgb)
    if landmarks is None:
        return FaceVerifyResponse(
            match_passed=False,
            match_score=0.0,
            match_threshold=settings.FACE_MATCH_THRESHOLD,
            face_detected=False,
            current_template_hash="",
            face_embedding_hash=""
        )

    current_embedding = face_engine.extract_embedding(landmarks)
    current_hash = face_engine.generate_face_hash(current_embedding)
    current_simhash = face_engine.generate_simhash(current_embedding)
    cache.set_template(current_hash, current_simhash)

    if not ref_hash:
        return FaceVerifyResponse(
            match_passed=False,
            match_score=0.0,
            match_threshold=settings.FACE_MATCH_THRESHOLD,
            face_detected=True,
            current_template_hash=current_hash,
            face_embedding_hash=current_hash
        )

    reference_simhash = cache.get_template(ref_hash)
    if reference_simhash is None:
        logger.warning("Reference face template not found in cache", ref_hash=ref_hash[:8] + "...")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template unavailable. Re-enrollment required."
        )

    if current_hash == ref_hash:
        match_score = 1.0
        match_passed = True
    else:
        match_score = face_engine.simhash_similarity(current_simhash, reference_simhash)
        match_passed = face_engine.simhash_matches(
            current_simhash,
            reference_simhash,
            max_distance=face_engine.SIMHASH_HAMMING_THRESHOLD,
        )

    return FaceVerifyResponse(
        match_passed=match_passed,
        match_score=round(match_score, 4),
        match_threshold=settings.FACE_MATCH_THRESHOLD,
        face_detected=True,
        current_template_hash=current_hash,
        face_embedding_hash=current_hash
    )


@app.post("/face/match", response_model=FaceVerifyResponse, status_code=status.HTTP_200_OK)
async def match_face(request: FaceVerifyRequest):
    """Legacy face matching endpoint (alias for /face/verify)."""
    return await verify_face(request)


# =============================================================================
# LIVENESS DETECTION ENDPOINT
# =============================================================================

@app.post("/liveness/check", response_model=LivenessResponse, status_code=status.HTTP_200_OK)
async def check_liveness(request: LivenessRequest):
    """
    Perform 3D depth cue, blink, or yaw liveness detection.
    """
    image_rgb = decode_base64_image(request.challenge_response)
    if image_rgb is None:
        return LivenessResponse(
            liveness_passed=False,
            liveness_score=0.0,
            liveness_threshold=settings.LIVENESS_THRESHOLD,
            challenge_type=request.challenge_type,
            face_embedding_hash="",
            details={"error": "Invalid image"}
        )

    landmarks = face_engine.extract_landmarks(image_rgb)
    if landmarks is None:
        return LivenessResponse(
            liveness_passed=False,
            liveness_score=0.0,
            liveness_threshold=settings.LIVENESS_THRESHOLD,
            challenge_type=request.challenge_type,
            face_embedding_hash="",
            details={"face_detected": False}
        )

    initial_landmarks = None
    if request.initial_image:
        initial_rgb = decode_base64_image(request.initial_image)
        initial_landmarks = face_engine.extract_landmarks(initial_rgb) if initial_rgb is not None else None

    liveness_score, liveness_passed, details = liveness_engine.evaluate_liveness(
        image_rgb=image_rgb,
        landmarks=landmarks,
        challenge_type=request.challenge_type,
        initial_landmarks=initial_landmarks
    )

    embedding = face_engine.extract_embedding(landmarks)
    face_hash = face_engine.generate_face_hash(embedding)
    # NOTE: Liveness is an anti-spoofing check, not an enrollment event.
    # We derive the hash for response metadata only; no template is stored here.

    return LivenessResponse(
        liveness_passed=liveness_passed,
        liveness_score=round(liveness_score, 4),
        liveness_threshold=settings.LIVENESS_THRESHOLD,
        challenge_type=request.challenge_type,
        face_embedding_hash=face_hash,
        details=details
    )


# =============================================================================
# FACE ENROLLMENT REVOCATION ENDPOINT
# =============================================================================

@app.delete("/face/enroll/{template_hash}", status_code=status.HTTP_200_OK)
async def revoke_face_enrollment(template_hash: str):
    """
    Revoke a face enrollment and permanently delete the stored biometric template.

    Called when:
    - A student withdraws camera/biometric consent
    - An admin unenrolls a student
    - A data deletion request is received (PDPA/GDPR right to erasure)
    """
    deleted = cache.delete_template(template_hash)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No biometric template found for that hash."
        )
    logger.info(
        "Face enrollment revoked",
        hash_prefix=template_hash[:8] + "...",
    )
    return {"revoked": True, "hash_prefix": template_hash[:8] + "..."}


# =============================================================================
# BIOMETRIC RISK ASSESSMENT ENDPOINT
# =============================================================================

@app.post("/risk/assess", response_model=RiskAssessResponse, status_code=status.HTTP_200_OK)
async def assess_risk(request: RiskAssessRequest):
    """
    Perform biometric risk assessment based on liveness and face matching signals.
    """
    return risk_engine.assess_risk(request)
