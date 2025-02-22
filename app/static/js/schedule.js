// Add event listener for disabling schedule
document.addEventListener('DOMContentLoaded', function() {
    // ... existing code ...
    document.querySelectorAll('.disable-schedule').forEach(button => {
        button.addEventListener('click', async function() {
            const scheduleId = this.getAttribute('data-schedule-id');
            if (confirm('Are you sure you want to disable this schedule?')) {
                try {
                    const response = await fetch(`/disable_schedule/${scheduleId}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': window.csrfToken  
                        }
                    });
                    const result = await response.json();
                    if (result.status === 'success') {
                        window.location.reload();
                    } else {
                        alert(result.message);
                    }
                } catch (error) {
                    alert('An error occurred while disabling the schedule');
                }
            }
        });
    });
});