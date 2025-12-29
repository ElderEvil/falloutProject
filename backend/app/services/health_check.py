"""Service health check utilities for startup and runtime monitoring."""

import logging
from dataclasses import dataclass
from enum import Enum

from minio import Minio
from minio.error import S3Error
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import settings

try:
    from app.core.celery import celery_app
except ImportError:
    celery_app = None

logger = logging.getLogger(__name__)


class ServiceStatus(str, Enum):
    """Health check status enum."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    service: str
    status: ServiceStatus
    message: str
    details: dict | None = None


class HealthCheckService:
    """Service for checking health of dependencies."""

    @staticmethod
    async def check_postgres(engine: AsyncEngine) -> HealthCheckResult:
        """
        Check PostgreSQL database connectivity.

        Args:
            engine: AsyncEngine instance

        Returns:
            HealthCheckResult with connection status
        """
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                return HealthCheckResult(
                    service="postgresql",
                    status=ServiceStatus.HEALTHY,
                    message="Database connection successful",
                    details={"host": settings.POSTGRES_SERVER, "database": settings.POSTGRES_DB},
                )
        except Exception as e:
            logger.exception("PostgreSQL health check failed")
            return HealthCheckResult(
                service="postgresql",
                status=ServiceStatus.UNHEALTHY,
                message=f"Database connection failed: {e!s}",
                details={"host": settings.POSTGRES_SERVER, "error": str(e)},
            )

    @staticmethod
    async def check_redis() -> HealthCheckResult:
        """
        Check Redis connectivity.

        Returns:
            HealthCheckResult with connection status
        """
        redis_client = None
        try:
            redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
            await redis_client.ping()
            return HealthCheckResult(
                service="redis",
                status=ServiceStatus.HEALTHY,
                message="Redis connection successful",
                details={"host": settings.REDIS_HOST, "port": settings.REDIS_PORT},
            )
        except Exception as e:
            logger.exception("Redis health check failed")
            return HealthCheckResult(
                service="redis",
                status=ServiceStatus.UNHEALTHY,
                message=f"Redis connection failed: {e!s}",
                details={"host": settings.REDIS_HOST, "error": str(e)},
            )
        finally:
            if redis_client:
                await redis_client.close()

    @staticmethod
    def check_celery() -> HealthCheckResult:
        """
        Check Celery worker and beat connectivity.

        Returns:
            HealthCheckResult with Celery status
        """
        if celery_app is None:
            return HealthCheckResult(
                service="celery",
                status=ServiceStatus.DEGRADED,
                message="Celery not configured",
                details={"workers": 0, "active_tasks": 0},
            )

        try:
            # Check if workers are available
            inspect = celery_app.control.inspect()
            stats = inspect.stats()
            active_tasks = inspect.active()

            if not stats:
                return HealthCheckResult(
                    service="celery",
                    status=ServiceStatus.UNHEALTHY,
                    message="No Celery workers available",
                    details={"workers": 0, "recommendation": "Start workers with: celery -A app.core.celery worker"},
                )

            worker_count = len(stats)
            total_active_tasks = sum(len(tasks) for tasks in (active_tasks or {}).values())

            return HealthCheckResult(
                service="celery",
                status=ServiceStatus.HEALTHY,
                message="Celery workers available",
                details={
                    "workers": worker_count,
                    "active_tasks": total_active_tasks,
                    "worker_names": list(stats.keys()),
                },
            )
        except Exception as e:
            logger.exception("Celery health check failed")
            return HealthCheckResult(
                service="celery",
                status=ServiceStatus.UNHEALTHY,
                message=f"Celery check failed: {e!s}",
                details={"error": str(e), "recommendation": "Check if Redis is running and workers are started"},
            )

    @staticmethod
    def check_minio() -> HealthCheckResult:
        """
        Check MinIO connectivity and bucket access.

        Returns:
            HealthCheckResult with connection status
        """
        try:
            client = Minio(
                f"{settings.MINIO_HOSTNAME}:{settings.MINIO_PORT}",
                access_key=settings.MINIO_ROOT_USER,
                secret_key=settings.MINIO_ROOT_PASSWORD,
                secure=False,
            )

            # Test connection by listing buckets
            buckets = client.list_buckets()
            bucket_names = [bucket.name for bucket in buckets]

            return HealthCheckResult(
                service="minio",
                status=ServiceStatus.HEALTHY,
                message="MinIO connection successful",
                details={
                    "host": settings.MINIO_HOSTNAME,
                    "port": settings.MINIO_PORT,
                    "buckets": bucket_names,
                },
            )
        except S3Error as e:
            logger.exception("MinIO health check failed")
            return HealthCheckResult(
                service="minio",
                status=ServiceStatus.UNHEALTHY,
                message=f"MinIO connection failed: {e!s}",
                details={"host": settings.MINIO_HOSTNAME, "error": str(e)},
            )
        except Exception as e:
            logger.exception("MinIO health check failed")
            return HealthCheckResult(
                service="minio",
                status=ServiceStatus.UNHEALTHY,
                message=f"MinIO connection failed: {e!s}",
                details={"host": settings.MINIO_HOSTNAME, "error": str(e)},
            )

    async def check_all_services(
        self, engine: AsyncEngine, *, include_celery: bool = True
    ) -> dict[str, HealthCheckResult]:
        """
        Check all services and return results.

        Args:
            engine: AsyncEngine for database connection
            include_celery: Whether to check Celery workers (default: True)

        Returns:
            Dictionary mapping service names to health check results
        """
        results = {}

        # Check PostgreSQL
        postgres_result = await self.check_postgres(engine)
        results["postgresql"] = postgres_result

        # Check Redis
        redis_result = await self.check_redis()
        results["redis"] = redis_result

        # Check MinIO
        minio_result = self.check_minio()
        results["minio"] = minio_result

        # Check Celery (optional, may be slow on startup)
        if include_celery:
            celery_result = self.check_celery()
            results["celery"] = celery_result

        return results

    @staticmethod
    def log_health_check_results(results: dict[str, HealthCheckResult]) -> bool:
        """
        Log health check results and return overall health status.

        Args:
            results: Dictionary of health check results

        Returns:
            True if all services are healthy, False otherwise
        """
        all_healthy = True

        logger.info("==================================================")
        logger.info("SERVICE HEALTH CHECK RESULTS")
        logger.info("==================================================")

        for _service_name, result in results.items():
            status_emoji = "✓" if result.status == ServiceStatus.HEALTHY else "✗"
            log_level = logging.INFO if result.status == ServiceStatus.HEALTHY else logging.WARNING

            logger.log(
                log_level,
                "%s %s: %s - %s",
                status_emoji,
                result.service.upper(),
                result.status.value,
                result.message,
            )

            if result.status != ServiceStatus.HEALTHY:
                all_healthy = False

        logger.info("==================================================")

        if all_healthy:
            logger.info("✓ All services are healthy")
        else:
            logger.warning("⚠ Some services are unhealthy - application may have degraded functionality")

        return all_healthy
