#!/usr/bin/env python3
"""
Cost Report Generator

Generates comprehensive cost reports for the AI Log Filter system.
Outputs cost analysis, ROI metrics, and savings breakdowns.

Usage:
    python scripts/cost_report.py --format json
    python scripts/cost_report.py --format text --output reports/cost_report.txt
    python scripts/cost_report.py --format markdown --output reports/cost_report.md
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.monitoring.cost_tracker import (
    INFRASTRUCTURE_COSTS,
    QRADAR_PRICING_TIERS,
    TOTAL_INFRASTRUCTURE_COST,
    get_cost_tracker,
)


# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def format_currency(value: float) -> str:
    """Format a value as USD currency."""
    return f"${value:,.2f}"


def format_number(value: float, decimals: int = 0) -> str:
    """Format a large number with commas."""
    return f"{value:,.{decimals}f}"


def print_header(text: str, color: str = Colors.HEADER):
    """Print a formatted header."""
    print(f"\n{color}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{color}{Colors.BOLD}{text:^80}{Colors.ENDC}")
    print(f"{color}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")


def print_section(title: str, color: str = Colors.BLUE):
    """Print a section header."""
    print(f"\n{color}{Colors.BOLD}── {title} {Colors.ENDC}")
    print(f"{color}{'─' * (len(title) + 4)}{Colors.ENDC}\n")


def generate_text_report(report_data: dict) -> str:
    """Generate a text-based cost report."""
    output = []

    # Header
    output.append("=" * 80)
    output.append("AI LOG FILTER - COST SAVINGS REPORT".center(80))
    output.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(80))
    output.append("=" * 80)
    output.append("")

    # Summary
    summary = report_data["summary"]
    output.append("SUMMARY")
    output.append("-" * 80)
    output.append(f"Current QRadar Tier:          {summary['current_tier'].upper()}")
    output.append(f"Current EPS Capacity:         {format_number(summary['current_eps_capacity'])} EPS")
    output.append(f"Current Tier Annual Cost:     {format_currency(summary['current_tier_cost'])}")
    output.append(f"Infrastructure Cost:          {format_currency(summary['infrastructure_cost'])}")
    output.append(f"Days in Production:           {summary['days_running']} days")
    output.append("")

    # Performance
    perf = report_data["performance"]
    output.append("PERFORMANCE METRICS")
    output.append("-" * 80)
    output.append(f"Avg EPS Before Filter:        {format_number(perf['avg_eps_before'], 2)}")
    output.append(f"Avg EPS After Filter:         {format_number(perf['avg_eps_after'], 2)}")
    output.append(f"EPS Reduction:                 {perf['avg_eps_reduction_percent']}%")
    output.append(f"Daily Logs Filtered:          {format_number(perf['eps_filtered_daily'])}")
    output.append(f"Monthly Logs Filtered:        {format_number(perf['eps_filtered_monthly'])}")
    output.append("")

    # Cost Savings
    savings = report_data["cost_savings"]
    output.append("COST SAVINGS")
    output.append("-" * 80)
    output.append(f"Hourly Savings:               {format_currency(savings['hourly'])}")
    output.append(f"Daily Savings:                {format_currency(savings['daily'])}")
    output.append(f"Monthly Savings:              {format_currency(savings['monthly'])}")
    output.append(f"Annual Savings:               {format_currency(savings['annual'])}")
    output.append("")

    # ROI
    roi = report_data["roi"]
    output.append("RETURN ON INVESTMENT (ROI)")
    output.append("-" * 80)
    output.append(f"Days to Break Even:           {roi['days_to_break_even']} days")
    output.append(f"Days Remaining:               {roi['days_remaining']} days")
    output.append(f"ROI Percentage:               {roi['roi_percentage']}%")
    output.append(f"Cumulative Savings:           {format_currency(roi['cumulative_savings'])}")
    output.append(f"Net Savings (after infra):    {format_currency(roi['net_savings'])}")
    output.append("")

    # Efficiency
    eff = report_data["efficiency"]
    output.append("EFFICIENCY METRICS")
    output.append("-" * 80)
    output.append(f"Cost per EPS Saved:           ${eff['cost_per_eps_saved_usd']:.6f}")
    output.append(f"Cost per Processed Event:    ${eff['cost_per_processed_event_usd']:.6f}")
    output.append(f"Cost Reduction Percentage:    {eff['cost_reduction_percentage']}%")
    output.append("")

    # Infrastructure Breakdown
    output.append("INFRASTRUCTURE COST BREAKDOWN")
    output.append("-" * 80)
    infra = report_data["infrastructure_breakdown"]
    for category, data in infra.items():
        output.append(f"{category:25} ${data['cost_usd']:>12,.2f}   {data['description']}")
    output.append(f"{'TOTAL':25} ${TOTAL_INFRASTRUCTURE_COST:>12,.2f}")
    output.append("")

    # QRadar Tiers
    output.append("QRADAR PRICING TIERS")
    output.append("-" * 80)
    tiers = report_data["qradar_tiers"]
    for tier, data in tiers.items():
        marker = " <-- CURRENT" if tier == summary["current_tier"].upper() else ""
        output.append(f"{tier:15} {data['max_eps']:>10,} EPS   ${data['annual_cost']:>12,.2f}/yr  {data['description']}{marker}")
    output.append("")

    return "\n".join(output)


def generate_markdown_report(report_data: dict) -> str:
    """Generate a Markdown cost report."""
    output = []

    # Header
    output.append("# AI Log Filter - Cost Savings Report")
    output.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Executive Summary Table
    summary = report_data["summary"]
    output.append("## 📊 Executive Summary")
    output.append("")
    output.append("| Metric | Value |")
    output.append("|--------|-------|")
    output.append(f"| Current QRadar Tier | {summary['current_tier'].upper()} |")
    output.append(f"| Current EPS Capacity | {format_number(summary['current_eps_capacity'])} EPS |")
    output.append(f"| Current Tier Annual Cost | {format_currency(summary['current_tier_cost'])} |")
    output.append(f"| Infrastructure Cost | {format_currency(summary['infrastructure_cost'])} |")
    output.append(f"| Days in Production | {summary['days_running']} days |")
    output.append("")

    # Performance
    perf = report_data["performance"]
    output.append("## 🚀 Performance Metrics")
    output.append("")
    output.append("| Metric | Value |")
    output.append("|--------|-------|")
    output.append(f"| Avg EPS Before Filter | {format_number(perf['avg_eps_before'], 2)} |")
    output.append(f"| Avg EPS After Filter | {format_number(perf['avg_eps_after'], 2)} |")
    output.append(f"| EPS Reduction | {perf['avg_eps_reduction_percent']}% |")
    output.append(f"| Daily Logs Filtered | {format_number(perf['eps_filtered_daily'])} |")
    output.append(f"| Monthly Logs Filtered | {format_number(perf['eps_filtered_monthly'])} |")
    output.append("")

    # Cost Savings
    savings = report_data["cost_savings"]
    output.append("## 💰 Cost Savings")
    output.append("")
    output.append("| Time Period | Savings |")
    output.append("|-------------|---------|")
    output.append(f"| Hourly | {format_currency(savings['hourly'])} |")
    output.append(f"| Daily | {format_currency(savings['daily'])} |")
    output.append(f"| Monthly | {format_currency(savings['monthly'])} |")
    output.append(f"| **Annual** | **{format_currency(savings['annual'])}** |")
    output.append("")

    # ROI
    roi = report_data["roi"]
    output.append("## 📈 Return on Investment (ROI)")
    output.append("")
    output.append("| Metric | Value |")
    output.append("|--------|-------|")
    output.append(f"| Days to Break Even | {roi['days_to_break_even']} days |")
    output.append(f"| Days Remaining | {roi['days_remaining']} days |")
    output.append(f"| ROI Percentage | {roi['roi_percentage']}% |")
    output.append(f"| Cumulative Savings | {format_currency(roi['cumulative_savings'])} |")
    output.append(f"| Net Savings (after infra) | {format_currency(roi['net_savings'])} |")
    output.append("")

    # Efficiency
    eff = report_data["efficiency"]
    output.append("## ⚡ Efficiency Metrics")
    output.append("")
    output.append("| Metric | Value |")
    output.append("|--------|-------|")
    output.append(f"| Cost per EPS Saved | ${eff['cost_per_eps_saved_usd']:.6f} |")
    output.append(f"| Cost per Processed Event | ${eff['cost_per_processed_event_usd']:.6f} |")
    output.append(f"| Cost Reduction | {eff['cost_reduction_percentage']}% |")
    output.append("")

    # Infrastructure
    output.append("## 🖥️ Infrastructure Cost Breakdown")
    output.append("")
    output.append("| Component | Annual Cost | Description |")
    output.append("|-----------|-------------|-------------|")
    infra = report_data["infrastructure_breakdown"]
    for category, data in infra.items():
        output.append(f"| {category} | {format_currency(data['cost_usd'])} | {data['description']} |")
    output.append("")

    # QRadar Tiers
    output.append("## 🎯 QRadar Pricing Tiers")
    output.append("")
    output.append("| Tier | Max EPS | Annual Cost | Description |")
    output.append("|------|---------|-------------|-------------|")
    tiers = report_data["qradar_tiers"]
    for tier, data in tiers.items():
        marker = " ✅ *Current*" if tier == summary["current_tier"].upper() else ""
        output.append(f"| {tier} | {format_number(data['max_eps'])} | {format_currency(data['annual_cost'])} | {data['description']}{marker} |")
    output.append("")

    return "\n".join(output)


def print_colored_report(report_data: dict):
    """Print a colored report to the terminal."""
    summary = report_data["summary"]
    perf = report_data["performance"]
    savings = report_data["cost_savings"]
    roi = report_data["roi"]
    eff = report_data["efficiency"]

    print_header("AI LOG FILTER - COST SAVINGS REPORT", Colors.CYAN)
    print(f"{Colors.CYAN}Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.ENDC}\n")

    # Summary
    print_section("SUMMARY", Colors.BLUE)
    print(f"{Colors.GREEN}Current QRadar Tier:          {Colors.BOLD}{summary['current_tier'].upper()}{Colors.ENDC}")
    print(f"Current EPS Capacity:         {format_number(summary['current_eps_capacity'])} EPS")
    print(f"Current Tier Annual Cost:     {format_currency(summary['current_tier_cost'])}")
    print(f"Infrastructure Cost:          {format_currency(summary['infrastructure_cost'])}")
    print(f"Days in Production:           {summary['days_running']} days")

    # Performance
    print_section("PERFORMANCE METRICS", Colors.YELLOW)
    print(f"Avg EPS Before Filter:        {format_number(perf['avg_eps_before'], 2)}")
    print(f"Avg EPS After Filter:         {format_number(perf['avg_eps_after'], 2)}")
    print(f"{Colors.GREEN}EPS Reduction:                 {Colors.BOLD}{perf['avg_eps_reduction_percent']}%{Colors.ENDC}")
    print(f"Daily Logs Filtered:          {format_number(perf['eps_filtered_daily'])}")
    print(f"Monthly Logs Filtered:        {format_number(perf['eps_filtered_monthly'])}")

    # Cost Savings
    print_section("COST SAVINGS", Colors.GREEN)
    print(f"Hourly Savings:               {format_currency(savings['hourly'])}")
    print(f"Daily Savings:                {format_currency(savings['daily'])}")
    print(f"Monthly Savings:              {format_currency(savings['monthly'])}")
    print(f"{Colors.GREEN}{Colors.BOLD}Annual Savings:               {format_currency(savings['annual'])}{Colors.ENDC}")

    # ROI
    print_section("RETURN ON INVESTMENT (ROI)", Colors.CYAN)
    print(f"Days to Break Even:           {roi['days_to_break_even']} days")
    print(f"Days Remaining:               {roi['days_remaining']} days")
    roi_color = Colors.GREEN if roi['roi_percentage'] >= 0 else Colors.RED
    print(f"{roi_color}ROI Percentage:               {Colors.BOLD}{roi['roi_percentage']}%{Colors.ENDC}")
    print(f"Cumulative Savings:           {format_currency(roi['cumulative_savings'])}")
    net_color = Colors.GREEN if roi['net_savings'] >= 0 else Colors.RED
    print(f"{net_color}Net Savings (after infra):    {format_currency(roi['net_savings'])}{Colors.ENDC}")

    # Efficiency
    print_section("EFFICIENCY METRICS", Colors.YELLOW)
    print(f"Cost per EPS Saved:           ${eff['cost_per_eps_saved_usd']:.6f}")
    print(f"Cost per Processed Event:    ${eff['cost_per_processed_event_usd']:.6f}")
    print(f"{Colors.GREEN}Cost Reduction Percentage:    {eff['cost_reduction_percentage']}%{Colors.ENDC}")

    # Infrastructure
    print_section("INFRASTRUCTURE COST BREAKDOWN", Colors.BLUE)
    infra = report_data["infrastructure_breakdown"]
    for category, data in infra.items():
        print(f"{category:25} {Colors.CYAN}{format_currency(data['cost_usd']):>15}{Colors.ENDC}   {data['description']}")
    print(f"{'TOTAL':25} {Colors.GREEN}{Colors.BOLD}{format_currency(TOTAL_INFRASTRUCTURE_COST):>15}{Colors.ENDC}")

    # QRadar Tiers
    print_section("QRADAR PRICING TIERS", Colors.BLUE)
    tiers = report_data["qradar_tiers"]
    for tier, data in tiers.items():
        marker = f" {Colors.GREEN}✅ <-- CURRENT{Colors.ENDC}" if tier == summary["current_tier"].upper() else ""
        print(f"{tier:15} {data['max_eps']:>10,} EPS   {Colors.CYAN}{format_currency(data['annual_cost']):>12}{Colors.ENDC}/yr  {data['description']}{marker}")

    print("\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate cost savings reports for AI Log Filter"
    )
    parser.add_argument(
        "--format",
        choices=["text", "markdown", "json", "terminal"],
        default="terminal",
        help="Output format (default: terminal)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (if not specified, prints to stdout)"
    )
    parser.add_argument(
        "--qradar-eps",
        type=int,
        default=15_000,
        help="Current QRadar EPS capacity (default: 15000)"
    )

    args = parser.parse_args()

    # Initialize cost tracker
    from src.monitoring.cost_tracker import init_cost_tracker
    tracker = init_cost_tracker(args.qradar_eps)

    # Generate sample EPS data for demo (in production, this would come from actual metrics)
    import random
    for _ in range(60):
        eps_before = random.uniform(14000, 16000)
        eps_after = eps_before * random.uniform(0.45, 0.55)
        reduction = (eps_before - eps_after) / eps_before
        tracker.record_eps_data(eps_before, eps_after, reduction)

    # Get cost report
    report_data = tracker.get_cost_report()

    # Generate output
    if args.format == "json":
        output = json.dumps(report_data, indent=2)
    elif args.format == "text":
        output = generate_text_report(report_data)
    elif args.format == "markdown":
        output = generate_markdown_report(report_data)
    elif args.format == "terminal":
        print_colored_report(report_data)
        return 0
    else:
        print(f"Unknown format: {args.format}", file=sys.stderr)
        return 1

    # Write to file or stdout
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
