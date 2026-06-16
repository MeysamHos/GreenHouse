/**
 * jalali-picker.js
 * Self-contained Persian (Jalali) date picker — no dependencies.
 *
 * HTML pattern:
 *   <input type="text" id="X_jalali" data-jalali-picker data-target="X"
 *          placeholder="انتخاب تاریخ" autocomplete="off" readonly>
 *   <input type="hidden" id="X" name="field_name" value="">
 */

(function () {
  'use strict';

  // ── Jalali ↔ Gregorian ────────────────────────────────────────────────────

  function jalaaliCal(jy) {
    var breaks = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
                  1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178];
    var bl = breaks.length, gy = jy + 621, leapJ = -14;
    var jp = breaks[0], jm, jump = 0, i, n;
    for (i = 1; i < bl; i++) {
      jm = breaks[i]; jump = jm - jp;
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
    var monthOffsets = [0, 31, 62, 93, 124, 155, 186, 216, 246, 276, 306, 336];
    var r = jalaaliCal(jy);
    var dayFromMarch1 = r.march - 1 + monthOffsets[jm - 1] + jd - 1;
    var gy = r.gy;
    var isLeap = function (y) { return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0; };
    var gMonths     = [31, 30, 31, 30, 31, 31, 30, 31, 30, 31, 31, isLeap(gy + 1) ? 29 : 28, 31];
    var gMonthNames = [3,   4,  5,  6,  7,  8,  9, 10, 11, 12,  1,  2,                        3];
    var gYears      = [gy, gy, gy, gy, gy, gy, gy, gy, gy, gy, gy+1, gy+1, gy+1];
    var remaining = dayFromMarch1;
    for (var i = 0; i < 13; i++) {
      if (remaining < gMonths[i]) return { gy: gYears[i], gm: gMonthNames[i], gd: remaining + 1 };
      remaining -= gMonths[i];
    }
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
    return { jy: jy, jm: i + 1, jd: j_d_no + 1 };
  }

  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  function toGregorianStr(jy, jm, jd) {
    var g = jalaaliToGregorian(jy, jm, jd);
    return g.gy + '-' + pad(g.gm) + '-' + pad(g.gd);
  }

  // ── Constants ─────────────────────────────────────────────────────────────

  var JALALI_MONTHS = [
    'فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور',
    'مهر','آبان','آذر','دی','بهمن','اسفند'
  ];
  var WEEKDAYS = ['ش','ی','د','س','چ','پ','ج'];

  function jalaaliDaysInMonth(jy, jm) {
    if (jm <= 6) return 31;
    if (jm <= 11) return 30;
    var g = jalaaliToGregorian(jy, 12, 29);
    return ((g.gy % 4 === 0 && g.gy % 100 !== 0) || g.gy % 400 === 0) ? 30 : 29;
  }

  function firstDayOfWeek(jy, jm) {
    var g = jalaaliToGregorian(jy, jm, 1);
    var dow = new Date(g.gy, g.gm - 1, g.gd).getDay();
    return (dow + 1) % 7; // Sat=0 … Fri=6
  }

  // ── Shared styles ─────────────────────────────────────────────────────────

  var BTN = 'background:none;border:1px solid var(--border);border-radius:var(--radius);' +
            'color:var(--text-muted);cursor:pointer;padding:2px 8px;font-size:16px;line-height:1.4;';

  function makeEl(tag, css, txt) {
    var e = document.createElement(tag);
    if (css) e.style.cssText = css;
    if (txt !== undefined) e.textContent = txt;
    return e;
  }

  function hoverGreen(el) {
    el.addEventListener('mouseenter', function () {
      el.style.borderColor = 'var(--green)'; el.style.color = 'var(--green)';
    });
    el.addEventListener('mouseleave', function () {
      el.style.borderColor = 'var(--border)'; el.style.color = 'var(--text-muted)';
    });
  }

  // ── Picker ────────────────────────────────────────────────────────────────

  function createPicker(inputEl, hiddenEl) {
    var today = gregorianToJalaali(
      new Date().getFullYear(), new Date().getMonth() + 1, new Date().getDate()
    );
    var viewJy = today.jy, viewJm = today.jm;
    var selJy = null, selJm = null, selJd = null;

    // 'day' | 'month' | 'year'
    var mode = 'day';

    // Pre-select on edit form
    if (hiddenEl.value) {
      var parts = hiddenEl.value.split('-');
      if (parts.length === 3) {
        var j = gregorianToJalaali(+parts[0], +parts[1], +parts[2]);
        selJy = j.jy; selJm = j.jm; selJd = j.jd;
        viewJy = selJy; viewJm = selJm;
        inputEl.value = selJy + '/' + pad(selJm) + '/' + pad(selJd);
      }
    }

    // Popup container
    var popup = makeEl('div', [
      'display:none', 'position:absolute', 'z-index:9999',
      'background:var(--surface)', 'border:1px solid var(--border)',
      'border-radius:var(--radius-lg)', 'box-shadow:0 8px 32px rgba(0,0,0,.5)',
      'width:272px', 'font-family:Vazirmatn,system-ui,sans-serif',
      'font-size:13px', 'color:var(--text)', 'user-select:none',
    ].join(';'));
    popup.setAttribute('dir', 'rtl');
    document.body.appendChild(popup);

    // ── Render header (shared by all modes) ───────────────────────────────
    function renderHeader(titleText, onPrev, onNext) {
      var header = makeEl('div',
        'display:flex;align-items:center;justify-content:space-between;' +
        'padding:12px 14px 8px;border-bottom:1px solid var(--border); flex-direction:row-reverse;'
      );

      var btnPrev = makeEl('button', BTN, '›');
      btnPrev.type = 'button'; btnPrev.title = 'بعدی';
      btnPrev.addEventListener('click', function (e) { e.stopPropagation(); onPrev(); });

      var btnNext = makeEl('button', BTN, '‹');
      btnNext.type = 'button'; btnNext.title = 'قبلی';
      btnNext.addEventListener('click', function (e) { e.stopPropagation(); onNext(); });

      var titleEl = makeEl('button',
        'background:none;border:none;cursor:pointer;font-weight:700;' +
        'color:var(--text);font-size:14px;font-family:Vazirmatn,sans-serif;' +
        'padding:2px 8px;border-radius:var(--radius);transition:background .12s;',
        titleText
      );
      titleEl.type = 'button';
      titleEl.addEventListener('mouseenter', function () { titleEl.style.background = 'var(--surface-2)'; });
      titleEl.addEventListener('mouseleave', function () { titleEl.style.background = 'none'; });
      titleEl.addEventListener('click', function (e) {
        e.stopPropagation();
        // Cycle: day → month → year → day
        if (mode === 'day')   { mode = 'month'; render(); }
        else if (mode === 'month') { mode = 'year';  render(); }
        else                  { mode = 'day';   render(); }
      });

      header.appendChild(btnPrev);
      header.appendChild(titleEl);
      header.appendChild(btnNext);
      return header;
    }

    // ── Day view ──────────────────────────────────────────────────────────
    function renderDayView() {
      popup.innerHTML = '';

      popup.appendChild(renderHeader(
        JALALI_MONTHS[viewJm - 1] + ' ' + viewJy,
        function () { viewJm++; if (viewJm > 12) { viewJm = 1; viewJy++; } render(); },
        function () { viewJm--; if (viewJm < 1) { viewJm = 12; viewJy--; } render(); }
      ));

      // Weekday labels
      var wdRow = makeEl('div', 'display:grid;grid-template-columns:repeat(7,1fr);padding:6px 8px 2px;');
      WEEKDAYS.forEach(function (wd) {
        wdRow.appendChild(makeEl('div',
          'text-align:center;font-size:11px;color:var(--text-dim);font-weight:600;padding:3px 0;', wd));
      });
      popup.appendChild(wdRow);

      // Days grid
      var grid = makeEl('div', 'display:grid;grid-template-columns:repeat(7,1fr);padding:4px 8px 10px;gap:2px;');
      var firstDow   = firstDayOfWeek(viewJy, viewJm);
      var daysInMonth = jalaaliDaysInMonth(viewJy, viewJm);

      for (var e = 0; e < firstDow; e++) grid.appendChild(makeEl('div'));

      for (var d = 1; d <= daysInMonth; d++) {
        (function (day) {
          var isToday = (viewJy === today.jy && viewJm === today.jm && day === today.jd);
          var isSel   = (selJy === viewJy && selJm === viewJm && selJd === day);
          var cell = makeEl('button',
            'background:' + (isSel ? 'var(--green)' : 'none') + ';' +
            'border:1px solid ' + (isSel ? 'var(--green)' : isToday ? 'var(--green)' : 'transparent') + ';' +
            'border-radius:var(--radius);' +
            'color:' + (isSel ? '#0d1117' : isToday ? 'var(--green)' : 'var(--text)') + ';' +
            'cursor:pointer;font-family:Vazirmatn,system-ui,sans-serif;font-size:12px;' +
            'font-weight:' + (isSel || isToday ? '700' : '400') + ';' +
            'padding:5px 2px;text-align:center;transition:background .12s,color .12s;',
            String(day)
          );
          cell.type = 'button';
          cell.addEventListener('mouseenter', function () {
            if (!isSel) { cell.style.background = 'var(--surface-2)'; cell.style.borderColor = 'var(--border)'; }
          });
          cell.addEventListener('mouseleave', function () {
            if (!isSel) { cell.style.background = 'none'; cell.style.borderColor = isToday ? 'var(--green)' : 'transparent'; }
          });
          cell.addEventListener('click', function (e) {
            e.stopPropagation();
            selJy = viewJy; selJm = viewJm; selJd = day;
            inputEl.value  = selJy + '/' + pad(selJm) + '/' + pad(selJd);
            hiddenEl.value = toGregorianStr(selJy, selJm, selJd);
            hiddenEl.dispatchEvent(new Event('change'));
            closePopup();
          });
          grid.appendChild(cell);
        })(d);
      }
      popup.appendChild(grid);

      // Footer — today button
      var footer = makeEl('div', 'padding:8px 14px 10px;border-top:1px solid var(--border);display:flex;justify-content:center;');
      var todayBtn = makeEl('button',
        'background:none;border:1px solid var(--border);border-radius:var(--radius);' +
        'color:var(--text-muted);cursor:pointer;padding:4px 16px;' +
        'font-family:Vazirmatn,sans-serif;font-size:12px;transition:all .12s;',
        'امروز'
      );
      todayBtn.type = 'button';
      hoverGreen(todayBtn);
      todayBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        selJy = today.jy; selJm = today.jm; selJd = today.jd;
        viewJy = today.jy; viewJm = today.jm;
        inputEl.value  = selJy + '/' + pad(selJm) + '/' + pad(selJd);
        hiddenEl.value = toGregorianStr(selJy, selJm, selJd);
        hiddenEl.dispatchEvent(new Event('change'));
        closePopup();
      });
      footer.appendChild(todayBtn);
      popup.appendChild(footer);
    }

    // ── Month view ────────────────────────────────────────────────────────
    function renderMonthView() {
      popup.innerHTML = '';

      popup.appendChild(renderHeader(
        String(viewJy),
        function () { viewJy++; render(); },
        function () { viewJy--; render(); }
      ));

      var grid = makeEl('div',
        'display:grid;grid-template-columns:repeat(3,1fr);gap:6px;padding:12px;'
      );
      JALALI_MONTHS.forEach(function (name, idx) {
        var m = idx + 1;
        var isCurrent = (viewJm === m && viewJy === today.jy) ||
                        (selJm === m && selJy === viewJy);
        var isSelMonth = (selJm === m && selJy === viewJy);
        var cell = makeEl('button',
          'background:' + (isSelMonth ? 'var(--green)' : 'none') + ';' +
          'border:1px solid ' + (isSelMonth ? 'var(--green)' : isCurrent ? 'var(--green)' : 'var(--border)') + ';' +
          'border-radius:var(--radius);' +
          'color:' + (isSelMonth ? '#0d1117' : isCurrent ? 'var(--green)' : 'var(--text)') + ';' +
          'cursor:pointer;font-family:Vazirmatn,sans-serif;font-size:12px;' +
          'font-weight:' + (isSelMonth ? '700' : '400') + ';' +
          'padding:8px 4px;text-align:center;transition:all .12s;',
          name
        );
        cell.type = 'button';
        cell.addEventListener('mouseenter', function () {
          if (!isSelMonth) { cell.style.background = 'var(--surface-2)'; }
        });
        cell.addEventListener('mouseleave', function () {
          if (!isSelMonth) { cell.style.background = 'none'; }
        });
        cell.addEventListener('click', function (e) {
          e.stopPropagation();
          viewJm = m;
          mode = 'day';
          render();
        });
        grid.appendChild(cell);
      });
      popup.appendChild(grid);
    }

    // ── Year view ─────────────────────────────────────────────────────────
    // Show a range of 12 years centered around viewJy
    var yearRangeStart = viewJy - 5;

    function renderYearView() {
      popup.innerHTML = '';

      var rangeEnd = yearRangeStart + 11;
      popup.appendChild(renderHeader(
        yearRangeStart + ' – ' + rangeEnd,
        function () { yearRangeStart += 12; render(); },
        function () { yearRangeStart -= 12; render(); }
      ));

      var grid = makeEl('div',
        'display:grid;grid-template-columns:repeat(3,1fr);gap:6px;padding:12px;'
      );
      for (var y = yearRangeStart; y <= rangeEnd; y++) {
        (function (year) {
          var isSelYear = (selJy === year);
          var isThisYear = (year === today.jy);
          var cell = makeEl('button',
            'background:' + (isSelYear ? 'var(--green)' : 'none') + ';' +
            'border:1px solid ' + (isSelYear ? 'var(--green)' : isThisYear ? 'var(--green)' : 'var(--border)') + ';' +
            'border-radius:var(--radius);' +
            'color:' + (isSelYear ? '#0d1117' : isThisYear ? 'var(--green)' : 'var(--text)') + ';' +
            'cursor:pointer;font-family:Vazirmatn,sans-serif;font-size:12px;' +
            'font-weight:' + (isSelYear ? '700' : '400') + ';' +
            'padding:8px 4px;text-align:center;transition:all .12s;',
            String(year)
          );
          cell.type = 'button';
          cell.addEventListener('mouseenter', function () {
            if (!isSelYear) { cell.style.background = 'var(--surface-2)'; }
          });
          cell.addEventListener('mouseleave', function () {
            if (!isSelYear) { cell.style.background = 'none'; }
          });
          cell.addEventListener('click', function (e) {
            e.stopPropagation();
            viewJy = year;
            yearRangeStart = year - 5;
            mode = 'month';
            render();
          });
          grid.appendChild(cell);
        })(y);
      }
      popup.appendChild(grid);
    }

    // ── Main render dispatcher ────────────────────────────────────────────
    function render() {
      if (mode === 'day')   renderDayView();
      else if (mode === 'month') renderMonthView();
      else                  renderYearView();
    }

    // ── Position & open/close ─────────────────────────────────────────────
    function positionPopup() {
      var rect = inputEl.getBoundingClientRect();
      var scrollY = window.scrollY || document.documentElement.scrollTop;
      var scrollX = window.scrollX || document.documentElement.scrollLeft;
      popup.style.top = (rect.bottom + scrollY + 4) + 'px';
      popup.style.right = (window.innerWidth - rect.right + scrollX) + 'px';
      popup.style.left = 'auto';
    }

    function openPopup() {
      mode = 'day';
      yearRangeStart = viewJy - 5;
      render();
      popup.style.display = 'block';
      positionPopup();
    }

    function closePopup() {
      popup.style.display = 'none';
    }

    inputEl.addEventListener('click', function (e) {
      e.stopPropagation();
      popup.style.display === 'none' ? openPopup() : closePopup();
    });
    inputEl.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closePopup();
    });
    document.addEventListener('click', function (e) {
      if (!popup.contains(e.target) && e.target !== inputEl) closePopup();
    });
    window.addEventListener('resize', function () {
      if (popup.style.display !== 'none') positionPopup();
    });
  }

  // ── Auto-init ─────────────────────────────────────────────────────────────
  function init() {
    document.querySelectorAll('[data-jalali-picker]').forEach(function (input) {
      var targetId = input.getAttribute('data-target');
      if (!targetId) return;
      var hiddenInput = document.getElementById(targetId);
      if (!hiddenInput) return;
      createPicker(input, hiddenInput);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

})();