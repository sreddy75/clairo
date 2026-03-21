"""Portal Document Upload Service.

Handles document uploads to MinIO/S3 storage for the client portal.

Spec: 030-client-portal-document-requests
"""

import contextlib
import hashlib
from datetime import datetime, timezone
from typing import BinaryIO
from uuid import UUID, uuid4

from minio import Minio
from minio.error import S3Error
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import MinioSettings
from app.modules.portal.exceptions import PortalError
from app.modules.portal.models import PortalDocument
from app.modules.portal.repository import PortalDocumentRepository


class UploadError(PortalError):
    """Raised when document upload fails."""

    pass


class PortalUploadService:
    """Service for handling document uploads in the client portal."""

    # Maximum file size (50MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024

    # Allowed file extensions and their MIME types
    ALLOWED_EXTENSIONS = {
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".csv": "text/csv",
        ".txt": "text/plain",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }

    def __init__(
        self,
        db: AsyncSession,
        settings: MinioSettings | None = None,
    ) -> None:
        """Initialize the upload service.

        Args:
            db: Database session.
            settings: MinIO settings (defaults to environment config).
        """
        self.db = db
        self.settings = settings or MinioSettings()
        self.doc_repo = PortalDocumentRepository(db)

        # Initialize MinIO client for internal operations (upload/delete)
        self._client = Minio(
            self.settings.endpoint,
            access_key=self.settings.access_key,
            secret_key=self.settings.secret_key.get_secret_value(),
            secure=self.settings.use_ssl,
        )

        # Store external endpoint for URL rewriting
        # We generate URLs with internal client, then rewrite the hostname
        self._external_endpoint = self.settings.external_endpoint

        # Ensure bucket exists
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Ensure the storage bucket exists."""
        try:
            if not self._client.bucket_exists(self.settings.bucket):
                self._client.make_bucket(self.settings.bucket)
        except S3Error:
            # Log but don't fail - bucket might exist with different permissions
            pass

    def _validate_file(
        self,
        filename: str,
        content_type: str | None,
        file_size: int,
    ) -> str:
        """Validate file upload.

        Args:
            filename: Original filename.
            content_type: MIME type of the file.
            file_size: Size in bytes.

        Returns:
            Validated content type.

        Raises:
            UploadError: If validation fails.
        """
        if file_size > self.MAX_FILE_SIZE:
            raise UploadError(
                f"File too large. Maximum size is {self.MAX_FILE_SIZE // (1024 * 1024)}MB"
            )

        if file_size == 0:
            raise UploadError("Empty file not allowed")

        # Get extension
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[1].lower()

        if ext not in self.ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(self.ALLOWED_EXTENSIONS.keys()))
            raise UploadError(f"File type not allowed. Allowed types: {allowed}")

        # Validate or infer content type
        if not content_type or content_type == "application/octet-stream":
            content_type = self.ALLOWED_EXTENSIONS.get(ext, "application/octet-stream")

        return content_type

    def _generate_storage_key(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        document_id: UUID,
        filename: str,
    ) -> str:
        """Generate a unique storage key for the document.

        Args:
            tenant_id: Tenant ID.
            connection_id: Connection (client) ID.
            document_id: Document ID.
            filename: Original filename.

        Returns:
            Storage key path.
        """
        # Get extension
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[1].lower()

        # Structure: tenant_id/connection_id/year/month/document_id.ext
        now = datetime.now(timezone.utc)
        return f"{tenant_id}/{connection_id}/{now.year}/{now.month:02d}/{document_id}{ext}"

    def _calculate_checksum(self, file_data: bytes) -> str:
        """Calculate SHA-256 checksum of file data.

        Args:
            file_data: File content.

        Returns:
            Hex-encoded SHA-256 hash.
        """
        return hashlib.sha256(file_data).hexdigest()

    async def upload_document(
        self,
        file: BinaryIO,
        filename: str,
        content_type: str | None,
        file_size: int,
        tenant_id: UUID,
        connection_id: UUID,
        document_type: str | None = None,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> PortalDocument:
        """Upload a document to storage.

        Args:
            file: File-like object to upload.
            filename: Original filename.
            content_type: MIME type.
            file_size: Size in bytes.
            tenant_id: Tenant ID.
            connection_id: Connection (client) ID.
            document_type: Optional document type classification.
            period_start: Optional period start date.
            period_end: Optional period end date.

        Returns:
            Created PortalDocument record.

        Raises:
            UploadError: If upload fails.
        """
        # Validate file
        validated_content_type = self._validate_file(filename, content_type, file_size)

        # Generate document ID and storage key
        document_id = uuid4()
        storage_key = self._generate_storage_key(tenant_id, connection_id, document_id, filename)

        # Read file data for checksum
        file_data = file.read()
        checksum = self._calculate_checksum(file_data)

        # Reset file position
        file.seek(0)

        try:
            # Upload to MinIO
            self._client.put_object(
                bucket_name=self.settings.bucket,
                object_name=storage_key,
                data=file,
                length=file_size,
                content_type=validated_content_type,
            )
        except S3Error as e:
            raise UploadError(f"Failed to upload file: {e}")

        # Create database record
        document = PortalDocument(
            id=document_id,
            tenant_id=tenant_id,
            connection_id=connection_id,
            filename=storage_key.split("/")[-1],  # Use generated filename
            original_filename=filename,
            s3_bucket=self.settings.bucket,
            s3_key=storage_key,
            content_type=validated_content_type,
            file_size=file_size,
            document_type=document_type,
            period_start=period_start.date() if period_start else None,
            period_end=period_end.date() if period_end else None,
            uploaded_at=datetime.now(timezone.utc),
        )

        created = await self.doc_repo.create(document)
        return created

    def get_presigned_upload_url(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        filename: str,
        content_type: str | None = None,
        expires_seconds: int = 3600,
    ) -> dict:
        """Generate a presigned URL for direct upload.

        Args:
            tenant_id: Tenant ID.
            connection_id: Connection (client) ID.
            filename: Original filename.
            content_type: Optional MIME type.
            expires_seconds: URL expiration time in seconds.

        Returns:
            Dict with upload_url, document_id, and storage_key.

        Raises:
            UploadError: If URL generation fails.
        """
        # Get extension for validation
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[1].lower()

        if ext not in self.ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(self.ALLOWED_EXTENSIONS.keys()))
            raise UploadError(f"File type not allowed. Allowed types: {allowed}")

        # Infer content type if not provided
        if not content_type:
            content_type = self.ALLOWED_EXTENSIONS.get(ext, "application/octet-stream")

        # Generate document ID and storage key
        document_id = uuid4()
        storage_key = self._generate_storage_key(tenant_id, connection_id, document_id, filename)

        try:
            # Generate presigned PUT URL
            from datetime import timedelta

            url = self._client.presigned_put_object(
                bucket_name=self.settings.bucket,
                object_name=storage_key,
                expires=timedelta(seconds=expires_seconds),
            )

            # Rewrite URL to use external endpoint for browser access
            url = url.replace(self.settings.endpoint, self._external_endpoint)

            return {
                "upload_url": url,
                "document_id": str(document_id),
                "storage_key": storage_key,
                "content_type": content_type,
                "expires_in": expires_seconds,
            }
        except S3Error as e:
            raise UploadError(f"Failed to generate upload URL: {e}")

    def get_presigned_download_url(
        self,
        storage_key: str,
        filename: str | None = None,
        expires_seconds: int = 3600,
    ) -> str:
        """Generate a presigned URL for downloading a document.

        Args:
            storage_key: Storage key of the document.
            filename: Optional filename for Content-Disposition header.
            expires_seconds: URL expiration time in seconds.

        Returns:
            Presigned download URL.

        Raises:
            UploadError: If URL generation fails.
        """
        try:
            from datetime import timedelta
            from urllib.parse import quote

            # Set response headers for download
            response_headers = {}
            if filename:
                response_headers["response-content-disposition"] = (
                    f'attachment; filename="{quote(filename)}"'
                )

            url = self._client.presigned_get_object(
                bucket_name=self.settings.bucket,
                object_name=storage_key,
                expires=timedelta(seconds=expires_seconds),
                response_headers=response_headers if response_headers else None,
            )

            # Rewrite URL to use external endpoint for browser access
            url = url.replace(self.settings.endpoint, self._external_endpoint)

            return url
        except S3Error as e:
            raise UploadError(f"Failed to generate download URL: {e}")

    async def confirm_presigned_upload(
        self,
        document_id: UUID,
        storage_key: str,
        filename: str,
        content_type: str,
        file_size: int,
        tenant_id: UUID,
        connection_id: UUID,
        document_type: str | None = None,
    ) -> PortalDocument:
        """Confirm a presigned upload and create database record.

        Called after client completes a presigned upload.

        Args:
            document_id: Document ID from presigned URL generation.
            storage_key: Storage key from presigned URL generation.
            filename: Original filename.
            content_type: MIME type.
            file_size: Size in bytes.
            tenant_id: Tenant ID.
            connection_id: Connection (client) ID.
            document_type: Optional document type classification.

        Returns:
            Created PortalDocument record.

        Raises:
            UploadError: If confirmation fails.
        """
        # Verify object exists in storage
        try:
            stat = self._client.stat_object(self.settings.bucket, storage_key)
        except S3Error:
            raise UploadError("Upload not found. Please try uploading again.")

        # Create database record
        document = PortalDocument(
            id=document_id,
            tenant_id=tenant_id,
            connection_id=connection_id,
            filename=storage_key.split("/")[-1],
            original_filename=filename,
            s3_bucket=self.settings.bucket,
            s3_key=storage_key,
            content_type=content_type,
            file_size=stat.size or file_size,
            document_type=document_type,
            uploaded_at=datetime.now(timezone.utc),
        )

        created = await self.doc_repo.create(document)
        return created

    async def delete_document(self, document_id: UUID, tenant_id: UUID) -> bool:
        """Delete a document from storage and database.

        Args:
            document_id: Document ID.
            tenant_id: Tenant ID for authorization.

        Returns:
            True if deleted successfully.

        Raises:
            UploadError: If deletion fails.
        """
        document = await self.doc_repo.get_by_id_and_tenant(document_id, tenant_id)
        if not document:
            return False

        # Continue with database deletion even if storage deletion fails
        with contextlib.suppress(S3Error):
            self._client.remove_object(self.settings.bucket, document.s3_key)

        # Delete from database
        await self.doc_repo.delete(document_id)
        return True
