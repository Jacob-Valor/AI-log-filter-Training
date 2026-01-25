"""
Cost Tracker Module

Tracks and calculates cost savings for the AI Log Filter system.
Calculates QRadar license cost savings, infrastructure costs, and ROI.

Key Features:
- QRadar EPS-based license cost tracking
- Infrastructure cost calculation
- Real-time cost savings reporting
- Cost trend analysis
- ROI metrics
"""

import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Any

from prometheus_client import Gauge

from src.utils.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# QRadar Pricing Model (based on typical IBM QRadar tiers)
# Adjust these values based on your actual contract
QRADAR_PRICING_TIERS = {
    "basic": {
        "max_eps": 5_000,
        "annual_cost": 150_000,  # $150K/year
        "description": "Basic SIEM license"
    },
    "standard": {
        "max_eps": 15_000,
        "annual_cost": 450_000,  # $450K/year
        "description": "Standard SIEM license"
    },
    "enterprise": {
        "max_eps": 50_000,
        "annual_cost": 1_200_000,  # $1.2M/year
        "description": "Enterprise SIEM license"
    },
    "premium": {
        "max_eps": 100_000,
        "annual_cost": 2_500_000,  # $2.5M/year
        "description": "Premium SIEM license"
    }
}

# AI Filter Infrastructure Costs (annual)
INFRASTRUCTURE_COSTS = {
    "kafka_cluster": {
        "annual_cost": 12_000,  # Kafka infrastructure
        "description": "Kafka cluster hosting"
    },
    "compute": {
        "annual_cost": 24_000,  # AI engine compute
        "description": "AI filter compute instances"
    },
    "storage": {
        "annual_cost": 8_000,   # S3 cold storage
        "description": "Cold storage for logs"
    },
    "monitoring": {
        "annual_cost": 6_000,   # Prometheus/Grafana
        "description": "Monitoring infrastructure"
    },
    "support": {
        "annual_cost": 10_000,  # Engineering support
        "description": "Ongoing support and maintenance"
    }
}

# Calculate total annual infrastructure cost
TOTAL_INFRASTRUCTURE_COST = sum(
    item["annual_cost"] for item in INFRASTRUCTURE_COSTS.values()
)

# =============================================================================
# PROMETHEUS METRICS
# =============================================================================

# Cost Savings Metrics
COST_SAVINGS_HOURLY = Gauge(
    'ai_filter_cost_savings_hourly_usd',
    'Hourly cost savings in USD'
)

COST_SAVINGS_DAILY = Gauge(
    'ai_filter_cost_savings_daily_usd',
    'Daily cost savings in USD'
)

COST_SAVINGS_MONTHLY = Gauge(
    'ai_filter_cost_savings_monthly_usd',
    'Monthly cost savings in USD'
)

COST_SAVINGS_ANNUAL = Gauge(
    'ai_filter_cost_savings_annual_usd',
    'Projected annual cost savings in USD'
)

# License Tier Metrics
QRADAR_CURRENT_TIER = Gauge(
    'ai_filter_qradar_current_tier',
    'Current QRadar license tier (1=basic, 2=standard, 3=enterprise, 4=premium)'
)

QRADAR_NEXT_LOWER_TIER = Gauge(
    'ai_filter_qradar_next_lower_tier',
    'Next lower QRadar license tier (0=none, 1-4)'
)

# Infrastructure Cost Metrics
INFRASTRUCTURE_COST_TOTAL = Gauge(
    'ai_filter_infrastructure_cost_annual_usd',
    'Total annual infrastructure cost for AI filter'
)

# ROI Metrics
ROI_DAYS_TO_BREAK_EVEN = Gauge(
    'ai_filter_roi_days_to_break_even',
    'Days to break even on infrastructure investment'
)

ROI_PERCENTAGE = Gauge(
    'ai_filter_roi_percentage',
    'Return on investment percentage'
)

# Cost per EPS Metrics
COST_PER_EPS_SAVED = Gauge(
    'ai_filter_cost_per_eps_saved_usd',
    'Cost per EPS of logs saved'
)

COST_PER_PROCESSED_EVENT = Gauge(
    'ai_filter_cost_per_processed_event_usd',
    'Cost per event processed by AI filter'
)

# Cost Trends
COST_SAVINGS_TREND_7D = Gauge(
    'ai_filter_cost_savings_trend_7d_usd',
    '7-day cost savings trend (average daily savings)'
)

COST_SAVINGS_TREND_30D = Gauge(
    'ai_filter_cost_savings_trend_30d_usd',
    '30-day cost savings trend (average daily savings)'
)

# Cost Breakdown by Category
COST_SAVINGS_BY_CATEGORY = Gauge(
    'ai_filter_cost_savings_by_category_usd',
    'Cost savings by log category',
    ['category']
)


# =============================================================================
# COST CALCULATOR CLASS
# =============================================================================

@dataclass
class CostSnapshot:
    """Snapshot of cost data at a point in time."""
    timestamp: float
    eps_before_filter: float
    eps_after_filter: float
    eps_reduction_ratio: float
    current_qradar_cost_annual: float
    potential_qradar_cost_annual: float
    savings_hourly: float
    savings_daily: float
    savings_monthly: float
    savings_annual: float
    infrastructure_cost: float


class CostTracker:
    """
    Tracks cost savings and calculates ROI for the AI Log Filter.

    Main Features:
    1. QRadar License Cost Savings
    2. Infrastructure Cost Tracking
    3. ROI Calculations
    4. Cost Trend Analysis
    5. Break-Even Analysis
    """

    def __init__(self, current_qradar_eps: int = 15_000):
        """
        Initialize cost tracker.

        Args:
            current_qradar_eps: Current EPS capacity of QRadar license
        """
        self.current_qradar_eps = current_qradar_eps
        self.current_qradar_tier = self._determine_tier(current_qradar_eps)

        # EPS tracking windows
        self.eps_before_window = deque(maxlen=60)  # 60 seconds
        self.eps_after_window = deque(maxlen=60)   # 60 seconds

        # Cost history for trend analysis
        self.cost_history_7d = deque(maxlen=7 * 24 * 60)  # 7 days (minute granularity)
        self.cost_history_30d = deque(maxlen=30 * 24 * 60)  # 30 days (minute granularity)

        # Infrastructure cost tracking
        self.infrastructure_cost = TOTAL_INFRASTRUCTURE_COST

        # Break-even tracking
        self.start_date = datetime.now()
        self.total_savings_cumulative = 0.0

        self._lock = Lock()

        # Update initial metrics
        self._update_infrastructure_metrics()
        self._update_tier_metrics()

        logger.info(
            f"Cost tracker initialized for QRadar tier: {self.current_qradar_tier}",
            extra={
                "current_qradar_eps": current_qradar_eps,
                "infrastructure_cost": self.infrastructure_cost,
                "current_tier": self.current_qradar_tier
            }
        )

    def _determine_tier(self, eps: int) -> str:
        """Determine QRadar pricing tier based on EPS."""
        if eps <= QRADAR_PRICING_TIERS["basic"]["max_eps"]:
            return "basic"
        elif eps <= QRADAR_PRICING_TIERS["standard"]["max_eps"]:
            return "standard"
        elif eps <= QRADAR_PRICING_TIERS["enterprise"]["max_eps"]:
            return "enterprise"
        else:
            return "premium"

    def _get_tier_cost(self, tier: str) -> float:
        """Get annual cost for a given tier."""
        return QRADAR_PRICING_TIERS.get(tier, {}).get("annual_cost", 0)

    def _get_max_eps_for_tier(self, tier: str) -> int:
        """Get max EPS for a given tier."""
        return QRADAR_PRICING_TIERS.get(tier, {}).get("max_eps", 0)

    def _get_next_lower_tier(self, current_tier: str) -> str | None:
        """Get the next lower pricing tier."""
        tiers = ["basic", "standard", "enterprise", "premium"]
        current_index = tiers.index(current_tier)
        if current_index > 0:
            return tiers[current_index - 1]
        return None

    def _update_infrastructure_metrics(self):
        """Update infrastructure cost metrics."""
        INFRASTRUCTURE_COST_TOTAL.set(self.infrastructure_cost)

    def _update_tier_metrics(self):
        """Update QRadar tier metrics."""
        tier_map = {"basic": 1, "standard": 2, "enterprise": 3, "premium": 4}

        current_tier_value = tier_map.get(self.current_qradar_tier, 1)
        QRADAR_CURRENT_TIER.set(current_tier_value)

        next_lower = self._get_next_lower_tier(self.current_qradar_tier)
        if next_lower:
            QRADAR_NEXT_LOWER_TIER.set(tier_map.get(next_lower, 0))
        else:
            QRADAR_NEXT_LOWER_TIER.set(0)

    def record_eps_data(
        self,
        eps_before_filter: float,
        eps_after_filter: float,
        eps_reduction_ratio: float
    ):
        """
        Record EPS data for cost calculation.

        Args:
            eps_before_filter: EPS before AI filtering
            eps_after_filter: EPS after AI filtering
            eps_reduction_ratio: Ratio of logs filtered (0-1)
        """
        with self._lock:
            timestamp = time.time()
            self.eps_before_window.append((timestamp, eps_before_filter))
            self.eps_after_window.append((timestamp, eps_after_filter))

            # Calculate cost savings
            cost_data = self._calculate_cost_savings(
                eps_before_filter,
                eps_after_filter,
                eps_reduction_ratio
            )

            # Store in history for trend analysis
            self.cost_history_7d.append((timestamp, cost_data))
            self.cost_history_30d.append((timestamp, cost_data))

            # Track cumulative savings (add daily savings, not hourly)
            # Since this is called per sample, we need to scale appropriately
            # Assuming samples are ~1 second apart
            self.total_savings_cumulative += cost_data["savings_hourly"] / 3600

            # Update all metrics
            self._update_all_metrics(cost_data)

    def _calculate_cost_savings(
        self,
        eps_before: float,
        eps_after: float,
        reduction_ratio: float
    ) -> dict[str, Any]:
        """
        Calculate cost savings based on EPS reduction.

        Args:
            eps_before: EPS before filtering
            eps_after: EPS after filtering
            reduction_ratio: Ratio of logs filtered

        Returns:
            Dictionary with all cost calculations
        """
        # Current QRadar annual cost
        current_qradar_cost = self._get_tier_cost(self.current_qradar_tier)

        # Determine if we can downgrade to a lower tier
        potential_tier = self._determine_tier(int(eps_after))
        potential_qradar_cost = self._get_tier_cost(potential_tier)

        # If we can downgrade, that's the savings
        # Otherwise, we calculate per-EPS savings
        if potential_tier != self.current_qradar_tier:
            savings_annual = current_qradar_cost - potential_qradar_cost
        else:
            # Calculate per-EPS cost for current tier (cost per EPS per second)
            eps_cost_per_second = current_qradar_cost / (self.current_qradar_eps * 365 * 24 * 3600)
            eps_saved = eps_before - eps_after
            # Annual savings = EPS saved per second * cost per EPS per second * seconds in year
            savings_annual = eps_saved * eps_cost_per_second * 365 * 24 * 3600

        # Convert to time periods
        savings_hourly = savings_annual / (365 * 24)
        savings_daily = savings_annual / 365
        savings_monthly = savings_annual / 12

        # Calculate cost per EPS saved (per second)
        eps_saved = eps_before - eps_after
        cost_per_eps_saved = (self.infrastructure_cost / (365 * 24 * 3600)) / eps_saved if eps_saved > 0 else 0

        # Cost per processed event (per second)
        cost_per_event = (self.infrastructure_cost / (365 * 24 * 3600)) / eps_before if eps_before > 0 else 0

        return {
            "current_qradar_cost_annual": current_qradar_cost,
            "potential_qradar_cost_annual": potential_qradar_cost,
            "savings_hourly": savings_hourly,
            "savings_daily": savings_daily,
            "savings_monthly": savings_monthly,
            "savings_annual": savings_annual,
            "infrastructure_cost": self.infrastructure_cost,
            "cost_per_eps_saved": cost_per_eps_saved,
            "cost_per_event": cost_per_event
        }

    def _update_all_metrics(self, cost_data: dict[str, Any]):
        """Update all Prometheus metrics with cost data."""
        # Cost Savings
        COST_SAVINGS_HOURLY.set(cost_data["savings_hourly"])
        COST_SAVINGS_DAILY.set(cost_data["savings_daily"])
        COST_SAVINGS_MONTHLY.set(cost_data["savings_monthly"])
        COST_SAVINGS_ANNUAL.set(cost_data["savings_annual"])

        # Cost Metrics
        COST_PER_EPS_SAVED.set(cost_data["cost_per_eps_saved"])
        COST_PER_PROCESSED_EVENT.set(cost_data["cost_per_event"])

        # ROI
        days_running = (datetime.now() - self.start_date).days
        if days_running > 0:
            days_to_break_even = int(self.infrastructure_cost / cost_data["savings_daily"]) if cost_data["savings_daily"] > 0 else 0
            ROI_DAYS_TO_BREAK_EVEN.set(days_to_break_even)

            roi_percentage = ((self.total_savings_cumulative - self.infrastructure_cost) / self.infrastructure_cost) * 100 if self.infrastructure_cost > 0 else 0
            ROI_PERCENTAGE.set(roi_percentage)

        # Trends
        if len(self.cost_history_7d) > 0:
            avg_daily_7d = sum(
                data["savings_daily"] for _, data in list(self.cost_history_7d)[-7*24*60:]
            ) / min(len(self.cost_history_7d), 7 * 24 * 60)
            COST_SAVINGS_TREND_7D.set(avg_daily_7d)

        if len(self.cost_history_30d) > 0:
            avg_daily_30d = sum(
                data["savings_daily"] for _, data in list(self.cost_history_30d)[-30*24*60:]
            ) / min(len(self.cost_history_30d), 30 * 24 * 60)
            COST_SAVINGS_TREND_30D.set(avg_daily_30d)

    def record_cost_by_category(self, category: str, eps_saved: float):
        """
        Record cost savings by log category.

        Args:
            category: Log category (critical, suspicious, routine, noise)
            eps_saved: EPS saved for this category
        """
        # Calculate cost savings for this category
        current_qradar_cost = self._get_tier_cost(self.current_qradar_tier)
        eps_cost_per_year = current_qradar_cost / self.current_qradar_eps
        savings_annual = eps_saved * eps_cost_per_year * 365 * 24 * 3600
        savings_monthly = savings_annual / 12

        COST_SAVINGS_BY_CATEGORY.labels(category=category).set(savings_monthly)

    def get_cost_report(self) -> dict[str, Any]:
        """
        Generate comprehensive cost report.

        Returns:
            Dictionary with all cost metrics and analysis
        """
        with self._lock:
            # Calculate averages
            avg_eps_before = sum(eps for _, eps in self.eps_before_window) / len(self.eps_before_window) if self.eps_before_window else 0
            avg_eps_after = sum(eps for _, eps in self.eps_after_window) / len(self.eps_after_window) if self.eps_after_window else 0
            avg_reduction = ((avg_eps_before - avg_eps_after) / avg_eps_before * 100) if avg_eps_before > 0 else 0

            # Get latest cost data
            latest_cost = self._calculate_cost_savings(
                avg_eps_before,
                avg_eps_after,
                avg_reduction / 100
            )

            # ROI calculations
            days_running = (datetime.now() - self.start_date).days
            days_to_break_even = int(self.infrastructure_cost / latest_cost["savings_daily"]) if latest_cost["savings_daily"] > 0 else 0
            roi_percentage = ((self.total_savings_cumulative - self.infrastructure_cost) / self.infrastructure_cost * 100) if self.infrastructure_cost > 0 else 0

            return {
                "summary": {
                    "current_tier": self.current_qradar_tier,
                    "current_eps_capacity": self.current_qradar_eps,
                    "current_tier_cost": self._get_tier_cost(self.current_qradar_tier),
                    "infrastructure_cost": self.infrastructure_cost,
                    "days_running": days_running
                },
                "performance": {
                    "avg_eps_before": round(avg_eps_before, 2),
                    "avg_eps_after": round(avg_eps_after, 2),
                    "avg_eps_reduction_percent": round(avg_reduction, 2),
                    "eps_filtered_daily": round((avg_eps_before - avg_eps_after) * 24 * 3600, 0),
                    "eps_filtered_monthly": round((avg_eps_before - avg_eps_after) * 30 * 24 * 3600, 0)
                },
                "cost_savings": {
                    "hourly": round(latest_cost["savings_hourly"], 2),
                    "daily": round(latest_cost["savings_daily"], 2),
                    "monthly": round(latest_cost["savings_monthly"], 2),
                    "annual": round(latest_cost["savings_annual"], 2)
                },
                "roi": {
                    "days_to_break_even": days_to_break_even,
                    "days_remaining": max(0, days_to_break_even - days_running),
                    "roi_percentage": round(roi_percentage, 2),
                    "cumulative_savings": round(self.total_savings_cumulative, 2),
                    "net_savings": round(self.total_savings_cumulative - self.infrastructure_cost, 2)
                },
                "efficiency": {
                    "cost_per_eps_saved_usd": round(latest_cost["cost_per_eps_saved"], 6),
                    "cost_per_processed_event_usd": round(latest_cost["cost_per_event"], 6),
                    "cost_reduction_percentage": round(
                        (latest_cost["savings_annual"] / latest_cost["current_qradar_cost_annual"] * 100)
                        if latest_cost["current_qradar_cost_annual"] > 0 else 0,
                        2
                    )
                },
                "infrastructure_breakdown": {
                    category: {
                        "cost_usd": item["annual_cost"],
                        "description": item["description"]
                    }
                    for category, item in INFRASTRUCTURE_COSTS.items()
                },
                "qradar_tiers": {
                    tier: {
                        "max_eps": item["max_eps"],
                        "annual_cost": item["annual_cost"],
                        "description": item["description"]
                    }
                    for tier, item in QRADAR_PRICING_TIERS.items()
                }
            }

    def get_cost_snapshot(self) -> CostSnapshot:
        """
        Get a snapshot of current cost data.

        Returns:
            CostSnapshot with current metrics
        """
        with self._lock:
            avg_eps_before = sum(eps for _, eps in self.eps_before_window) / len(self.eps_before_window) if self.eps_before_window else 0
            avg_eps_after = sum(eps for _, eps in self.eps_after_window) / len(self.eps_after_window) if self.eps_after_window else 0
            avg_reduction = ((avg_eps_before - avg_eps_after) / avg_eps_before) if avg_eps_before > 0 else 0

            cost_data = self._calculate_cost_savings(avg_eps_before, avg_eps_after, avg_reduction)

            return CostSnapshot(
                timestamp=time.time(),
                eps_before_filter=avg_eps_before,
                eps_after_filter=avg_eps_after,
                eps_reduction_ratio=avg_reduction,
                current_qradar_cost_annual=cost_data["current_qradar_cost_annual"],
                potential_qradar_cost_annual=cost_data["potential_qradar_cost_annual"],
                savings_hourly=cost_data["savings_hourly"],
                savings_daily=cost_data["savings_daily"],
                savings_monthly=cost_data["savings_monthly"],
                savings_annual=cost_data["savings_annual"],
                infrastructure_cost=cost_data["infrastructure_cost"]
            )


# =============================================================================
# GLOBAL COST TRACKER INSTANCE
# =============================================================================

# Global cost tracker instance (will be initialized with config)
_cost_tracker: CostTracker | None = None
_tracker_lock = Lock()


def init_cost_tracker(current_qradar_eps: int = 15_000) -> CostTracker:
    """
    Initialize the global cost tracker.

    Args:
        current_qradar_eps: Current EPS capacity of QRadar license

    Returns:
        Initialized CostTracker instance
    """
    global _cost_tracker

    with _tracker_lock:
        if _cost_tracker is None:
            _cost_tracker = CostTracker(current_qradar_eps)
            logger.info("Global cost tracker initialized")

    return _cost_tracker


def get_cost_tracker() -> CostTracker | None:
    """Get the global cost tracker instance."""
    return _cost_tracker
