"""
Chart generation utilities for Genie Bot.

This module provides:
- Auto-detection of appropriate chart types based on data structure
- Chart generation using matplotlib
- Export to base64 PNG for Bot Framework attachments
- CSV export for data downloads

Supported chart types: Bar, Line, Pie, Scatter, Histogram
"""

from __future__ import annotations

import base64
import csv
import io
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any


def _debug_print(message: str) -> None:
    """Print debug message and flush immediately for Azure logs."""
    try:
        print(f"[GENIE_CHARTS_DEBUG] {message}", flush=True)
        sys.stdout.flush()
    except Exception:
        pass


class ChartType(Enum):
    """Supported chart types."""
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    TABLE = "table"  # No chart, just table


@dataclass
class ChartData:
    """Container for chart-ready data."""
    columns: list[str]
    rows: list[list[Any]]
    recommended_type: ChartType
    chartable: bool
    reason: str  # Why this chart type was recommended or why not chartable


@dataclass
class ChartResult:
    """Result of chart generation."""
    success: bool
    image_base64: str | None  # PNG image as base64
    content_type: str  # e.g., "image/png"
    error: str | None
    chart_type: ChartType


def analyze_data_for_chart(columns: list[str], rows: list[list[Any]]) -> ChartData:
    """
    Analyze data structure and recommend appropriate chart type.
    
    Rules:
    - Empty data or too many rows (>100) → TABLE (not chartable)
    - 1 numeric column → HISTOGRAM
    - 1 categorical + 1 numeric → BAR
    - 2 numeric columns → SCATTER
    - Time/date column + numeric → LINE
    - 1 categorical with counts (small set) → PIE
    - Otherwise → BAR (default for chartable data)
    """
    _debug_print(f"Analyzing data: {len(columns)} columns, {len(rows)} rows")
    
    if not columns or not rows:
        return ChartData(
            columns=columns,
            rows=rows,
            recommended_type=ChartType.TABLE,
            chartable=False,
            reason="No data to chart"
        )
    
    if len(rows) > 100:
        return ChartData(
            columns=columns,
            rows=rows,
            recommended_type=ChartType.TABLE,
            chartable=False,
            reason=f"Too many rows ({len(rows)}) for effective visualization"
        )
    
    # Analyze column types
    numeric_cols = []
    categorical_cols = []
    date_cols = []
    
    for i, col in enumerate(columns):
        col_values = [row[i] for row in rows if i < len(row) and row[i] is not None]
        
        if not col_values:
            continue
            
        # Check if numeric
        numeric_count = 0
        for v in col_values:
            try:
                float(v)
                numeric_count += 1
            except (ValueError, TypeError):
                pass
        
        # Check if date-like (simple heuristic)
        date_keywords = ['date', 'time', 'timestamp', 'day', 'month', 'year', 'created', 'updated']
        is_date = any(kw in col.lower() for kw in date_keywords)
        
        if numeric_count > len(col_values) * 0.8:  # 80% numeric
            if is_date:
                date_cols.append(i)
            else:
                numeric_cols.append(i)
        else:
            categorical_cols.append(i)
    
    _debug_print(f"Column analysis: numeric={numeric_cols}, categorical={categorical_cols}, date={date_cols}")
    
    # Determine chart type based on column composition
    num_numeric = len(numeric_cols)
    num_categorical = len(categorical_cols)
    num_date = len(date_cols)
    
    # Single numeric column → Histogram
    if num_numeric == 1 and num_categorical == 0 and num_date == 0:
        return ChartData(
            columns=columns,
            rows=rows,
            recommended_type=ChartType.HISTOGRAM,
            chartable=True,
            reason="Single numeric column - histogram shows distribution"
        )
    
    # Date + numeric → Line chart
    if num_date >= 1 and num_numeric >= 1:
        return ChartData(
            columns=columns,
            rows=rows,
            recommended_type=ChartType.LINE,
            chartable=True,
            reason="Time-series data - line chart shows trends"
        )
    
    # 2 numeric columns → Scatter
    if num_numeric >= 2 and num_categorical == 0:
        return ChartData(
            columns=columns,
            rows=rows,
            recommended_type=ChartType.SCATTER,
            chartable=True,
            reason="Two numeric columns - scatter plot shows correlation"
        )
    
    # Categorical + numeric → Bar or Pie
    if num_categorical >= 1 and num_numeric >= 1:
        # Pie chart for small number of categories (≤10)
        unique_categories = set()
        cat_col_idx = categorical_cols[0]
        for row in rows:
            if cat_col_idx < len(row):
                unique_categories.add(str(row[cat_col_idx]))
        
        if len(unique_categories) <= 10 and num_numeric == 1:
            return ChartData(
                columns=columns,
                rows=rows,
                recommended_type=ChartType.PIE,
                chartable=True,
                reason=f"Small categorical set ({len(unique_categories)} categories) - pie chart shows proportions"
            )
        
        return ChartData(
            columns=columns,
            rows=rows,
            recommended_type=ChartType.BAR,
            chartable=True,
            reason="Categorical with numeric values - bar chart for comparison"
        )
    
    # Default: If we have at least 2 columns and some rows, try bar chart
    if len(columns) >= 2 and len(rows) >= 1:
        return ChartData(
            columns=columns,
            rows=rows,
            recommended_type=ChartType.BAR,
            chartable=True,
            reason="Default visualization - bar chart"
        )
    
    return ChartData(
        columns=columns,
        rows=rows,
        recommended_type=ChartType.TABLE,
        chartable=False,
        reason="Data structure not suitable for visualization"
    )


def generate_chart(
    columns: list[str],
    rows: list[list[Any]],
    chart_type: ChartType,
    title: str = "Query Results"
) -> ChartResult:
    """
    Generate a chart image as base64 PNG.
    
    Args:
        columns: Column names
        rows: Data rows
        chart_type: Type of chart to generate
        title: Chart title
        
    Returns:
        ChartResult with base64 image or error
    """
    _debug_print(f"Generating {chart_type.value} chart: {len(columns)} cols, {len(rows)} rows")
    
    if chart_type == ChartType.TABLE:
        return ChartResult(
            success=False,
            image_base64=None,
            content_type="",
            error="TABLE type does not generate an image",
            chart_type=chart_type
        )
    
    try:
        # Import matplotlib here to avoid startup overhead
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend for server
        import matplotlib.pyplot as plt
        
        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))
        
        if chart_type == ChartType.BAR:
            _generate_bar_chart(ax, columns, rows)
        elif chart_type == ChartType.LINE:
            _generate_line_chart(ax, columns, rows)
        elif chart_type == ChartType.PIE:
            _generate_pie_chart(ax, columns, rows)
        elif chart_type == ChartType.SCATTER:
            _generate_scatter_chart(ax, columns, rows)
        elif chart_type == ChartType.HISTOGRAM:
            _generate_histogram(ax, columns, rows)
        
        ax.set_title(title, fontsize=12, fontweight='bold')
        plt.tight_layout()
        
        # Export to base64 PNG
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        plt.close(fig)
        
        _debug_print(f"Chart generated successfully: {len(image_base64)} chars base64")
        
        return ChartResult(
            success=True,
            image_base64=image_base64,
            content_type="image/png",
            error=None,
            chart_type=chart_type
        )
        
    except ImportError as e:
        _debug_print(f"matplotlib not available: {e}")
        return ChartResult(
            success=False,
            image_base64=None,
            content_type="",
            error=f"Chart library not available: {e}",
            chart_type=chart_type
        )
    except Exception as e:
        _debug_print(f"Chart generation error: {e}")
        return ChartResult(
            success=False,
            image_base64=None,
            content_type="",
            error=f"Failed to generate chart: {e}",
            chart_type=chart_type
        )


def _generate_bar_chart(ax, columns: list[str], rows: list[list[Any]]) -> None:
    """Generate a bar chart."""
    if len(columns) < 2:
        ax.text(0.5, 0.5, "Need at least 2 columns for bar chart", 
                ha='center', va='center', transform=ax.transAxes)
        return
    
    # Use first column as labels, second as values
    labels = [str(row[0])[:20] if row else "" for row in rows]  # Truncate long labels
    
    # Find first numeric column for values
    values = []
    for row in rows:
        if len(row) > 1:
            try:
                values.append(float(row[1]))
            except (ValueError, TypeError):
                values.append(0)
        else:
            values.append(0)
    
    # Limit to 20 bars for readability
    if len(labels) > 20:
        labels = labels[:20]
        values = values[:20]
    
    bars = ax.bar(range(len(labels)), values, color='steelblue')
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
    ax.set_xlabel(columns[0])
    ax.set_ylabel(columns[1] if len(columns) > 1 else "Value")
    
    # Add value labels on bars
    for bar, val in zip(bars, values):
        height = bar.get_height()
        ax.annotate(f'{val:.1f}' if isinstance(val, float) else str(val),
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=7)


def _generate_line_chart(ax, columns: list[str], rows: list[list[Any]]) -> None:
    """Generate a line chart."""
    if len(columns) < 2:
        ax.text(0.5, 0.5, "Need at least 2 columns for line chart",
                ha='center', va='center', transform=ax.transAxes)
        return
    
    x_labels = [str(row[0])[:15] if row else "" for row in rows]
    
    # Plot each numeric column
    colors = ['steelblue', 'coral', 'green', 'purple', 'orange']
    for col_idx in range(1, min(len(columns), 6)):  # Max 5 lines
        values = []
        for row in rows:
            if col_idx < len(row):
                try:
                    values.append(float(row[col_idx]))
                except (ValueError, TypeError):
                    values.append(None)
            else:
                values.append(None)
        
        # Filter None values for plotting
        valid_points = [(i, v) for i, v in enumerate(values) if v is not None]
        if valid_points:
            x_vals, y_vals = zip(*valid_points)
            ax.plot(x_vals, y_vals, marker='o', label=columns[col_idx], 
                    color=colors[(col_idx - 1) % len(colors)])
    
    ax.set_xticks(range(len(x_labels)))
    ax.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=8)
    ax.set_xlabel(columns[0])
    ax.legend(loc='best', fontsize=8)
    ax.grid(True, alpha=0.3)


def _generate_pie_chart(ax, columns: list[str], rows: list[list[Any]]) -> None:
    """Generate a pie chart."""
    if len(columns) < 2:
        ax.text(0.5, 0.5, "Need at least 2 columns for pie chart",
                ha='center', va='center', transform=ax.transAxes)
        return
    
    labels = []
    values = []
    
    for row in rows:
        if len(row) >= 2:
            try:
                val = float(row[1])
                if val > 0:  # Only positive values for pie
                    labels.append(str(row[0])[:20])
                    values.append(val)
            except (ValueError, TypeError):
                pass
    
    if not values:
        ax.text(0.5, 0.5, "No valid numeric data for pie chart",
                ha='center', va='center', transform=ax.transAxes)
        return
    
    # Limit to 10 slices
    if len(labels) > 10:
        # Group smaller values as "Other"
        sorted_data = sorted(zip(values, labels), reverse=True)
        top_9 = sorted_data[:9]
        other_sum = sum(v for v, _ in sorted_data[9:])
        values, labels = zip(*top_9)
        values = list(values) + [other_sum]
        labels = list(labels) + ["Other"]
    
    colors = plt.cm.Set3(range(len(labels)))
    wedges, texts, autotexts = ax.pie(values, labels=labels, autopct='%1.1f%%',
                                       colors=colors, startangle=90)
    
    for text in texts:
        text.set_fontsize(8)
    for autotext in autotexts:
        autotext.set_fontsize(7)


def _generate_scatter_chart(ax, columns: list[str], rows: list[list[Any]]) -> None:
    """Generate a scatter plot."""
    if len(columns) < 2:
        ax.text(0.5, 0.5, "Need at least 2 columns for scatter plot",
                ha='center', va='center', transform=ax.transAxes)
        return
    
    x_values = []
    y_values = []
    
    for row in rows:
        if len(row) >= 2:
            try:
                x = float(row[0])
                y = float(row[1])
                x_values.append(x)
                y_values.append(y)
            except (ValueError, TypeError):
                pass
    
    if not x_values:
        ax.text(0.5, 0.5, "No valid numeric data for scatter plot",
                ha='center', va='center', transform=ax.transAxes)
        return
    
    ax.scatter(x_values, y_values, alpha=0.6, color='steelblue', edgecolors='white')
    ax.set_xlabel(columns[0])
    ax.set_ylabel(columns[1])
    ax.grid(True, alpha=0.3)


def _generate_histogram(ax, columns: list[str], rows: list[list[Any]]) -> None:
    """Generate a histogram."""
    # Find first numeric column
    values = []
    col_name = columns[0] if columns else "Value"
    
    for row in rows:
        for i, val in enumerate(row):
            try:
                values.append(float(val))
                if i < len(columns):
                    col_name = columns[i]
                break
            except (ValueError, TypeError):
                continue
    
    if not values:
        ax.text(0.5, 0.5, "No numeric data for histogram",
                ha='center', va='center', transform=ax.transAxes)
        return
    
    ax.hist(values, bins=min(20, len(values) // 2 + 1), color='steelblue', 
            edgecolor='white', alpha=0.7)
    ax.set_xlabel(col_name)
    ax.set_ylabel("Frequency")
    ax.grid(True, alpha=0.3, axis='y')


def export_to_csv(columns: list[str], rows: list[list[Any]]) -> str:
    """
    Export data to CSV format as a string.
    
    Returns:
        CSV data as string
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def get_chart_type_options() -> list[dict[str, str]]:
    """
    Get list of available chart types for Adaptive Card buttons.
    
    Returns:
        List of dicts with 'title' and 'value' keys
    """
    return [
        {"title": "📊 Bar", "value": ChartType.BAR.value},
        {"title": "📈 Line", "value": ChartType.LINE.value},
        {"title": "🥧 Pie", "value": ChartType.PIE.value},
        {"title": "⚫ Scatter", "value": ChartType.SCATTER.value},
        {"title": "📉 Histogram", "value": ChartType.HISTOGRAM.value},
    ]
