/**
 * Tour Cost Estimator - Frontend Enhancement Script
 * ==================================================
 * Handles client-side validation, submit button loading states,
 * and quick-fill presets.
 * 
 * Note: Server-side validation and Python/NumPy calculations
 * remain authoritative at all times.
 */

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('tourEstimatorForm');
    if (!form) return;

    const daysInput = document.getElementById('days');
    const groupSizeInput = document.getElementById('group_size');
    const seasonSelect = document.getElementById('season');
    const comfortSelect = document.getElementById('comfort_level');
    const submitBtn = document.getElementById('submitBtn');
    const loadingSpinner = document.getElementById('loadingSpinner');
    const btnText = submitBtn ? submitBtn.querySelector('.btn-text') : null;

    const daysError = document.getElementById('daysError');
    const groupSizeError = document.getElementById('groupSizeError');
    const seasonError = document.getElementById('seasonError');
    const comfortError = document.getElementById('comfortError');

    // Live validation triggers on input
    if (daysInput) {
        daysInput.addEventListener('input', () => validateDaysField());
    }
    if (groupSizeInput) {
        groupSizeInput.addEventListener('input', () => validateGroupSizeField());
    }
    if (seasonSelect) {
        seasonSelect.addEventListener('change', () => validateSeasonField());
    }
    if (comfortSelect) {
        comfortSelect.addEventListener('change', () => validateComfortField());
    }

    // Form submission validation
    form.addEventListener('submit', (e) => {
        const isDaysValid = validateDaysField();
        const isGroupValid = validateGroupSizeField();
        const isSeasonValid = validateSeasonField();
        const isComfortValid = validateComfortField();

        if (!isDaysValid || !isGroupValid || !isSeasonValid || !isComfortValid) {
            e.preventDefault();
            return;
        }

        // Visual loading state
        if (submitBtn) {
            submitBtn.disabled = true;
            if (loadingSpinner) loadingSpinner.classList.remove('hidden');
            if (btnText) btnText.textContent = 'Calculating with NumPy...';
        }
    });

    function validateDaysField() {
        if (!daysInput || !daysError) return true;
        const val = daysInput.value.trim();

        if (!val) {
            setError(daysInput, daysError, 'Number of days is required.');
            return false;
        }

        const num = Number(val);
        if (!Number.isInteger(num) || num <= 0) {
            setError(daysInput, daysError, 'Please enter a positive whole number (e.g. 1, 3, 7).');
            return false;
        }

        clearError(daysInput, daysError);
        return true;
    }

    function validateGroupSizeField() {
        if (!groupSizeInput || !groupSizeError) return true;
        const val = groupSizeInput.value.trim();

        if (!val) {
            setError(groupSizeInput, groupSizeError, 'Group size is required.');
            return false;
        }

        const num = Number(val);
        if (!Number.isInteger(num) || num <= 0) {
            setError(groupSizeInput, groupSizeError, 'Please enter a positive whole number (e.g. 1, 2, 4).');
            return false;
        }

        clearError(groupSizeInput, groupSizeError);
        return true;
    }

    function validateSeasonField() {
        if (!seasonSelect || !seasonError) return true;
        if (!seasonSelect.value) {
            setError(seasonSelect, seasonError, 'Please select a travel season.');
            return false;
        }
        clearError(seasonSelect, seasonError);
        return true;
    }

    function validateComfortField() {
        if (!comfortSelect || !comfortError) return true;
        if (!comfortSelect.value) {
            setError(comfortSelect, comfortError, 'Please select a comfort level.');
            return false;
        }
        clearError(comfortSelect, comfortError);
        return true;
    }

    function setError(inputElem, errorElem, message) {
        inputElem.classList.add('is-invalid');
        errorElem.textContent = message;
    }

    function clearError(inputElem, errorElem) {
        inputElem.classList.remove('is-invalid');
        errorElem.textContent = '';
    }
});

/**
 * Apply quick test presets to the form fields.
 */
function applyPreset(days, groupSize, season, comfort) {
    const daysInput = document.getElementById('days');
    const groupSizeInput = document.getElementById('group_size');
    const seasonSelect = document.getElementById('season');
    const comfortSelect = document.getElementById('comfort_level');

    if (daysInput) daysInput.value = days;
    if (groupSizeInput) groupSizeInput.value = groupSize;
    if (seasonSelect) seasonSelect.value = season;
    if (comfortSelect) comfortSelect.value = comfort;

    // Clear any previous error states
    document.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
    document.querySelectorAll('.field-error').forEach(el => el.textContent = '');
}
