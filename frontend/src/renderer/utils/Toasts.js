/**
 * Toast Notification System
 * Displays temporary toast notifications with color-coded severity levels
 * 
 * Usage:
 *   showToast('Operation successful!', 'success');
 *   showToast('Please check your input', 'warning');
 *   showToast('Failed to save data', 'error');
 */

// Toast container element (created once)
let toastContainer = null;

// Toast configuration
const TOAST_CONFIG = {
  duration: 4000, // Default display duration in ms
  maxToasts: 5,   // Maximum number of toasts visible at once
};

// Color schemes for different toast types
const TOAST_STYLES = {
  success: {
    background: '#10b981', // Green
    icon: '✓',
  },
  warning: {
    background: '#f59e0b', // Orange
    icon: '⚠',
  },
  error: {
    background: '#ef4444', // Red
    icon: '✕',
  },
  info: {
    background: '#3b82f6', // Blue
    icon: 'ℹ',
  },
};

/**
 * Initialize the toast container
 */
function initToastContainer() {
  if (toastContainer) return;

  toastContainer = document.createElement('div');
  toastContainer.id = 'toast-container';
  toastContainer.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 10000;
    display: flex;
    flex-direction: column;
    gap: 10px;
    pointer-events: none;
  `;
  document.body.appendChild(toastContainer);
}

/**
 * Show a toast notification
 * @param {string} message - The message to display
 * @param {string} type - Toast type: 'success', 'warning', 'error', or 'info'
 * @param {number} duration - Optional duration in ms (defaults to 4000)
 */
export function showToast(message, type = 'info', duration = TOAST_CONFIG.duration) {
  initToastContainer();

  // Limit number of visible toasts
  const existingToasts = toastContainer.querySelectorAll('.toast');
  if (existingToasts.length >= TOAST_CONFIG.maxToasts) {
    existingToasts[0].remove();
  }

  const style = TOAST_STYLES[type] || TOAST_STYLES.info;

  // Create toast element
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.style.cssText = `
    background: ${style.background};
    color: white;
    padding: 12px 16px;
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 250px;
    max-width: 400px;
    pointer-events: auto;
    animation: slideIn 0.3s ease-out;
    font-size: 14px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    opacity: 1;
    transition: opacity 0.3s ease-out;
  `;

  // Icon
  const icon = document.createElement('span');
  icon.style.cssText = `
    font-size: 18px;
    font-weight: bold;
    flex-shrink: 0;
  `;
  icon.textContent = style.icon;

  // Message
  const messageEl = document.createElement('span');
  messageEl.style.cssText = `
    flex: 1;
    word-wrap: break-word;
  `;
  messageEl.textContent = message;

  // Close button
  const closeBtn = document.createElement('button');
  closeBtn.style.cssText = `
    background: transparent;
    border: none;
    color: white;
    font-size: 18px;
    cursor: pointer;
    padding: 0;
    margin-left: 8px;
    opacity: 0.7;
    transition: opacity 0.2s;
    flex-shrink: 0;
  `;
  closeBtn.textContent = '×';
  closeBtn.onmouseover = () => closeBtn.style.opacity = '1';
  closeBtn.onmouseout = () => closeBtn.style.opacity = '0.7';
  closeBtn.onclick = () => removeToast(toast);

  // Assemble toast
  toast.appendChild(icon);
  toast.appendChild(messageEl);
  toast.appendChild(closeBtn);

  // Add to container
  toastContainer.appendChild(toast);

  // Auto-remove after duration
  setTimeout(() => {
    removeToast(toast);
  }, duration);
}

/**
 * Remove a toast with fade-out animation
 */
function removeToast(toast) {
  if (!toast || !toast.parentElement) return;

  toast.style.opacity = '0';
  toast.style.transform = 'translateX(400px)';
  
  setTimeout(() => {
    if (toast.parentElement) {
      toast.remove();
    }
  }, 300);
}

/**
 * Clear all toasts
 */
export function clearAllToasts() {
  if (!toastContainer) return;
  
  const toasts = toastContainer.querySelectorAll('.toast');
  toasts.forEach(toast => removeToast(toast));
}

// Add CSS keyframes for slide-in animation
if (typeof document !== 'undefined') {
  const style = document.createElement('style');
  style.textContent = `
    @keyframes slideIn {
      from {
        transform: translateX(400px);
        opacity: 0;
      }
      to {
        transform: translateX(0);
        opacity: 1;
      }
    }
  `;
  document.head.appendChild(style);
}

// Export default for convenience
export default showToast;
