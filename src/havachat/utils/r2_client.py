"""Cloudflare R2 storage client for audio file uploads."""

import logging
import os
import time
from pathlib import Path
from typing import List

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class R2Client:
    """Client for Cloudflare R2 storage with retry logic."""
    
    def __init__(
        self,
        account_id: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        bucket_name: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """Initialize R2 client.
        
        Args:
            account_id: Cloudflare account ID (or R2_ACCOUNT_ID env var)
            access_key_id: R2 access key (or R2_ACCESS_KEY_ID env var)
            secret_access_key: R2 secret key (or R2_SECRET_ACCESS_KEY env var)
            bucket_name: R2 bucket name (or R2_BUCKET_NAME env var)
            max_retries: Maximum retry attempts
            retry_delay: Initial delay between retries in seconds
        """
        self.account_id = account_id or os.getenv("R2_ACCOUNT_ID")
        self.access_key_id = access_key_id or os.getenv("R2_ACCESS_KEY_ID")
        self.secret_access_key = secret_access_key or os.getenv("R2_SECRET_ACCESS_KEY")
        self.bucket_name = bucket_name or os.getenv("R2_BUCKET_NAME")
        
        if not all([self.account_id, self.access_key_id, self.secret_access_key, self.bucket_name]):
            raise ValueError(
                "R2 credentials required: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, "
                "R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME env vars or constructor params"
            )
        
        # Create boto3 S3 client configured for R2
        self.s3_client = boto3.client(
            's3',
            endpoint_url=f'https://{self.account_id}.r2.cloudflarestorage.com',
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name='auto'  # R2 uses 'auto' region
        )
        
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Statistics
        self.total_uploads = 0
        self.failed_uploads = 0
        self.total_bytes_uploaded = 0
    
    def upload_file(
        self,
        local_path: str | Path,
        r2_path: str,
        content_type: str | None = None
    ) -> tuple[bool, dict]:
        """Upload a file to R2 storage.
        
        Args:
            local_path: Path to local file
            r2_path: Destination path in R2 (e.g., "zh/vocab/uuid.opus")
            content_type: Optional MIME type (auto-detected from extension if not provided)
            
        Returns:
            Tuple of (success, metadata_dict)
            metadata includes: file_size_bytes, upload_time_ms, url, attempts
        """
        local_path = Path(local_path)
        
        if not local_path.exists():
            logger.error(f"Local file not found: {local_path}")
            return False, {"error": f"File not found: {local_path}"}
        
        file_size = local_path.stat().st_size
        
        # Auto-detect content type if not provided
        if content_type is None:
            ext = local_path.suffix.lower()
            content_types = {
                ".opus": "audio/opus",
                ".mp3": "audio/mpeg",
                ".ogg": "audio/ogg",
                ".wav": "audio/wav"
            }
            content_type = content_types.get(ext, "application/octet-stream")
        
        metadata = {
            "file_size_bytes": file_size,
            "r2_path": r2_path,
            "content_type": content_type,
            "attempts": 0,
            "upload_time_ms": 0,
            "url": f"https://pub-{self.account_id}.r2.dev/{r2_path}"  # Public URL
        }
        
        for attempt in range(self.max_retries):
            metadata["attempts"] = attempt + 1
            
            try:
                start_time = time.time()
                
                logger.info(
                    f"Uploading to R2 (attempt {attempt + 1}/{self.max_retries}): "
                    f"{local_path.name} -> {r2_path}"
                )
                
                # Upload file
                self.s3_client.upload_file(
                    str(local_path),
                    self.bucket_name,
                    r2_path,
                    ExtraArgs={
                        'ContentType': content_type,
                        'ACL': 'public-read'  # Make publicly accessible
                    }
                )
                
                upload_time_ms = int((time.time() - start_time) * 1000)
                metadata["upload_time_ms"] = upload_time_ms
                
                # Update statistics
                self.total_uploads += 1
                self.total_bytes_uploaded += file_size
                
                logger.info(
                    f"✓ Uploaded successfully: {file_size} bytes, {upload_time_ms}ms"
                )
                
                return True, metadata
                
            except ClientError as e:
                error_msg = str(e)
                logger.warning(
                    f"Upload failed (attempt {attempt + 1}/{self.max_retries}): {error_msg}"
                )
                
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    self.failed_uploads += 1
                    logger.error(
                        f"✗ Upload failed after {self.max_retries} attempts: {error_msg}"
                    )
                    metadata["error"] = error_msg
                    return False, metadata
            
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Unexpected error during upload: {error_msg}")
                self.failed_uploads += 1
                metadata["error"] = error_msg
                return False, metadata
        
        return False, metadata
    
    def batch_upload(
        self,
        file_paths: List[tuple[str | Path, str]]
    ) -> dict:
        """Upload multiple files in batch.
        
        Args:
            file_paths: List of (local_path, r2_path) tuples
            
        Returns:
            Dict with summary statistics
        """
        results = {
            "total": len(file_paths),
            "successful": 0,
            "failed": 0,
            "failed_files": [],
            "total_bytes": 0,
            "total_time_ms": 0
        }
        
        start_time = time.time()
        
        for local_path, r2_path in file_paths:
            success, metadata = self.upload_file(local_path, r2_path)
            
            if success:
                results["successful"] += 1
                results["total_bytes"] += metadata.get("file_size_bytes", 0)
            else:
                results["failed"] += 1
                results["failed_files"].append({
                    "local_path": str(local_path),
                    "r2_path": r2_path,
                    "error": metadata.get("error", "Unknown error")
                })
        
        results["total_time_ms"] = int((time.time() - start_time) * 1000)
        results["success_rate"] = (
            results["successful"] / results["total"] * 100
            if results["total"] > 0 else 0
        )
        
        logger.info(
            f"Batch upload complete: {results['successful']}/{results['total']} successful "
            f"({results['success_rate']:.1f}%), {results['total_bytes']} bytes, "
            f"{results['total_time_ms']}ms"
        )
        
        return results
    
    def file_exists(self, r2_path: str) -> bool:
        """Check if a file exists in R2.
        
        Args:
            r2_path: Path in R2 bucket
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=r2_path)
            return True
        except ClientError:
            return False
    
    def delete_file(self, r2_path: str) -> bool:
        """Delete a file from R2.
        
        Args:
            r2_path: Path in R2 bucket
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=r2_path)
            logger.info(f"Deleted from R2: {r2_path}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete {r2_path}: {e}")
            return False
    
    def get_statistics(self) -> dict:
        """Get upload statistics.
        
        Returns:
            Dict with upload statistics
        """
        return {
            "total_uploads": self.total_uploads,
            "failed_uploads": self.failed_uploads,
            "total_bytes_uploaded": self.total_bytes_uploaded,
            "success_rate": (
                (self.total_uploads - self.failed_uploads) / self.total_uploads * 100
                if self.total_uploads > 0 else 0
            )
        }
    
    def reset_statistics(self):
        """Reset upload statistics."""
        self.total_uploads = 0
        self.failed_uploads = 0
        self.total_bytes_uploaded = 0
