/**
 * Indian number formatter utilities — shared across all pages.
 * Formats numbers in the Indian numbering system (2,3-digit grouping).
 */

/**
 * Format a number as Indian currency string with ₹ prefix.
 * Examples: 150000 -> ₹1,50,000 | 10000000 -> ₹1,00,00,000
 * @param {number} num
 * @returns {string}
 */
function formatIndianCurrency(num) {
    if (num === null || num === undefined || isNaN(num)) return '₹0';
    const negative = num < 0;
    const abs = Math.abs(Math.round(num));
    const str = abs.toString();
    const lastThree = str.length > 3 ? str.substring(str.length - 3) : str;
    const otherNums = str.length > 3 ? str.substring(0, str.length - 3) : '';
    const grouped = otherNums.replace(/\B(?=(\d{2})+(?!\d))/g, ',');
    const result = (otherNums ? grouped + ',' : '') + lastThree;
    return (negative ? '-' : '') + '₹' + result;
}

/**
 * Short notation: 1,50,000 -> ₹1.5 L  | 1,00,00,000 -> ₹1 Cr
 * @param {number} num
 * @returns {string}
 */
function formatIndianShort(num) {
    if (num === null || isNaN(num)) return '₹0';
    const abs = Math.abs(num);
    const sign = num < 0 ? '-' : '';
    if (abs >= 1e7) return sign + '₹' + (abs / 1e7).toFixed(2).replace(/\.?0+$/, '') + ' Cr';
    if (abs >= 1e5) return sign + '₹' + (abs / 1e5).toFixed(2).replace(/\.?0+$/, '') + ' L';
    return sign + formatIndianCurrency(num);
}

/**
 * Apply Indian currency formatting to all .indian-currency elements on the page.
 */
function applyIndianCurrencyFormatting() {
    document.querySelectorAll('.indian-currency[data-value]').forEach(el => {
        const v = parseFloat(el.dataset.value);
        if (!isNaN(v)) el.textContent = formatIndianCurrency(v);
    });
    document.querySelectorAll('.indian-short[data-value]').forEach(el => {
        const v = parseFloat(el.dataset.value);
        if (!isNaN(v)) el.textContent = formatIndianShort(v);
    });
}

// Convenience alias used by wizard/dashboard inline scripts
const formatIN = formatIndianCurrency;
const formatINShort = formatIndianShort;

// Auto-format on input fields: type a number, get live Indian formatting shown
document.addEventListener('DOMContentLoaded', function () {
    applyIndianCurrencyFormatting();

    // Live formatting hint below currency inputs
    document.querySelectorAll('input[type="number"]').forEach(inp => {
        const hint = document.createElement('span');
        hint.style.cssText = 'font-size:0.78rem; color:#6b7280; display:block; margin-top:2px;';
        inp.parentNode.insertBefore(hint, inp.nextSibling.nextSibling || null);
        inp.addEventListener('input', () => {
            const v = parseFloat(inp.value);
            hint.textContent = isNaN(v) ? '' : '= ' + formatIndianShort(v);
        });
        // Init
        if (inp.value) inp.dispatchEvent(new Event('input'));
    });
});

window.formatIndianCurrency = formatIndianCurrency;
window.formatIndianShort = formatIndianShort;
window.formatIN = formatIN;
window.formatINShort = formatINShort;
