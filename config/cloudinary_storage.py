"""Django media storage backed by Cloudinary's official Python SDK.

Only product images and product-gallery images are supported. Static assets
continue to be served by WhiteNoise; local development stays on FileSystemStorage
unless EKAKO_MEDIA_STORAGE=cloudinary is explicitly enabled.
"""

from pathlib import PurePosixPath
from uuid import uuid4

import cloudinary
import cloudinary.api
import cloudinary.uploader
from cloudinary.exceptions import NotFound
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from urllib.request import urlopen


class CloudinaryMediaStorage(Storage):
    """Store names as `products/<uuid>.<format>` in existing ImageFields."""

    VALID_FOLDERS = {"products", "products/gallery"}
    VALID_FORMATS = {"jpg", "jpeg", "png", "webp"}

    def __init__(self):
        cloud_name = settings.CLOUDINARY_CLOUD_NAME
        api_key = settings.CLOUDINARY_API_KEY
        api_secret = settings.CLOUDINARY_API_SECRET
        if not all((cloud_name, api_key, api_secret)):
            raise ImproperlyConfigured("Cloudinary requires its three Render secrets")
        cloudinary.config(
            cloud_name=cloud_name, api_key=api_key, api_secret=api_secret, secure=True
        )

    @staticmethod
    def _asset(name):
        if not name or "/" not in name or "." not in name:
            raise SuspiciousFileOperation("Invalid Cloudinary media name")
        path = PurePosixPath(name)
        if path.parent.as_posix() not in CloudinaryMediaStorage.VALID_FOLDERS:
            raise SuspiciousFileOperation("Media path must be under products/")
        public_id, file_format = name.rsplit(".", 1)
        file_format = file_format.lower()
        if file_format not in CloudinaryMediaStorage.VALID_FORMATS:
            raise SuspiciousFileOperation("Unsupported product image format")
        return public_id, "jpg" if file_format == "jpeg" else file_format

    def get_available_name(self, name, max_length=None):
        # _save generates a random public_id, so no remote name lookup is needed.
        return name

    def _save(self, name, content):
        path = PurePosixPath(name)
        folder = path.parent.as_posix()
        if folder not in self.VALID_FOLDERS:
            raise SuspiciousFileOperation("Only eKAKO product media may be uploaded")
        if path.suffix.lower().lstrip(".") not in self.VALID_FORMATS:
            raise SuspiciousFileOperation("Upload a JPG, PNG or WebP image")
        if hasattr(content, "seek"):
            content.seek(0)
        public_id = f"{folder}/{uuid4().hex}"
        result = cloudinary.uploader.upload(
            content, public_id=public_id, resource_type="image", overwrite=False
        )
        actual_public_id = result.get("public_id")
        image_format = str(result.get("format", "")).lower()
        if image_format not in self.VALID_FORMATS or not actual_public_id:
            raise IOError("Cloudinary returned invalid image metadata")
        saved_name = f"{actual_public_id}.{image_format}"
        if len(saved_name) > 100:
            raise IOError("Cloudinary filename too long for the product field")
        self._asset(saved_name)
        return saved_name

    def url(self, name):
        public_id, image_format = self._asset(name)
        return cloudinary.CloudinaryImage(public_id).build_url(
            format=image_format, secure=True
        )

    def _open(self, name, mode="rb"):
        if mode != "rb":
            raise ValueError("Product images can only be opened in binary mode")
        with urlopen(self.url(name), timeout=15) as response:
            return ContentFile(response.read(), name=name)

    def exists(self, name):
        public_id, _ = self._asset(name)
        try:
            cloudinary.api.resource(public_id, resource_type="image")
        except NotFound:
            return False
        return True

    def size(self, name):
        public_id, _ = self._asset(name)
        resource = cloudinary.api.resource(public_id, resource_type="image")
        return int(resource["bytes"])

    def delete(self, name):
        if not name:
            return
        public_id, _ = self._asset(name)
        cloudinary.uploader.destroy(
            public_id, resource_type="image", invalidate=True
        )
