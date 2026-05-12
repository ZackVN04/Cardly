"""
----------------------
Pydantic v2 schemas cho Uploads module.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UploadResponse(BaseModel):
    # URL public của file trên GCS — client dùng để hiển thị avatar
    url: str = Field(description="Public GCS URL của file đã upload")

    # blob_name lưu lại để sau này có thể xóa file cũ khi user đổi avatar
    # Nếu chỉ lưu URL thì không thể tính blob_name ngược lại nếu bucket thay đổi
    blob_name: str = Field(description="GCS blob path, dùng cho việc xóa file sau này")

    # Server-side timestamp — không tin client, tính tại thời điểm upload hoàn thành
    uploaded_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Thời điểm upload hoàn thành (UTC)",
    )

    model_config = ConfigDict(populate_by_name=True)