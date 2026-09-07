import pytest

from app.models import FaceEnrollRequest, FaceVerifyRequest, LivenessRequest


@pytest.mark.parametrize(
    ("model", "field_name"),
    [
        (FaceEnrollRequest, "image"),
        (FaceVerifyRequest, "image"),
        (LivenessRequest, "challenge_response"),
        (LivenessRequest, "initial_image"),
    ],
)
def test_image_fields_have_shared_encoded_size_limit(model, field_name):
    field_schema = model.model_json_schema()["properties"][field_name]
    if "anyOf" in field_schema:
        field_schema = next(
            candidate
            for candidate in field_schema["anyOf"]
            if candidate.get("type") == "string"
        )
    assert field_schema["minLength"] == 1
    assert field_schema["maxLength"] == 15_000_000
