"""
Hằng số dùng chung cho toàn bộ uploads module.
Tập trung tại đây để thay đổi 1 chỗ, ảnh hưởng toàn module.
"""

# Giới hạn 5MB — tránh abuse storage và bandwidth GCS
MAX_FILE_SIZE: int = 5 * 1024 * 1024

# frozenset cho O(1) lookup thay vì list O(n) — dùng khi check membership
# frozenset còn immutable → tránh vô tình mutate trong runtime
ALLOWED_MIME_TYPES: frozenset = frozenset({
    "image/jpeg",
    "image/png",
    "image/webp",
})

# Extension check bổ sung cho MIME — tránh trường hợp client gửi sai content-type
ALLOWED_EXTENSIONS: frozenset = frozenset({".jpg", ".jpeg", ".png", ".webp"})

# Folder prefix trên GCS — tất cả avatar nằm trong "avatars/" để dễ quản lý và phân quyền
AVATAR_FOLDER: str = "avatars"

# Giới hạn độ dài filename — theo POSIX filesystem limit, tránh lỗi OS/GCS
MAX_FILENAME_LENGTH: int = 255