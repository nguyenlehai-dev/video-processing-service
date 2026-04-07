from app.services.storage_service import _get_r2_client
from app.config import get_settings

def set_cors():
    settings = get_settings()
    s3 = _get_r2_client()
    cors_configuration = {
        'CORSRules': [{
            'AllowedHeaders': ['*'],
            'AllowedMethods': ['GET', 'PUT', 'POST', 'DELETE', 'HEAD'],
            'AllowedOrigins': ['*'],
            'ExposeHeaders': ['ETag'],
            'MaxAgeSeconds': 3000
        }]
    }
    print(f"Setting CORS for bucket {settings.R2_BUCKET_NAME}")
    s3.put_bucket_cors(Bucket=settings.R2_BUCKET_NAME, CORSConfiguration=cors_configuration)
    print("Done!")

if __name__ == "__main__":
    set_cors()
