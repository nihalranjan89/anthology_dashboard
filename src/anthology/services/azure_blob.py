from urllib.parse import quote
from django.conf import settings

def get_blob_url(filename, report_type='draft'):
    # Builds a simple URL; production should use azure-storage-blob BlobClient to generate SAS urls
    if report_type == 'final':
        container = settings.AZ_STORAGE_FINALS_URI
    else:
        container = settings.AZ_STORAGE_DRAFTS_URI
    hostname = settings.AZ_STORAGE_HOSTNAME.rstrip('/')
    token = settings.AZ_TOKEN.lstrip('?')
    # Ensure filename is URL-encoded
    return f"https://{hostname}/{container}/{quote(filename)}?{token}"

def download_blob_to_bytes(filename, report_type='draft'):
    # Use azure-storage-blob in production; here is a hint code piece
    from azure.storage.blob import BlobClient
    hostname = settings.AZ_STORAGE_HOSTNAME
    container = settings.AZ_STORAGE_FINALS_URI if report_type == 'final' else settings.AZ_STORAGE_DRAFTS_URI
    blob = BlobClient(account_url=f"https://{hostname}", container_name=container, blob_name=filename, credential=settings.AZ_TOKEN)
    stream = blob.download_blob()
    return stream.readall()
