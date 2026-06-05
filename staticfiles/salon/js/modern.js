// ============================================
// SMART SALON - MODERN UI ENHANCEMENTS
// Interactive animations, smooth scrolling, and UX improvements
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all components
    initScrollAnimations();
    initSmoothScroll();
    initFormEnhancements();
    initToastNotifications();
    initMobileMenu();
    initHoverEffects();
    initLazyLoading();
});

/**
 * Scroll Animations - Elements fade in as they come into view
 */
function initScrollAnimations() {
    const elements = document.querySelectorAll('[class*="animate-"]');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0) translateX(0) scale(1)';
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });

    elements.forEach(el => {
        // Skip carousel items: CSS animation handles entrance, IntersectionObserver
        // conflicts with Bootstrap's display:none/flex toggling on slides.
        if (el.closest('.carousel-item')) {
            return;
        }

        el.style.opacity = '0';
        
        if (el.classList.contains('animate-fade-in-up')) {
            el.style.transform = 'translateY(30px)';
        } else if (el.classList.contains('animate-slide-in-left')) {
            el.style.transform = 'translateX(-40px)';
        } else if (el.classList.contains('animate-slide-in-right')) {
            el.style.transform = 'translateX(40px)';
        } else if (el.classList.contains('animate-scale-in')) {
            el.style.transform = 'scale(0.9)';
        }
        
        el.style.transition = 'all 0.6s cubic-bezier(0.4, 0, 0.2, 1)';
        observer.observe(el);
    });
}

/**
 * Smooth Scroll Behavior
 */
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href === '#') return;
            
            e.preventDefault();
            const target = document.querySelector(href);
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

/**
 * Form Enhancements
 */
function initFormEnhancements() {
    // Floating label animation
    const inputs = document.querySelectorAll('.form-control-modern, .floating-label input');
    inputs.forEach(input => {
        input.addEventListener('focus', function() {
            this.style.borderColor = '#7C3AED';
            this.style.boxShadow = '0 0 0 3px rgba(124, 58, 237, 0.1)';
        });
        
        input.addEventListener('blur', function() {
            if (!this.value) {
                this.style.borderColor = '#E5E7EB';
                this.style.boxShadow = 'none';
            }
        });

        // Validate input in real-time
        if (input.type === 'email') {
            input.addEventListener('change', function() {
                const isValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(this.value);
                this.style.borderColor = isValid ? '#10B981' : '#EF4444';
            });
        }
    });

    // Form submission feedback
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                const originalText = submitBtn.innerHTML;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
                submitBtn.disabled = true;

                setTimeout(() => {
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }, 1000);
            }
        });
    });
}

/**
 * Toast Notifications
 */
function initToastNotifications() {
    const toastElements = document.querySelectorAll('.toast');
    toastElements.forEach(toastElement => {
        const toast = new bootstrap.Toast(toastElement, {
            autohide: true,
            delay: 5000
        });

        // Add enter animation
        toastElement.style.animation = 'slideInRight 0.3s ease-out';
        
        // Auto-dismiss with animation
        toastElement.addEventListener('hidden.bs.toast', function() {
            this.style.animation = 'slideOutRight 0.3s ease-out';
        });

        toast.show();
    });
}

/**
 * Mobile Menu Toggle
 */
function initMobileMenu() {
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbarCollapse = document.querySelector('.navbar-collapse');

    if (navbarToggler) {
        navbarToggler.addEventListener('click', function() {
            navbarCollapse?.classList.toggle('show');
        });

        // Close menu when a link is clicked
        document.querySelectorAll('.navbar-collapse a').forEach(link => {
            link.addEventListener('click', function() {
                navbarCollapse?.classList.remove('show');
            });
        });
    }
}

/**
 * Hover Effects
 */
function initHoverEffects() {
    // Service cards
    document.querySelectorAll('.service-card').forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-10px)';
            this.style.boxShadow = '0 20px 40px rgba(124, 58, 237, 0.2)';
        });

        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = '0 10px 25px rgba(124, 58, 237, 0.15)';
        });
    });

    // Buttons
    document.querySelectorAll('.btn-primary-modern, .btn-secondary-modern').forEach(btn => {
        btn.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
            this.style.boxShadow = '0 10px 25px rgba(124, 58, 237, 0.3)';
        });

        btn.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = '';
        });
    });

    // Stat cards
    document.querySelectorAll('.stat-card').forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px)';
            this.style.boxShadow = '0 10px 25px rgba(124, 58, 237, 0.15)';
        });

        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = '0 4px 6px rgba(0, 0, 0, 0.1)';
        });
    });
}

/**
 * Lazy Loading Images
 */
function initLazyLoading() {
    const images = document.querySelectorAll('img[data-src]');
    
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.style.animation = 'fadeIn 0.5s ease-in';
                    observer.unobserve(img);
                }
            });
        });

        images.forEach(img => imageObserver.observe(img));
    }
}

/**
 * Filter Services
 */
function filterServices() {
    const searchInput = document.getElementById('serviceSearch');
    const categoryFilter = document.getElementById('categoryFilter');
    const serviceItems = document.querySelectorAll('.service-item');

    if (!searchInput || !categoryFilter) return;

    const searchTerm = searchInput.value.toLowerCase();
    const categoryTerm = categoryFilter.value.toLowerCase();

    let visibleCount = 0;

    serviceItems.forEach(item => {
        const name = item.dataset.name;
        const category = item.dataset.category.toLowerCase();
        
        const matchesSearch = name.includes(searchTerm);
        const matchesCategory = categoryTerm === '' || category === categoryTerm;
        
        if (matchesSearch && matchesCategory) {
            item.style.display = 'block';
            item.style.animation = 'fadeIn 0.3s ease-out';
            visibleCount++;
        } else {
            item.style.display = 'none';
        }
    });

    // Show empty state if no results
    const emptyState = document.querySelector('.empty-state');
    if (emptyState) {
        emptyState.style.display = visibleCount === 0 ? 'block' : 'none';
    }
}

// Add event listeners for filter
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('serviceSearch');
    const categoryFilter = document.getElementById('categoryFilter');

    if (searchInput) searchInput.addEventListener('input', filterServices);
    if (categoryFilter) categoryFilter.addEventListener('change', filterServices);
});

/**
 * Booking Modal
 */
function openBookingModal(serviceId) {
    const modal = new bootstrap.Modal(document.getElementById('bookingModal'));
    document.getElementById('serviceIdInput').value = serviceId;
    modal.show();
}

/**
 * Dark Mode Toggle
 */
function toggleDarkMode() {
    const html = document.documentElement;
    const isDark = html.getAttribute('data-bs-theme') === 'dark';
    
    html.setAttribute('data-bs-theme', isDark ? 'light' : 'dark');
    localStorage.setItem('darkMode', !isDark);
}

/**
 * Loading Skeleton Animation
 */
function showLoadingSkeletons() {
    const skeletons = document.querySelectorAll('.skeleton');
    skeletons.forEach(skeleton => {
        skeleton.style.background = 'linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)';
        skeleton.style.backgroundSize = '200% 100%';
        skeleton.style.animation = 'loading 1.5s infinite';
    });
}

/**
 * Confirmation Dialog
 */
function showConfirmDialog(message, onConfirm) {
    if (confirm(message)) {
        onConfirm();
    }
}

/**
 * Copy to Clipboard
 */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard!', 'success');
    });
}

/**
 * Show Toast Message
 */
function showToast(message, type = 'info') {
    const toastContainer = document.querySelector('.toast-container') || createToastContainer();
    
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white border-0 shadow-lg`;
    toast.style.borderRadius = '12px';
    
    const bgClass = {
        'success': 'bg-success',
        'danger': 'bg-danger',
        'warning': 'bg-warning',
        'info': 'bg-info'
    }[type] || 'bg-primary';
    
    toast.classList.add(bgClass);
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="bi bi-check-circle me-2"></i>${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    const bootstrapToast = new bootstrap.Toast(toast);
    bootstrapToast.show();
    
    setTimeout(() => toast.remove(), 6000);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '9999';
    container.style.marginTop = '80px';
    document.body.appendChild(container);
    return container;
}

/**
 * Format Currency (KES)
 */
function formatKES(amount) {
    return new Intl.NumberFormat('en-KE', {
        style: 'currency',
        currency: 'KES'
    }).format(amount);
}

/**
 * Format Date
 */
function formatDate(date, format = 'short') {
    const options = format === 'short' 
        ? { year: 'numeric', month: 'short', day: 'numeric' }
        : { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' };
    
    return new Date(date).toLocaleDateString('en-KE', options);
}

/**
 * Debounce Function for search inputs
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Add CSS animations dynamically
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }

    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }

    @keyframes fadeOut {
        from { opacity: 1; }
        to { opacity: 0; }
    }

    @keyframes loading {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }

    @keyframes float {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-20px); }
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
`;
document.head.appendChild(style);

// Export functions for use in other scripts
window.SmartSalon = {
    filterServices,
    openBookingModal,
    toggleDarkMode,
    showLoadingSkeletons,
    showConfirmDialog,
    copyToClipboard,
    showToast,
    formatKES,
    formatDate,
    debounce
};
