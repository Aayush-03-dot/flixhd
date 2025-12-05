// This is the only code that should be in your static/js/script.js file

document.addEventListener('DOMContentLoaded', () => {
    
    // This code finds the new animated toast notification
    const toastNotification = document.querySelector('.toast-notification');

    // If the toast exists on the page (because Flask flashed a message)...
    if (toastNotification) {
        
        // 1. After a brief moment, add the 'show' class to trigger the slide-in animation.
        setTimeout(() => {
            toastNotification.classList.add('show');
        }, 100); // 100ms delay

        // 2. After 5 seconds, remove the 'show' class to trigger the slide-out animation.
        setTimeout(() => {
            toastNotification.classList.remove('show');
        }, 5000); // 5000ms = 5 seconds
    }
    
});