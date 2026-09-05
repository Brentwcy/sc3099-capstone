from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class EnrollmentCreate(BaseModel):
    student_id: str
    course_id: str


class EnrollmentResponse(BaseModel):
    id: str
    student_id: str
    course_id: str
    is_active: bool
    enrolled_at: datetime
    dropped_at: datetime | None = None


class MyEnrollmentResponse(EnrollmentResponse):
    course_code: str
    course_name: str
    semester: str


class EnrolledStudentResponse(BaseModel):
    id: str
    student_id: str
    student_email: EmailStr
    student_name: str
    enrolled_at: datetime
    is_active: bool
    face_enrolled: bool


class CourseEnrollmentsResponse(BaseModel):
    course_id: str
    course_code: str
    total_enrolled: int
    students: list[EnrolledStudentResponse]


class BulkEnrollmentRequest(BaseModel):
    course_id: str
    student_emails: list[EmailStr] = Field(min_length=1, max_length=500)
    create_accounts: bool = False

    @field_validator("student_emails")
    @classmethod
    def normalize_and_deduplicate(cls, values: list[EmailStr]) -> list[str]:
        normalized = [str(value).strip().lower() for value in values]
        return list(dict.fromkeys(normalized))


class BulkEnrollmentDetail(BaseModel):
    email: EmailStr
    status: str


class BulkEnrollmentResponse(BaseModel):
    enrolled: int
    already_enrolled: int
    not_found: int
    created: int
    details: list[BulkEnrollmentDetail]
