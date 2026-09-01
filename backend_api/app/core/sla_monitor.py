"""SLA Monitoring and Uptime Tracking.

Tracks:
- Service uptime percentage
- Response time percentiles (p50, p95, p99)
- Incident history
- SLA compliance status

SLA Targets:
- Availability: 99.9% (8.76 hours downtime/year)
- Response time: p95 < 200ms
- Error rate: < 0.1%
"""

import time
import logging
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class Incident:
    """Represents a service incident."""
    id: str
    start_time: float
    end_time: Optional[float] = None
    severity: str = "unknown"
    description: str = ""
    resolved: bool = False

    @property
    def duration_seconds(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def is_active(self) -> bool:
        return not self.resolved


@dataclass
class SLAMetrics:
    """SLA compliance metrics."""
    period_start: float = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    response_times: List[float] = field(default_factory=list)
    incidents: List[Incident] = field(default_factory=list)

    @property
    def availability(self) -> float:
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.failed_requests / self.total_requests) * 100

    @property
    def avg_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)

    @property
    def p50_response_time(self) -> float:
        return self._percentile(50)

    @property
    def p95_response_time(self) -> float:
        return self._percentile(95)

    @property
    def p99_response_time(self) -> float:
        return self._percentile(99)

    def _percentile(self, p: int) -> float:
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * p / 100)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    @property
    def sla_compliant(self) -> bool:
        """Check if all SLA targets are met."""
        return (
            self.availability >= 99.9 and
            self.p95_response_time < 200 and
            self.error_rate < 0.1
        )


class SLAMonitor:
    """Monitors SLA compliance and tracks incidents."""

    def __init__(self):
        self._metrics = SLAMetrics(period_start=time.time())
        self._current_incident: Optional[Incident] = None
        self._incident_counter = 0

    def record_request(self, success: bool, response_time_ms: float):
        """Record a request for SLA tracking."""
        self._metrics.total_requests += 1
        if success:
            self._metrics.successful_requests += 1
        else:
            self._metrics.failed_requests += 1
            # Auto-create incident on failure
            if self._current_incident is None:
                self._start_incident("request_failure", f"Request failed (response: {response_time_ms:.0f}ms)")

        self._metrics.response_times.append(response_time_ms)

        # Keep only last 10000 response times to prevent memory growth
        if len(self._metrics.response_times) > 10000:
            self._metrics.response_times = self._metrics.response_times[-10000:]

    def _start_incident(self, severity: str, description: str):
        """Start a new incident."""
        self._incident_counter += 1
        incident = Incident(
            id=f"INC-{self._incident_counter:04d}",
            start_time=time.time(),
            severity=severity,
            description=description,
        )
        self._current_incident = incident
        self._metrics.incidents.append(incident)
        logger.warning("SLA incident started: %s — %s", incident.id, description)

    def resolve_incident(self, incident_id: str = None):
        """Resolve an incident."""
        if self._current_incident and (incident_id is None or self._current_incident.id == incident_id):
            self._current_incident.end_time = time.time()
            self._current_incident.resolved = True
            logger.info(
                "SLA incident resolved: %s (duration: %.1fs)",
                self._current_incident.id,
                self._current_incident.duration_seconds,
            )
            self._current_incident = None

    def get_status(self) -> dict:
        """Get current SLA status."""
        metrics = self._metrics
        active_incidents = [i for i in metrics.incidents if i.is_active]

        return {
            "sla_compliant": metrics.sla_compliant,
            "availability": round(metrics.availability, 4),
            "error_rate": round(metrics.error_rate, 4),
            "response_time": {
                "avg_ms": round(metrics.avg_response_time, 1),
                "p50_ms": round(metrics.p50_response_time, 1),
                "p95_ms": round(metrics.p95_response_time, 1),
                "p99_ms": round(metrics.p99_response_time, 1),
            },
            "requests": {
                "total": metrics.total_requests,
                "successful": metrics.successful_requests,
                "failed": metrics.failed_requests,
            },
            "incidents": {
                "active": len(active_incidents),
                "total": len(metrics.incidents),
                "active_list": [
                    {
                        "id": i.id,
                        "severity": i.severity,
                        "description": i.description,
                        "duration_seconds": round(i.duration_seconds, 1),
                    }
                    for i in active_incidents
                ],
            },
            "targets": {
                "availability": "99.9%",
                "p95_response_ms": "< 200ms",
                "error_rate": "< 0.1%",
            },
            "period_start": datetime.fromtimestamp(
                metrics.period_start, tz=timezone.utc
            ).isoformat(),
        }

    def get_uptime_string(self) -> str:
        """Get human-readable uptime."""
        uptime = time.time() - self._metrics.period_start
        days = int(uptime // 86400)
        hours = int((uptime % 86400) // 3600)
        minutes = int((uptime % 3600) // 60)
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"


# Global SLA monitor instance
sla_monitor = SLAMonitor()
