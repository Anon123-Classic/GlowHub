document.addEventListener('DOMContentLoaded', function() {
    initToasts();
    initBookingFlow();
    initDeleteConfirmations();
    initPasswordToggle();
    initChartsFromData();
});

function initToasts() {
    var toastEls = document.querySelectorAll('.toast');
    toastEls.forEach(function(el) {
        var toast = new bootstrap.Toast(el);
        toast.show();
    });
}

function initBookingFlow() {
    var dateInput = document.getElementById('id_date');
    var timeContainer = document.getElementById('time-slots-container');
    var timeInput = document.getElementById('id_time');
    var loadingEl = document.getElementById('slots-loading');
    var bookForm = document.getElementById('booking-form');

    if (!dateInput || !timeContainer) return;

    var slotsUrl = dateInput.dataset.slotsUrl || '/get-slots/';

    function fetchSlots(date) {
        if (!date) return;
        if (loadingEl) loadingEl.style.display = 'block';
        timeContainer.innerHTML = '';
        if (timeInput) timeInput.value = '';

        fetch(slotsUrl + '?date=' + date)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (loadingEl) loadingEl.style.display = 'none';
                if (data.slots && data.slots.length > 0) {
                    var hasAvailable = false;
                    data.slots.forEach(function(slot) {
                        var btn = document.createElement('button');
                        btn.type = 'button';
                        btn.className = 'time-slot-btn';
                        btn.dataset.time = slot.time;
                        btn.textContent = slot.display;
                        if (slot.available) {
                            btn.classList.add('available');
                            hasAvailable = true;
                        } else {
                            btn.classList.add('disabled');
                        }
                        btn.addEventListener('click', function() {
                            if (this.classList.contains('disabled')) return;
                            document.querySelectorAll('.time-slot-btn.selected').forEach(function(b) {
                                b.classList.remove('selected');
                            });
                            this.classList.add('selected');
                            if (timeInput) timeInput.value = this.dataset.time;
                        });
                        timeContainer.appendChild(btn);
                    });
                    if (!hasAvailable) {
                        timeContainer.innerHTML = '<div class="alert alert-warning text-center">No available slots for this date.</div>';
                    }
                } else {
                    timeContainer.innerHTML = '<div class="alert alert-info text-center">No time slots available for this date.</div>';
                }
            })
            .catch(function() {
                if (loadingEl) loadingEl.style.display = 'none';
                timeContainer.innerHTML = '<div class="alert alert-danger text-center">Failed to load time slots.</div>';
            });
    }

    dateInput.addEventListener('change', function() {
        fetchSlots(this.value);
    });

    if (dateInput.value) {
        fetchSlots(dateInput.value);
    }

    updateServiceSummary();

    var serviceSelect = document.getElementById('id_service');
    if (serviceSelect) {
        serviceSelect.addEventListener('change', updateServiceSummary);
    }

    if (bookForm) {
        bookForm.addEventListener('submit', function(e) {
            if (timeInput && !timeInput.value && dateInput.value) {
                var selected = document.querySelector('.time-slot-btn.selected');
                if (!selected) {
                    e.preventDefault();
                    alert('Please select a time slot.');
                    return;
                }
            }
            var submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="loading-spinner me-2"></span> Booking...';
            }
        });
    }
}

function updateServiceSummary() {
    var select = document.getElementById('id_service');
    var nameEl = document.getElementById('selected-service-name');
    var priceEl = document.getElementById('selected-service-price');
    var durationEl = document.getElementById('selected-service-duration');
    var descEl = document.getElementById('selected-service-description');
    if (!select || !nameEl) return;
    var option = select.options[select.selectedIndex];
    if (option && option.value) {
        nameEl.textContent = option.textContent;
        priceEl.textContent = 'Ksh ' + option.dataset.price;
        durationEl.textContent = option.dataset.duration + ' min';
        descEl.textContent = option.dataset.description || 'No description available.';
    } else {
        nameEl.textContent = 'Select a service';
        priceEl.textContent = '—';
        durationEl.textContent = '—';
        descEl.textContent = 'Choose a service to preview details.';
    }
}

function initDeleteConfirmations() {
    document.querySelectorAll('[data-confirm]').forEach(function(el) {
        el.addEventListener('click', function(e) {
            if (!confirm(this.dataset.confirm || 'Are you sure?')) {
                e.preventDefault();
            }
        });
    });
}

function initPasswordToggle() {
    document.querySelectorAll('.password-toggle').forEach(function(toggle) {
        toggle.addEventListener('click', function() {
            var input = this.parentElement.querySelector('input');
            if (!input) return;
            if (input.type === 'password') {
                input.type = 'text';
                this.classList.remove('bi-eye');
                this.classList.add('bi-eye-slash');
            } else {
                input.type = 'password';
                this.classList.remove('bi-eye-slash');
                this.classList.add('bi-eye');
            }
        });
    });
}

function initChartsFromData() {
    var canvas = document.getElementById('bookingsChart');
    if (!canvas) return;
    try {
        var labels = JSON.parse(canvas.dataset.labels || '[]');
        var counts = JSON.parse(canvas.dataset.counts || '[]');
        if (labels.length && counts.length) {
            initCharts(labels, counts);
        }
    } catch(e) {}
}

function initCharts(labels, counts) {
    var canvas = document.getElementById('bookingsChart');
    if (!canvas) return;

    var ctx = canvas.getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Bookings',
                data: counts,
                backgroundColor: 'rgba(111, 66, 193, 0.2)',
                borderColor: '#6f42c1',
                borderWidth: 2,
                borderRadius: 6,
                barPercentage: 0.6,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { stepSize: 1, font: { size: 12 } },
                    grid: { color: 'rgba(0,0,0,0.05)' }
                },
                x: {
                    grid: { display: false },
                    ticks: { font: { size: 12 } }
                }
            }
        }
    });
}
