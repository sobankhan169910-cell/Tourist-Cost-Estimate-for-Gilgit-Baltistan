"""
Tour Cost Estimator - Numerical Calculation Module
==================================================
This module contains the core business and numerical calculation logic
for estimating guided tour costs using NumPy.

It provides functions for:
1. Loading and validating CSV pricing matrices.
2. Loading and validating JSON historical trip records.
3. Input validation for tour parameters (days, group size, season, comfort level).
4. Vectorized cost calculation with NumPy arrays and broadcasting.
5. Statistical price range analysis (25th, 50th, 75th percentiles).
6. Linear price forecasting using NumPy polyfit/polyval.
"""

from pathlib import Path
import csv
import json
from typing import Any, Dict, List, Tuple, Optional
import numpy as np


# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

# Default file paths relative to the project root
DEFAULT_PRICING_FILE = Path(__file__).resolve().parent / "data" / "pricing_data.csv"
DEFAULT_PAST_TRIPS_FILE = Path(__file__).resolve().parent / "data" / "past_trips.json"

# Expected categories (rows in the pricing matrix)
EXPECTED_CATEGORIES = ["Hotel", "Transport", "Food", "Guide", "Permits"]

# Expected comfort levels (columns in the pricing matrix)
EXPECTED_COMFORT_LEVELS = ["Budget", "Standard", "Luxury"]

# Season multiplier lookup table
# Low season: 20% discount (0.8x)
# Shoulder season: standard rate (1.0x)
# Peak season: 30% surcharge (1.3x)
SEASON_MULTIPLIERS: Dict[str, float] = {
    "Low": 0.8,
    "Shoulder": 1.0,
    "Peak": 1.3,
}

# Group discount threshold and rate
# Groups of 5 or more receive a 10% discount on all category costs
GROUP_DISCOUNT_THRESHOLD = 5
GROUP_DISCOUNT_RATE = 0.10


# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================

class CalculatorError(Exception):
    """Base exception for all tour cost estimator errors."""
    pass


class CalculatorDataError(CalculatorError):
    """Raised when pricing data or historical trip data is missing, invalid, or malformed."""
    pass


class CalculatorInputError(CalculatorError):
    """Raised when user-provided input parameters fail validation."""
    pass


# ============================================================================
# DATA LOADING & VALIDATION
# ============================================================================

def load_pricing_data(
    filepath: Path | str = DEFAULT_PRICING_FILE,
) -> Tuple[np.ndarray, List[str], List[str]]:
    """
    Load and validate the category pricing matrix from a CSV file.

    Parameters:
        filepath: Path to the pricing CSV file.

    Returns:
        Tuple containing:
        - pricing_matrix (np.ndarray): 2D NumPy array of shape (num_categories, num_comfort_levels)
        - categories (List[str]): List of category row labels in order
        - comfort_levels (List[str]): List of comfort level column labels in order

    Raises:
        CalculatorDataError: If the file is missing, empty, or has invalid format/data.
    """
    path = Path(filepath)
    if not path.is_file():
        raise CalculatorDataError(f"Pricing data file not found: {path.name}")

    try:
        with open(path, mode="r", encoding="utf-8") as file:
            reader = csv.reader(file)
            rows = [row for row in reader if row and any(cell.strip() for cell in row)]
    except Exception as exc:
        raise CalculatorDataError(f"Failed to read pricing file: {exc}") from exc

    if len(rows) < 2:
        raise CalculatorDataError("Pricing file is empty or missing data rows.")

    # Validate header row
    header = [col.strip().lower() for col in rows[0]]
    expected_header_cols = ["category", "budget", "standard", "luxury"]
    if header != expected_header_cols:
        raise CalculatorDataError(
            f"Invalid CSV header. Expected {expected_header_cols}, but found {header}"
        )

    categories: List[str] = []
    matrix_rows: List[List[float]] = []

    # Parse and validate each row
    for row_idx, row in enumerate(rows[1:], start=2):
        if len(row) != 4:
            raise CalculatorDataError(
                f"Row {row_idx} has {len(row)} columns, expected 4 columns."
            )

        category_name = row[0].strip()
        if not category_name:
            raise CalculatorDataError(f"Row {row_idx} has an empty category name.")

        categories.append(category_name)

        # Parse numeric prices for Budget, Standard, Luxury
        try:
            prices = [float(val.strip()) for val in row[1:]]
        except ValueError as exc:
            raise CalculatorDataError(
                f"Non-numeric price found in row {row_idx} ({category_name}): {exc}"
            ) from exc

        # Check for non-negative values
        if any(price < 0 for price in prices):
            raise CalculatorDataError(
                f"Negative price found in row {row_idx} ({category_name}): {prices}"
            )

        matrix_rows.append(prices)

    # Convert to 2D NumPy array with float64 data type
    pricing_matrix = np.array(matrix_rows, dtype=np.float64)

    # Validate expected categories are present
    if set(categories) != set(EXPECTED_CATEGORIES):
        raise CalculatorDataError(
            f"CSV categories mismatch. Expected {EXPECTED_CATEGORIES}, got {categories}"
        )

    comfort_levels = ["Budget", "Standard", "Luxury"]
    return pricing_matrix, categories, comfort_levels


def load_historical_trips(
    filepath: Path | str = DEFAULT_PAST_TRIPS_FILE,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Load and validate historical trip records from a JSON file.

    Supports either a top-level list of objects `[{"days": 3, "total_cost": 500}, ...]`
    or an object with a "trips" key `{"trips": [...]}`.

    Parameters:
        filepath: Path to the past trips JSON file.

    Returns:
        Tuple containing:
        - days_array (np.ndarray): 1D array of trip durations in days
        - costs_array (np.ndarray): 1D array of total trip costs

    Raises:
        CalculatorDataError: If the file is missing, invalid JSON, or lacks valid trip data.
    """
    path = Path(filepath)
    if not path.is_file():
        raise CalculatorDataError(f"Historical trips file not found: {path.name}")

    try:
        with open(path, mode="r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception as exc:
        raise CalculatorDataError(f"Failed to parse JSON file {path.name}: {exc}") from exc

    # Support either top-level list or dict with 'trips' key
    if isinstance(data, dict):
        if "trips" in data and isinstance(data["trips"], list):
            trip_list = data["trips"]
        else:
            raise CalculatorDataError(
                "Historical JSON object must contain a 'trips' list."
            )
    elif isinstance(data, list):
        trip_list = data
    else:
        raise CalculatorDataError("Historical JSON root must be a list or object with 'trips'.")

    if not trip_list:
        raise CalculatorDataError("Historical trip list is empty.")

    days_list: List[float] = []
    costs_list: List[float] = []

    for idx, item in enumerate(trip_list, start=1):
        if not isinstance(item, dict):
            raise CalculatorDataError(f"Trip record #{idx} is not a valid JSON object.")

        if "days" not in item or "total_cost" not in item:
            raise CalculatorDataError(
                f"Trip record #{idx} is missing 'days' or 'total_cost'."
            )

        try:
            days_val = float(item["days"])
            cost_val = float(item["total_cost"])
        except (ValueError, TypeError) as exc:
            raise CalculatorDataError(
                f"Non-numeric values in trip record #{idx}: {exc}"
            ) from exc

        if days_val <= 0 or cost_val < 0:
            raise CalculatorDataError(
                f"Invalid values in trip record #{idx}: days must be > 0 and cost >= 0."
            )

        days_list.append(days_val)
        costs_list.append(cost_val)

    days_array = np.array(days_list, dtype=np.float64)
    costs_array = np.array(costs_list, dtype=np.float64)

    return days_array, costs_array


# ============================================================================
# USER INPUT VALIDATION
# ============================================================================

def validate_inputs(
    days: Any,
    group_size: Any,
    season: Any,
    comfort_level: Any,
) -> Tuple[int, int, str, str]:
    """
    Validate and normalize user-submitted tour parameters.

    Parameters:
        days: Number of days (must be positive integer).
        group_size: Group size / number of persons (must be positive integer).
        season: Travel season ("Low", "Shoulder", "Peak").
        comfort_level: Comfort level ("Budget", "Standard", "Luxury").

    Returns:
        Tuple of validated (days_int, group_size_int, season_normalized, comfort_normalized).

    Raises:
        CalculatorInputError: If any parameter is invalid with a helpful error message.
    """
    # 1. Validate Days
    if days is None or str(days).strip() == "":
        raise CalculatorInputError("Number of days is required.")

    try:
        # Prevent float strings like "3.5" from converting to int without error
        days_str = str(days).strip()
        days_val = float(days_str)
        if not days_val.is_integer() or days_val <= 0:
            raise ValueError
        days_int = int(days_val)
    except (ValueError, TypeError):
        raise CalculatorInputError(
            "Number of days must be a positive whole number (e.g. 1, 2, 5, 10)."
        )

    # 2. Validate Group Size
    if group_size is None or str(group_size).strip() == "":
        raise CalculatorInputError("Group size is required.")

    try:
        group_str = str(group_size).strip()
        group_val = float(group_str)
        if not group_val.is_integer() or group_val <= 0:
            raise ValueError
        group_size_int = int(group_val)
    except (ValueError, TypeError):
        raise CalculatorInputError(
            "Group size must be a positive whole number (e.g. 1, 2, 4, 8)."
        )

    # 3. Validate Season
    if not season or not isinstance(season, str) or not season.strip():
        raise CalculatorInputError("Travel season is required.")

    season_clean = season.strip().title()
    if season_clean not in SEASON_MULTIPLIERS:
        allowed_seasons = ", ".join(SEASON_MULTIPLIERS.keys())
        raise CalculatorInputError(
            f"Invalid season '{season}'. Allowed options are: {allowed_seasons}."
        )

    # 4. Validate Comfort Level
    if not comfort_level or not isinstance(comfort_level, str) or not comfort_level.strip():
        raise CalculatorInputError("Comfort level is required.")

    comfort_clean = comfort_level.strip().title()
    if comfort_clean not in EXPECTED_COMFORT_LEVELS:
        allowed_levels = ", ".join(EXPECTED_COMFORT_LEVELS)
        raise CalculatorInputError(
            f"Invalid comfort level '{comfort_level}'. Allowed options are: {allowed_levels}."
        )

    return days_int, group_size_int, season_clean, comfort_clean


# ============================================================================
# NUMERICAL & STATISTICAL CALCULATIONS (NUMPY)
# ============================================================================

def calculate_itemized_costs(
    days: int,
    group_size: int,
    season: str,
    comfort_level: str,
    pricing_matrix: np.ndarray,
    categories: List[str],
    comfort_levels: List[str],
) -> Dict[str, float]:
    """
    Calculate itemized category costs using NumPy vectorized operations.

    Formula per category:
        category_cost = base_price * days * group_size * season_multiplier * discount_factor

    Parameters:
        days: Tour duration in days.
        group_size: Total number of travelers.
        season: Normalized season name ("Low", "Shoulder", "Peak").
        comfort_level: Normalized comfort level ("Budget", "Standard", "Luxury").
        pricing_matrix: 2D NumPy array of category prices (shape: N x M).
        categories: List of category names matching matrix rows.
        comfort_levels: List of comfort names matching matrix columns.

    Returns:
        Dict mapping each category name to its calculated total cost.
    """
    # Find column index for the selected comfort level
    col_idx = comfort_levels.index(comfort_level)

    # Extract 1D NumPy array of base daily rates for this comfort level
    base_prices = pricing_matrix[:, col_idx]

    # Retrieve season multiplier
    season_multiplier = SEASON_MULTIPLIERS[season]

    # Check for group discount (10% discount for groups of 5+)
    discount_multiplier = (
        (1.0 - GROUP_DISCOUNT_RATE)
        if group_size >= GROUP_DISCOUNT_THRESHOLD
        else 1.0
    )

    # NumPy vectorized calculation across all categories at once
    # base_prices is a 1D NumPy array; scalar multipliers broadcast across the array
    calculated_costs = (
        base_prices
        * days
        * group_size
        * season_multiplier
        * discount_multiplier
    )

    # Package into a clean dictionary with rounded floats
    return {
        category: round(float(cost), 2)
        for category, cost in zip(categories, calculated_costs)
    }


def calculate_historical_range(costs_array: np.ndarray) -> Dict[str, float]:
    """
    Compute statistical price percentiles from historical trip data using NumPy.

    - Low: 25th percentile
    - Typical: 50th percentile (median)
    - High: 75th percentile

    Parameters:
        costs_array: 1D NumPy array of past trip total costs.

    Returns:
        Dict with "low", "typical", and "high" cost boundaries.
    """
    if costs_array.size == 0:
        return {"low": 0.0, "typical": 0.0, "high": 0.0}

    p25 = float(np.percentile(costs_array, 25))
    p50 = float(np.percentile(costs_array, 50))
    p75 = float(np.percentile(costs_array, 75))

    return {
        "low": round(p25, 2),
        "typical": round(p50, 2),
        "high": round(p75, 2),
    }


def forecast_price_for_days(
    days: int,
    days_array: np.ndarray,
    costs_array: np.ndarray,
) -> Optional[Dict[str, Any]]:
    """
    Perform a simple linear price forecast for a given trip duration
    using numpy.polyfit and numpy.polyval.

    Model: price = slope * days + intercept

    Parameters:
        days: Trip duration to forecast.
        days_array: 1D NumPy array of historical trip days.
        costs_array: 1D NumPy array of historical trip costs.

    Returns:
        Dict with forecasted price, slope, intercept, and formula,
        or None if insufficient distinct historical durations exist.
    """
    # We require at least two distinct trip durations to fit a linear model
    unique_days = np.unique(days_array)
    if len(unique_days) < 2:
        return None

    # Fit 1st-degree polynomial (linear regression)
    # returns [slope, intercept]
    coefficients = np.polyfit(days_array, costs_array, deg=1)
    slope = float(coefficients[0])
    intercept = float(coefficients[1])

    # Evaluate polynomial at target duration
    predicted_val = float(np.polyval(coefficients, days))

    # Clamp negative prediction to zero
    forecast_price = max(0.0, round(predicted_val, 2))

    return {
        "forecast_price": forecast_price,
        "slope": round(slope, 2),
        "intercept": round(intercept, 2),
        "formula": f"price = {slope:.2f} × days + ({intercept:.2f})",
    }


# ============================================================================
# COMBINED HIGH-LEVEL ESTIMATION FUNCTION
# ============================================================================

def calculate_tour_estimate(
    days: Any,
    group_size: Any,
    season: Any,
    comfort_level: Any,
    pricing_file: Path | str = DEFAULT_PRICING_FILE,
    past_trips_file: Path | str = DEFAULT_PAST_TRIPS_FILE,
) -> Dict[str, Any]:
    """
    Master function to validate inputs, load datasets, compute itemized tour costs,
    calculate historical ranges, and generate linear price forecasts.

    Parameters:
        days: Tour duration in days.
        group_size: Number of travelers.
        season: "Low", "Shoulder", or "Peak".
        comfort_level: "Budget", "Standard", or "Luxury".
        pricing_file: Optional custom pricing CSV path.
        past_trips_file: Optional custom historical JSON path.

    Returns:
        Dictionary with complete calculation results, breakdown, and statistics.
    """
    # 1. Validate inputs
    days_val, group_val, season_val, comfort_val = validate_inputs(
        days=days,
        group_size=group_size,
        season=season,
        comfort_level=comfort_level,
    )

    # 2. Load pricing data & historical data
    pricing_matrix, categories, comfort_levels = load_pricing_data(pricing_file)
    hist_days, hist_costs = load_historical_trips(past_trips_file)

    # 3. Calculate itemized costs using NumPy
    itemized_breakdown = calculate_itemized_costs(
        days=days_val,
        group_size=group_val,
        season=season_val,
        comfort_level=comfort_val,
        pricing_matrix=pricing_matrix,
        categories=categories,
        comfort_levels=comfort_levels,
    )

    # Total trip cost is the sum of itemized costs
    total_cost = round(sum(itemized_breakdown.values()), 2)

    # Cost per person
    cost_per_person = round(total_cost / group_val, 2)

    # 4. Statistical analysis on historical trips
    historical_range = calculate_historical_range(hist_costs)

    # 5. Linear price forecast based on duration
    forecast_result = forecast_price_for_days(days_val, hist_days, hist_costs)

    is_discounted = group_val >= GROUP_DISCOUNT_THRESHOLD

    return {
        "inputs": {
            "days": days_val,
            "group_size": group_val,
            "season": season_val,
            "comfort_level": comfort_val,
            "season_multiplier": SEASON_MULTIPLIERS[season_val],
            "group_discount_applied": is_discounted,
            "group_discount_percent": int(GROUP_DISCOUNT_RATE * 100) if is_discounted else 0,
        },
        "total_cost": total_cost,
        "cost_per_person": cost_per_person,
        "itemized_breakdown": itemized_breakdown,
        "historical_price_range": historical_range,
        "forecast": forecast_result,
    }
