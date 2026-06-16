/**
 * jalali-picker.js
 * Self-contained Persian (Jalali) date picker — no dependencies.
 * Converts between Jalali and Gregorian internally.
 * Usage: attach to any <input> with data-jalali-picker attribute.
 *
 * How it works:
 *   - Shows a Jalali calendar popup to the user
 *   - Stores the selected date as Jalali in the visible input (display only)
 *   - Writes the Gregorian equivalent to a hidden input (submitted to Django)
 *
 * HTML pattern required:
 *   <input type="text"
 *          id="id_performed_at_jalali"
 *          data-jalali-picker
 *          data-target="id_performed_at"
 *          placeholder="انتخاب تاریخ"
 *          readonly>
 *   <input type="hidden" id="id_performed_at" name="performed_at">
 */

(function () {
  'use strict';

  // ── Jalali ↔ Gregorian conversion ──────────────────────────────────────────
  // Algorithm: https://www.fourmilab.ch/documents/calendar/

  // jalaaliCal: computes leap year data and the Gregorian March day of Nowruz.
  // Ported from jalaali-js (https://github.com/jalaali/jalaali-js) — the
  // standard reference implementation for Persian calendar conversions.
  function jalaaliCal(jy) {
    var breaks = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
                  1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178];
    var bl = breaks.length, gy = jy + 621, leapJ = -14;
    var jp = breaks[0], jm, jump = 0, i, n;
    for (i = 1; i < bl; i++) {
      jm = breaks[i];
      jump = jm - jp;
      if (jy < jm) break;
      leapJ += Math.floor(jump / 33) * 8 + Math.floor((jump % 33) / 4);
      jp = jm;
    }
    n = jy - jp;
    leapJ += Math.floor(n / 33) * 8 + Math.floor((n % 33 + 3) / 4);
    var leapG = Math.floor(gy / 4) - Math.floor((Math.floor(gy / 100) + 1) * 3 / 4) - 150;
    var march = 20 + leapJ - leapG;
    return { gy: gy, march: march };
  }

  function jalaaliToGregorian(jy, jm, jd) {
    // Month day-of-year offsets for Jalali months 1–12
    var monthOffsets = [0, 31, 62, 93, 124, 155, 186, 216, 246, 276, 306, 336];
    var r = jalaaliCal(jy);
    // Day offset from March 1 of the corresponding Gregorian year
    var dayFromMarch1 = r.march - 1 + monthOffsets[jm - 1] + jd - 1;
    // March 1 = day 60 in a non-leap year (Jan=31, Feb=28, Mar1=0-based day 59+1)
    // Simpler: walk forward from March 1, r.gy
    var gy = r.gy;
    // Days in months for the Gregorian year starting from March
    var isLeap = function (y) { return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0; };
    // 13 slots: Mar–Dec of gy, then Jan–Mar of gy+1.
    // We need the extra March slot because late-year Jalali dates (e.g. 12/29–30)
    // can fall in March of the following Gregorian year.
    var gMonths     = [31, 30, 31, 30, 31, 31, 30, 31, 30, 31, 31, isLeap(gy + 1) ? 29 : 28, 31];
    var gMonthNames = [3,  4,  5,  6,  7,  8,  9,  10, 11, 12, 1,  2,                         3 ];
    var gYears      = [gy, gy, gy, gy, gy, gy, gy, gy, gy, gy, gy+1, gy+1, gy+1];
    var remaining = dayFromMarch1;
    for (var i = 0; i < 13; i++) {
      if (remaining < gMonths[i]) {
        return { gy: gYears[i], gm: gMonthNames[i], gd: remaining + 1 };
      }
      remaining -= gMonths[i];
    }
    // Should never reach here for valid Jalali dates
    return { gy: gy, gm: 3, gd: 1 };
  }

  function gregorianToJalaali(gy, gm, gd) {
    var g_d_no, j_d_no, j_np, i;
    var g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    var j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29];

    gy -= 1600; gm -= 1; gd -= 1;
    g_d_no = 365 * gy + Math.floor((gy + 3) / 4) - Math.floor((gy + 99) / 100) +
             Math.floor((gy + 399) / 400);
    for (i = 0; i < gm; ++i) g_d_no += g_days_in_month[i];
    if (gm > 1 && ((gy + 1600) % 4 === 0 && ((gy + 1600) % 100 !== 0 ||
        (gy + 1600) % 400 === 0))) g_d_no++;
    g_d_no += gd;

    j_d_no = g_d_no - 79;
    j_np = Math.floor(j_d_no / 12053);
    j_d_no %= 12053;
    var jy = 979 + 33 * j_np + 4 * Math.floor(j_d_no / 1461);
    j_d_no %= 1461;
    if (j_d_no >= 366) { jy += Math.floor((j_d_no - 1) / 365); j_d_no = (j_d_no - 1) % 365; }
    for (i = 0; i < 11 && j_d_no >= j_days_in_month[i]; ++i) j_d_no -= j_days_in_month[i];
    var jm = i + 1, jd = j_d_no + 1;
    return { jy: jy, jm: jm, jd: jd };
  }

  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  function toJalaliStr(gy, gm, gd) {
    var j = gregorianToJalaali(gy, gm, gd);
    return j.jy + '/' + pad(j.jm) + '/' + pad(j.jd);
  }

  function toGregorianStr(jy, jm, jd) {
    var g = jalaaliToGregorian(jy, jm, jd);
    return g.gy + '-' + pad(g.gm) + '-' + pad(g.gd);
  }

  // ── Persian number & month names ──────────────────────────────────────────
  var JALALI_MONTHS = [
    'فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور',
    'مهر','آبان','آذر','دی','بهمن','اسفند'
  ];
  var WEEKDAYS = ['ش','ی','د','س','چ','پ','ج'];

  function jalaaliDaysInMonth(jy, jm) {
    if (jm <= 6) return 31;
    if (jm <= 11) return 30;
    // Esfand: 29 or 30
    var g = jalaaliToGregorian(jy, 12, 29);
    var leap = (g.gy % 4 === 0 && g.gy % 100 !== 0) || g.gy % 400 === 0;
    return leap ? 30 : 29;
  }

  // Day of week for first day of Jalali month (0=Shanbe, 6=Jome)
  function firstDayOfWeek(jy, jm) {
    var g = jalaaliToGregorian(jy, jm, 1);
    var date = new Date(g.gy, g.gm - 1, g.gd);
    // JS: 0=Sun,1=Mon,...,6=Sat  → Persian week: Sat=0
    var dow = date.getDay(); // 0-6
    return (dow + 1) % 7; // Sat=0, Sun=1, Mon=2, ..., Fri=6
  }

  // ── DOM helpers ───────────────────────────────────────────────────────────
  function el(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt !== undefined) e.textContent = txt;
    return e;
  }

  // ── Picker factory ────────────────────────────────────────────────────────
  function createPicker(inputEl, hiddenEl) {
    var today = gregorianToJalaali(
      new Date().getFullYear(), new Date().getMonth() + 1, new Date().getDate()
    );
    var viewJy = today.jy, viewJm = today.jm;
    var selectedJy = null, selectedJm = null, selectedJd = null;

    // If hidden already has a value (edit form), pre-select it
    if (hiddenEl.value) {
      var parts = hiddenEl.value.split('-');
      if (parts.length === 3) {
        var j = gregorianToJalaali(+parts[0], +parts[1], +parts[2]);
        selectedJy = j.jy; selectedJm = j.jm; selectedJd = j.jd;
        viewJy = selectedJy; viewJm = selectedJm;
        inputEl.value = selectedJy + '/' + pad(selectedJm) + '/' + pad(selectedJd);
      }
    }

    // ── Popup element ────────────────────────────────────────────────
    var popup = el('div', 'jp-popup');
    popup.setAttribute('dir', 'rtl');
    popup.style.cssText = [
      'display:none',
      'position:absolute',
      'z-index:9999',
      'background:var(--surface)',
      'border:1px solid var(--border)',
      'border-radius:var(--radius-lg)',
      'box-shadow:0 8px 32px rgba(0,0,0,.5)',
      'padding:0',
      'width:272px',
      'font-family:Vazirmatn,system-ui,sans-serif',
      'font-size:13px',
      'color:var(--text)',
      'user-select:none',
    ].join(';');
    document.body.appendChild(popup);

    function render() {
      popup.innerHTML = '';

      // Header
      var header = el('div');
      header.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:12px 14px 8px;border-bottom:1px solid var(--border); flex-direction:row-reverse;';

      var btnPrev = el('button', '', '›');
      btnPrev.type = 'button';
      btnPrev.style.cssText = 'background:none;border:1px solid var(--border);border-radius:var(--radius);color:var(--text-muted);cursor:pointer;padding:2px 8px;font-size:16px;line-height:1.4;';
      btnPrev.title = 'ماه بعد';

      var btnNext = el('button', '', '‹');
      btnNext.type = 'button';
      btnNext.style.cssText = btnPrev.style.cssText;
      btnNext.title = 'ماه قبل';

      var title = el('span', '', JALALI_MONTHS[viewJm - 1] + ' ' + viewJy);
      title.style.cssText = 'font-weight:700;color:var(--text);font-size:14px;';

      // RTL: "next" visually is on the right (‹), previous is on the left (›)
      btnPrev.addEventListener('click', function () {
        event.stopPropagation();
        viewJm++;
        if (viewJm > 12) { viewJm = 1; viewJy++; }
        render();
      });
      btnNext.addEventListener('click', function () {
        event.stopPropagation();
        viewJm--;
        if (viewJm < 1) { viewJm = 12; viewJy--; }
        render();
      });

      header.appendChild(btnPrev);
      header.appendChild(title);
      header.appendChild(btnNext);
      popup.appendChild(header);

      // Weekday row
      var wdRow = el('div');
      wdRow.style.cssText = 'display:grid;grid-template-columns:repeat(7,1fr);padding:6px 8px 2px;';
      WEEKDAYS.forEach(function (wd) {
        var d = el('div', '', wd);
        d.style.cssText = 'text-align:center;font-size:11px;color:var(--text-dim);font-weight:600;padding:3px 0;';
        wdRow.appendChild(d);
      });
      popup.appendChild(wdRow);

      // Days grid
      var grid = el('div');
      grid.style.cssText = 'display:grid;grid-template-columns:repeat(7,1fr);padding:4px 8px 10px;gap:2px;';

      var firstDow = firstDayOfWeek(viewJy, viewJm); // 0=Sat
      var daysInMonth = jalaaliDaysInMonth(viewJy, viewJm);

      // Empty cells before first day
      for (var e = 0; e < firstDow; e++) {
        grid.appendChild(el('div'));
      }

      for (var d = 1; d <= daysInMonth; d++) {
        (function (day) {
          var cell = el('button', '', '' + day);
          cell.type = 'button';
          var isToday = (viewJy === today.jy && viewJm === today.jm && day === today.jd);
          var isSelected = (selectedJy === viewJy && selectedJm === viewJm && selectedJd === day);
          cell.style.cssText = [
            'background:' + (isSelected ? 'var(--green)' : isToday ? 'var(--green-dim)' : 'none'),
            'border:1px solid ' + (isSelected ? 'var(--green)' : isToday ? 'var(--green)' : 'transparent'),
            'border-radius:var(--radius)',
            'color:' + (isSelected ? '#0d1117' : isToday ? 'var(--green)' : 'var(--text)'),
            'cursor:pointer',
            'font-family:Vazirmatn,system-ui,sans-serif',
            'font-size:12px',
            'font-weight:' + (isSelected || isToday ? '700' : '400'),
            'padding:5px 2px',
            'text-align:center',
            'transition:background .12s,color .12s',
          ].join(';');

          cell.addEventListener('mouseenter', function () {
            if (!isSelected) {
              cell.style.background = 'var(--surface-2)';
              cell.style.borderColor = 'var(--border)';
            }
          });
          cell.addEventListener('mouseleave', function () {
            if (!isSelected) {
              cell.style.background = 'none';
              cell.style.borderColor = 'transparent';
            }
          });

          cell.addEventListener('click', function () {
            selectedJy = viewJy; selectedJm = viewJm; selectedJd = day;
            // Set visible input
            inputEl.value = selectedJy + '/' + pad(selectedJm) + '/' + pad(selectedJd);
            // Set hidden Gregorian input for Django
            hiddenEl.value = toGregorianStr(selectedJy, selectedJm, selectedJd);
            // Trigger change event so other JS can react
            hiddenEl.dispatchEvent(new Event('change'));
            closePopup();
          });

          grid.appendChild(cell);
        })(d);
      }
      popup.appendChild(grid);

      // Today button
      var footer = el('div');
      footer.style.cssText = 'padding:8px 14px 10px;border-top:1px solid var(--border);display:flex;justify-content:center;';
      var todayBtn = el('button', '', 'امروز');
      todayBtn.type = 'button';
      todayBtn.style.cssText = 'background:none;border:1px solid var(--border);border-radius:var(--radius);color:var(--text-muted);cursor:pointer;padding:4px 16px;font-family:Vazirmatn,sans-serif;font-size:12px;transition:all .12s;';
      todayBtn.addEventListener('mouseenter', function () {
        todayBtn.style.borderColor = 'var(--green)';
        todayBtn.style.color = 'var(--green)';
      });
      todayBtn.addEventListener('mouseleave', function () {
        todayBtn.style.borderColor = 'var(--border)';
        todayBtn.style.color = 'var(--text-muted)';
      });
      todayBtn.addEventListener('click', function () {
        selectedJy = today.jy; selectedJm = today.jm; selectedJd = today.jd;
        viewJy = today.jy; viewJm = today.jm;
        inputEl.value = selectedJy + '/' + pad(selectedJm) + '/' + pad(selectedJd);
        hiddenEl.value = toGregorianStr(selectedJy, selectedJm, selectedJd);
        hiddenEl.dispatchEvent(new Event('change'));
        closePopup();
      });
      footer.appendChild(todayBtn);
      popup.appendChild(footer);
    }

    function positionPopup() {
      var rect = inputEl.getBoundingClientRect();
      var scrollY = window.scrollY || document.documentElement.scrollTop;
      var scrollX = window.scrollX || document.documentElement.scrollLeft;
      popup.style.top = (rect.bottom + scrollY + 4) + 'px';
      // RTL: align popup to the right edge of the input
      var rightEdge = window.innerWidth - rect.right + scrollX;
      popup.style.right = rightEdge + 'px';
      popup.style.left = 'auto';
    }

    function openPopup() {
      render();
      popup.style.display = 'block';
      positionPopup();
    }

    function closePopup() {
      popup.style.display = 'none';
    }

    inputEl.addEventListener('click', function (e) {
      e.stopPropagation();
      if (popup.style.display === 'none') {
        openPopup();
      } else {
        closePopup();
      }
    });

    inputEl.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closePopup();
    });

    // Close when clicking outside
    document.addEventListener('click', function (e) {
      if (!popup.contains(e.target) && e.target !== inputEl) {
        closePopup();
      }
    });

    // Reposition on scroll/resize
    window.addEventListener('resize', function () {
      if (popup.style.display !== 'none') positionPopup();
    });
  }

  // ── Auto-init: find all inputs with data-jalali-picker ────────────────────
  function init() {
    var inputs = document.querySelectorAll('[data-jalali-picker]');
    inputs.forEach(function (input) {
      var targetId = input.getAttribute('data-target');
      if (!targetId) { console.warn('jalali-picker: missing data-target on', input); return; }
      var hiddenInput = document.getElementById(targetId);
      if (!hiddenInput) { console.warn('jalali-picker: hidden input #' + targetId + ' not found'); return; }
      createPicker(input, hiddenInput);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();