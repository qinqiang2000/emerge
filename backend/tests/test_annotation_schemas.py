import pytest
from pydantic import ValidationError

from app.schemas.annotation import AnnotationIn, FeedbackIn


def test_annotation_in_minimum():
    a = AnnotationIn(output=[{"x": 1}])
    assert a.notes is None


def test_annotation_in_rejects_non_array_root():
    with pytest.raises(ValidationError):
        AnnotationIn(output={"x": 1})  # must be list


def test_annotation_in_rejects_non_object_entries():
    with pytest.raises(ValidationError):
        AnnotationIn(output=["x", "y"])  # entries must be objects


def test_feedback_in_requires_correct_output_array():
    fb = FeedbackIn(request_id=1, correct_output=[{"shop": "X"}])
    assert fb.request_id == 1
    with pytest.raises(ValidationError):
        FeedbackIn(request_id=1, correct_output={"x": 1})
