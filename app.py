"""
Tour Cost Estimator - Flask Web Application
===========================================
This module serves the web application and JSON API for the Tour Cost Estimator.
All numerical calculations, statistics, and forecasts are delegated to calculator.py.

Routes:
- GET  /              : Render calculator form (index.html)
- POST /              : Process form data and render calculation result (result.html)
- POST /result        : Alias for POST / to ensure template & form compatibility
- POST /api/estimate  : JSON API endpoint for programmatic tour cost estimates

Run locally with:
    python app.py
"""

from typing import Dict, Any
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash

from calculator import (
    calculate_tour_estimate,
    CalculatorError,
    CalculatorInputError,
    CalculatorDataError,
    SEASON_MULTIPLIERS,
    EXPECTED_COMFORT_LEVELS,
)

# Initialize Flask application
app = Flask(__name__)
# Secret key for session/flash messages
app.config["SECRET_KEY"] = "tour-cost-estimator-secret-key-2026"
# Limit max content length (e.g. 1MB) to prevent oversized payloads
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024


# ============================================================================
# WEB ROUTES
# ============================================================================

@app.route("/", methods=["GET", "POST"])
def index():
    """
    Handle the main calculator page.
    - GET: Displays the input form with available season and comfort options.
    - POST: Validates input, calculates costs, and renders the result page.
    """
    if request.method == "POST":
        return handle_form_submission()

    # GET request - render blank calculator form
    return render_template(
        "index.html",
        seasons=list(SEASON_MULTIPLIERS.keys()),
        comfort_levels=EXPECTED_COMFORT_LEVELS,
        form_data={},
    )


@app.route("/result", methods=["POST"])
def result_page():
    """
    Alternative endpoint for form submission to support explicit /result actions.
    """
    return handle_form_submission()


def handle_form_submission():
    """
    Extract form fields, execute calculations via calculator.py,
    and render the result page or return to the form with error messages.
    """
    # Extract raw form inputs
    raw_days = request.form.get("days", "").strip()
    raw_group_size = request.form.get("group_size", "").strip()
    raw_season = request.form.get("season", "").strip()
    raw_comfort_level = request.form.get("comfort_level", "").strip()

    form_data = {
        "days": raw_days,
        "group_size": raw_group_size,
        "season": raw_season,
        "comfort_level": raw_comfort_level,
    }

    try:
        # Delegate complete calculation to calculator module
        estimate_result = calculate_tour_estimate(
            days=raw_days,
            group_size=raw_group_size,
            season=raw_season,
            comfort_level=raw_comfort_level,
        )

        return render_template(
            "result.html",
            estimate=estimate_result,
        )

    except CalculatorInputError as err:
        flash(str(err), category="danger")
        return render_template(
            "index.html",
            seasons=list(SEASON_MULTIPLIERS.keys()),
            comfort_levels=EXPECTED_COMFORT_LEVELS,
            form_data=form_data,
        ), 400

    except CalculatorDataError as err:
        flash(f"System Data Error: {err}", category="danger")
        return render_template(
            "index.html",
            seasons=list(SEASON_MULTIPLIERS.keys()),
            comfort_levels=EXPECTED_COMFORT_LEVELS,
            form_data=form_data,
        ), 500

    except Exception as err:
        flash(f"An unexpected error occurred while calculating: {err}", category="danger")
        return render_template(
            "index.html",
            seasons=list(SEASON_MULTIPLIERS.keys()),
            comfort_levels=EXPECTED_COMFORT_LEVELS,
            form_data=form_data,
        ), 500


# ============================================================================
# JSON API ENDPOINT
# ============================================================================

@app.route("/api/estimate", methods=["POST"])
def api_estimate():
    """
    JSON API endpoint for tour cost estimation.

    Accepts:
        Content-Type: application/json
        {
            "days": 5,
            "group_size": 4,
            "season": "Peak",
            "comfort_level": "Standard"
        }

    Returns:
        JSON response with total cost, cost per person, itemized breakdown,
        historical range, and price forecast.
    """
    if not request.is_json:
        return jsonify({
            "status": "error",
            "message": "Request must be JSON with Content-Type: application/json.",
        }), 415

    payload = request.get_json(silent=True)
    if payload is None or not isinstance(payload, dict):
        return jsonify({
            "status": "error",
            "message": "Malformed JSON payload in request body.",
        }), 400

    days = payload.get("days")
    group_size = payload.get("group_size")
    season = payload.get("season")
    comfort_level = payload.get("comfort_level")

    try:
        result = calculate_tour_estimate(
            days=days,
            group_size=group_size,
            season=season,
            comfort_level=comfort_level,
        )
        return jsonify({
            "status": "success",
            "data": result,
        }), 200

    except CalculatorInputError as err:
        return jsonify({
            "status": "error",
            "error_type": "InputValidationError",
            "message": str(err),
        }), 400

    except CalculatorDataError as err:
        return jsonify({
            "status": "error",
            "error_type": "DataStorageError",
            "message": str(err),
        }), 500

    except Exception as err:
        return jsonify({
            "status": "error",
            "error_type": "InternalServerError",
            "message": f"Unexpected server error: {err}",
        }), 500


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def handle_404(err):
    """Handle page not found errors."""
    if request.path.startswith("/api/"):
        return jsonify({
            "status": "error",
            "message": "API endpoint not found.",
        }), 404
    return render_template(
        "base.html",
        custom_content="<div class='card error-card'><h2>404 - Page Not Found</h2><p>The page you requested does not exist.</p><a href='/' class='btn btn-primary'>Return Home</a></div>",
    ), 404


@app.errorhandler(413)
def handle_413(err):
    """Handle payload too large."""
    if request.path.startswith("/api/"):
        return jsonify({
            "status": "error",
            "message": "Request payload exceeds allowed limit.",
        }), 413
    flash("The submitted request is too large.", category="danger")
    return redirect(url_for("index"))


@app.errorhandler(500)
def handle_500(err):
    """Handle unexpected server errors."""
    if request.path.startswith("/api/"):
        return jsonify({
            "status": "error",
            "message": "Internal server error.",
        }), 500
    flash("An unexpected server error occurred. Please try again.", category="danger")
    return redirect(url_for("index"))


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )
