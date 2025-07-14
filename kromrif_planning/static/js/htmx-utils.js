/**
 * HTMX Utilities for Kromrif Planning
 * Enhanced interactivity patterns and helper functions
 */

// Progressive Enhancement Detection
document.documentElement.classList.remove('no-js');
document.documentElement.classList.add('js');

// Global HTMX configuration
document.addEventListener('DOMContentLoaded', function() {
    
    // Configure HTMX
    htmx.config.defaultSwapStyle = 'innerHTML';
    htmx.config.defaultSwapDelay = 0;
    htmx.config.defaultSettleDelay = 20;
    htmx.config.historyCacheSize = 10;
    htmx.config.refreshOnHistoryMiss = false;
    htmx.config.defaultFocusScroll = false;
    htmx.config.getCacheBusterParam = false;
    htmx.config.globalViewTransitions = false;
    htmx.config.methodsThatUseUrlParams = ["get"];
    htmx.config.selfRequestsOnly = false;
    htmx.config.ignoreTitle = false;
    htmx.config.scrollBehavior = 'smooth';
    htmx.config.defaultIndicatorClass = 'htmx-indicator';
    htmx.config.includeIndicatorStyles = false;
    
    // Set up global HTMX event handlers
    setupGlobalEventHandlers();
    
    // Initialize enhanced features
    initializeProgressiveEnhancement();
    initializeAutoRefresh();
    initializeFormValidation();
    initializeTooltips();
    initializeKeyboardShortcuts();
    initializeOptimisticUpdates();
});

/**
 * Initialize progressive enhancement features
 */
function initializeProgressiveEnhancement() {
    // Add graceful degradation classes
    document.body.classList.add('js-enabled');
    
    // Show JS-only elements
    document.querySelectorAll('.js-only').forEach(el => {
        el.style.display = '';
    });
    
    // Hide fallback content
    document.querySelectorAll('.js-fallback').forEach(el => {
        el.style.display = 'none';
    });
    
    // Enable enhanced form elements
    document.querySelectorAll('.js-enhanced').forEach(el => {
        el.classList.remove('opacity-50', 'pointer-events-none');
    });
    
    // Initialize enhanced navigation
    initializeEnhancedNavigation();
    
    // Initialize enhanced interactions
    initializeEnhancedInteractions();
    
    console.log('Progressive enhancement initialized');
}

/**
 * Initialize enhanced navigation with smooth transitions
 */
function initializeEnhancedNavigation() {
    document.querySelectorAll('.nav-link-enhanced').forEach(link => {
        // Add active state based on current URL
        if (link.href === window.location.href) {
            link.classList.add('active');
        }
        
        // Add hover effects
        link.addEventListener('mouseenter', function() {
            this.classList.add('hover');
        });
        
        link.addEventListener('mouseleave', function() {
            this.classList.remove('hover');
        });
    });
}

/**
 * Initialize enhanced interactions (hover effects, press effects, etc.)
 */
function initializeEnhancedInteractions() {
    // Add enhanced classes to buttons and cards
    document.querySelectorAll('button:not(.btn-enhanced)').forEach(btn => {
        btn.classList.add('btn-enhanced', 'press-effect');
    });
    
    document.querySelectorAll('.card:not(.card-enhanced)').forEach(card => {
        card.classList.add('card-enhanced', 'hover-lift');
    });
    
    // Add focus ring to interactive elements
    document.querySelectorAll('a, button, input, select, textarea').forEach(el => {
        if (!el.classList.contains('focus-ring')) {
            el.classList.add('focus-ring');
        }
    });
}

/**
 * Initialize optimistic UI updates
 */
function initializeOptimisticUpdates() {
    // Listen for form submissions to provide optimistic feedback
    document.body.addEventListener('htmx:beforeRequest', function(evt) {
        const element = evt.detail.elt;
        const verb = evt.detail.requestConfig.verb;
        
        // Apply optimistic update for non-GET requests
        if (verb !== 'get') {
            applyOptimisticUpdate(element, verb);
        }
    });
    
    // Handle successful responses
    document.body.addEventListener('htmx:afterRequest', function(evt) {
        const element = evt.detail.elt;
        const successful = evt.detail.successful;
        
        if (successful) {
            showOptimisticSuccess(element);
        } else {
            showOptimisticError(element);
        }
        
        // Remove optimistic state after animation
        setTimeout(() => {
            clearOptimisticState(element);
        }, 1000);
    });
}

/**
 * Apply optimistic update to element
 */
function applyOptimisticUpdate(element, verb) {
    // Add optimistic update class
    element.classList.add('optimistic-update');
    
    // For delete operations, add visual feedback
    if (verb === 'delete') {
        element.style.opacity = '0.5';
        element.style.transform = 'scale(0.95)';
    }
    
    // For form submissions, disable form temporarily
    if (element.tagName === 'FORM') {
        disableForm(element);
    }
}

/**
 * Show optimistic success state
 */
function showOptimisticSuccess(element) {
    element.classList.remove('optimistic-update');
    element.classList.add('optimistic-success');
    
    // Add success animation
    element.style.animation = 'successPulse 0.6s ease-out';
}

/**
 * Show optimistic error state
 */
function showOptimisticError(element) {
    element.classList.remove('optimistic-update');
    element.classList.add('optimistic-error');
    
    // Add error animation
    element.style.animation = 'errorShake 0.6s ease-out';
    
    // Re-enable form if it was disabled
    if (element.tagName === 'FORM') {
        enableForm(element);
    }
}

/**
 * Clear optimistic state
 */
function clearOptimisticState(element) {
    element.classList.remove('optimistic-update', 'optimistic-success', 'optimistic-error');
    element.style.opacity = '';
    element.style.transform = '';
    element.style.animation = '';
}

/**
 * Set up global HTMX event handlers
 */
function setupGlobalEventHandlers() {
    
    // Loading states
    document.body.addEventListener('htmx:beforeRequest', function(evt) {
        showLoadingState(evt.detail.elt);
    });
    
    document.body.addEventListener('htmx:afterRequest', function(evt) {
        hideLoadingState(evt.detail.elt);
        
        // Handle errors
        if (evt.detail.xhr.status >= 400) {
            handleRequestError(evt);
        }
    });
    
    // Success handling
    document.body.addEventListener('htmx:afterSwap', function(evt) {
        // Re-initialize Alpine.js components
        if (window.Alpine) {
            Alpine.initTree(evt.detail.target);
        }
        
        // Show success messages
        if (evt.detail.xhr.status >= 200 && evt.detail.xhr.status < 300) {
            handleRequestSuccess(evt);
        }
        
        // Auto-focus first input in forms
        autoFocusFirstInput(evt.detail.target);
        
        // Initialize any new tooltips
        initializeTooltips(evt.detail.target);
    });
    
    // Form submission handling
    document.body.addEventListener('htmx:beforeRequest', function(evt) {
        if (evt.detail.elt.tagName === 'FORM') {
            // Clear previous error states
            clearFormErrors(evt.detail.elt);
            
            // Disable form during submission
            disableForm(evt.detail.elt);
        }
    });
    
    document.body.addEventListener('htmx:afterRequest', function(evt) {
        if (evt.detail.elt.tagName === 'FORM') {
            // Re-enable form
            enableForm(evt.detail.elt);
        }
    });
    
    // Modal handling
    document.body.addEventListener('htmx:afterSwap', function(evt) {
        // Auto-open modals if they contain content
        const modals = evt.detail.target.querySelectorAll('[id$="-modal"]');
        modals.forEach(modal => {
            if (modal.innerHTML.trim() && modal.classList.contains('hidden')) {
                openModal(modal.id);
            }
        });
    });
    
    // History handling
    document.body.addEventListener('htmx:pushedIntoHistory', function(evt) {
        // Update page title if provided
        const title = evt.detail.path.title;
        if (title) {
            document.title = title;
        }
    });
    
    // Error handling
    document.body.addEventListener('htmx:responseError', function(evt) {
        showNotification('Error: ' + evt.detail.xhr.statusText, 'error');
    });
    
    document.body.addEventListener('htmx:sendError', function(evt) {
        showNotification('Network error. Please check your connection.', 'error');
    });
    
    document.body.addEventListener('htmx:timeout', function(evt) {
        showNotification('Request timed out. Please try again.', 'warning');
    });
}

/**
 * Show loading state for element
 */
function showLoadingState(element) {
    // Add loading class
    element.classList.add('htmx-loading');
    
    // Disable buttons and inputs
    if (element.tagName === 'BUTTON' || element.tagName === 'INPUT') {
        element.disabled = true;
        element.dataset.originalText = element.textContent || element.value;
        
        if (element.tagName === 'BUTTON') {
            element.innerHTML = '<svg class="animate-spin h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>Loading...';
        }
    }
    
    // Show global loading indicator
    const indicator = document.getElementById('htmx-indicator');
    if (indicator) {
        indicator.style.display = 'block';
    }
}

/**
 * Hide loading state for element
 */
function hideLoadingState(element) {
    // Remove loading class
    element.classList.remove('htmx-loading');
    
    // Re-enable buttons and inputs
    if (element.tagName === 'BUTTON' || element.tagName === 'INPUT') {
        element.disabled = false;
        
        if (element.dataset.originalText && element.tagName === 'BUTTON') {
            element.textContent = element.dataset.originalText;
            delete element.dataset.originalText;
        }
    }
    
    // Hide global loading indicator
    const indicator = document.getElementById('htmx-indicator');
    if (indicator) {
        indicator.style.display = 'none';
    }
}

/**
 * Handle request errors
 */
function handleRequestError(evt) {
    const status = evt.detail.xhr.status;
    let message = 'An error occurred';
    
    switch (status) {
        case 400:
            message = 'Invalid request. Please check your input.';
            break;
        case 401:
            message = 'Please log in to continue.';
            window.location.href = '/accounts/login/';
            return;
        case 403:
            message = 'You do not have permission to perform this action.';
            break;
        case 404:
            message = 'The requested resource was not found.';
            break;
        case 422:
            // Validation errors - these are usually handled by the form
            return;
        case 500:
            message = 'Server error. Please try again later.';
            break;
        default:
            message = `Error ${status}: ${evt.detail.xhr.statusText}`;
    }
    
    showNotification(message, 'error');
}

/**
 * Handle request success
 */
function handleRequestSuccess(evt) {
    // Look for success messages in response headers
    const successMessage = evt.detail.xhr.getResponseHeader('HX-Success-Message');
    if (successMessage) {
        showNotification(successMessage, 'success');
    }
    
    // Auto-close modals on successful form submission
    if (evt.detail.elt.tagName === 'FORM') {
        const modal = evt.detail.elt.closest('[id$="-modal"]');
        if (modal) {
            setTimeout(() => closeModal(modal.id), 1000);
        }
    }
}

/**
 * Show notification
 */
function showNotification(message, type = 'info', duration = 5000) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 max-w-sm w-full z-50 transform transition-all duration-300 translate-x-full`;
    
    const bgColor = {
        'success': 'bg-green-500',
        'error': 'bg-red-500',
        'warning': 'bg-yellow-500',
        'info': 'bg-blue-500'
    }[type] || 'bg-blue-500';
    
    notification.innerHTML = `
        <div class="${bgColor} text-white px-6 py-4 rounded-lg shadow-lg">
            <div class="flex items-center justify-between">
                <span class="font-medium">${message}</span>
                <button onclick="this.parentElement.parentElement.remove()" class="ml-4 text-white hover:text-gray-200">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(() => {
        notification.classList.remove('translate-x-full');
    }, 10);
    
    // Auto-remove
    setTimeout(() => {
        notification.classList.add('translate-x-full');
        setTimeout(() => notification.remove(), 300);
    }, duration);
}

/**
 * Modal utilities
 */
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('hidden');
        
        // Focus first input
        const firstInput = modal.querySelector('input, select, textarea');
        if (firstInput) {
            setTimeout(() => firstInput.focus(), 100);
        }
        
        // Prevent body scroll
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('hidden');
        
        // Restore body scroll
        document.body.style.overflow = '';
        
        // Clear modal content if it's dynamic
        const content = modal.querySelector('[id$="-content"]');
        if (content) {
            content.innerHTML = '';
        }
    }
}

/**
 * Form utilities
 */
function clearFormErrors(form) {
    // Remove error classes and messages
    form.querySelectorAll('.border-red-300, .text-red-600').forEach(el => {
        el.classList.remove('border-red-300', 'text-red-600');
    });
    
    form.querySelectorAll('.form-error').forEach(el => {
        el.remove();
    });
}

function disableForm(form) {
    form.querySelectorAll('input, select, textarea, button').forEach(el => {
        if (!el.disabled) {
            el.disabled = true;
            el.dataset.wasEnabled = 'true';
        }
    });
}

function enableForm(form) {
    form.querySelectorAll('input, select, textarea, button').forEach(el => {
        if (el.dataset.wasEnabled) {
            el.disabled = false;
            delete el.dataset.wasEnabled;
        }
    });
}

function autoFocusFirstInput(container) {
    const firstInput = container.querySelector('input:not([type="hidden"]), select, textarea');
    if (firstInput && !firstInput.disabled) {
        setTimeout(() => firstInput.focus(), 100);
    }
}

/**
 * Initialize auto-refresh for dynamic content
 */
function initializeAutoRefresh() {
    // Auto-refresh elements with data-auto-refresh attribute
    document.querySelectorAll('[data-auto-refresh]').forEach(element => {
        const interval = parseInt(element.dataset.autoRefresh) || 30000; // Default 30 seconds
        const url = element.dataset.refreshUrl || window.location.pathname;
        
        setInterval(() => {
            htmx.ajax('GET', url, {
                target: element,
                swap: 'innerHTML'
            });
        }, interval);
    });
}

/**
 * Initialize enhanced form validation
 */
function initializeFormValidation() {
    // Real-time validation for forms with data-validate attribute
    document.querySelectorAll('form[data-validate]').forEach(form => {
        form.querySelectorAll('input, select, textarea').forEach(field => {
            field.addEventListener('blur', function() {
                validateField(this);
            });
            
            field.addEventListener('input', function() {
                // Clear errors on input
                clearFieldError(this);
            });
        });
    });
}

function validateField(field) {
    const value = field.value.trim();
    const type = field.type;
    const required = field.required;
    
    // Clear previous errors
    clearFieldError(field);
    
    // Required validation
    if (required && !value) {
        showFieldError(field, 'This field is required.');
        return false;
    }
    
    // Type-specific validation
    if (value) {
        switch (type) {
            case 'email':
                if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
                    showFieldError(field, 'Please enter a valid email address.');
                    return false;
                }
                break;
            case 'url':
                if (!/^https?:\/\/.+/.test(value)) {
                    showFieldError(field, 'Please enter a valid URL.');
                    return false;
                }
                break;
            case 'number':
                if (isNaN(value)) {
                    showFieldError(field, 'Please enter a valid number.');
                    return false;
                }
                break;
        }
    }
    
    return true;
}

function showFieldError(field, message) {
    field.classList.add('border-red-300');
    
    const errorElement = document.createElement('p');
    errorElement.className = 'mt-2 text-sm text-red-600 form-error';
    errorElement.textContent = message;
    
    field.parentElement.appendChild(errorElement);
}

function clearFieldError(field) {
    field.classList.remove('border-red-300');
    const errorElement = field.parentElement.querySelector('.form-error');
    if (errorElement) {
        errorElement.remove();
    }
}

/**
 * Initialize tooltips
 */
function initializeTooltips(container = document) {
    container.querySelectorAll('[data-tooltip]').forEach(element => {
        const tooltip = element.dataset.tooltip;
        const position = element.dataset.tooltipPosition || 'top';
        
        element.addEventListener('mouseenter', function() {
            showTooltip(this, tooltip, position);
        });
        
        element.addEventListener('mouseleave', function() {
            hideTooltip();
        });
    });
}

function showTooltip(element, text, position) {
    const tooltip = document.createElement('div');
    tooltip.id = 'tooltip';
    tooltip.className = `absolute z-50 px-3 py-2 text-sm text-white bg-gray-900 rounded-md shadow-lg pointer-events-none`;
    tooltip.textContent = text;
    
    document.body.appendChild(tooltip);
    
    const rect = element.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();
    
    let top, left;
    
    switch (position) {
        case 'top':
            top = rect.top - tooltipRect.height - 8;
            left = rect.left + (rect.width - tooltipRect.width) / 2;
            break;
        case 'bottom':
            top = rect.bottom + 8;
            left = rect.left + (rect.width - tooltipRect.width) / 2;
            break;
        case 'left':
            top = rect.top + (rect.height - tooltipRect.height) / 2;
            left = rect.left - tooltipRect.width - 8;
            break;
        case 'right':
            top = rect.top + (rect.height - tooltipRect.height) / 2;
            left = rect.right + 8;
            break;
    }
    
    tooltip.style.top = `${top}px`;
    tooltip.style.left = `${left}px`;
    
    // Animate in
    tooltip.style.opacity = '0';
    tooltip.style.transform = 'scale(0.95)';
    setTimeout(() => {
        tooltip.style.opacity = '1';
        tooltip.style.transform = 'scale(1)';
        tooltip.style.transition = 'opacity 0.2s, transform 0.2s';
    }, 10);
}

function hideTooltip() {
    const tooltip = document.getElementById('tooltip');
    if (tooltip) {
        tooltip.remove();
    }
}

/**
 * Initialize keyboard shortcuts
 */
function initializeKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Escape key closes modals
        if (e.key === 'Escape') {
            const openModal = document.querySelector('[id$="-modal"]:not(.hidden)');
            if (openModal) {
                closeModal(openModal.id);
                e.preventDefault();
            }
        }
        
        // Ctrl/Cmd + K for search
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            const searchInput = document.querySelector('input[type="search"], input[name="search"]');
            if (searchInput) {
                searchInput.focus();
                e.preventDefault();
            }
        }
        
        // Ctrl/Cmd + Enter to submit forms
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            const activeElement = document.activeElement;
            if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA')) {
                const form = activeElement.closest('form');
                if (form) {
                    form.dispatchEvent(new Event('submit', { bubbles: true }));
                    e.preventDefault();
                }
            }
        }
    });
}

/**
 * Utility functions for common patterns
 */
window.KromrifUtils = {
    showNotification,
    openModal,
    closeModal,
    validateField,
    showTooltip,
    hideTooltip,
    
    // Bulk actions
    selectAll: function(checkbox) {
        const checkboxes = document.querySelectorAll('input[type="checkbox"][name="selected_items"]');
        checkboxes.forEach(cb => cb.checked = checkbox.checked);
    },
    
    // Confirm actions
    confirm: function(message, callback) {
        if (window.confirm(message)) {
            callback();
        }
    },
    
    // Auto-save functionality
    autoSave: function(form, url, interval = 30000) {
        setInterval(() => {
            const formData = new FormData(form);
            htmx.ajax('POST', url, {
                values: formData,
                headers: {
                    'X-Auto-Save': 'true'
                }
            });
        }, interval);
    },
    
    // Copy to clipboard
    copyToClipboard: function(text) {
        navigator.clipboard.writeText(text).then(() => {
            showNotification('Copied to clipboard!', 'success', 2000);
        });
    }
};