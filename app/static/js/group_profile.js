document.addEventListener('DOMContentLoaded', function() {
    // Get all remove action buttons
    const removeButtons = document.querySelectorAll('.remove-action-btn');
    
    // Add click event listener to each button
    removeButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Get comparison and group IDs from data attributes
            const comparisonId = this.getAttribute('data-comparison-id');
            const groupId = this.getAttribute('data-group-id');
            
            if (!confirm('Are you sure you want to remove this article from the group?')) {
                return;
            }
            
            // Send API request to remove action
            fetch('/groups/remove_action', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.csrfToken
                },
                body: JSON.stringify({
                    comparison_id: comparisonId,
                    group_id: groupId
                })
            })
            .then(response => {
                console.log(`Response status: ${response.status}`);
                // Check if response is ok before trying to parse JSON
                if (!response.ok) {
                    // Try to get the error message from the response
                    return response.json().then(errorData => {
                        console.error('Server error response:', errorData);
                        throw new Error(`Server responded with status: ${response.status}. Message: ${errorData.message || 'Unknown error'}`);
                    }).catch(jsonError => {
                        // If JSON parsing fails, throw the original error
                        console.error('Failed to parse error response:', jsonError);
                        throw new Error(`Server responded with status: ${response.status}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    // Remove the row from the table
                    const row = this.closest('tr');
                    row.remove();
                    
                    // Show success message
                    const alertDiv = document.createElement('div');
                    alertDiv.className = 'alert alert-success';
                    alertDiv.textContent = data.message || 'Article removed successfully';
                    
                    // Add alert to the page
                    const tableContainer = document.querySelector('.table-responsive');
                    tableContainer.parentNode.insertBefore(alertDiv, tableContainer);
                    
                    // Auto-dismiss alert after 3 seconds
                    setTimeout(() => {
                        alertDiv.remove();
                    }, 3000);
                    
                    // If no more comparisons, show the "No actions" message
                    const tableRows = document.querySelectorAll('tbody tr');
                    if (tableRows.length === 0) {
                        const tableResponsive = document.querySelector('.table-responsive');
                        tableResponsive.innerHTML = `
                            <div class="alert alert-info">
                                No actions have been added to this group yet.
                            </div>
                        `;
                    }
                } else {
                    // Show error message
                    alert(data.message || 'Failed to remove article');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred while removing the article');
            });
        });
    });
});